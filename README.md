# 🎙️ AI Voice Agent — Mission Control

![AI Voice Agent Interface Screenshot](assets/interface.PNG)

## 🏗️ System Architecture

![System Architecture Diagram](assets/architecture_diagram.png)

A production-ready, conversational AI Customer Support Voice Agent. Built to demonstrate a complete system architecture (Speech-to-Text → LLM → Text-to-Speech) using high-performance local and free-tier components.

## ✨ Features

- **Local STT:** Powered by **Faster-Whisper** (`tiny.en`, int8 quantized, runs on CPU)
- **Fast LLM Inference:** **Groq (Llama 3.3 70B)** for millisecond reasoning
- **Neural TTS:** **Microsoft Edge TTS** — high-quality neural voice, zero cost
- **Energy-Based VAD:** Server-side silence detection triggers transcription automatically
- **AI Tool Use:** LLM autonomously creates support tickets via function calling
- **Barge-in:** Interrupts cancel ongoing TTS and process new speech instantly
- **Mission Control UI:** Cyberpunk dark-mode HUD with live waveforms and real-time ticket tracking
- **Zero-Cost STT/TTS:** Runs entirely on local models and free APIs

## 🛠️ Tech Stack

- **Backend:** Python + FastAPI (WebSocket streaming)
- **Frontend:** Vanilla HTML/CSS/JS (**Share Tech Mono + Fira Code + IBM Plex Sans** fonts)
- **Database:** SQLite via SQLAlchemy
- **AI:** `faster-whisper` (local STT), `edge-tts` (neural TTS), `groq` (Llama 3.3 LLM)

## 📂 Project Structure

```text
.
├── app/
│   ├── static/
│   │   ├── index.html        # Dashboard UI
│   │   ├── script.js         # Audio capture & WebSocket logic
│   │   └── style.css         # Dark-mode styling
│   ├── agent.py              # LLM logic & tool definitions
│   ├── config.py             # Environment config
│   ├── database.py           # SQLAlchemy models
│   ├── whisper_client.py     # Whisper STT & Edge TTS
│   ├── logger.py             # Logging
│   ├── main.py               # FastAPI app
│   └── websocket.py          # Real-time streaming handler
├── main.py                   # Entry point
├── requirements.txt          # Dependencies
└── .env                      # API keys (Groq only)
```

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- **[Groq Cloud API Key](https://console.groq.com/keys)**

### Setup

```bash
git clone https://github.com/Abdullah-Zafarr/Customer-Support-Voice-Agent-.git
cd Customer-Support-Voice-Agent-

python -m venv .venv
.\.venv\Scripts\activate        # Windows
# source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

### Configure

Create `.env` in the root directory:

```env
GROQ_API_KEY="your_groq_api_key_here"
```

### Run

```bash
python main.py
```

Open **http://127.0.0.1:8000** → Click **Start Call** → Speak.

## 🧠 Pipeline

1. Browser captures audio → 16kHz PCM16 via WebSocket
2. Server VAD detects speech boundaries
3. **Faster-Whisper** transcribes locally
4. **Groq (Llama 3.3)** generates response + tool calls
5. **Edge TTS** converts response to audio
6. **PyAV** decodes MP3 → PCM16 chunks → streamed to browser

## 📄 License

MIT License. Built as a portfolio project.
