"""
Chinese text ingestion.

Uses `jieba` to tokenize pasted Chinese text into candidate words,
drops pure punctuation/whitespace tokens, and cross-references the
`words` table so the ingestion UI only shows words not already
tracked for that language.
"""
import re
from typing import List, Set

import jieba

from src.database.queries import get_all_words

# Any token containing at least one letter/digit/CJK character is a
# real candidate word; pure punctuation or whitespace tokens are
# dropped. `\w` on a Python 3 str pattern already matches Unicode
# word characters, including CJK ideographs.
_WORDY_CHAR_RE = re.compile(r"\w", re.UNICODE)


def tokenize_chinese_text(text: str) -> List[str]:
    """Segment Chinese text into candidate words using jieba.

    Drops punctuation/whitespace-only tokens and de-duplicates while
    preserving first-seen order.
    """
    if not text:
        return []

    seen: Set[str] = set()
    ordered: List[str] = []
    for token in jieba.cut(text):
        token = token.strip()
        if not token or not _WORDY_CHAR_RE.search(token):
            continue
        if token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def get_existing_word_set(language: str) -> Set[str]:
    """Return the set of words already stored for `language`."""
    return {row["word"] for row in get_all_words(language)}


def filter_new_words(language: str, candidate_words: List[str]) -> List[str]:
    """Remove candidates already present in the `words` table, so the
    ingestion UI only surfaces genuinely new vocabulary."""
    existing = get_existing_word_set(language)
    return [w for w in candidate_words if w not in existing]
