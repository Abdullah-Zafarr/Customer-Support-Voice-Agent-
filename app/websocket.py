import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any

from .whisper_client import setup_stt, get_tts_stream
from .agent import process_llm_turn
from .logger import logger

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted.")
    
    messages: List[Dict[str, Any]] = []
    tts_task = None
    
    # Callback handles recognized speech from STT
    async def on_transcript(transcript: str, is_final: bool):
        nonlocal tts_task
        if not transcript.strip() or not is_final:
            return  # Wait for full sentence to avoid fragmented LLM queries
            
        logger.info(f"User Transcribed: {transcript}")
        
        # Send transcript to frontend for Live Transcript display
        await websocket.send_json({"type": "transcript", "text": transcript})
        
        if tts_task and not tts_task.done():
            tts_task.cancel()
            logger.info("Barge-in detected! Cancelled TTS.")
            # Send message to client to flush audio buffers
            await websocket.send_json({"type": "clear_audio"})
            
        messages.append({"role": "user", "content": transcript})
        tts_task = asyncio.create_task(process_and_speak())

    async def process_and_speak():
        try:
            # Get response from Groq (now returns dict with response + tool_calls)
            result = await process_llm_turn(messages)
            llm_response = result["response"]
            tool_calls_info = result.get("tool_calls", [])

            logger.info(f"LLM Response: {llm_response}")
            messages.append({"role": "assistant", "content": llm_response})

            # Send tool call info to frontend (for Live Transcript + Appointments)
            for tc in tool_calls_info:
                await websocket.send_json({
                    "type": "tool_call",
                    "name": tc["name"],
                    "result": tc.get("result")
                })

            # Send agent text response to frontend for Live Transcript
            await websocket.send_json({"type": "response", "text": llm_response})
            
            # Stream TTS chunks to client (Edge TTS produces MP3 chunks)
            async for audio_chunk in get_tts_stream(llm_response):
                await websocket.send_bytes(audio_chunk)
                
            await websocket.send_json({"type": "tts_complete"})
            logger.info("TTS stream completed.")
            
        except asyncio.CancelledError:
            logger.info("TTS generation aborted due to barge-in.")
        except Exception as e:
            logger.error(f"Error in LLM/TTS logic: {e}")
            try:
                await websocket.send_json({"type": "error", "text": str(e)})
            except Exception:
                pass  # WebSocket may already be closed

    # Initialize STT with Whisper
    stt_buffer = await setup_stt(on_transcript)
    if not stt_buffer:
        await websocket.close(code=1011, reason="Failed to initialize Whisper STT")
        return

    try:
        while True:
            data = await websocket.receive()
            if "bytes" in data:
                # Raw audio chunk received from client, pass to Whisper audio buffer
                audio_data = data["bytes"]
                await stt_buffer.add_chunk(audio_data)
            elif "text" in data:
                # Control messages or greetings
                text_msg = json.loads(data["text"])
                if text_msg.get("type") == "greeting":
                    logger.info("Initializing conversation with greeting")
                    tts_task = asyncio.create_task(process_and_speak())
                elif text_msg.get("type") == "correction":
                    corrected = text_msg.get("corrected", "").strip()
                    original = text_msg.get("original", "").strip()
                    if corrected and original:
                        # Replace the last matching user message with the corrected text
                        for i in range(len(messages) - 1, -1, -1):
                            if messages[i].get("role") == "user" and messages[i].get("content") == original:
                                messages[i]["content"] = corrected
                                logger.info(f"Transcript corrected: '{original}' → '{corrected}'")
                                break
                        # Re-process with corrected text
                        if tts_task and not tts_task.done():
                            tts_task.cancel()
                            await websocket.send_json({"type": "clear_audio"})
                        tts_task = asyncio.create_task(process_and_speak())
                    
    except WebSocketDisconnect:
        logger.info("Client disconnected gracefully.")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
