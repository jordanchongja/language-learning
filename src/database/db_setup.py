"""
Database setup.

Creates the SQLite database file (if missing) and the four core
tables defined in the implementation plan's schema: words, cards,
srs_reviews, study_logs. `initialize_database()` is safe to call on
every app startup — it only creates tables that don't already exist.
"""
import os
import sqlite3

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT NOT NULL,        -- 'Chinese' or 'Korean'
    word TEXT NOT NULL,
    pronunciation TEXT,            -- Pinyin for Chinese, Romanization for Korean
    meaning TEXT,
    domain TEXT DEFAULT 'General',
    status TEXT DEFAULT 'New',     -- 'New', 'Learning', 'Known'
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(language, word)
);

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER,
    sentence_text TEXT NOT NULL,
    cloze_text TEXT NOT NULL,
    translation TEXT,
    source_article TEXT,
    FOREIGN KEY (word_id) REFERENCES words(id)
);

CREATE TABLE IF NOT EXISTS srs_reviews (
    card_id INTEGER PRIMARY KEY,
    repetition_number INTEGER DEFAULT 0,
    easiness_factor REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 0,
    next_review_date DATE DEFAULT CURRENT_DATE,
    last_review_date DATE,
    FOREIGN KEY (card_id) REFERENCES cards(id)
);

CREATE TABLE IF NOT EXISTS study_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT NOT NULL,
    study_date DATE DEFAULT CURRENT_DATE,
    cards_reviewed INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    session_duration_seconds INTEGER DEFAULT 0
);
"""


def get_connection() -> sqlite3.Connection:
    """Open a connection to the app database.

    Ensures the `data/` directory exists, enforces foreign keys, and
    returns rows as `sqlite3.Row` so callers can access columns by
    name (e.g. `row["word"]`).
    """
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database() -> None:
    """Create all four tables if they don't already exist."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    # Allows manual setup via: python -m src.database.db_setup
    # (run as a module from the project root so `import config` resolves)
    initialize_database()
    print(f"Database initialized at: {config.DB_PATH}")
