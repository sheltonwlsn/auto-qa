import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from langgraph.graph import END, START, StateGraph
from pydantic import create_model

from common.slack import post_slack_notification
from common.utils import clean_code_fences
from graph.prompt_node import create_generation_chain, create_repair_chain

GraphState = create_model(
    "GraphState",
    input_code=(str, ...),
    file_path=(str, ...),  # relative path inside project
    test_type=(str, ...),
    framework=(str, ...),
    project_root=(str, ...),  # --project
    output_project_root=(str, ...),  # --output-project
    output_path=(str, ...),  # final file path
    generated_tests=(Optional[str], None),
    validated=(bool, False),
    approved=(bool, False),
    status=(str, "pending"),
    test_results=(Optional[str], None),
    slack_webhook=(Optional[str], None),
    retry_count=(int, 0),
)


# Prompt generation node as a chain
def generation_node(state: GraphState):  # type: ignore
    chain = create_generation_chain(state.test_type, state.framework)
    result = chain.invoke({"code": state.input_code, "file_path": state.file_path})
    return state.copy(update={"generated_tests": result.content, "status": "generating"})


def approval_node(state: GraphState):  # type: ignore
    if state.test_type == "manual":
        if state.approved:
            return state.copy(update={"status": "approved"})
        else:
            text = (
                f"*AutoQA Notification*\n"
                f"⚠️ *Workflow is awaiting approval.*\n\n"
                f"*File:* `{state.file_path}`\n"
                f"*Test Type:* {state.test_type}\n"
                f"*Framework:* {state.framework}\n"
            )
            post_slack_notification(text, webhook_url=state.slack_webhook)
            with open("pending_state.json", "w") as f:
                f.write(state.json())
            return state.copy(update={"status": "awaiting_approval"})
    else:
        return state.copy(update={"approved": True, "status": "approved"})


# Simple validation node
def validation_node(state: GraphState):  # type: ignore
    if not state.generated_tests or len(state.generated_tests.strip()) < 10:
        raise ValueError("Generated tests too short.")
    return state.copy(update={"validated": True, "status": "validating"})


# Notification node stub
def notify_node(state: GraphState):  # type: ignore
    # For MVP, just log to console
    click.echo("\n=== [AutoQA] Notification ===")
    click.echo("Test generation workflow completed.")
    click.echo(f"Test Type: {state.test_type}")
    click.echo(f"Framework: {state.framework}")
    click.echo(f"Output Path: {state.output_path}")
    click.echo(f"Status: {state.status}")
    click.echo(f"Retries: {state.retry_count}")
    click.echo("==========================\n")

    # Post to Slack
    text = (
        f"*AutoQA Notification*\n\n"
        f"*File:* `{state.file_path}`\n"
        f"*Test Type:* {state.test_type}\n"
        f"*Framework:* {state.framework}\n"
        f"*Output Path:* `{state.output_path}`\n"
        f"*Status:* {state.status}\n"
        f"*Retries:* {state.retry_count}\n"
    )

    post_slack_notification(text, webhook_url=state.slack_webhook)

    return state.copy(update={"status": "completed"})


def output_node(state: GraphState):  # type: ignore

    # Join all generated content
    output_text = (
        "\n\n".join(state.generated_tests)
        if isinstance(state.generated_tests, list)
        else state.generated_tests
    )

    # Clean code fences
    output_text = clean_code_fences(output_text)

    output_path = Path(state.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write(output_text)

    return state.copy(update={"status": "saving", "output_path": str(output_path)})


def runner_node(state: GraphState):  # type: ignore
    env = os.environ.copy()
    env["CI"] = "1"

    if state.test_type == "manual":
        return state.copy(update={"status": "skipped"})

    resolved_path = str(Path(state.output_path).resolve())

    if state.test_type == "unit":
        if state.framework == "pytest":
            pytest_path = Path(sys.executable).parent / "pytest"
            command = [str(pytest_path), resolved_path]
        elif state.framework == "jest":
            command = ["npx", "--yes", "jest", resolved_path]
        else:
            raise ValueError(f"Unsupported unit framework: {state.framework}")

    elif state.test_type == "e2e":
        if state.framework == "cypress":
            command = ["npx", "cypress", "run", "--spec", resolved_path]
        elif state.framework == "playwright":
            pytest_path = Path(sys.executable).parent / "pytest"
            command = [str(pytest_path), resolved_path]
        else:
            raise ValueError(f"Unsupported e2e framework: {state.framework}")

    else:
        raise ValueError(f"Unsupported test type: {state.test_type}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=Path(state.project_root),
            timeout=300,
            env=env,
        )
        output = result.stdout + "\n" + result.stderr
        exit_code = result.returncode
        status = "passed" if exit_code == 0 else "failed"

        return state.copy(update={"status": status, "test_results": output})

    except Exception as e:
        return state.copy(
            update={
                "status": "failed",
                "test_results": f"Error running tests: {str(e)}",
            }
        )


def repair_node(state: GraphState):  # type: ignore
    chain = create_repair_chain(state.framework)
    result = chain.invoke(
        {
            "code": state.input_code,
            "failing_tests": state.generated_tests,
            "error_output": state.test_results,
        }
    )
    return state.copy(
        update={"generated_tests": result.content, "retry_count": state.retry_count + 1}
    )


def build_workflow():
    graph = StateGraph(GraphState)
    # Add nodes
    graph.add_node("generate", generation_node)
    graph.add_node("validate", validation_node)
    graph.add_node("approve", approval_node)
    graph.add_node("save", output_node)
    graph.add_node("run", runner_node)
    graph.add_node("repair", repair_node)
    graph.add_node("notify", notify_node)

    graph.add_conditional_edges(
        START,
        lambda state: "save" if state.approved else "generate",
        {"save": "save", "generate": "generate"},
    )

    # Define edges
    graph.add_edge("generate", "validate")
    graph.add_edge("validate", "approve")
    graph.add_conditional_edges(
        "approve",
        lambda state: ("awaiting_approval" if state.status == "awaiting_approval" else "approved"),
        {
            "approved": "save",  # Continue as normal
            "awaiting_approval": END,  # Stop here
        },
    )

    graph.add_edge("save", "run")

    graph.add_conditional_edges(
        "run",
        lambda state: (
            "notify"
            if state.status == "passed"
            else "repair" if state.retry_count < 10 else "notify"
        ),
        {"notify": "notify", "repair": "repair"},
    )

    graph.add_edge("repair", "validate")
    graph.add_edge("notify", END)

    return graph.compile()


def build_repair_workflow():
    graph = StateGraph(GraphState)
    # Add nodes
    graph.add_node("run", runner_node)
    graph.add_node("repair", repair_node)
    graph.add_node("save", output_node)
    graph.add_node("notify", notify_node)

    # Define edges
    graph.set_entry_point("run")

    graph.add_conditional_edges(
        "run",
        lambda state: (
            "notify"
            if state.status == "passed"
            else "repair" if state.retry_count < 10 else "notify"
        ),
        {"notify": "notify", "repair": "repair"},
    )

    # After repair, save the fixed test file
    graph.add_edge("repair", "save")
    graph.add_edge("save", "run")
    graph.add_edge("notify", END)

    return graph.compile()
