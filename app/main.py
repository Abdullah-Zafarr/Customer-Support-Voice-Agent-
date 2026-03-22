from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
import os
import json
import asyncio
from datetime import datetime

from .config import log_latency_middleware, logger
from .database import Base, engine, CallSession, get_db
from .rag import ingest_documents
from .settings import load_settings, save_settings
from .whisper_client import setup_stt, get_tts_stream
from .agent import process_llm_turn

app = FastAPI(title="Voice Agent API")

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(log_latency_middleware)

# Ensure the static directory exists before mounting, or create it if not
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ─── STARTUP EVENT ───
@app.on_event("startup")
async def startup_event():
    """Auto-ingest knowledge documents on server startup."""
    knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
    if os.path.isdir(knowledge_dir) and any(
        f.endswith(('.txt', '.md', '.pdf')) for f in os.listdir(knowledge_dir)
        if f != "README.md"
    ):
        logger.info("Knowledge folder detected — ingesting documents...")
        result = await run_in_threadpool(ingest_documents, knowledge_dir)
        logger.info(f"Ingestion result: {result['message']}")
    else:
        logger.info("No knowledge documents found. RAG will be inactive.")


# ─── API ENDPOINTS ───
@app.get("/")
async def root():
    return FileResponse("app/static/index.html")

@app.post("/ingest")
async def ingest():
    """Re-index all documents in the knowledge/ folder."""
    result = await run_in_threadpool(ingest_documents)
    return result

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Upload documents to the knowledge/ folder and trigger ingestion."""
    knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
    os.makedirs(knowledge_dir, exist_ok=True)
    
    uploaded_files = []
    for file in files:
        file_path = os.path.join(knowledge_dir, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        uploaded_files.append(file.filename)
        logger.info(f"Uploaded: {file.filename}")
    
    # Trigger re-index
    result = await run_in_threadpool(ingest_documents, knowledge_dir)
    return {
        "status": "success",
        "files": uploaded_files,
        "message": f"Successfully uploaded and indexed {len(uploaded_files)} file(s)."
    }

class SettingsUpdate(BaseModel):
    agent_name: str = None
    voice: str = None
    temperature: float = None
    system_prompt: str = None

@app.get("/api/settings")
async def get_settings():
    return load_settings()

@app.patch("/api/settings")
async def update_settings(payload: SettingsUpdate):
    data = {k: v for k, v in payload.dict().items() if v is not None}
    if save_settings(data):
        return {"status": "success", "message": "Settings updated."}
    return {"status": "error", "message": "Failed to update settings."}

@app.get("/api/knowledge-files")
async def get_knowledge_files():
    knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
    if not os.path.exists(knowledge_dir):
        return []
    files = [f for f in os.listdir(knowledge_dir) if f != "README.md" and f.endswith(('.txt', '.md', '.pdf', '.json'))]
    return files

@app.delete("/api/knowledge-files/{filename}")
async def delete_knowledge_file(filename: str):
    knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")
    file_path = os.path.join(knowledge_dir, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        # Trigger re-index
        await run_in_threadpool(ingest_documents, knowledge_dir)
        return {"status": "success", "message": f"Deleted {filename} and re-indexed knowledge."}
    return {"status": "error", "message": "File not found."}


# ─── WEBSOCKET ENDPOINT (Inlined from websocket.py) ───
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted.")
    
    messages: List[Dict[str, Any]] = []
    tts_task = None
    agent_speaking = False
    
    # Session stats
    session_start = datetime.now()
    tickets_created = 0
    
    async def on_transcript(transcript: str, is_final: bool):
        nonlocal tts_task
        if not transcript.strip() or not is_final:
            return  
            
        logger.info(f"User Transcribed: {transcript}")
        await websocket.send_json({"type": "transcript", "text": transcript})
        
        if tts_task and not tts_task.done():
            tts_task.cancel()
            logger.info("Barge-in detected! Cancelled TTS.")
            await websocket.send_json({"type": "clear_audio"})
            
        messages.append({"role": "user", "content": transcript})
        tts_task = asyncio.create_task(process_and_speak())

    async def process_and_speak():
        nonlocal agent_speaking
        checkpoint = [m.copy() for m in messages]
        try:
            current_settings = load_settings()
            current_voice = current_settings.get("voice", "en-AU-NatashaNeural")
            
            result = await process_llm_turn(messages)
            llm_response = result["response"]
            tool_calls_info = result.get("tool_calls", [])

            logger.info(f"LLM Response: {llm_response}")
            messages.append({"role": "assistant", "content": llm_response})

            for tc in tool_calls_info:
                if tc["name"] == "log_inquiry":
                    nonlocal tickets_created
                    tickets_created += 1
                await websocket.send_json({
                    "type": "tool_call",
                    "name": tc["name"],
                    "result": tc.get("result")
                })

            await websocket.send_json({"type": "response", "text": llm_response})
            
            agent_speaking = True
            try:
                async for audio_chunk in get_tts_stream(llm_response, voice=current_voice):
                    if asyncio.current_task().cancelled():
                        break
                    await websocket.send_bytes(audio_chunk)
            finally:
                agent_speaking = False
                
            await websocket.send_json({"type": "tts_complete"})
            logger.info("TTS stream completed.")
            
        except asyncio.CancelledError:
            messages.clear()
            messages.extend(checkpoint)
            agent_speaking = False
            logger.info("Barge-in: message history restored.")
        except Exception as e:
            logger.error(f"Error in LLM/TTS logic: {e}")
            try:
                await websocket.send_json({"type": "error", "text": str(e)})
            except Exception:
                pass  

    stt_buffer = await setup_stt(on_transcript)
    if not stt_buffer:
        await websocket.close(code=1011, reason="Failed to initialize Whisper STT")
        return

    try:
        while True:
            data = await websocket.receive()
            if "bytes" in data:
                if not agent_speaking:
                    audio_data = data["bytes"]
                    await stt_buffer.add_chunk(audio_data)
            elif "text" in data:
                try:
                    text_msg = json.loads(data["text"])
                except json.JSONDecodeError:
                    logger.warning(f"Received malformed JSON over WebSocket: {data['text']}")
                    continue

                if text_msg.get("type") == "greeting":
                    logger.info("Initializing conversation with greeting")
                    tts_task = asyncio.create_task(process_and_speak())
                elif text_msg.get("type") == "barge_in":
                    if tts_task and not tts_task.done():
                        tts_task.cancel()
                        await websocket.send_json({"type": "clear_audio"})
                elif text_msg.get("type") == "correction":
                    corrected = text_msg.get("corrected", "").strip()
                    original = text_msg.get("original", "").strip()
                    if corrected and original:
                        for i in range(len(messages) - 1, -1, -1):
                            if messages[i].get("role") == "user" and messages[i].get("content") == original:
                                messages[i]["content"] = corrected
                                del messages[i+1:] 
                                logger.info(f"Transcript corrected: '{original}' → '{corrected}' (History truncated)")
                                break
                        
                        if tts_task and not tts_task.done():
                            tts_task.cancel()
                            await websocket.send_json({"type": "clear_audio"})
                        tts_task = asyncio.create_task(process_and_speak())
                    
    except WebSocketDisconnect:
        logger.info("Client disconnected gracefully.")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
    finally:
        # Log call session
        duration = (datetime.now() - session_start).total_seconds()
        db = next(get_db())
        try:
            session = CallSession(
                start_time=session_start,
                end_time=datetime.now(),
                duration_seconds=int(duration),
                messages_count=len(messages),
                tickets_created=tickets_created
            )
            db.add(session)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log call session: {e}")
        finally:
            db.close()

@app.get("/api/history")
def get_call_history(db: Session = Depends(get_db)):
    try:
        sessions = db.query(CallSession).order_by(CallSession.start_time.desc()).limit(50).all()
        return {"status": "success", "data": [
            {
                "id": s.id,
                "start_time": s.start_time.isoformat(),
                "duration_seconds": s.duration_seconds,
                "messages_count": s.messages_count,
                "tickets_created": s.tickets_created
            } for s in sessions
        ]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
