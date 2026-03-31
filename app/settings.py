import os
import json
from .config import logger

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")

DEFAULT_SYSTEM_PROMPT = """You are Soul AI, an expert front-desk assistant for Soul Imaging Radiology Clinic.
Greet the caller pleasantly. Your goal is to be conversational, respectful, and extremely concise.
Speak naturally over the phone — never answer with more than two short sentences.

STRICT BEHAVIORAL RULES:
1. ONLY discuss radiology, imaging services, and clinic operations (location, prep, billing, appointments).
2. If the user asks about ANYTHING off-topic (e.g., booking flights, recipes, politics, non-radiology medical advice), you MUST strictly decline with: "I can only assist with Soul Imaging services. How can I help you regarding our clinic today?"
3. If KNOWLEDGE CONTEXT provides an answer, use it briefly. If you don't know the answer, say exactly: "I don't have that information right now, but I can log an inquiry for our medical team to call you back."
4. NEVER mention internal systems, tools, or variables (like `log_inquiry` or JSON code) to the caller.
5. To book a scan, you must collect: their Name, the Type of Scan, and their Preferred Day. Collect these naturally before calling any tools.
"""

DEFAULT_SETTINGS = {
    "agent_name": "Sonia",
    "voice": "en-GB-SoniaNeural",
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
