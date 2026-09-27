"""
Global constants for the Language Learning Studio app.

Centralizes filesystem paths and the language/domain vocabulary so
every module (db_setup, queries, UI pages) references the same
values instead of hardcoding strings.
"""
import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "language.db")

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")

# ---------------------------------------------------------------------------
# Languages
# ---------------------------------------------------------------------------
# Maps the sidebar display label -> the value stored in the `language`
# column of the `words` table (and used to filter every query).
LANGUAGES = {
    "Business Chinese": "Chinese",
    "Beginner Korean": "Korean",
}

# ---------------------------------------------------------------------------
# Domains (used to populate the "Domain" selector during ingestion)
# ---------------------------------------------------------------------------
DEFAULT_DOMAINS = {
    "Chinese": ["General", "Dairy Futures", "Supply Chain", "Business"],
    "Korean": ["General", "Korean Basics"],
}

# ---------------------------------------------------------------------------
# Word lifecycle
# ---------------------------------------------------------------------------
WORD_STATUSES = ["New", "Learning", "Known"]

# A word becomes 'Known' once its card's SRS interval reaches this many
# days (i.e. you've recalled it successfully several times in a row).
KNOWN_INTERVAL_DAYS = 21

# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------
# "Today" for due dates and study logs is computed in this UTC offset,
# so the day rolls over at local midnight rather than UTC midnight
# (Streamlit Cloud servers run on UTC).
UTC_OFFSET_HOURS = 8


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------
def get_secret(name: str) -> str:
    """Look up a secret from the environment, then Streamlit secrets
    (`.streamlit/secrets.toml` locally, the Secrets panel on Streamlit
    Cloud). Returns "" if it isn't set anywhere."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get(name, "") or "")
    except Exception:
        # No secrets.toml at all — Streamlit raises rather than
        # returning empty.
        return ""
