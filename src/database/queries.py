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
def count_new_cards_started(language: str, today: str) -> int:
    """How many never-seen cards were studied for the first time today."""
    row = get_db().query_one(
        """
        SELECT COUNT(*) AS c
        FROM srs_reviews
        JOIN cards ON cards.id = srs_reviews.card_id
        JOIN words ON words.id = cards.word_id
        WHERE words.language = ? AND srs_reviews.first_review_date = ?
        """,
        (language, today),
    )
    return row["c"] if row else 0


def get_due_cards(language: str, today: str, new_card_limit: int) -> List[dict]:
    """Cards for `language` due on or before `today`, joined with their
    word and SRS state.

    Every due review is included (earliest-due first), followed by at
    most `new_card_limit` never-studied cards in the order they were
    added. Each row has `is_new` (0/1).
    """
    return get_db().query(
        """
        WITH due AS (
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
                srs_reviews.next_review_date,
                srs_reviews.last_review_date
            FROM cards
            JOIN words ON words.id = cards.word_id
            JOIN srs_reviews ON srs_reviews.card_id = cards.id
            WHERE words.language = ? AND srs_reviews.next_review_date <= ?
        ),
        new_cards AS (
            SELECT * FROM due WHERE last_review_date IS NULL ORDER BY card_id LIMIT ?
        )
        SELECT *, 0 AS is_new FROM due WHERE last_review_date IS NOT NULL
        UNION ALL
        SELECT *, 1 AS is_new FROM new_cards
        ORDER BY is_new, next_review_date, card_id
        """,
        (language, today, max(0, new_card_limit)),
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
            next_review_date = ?, last_review_date = ?,
            first_review_date = COALESCE(first_review_date, ?)
        WHERE card_id = ?
        """,
        (
            srs_result["repetition_number"],
            srs_result["easiness_factor"],
            srs_result["interval_days"],
            srs_result["next_review_date"],
            today,
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


def get_study_dates(language: str) -> List[str]:
    """Every date (ISO string) with at least one review, newest first."""
    rows = get_db().query(
        """
        SELECT DISTINCT study_date FROM study_logs
        WHERE language = ? AND cards_reviewed > 0
        ORDER BY study_date DESC
        """,
        (language,),
    )
    return [row["study_date"] for row in rows]


# ---------------------------------------------------------------------------
# Settings (shared across devices, unlike session state)
# ---------------------------------------------------------------------------
def get_setting(key: str, default: str = "") -> str:
    row = get_db().query_one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    get_db().execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


def get_new_card_limit(language: str) -> int:
    """Daily new-card cap for `language` (config default if unset)."""
    try:
        return int(get_setting(f"new_cards_per_day:{language}", str(config.NEW_CARDS_PER_DAY)))
    except ValueError:
        return config.NEW_CARDS_PER_DAY


def set_new_card_limit(language: str, limit: int) -> None:
    set_setting(f"new_cards_per_day:{language}", str(int(limit)))


# ---------------------------------------------------------------------------
# Vocabulary management
# ---------------------------------------------------------------------------
def get_vocabulary(language: str) -> List[dict]:
    """Every word for `language` with its next review date, newest first."""
    return get_db().query(
        """
        SELECT words.id, words.word, words.pronunciation, words.meaning, words.domain,
               words.status, words.added_at, MIN(srs_reviews.next_review_date) AS next_review_date
        FROM words
        LEFT JOIN cards ON cards.word_id = words.id
        LEFT JOIN srs_reviews ON srs_reviews.card_id = cards.id
        WHERE words.language = ?
        GROUP BY words.id
        ORDER BY words.added_at DESC, words.id DESC
        """,
        (language,),
    )


def update_words(changes: List[dict]) -> None:
    """Apply edits (id, pronunciation, meaning, domain) in one transaction."""
    if not changes:
        return
    db = get_db()
    with db.transaction():
        for c in changes:
            db.execute(
                "UPDATE words SET pronunciation = ?, meaning = ?, domain = ? WHERE id = ?",
                ((c["pronunciation"] or "").strip(), (c["meaning"] or "").strip(), c["domain"] or "General", c["id"]),
            )


def delete_words(word_ids: List[int]) -> None:
    """Delete words along with their cards and SRS state."""
    if not word_ids:
        return
    marks = ", ".join("?" * len(word_ids))
    db = get_db()
    with db.transaction():
        db.execute(
            f"DELETE FROM srs_reviews WHERE card_id IN (SELECT id FROM cards WHERE word_id IN ({marks}))",
            word_ids,
        )
        db.execute(f"DELETE FROM cards WHERE word_id IN ({marks})", word_ids)
        db.execute(f"DELETE FROM words WHERE id IN ({marks})", word_ids)


def export_all_tables() -> Dict[str, List[dict]]:
    """Every row of every table, for a full backup download."""
    db = get_db()
    return {
        table: db.query(f"SELECT * FROM {table}")
        for table in ("words", "cards", "srs_reviews", "study_logs", "settings")
    }
