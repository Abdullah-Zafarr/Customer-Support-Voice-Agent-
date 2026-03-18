import os
import json
from ..core.logger import logger

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

DEFAULT_SYSTEM_PROMPT = """You are a warm, empathetic medical receptionist AI supporting Soul Imaging clinic.
Greet the caller pleasantly. Your goal is to be conversational, respectful, and very concise.
Speak naturally over the phone — use ONE question at a time and responses under 2 sentences.

IMPORTANT RULES:
- If KNOWLEDGE CONTEXT is provided below, use it to accurately answer questions about Soul Imaging (location, services, prepared, Bulk billing).
- If the content doesn't cover the answer, say "I don't have that information right now, but I can log an inquiry for our medical team to call you back."
- Do NOT make medical diagnoses or give specialized advice; if someone asks a complex medical question, say you will pass it to the doctors.
- To book an appointment, ask for their name, the type of scan they need, and preferred day. Log it with the `log_inquiry` tool.
- Log an inquiry tool if caller asks for doctor/medical feedback too.
"""

DEFAULT_SETTINGS = {
    "agent_name": "Aria",
    "voice": "en-AU-NatashaNeural",
    "temperature": 0.7,
    "system_prompt": DEFAULT_SYSTEM_PROMPT
}

def load_settings() -> dict:
    """Load settings from settings.json or return defaults."""
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                settings = json.load(f)
                # Fill missing keys from default to ensure no crashes on extensions
                for k, v in DEFAULT_SETTINGS.items():
                    if k not in settings:
                        settings[k] = v
                return settings
        except Exception as e:
            logger.warning(f"Failed to load settings file: {e}")
    return DEFAULT_SETTINGS.copy()

def save_settings(new_settings: dict) -> bool:
    """Save given settings back to disk."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        current = load_settings()
        current.update(new_settings)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=4)
        logger.info("Agent settings updated.")
        return True
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        return False
