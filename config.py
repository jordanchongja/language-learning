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
