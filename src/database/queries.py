"""
CRUD wrapper functions for the full schema: words, cards,
srs_reviews, and study_logs. Every module in the app (ingestion,
quiz, dashboard) goes through this file rather than touching SQLite
directly.
"""
import sqlite3
from typing import List, Optional

from src.database.db_setup import get_connection


def add_word(
    language: str,
    word: str,
    pronunciation: str = "",
    meaning: str = "",
    domain: str = "General",
) -> Optional[int]:
    """Insert a new word for the given language.

    Returns the new row's id, or None if the word already exists for
    that language (the `UNIQUE(language, word)` constraint silently
    ignores the insert) or `language`/`word` is empty.
    """
    word = (word or "").strip()
    if not language or not word:
        return None

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO words (language, word, pronunciation, meaning, domain)
            VALUES (?, ?, ?, ?, ?)
            """,
            (language, word, (pronunciation or "").strip(), (meaning or "").strip(), domain or "General"),
        )
        conn.commit()
        if cursor.rowcount == 0:
            return None  # duplicate for this language, insert was ignored
        return cursor.lastrowid
    finally:
        conn.close()


def get_all_words(language: str) -> List[sqlite3.Row]:
    """Return every word row for the given language, newest first."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT * FROM words WHERE language = ? ORDER BY added_at DESC",
            (language,),
        ).fetchall()
    finally:
        conn.close()


def mark_word_known(word_id: int) -> bool:
    """Set a word's status to 'Known'. Returns True if a row was updated."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE words SET status = 'Known' WHERE id = ?", (word_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# cards (Phase 3: cloze/basic card generation)
# ---------------------------------------------------------------------------
def add_card(
    word_id: int,
    sentence_text: str,
    cloze_text: str,
    translation: str = "",
    source_article: str = "",
) -> int:
    """Insert a card (cloze sentence for Chinese, basic front/back for
    Korean) for `word_id`. Returns the new card's id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO cards (word_id, sentence_text, cloze_text, translation, source_article)
            VALUES (?, ?, ?, ?, ?)
            """,
            (word_id, sentence_text, cloze_text, translation, source_article),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# srs_reviews (Phase 3 init, Phase 4 grading)
# ---------------------------------------------------------------------------
def init_srs_review(card_id: int) -> None:
    """Create the default SM-2 state row for a newly created card."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO srs_reviews (card_id) VALUES (?)",
            (card_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_due_cards(language: str) -> List[sqlite3.Row]:
    """Return every card for `language` whose next_review_date has
    arrived, joined with its word and SRS state, earliest-due first."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT
                cards.id AS card_id,
                cards.word_id,
                cards.sentence_text,
                cards.cloze_text,
                cards.translation,
                words.word,
                words.pronunciation,
                words.meaning,
                words.language,
                srs_reviews.repetition_number,
                srs_reviews.easiness_factor,
                srs_reviews.interval_days,
                srs_reviews.next_review_date
            FROM cards
            JOIN words ON words.id = cards.word_id
            JOIN srs_reviews ON srs_reviews.card_id = cards.id
            WHERE words.language = ? AND srs_reviews.next_review_date <= date('now')
            ORDER BY srs_reviews.next_review_date
            """,
            (language,),
        ).fetchall()
    finally:
        conn.close()


def update_srs_review(
    card_id: int,
    repetition_number: int,
    easiness_factor: float,
    interval_days: int,
    next_review_date: str,
) -> None:
    """Persist the SM-2 state computed by `srs_engine.grade_review()`."""
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE srs_reviews
            SET repetition_number = ?,
                easiness_factor = ?,
                interval_days = ?,
                next_review_date = ?,
                last_review_date = date('now')
            WHERE card_id = ?
            """,
            (repetition_number, easiness_factor, interval_days, next_review_date, card_id),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# study_logs (Phase 5: analytics)
# ---------------------------------------------------------------------------
def log_study_session(
    language: str, cards_reviewed: int, correct_count: int, session_duration_seconds: int = 0
) -> None:
    """Record one completed quiz session for the dashboard."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO study_logs (language, cards_reviewed, correct_count, session_duration_seconds)
            VALUES (?, ?, ?, ?)
            """,
            (language, cards_reviewed, correct_count, session_duration_seconds),
        )
        conn.commit()
    finally:
        conn.close()


def get_daily_review_counts(language: str, days: int = 30) -> List[sqlite3.Row]:
    """Total cards reviewed per day for `language` over the last `days` days."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT study_date, SUM(cards_reviewed) AS cards_reviewed
            FROM study_logs
            WHERE language = ? AND study_date >= date('now', ?)
            GROUP BY study_date
            ORDER BY study_date
            """,
            (language, f"-{days} days"),
        ).fetchall()
    finally:
        conn.close()


def get_word_counts_by_domain(language: str) -> List[sqlite3.Row]:
    """Word count per domain for `language`, largest domain first."""
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT domain, COUNT(*) AS word_count
            FROM words
            WHERE language = ?
            GROUP BY domain
            ORDER BY word_count DESC
            """,
            (language,),
        ).fetchall()
    finally:
        conn.close()


def get_known_word_count(language: str) -> int:
    """Total words marked 'Known' for `language`."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM words WHERE language = ? AND status = 'Known'",
            (language,),
        ).fetchone()
        return row["c"] if row else 0
    finally:
        conn.close()
