# 📦 Voice Agent Dependencies

The following open-source frameworks and libraries power the AI Voice Agent.

## Core Backend & Server
- **FastAPI** (`fastapi`): The lightning-fast asynchronous web framework powering the backend.
- **Uvicorn** (`uvicorn`): The robust ASGI server that runs the FastAPI application.
- **WebSockets** (`websockets==12.0`): Dedicated library for managing full-duplex, real-time client-agent communication streams.
- **Httpx** (`httpx`): Async HTTP client used for efficient REST API calls (like to HuggingFace or Groq).

## AI Models & Inference
- **Groq** (`groq`): Official Python SDK for Groq Cloud. Used to run the Llama 3.1 8B Instant Language Model at ultra-low latencies.
- **Faster-Whisper** (`faster-whisper`): A highly optimized, local Speech-to-Text inference engine. Powers the `small.en` model for precise voice transcription on the CPU.
- **Microosft Edge TTS** (`edge-tts`): A lightweight wrapper allowing access to highly expressive, zero-cost neural text-to-speech voices.

## RAG Knowledge Base Engine (Local Search)
- **Sentence-Transformers** (`sentence-transformers`): Used to generate high-quality text embeddings locally (model: `all-MiniLM-L6-v2`) without API costs.
- **NumPy** (`numpy`): The math engine utilized for calculating Cosine Similarity scores between the user query and knowledge chunks.
- **PyMuPDF** (`PyMuPDF` / `fitz`): An incredibly fast and reliable library used to parse and extract raw text from `.pdf` documentation files in the `knowledge/` directory.

## Persistence & Configuration
- **SQLAlchemy** (`sqlalchemy`): The foundational Database ORM used to map Support Tickets to a local SQLite database (`appointments.db`).
- **Python-Dotenv** (`python-dotenv`): Parses the local `.env` file to securely inject API keys.
- **Pydantic** (`pydantic` & `pydantic-settings`): Used for strict data validation schema definitions (e.g. for Groq tool calling).
