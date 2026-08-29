import os
import credentials  # Ensures environment keys are loaded
from pydantic import BaseModel

# Ponytail: make langmem optional — only import if needed, don't crash the server
try:
    from langgraph.store.memory import InMemoryStore
    from langmem import create_memory_store_manager
    LANGMEM_AVAILABLE = True
except (ImportError, AttributeError) as e:
    print(f"[MEMORY] langmem not available, disabling memory features: {e}")
    LANGMEM_AVAILABLE = False
    InMemoryStore = None
    create_memory_store_manager = None

# Enable memory manager only if a custom API key is supplied
use_memory = False
key_file_path = os.path.join(credentials.BASE_DIR, "api key openrouter.txt")

if os.path.exists(key_file_path):
    with open(key_file_path, "r", encoding="utf-8") as f:
        file_key = f.read().strip()
        default_key = getattr(credentials, "DEFAULT_KEY", "")
        if file_key and file_key != default_key:
            use_memory = True

class UserFact(BaseModel):
    """Store stable facts or preferences about the user."""
    topic: str
    fact: str

memory_store = None
memory_manager = None

if use_memory and LANGMEM_AVAILABLE:
    memory_store = InMemoryStore(
        index={
            "dims": 1536,
            "embed": "openai:text-embedding-3-small",
        }
    )
    memory_manager = create_memory_store_manager( 
        "openai:meta-llama/llama-3.1-8b-instruct",
        schemas=[UserFact],
        namespace=("memories", "{user_id}"),
        store=memory_store
    )
