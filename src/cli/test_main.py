import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import click
import toml
from dotenv import load_dotenv
from rich.progress import Progress

from common.utils import discover_source_files, resolve_output_path
from graph.workflow import GraphState, build_workflow

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
    click.echo("AutoQA CLI version 1.0.0")


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

    async def process_file(source_file: Path):
        relative_path = source_file.relative_to(project)
        info = file_metadata[str(source_file)]
        with open(source_file, "r") as f:
            input_code = f.read()

        effective_test_type = test_type or info.get("test_type")
        if not effective_test_type:
            raise ValueError(f"Could not determine test_type for {source_file}")

        # Determine framework
        default_frameworks = {"unit": "pytest", "e2e": "cypress", "manual": ""}

        framework = info.get("framework") or default_frameworks.get(effective_test_type, "")

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
            test_type=info["test_type"] or test_type,
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

            print(f"[AutoQA] [{relative_path}] Step ({node_name}): {current_state.status}")

            if node_name == "run":
                print("=== Test Results ===")
                print(current_state.test_results)

            final_state = current_state

        if final_state.status == "awaiting_approval":
            with open(f"pending_state_{relative_path.name}.json", "w") as f:
                f.write(final_state.model_dump_json())
            print(f"[AutoQA] [{relative_path}] Workflow awaiting approval.")
        else:
            print(f"[AutoQA] [{relative_path}] Workflow completed.")

    # Launch all workflows concurrently
    async def run_all():
        progress = Progress()
        progress.start()

        task_id = progress.add_task("[cyan]Processing files...", total=len(source_files))

        async def wrapped_process(source_file: Path):
            await process_file(source_file)
            progress.advance(task_id)

        tasks = [wrapped_process(f) for f in source_files]
        await asyncio.gather(*tasks)

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

        print(f"[AutoQA] Step ({node_name}): {step_state.status}")

        if node_name == "run":
            print("\n=== Test Results ===")
            print(step_state.test_results)

        final_state = step_state

    if final_state.status == "awaiting_approval":
        click.echo("Workflow is awaiting further approval. Saving state again.")
        with open(state, "w") as f:
            f.write(final_state.json())
    else:
        click.echo("Workflow completed.")


def test_load_config_file_exists():
    # Mock the Path.exists method to return True
    with patch("pathlib.Path.exists", return_value=True):
        # Mock the toml.load method to return a specific dictionary
        with patch("toml.load", return_value={"key": "value"}):
            config = load_config("dummy_path")
            assert config == {"key": "value"}


def test_load_config_file_does_not_exist():
    # Mock the Path.exists method to return False
    with patch("pathlib.Path.exists", return_value=False):
        config = load_config("dummy_path")
        assert config == {}


def test_load_config_default_path():
    # Mock the Path.exists method to return True
    with patch("pathlib.Path.exists", return_value=True):
        # Mock the toml.load method to return a specific dictionary
        with patch("toml.load", return_value={"default_key": "default_value"}):
            config = load_config()
            assert config == {"default_key": "default_value"}
