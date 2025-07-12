import asyncio
import json
import sys
from pathlib import Path

import click
import toml
from dotenv import load_dotenv
from rich.progress import Progress

from common.utils import discover_source_files, resolve_output_path
from graph.workflow import GraphState, build_repair_workflow, build_workflow

# Load environment variables from .env file
load_dotenv()

# Make sure Python can find the graph modules
sys.path.append(str(Path(__file__).resolve().parent.parent))


def load_config(config_path=".autoqa.toml"):
    if not Path(config_path).exists():
        return {}
    return toml.load(config_path)


@click.group()
def cli():
    """AutoQA CLI"""
    pass


@cli.command()
def version():
    """Show the current version of AutoQA."""
    click.echo("AutoQA CLI version 0.1.0")


@cli.command()
@click.option(
    "--project",
    type=click.Path(exists=True),
    required=True,
    help="Target project directory to scan.",
)
@click.option(
    "--output-project",
    type=click.Path(exists=True),
    help="Directory to write generated tests.",
)
@click.option(
    "--type",
    "test_type",
    type=click.Choice(["unit", "e2e", "manual"]),
    required=True,
    help="Type of tests to generate.",
)
@click.option(
    "--framework",
    type=click.Choice(["pytest", "jest", "playwright", "cypress"]),
    help="Framework to use.",
)
@click.option("--max-workers", default=4, help="Max parallel workflows.")
@click.option(
    "--include-dirs",
    type=click.Path(),
    multiple=True,
    help="One or more subdirectories to include (relative to project root).",
)
@click.option(
    "--exclude-dirs",
    type=click.Path(),
    multiple=True,
    help="One or more subdirectories to exclude (relative to project root).",
)
@click.option("--file-glob", type=str, help="Glob pattern to filter files (e.g., '*.service.js').")
@click.option(
    "--strip-prefix",
    type=click.Path(),
    help="Prefix to strip from input file paths when determining output paths.",
)
@click.option("--slack-webhook", type=str, help="Override Slack webhook URL.")
@click.option("--max-recursion", type=int, help="Set maximum recursion limit for LLM calls.")
def generate(
    project,
    output_project,
    test_type,
    framework,
    max_workers,
    include_dirs,
    exclude_dirs,
    file_glob,
    strip_prefix,
    slack_webhook=None,
    max_recursion=None,
):
    """Generate tests for the provided project."""
    config_defaults = load_config()

    # For example, fallback to config if CLI arg is None
    framework = framework or config_defaults.get("framework")
    output_project = output_project or config_defaults.get("output_project")
    test_type = test_type or config_defaults.get("test_type")
    if test_type != "manual" and not framework:
        click.echo(f"Error: --framework is required for {test_type} tests.")
        return

    if not framework:
        framework = ""

    click.echo(f"Scanning project: {project}")
    click.echo(f"Output project: {output_project}")

    source_files, file_metadata = discover_source_files(
        project,
        test_type,
        include_dirs=list(include_dirs) if include_dirs else None,
        exclude_dirs=list(exclude_dirs) if exclude_dirs else None,
        file_glob=file_glob,
    )

    if not source_files:
        click.echo("No source files found.")
        return

    click.echo(f"Discovered {len(source_files)} files to process.")

    async def process_file(source_file: Path, progress, task_id):
        relative_path = source_file.relative_to(project)
        info = file_metadata[str(source_file)]

        # Read file once
        with open(source_file, "r") as f:
            input_code = f.read()

        effective_test_type = test_type or info.get("test_type")
        if not effective_test_type:
            raise ValueError(f"Could not determine test_type for {source_file}")

        output_path = resolve_output_path(
            Path(project),
            Path(output_project or project),
            source_file,
            test_type,
            framework,
            strip_prefix=strip_prefix,
        )

        workflow = build_workflow()
        state = GraphState(
            input_code=input_code,
            file_path=str(relative_path),
            test_type=test_type,
            framework=framework,
            project_root=str(project),
            output_project_root=str(output_project),
            output_path=str(output_path),
            slack_webhook=slack_webhook or None,
        )

        final_state = None
        for step in workflow.stream(
            state, {"recursion_limit": max_recursion if max_recursion else 100}
        ):
            node_name, state_dict = next(iter(step.items()))
            current_state = GraphState(**state_dict)

            click.echo(f"[AutoQA] [{relative_path}] Step ({node_name}): {current_state.status}")

            if node_name == "run":
                click.echo("=== Test Results ===")
                click.echo(current_state.test_results)

            final_state = current_state

        if final_state.status == "awaiting_approval":
            with open(f"pending_state_{relative_path.name}.json", "w") as f:
                f.write(final_state.model_dump_json())
            click.echo(f"[AutoQA] [{relative_path}] Workflow awaiting approval.")
        else:
            click.echo(f"[AutoQA] [{relative_path}] Workflow completed.")

        progress.advance(task_id)

    # Launch all workflows with proper concurrency control
    async def run_all():
        progress = Progress()
        progress.start()

        task_id = progress.add_task("[cyan]Processing files...", total=len(source_files))

        # Use semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_workers)

        async def semaphore_wrapped_process(source_file: Path):
            async with semaphore:
                await process_file(source_file, progress, task_id)

        # Process files in batches to avoid overwhelming the system
        batch_size = max_workers * 2
        for i in range(0, len(source_files), batch_size):
            batch = source_files[i : i + batch_size]
            tasks = [semaphore_wrapped_process(f) for f in batch]
            await asyncio.gather(*tasks, return_exceptions=True)

        progress.stop()

    # Entry point
    asyncio.run(run_all())


@cli.command()
@click.option(
    "--state",
    type=click.Path(exists=True),
    required=True,
    help="Path to the saved state JSON file.",
)
@click.option("--slack-webhook", type=str, help="Override Slack webhook URL.")
def resume(state, slack_webhook):
    """Resume a workflow that was paused for approval."""
    click.echo(f"Loading pending state: {state}")

    with open(state, "r") as f:
        state_data = json.load(f)

    if slack_webhook:
        state_data["slack_webhook"] = slack_webhook

    current_state = GraphState(**state_data)

    if current_state.status != "awaiting_approval":
        click.echo("Error: This workflow is not awaiting approval.")
        return

    if current_state.status == "awaiting_approval":
        current_state = current_state.model_copy(update={"approved": True, "status": "approved"})

    workflow = build_workflow()
    final_state = None

    for step in workflow.stream(current_state):
        node_name, state_dict = next(iter(step.items()))
        step_state = GraphState(**state_dict)

        click.echo(f"[AutoQA] Step ({node_name}): {step_state.status}")

        if node_name == "run":
            click.echo("\n=== Test Results ===")
            click.echo(step_state.test_results)

        final_state = step_state

    if final_state.status == "awaiting_approval":
        click.echo("Workflow is awaiting further approval. Saving state again.")
        with open(state, "w") as f:
            f.write(final_state.json())
    else:
        click.echo("Workflow completed.")


@cli.command("repair-test")
@click.option(
    "--source-file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help="Source code file the tests cover.",
)
@click.option(
    "--test-file",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    required=True,
    help="Test file to repair.",
)
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help="Project root directory.",
)
@click.option(
    "--framework",
    type=click.Choice(["pytest", "jest", "cypress"]),
    required=True,
    help="Framework to use.",
)
@click.option("--max-retries", default=5, help="Maximum repair attempts.")
@click.option("--slack-webhook", type=str, help="Slack webhook URL.")
def repair_test(source_file, test_file, project_root, framework, max_retries, slack_webhook):
    """Repair a failing test file against its source code."""
    click.echo(f"Repairing test: {test_file} against source: {source_file}")

    async def process():
        with open(source_file, "r") as f:
            input_code = f.read()
        with open(test_file, "r") as f:
            test_code = f.read()

        output_path = Path(test_file)

        state = GraphState(
            input_code=input_code,
            generated_tests=test_code,
            file_path=str(Path(test_file).relative_to(project_root)),
            test_type="unit",
            framework=framework,
            project_root=str(project_root),
            output_project_root=str(project_root),
            output_path=str(output_path),
            retry_count=0,
            slack_webhook=slack_webhook,
        )

        workflow = build_repair_workflow()
        final_state = None

        for step in workflow.stream(state):
            node_name, state_dict = next(iter(step.items()))
            current_state = GraphState(**state_dict)
            click.echo(f"[AutoQA] Step: {node_name} - Status: {current_state.status}")

            if node_name == "run":
                click.echo("=== Test Results ===")
                click.echo(current_state.test_results)

            final_state = current_state

        if final_state.status == "passed":
            click.echo(f"✅ Test repaired successfully: {test_file}")
        else:
            click.echo(f"⚠️ Repair incomplete after {max_retries} retries.")

    asyncio.run(process())
