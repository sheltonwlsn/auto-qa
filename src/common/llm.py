import click
from dotenv import load_dotenv

load_dotenv()

# provider = os.environ.get("AI_PROVIDER", "openai").lower()


def get_llm(prefered_provider: str = None):
    provider = "vertex"  # Force using Vertex AI with Claude Sonnet 4
    if prefered_provider:
        provider = prefered_provider.lower()
    click.echo(f"[AutoQA] [LLM]: Using provider: {provider}")
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-sonnet-4-20250514", max_tokens_to_sample=8000)
    elif provider == "vertex":
        from langchain_google_vertexai import ChatVertexAI

        return ChatVertexAI(model="gemini-2.5-pro", location="europe-west1", max_output_tokens=8000)
    elif provider == "vertex[claude]":
        from langchain_google_vertexai.model_garden import ChatAnthropicVertex

        return ChatAnthropicVertex(
            model="claude-sonnet-4", location="europe-west1", max_output_tokens=8000
        )
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="o3-mini")  # Default to OpenAI if not specified
