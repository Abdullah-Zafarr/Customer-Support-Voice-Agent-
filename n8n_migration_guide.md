# 🎙️ AI Voice Agent → n8n Migration Guide

> **Project:** Soul Imaging AI Voice Agent  
> **Current Stack:** Python · FastAPI · WebSocket · Groq (Whisper + LLaMA-3.3) · Edge TTS · ChromaDB · SQLite  
> **Target:** n8n workflow automation platform  
> **Last Updated:** March 2026

---

## 📌 Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Codebase Architecture](#2-current-codebase-architecture)
3. [What n8n Can and Cannot Replace](#3-what-n8n-can-and-cannot-replace)
4. [Migration Strategy — Two Approaches](#4-migration-strategy--two-approaches)
5. [Approach A: Full n8n Workflow (Recommended for Text-Based)](#5-approach-a-full-n8n-workflow-recommended-for-text-based)
6. [Approach B: Hybrid — n8n Orchestrates Your Existing Backend](#6-approach-b-hybrid--n8n-orchestrates-your-existing-backend)
7. [Step-by-Step: Building Each Workflow in n8n](#7-step-by-step-building-each-workflow-in-n8n)
8. [RAG Knowledge Base in n8n](#8-rag-knowledge-base-in-n8n)
9. [Database (SQLite → n8n-compatible)](#9-database-sqlite--n8n-compatible)
10. [Handling Voice (STT + TTS) in n8n](#10-handling-voice-stt--tts-in-n8n)
11. [Environment Variables & Credentials Setup](#11-environment-variables--credentials-setup)
12. [Comparing Feature Parity](#12-comparing-feature-parity)
13. [Recommended Final Architecture Diagram](#13-recommended-final-architecture-diagram)
14. [Tools & Services You Will Need](#14-tools--services-you-will-need)
15. [Honest Limitations & What to Keep in Python](#15-honest-limitations--what-to-keep-in-python)

---

## 1. Executive Summary

Your current project is a **real-time AI voice agent** that:

- Accepts **live microphone audio** over WebSocket
- Sends audio to **Groq Whisper API** for speech-to-text
- Retrieves relevant context from a **ChromaDB vector store** (RAG)
- Sends the transcript + RAG context to **LLaMA-3.3-70b** via Groq for a response
- Converts the response to **speech via Microsoft Edge TTS**
- Streams audio back to the browser
- Optionally logs patient inquiries to **SQLite** via the `log_inquiry` tool

**n8n is an excellent fit** for orchestrating the LLM logic, RAG retrieval (via HTTP tools), database writes, and admin-facing workflows. However, the **real-time WebSocket audio pipeline** (VAD + Whisper streaming + Edge TTS PCM streaming) cannot be replicated inside n8n natively — n8n is fundamentally HTTP-request driven, not a streaming binary protocol handler.

This guide presents **two strategies**:
- **Approach A:** Build the entire conversational + data logic in n8n (best if you switch the frontend to a phone/telephony platform like Twilio, Vapi, or Bland.ai)
- **Approach B (Hybrid):** Keep the WebSocket audio layer in Python, but have it **call n8n webhooks** for LLM processing, RAG, and DB writes — giving you n8n's visual orchestration for the "brain" part

---

## 2. Current Codebase Architecture

### File Map

| File | Role |
|---|---|
| `app/main.py` | FastAPI app, WebSocket handler, REST endpoints |
| `app/agent.py` | LLM orchestration, function calling (`log_inquiry`) |
| `app/whisper_client.py` | STT (Groq Whisper), TTS (Edge TTS), VAD (energy-based) |
| `app/rag.py` | ChromaDB ingestion and vector search |
| `app/database.py` | SQLAlchemy models: `PatientInquiry`, `CallSession` |
| `app/settings.py` | System prompt, agent name, voice, temperature config |
| `app/config.py` | API keys, logging, CORS middleware |
| `knowledge/*.md` | Source documents fed into ChromaDB |
| `data/appointments.db` | SQLite database |
| `data/chroma/` | ChromaDB vector store |

### Data Flow (Current)

```
Browser Mic Audio (PCM16)
    ↓ WebSocket (binary)
AudioBuffer (VAD — energy-based silence detection)
    ↓ when silence detected
Groq Whisper API (whisper-large-v3-turbo)  ← STT
    ↓ transcript text
RAG Query (ChromaDB — all-MiniLM-L6-v2 embeddings)
    ↓ top-3 chunks injected into system prompt
Groq Chat Completions (llama-3.3-70b-versatile)  ← LLM
    ↓ may call log_inquiry tool
SQLite DB write (PatientInquiry)
    ↓ final text response
Edge TTS (en-AU-NatashaNeural → MP3 → PCM16)  ← TTS
    ↓ WebSocket (binary, 100ms chunks)
Browser Speaker (AudioContext)
```

### APIs & Keys Required

- `GROQ_API_KEY` — used for both Whisper STT and LLaMA-3.3 LLM

---

## 3. What n8n Can and Cannot Replace

### ✅ n8n CAN Handle

| Component | n8n Solution |
|---|---|
| Calling Groq LLaMA-3.3 LLM | HTTP Request node → Groq Chat Completions API |
| RAG retrieval | HTTP Request to an external embedding/vector API (Pinecone, Supabase pgvector, or Weaviate) |
| Logging inquiries to DB | Postgres / MySQL / Airtable / Notion nodes |
| System prompt management | n8n Variables or Set node |
| Tool/function calling logic | IF node → Switch node → separate sub-workflow |
| Webhook triggers from the frontend | Webhook node |
| Sending results back | Respond to Webhook node |
| File ingestion (knowledge docs upload) | Form trigger + Read Binary File + HTTP Request to embedding service |
| Admin dashboard data (call history) | Database read + API response |
| Sending email/SMS notifications on new inquiries | Gmail/Twilio nodes |

### ❌ n8n CANNOT Handle Natively

| Component | Why Not | Alternative |
|---|---|---|
| Real-time WebSocket binary audio | n8n doesn't support persistent WebSocket connections for binary streaming | Keep Python layer for this |
| Energy-based Voice Activity Detection (VAD) | Requires DSP on raw PCM16 bytes | Keep in Python or use Deepgram/AssemblyAI |
| Edge TTS streaming (PCM16 chunks at 100ms intervals) | Requires async generator that streams binary back over WebSocket | Keep in Python |
| ChromaDB (local) vector store | n8n has no native ChromaDB node; ChromaDB has no hosted HTTP API by default | Switch to Pinecone, Supabase pgvector, or run ChromaDB as a separate service |
| Session-scoped conversation memory (in-memory list `messages`) | n8n is stateless between executions | Use n8n's built-in memory with AI Agent node, or store in Redis/DB |

---

## 4. Migration Strategy — Two Approaches

### Approach A: Full n8n (Telephony-First)
> Best if you want to **replace the browser frontend** with a phone number or a voice platform.

**How it works:**
- Sign up for **Vapi.ai**, **Bland.ai**, or **Twilio Voice** to handle the call
- These platforms handle STT and TTS natively
- When a caller speaks, they send a **webhook** to your n8n instance with the transcript
- n8n handles: RAG lookup, LLM call, `log_inquiry` tool logic, DB write
- n8n sends back the text response; the phone platform speaks it

**Pros:** Fully visual, no code, real phone number, enterprise-ready  
**Cons:** You lose your custom browser frontend; monthly costs for Vapi/Bland

---

### Approach B: Hybrid (Keep Python for Audio, n8n for Logic)
> Best if you want to **keep the existing browser-based frontend** and just move the "business logic brain" to n8n.

**How it works:**
- Keep `app/whisper_client.py` (VAD + STT + TTS) and the WebSocket handler in Python
- Replace `process_llm_turn()` in `app/agent.py` with an HTTP POST to an **n8n Webhook**
- n8n receives the transcript + message history, runs RAG + LLM + tool logic, returns JSON
- Python gets the response and feeds it back into Edge TTS → WebSocket as before

**Pros:** Keep your existing UI; only "brain" moves to n8n for visual editing  
**Cons:** Still need Python running; two systems to maintain

---

## 5. Approach A: Full n8n Workflow (Recommended for Text-Based)

### Prerequisites
- n8n installed (cloud or self-hosted: `npx n8n`)
- Groq API key
- Pinecone or Supabase account (for vector search/RAG)
- Vapi.ai or Bland.ai account (for voice calls), OR use browser-based Retell AI

### Main Workflow: Inbound Voice Webhook

```
[Webhook Trigger]
    ↓  { transcript, call_id, conversation_history }
[Set Node — Build System Prompt]
    ↓
[HTTP Request — Pinecone/Supabase Vector Search]
    ↓  top-3 RAG chunks
[Code Node — Inject RAG into System Prompt]
    ↓
[HTTP Request — Groq Chat Completions]
    ↓  LLM response (may include tool_calls)
[IF Node — Did LLM call log_inquiry tool?]
    ├── YES → [Postgres Node — Insert PatientInquiry] → [HTTP Request — Groq (second pass)]
    └── NO  → [Respond to Webhook — return text response]
```

### Groq Chat API HTTP Request Node Configuration

- **Method:** POST
- **URL:** `https://api.groq.com/openai/v1/chat/completions`
- **Headers:**
  - `Authorization: Bearer {{ $credentials.groqApiKey }}`
  - `Content-Type: application/json`
- **Body (JSON):**

```json
{
  "model": "llama-3.3-70b-versatile",
  "messages": "{{ $json.messages }}",
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "log_inquiry",
        "description": "Log a patient inquiry. Call only after collecting name, type, and notes.",
        "parameters": {
          "type": "object",
          "properties": {
            "name": { "type": "string" },
            "inquiry_type": {
              "type": "string",
              "enum": ["booking", "general_question", "referral_query", "callback"]
            },
            "notes": { "type": "string" }
          },
          "required": ["name", "inquiry_type", "notes"]
        }
      }
    }
  ],
  "tool_choice": "auto",
  "temperature": 0.7,
  "max_tokens": 200
}
```

---

## 6. Approach B: Hybrid — n8n Orchestrates Your Existing Backend

### Step 1: Modify `app/agent.py`

Replace the entire `process_llm_turn()` function body with an HTTP call to n8n:

```python
import httpx

N8N_WEBHOOK_URL = "http://localhost:5678/webhook/voice-agent"

async def process_llm_turn(messages: list) -> dict:
    """Delegate LLM orchestration to n8n."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(N8N_WEBHOOK_URL, json={"messages": messages})
        resp.raise_for_status()
        return resp.json()  # expects: { "response": "...", "tool_calls": [...] }
```

### Step 2: Create n8n Webhook Workflow

1. Open n8n → New Workflow
2. Add **Webhook** node
   - Method: POST
   - Path: `voice-agent`
   - Response Mode: `Last Node`
3. Add **Code** node — extract transcript and conversation history from `{{ $json.body }}`
4. Add **HTTP Request** node — call Pinecone/Supabase for RAG
5. Add **HTTP Request** node — call Groq LLM
6. Add **IF** node — check for `tool_calls` in response
7. **IF YES:** Add **Postgres** node to insert inquiry, then second Groq call
8. Add **Respond to Webhook** node — return `{ response, tool_calls }`

### Step 3: Keep Python Running

Your Python server still handles:
- WebSocket connection from the browser
- VAD and audio buffering
- Groq Whisper for STT
- Edge TTS for speech synthesis
- Streaming PCM16 audio back

The only change: instead of calling Groq LLM internally, it calls your n8n webhook.

---

## 7. Step-by-Step: Building Each Workflow in n8n

### Workflow 1: Main Conversational AI

| Step | Node Type | Configuration |
|---|---|---|
| 1 | Webhook | POST `/webhook/voice-agent` |
| 2 | Set | Build `messages` array with system prompt |
| 3 | HTTP Request | POST to Pinecone — vector search |
| 4 | Code | Inject RAG chunks into system prompt |
| 5 | HTTP Request | POST to Groq `/v1/chat/completions` |
| 6 | IF | `{{ $json.choices[0].message.tool_calls }}` exists? |
| 7a | Code | Parse `log_inquiry` tool args |
| 7b | Postgres | INSERT INTO patient_inquiries |
| 7c | HTTP Request | Second Groq call for final response |
| 8 | Respond to Webhook | Return JSON `{ response, tool_calls }` |

### Workflow 2: Knowledge Ingestion

| Step | Node Type | Configuration |
|---|---|---|
| 1 | Webhook | POST `/webhook/ingest-knowledge` |
| 2 | Read Binary File | Read uploaded .md, .txt, .pdf files |
| 3 | Code | Chunk text (500 chars, 100 overlap) |
| 4 | HTTP Request | POST chunks to Pinecone upsert |
| 5 | Respond to Webhook | Return `{ status: "success", chunks: N }` |

### Workflow 3: New Inquiry Notification

| Step | Node Type | Configuration |
|---|---|---|
| 1 | Postgres Trigger | On INSERT to `patient_inquiries` table |
| 2 | Gmail / Twilio SMS | Send notification to clinic staff |

### Workflow 4: Call History Report

| Step | Node Type | Configuration |
|---|---|---|
| 1 | Webhook | GET `/webhook/call-history` |
| 2 | Postgres | SELECT * FROM call_sessions ORDER BY start_time DESC LIMIT 50 |
| 3 | Respond to Webhook | Return JSON array |

---

## 8. RAG Knowledge Base in n8n

Because ChromaDB is a local file-based store and n8n has no native node for it, you must migrate to a cloud-accessible vector database.

### Option 1: Pinecone (Easiest)

1. Create a free Pinecone account → Create index (dimension: 384 for all-MiniLM-L6-v2)
2. In n8n add **HTTP Request** nodes for:
   - **Upsert:** `POST https://your-index.pinecone.io/vectors/upsert`
   - **Query:** `POST https://your-index.pinecone.io/query`
3. For embeddings, call the **Groq** or **OpenAI Embeddings API** before upserting

> **Note:** Groq doesn't provide an embeddings API. Use OpenAI's `text-embedding-3-small` or run a free **Jina AI** embeddings endpoint.

### Option 2: Supabase pgvector (Free, SQL-based)

1. Create a Supabase project → Enable `pgvector` extension
2. Create table:
```sql
CREATE TABLE knowledge_chunks (
  id SERIAL PRIMARY KEY,
  content TEXT,
  embedding VECTOR(384),
  source TEXT
);
```
3. Use n8n's built-in **Supabase** node for inserts
4. For similarity search, use n8n **Postgres** node with:
```sql
SELECT content, source 
FROM knowledge_chunks 
ORDER BY embedding <=> '{{ $json.query_vector }}'::vector 
LIMIT 3;
```

### Option 3: Keep ChromaDB — Expose It As an HTTP API

Run ChromaDB in server mode alongside your project:
```bash
chroma run --path ./data/chroma --port 8001
```
Then from n8n, call `http://localhost:8001/api/v1/collections/knowledge/query` using the HTTP Request node.

This requires the least code change — ChromaDB stays, n8n queries it via HTTP.

---

## 9. Database (SQLite → n8n-compatible)

SQLite cannot be accessed directly by n8n. You have two options:

### Option 1: Migrate to PostgreSQL (Recommended)

1. Install PostgreSQL locally or use free tier on **Supabase** / **Railway**
2. Export your SQLite data:
```bash
sqlite3 data/appointments.db .dump > dump.sql
```
3. Import into Postgres (adjust syntax for types)
4. In n8n, use the built-in **Postgres** node with your DB credentials

Your tables in Postgres:
```sql
CREATE TABLE patient_inquiries (
  id SERIAL PRIMARY KEY,
  patient_name VARCHAR(255),
  inquiry_details TEXT,
  urgency VARCHAR(50) DEFAULT 'medium',
  created_at TIMESTAMP DEFAULT NOW(),
  status VARCHAR(50) DEFAULT 'open'
);

CREATE TABLE call_sessions (
  id SERIAL PRIMARY KEY,
  start_time TIMESTAMP,
  end_time TIMESTAMP,
  duration_seconds INTEGER DEFAULT 0,
  messages_count INTEGER DEFAULT 0,
  tickets_created INTEGER DEFAULT 0
);
```

### Option 2: Use Airtable or Notion (No-Code Alternative)

- Create an **Airtable** base with `PatientInquiries` and `CallSessions` tables
- Use n8n's native **Airtable** node to insert/query records
- Provides beautiful spreadsheet-style visibility of all inquiries

---

## 10. Handling Voice (STT + TTS) in n8n

### Option A: Use Vapi.ai (Best Full-Stack Voice Platform)

Vapi handles everything — phone calls, STT, and TTS — and webhooks your n8n:

1. Create a Vapi account → Create an Assistant
2. Set **System Prompt** to your Soul AI prompt  
3. Set **Model:** Custom → Provider: Groq → Model: `llama-3.3-70b-versatile`
4. Set **Voice:** ElevenLabs or Cartesia (Vapi handles TTS)
5. Set **Server URL** to your n8n webhook: `https://your-n8n.com/webhook/voice-agent`
6. Vapi will POST the transcript to n8n and speak n8n's text response

**Webhook payload from Vapi:**
```json
{
  "message": {
    "type": "function-call",
    "call": { "id": "call_abc123" },
    "transcript": "I'd like to book an MRI scan",
    "messages": [ ... conversation history ... ]
  }
}
```

### Option B: Retell AI (Similar to Vapi, easier setup)

- Point Retell to your n8n webhook
- Retell handles WebRTC, STT (Deepgram), TTS (ElevenLabs/OpenAI)

### Option C: Keep Python for Audio, Use n8n for Logic (Hybrid)

As described in Approach B, only the LLM + RAG + DB logic moves to n8n.

### Option D: Twilio + Groq (Phone calls via Twilio)

1. Buy a Twilio phone number
2. Set **Voice Webhook** to n8n: `POST https://your-n8n.com/webhook/twilio-inbound`
3. n8n receives the spoken transcript (Twilio auto-does STT via Programmable Voice)
4. n8n calls Groq LLM, returns TwiML with `<Say>` for TTS

---

## 11. Environment Variables & Credentials Setup

In n8n, all secrets are stored as **Credentials** (not `.env`).

### Credentials to Create in n8n

| Credential Name | Type | Fields |
|---|---|---|
| `Groq API` | HTTP Header Auth | `Authorization: Bearer <GROQ_API_KEY>` |
| `Pinecone` | HTTP Header Auth | `Api-Key: <PINECONE_API_KEY>` |
| `PostgreSQL` | Postgres | host, port, user, password, database |
| `Supabase` | Supabase | URL, anon key |
| `Gmail` | Gmail OAuth2 | (follow n8n OAuth flow) |
| `Twilio` | Twilio | Account SID, Auth Token |

### System Prompt as n8n Variable

In n8n → Settings → Variables, create:

| Variable | Value |
|---|---|
| `SOUL_AI_SYSTEM_PROMPT` | (paste your full system prompt from `app/settings.py`) |
| `AGENT_VOICE` | `en-AU-NatashaNeural` |
| `LLM_TEMPERATURE` | `0.7` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` |

Reference in nodes as `{{ $vars.SOUL_AI_SYSTEM_PROMPT }}`

---

## 12. Comparing Feature Parity

| Feature | Current Python | n8n Equivalent | Notes |
|---|---|---|---|
| Groq Whisper STT | `whisper_client.py` | Vapi/Retell handles it | Or keep Python |
| LLaMA-3.3 LLM | `agent.py` + Groq SDK | HTTP Request node | ✅ Direct replacement |
| RAG (ChromaDB) | `rag.py` | Pinecone/Supabase HTTP | Needs vector DB migration |
| Function Calling (`log_inquiry`) | In-code JSON parse | IF + Code node | ✅ Possible |
| SQLite DB writes | `database.py` | Postgres node | ✅ With DB migration |
| Edge TTS streaming | `whisper_client.py` | Vapi/Retell handles it | Or keep Python |
| WebSocket audio stream | `app/main.py` | ❌ Not possible in n8n | Keep Python |
| Barge-in detection | `app/main.py` | ❌ Not possible in n8n | Vapi handles this |
| Call session logging | `app/main.py` | Postgres node | ✅ Possible |
| Knowledge file upload | `/upload` endpoint | Form trigger + HTTP | ✅ Possible |
| Settings management | `data/settings.json` | n8n Variables | ✅ Possible |
| System prompt hot-reload | `load_settings()` | n8n Variables | ✅ Possible |

---

## 13. Recommended Final Architecture Diagram

### Approach A (Phone-based, Full n8n):

```
[Patient Phone Call]
       ↓
[Vapi.ai / Retell AI]
  ├── STT: Deepgram / OpenAI Whisper
  ├── TTS: ElevenLabs / Cartesia
  └── Webhook → n8n
       ↓
[n8n Webhook Trigger]
       ↓
[Set: Build Messages Array]
       ↓
[HTTP Request: Groq LLaMA-3.3]
       ↓
[IF: tool_calls present?]
  ├── YES → [Code: Parse args] → [Postgres: INSERT inquiry] → [HTTP: Second Groq call]
  └── NO  → continue
       ↓
[HTTP Request: Pinecone — RAG Query]
       ↓
[Respond to Webhook: { "response": "..." }]
       ↓
[Vapi speaks response to caller]
```

### Approach B (Hybrid, Keep Browser Frontend):

```
[Browser Microphone]
       ↓ WebSocket (PCM16)
[Python FastAPI + AudioBuffer VAD]
       ↓ transcript text
[Python: HTTP POST to n8n Webhook]
       ↓
[n8n: RAG + LLM + tool logic]
       ↓ { response, tool_calls }
[Python: Edge TTS → PCM16]
       ↓ WebSocket (PCM16 chunks)
[Browser Speaker]
```

---

## 14. Tools & Services You Will Need

### Required

| Tool | Purpose | Cost |
|---|---|---|
| [n8n](https://n8n.io) | Workflow orchestration | Free self-hosted / $20+/mo cloud |
| [Groq](https://groq.com) | LLaMA-3.3 LLM + Whisper STT | Free tier available |
| [Pinecone](https://pinecone.io) | Vector database for RAG | Free tier: 1 index |
| [PostgreSQL](https://supabase.com) | Patient inquiries + session logs | Free on Supabase |

### For Voice (Pick One)

| Tool | Purpose | Cost |
|---|---|---|
| [Vapi.ai](https://vapi.ai) | Full voice AI platform | ~$0.05/min |
| [Retell AI](https://retellai.com) | Full voice AI platform | ~$0.05/min |
| [Twilio](https://twilio.com) | Phone call infrastructure | ~$0.013/min + number |
| [Bland.ai](https://bland.ai) | Outbound AI calling | ~$0.09/min |

### Optional

| Tool | Purpose |
|---|---|
| [Jina AI Embeddings](https://jina.ai) | Free embeddings API (no OpenAI key needed) |
| [Airtable](https://airtable.com) | No-code alternative to Postgres for inquiries |
| [Railway.app](https://railway.app) | Host PostgreSQL + n8n in one place |

---

## 15. Honest Limitations & What to Keep in Python

Even after migration, **these components must remain in Python** (or be replaced by a paid voice platform):

| Component | Why Keep in Python | Why a Platform Replaces It |
|---|---|---|
| WebSocket handler | n8n doesn't support persistent WSS binary streams | Vapi/Retell handle the connection |
| Energy-based VAD | Raw PCM16 signal processing requires NumPy | Vapi/Retell have built-in VAD |
| Groq Whisper STT | Requires in-memory WAV construction and audio API calls | Vapi: uses Deepgram; Retell: Deepgram |
| Edge TTS PCM streaming | Async generator streaming binary over WebSocket | Vapi handles TTS with Cartesia |
| Barge-in / interruption | Cancelling async tasks mid-stream | Vapi handles this natively |

### Recommendation

> If the goal is to **eliminate Python entirely**, migrate to **Vapi.ai** for voice handling and use n8n for all business logic (RAG, LLM, DB, notifications). This gives you:
> - A real phone number callers can dial
> - No server to maintain for audio
> - n8n visual workflows for everything else
> - Enterprise-grade reliability

> If you want to **keep the existing browser-based UI and WebSocket**, use the **Hybrid approach** — move only the LLM + RAG + database logic into n8n, while Python stays as the audio gateway.

---

## 🚀 Quick Start: Hybrid Setup (Get Running Fast)

### 1. Install & Start n8n

```bash
npx n8n
# Opens at http://localhost:5678
```

### 2. Import Workflow

Create a new workflow in n8n and build the Webhook → Groq → Respond chain as described in Section 7, Workflow 1.

### 3. Modify Python Agent

In `app/agent.py`, add at the top:
```python
import httpx
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/voice-agent"
```

Replace `process_llm_turn` body with the `httpx` call shown in Section 6, Step 1.

### 4. Start Both

```bash
# Terminal 1 — n8n
npx n8n

# Terminal 2 — Python server
.\.venv\Scripts\python.exe main.py
```

### 5. Test

Open the browser frontend → speak into the mic → Python handles audio → n8n handles LLM → response comes back and is spoken.

---

*This guide was generated by analyzing all source files in the Voice Agent project: `app/agent.py`, `app/main.py`, `app/whisper_client.py`, `app/rag.py`, `app/database.py`, `app/settings.py`, `app/config.py`, `knowledge/*.md`, and `requirements.txt`.*
