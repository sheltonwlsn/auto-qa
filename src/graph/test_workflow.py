from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Assuming the code to be tested is in 'graph/workflow.py'
# and the test file is 'graph/test_workflow.py'
from graph.workflow import (
    GraphState,
    approval_node,
    build_repair_workflow,
    build_workflow,
    output_node,
    runner_node,
    validation_node,
)


# A pytest fixture to provide a default state for tests
@pytest.fixture
def base_state():
    """Provides a basic GraphState object for testing."""
    return GraphState(
        input_code="def hello():\n    return 'world'",
        file_path="src/hello.py",
        test_type="unit",
        framework="pytest",
        project_root="/tmp/proj",
        output_project_root="/tmp/proj/output",
        output_path="/tmp/proj/output/test_hello.py",
        generated_tests="def test_hello():\n    assert hello() == 'world'",
        slack_webhook="https://hooks.slack.com/services/...",
        retry_count=0,
    )


# Test the graph building functions
def test_build_workflow_compiles():
    """Test that the main workflow graph compiles without errors."""
    workflow = build_workflow()
    # A compiled graph has 'invoke' and 'stream' methods
    assert hasattr(workflow, "invoke")
    assert hasattr(workflow, "stream")
    assert workflow is not None


def test_build_repair_workflow_compiles():
    """Test that the repair workflow graph compiles without errors."""
    repair_workflow = build_repair_workflow()
    assert hasattr(repair_workflow, "invoke")
    assert hasattr(repair_workflow, "stream")
    assert repair_workflow is not None


# Test individual nodes
def test_validation_node_success(base_state):
    """Test validation_node with valid generated tests."""
    state = base_state
    # Assuming Pydantic v2 `model_copy` is used in the corrected code
    updated_state = validation_node(state)
    assert updated_state.validated is True
    assert updated_state.status == "validating"


def test_validation_node_failure_short(base_state):
    """Test validation_node with tests that are too short."""
    state = base_state.model_copy(update={"generated_tests": "short"})
    with pytest.raises(ValueError, match="Generated tests too short."):
        validation_node(state)


def test_validation_node_failure_none(base_state):
    """Test validation_node with no generated tests."""
    state = base_state.model_copy(update={"generated_tests": None})
    with pytest.raises(ValueError, match="Generated tests too short."):
        validation_node(state)


@patch("graph.workflow.post_slack_notification")
@patch("builtins.open", new_callable=mock_open)
def test_approval_node_manual_awaiting(mock_file_open, mock_slack, base_state):
    """Test approval_node for manual tests that need approval."""
    state = base_state.model_copy(update={"test_type": "manual", "approved": False})

    updated_state = approval_node(state)

    assert updated_state.status == "awaiting_approval"
    mock_slack.assert_called_once()
    mock_file_open.assert_called_once_with("pending_state.json", "w")
    # Get the actual JSON content that was written
    written_content = mock_file_open().write.call_args[0][0]
    import json

    # Verify it's valid JSON
    json.loads(written_content)


def test_approval_node_manual_approved(base_state):
    """Test approval_node for manual tests that are pre-approved."""
    state = base_state.model_copy(update={"test_type": "manual", "approved": True})
    updated_state = approval_node(state)
    assert updated_state.status == "approved"


def test_approval_node_automatic(base_state):
    """Test approval_node for automatic tests (e.g., unit tests)."""
    state = base_state.model_copy(update={"test_type": "unit"})
    updated_state = approval_node(state)
    assert updated_state.approved is True
    assert updated_state.status == "approved"


# Use parametrize to test runner_node with different frameworks
@pytest.mark.parametrize(
    "test_type, framework, expected_command_part",
    [
        ("unit", "pytest", ["pytest"]),
        ("unit", "jest", ["npx", "--yes", "jest"]),
        ("e2e", "cypress", ["npx", "cypress", "run"]),
        ("e2e", "playwright", ["pytest"]),
    ],
)
@patch("graph.workflow.subprocess.run")
def test_runner_node_command_construction(
    mock_subprocess, test_type, framework, expected_command_part, base_state
):
    """Test runner_node constructs the correct command for different frameworks."""
    state = base_state.model_copy(update={"test_type": test_type, "framework": framework})

    # Mock a successful run
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="OK", stderr="")

    runner_node(state)

    mock_subprocess.assert_called_once()
    called_command = mock_subprocess.call_args.args[0]

    # Check if any expected command part exists in the command
    assert any(
        expected_part in cmd_part
        for expected_part in expected_command_part
        for cmd_part in called_command
    )
    # Check if the resolved path is in the command
    resolved_path = str(Path(state.output_path).resolve())
    assert resolved_path in called_command


@patch("graph.workflow.subprocess.run")
def test_runner_node_success(mock_subprocess, base_state):
    """Test runner_node handling a successful test run."""
    mock_subprocess.return_value = MagicMock(returncode=0, stdout="All tests passed", stderr="")
    updated_state = runner_node(base_state)
    assert updated_state.status == "passed"
    assert "All tests passed" in updated_state.test_results


@patch("graph.workflow.subprocess.run")
def test_runner_node_failure(mock_subprocess, base_state):
    """Test runner_node handling a failed test run."""
    mock_subprocess.return_value = MagicMock(returncode=1, stdout="", stderr="AssertionError")
    updated_state = runner_node(base_state)
    assert updated_state.status == "failed"
    assert "AssertionError" in updated_state.test_results


@patch("graph.workflow.subprocess.run", side_effect=Exception("command not found"))
def test_runner_node_exception(mock_subprocess, base_state):
    """Test runner_node handling an exception during subprocess execution."""
    updated_state = runner_node(base_state)
    assert updated_state.status == "failed"
    assert "Error running tests: command not found" in updated_state.test_results


def test_runner_node_manual_skip(base_state):
    """Test that runner_node skips manual tests."""
    state = base_state.model_copy(update={"test_type": "manual"})
    updated_state = runner_node(state)
    assert updated_state.status == "skipped"


@patch("graph.workflow.clean_code_fences", side_effect=lambda x: x)
@patch("builtins.open", new_callable=mock_open)
def test_output_node(mock_file_open, mock_clean_fences, base_state):
    """Test output_node writes the generated tests to a file."""
    state = base_state

    # Mock Path methods
    with patch.object(Path, "mkdir") as mock_mkdir:
        updated_state = output_node(state)

        # Assertions
        mock_clean_fences.assert_called_once_with(state.generated_tests)
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_file_open.assert_called_once_with(Path(state.output_path), "w")
        mock_file_open().write.assert_called_once_with(state.generated_tests)
        assert updated_state.status == "saving"
