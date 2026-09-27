"""
Database setup and connection management.

Backend is picked at startup:
- Turso (cloud libSQL) when TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are
  set (env vars or Streamlit secrets) — data survives Streamlit Cloud
  restarts and is shared between your phone and computer.
- Otherwise the local SQLite file at `data/language.db`.

Turso speaks the same SQL dialect as SQLite, so the schema and queries
are identical for both. Every round trip to Turso costs ~0.2s, so one
connection is opened per process and reused (opening one costs ~0.6s),
in autocommit mode to avoid a separate COMMIT round trip per write.
"""
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import List, Optional

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


class Result:
    """What a write returns: the affected-row count, the last inserted
    id, and any rows from a RETURNING clause (as dicts)."""

    def __init__(self, rows: List[dict], rowcount: int, lastrowid: Optional[int]):
        self.rows = rows
        self.rowcount = rowcount
        self.lastrowid = lastrowid


def _rows_as_dicts(cursor) -> List[dict]:
    # libsql has no row_factory, so build dicts from the column names
    # (keeps the `row["word"]` style working for both backends).
    if cursor.description is None:
        return []
    columns = [d[0] for d in cursor.description]
    # libsql returns None rather than [] for statements like BEGIN.
    return [dict(zip(columns, row)) for row in cursor.fetchall() or []]


class Database:
    """One shared connection, serialized with a lock because Streamlit
    runs each browser session's script on its own thread."""

    def __init__(self):
        self.url = config.get_secret("TURSO_DATABASE_URL")
        self.token = config.get_secret("TURSO_AUTH_TOKEN")
        self.is_remote = bool(self.url and self.token)
        self._conn = None
        self._lock = threading.RLock()
        self._in_transaction = False

    def _connect(self):
        if self.is_remote:
            import libsql

            return libsql.connect(self.url, auth_token=self.token, isolation_level=None)

        os.makedirs(config.DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(config.DB_PATH, check_same_thread=False, isolation_level=None)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _run(self, fn):
        """Run `fn(conn)`, reconnecting and retrying once if the
        connection has gone stale (e.g. Turso dropped an idle stream)."""
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            try:
                return fn(self._conn)
            except Exception:
                # A fresh connection would silently fall outside any
                # open transaction, so only retry standalone statements.
                if not self.is_remote or self._in_transaction:
                    raise
                self._conn = self._connect()
                return fn(self._conn)

    def query(self, sql: str, params=()) -> List[dict]:
        return self._run(lambda c: _rows_as_dicts(c.execute(sql, params)))

    def query_one(self, sql: str, params=()) -> Optional[dict]:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params=()) -> Result:
        def fn(c):
            cursor = c.execute(sql, params)
            rows = _rows_as_dicts(cursor)
            return Result(rows, cursor.rowcount, cursor.lastrowid)

        return self._run(fn)

    def executescript(self, script: str) -> None:
        self._run(lambda c: c.executescript(script))

    @contextmanager
    def transaction(self):
        """Group several writes so they all land or none do. Holds the
        lock throughout so no other session interleaves statements."""
        with self._lock:
            self.execute("BEGIN")
            self._in_transaction = True
            try:
                yield self
                self.execute("COMMIT")
            except Exception:
                try:
                    self.execute("ROLLBACK")
                except Exception:
                    pass  # connection is gone; the server discards the transaction
                raise
            finally:
                self._in_transaction = False


_db: Optional[Database] = None
_db_lock = threading.Lock()
_initialized = False


def get_db() -> Database:
    """Return the process-wide Database, creating it on first use."""
    global _db
    with _db_lock:
        if _db is None:
            _db = Database()
        return _db


def initialize_database() -> None:
    """Create all four tables if they don't already exist. Runs once
    per process — Streamlit calls this on every rerun, and re-running
    the schema against Turso would cost a round trip each time."""
    global _initialized
    if _initialized:
        return
    get_db().executescript(SCHEMA)
    _initialized = True


if __name__ == "__main__":
    # Manual setup: python -m src.database.db_setup (from the project root)
    initialize_database()
    db = get_db()
    print("Database initialized:", "Turso" if db.is_remote else config.DB_PATH)
