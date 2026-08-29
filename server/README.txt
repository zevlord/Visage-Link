Zero Two Chat Server - Architecture File Guide
=============================================

This directory contains the modularized backend files for the Zero Two VTuber chat companion:

1. server.py
   - The main entry point. Initializes FastAPI, mounts static folders (Models, voice sample),
     serves index.html, and maps the WebSocket route.

2. chat_handler.py
   - Implements the WebSocket connection loop. Manages the system prompt, handles memory context
     injection, calls the local LLM, parses output, triggers voice synthesis, and sends payload response.

3. credentials.py
   - Handles API key loading for OpenRouter/LangMem. Checks the parent workspace directory for the
     credentials file.

4. models.py
   - Initializes the LangChain ChatOpenAI client pointing to the local Ollama endpoint (Qwen 2.5 1.5B).

5. memory.py
   - Configures the optional LangMem vector database and schemas. Disables memory extraction gracefully
     in offline mode if no custom OpenRouter key is detected.

6. voice_config.py
   - Configures local GPT-SoVITS voice endpoints, spoken prompt texts, and target language codes.

7. voice_service.py
   - Formats input strings into safe line breaks (preventing cutoffs) and makes HTTP requests to
     the local GPT-SoVITS API.
