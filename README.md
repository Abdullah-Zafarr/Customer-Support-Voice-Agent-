# 🎙️ AI Voice Agent — Mission Control Console

![A screenshot or mockup of your dark-themed "Mission Control" UI would look perfect here.](app/static/screenshot.png)

A production-ready, ultra-low latency, conversational AI Voice Agent designed to simulate an automated customer service representative for an HVAC & Plumbing company. Built to demonstrate a complete, robust system architecture (Speech-to-Text → LLM inference → Text-to-Speech) using high-performance, free-tier APIs.

## ✨ Features

- **Real-Time Speech-to-Text (STT):** Uses Deepgram Nova-3 for highly accurate, low-latency live transcription via WebSockets.
- **Lightning Fast LLM Inference:** Powered by Groq (Llama 3.3 70B), ensuring reasoning and response generation happen in milliseconds.
- **Live Text-to-Speech (TTS):** Streams Deepgram Aura Asteria audio chunks directly back to the client, virtually eliminating wait times.
- **AI Function Calling (Tool Use):** The LLM autonomously extracts caller details (Name, Issue, Urgency) and schedules database appointments in real-time.
- **Barge-in Support:** If the user interrupts, the system cancels the ongoing TTS stream and process the new speech instantly.
- **Cyberpunk "Mission Control" UI:** A custom, fully responsive frontend Dashboard that visualizes live waveforms, agent text streams, active states, and real-time booked appointments.
- **$0 Infrastructure:** Thoughtfully architected using free-tier / open-source tools to keep operational costs non-existent while delivering production quality.

## 🛠️ Architecture & Tech Stack

- **Backend:** Python + FastAPI (handling REST endpoints and highly concurrent WebSocket streaming).
- **Frontend:** Vanilla HTML, TailwindCSS, JavaScript (handling the Web Audio API, Canvas Visualization, and WebSocket binary buffers).
- **Database:** SQLite (managed via SQLAlchemy ORM).
- **AI Core:**
  - `groq` (Llama 3.3) for intelligence and tool calling.
  - `deepgram-sdk` for STT listener and TTS chunked streaming.

## 🚀 Getting Started

### Prerequisites

You will need Python 3.9+ and valid free API keys from:
- **[Groq Cloud](https://console.groq.com/keys)** (for Llama model execution)
- **[Deepgram](https://console.deepgram.com/)** (for STT and TTS)

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/your-username/voice-agent-mission-control.git
cd voice-agent-mission-control

# Create and activate a virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory and add your API keys:

```env
GROQ_API_KEY="your_groq_api_key_here"
DEEPGRAM_API_KEY="your_deepgram_api_key_here"
```

### 3. Run the Server

```bash
python main.py
```
*Note: This utilizes Uvicorn under the hood to handle asynchronous requests.*

### 4. Experience the Agent

Open your browser and navigate to:
**http://127.0.0.1:8000**

- Ensure your microphone is attached and permissions are granted.
- Click **"Initialize Call"**.
- Try saying: *"Hi, my name is John and my basement is flooding!"*
- Watch the Mission Control console process the transcript, make a tool call, and book the emergency appointment on the dashboard while speaking back to you seamlessly.

## 🧠 System Pipeline Internals

1. Audio is captured via the browser's `MediaDevices` API, resampled to 16kHz PCM16.
2. Binary chunks are piped over a persistent `WebSocket` to the FastAPI server.
3. FastAPI forwards chunks to the Deepgram Live Client.
4. Deepgram returns structured transcript JSON upon detecting sentence boundaries.
5. The transcript is injected into a persistent, memory-injected `messages` array, and routed through an `AsyncGroq` chat completion call.
6. If the LLM invokes the `book_appointment` tool, the server executes the mocked database write, appends the result, and loops back to Groq for a finalized spoken response.
7. The final text is passed via a streaming HTTP hook to Deepgram Aura TTS.
8. Raw audio bytes are yielded dynamically over the WebSocket and queued into the browser's `AudioContext` for interruption-safe playback.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. Built as a portfolio project demonstrating scalable AI architecture.
