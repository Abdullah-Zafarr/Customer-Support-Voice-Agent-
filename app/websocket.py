import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any

from .deepgram_client import setup_stt, get_tts_stream
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
            
            # Stream TTS chunks to client
            async for audio_chunk in get_tts_stream(llm_response):
                await websocket.send_bytes(audio_chunk)
                
            await websocket.send_json({"type": "tts_complete"})
            logger.info("TTS stream completed.")
            
        except asyncio.CancelledError:
            logger.info("TTS generation aborted due to barge-in.")
        except Exception as e:
            logger.error(f"Error in LLM/TTS logic: {e}")
            await websocket.send_json({"type": "error", "text": str(e)})

    # Initialize STT with Deepgram
    stt_connection = await setup_stt(on_transcript)
    if not stt_connection:
        await websocket.close(code=1011, reason="Failed to connect to Deepgram STT")
        return

    try:
        while True:
            data = await websocket.receive()
            if "bytes" in data:
                # Raw audio chunk received from client, pass to Deepgram STT
                audio_data = data["bytes"]
                await stt_connection.send(audio_data)
            elif "text" in data:
                # Control messages or greetings
                text_msg = json.loads(data["text"])
                if text_msg.get("type") == "greeting":
                    logger.info("Initializing conversation with greeting")
                    tts_task = asyncio.create_task(process_and_speak())
                    
    except WebSocketDisconnect:
        logger.info("Client disconnected gracefully.")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
    finally:
        await stt_connection.finish()
