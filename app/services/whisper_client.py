"""
Whisper STT + Edge TTS Client
Primary engine for Speech-to-Text using local Faster-Whisper 
and Text-to-Speech using Microsoft Edge TTS.
"""

import asyncio
import io
import tempfile
import os
import wave
import numpy as np
from faster_whisper import WhisperModel
import edge_tts
import av

from ..core.logger import logger

# ─── WHISPER MODEL (loaded once at startup) ───
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper model (small.en) — first load may take a moment to download...")
        _whisper_model = WhisperModel(
            "small.en",
            device="cpu",
            compute_type="int8",
        )
        logger.info("Whisper model loaded successfully.")
    return _whisper_model


# ─── VOICE ACTIVITY DETECTION (energy-based) ───
SILENCE_THRESHOLD = 500
SILENCE_DURATION_MS = 800
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
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

    async def add_chunk(self, chunk: bytes):
        async with self._lock:
            self.buffer.extend(chunk)
            rms = self._compute_rms(chunk)

            if rms > SILENCE_THRESHOLD:
                self.has_speech = True
                self._silence_accumulated = 0
            else:
                self._silence_accumulated += len(chunk)

            if self.has_speech and self._silence_accumulated >= self._silence_bytes_threshold:
                audio_data = bytes(self.buffer)
                self.buffer = bytearray()
                self.has_speech = False
                self._silence_accumulated = 0
                asyncio.create_task(self._transcribe(audio_data))

    async def _transcribe(self, pcm_bytes: bytes):
        try:
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(pcm_bytes)
            wav_buffer.seek(0)

            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(None, self._run_whisper, wav_buffer)

            if transcript and transcript.strip():
                await self.on_speech_complete(transcript.strip(), True)

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")

    def _run_whisper(self, wav_buffer: io.BytesIO) -> str:
        model = get_whisper_model()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_buffer.read())
            tmp_path = tmp.name

        try:
            segments, info = model.transcribe(
                tmp_path,
                language="en",
                beam_size=1,
                best_of=1,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=400,
                ),
            )
            text = " ".join(segment.text for segment in segments)
            return text
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


async def setup_stt(on_transcript_callback):
    """Setup Whisper-based STT. Returns an AudioBuffer that accepts raw PCM16 chunks."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_whisper_model)

    audio_buffer = AudioBuffer(on_transcript_callback)
    logger.info("Whisper STT initialized and ready.")
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


import re

def _split_into_sentences(text: str) -> list:
    """Split text into sentences for incremental TTS streaming."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s.strip()]


async def get_tts_stream(text: str):
    """Generate TTS audio sentence-by-sentence for low-latency streaming."""
    try:
        sentences = _split_into_sentences(text)
        if not sentences:
            return

        for sentence in sentences:
            communicate = edge_tts.Communicate(
                sentence,
                voice="en-US-GuyNeural",
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

            offset = 0
            while offset < len(pcm_data):
                chunk = pcm_data[offset:offset + TTS_CHUNK_BYTES]
                yield chunk
                offset += TTS_CHUNK_BYTES

    except Exception as e:
        logger.error(f"Error in TTS pipeline: {e}")

