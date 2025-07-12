from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate

from common.llm import get_llm

load_dotenv()

llm = get_llm()

# Create prompt templates
UNIT_TEST_TEMPLATE = ChatPromptTemplate.from_template(
    """
You are an expert QA engineer.
Generate Python unit tests using pytest for this file:

{file_path}

The contents of the file is:

{code}

Return only valid Python code and ensure imports are correct. Include code comments where necessary to explain the test logic but do not include any additional text or explanations outside the code block.
"""
)

UNIT_JEST_TEMPLATE = ChatPromptTemplate.from_template(
    """
You are an expert QA engineer.
Generate JavaScript unit tests using Jest for this file:

{file_path}

The contents of the file is:

{code}

Return only valid JavaScript code and ensure imports are correct. Include code comments where necessary to explain the test logic but do not include any additional text or explanations outside the code block.

Important:
- Output ONLY valid JavaScript, no TypeScript syntax.
- Do not use "as" type assertions or type imports.
- Do not include explanations or markdown.
"""
)


E2E_PLAYWRIGHT_TEMPLATE = ChatPromptTemplate.from_template(
    """
You are an expert QA engineer.
Generate end-to-end tests using Playwright in Python for this web application code:

{code}

Return only valid Python code. Include code comments where necessary to explain the test logic but do not include any additional text or explanations outside the code block.
"""
)

E2E_CYPRESS_TEMPLATE = ChatPromptTemplate.from_template(
    """
You are an expert QA engineer.
Generate end-to-end tests using Cypress (JavaScript) for this web application code:

{code}

Return only valid JavaScript code. Include code comments where necessary to explain the test logic but do not include any additional text or explanations outside the code block.
"""
)

MANUAL_QA_TEMPLATE = ChatPromptTemplate.from_template(
    """
You are a senior QA analyst.
Given this PRD and user stories, generate a detailed manual QA checklist:

{code}

Return a numbered list of steps as a checklist. Also return related user stories.

For example, if the PRD describes a login feature, return the following:
==================
Feature checklist:
1. [ ] Verify the login page loads correctly.
2. [ ] Check that the login form accepts valid credentials.
3. [ ] Ensure the login form rejects invalid credentials with appropriate error messages.

Feature user stories:
1. As a user, I want to log in to the application so that I can access my account.
2. As a user, I want to see an error message when I enter invalid credentials so that I know what went wrong.
==================

The title should be "Manual Testing Checklist".
"""
)

# Map test type/framework to prompt template
PROMPT_MAP = {
    ("unit", "pytest"): UNIT_TEST_TEMPLATE,
    ("unit", "jest"): UNIT_JEST_TEMPLATE,
    ("e2e", "playwright"): E2E_PLAYWRIGHT_TEMPLATE,
    ("e2e", "cypress"): E2E_CYPRESS_TEMPLATE,
    ("manual", None): MANUAL_QA_TEMPLATE,
}


def create_generation_chain(test_type: str, framework: str):
    # Determine which prompt to use
    key = (test_type, framework) if test_type != "manual" else ("manual", None)
    prompt = PROMPT_MAP.get(key)
    if not prompt:
        raise ValueError(f"Unsupported combination: {test_type}/{framework}")

    return prompt | llm


REPAIR_PYTEST_TEMPLATE = ChatPromptTemplate.from_template(
    """
You are an expert Python QA engineer.

The following tests failed when executed:

{error_output}

Here is the code you were testing:

{code}

Here is the failing test code:

{failing_tests}

Please correct the tests so they pass.

Return ONLY valid Python code. Do not include explanations or markdown.
"""
)

REPAIR_JEST_TEMPLATE = ChatPromptTemplate.from_template(
    """
You are an expert JavaScript QA engineer.

The following Jest tests failed:

{error_output}

Here is the code under test:

{code}

Here is the failing test code:

{failing_tests}

Please correct the tests so they pass.

Important:
- Output ONLY valid JavaScript, no TypeScript syntax.
- Use correct Jest imports and mocks.
- Ensure the code is syntactically valid and will pass Babel parsing.
- Do not repeat the same failing patterns.
- If the error relates to syntax, adjust accordingly.
- Return ONLY the full corrected test file as valid JavaScript.
"""
)


REPAIR_CYPRESS_TEMPLATE = ChatPromptTemplate.from_template(
    """
You are an expert QA engineer.

The following Cypress tests failed:

{error_output}

Here is the application code:

{code}

Here is the failing test code:

{failing_tests}

Please correct the tests so they pass.

Return ONLY valid JavaScript code. Do not include explanations or markdown.
"""
)


def create_repair_chain(framework: str):
    if framework == "pytest":
        prompt = REPAIR_PYTEST_TEMPLATE
    elif framework == "jest":
        prompt = REPAIR_JEST_TEMPLATE
    elif framework == "cypress":
        prompt = REPAIR_CYPRESS_TEMPLATE
    else:
        raise ValueError(f"Unsupported framework for repair: {framework}")

    return prompt | llm
