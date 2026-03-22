# 📜 Version Changes (Changelog)

This document tracks the technical evolution, architectural shifts, and core feature additions of the AI Voice Agent project.

## 📂 Version 2.2 — Intelligence Expansion & Async Concurrency (March 7, 2026)
*Architectural Focus: High-performance data ingestion and non-blocking event loops.*
- **Deep-Intelligence RAG Implementation:** Engineered a custom Retrieval-Augmented Generation engine (`app/rag.py`) allowing the agent to answer questions grounded in custom documentation.
- **Multimodal Knowledge Upload:** Developed a "Mission Control" HUD panel with drag-and-drop support for `.txt`, `.md`, and `.pdf` files, creating a seamless way for users to "train" the AI on the fly.
- **Asynchronous Threadpooling Fix:** Solved a critical server-stuttering issue by offloading CPU-bound `sentence-transformers` embedding tasks to `fastapi.concurrency.run_in_threadpool`, ensuring real-time voice response never drops during document ingestion.
- **Multipart API Infrastructure:** Deployed a high-performance `/upload` POST route using `python-multipart` to handle binary file streams and immediate background re-indexing.
- **UX Feedback Engine:** Implemented specialized CSS states and Javascript event listeners (`dragover`, `drop`) to provide premium visual feedback (cyan glow) during knowledge injection.

---

## 🚀 Version 2.1 — Precision, State Correction & Reliability (March 7, 2026)
*Architectural Focus: Conversational state mutability and error-resistant networking.*
- **Real-Time Transcript Correction:** Designed a first-of-its-kind "Editable Transcript" UI that allows users to click and fix any STT mishearings directly on the dashboard.
- **State Truncation Protocol:** Engineered a WebSocket `correction` handler that dynamically rewrites the LLM's conversation history on the backend, truncating downstream messages to ensure the AI resets its state to the user's manual fix.
- **Fault-Tolerant WebSocket Architecture:** Implemented rigorous `try/except` JSON parsing guards within the main receiver loop to prevent malformed data from crashing live audio connections.
- **Smart Support Logic:** Hardened the agent's behavior via complex `SYSTEM_PROMPT` guardrails, ensuring it strictly refuses to create database records without validated name and issue data.
- **Project Standardization:** Added `AGENT.md` and `DEPENDENCIES.md` to provide a professional specification for both human and AI developers browsing the codebase.

---

## ⚡ Version 2.0 — Local Infrastructure & Cyberpunk HUD (March 5, 2026)
*Architectural Focus: Replacing cloud dependencies with high-speed local processing.*
- **Faster-Whisper STT Integration:** Ripped out expensive cloud-streaming Speech-to-Text and integrated `faster-whisper` (`small.en`) running 100% locally on the CPU for sub-second transcription.
- **Zero-Cost Neural TTS:** Switched the voice generation to Microsoft Edge's Free Neural TTS engine (`edge-tts`), streaming raw audio packets back over WebSockets.
- **Mission Control UI Overhaul:** Re-imagined the frontend as a dark-mode cyberpunk dashboard with custom "Share Tech Mono" typography and an "Outfit" aesthetic.
- **Dynamic Waveform Visualizer:** Engineered a real-time waveform engine using the Web Audio API and HTML5 Canvas, drawing live audio frequency data captured from the microphone.
- **Support Ticket ORM:** Refactored the entire back-end database from "Appointments" to a specialized "SupportTicket" tracking system with SQLite and SQLAlchemy.

---

## 🎙️ Version 1.1 — Core AI Synthesis & Barge-in (March 4, 2026)
*Architectural Focus: Multi-threaded task management and AI Tool Calling.*
- **AI Tool Usage:** Successfully linked the Groq LLM brain to the SQLite database via JSON schema-based function calling (tools).
- **Asynchronous TTS Interruption:** Implemented "Barge-in" support by wrapping the audio generation loop in `asyncio.create_task`, allowing the backend to instantly kill speaking tasks if the user interrupts.
- **PCM16 Audio Marshalling:** Developed the logic to convert raw binary microphone buffers into PCM16 chunks for server-side processing.

---

## 🛠️ Version 1.0 — Architecture Foundation (March 3, 2026)
*Architectural Focus: Server scaffolding and initial routing.*
- **FastAPI Core:** Initialized the project with Uvicorn/FastAPI and CORS middleware.
- **Database Dependency Injection:** Set up SQLite with an SQLAlchemy session manager.
- **Environment Management:** Implemented secure `.env` secrets using `pydantic-settings`.
- **Static Asset Serving:** Built the foundation for the single-page application (SPA) dashboard.
