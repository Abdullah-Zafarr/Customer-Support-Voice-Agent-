# 📜 Version Changes (Changelog)

This document tracks the technical evolution, architectural shifts, and core feature additions of the AI Voice Agent project.

## 📂 Version 2.2 — Intelligence Expansion & Concurrency (March 7, 2026)
*Architectural Focus: Non-blocking data ingestion and multipart API endpoints.*
- **Async Threadpooling:** Offloaded CPU-bound `sentence-transformers` embedding tasks to `fastapi.concurrency.run_in_threadpool`, ensuring the async event loop remains unblocked during heavy RAG ingestions.
- **Multipart Upload API:** Deployed a new `/upload` POST endpoint utilizing `python-multipart` for secure, high-performance binary file streaming from the client to the server's `knowledge/` directory.
- **Drag & Drop Pipeline:** Engineered a frontend drag-and-drop interface with custom event listeners (`dragover`, `drop`) that instantly triggers background re-indexing upon file drop.
- **Fault-Tolerant WebSockets:** Implemented strict `try/except` JSON parsing guards within the WebSocket receiver loop to prevent malformed text packets from crashing active audio streams.

---

## 🚀 Version 2.1 — RAG Foundation & State Correction (March 7, 2026)
*Architectural Focus: Vector similarity search and conversational state mutability.*
- **Lightweight RAG Engine:** Built a custom retrieval-augmented generation engine (`app/rag.py`) using `sentence-transformers` for embeddings and NumPy for fast cosine similarity search, bypassing the need for heavy external vector databases (like ChromaDB).
- **Vector Persistence:** Engineered local JSON-based indexing (`knowledge_index.json`) for fast startup caching of chunked embeddings and metadata.
- **State Correction Protocol:** Invented a WebSocket protocol allowing the frontend to send `correction` events. The backend now dynamically traverses the `messages` array, injects the corrected transcript, and truncates subsequent history to force the LLM to re-evaluate the accurate state.
- **Context Injection:** Modified the Groq LLM processing pipeline to dynamically inject top-K relevant chunks into the `SYSTEM_PROMPT` immediately before inference.

---

## ⚡ Version 2.0 — Local Power & Audio Streaming (March 5, 2026)
*Architectural Focus: Complete overhaul of the audio I/O pipeline and local processing.*
- **Local STT Pipeline:** Ripped out cloud-dependent STT APIs and integrated `faster-whisper` (`small.en` model) running directly on the CPU, aggressively optimizing latency.
- **Neural TTS Streaming:** Replaced standard text-to-speech with Microsoft Edge's Neural TTS wrapper (`edge-tts`), streaming raw MP3 bytes directly back through the WebSocket.
- **Web Audio API Integration:** Architected the frontend `script.js` to capture microphone inputs, convert them to raw PCM16 chunks via an `AudioContext` ScriptProcessor, and stream binary data to the backend.
- **PCM Playback:** Implemented raw Float32 audio buffering on the client side to accept incoming TTS bytes, feed an AnalyserNode for the dynamic waveform visualizer, and output to the speakers without stuttering.
- **Database Abstraction:** Refactored SQLAlchemy models, abstracting domain-specific "Appointments" into a flexible "SupportTicket" entity capable of handling various customer issues.

---

## 🎙️ Version 1.1 — Core AI Synthesis (March 4, 2026)
*Architectural Focus: LLM integration and Tool Calling.*
- **Function Calling Engine:** Enabled the Groq API to utilize JSON schema-based tool calling (`manage_ticket`), allowing the AI to autonomously interact with the SQLite database.
- **Prompt Guardrails:** Engineered strict state-machine logic within the `SYSTEM_PROMPT` to prevent the agent from firing database tools with incomplete data (e.g., missing issue descriptions).
- **Asynchronous Task Management:** Built the core `asyncio.create_task` wrapper surrounding the LLM/TTS generation loop in `websocket.py`, allowing the system to cancel TTS streams instantly upon STT "barge-in" events.

---

## 🛠️ Version 1.0 — System Foundation (March 3, 2026)
*Architectural Focus: Scaffolding and initial routing.*
- **FastAPI Core:** Initialized the Uvicorn/FastAPI backend framework with CORS middleware.
- **Database ORM:** Established the SQLite database connection and SQLAlchemy dependency injection models.
- **Environment Management:** Implemented secure `.env` secret management via `pydantic-settings`.
- **Static Marshalling:** Set up `StaticFiles` mounting for serving the vanilla HTML/CSS/JS frontend dashboard.
