"""
Data access for the full schema: words, cards, srs_reviews, and
study_logs. Every module in the app goes through this file rather than
touching the database directly.

Dates are always passed in from Python (see `time_utils.local_today`)
instead of using SQLite's `date('now')`, which is UTC.
"""
from typing import Dict, List, Optional, Tuple

import config
from src.database.db_setup import get_db

# Rows per multi-row INSERT — keeps each statement well under SQLite's
# bound-parameter limit.
_CHUNK = 200


def _chunks(items: list, size: int = _CHUNK):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _placeholders(n_rows: int, n_cols: int) -> str:
    row = "(" + ", ".join("?" * n_cols) + ")"
    return ", ".join([row] * n_rows)


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------
def add_word(
    language: str,
    word: str,
    pronunciation: str = "",
    meaning: str = "",
    domain: str = "General",
) -> Optional[int]:
    """Insert a single word. Returns its new id, or None if it already
    exists for this language or `language`/`word` is empty."""
    word = (word or "").strip()
    if not language or not word:
        return None

    result = get_db().execute(
        """
        INSERT OR IGNORE INTO words (language, word, pronunciation, meaning, domain)
        VALUES (?, ?, ?, ?, ?)
        RETURNING id
        """,
        (language, word, (pronunciation or "").strip(), (meaning or "").strip(), domain or "General"),
    )
    return result.rows[0]["id"] if result.rows else None


def get_all_words(language: str) -> List[dict]:
    """Return every word row for the given language, newest first."""
    return get_db().query(
        "SELECT * FROM words WHERE language = ? ORDER BY added_at DESC",
        (language,),
    )


def mark_word_known(word_id: int) -> bool:
    """Set a word's status to 'Known'. Returns True if a row was updated."""
    result = get_db().execute("UPDATE words SET status = 'Known' WHERE id = ?", (word_id,))
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# Ingestion: words + cards + initial SRS state, in bulk
# ---------------------------------------------------------------------------
def save_words_with_cards(language: str, items: List[dict], today: str) -> Tuple[int, int]:
    """Save new words, one card per word, and each card's initial SRS
    state (due `today`), all in one transaction.

    Each item needs: word, pronunciation, meaning, domain,
    sentence_text, cloze_text, source_article.

    Uses multi-row INSERTs so a 50-word article is 3 round trips to
    Turso, not 150. Returns (added, skipped_as_duplicates).
    """
    # Drop blanks and repeats within the batch itself.
    unique: Dict[str, dict] = {}
    for item in items:
        word = (item.get("word") or "").strip()
        if word and word not in unique:
            unique[word] = {**item, "word": word}
    if not unique:
        return 0, 0

    db = get_db()
    with db.transaction():
        word_ids: Dict[str, int] = {}
        for chunk in _chunks(list(unique.values())):
            params = []
            for it in chunk:
                params += [
                    language,
                    it["word"],
                    (it.get("pronunciation") or "").strip(),
                    (it.get("meaning") or "").strip(),
                    it.get("domain") or "General",
                ]
            # OR IGNORE skips words already in the DB; RETURNING only
            # yields the rows actually inserted.
            result = db.execute(
                f"""
                INSERT OR IGNORE INTO words (language, word, pronunciation, meaning, domain)
                VALUES {_placeholders(len(chunk), 5)}
                RETURNING id, word
                """,
                params,
            )
            word_ids.update({row["word"]: row["id"] for row in result.rows})

        added = [unique[w] for w in unique if w in word_ids]
        card_ids: List[int] = []
        for chunk in _chunks(added):
            params = []
            for it in chunk:
                params += [
                    word_ids[it["word"]],
                    it["sentence_text"],
                    it["cloze_text"],
                    (it.get("meaning") or "").strip(),
                    it.get("source_article") or "",
                ]
            result = db.execute(
                f"""
                INSERT INTO cards (word_id, sentence_text, cloze_text, translation, source_article)
                VALUES {_placeholders(len(chunk), 5)}
                RETURNING id
                """,
                params,
            )
            card_ids += [row["id"] for row in result.rows]

        for chunk in _chunks(card_ids):
            params = []
            for card_id in chunk:
                params += [card_id, today]
            db.execute(
                f"INSERT OR IGNORE INTO srs_reviews (card_id, next_review_date) VALUES {_placeholders(len(chunk), 2)}",
                params,
            )

    return len(added), len(unique) - len(added)


# ---------------------------------------------------------------------------
# Study: due cards and grading
# ---------------------------------------------------------------------------
def get_due_cards(language: str, today: str) -> List[dict]:
    """Every card for `language` due on or before `today`, joined with
    its word and SRS state, earliest-due first."""
    return get_db().query(
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
        WHERE words.language = ? AND srs_reviews.next_review_date <= ?
        ORDER BY srs_reviews.next_review_date, cards.id
        """,
        (language, today),
    )


def record_review(
    card: dict,
    srs_result: dict,
    correct: bool,
    duration_seconds: int,
    today: str,
) -> None:
    """Persist one graded review:
    - the card's new SM-2 state,
    - the word's status ('Known' once the interval reaches
      config.KNOWN_INTERVAL_DAYS, otherwise 'Learning'),
    - today's study_logs row for the language (created on the first
      review of the day, incremented after that).

    Logging per review (not per finished session) means a half-finished
    session still shows up on the dashboard.
    """
    db = get_db()
    db.execute(
        """
        UPDATE srs_reviews
        SET repetition_number = ?, easiness_factor = ?, interval_days = ?,
            next_review_date = ?, last_review_date = ?
        WHERE card_id = ?
        """,
        (
            srs_result["repetition_number"],
            srs_result["easiness_factor"],
            srs_result["interval_days"],
            srs_result["next_review_date"],
            today,
            card["card_id"],
        ),
    )

    status = "Known" if srs_result["interval_days"] >= config.KNOWN_INTERVAL_DAYS else "Learning"
    db.execute("UPDATE words SET status = ? WHERE id = ?", (status, card["word_id"]))

    correct_inc = 1 if correct else 0
    updated = db.execute(
        """
        UPDATE study_logs
        SET cards_reviewed = cards_reviewed + 1,
            correct_count = correct_count + ?,
            session_duration_seconds = session_duration_seconds + ?
        WHERE language = ? AND study_date = ?
        """,
        (correct_inc, duration_seconds, card["language"], today),
    )
    if updated.rowcount == 0:
        db.execute(
            """
            INSERT INTO study_logs (language, study_date, cards_reviewed, correct_count, session_duration_seconds)
            VALUES (?, ?, 1, ?, ?)
            """,
            (card["language"], today, correct_inc, duration_seconds),
        )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
def get_daily_review_counts(language: str, since: str) -> List[dict]:
    """Total cards reviewed per day for `language` from `since` onward."""
    return get_db().query(
        """
        SELECT study_date, SUM(cards_reviewed) AS cards_reviewed
        FROM study_logs
        WHERE language = ? AND study_date >= ?
        GROUP BY study_date
        ORDER BY study_date
        """,
        (language, since),
    )


def get_word_counts_by_domain(language: str) -> List[dict]:
    """Word count per domain for `language`, largest domain first."""
    return get_db().query(
        """
        SELECT domain, COUNT(*) AS word_count
        FROM words
        WHERE language = ?
        GROUP BY domain
        ORDER BY word_count DESC
        """,
        (language,),
    )


def get_known_word_count(language: str) -> int:
    """Total words marked 'Known' for `language`."""
    row = get_db().query_one(
        "SELECT COUNT(*) AS c FROM words WHERE language = ? AND status = 'Known'",
        (language,),
    )
    return row["c"] if row else 0
