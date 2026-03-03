import asyncio
import os
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)
from .config import settings
from .logger import logger

deepgram = DeepgramClient(settings.DEEPGRAM_API_KEY)

async def setup_stt(on_transcript_callback):
    """Setup Deepgram live STT connection."""
    try:
        dg_connection = deepgram.listen.asyncwebsocket.v("1")

        async def on_message(self, result, **kwargs):
            if result.channel.alternatives[0].transcript:
                transcript = result.channel.alternatives[0].transcript
                is_final = result.is_final
                await on_transcript_callback(transcript, is_final)

        async def on_error(self, error, **kwargs):
            logger.error(f"Deepgram STT Error: {error}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        options = LiveOptions(
            model="nova-3",
            language="en",
            smart_format=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
            interim_results=False, # Wait for final sentence boundary for simplicity right now
            endpointing=300 # 300ms of silence
        )

        if await dg_connection.start(options) is False:
            logger.error("Failed to start Deepgram STT connection")
            return None

        return dg_connection

    except Exception as e:
        logger.error(f"Error setting up Deepgram: {e}")
        return None

async def get_tts_stream(text: str):
    """Get Deepgram Aura TTS audio stream."""
    import httpx
    
    url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"
    headers = {
        "Authorization": f"Token {settings.DEEPGRAM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"text": text}
    
    try:
        async with httpx.AsyncClient() as client:
            # We stream the response
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    yield chunk
    except Exception as e:
        logger.error(f"Error calling Deepgram TTS: {e}")
