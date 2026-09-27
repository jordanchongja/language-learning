"""
Pronunciation audio generation via gTTS.

gTTS needs internet access, so every call here is best-effort: on any
failure (offline, blocked, gTTS error) we return None instead of
raising, and callers (the quiz UI) simply skip audio playback rather
than crash the session.

Files are cached in `assets/audio/`, named by a hash of the language
and text, so a word or sentence is only fetched once per server. On
Streamlit Cloud the cache is wiped on restart and simply refills.
"""
import hashlib
import os
from typing import Optional

from gtts import gTTS

import config

_LANG_CODES = {
    "Chinese": "zh-CN",
    "Korean": "ko",
}


def audio_path(text: str, language: str) -> str:
    """Path where the audio for `text` is/would be cached."""
    digest = hashlib.sha1(f"{language}:{text}".encode("utf-8")).hexdigest()[:16]
    return os.path.join(config.AUDIO_DIR, f"{digest}.mp3")


def generate_audio(text: str, language: str) -> Optional[str]:
    """Return a path to pronunciation audio for `text`, generating it
    on first use. None if generation failed or `language` isn't
    supported — callers should treat audio as optional."""
    text = (text or "").strip()
    lang_code = _LANG_CODES.get(language)
    if not text or not lang_code:
        return None

    path = audio_path(text, language)
    if os.path.exists(path):
        return path

    os.makedirs(config.AUDIO_DIR, exist_ok=True)
    try:
        gTTS(text=text, lang=lang_code).save(path)
        return path
    except Exception:
        if os.path.exists(path):
            os.remove(path)  # don't leave a partial file that looks cached
        return None
