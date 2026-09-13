"""
Card content generation.

Chinese: splits the pasted source article into sentences (accounting
for full-width punctuation), locates a sentence containing the target
word, and blanks the word out to build a cloze card.

Korean: no source article context — words map straight to a basic
front/back card.
"""
import re
from typing import List, Optional

# Sentence terminators: full-width Chinese (。！？) and half-width
# (.!?), kept out of the resulting sentences.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？.!?])\s*")


def split_into_sentences(text: str) -> List[str]:
    """Split article text into sentences on full/half-width
    terminators, dropping empty fragments."""
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def find_context_sentence(word: str, sentences: List[str]) -> Optional[str]:
    """Return the first sentence containing `word`, or None if none do."""
    for sentence in sentences:
        if word in sentence:
            return sentence
    return None


def make_cloze(word: str, sentence: str) -> str:
    """Replace every occurrence of `word` in `sentence` with a blank."""
    return sentence.replace(word, "___")


def build_chinese_card(word: str, source_text: str) -> dict:
    """Build `sentence_text`/`cloze_text` for a Chinese word from its
    source article. Falls back to a word-only card if no sentence in
    the source contains the word (e.g. manual entry with no article).
    """
    context = find_context_sentence(word, split_into_sentences(source_text))
    if context:
        return {"sentence_text": context, "cloze_text": make_cloze(word, context)}
    return {"sentence_text": word, "cloze_text": "___"}


def build_korean_card(word: str, meaning: str) -> dict:
    """Basic front/back card for Korean — the front is just the word,
    there is no context sentence to blank out."""
    return {"sentence_text": word, "cloze_text": word}
