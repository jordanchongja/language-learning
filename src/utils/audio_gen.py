"""
Pronunciation audio generation via gTTS.

gTTS needs internet access, so every call here is best-effort: on any
failure (offline, blocked, gTTS error) we return None instead of
raising, and callers (the quiz UI) simply skip audio playback rather
than crash the session.

Files are named deterministically from the card id
(`assets/audio/<card_id>.mp3`) so callers can check for an existing
file with `audio_path_for_card()` before generating it.
"""
import os
from typing import Optional

from gtts import gTTS

import config

_LANG_CODES = {
    "Chinese": "zh-CN",
    "Korean": "ko",
}


def audio_path_for_card(card_id: int) -> str:
    """Path where `card_id`'s pronunciation audio is/would be stored."""
    return os.path.join(config.AUDIO_DIR, f"{card_id}.mp3")


def generate_audio(card_id: int, text: str, language: str) -> Optional[str]:
    """Generate and save pronunciation audio for `text` in `language`.

    Returns the saved file path on success, or None if generation
    failed or `language` isn't supported for TTS — the caller should
    treat audio as optional either way.
    """
    text = (text or "").strip()
    lang_code = _LANG_CODES.get(language)
    if not text or not lang_code:
        return None

    os.makedirs(config.AUDIO_DIR, exist_ok=True)
    path = audio_path_for_card(card_id)
    try:
        gTTS(text=text, lang=lang_code).save(path)
        return path
    except Exception:
        return None
