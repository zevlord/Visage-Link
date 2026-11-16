import os

from langchain_openai import ChatOpenAI

# LLM client. Defaults to a local Ollama instance; override via environment
# variables to point at a hosted [OI]-compatible endpoint instead.
LLM_MODEL = os.getenv("VISAGE_LLM_MODEL", "qwen2.5:latest")
LLM_BASE_URL = os.getenv("VISAGE_LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY = os.getenv("VISAGE_LLM_API_KEY", "ollama")  # Ollama ignores this value

llm = ChatOpenAI(
    model=LLM_MODEL,
    base_url=LLM_BASE_URL,
    api_key=LLM_API_KEY,
    temperature=0.7,
    # The chat pipeline parses structured JSON (emotion + text), so the model
    # is asked to constrain its output format.
    model_kwargs={"response_format": {"type": "json_object"}},
)
