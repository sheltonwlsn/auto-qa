import pytest
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

# Import the actual module where create_generation_chain and create_repair_chain are defined
from prompt_node import (  # Replace 'your_module_name' with the actual module name
    create_generation_chain,
    create_repair_chain,
)


# Unit tests for create_generation_chain function
def test_create_generation_chain_valid_unit_pytest():
    # Test with valid unit test type and pytest framework
    chain = create_generation_chain("unit", "pytest")
    assert isinstance(
        chain, type(ChatPromptTemplate.from_template("") | ChatOpenAI())
    ), "Expected a ChatChain instance"


def test_create_generation_chain_valid_unit_jest():
    # Test with valid unit test type and jest framework
    chain = create_generation_chain("unit", "jest")
    assert isinstance(
        chain, type(ChatPromptTemplate.from_template("") | ChatOpenAI())
    ), "Expected a ChatChain instance"


def test_create_generation_chain_valid_e2e_playwright():
    # Test with valid e2e test type and playwright framework
    chain = create_generation_chain("e2e", "playwright")
    assert isinstance(
        chain, type(ChatPromptTemplate.from_template("") | ChatOpenAI())
    ), "Expected a ChatChain instance"


def test_create_generation_chain_valid_e2e_cypress():
    # Test with valid e2e test type and cypress framework
    chain = create_generation_chain("e2e", "cypress")
    assert isinstance(
        chain, type(ChatPromptTemplate.from_template("") | ChatOpenAI())
    ), "Expected a ChatChain instance"


def test_create_generation_chain_valid_manual():
    # Test with valid manual test type
    chain = create_generation_chain("manual", None)
    assert isinstance(
        chain, type(ChatPromptTemplate.from_template("") | ChatOpenAI())
    ), "Expected a ChatChain instance"


def test_create_generation_chain_invalid_combination():
    # Test with invalid combination of test type and framework
    with pytest.raises(ValueError, match="Unsupported combination: invalid/invalid"):
        create_generation_chain("invalid", "invalid")


# Unit tests for create_repair_chain function
def test_create_repair_chain_valid_pytest():
    # Test with valid pytest framework
    chain = create_repair_chain("pytest")
    assert isinstance(
        chain, type(ChatPromptTemplate.from_template("") | ChatOpenAI())
    ), "Expected a ChatChain instance"


def test_create_repair_chain_valid_jest():
    # Test with valid jest framework
    chain = create_repair_chain("jest")
    assert isinstance(
        chain, type(ChatPromptTemplate.from_template("") | ChatOpenAI())
    ), "Expected a ChatChain instance"


def test_create_repair_chain_valid_cypress():
    # Test with valid cypress framework
    chain = create_repair_chain("cypress")
    assert isinstance(
        chain, type(ChatPromptTemplate.from_template("") | ChatOpenAI())
    ), "Expected a ChatChain instance"


def test_create_repair_chain_invalid_framework():
    # Test with invalid framework
    with pytest.raises(ValueError, match="Unsupported framework for repair: invalid"):
        create_repair_chain("invalid")
