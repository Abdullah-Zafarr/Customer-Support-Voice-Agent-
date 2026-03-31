"""
Whisper STT + Edge TTS Client
Primary engine for Speech-to-Text using Groq Whisper API 
and Text-to-Speech using Microsoft Edge TTS with pydub conversion.
"""

import asyncio
import io
import os
import wave
import numpy as np
import edge_tts
import av
from nltk.tokenize import sent_tokenize
from groq import AsyncGroq

from .config import logger, settings

# ─── VOICE ACTIVITY DETECTION (energy-based) ───
SILENCE_THRESHOLD = 800  # Bumped slightly to ignore background noise/fan noise better
SILENCE_DURATION_MS = 500
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2


class AudioBuffer:
    """Accumulates PCM16 audio chunks and detects speech boundaries using energy-based VAD."""

    def __init__(self, on_speech_complete_callback):
        self.buffer = bytearray()
        self.silence_frames = 0
        self.has_speech = False
        self.on_speech_complete = on_speech_complete_callback
        self._lock = asyncio.Lock()
        self._silence_bytes_threshold = int(SAMPLE_RATE * BYTES_PER_SAMPLE * SILENCE_DURATION_MS / 1000)
        self._silence_accumulated = 0

    def _compute_rms(self, pcm_bytes: bytes) -> float:
        if len(pcm_bytes) < 2:
            return 0.0
        
        # Prevent odd-length buffer crashes
        safe_bytes = pcm_bytes[:len(pcm_bytes) - (len(pcm_bytes) % 2)]
        samples = np.frombuffer(safe_bytes, dtype=np.int16)
        
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

    async def add_chunk(self, chunk: bytes):
        async with self._lock:
            rms = self._compute_rms(chunk)

            if rms > SILENCE_THRESHOLD:
                self.has_speech = True
                self._silence_accumulated = 0
            else:
                self._silence_accumulated += len(chunk)

            self.buffer.extend(chunk)

            # --- BUG FIX: SILENCE ACCUMULATION ---
            # If we haven't detected speech yet, don't let the buffer grow infinitely with silence.
            # Keep only a 500ms sliding pre-buffer window to catch the start of sentences.
            if not self.has_speech:
                max_pre_buffer = int(SAMPLE_RATE * BYTES_PER_SAMPLE * 0.5) # 500ms pre-buffer
                if len(self.buffer) > max_pre_buffer:
                    self.buffer = self.buffer[-max_pre_buffer:]

            if self.has_speech and self._silence_accumulated >= self._silence_bytes_threshold:
                # Dispatch for transcription
                audio_data = bytes(self.buffer)
                self.buffer = bytearray()
                self.has_speech = False
                self._silence_accumulated = 0
                
                # --- HEURISTIC: DISCARD ISOLATED NOISE POPS ---
                # A 500ms silence threshold is ~16,000 bytes. If total audio length is extremely short,
                # it means VAD was triggered by a quick mouse-click or pop and instantly went quiet.
                # Threshold buffer (800ms) = 25,600 bytes. Minimum valid utterance is usually above 1 sec total.
                if len(audio_data) < 8000: # Ignore clicks
                    return
                    
                asyncio.create_task(self._transcribe(audio_data))

    async def _transcribe(self, pcm_bytes: bytes):
        try:
            # Wrap as WAV in-memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(pcm_bytes)
            wav_buffer.seek(0)

            # Use Groq Whisper API (Upgrades accuracy to whisper-large-v3-turbo)
            client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            
            transcription = await client.audio.transcriptions.create(
                file=("audio.wav", wav_buffer.getvalue()), # Pass bytes
                model="whisper-large-v3-turbo",
                language="en",
                temperature=0.0,
                prompt="Please properly transcribe the user. Do not transcribe background noise as 'Thank you' or 'Yeah'."
            )
            transcript = transcription.text.strip()

            import string
            clean_text = transcript.lower().translate(str.maketrans("", "", string.punctuation)).strip()
            hallucinations = ["thank you", "thanks", "yeah", "okay", "you", "bye"]
            
            if clean_text in hallucinations and len(pcm_bytes) < 60000:
                logger.info("Filtered likely Whisper hallucination.")
                return

            if transcript:
                await self.on_speech_complete(transcript, True)

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")


async def setup_stt(on_transcript_callback):
    """Setup Whisper-based STT. Returns an AudioBuffer that accepts raw PCM16 chunks."""
    audio_buffer = AudioBuffer(on_transcript_callback)
    logger.info("Groq Whisper API STT initialized and ready.")
    return audio_buffer


# ─── TTS: Edge TTS → PCM16 chunks ───
TTS_SAMPLE_RATE = 24000
TTS_CHUNK_DURATION_MS = 100  # 100ms per chunk for smooth streaming
TTS_CHUNK_SAMPLES = int(TTS_SAMPLE_RATE * TTS_CHUNK_DURATION_MS / 1000)
TTS_CHUNK_BYTES = TTS_CHUNK_SAMPLES * 2  # 16-bit = 2 bytes per sample


def _convert_mp3_to_pcm(mp3_bytes: bytes) -> bytes:
    """Convert MP3 bytes to raw PCM16 mono 24kHz using PyAV. Runs in thread pool."""
    input_buf = io.BytesIO(mp3_bytes)
    output_buf = io.BytesIO()

    container = av.open(input_buf, mode='r')
    resampler = av.AudioResampler(
        format='s16',
        layout='mono',
        rate=TTS_SAMPLE_RATE,
    )

    for frame in container.decode(audio=0):
        resampled = resampler.resample(frame)
        for rf in resampled:
            output_buf.write(rf.to_ndarray().tobytes())

    container.close()
    return output_buf.getvalue()


def _split_into_sentences(text: str) -> list:
    """Split text into sentences for incremental TTS streaming using nltk."""
    return sent_tokenize(text.strip())


async def get_tts_stream(text: str, voice: str = "en-AU-NatashaNeural"):
    """Generate TTS audio sentence-by-sentence for low-latency streaming."""
    try:
        sentences = _split_into_sentences(text)
        if not sentences:
            return

        for sentence in sentences:
            communicate = edge_tts.Communicate(
                sentence,
                voice=voice,
            )

            # Collect MP3 for this sentence
            mp3_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_chunks.append(chunk["data"])

            if not mp3_chunks:
                continue

            mp3_data = b"".join(mp3_chunks)

            # Convert and stream immediately
            loop = asyncio.get_event_loop()
            pcm_data = await loop.run_in_executor(None, _convert_mp3_to_pcm, mp3_data)

            # Yield chunks
            offset = 0
            while offset < len(pcm_data):
                chunk = pcm_data[offset:offset + TTS_CHUNK_BYTES]
                yield chunk
                offset += TTS_CHUNK_BYTES

    except Exception as e:
        logger.error(f"Error in TTS pipeline: {e}")
