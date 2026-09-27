"""
Chinese text ingestion.

Uses `jieba` to tokenize pasted Chinese text into candidate words,
drops tokens with no Chinese characters (punctuation, numbers, Latin
text), cross-references the `words` table so the ingestion UI only
shows words not already tracked, and offers optional filters for
single characters and common function words.
"""
import re
from typing import List, Set, Tuple

import jieba

from src.database.queries import get_all_words

_CJK_RE = re.compile(r"[一-鿿]")

# Function words, pronouns, and grammatical fillers that show up in
# every article but aren't vocabulary worth drilling.
STOPWORDS = set(
    """
    的 了 在 是 和 与 及 等 也 都 而 就 还 又 但 并 或 被 把 从 向 对 为 以 于 将 其 之
    这 那 这些 那些 这个 那个 这样 那样 这里 那里 此 该 本 各 每
    我 你 他 她 它 我们 你们 他们 她们 它们 自己 大家
    有 没有 不 没 很 更 最 已 已经 会 能 可以 要 着 过 吗 呢 吧 啊 个 些
    因为 所以 如果 虽然 但是 而且 以及 并且 或者 还是 由于 因此 然后 同时 其中 之一
    一个 一些 什么 怎么 如何 哪 谁 等等
    """.split()
)


def tokenize_chinese_text(text: str) -> List[str]:
    """Segment Chinese text into candidate words using jieba.

    Keeps only tokens containing at least one Chinese character and
    de-duplicates while preserving first-seen order.
    """
    if not text:
        return []

    seen: Set[str] = set()
    ordered: List[str] = []
    for token in jieba.cut(text):
        token = token.strip()
        if not token or not _CJK_RE.search(token):
            continue
        if token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def apply_filters(words: List[str], skip_single_char: bool, skip_stopwords: bool) -> Tuple[List[str], int]:
    """Drop single-character words and/or stopwords. Returns the kept
    words and how many were hidden."""
    kept = [
        w
        for w in words
        if not (skip_single_char and len(w) == 1) and not (skip_stopwords and w in STOPWORDS)
    ]
    return kept, len(words) - len(kept)


def get_existing_word_set(language: str) -> Set[str]:
    """Return the set of words already stored for `language`."""
    return {row["word"] for row in get_all_words(language)}


def filter_new_words(language: str, candidate_words: List[str]) -> List[str]:
    """Remove candidates already present in the `words` table, so the
    ingestion UI only surfaces genuinely new vocabulary."""
    existing = get_existing_word_set(language)
    return [w for w in candidate_words if w not in existing]
