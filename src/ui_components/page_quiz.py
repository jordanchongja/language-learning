"""
SRS quiz/review session UI.

Loads every due review plus up to the daily limit of new cards for the
active language, shows the cloze/basic front, reveals the answer +
pronunciation audio on request, and grades the card via SM-2
(Again/Hard/Good/Easy). Each grade is saved immediately, so the
dashboard counts reviews even if you stop halfway.
"""
import time

import streamlit as st

from src.core.srs_engine import grade_review
from src.database.queries import (
    count_new_cards_started,
    get_due_cards,
    get_new_card_limit,
    record_review,
    set_new_card_limit,
)
from src.utils.audio_gen import generate_audio
from src.utils.time_utils import local_today

# Cap on seconds counted for one card, so leaving the app open on a
# card doesn't inflate the dashboard's study time.
_MAX_SECONDS_PER_CARD = 300


def _load_queue(language: str):
    today = local_today().isoformat()
    limit = get_new_card_limit(language)
    remaining_new = max(0, limit - count_new_cards_started(language, today))
    st.session_state["quiz_language"] = language
    st.session_state["quiz_queue"] = get_due_cards(language, today, remaining_new)
    st.session_state["quiz_new_limit"] = limit
    st.session_state["quiz_index"] = 0
    st.session_state["quiz_show_answer"] = False
    st.session_state["quiz_play_sentence"] = False
    st.session_state["quiz_reviewed"] = 0
    st.session_state["quiz_card_started_at"] = time.time()


def _grade(card: dict, label: str):
    today = local_today()
    result = grade_review(
        card["easiness_factor"], card["interval_days"], card["repetition_number"], label, today
    )
    elapsed = int(time.time() - st.session_state["quiz_card_started_at"])
    record_review(
        card,
        result,
        correct=(label != "Again"),
        duration_seconds=min(elapsed, _MAX_SECONDS_PER_CARD),
        today=today.isoformat(),
    )

    if label == "Again":
        # Show it again at the end of this session, carrying its reset
        # SRS state so the next grade builds on it.
        st.session_state["quiz_queue"].append({**card, **result, "is_new": 0})

    st.session_state["quiz_reviewed"] += 1
    st.session_state["quiz_index"] += 1
    st.session_state["quiz_show_answer"] = False
    st.session_state["quiz_play_sentence"] = False
    st.session_state["quiz_card_started_at"] = time.time()


def _render_limit_setting(language: str):
    with st.expander("⚙️ New cards per day"):
        new_limit = st.number_input(
            "Maximum never-seen cards to introduce per day",
            min_value=0,
            max_value=500,
            value=st.session_state["quiz_new_limit"],
            step=5,
            key=f"new_limit_input_{language}",
        )
        if new_limit != st.session_state["quiz_new_limit"]:
            set_new_card_limit(language, new_limit)
            _load_queue(language)
            st.rerun()


def render(language: str):
    st.subheader("📚 Study Session")

    # (Re)load the due-card queue on first visit, when the language
    # changes, or when app.py clears quiz_language on navigating here.
    if st.session_state.get("quiz_language") != language:
        _load_queue(language)

    queue = st.session_state["quiz_queue"]
    index = st.session_state["quiz_index"]

    if index >= len(queue):
        reviewed = st.session_state.get("quiz_reviewed", 0)
        if reviewed:
            st.success(f"Session complete — {reviewed} review(s) done. 🎉")
        else:
            st.info("Nothing due right now. Add some words or check back tomorrow!")
        if st.button("🔄 Check for due cards again"):
            _load_queue(language)
            st.rerun()
        _render_limit_setting(language)
        return

    card = queue[index]
    remaining = queue[index:]
    new_left = sum(1 for c in remaining if c["is_new"])
    st.caption(
        f"Card {index + 1} of {len(queue)} · {len(remaining) - new_left} review(s) + {new_left} new left"
    )

    if card["is_new"]:
        st.markdown("🆕 **New card**")
    st.markdown(f"## {card['cloze_text'] or card['word']}")

    if not st.session_state["quiz_show_answer"]:
        if st.button("Show Answer", type="primary", width="stretch"):
            st.session_state["quiz_show_answer"] = True
            st.rerun()
        _render_limit_setting(language)
        return

    st.markdown(f"### {card['word']}")
    if card["pronunciation"]:
        st.caption(card["pronunciation"])
    # Word meaning first (it reflects edits made on the Vocabulary page).
    meaning = card["meaning"] or card["translation"]
    if meaning:
        st.markdown(f"**Meaning:** {meaning}")

    word_audio = generate_audio(card["word"], card["language"])
    if word_audio:
        st.audio(word_audio)
    else:
        st.caption("🔇 Audio unavailable (gTTS needs an internet connection).")

    has_sentence = card["sentence_text"] and card["sentence_text"] != card["word"]
    if has_sentence:
        st.markdown(f"**Sentence:** {card['sentence_text']}")
        if st.session_state["quiz_play_sentence"]:
            sentence_audio = generate_audio(card["sentence_text"], card["language"])
            if sentence_audio:
                st.audio(sentence_audio)
        elif st.button("🔊 Sentence audio"):
            st.session_state["quiz_play_sentence"] = True
            st.rerun()

    st.write("How well did you know this?")
    cols = st.columns(4)
    for col, label in zip(cols, ("Again", "Hard", "Good", "Easy")):
        if col.button(label, key=f"grade_{label}_{index}", width="stretch"):
            _grade(card, label)
            st.rerun()
    st.caption("Again = forgot (see it again today) · Hard/Good/Easy = remembered, with growing gaps")
