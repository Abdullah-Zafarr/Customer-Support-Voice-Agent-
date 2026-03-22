# AI Agent Instructions for Voice Agent Project

Hello AI! If you are reading this, you are navigating the "Voice Agent — Mission Control" repository.
This document provides a high-level map of the codebase to help you understand the architecture, design choices, and conventions used in this project so you can assist the human user more effectively.

## Project Overview
This is a real-time conversational AI customer support agent. It streams audio via WebSockets, processes it with local STT (Faster-Whisper), generates responses using an LLM (Llama 3.3 via Groq), and streams TTS audio back to the client using Microsoft Edge TTS.

## Key Directories & Files
- `/app/main.py`: The FastAPI server entry point. Serves static files and WebSocket endpoints.
- `/app/websocket.py`: Handles the real-time WebSocket connection, audio chunk receiving, VAD triggering, and streaming TTS back.
- `/app/agent.py`: Contains the LLM interaction logic, `SYSTEM_PROMPT`, and tool definitions (e.g., `manage_ticket`).
- `/app/whisper_client.py`: The core STT and TTS engine. Uses `faster-whisper` (`small.en`) for transcription and `edge-tts` for TTS. Includes custom VAD logic and sentence-by-sentence low-latency TTS streaming.
- `/app/database.py`: SQLAlchemy database configuration and schema (e.g., the `SupportTicket` model).
- `/app/static/`: Contains the frontend assets:
  - `index.html`: The Mission Control UI (Tailwind CSS, HUD styling).
  - `script.js`: Audio capture logic, waveform visualization, and WebSocket communication.
  - `style.css`: Custom CSS variables and animations.

## Architectural Notes & Constraints
1. **Low Latency Streaming:** The TTS pipeline (`get_tts_stream` in `whisper_client.py`) streams audio sentence-by-sentence. If you are modifying the LLM or TTS logic, ensure this streaming behavior is preserved so latency remains low.
2. **Ticket Management Logic:** The tool `manage_ticket` (in `agent.py`) is designed so the LLM must gather *both* the user's name and a description of their issue before creating a ticket. Updates to existing tickets in a conversation use the *same* ticket ID to avoid duplicate clutter.
3. **Barge-in / Interruptions:** The frontend handles barge-in by clearing the audio playback queue and notifying the backend when the user interrupts the agent.
4. **Environment Variables:** The project heavily relies on the `GROQ_API_KEY` defined in a `.env` file for fast Llama inference. Never expose or hardcode API keys.

## Design Aesthetic
- If you are modifying the frontend, maintain the "Mission Control" cyberpunk aesthetic.
- Key colors: `void` (dark background), `hud-cyan` (primary text/accents), `hud-emerald` (success/metrics), `hud-rose` (alerts/errors).
- Use strictly monospaced / sans-serif technical fonts (`Share Tech Mono`, `Fira Code`, `IBM Plex Sans`).
- Always use cache-busting (e.g., `?v=X`) on static files in `index.html` after making frontend changes to avoid local caching issues.
