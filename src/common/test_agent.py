import json
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

llm = ChatOpenAI(temperature=0, model="gpt-4")


def should_test_file(file_path: str, file_contents: str) -> bool:
    print(f"[AutoQA] [Agent]: Evaluating {file_path}")
    if not file_contents.strip():
        print(f"[AutoQA] [Agent]: Skipping empty file {file_path}")
        return False

    if len(file_contents) > 5000:
        file_contents = file_contents[:5000]

    prompt = (
        "You are an AI code reviewer. "
        "Given this file, decide if it should have tests generated.\n\n"
        f"File: {file_path}\n\n"
        "Contents:\n"
        f"{file_contents}\n\n"
        "Respond only with 'yes' or 'no'."
    )
    response = llm.invoke(prompt)
    decision = response.content.strip().lower()
    print(f"[AutoQA] [Agent]: Model response for {file_path}: {decision}")
    return decision == "yes"


def classify_file(file_path: str, file_contents: str) -> dict:
    print(f"[AutoQA] [Agent]: Classifying {file_path}")

    if not file_contents.strip():
        print(f"[AutoQA] [Agent]: Skipping empty file {file_path}")
        return {"should_test": False, "test_type": None, "priority": None}

    if len(file_contents) > 5000:
        file_contents = file_contents[:5000]

    prompt = (
        "You are an AI code reviewer. "
        "Given this file, decide:\n"
        "- Should it have tests generated? (true/false)\n"
        "- What type of test? (unit, e2e, manual)\n"
        "- What framework to use? (pytest, cypress, playwright)\n"
        "- What priority? (high, medium, low)\n\n"
        "Respond ONLY in this JSON format:\n\n"
        "{\n"
        '  "should_test": true,\n'
        '  "test_type": "unit",\n'
        '  "framework": "pytest",\n'
        '  "priority": "high"\n'
        "}\n\n"
        f"File: {file_path}\n\n"
        "Contents:\n"
        f"{file_contents}\n"
    )

    response = llm.invoke(prompt)
    raw = response.content.strip()
    print(f"[AutoQA] [Agent]: Raw model response:\n{raw}\n")

    # Parse JSON safely
    try:
        result = json.loads(raw)
    except Exception as e:
        print(f"[AutoQA] [Agent]: JSON parsing error: {e}")
        return {"should_test": False, "test_type": None, "priority": None}

    return result


# Unit tests for should_test_file function
@pytest.mark.parametrize(
    "file_path, file_contents, expected",
    [
        ("test.py", "", False),  # Test with empty file contents
        (
            "test.py",
            "print('Hello, World!')",
            True,
        ),  # Test with non-empty file contents
        (
            "test.py",
            "a" * 6000,
            True,
        ),  # Test with file contents longer than 5000 characters
    ],
)
@patch("langchain_openai.ChatOpenAI.invoke")
def test_should_test_file(mock_invoke, file_path, file_contents, expected):
    # Mock the response from the LLM
    mock_response = MagicMock()
    mock_response.content = "yes" if expected else "no"
    mock_invoke.return_value = mock_response

    assert should_test_file(file_path, file_contents) == expected


# Unit tests for classify_file function
@pytest.mark.parametrize(
    "file_path, file_contents, expected",
    [
        (
            "test.py",
            "",
            {"should_test": False, "test_type": None, "priority": None},
        ),  # Test with empty file contents
        (
            "test.py",
            "print('Hello, World!')",
            {
                "should_test": True,
                "test_type": "unit",
                "framework": "pytest",
                "priority": "high",
            },
        ),  # Test with non-empty file contents
        (
            "test.py",
            "a" * 6000,
            {
                "should_test": True,
                "test_type": "unit",
                "framework": "pytest",
                "priority": "high",
            },
        ),  # Test with file contents longer than 5000 characters
    ],
)
@patch("langchain_openai.ChatOpenAI.invoke")
def test_classify_file(mock_invoke, file_path, file_contents, expected):
    # Mock the response from the LLM
    mock_response = MagicMock()
    mock_response.content = json.dumps(expected)
    mock_invoke.return_value = mock_response

    assert classify_file(file_path, file_contents) == expected
