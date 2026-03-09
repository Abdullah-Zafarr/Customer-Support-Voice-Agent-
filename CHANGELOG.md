# 📜 Version Changes (Changelog)

This document tracks the evolution of the AI Voice Agent project, highlighting what new features were added for the user and how they were built under the hood.

## 📂 Version 2.2 — Intelligence Expansion (March 7, 2026)
*Focus: Allowing the AI to read your documents and answer questions based on them.*

- **Feature: Knowledge Base (RAG)**
  The agent can now read custom uploaded documents (like Shopify FAQs or manuals) and ground its answers in your specific text.
  *Tech:* Implemented a custom RAG (Retrieval-Augmented Generation) engine using `sentence-transformers` for local file embeddings. Top-K relevant chunks are injected into the Groq LLM `SYSTEM_PROMPT`.
- **Feature: Drag-and-Drop Uploads**
  Added a slick UI zone allowing you to drag `.txt`, `.md`, or `.pdf` files straight into the dashboard.
  *Tech:* Used `python-multipart` for secure backend routing and added Javascript `drop` events that visually highlight the HUD and trigger background re-indexing.
- **Feature: Zero-Freeze Processing**
  Uploading massive documents won't stutter the live voice call; the AI keeps listening while it reads.
  *Tech:* Offloaded the heavily CPU-bound embedding tasks to background threads using `fastapi.concurrency.run_in_threadpool`.

---

## 🚀 Version 2.1 — Precision & Stability (March 7, 2026)
*Focus: Giving users control over mistakes and stopping the AI from making bad guesses.*

- **Feature: Editable Transcripts**
  If the speech-to-text mishears a name, you can click the live transcript on the screen, edit the typo, and hit Enter to correct it before the AI gets confused.
  *Tech:* Built a WebSocket `correction` protocol. When you edit text, the backend searches its internal `messages` array, injects your fix, and dynamically truncates the conversation history so the LLM resets its context perfectly.
- **Feature: Smarter Ticket Creation**
  The AI will now strictly refuse to log a support ticket unless you give it *both* your name and the specific issue you're facing.
  *Tech:* Engineered strict guardrails into the Groq system prompt mapping, preventing premature JSON tool calls (`manage_ticket`).
- **Feature: Bulletproof Audio Link**
  The voice connection is now highly resilient against network blips or bad data.
  *Tech:* Wrapped the WebSocket receiver loop in rigorous `try/except` JSON parsing guards to prevent malformed text packets from crashing the stream.

---

## ⚡ Version 2.0 — Local Power & Audio Streaming (March 5, 2026)
*Focus: Making the app faster, entirely free to run, and visually stunning.*

- **Feature: 100% Free Voice Infrastructure**
  Ripped out expensive cloud subscriptions; the agent's ears and mouth are now powered locally and for free.
  *Tech:* Transitioned the Speech-to-Text engine to run directly on your CPU using `faster-whisper` (`small.en`), and the Text-to-Speech to Microsoft Edge's Neural wrapper (`edge-tts`).
- **Feature: "Mission Control" Overhaul**
  Replaced the generic white UI with a stunning, dark-mode cyberpunk dashboard featuring a pulsing audio visualizer.
  *Tech:* Built a custom CSS grid using Tailwind, the "Share Tech Mono" font, and native Web Audio API `AudioContext` nodes to draw raw Float32 audio data onto an HTML5 Canvas.
- **Feature: Support Ticket Database**
  Changed the fundamental purpose of the agent from taking random "Appointments" to managing technical "Support Tickets."
  *Tech:* Refactored the underlying SQLite DB and SQLAlchemy ORM models from `Appointment` to `SupportTicket` with urgency tracking.

---

## 🎙️ Version 1.1 — Core AI Synthesis (March 4, 2026)
*Focus: Connecting the brain to the mouth.*

- **Feature: AI Tool Usage**
  The Voice Agent isn't just a chatbot; it can autonomously take actions and decide when to create database records.
  *Tech:* Enabled the Groq API to utilize JSON schema-based tool calling.
- **Feature: Seamless Interruptions (Barge-in)**
  If the AI is talking and you interrupt it, it instantly shuts up and listens to your new sentence.
  *Tech:* Wrapped the TTS generation loop in an `asyncio.create_task` that is instantly cancelled upon triggering the STT audio buffer callback.

---

## 🛠️ Version 1.0 — Architecture Foundation (March 3, 2026)
*Focus: Getting the server breathing.*

- **Feature:** Initial project scaffolding and routing.
- **Tech:** Established the Uvicorn/FastAPI backend framework, configured the SQLite connection, and implemented `.env` secret management via `pydantic-settings`.
