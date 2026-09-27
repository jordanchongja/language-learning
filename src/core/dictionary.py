"""
Offline lookups used to pre-fill new words.

Chinese: pinyin via `pypinyin`, English meanings via CC-CEDICT
(assets/dict/cedict_ts.u8.gz — CC BY-SA 4.0, MDBG, https://www.mdbg.net/chinese/dictionary?page=cedict).
Compounds jieba produces that CC-CEDICT doesn't list (e.g. 期货市场)
get a meaning built from their parts ("期货 futures · 市场 market").

Korean: rule-based romanization via `korean-romanizer`. It
transliterates spelling rather than sound changes, so treat it as a
starting point you can edit.

Everything here is best-effort and returns "" when it can't help.
"""
import gzip
import os
import re
from functools import lru_cache
from typing import Dict

from pypinyin import Style, lazy_pinyin

import config

CEDICT_PATH = os.path.join(config.ASSETS_DIR, "dict", "cedict_ts.u8.gz")

# `Traditional Simplified [pin1 yin1] /def 1/def 2/`
_LINE_RE = re.compile(r"^(\S+) (\S+) \[([^\]]*)\] /(.*)/\s*$")
# Definitions that rarely help a learner; dropped unless nothing else is left.
_NOISE_RE = re.compile(r"^(surname |(old )?variant of |see |CL:|used in |also pr\. |also written )", re.IGNORECASE)
# Cross-references like 期貨合約|期货合约[qi1 huo4 he2 yue1] → 期货合约
_XREF_RE = re.compile(r"(?:[^\s|\[\],;]+\|)?([^\s|\[\],;]+)\[[^\]]*\]")
# Pronunciation notes like "(Taiwan pr. [zhuo2])"
_PRON_NOTE_RE = re.compile(r"\s*\((?:Taiwan |also )?pr\. \[[^\]]*\]\)")
# Grammar particles jieba glues onto words (扮演着); their dictionary
# senses are misleading when assembling a compound's meaning.
_PARTICLES = set("着了过的地得们")
_MAX_DEFINITIONS = 3


def _xref_target(match: "re.Match") -> str:
    return match.group(1)


_MAX_PART_LEN = 8


@lru_cache(maxsize=1)
def _cedict() -> Dict[str, str]:
    """Parse CC-CEDICT once per process into {simplified: meaning}.

    Common-word readings (lowercase pinyin) are listed ahead of proper
    nouns (capitalized pinyin) when a word has several entries.
    """
    entries: Dict[str, list] = {}
    with gzip.open(CEDICT_PATH, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            m = _LINE_RE.match(line)
            if not m:
                continue
            _, simplified, pinyin, defs = m.groups()
            is_proper_noun = pinyin[:1].isupper()
            cleaned = [_XREF_RE.sub(_xref_target, _PRON_NOTE_RE.sub("", d)).strip() for d in defs.split("/")]
            entries.setdefault(simplified, []).append((is_proper_noun, cleaned))

    meanings = {}
    for word, word_entries in entries.items():
        defs = [d for _, entry_defs in sorted(word_entries, key=lambda e: e[0]) for d in entry_defs if d]
        useful = [d for d in defs if not _NOISE_RE.match(d)] or defs
        meanings[word] = "; ".join(dict.fromkeys(useful[:_MAX_DEFINITIONS]))
    return meanings


def chinese_pinyin(word: str) -> str:
    """Tone-marked pinyin, one syllable per character: 期货 → 'qī huò'."""
    return " ".join(lazy_pinyin(word, style=Style.TONE)) if word else ""


def chinese_meaning(word: str) -> str:
    """English meaning from CC-CEDICT, or one assembled from the
    longest dictionary words the term splits into. "" if unknown."""
    if not word:
        return ""
    try:
        cedict = _cedict()
    except OSError:
        return ""  # dictionary file missing
    if word in cedict:
        return cedict[word]

    # Greedy longest-match split, e.g. 期货市场 → 期货 + 市场.
    parts, i = [], 0
    while i < len(word):
        for j in range(min(len(word), i + _MAX_PART_LEN), i, -1):
            if word[i:j] in cedict:
                parts.append(word[i:j])
                i = j
                break
        else:
            return ""  # a character the dictionary doesn't know
    content = [p for p in parts if p not in _PARTICLES]
    if not content or len(parts) < 2:
        return ""
    if len(content) == 1:
        return cedict[content[0]]  # e.g. 扮演着 → meaning of 扮演
    return " · ".join(f"{p} {cedict[p].split(';')[0]}" for p in content)


def korean_romanization(word: str) -> str:
    """Revised Romanization of a Hangul word: 안녕하세요 → 'annyeonghaseyo'."""
    if not word:
        return ""
    try:
        from korean_romanizer.romanizer import Romanizer

        return Romanizer(word).romanize()
    except Exception:
        return ""
