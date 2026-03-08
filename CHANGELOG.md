# 📜 Version Changes (Changelog)

This document tracks the evolution of the AI Voice Agent project across different iterative versions.

## 🚀 Version 2.1 — Precision & Stability (March 7, 2026)
*Focus: Enhancing AI accuracy, real-time corrections, and robust UI.*
- **Editable Transcripts:** Added a clickable, editable UI for Live Transcripts. Users can now instantly correct STT mistakes before the LLM processes them.
- **History Truncation:** Backend WebSocket handler now truncates conversation history gracefully upon receiving text corrections to prevent the agent from looping or stalling.
- **Whisper Upgrade:** Upgraded Faster-Whisper model (`small.en`) and tuned VAD (Voice Activity Detection) parameters for significantly higher precision on names and accents.
- **Smart Tickets:** Guardrails added to the System Prompt mapping so the AI strictly refuses to create a ticket without *both* a name and an issue descriptions.
- **UI Bug Fixes:** Resolved a destructive DOM rendering bug that caused old tickets to disappear when new ones were processed.
- **Cache-Busting:** Implemented `?v=` version tracking on static assets to ensure browsers never load stale UI code.
- **AI Agent Map:** Added `AGENT.md` guidelines for any autonomous agents browsing the repository.

---

## ⚡ Version 2.0 — Local Power (March 5, 2026)
*Focus: Replacing cloud-dependent components with powerful local/free alternatives while restoring the cyberpunk aesthetic.*
- **Faster-Whisper STT:** Switched the transcription engine to run completely locally using `faster-whisper`.
- **Zero-Cost Neural TTS:** Replaced standard text-to-speech with Microsoft Edge's free Neural TTS wrapper.
- **Mission Control Restored:** Re-applied the dark-mode "Mission Control" UI (HUD styling, Share Tech Mono fonts, dynamic waveforms).
- **Ticket Tracking:** Fully transitioned the backend database from "Appointments" to a professional "Support Ticket" tracking system.
- **Documentation:** Added Mermaid/Eraser architectural flowcharts and detailed diagrams to `README.md`.

---

## 🎙️ Version 1.1 — Core Launch (March 4, 2026)
*Focus: Bringing the pieces together into a working prototype.*
- **Voice Agent Engine:** Fully linked the Web Audio API (PCM16 chunks) to the backend STT engine.
- **LLM Brain:** Enabled Groq to process text transcripts and fire function calls (tool usage).
- **Real-Time I/O:** Established stable bidirectional WebSocket streaming.

---

## 🛠️ Version 1.0 — Architecture Foundation (March 3, 2026)
*Focus: Project scaffolding, server routing, and database setup.*
- **FastAPI Setup:** Initialized the Uvicorn/FastAPI backend framework.
- **Database ORM:** Set up SQLite using SQLAlchemy models.
- **Environment Management:** Implemented `.env` integration and `pydantic-settings`.
- **Initial APIs:** Integrated initial Deepgram streaming endpoints (later replaced).
- **Frontend Skeleton:** Created the semantic HTML structure for the dashboard UI.
