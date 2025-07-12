import json
import os

import click
from dotenv import load_dotenv

from common.llm import get_llm

load_dotenv()

provider = os.environ.get("AI_PROVIDER", "openai").lower()

llm = get_llm(prefered_provider="openai")


def should_test_file(file_path: str, file_contents: str) -> bool:
    click.echo(f"[AutoQA] [Agent]: Evaluating {file_path}")
    if not file_contents.strip():
        click.echo(f"[AutoQA] [Agent]: Skipping empty file {file_path}")
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
    click.echo(f"[AutoQA] [Agent]: Model response for {file_path}: {decision}")
    return decision == "yes"


def classify_file(file_path: str, file_contents: str) -> dict:
    click.echo(f"[AutoQA] [Agent]: Classifying {file_path}")

    if not file_contents.strip():
        click.echo(f"[AutoQA] [Agent]: Skipping empty file {file_path}")
        return {"should_test": False, "test_type": None, "priority": None}

    if len(file_contents) > 5000:
        file_contents = file_contents[:5000]

    prompt = (
        "You are an AI code reviewer. "
        "Given this file, decide:\n"
        "- Should it have tests generated? (true/false)\n"
        "- What type of test? (unit, e2e, manual)\n"
        "- What priority? (high, medium, low)\n\n"
        "Respond ONLY in this JSON format:\n\n"
        "{\n"
        '  "should_test": true,\n'
        '  "test_type": "unit",\n'
        '  "priority": "high"\n'
        "}\n\n"
        f"File: {file_path}\n\n"
        "Contents:\n"
        f"{file_contents}\n"
    )

    response = llm.invoke(prompt)
    raw = response.content.strip()
    click.echo(f"[AutoQA] [Agent]: Raw model response:\n{raw}\n")

    # Parse JSON safely
    try:
        result = json.loads(raw)
    except Exception as e:
        click.echo(f"[AutoQA] [Agent]: JSON parsing error: {e}")
        return {"should_test": False, "test_type": None, "priority": None}

    return result
