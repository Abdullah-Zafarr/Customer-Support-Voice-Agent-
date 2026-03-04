"""
Whisper STT + Edge TTS Client
Primary engine for Speech-to-Text using local Faster-Whisper 
and Text-to-Speech using Microsoft Edge TTS.
"""

import asyncio
import io
import struct
import tempfile
import os
import wave
import numpy as np
from faster_whisper import WhisperModel
import edge_tts

from .logger import logger

# ─── WHISPER MODEL (loaded once at startup) ───
# Using "tiny" for lowest latency on CPU. Options: tiny, base, small, medium, large-v3
_whisper_model = None

def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        logger.info("Loading Whisper model (tiny.en) — first load may take a moment...")
        _whisper_model = WhisperModel(
            "tiny.en",
            device="cpu",
            compute_type="int8",
        )
        logger.info("Whisper model loaded successfully.")
    return _whisper_model


# ─── VOICE ACTIVITY DETECTION (energy-based) ───
SILENCE_THRESHOLD = 500       # RMS energy below this = silence
SILENCE_DURATION_MS = 400     # Reduced from 800ms for faster response
SAMPLE_RATE = 16000
BYTES_PER_SAMPLE = 2          # 16-bit PCM


class AudioBuffer:
    """Accumulates PCM16 audio chunks and detects speech boundaries using energy-based VAD."""

    def __init__(self, on_speech_complete_callback):
        self.buffer = bytearray()
        self.silence_frames = 0
        self.has_speech = False
        self.on_speech_complete = on_speech_complete_callback
        self._lock = asyncio.Lock()
        # How many bytes of silence correspond to SILENCE_DURATION_MS
        self._silence_bytes_threshold = int(SAMPLE_RATE * BYTES_PER_SAMPLE * SILENCE_DURATION_MS / 1000)
        self._silence_accumulated = 0

    def _compute_rms(self, pcm_bytes: bytes) -> float:
        """Compute RMS energy of a PCM16 chunk."""
        if len(pcm_bytes) < 2:
            return 0.0
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        if len(samples) == 0:
            return 0.0
        return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

    async def add_chunk(self, chunk: bytes):
        """Add an audio chunk. If speech-then-silence is detected, trigger transcription."""
        async with self._lock:
            self.buffer.extend(chunk)
            rms = self._compute_rms(chunk)

            if rms > SILENCE_THRESHOLD:
                # Speech detected
                self.has_speech = True
                self._silence_accumulated = 0
            else:
                # Silence
                self._silence_accumulated += len(chunk)

            # If we had speech and now enough silence, trigger transcription
            if self.has_speech and self._silence_accumulated >= self._silence_bytes_threshold:
                audio_data = bytes(self.buffer)
                self.buffer = bytearray()
                self.has_speech = False
                self._silence_accumulated = 0
                # Fire transcription in background
                asyncio.create_task(self._transcribe(audio_data))

    async def _transcribe(self, pcm_bytes: bytes):
        """Transcribe accumulated audio using Whisper."""
        try:
            # Convert PCM16 to WAV in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(pcm_bytes)
            wav_buffer.seek(0)

            # Run Whisper transcription in a thread to not block the event loop
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(None, self._run_whisper, wav_buffer)

            if transcript and transcript.strip():
                await self.on_speech_complete(transcript.strip(), True)

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")

    def _run_whisper(self, wav_buffer: io.BytesIO) -> str:
        """Synchronous Whisper transcription (runs in thread pool)."""
        model = get_whisper_model()

        # Write to temp file since faster-whisper needs file path or numpy array
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
                    speech_pad_ms=200,
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
    # Pre-load the model
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_whisper_model)

    audio_buffer = AudioBuffer(on_transcript_callback)
    logger.info("Whisper STT initialized and ready.")
    return audio_buffer


async def get_tts_stream(text: str):
    """Stream TTS audio, converting Edge TTS MP3 to raw PCM16 on the fly for instant playback."""
    import av
    
    try:
        communicate = edge_tts.Communicate(
            text,
            voice="en-US-AriaNeural",
        )

        # Buffer to feed MP3 data into PyAV
        mp3_buffer = io.BytesIO()
        
        # Setup PyAV to decode MP3 from the buffer and reformat to PCM16 at 24kHz
        container = None
        resampler = av.AudioResampler(
            format='s16',
            layout='mono',
            rate=24000,
        )

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                # Write chunk to buffer and seek back
                current_pos = mp3_buffer.tell()
                mp3_buffer.write(chunk["data"])
                mp3_buffer.seek(current_pos)
                
                # If this is the first chunk, open the container
                if container is None:
                    try:
                        container = av.open(mp3_buffer, mode='r')
                        stream = container.streams.audio[0]
                    except av.AVError:
                        continue # Wait for more data if header is incomplete

                # Decode frames from the stream
                try:
                    for frame in container.decode(stream):
                        resampled_frames = resampler.resample(frame)
                        for resampled_frame in resampled_frames:
                            yield resampled_frame.to_ndarray().tobytes()
                except (av.AVError, EOFError):
                    continue

        # Flush decoder at the end
        if container:
            try:
                for frame in container.decode(stream):
                    resampled_frames = resampler.resample(frame)
                    for resampled_frame in resampled_frames:
                        yield resampled_frame.to_ndarray().tobytes()
                container.close()
            except:
                pass

    except Exception as e:
        logger.error(f"Error in streaming TTS conversion: {e}")
