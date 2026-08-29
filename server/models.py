from langchain_openai import ChatOpenAI

# Setup local chatbot client pointing to the Ollama server
llm = ChatOpenAI(
    model="qwen2.5:latest",                    # Specify the local model name to run via Ollama
    base_url="http://localhost:11434/v1",    # Point the client base URL to the local Ollama API port
    api_key="ollama",                        # Provide a dummy API key string as Ollama requires no authentication
    temperature=0.7,                         # Set creativity (0.7 balances coherence and conversational variety)
    model_kwargs={"response_format": {"type": "json_object"}} # Force local Ollama to return structured JSON
)
