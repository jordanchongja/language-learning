"""
SRS quiz/review session UI.

Loads every due card for the active language, shows the cloze/basic
front, reveals the answer + pronunciation audio on request, and grades
the card via SM-2 (Again/Hard/Good/Easy). Each grade is saved
immediately, so the dashboard counts reviews even if you stop halfway.
"""
import os
import time

import streamlit as st

from src.core.srs_engine import grade_review
from src.database.queries import get_due_cards, record_review
from src.utils.audio_gen import audio_path_for_card, generate_audio
from src.utils.time_utils import local_today

# Cap on seconds counted for one card, so leaving the app open on a
# card doesn't inflate the dashboard's study time.
_MAX_SECONDS_PER_CARD = 300


def _load_queue(language: str):
    st.session_state["quiz_language"] = language
    st.session_state["quiz_queue"] = get_due_cards(language, local_today().isoformat())
    st.session_state["quiz_index"] = 0
    st.session_state["quiz_show_answer"] = False
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
        st.session_state["quiz_queue"].append({**card, **result})

    st.session_state["quiz_reviewed"] += 1
    st.session_state["quiz_index"] += 1
    st.session_state["quiz_show_answer"] = False
    st.session_state["quiz_card_started_at"] = time.time()


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
            st.success(f"Session complete — {reviewed} review(s) done.")
        else:
            st.info("No cards are due for review right now. Add some vocabulary or check back later!")
        if st.button("🔄 Check for due cards again"):
            _load_queue(language)
            st.rerun()
        return

    card = queue[index]
    st.caption(f"Card {index + 1} of {len(queue)}")

    front = card["cloze_text"] or card["word"]
    st.markdown(f"## {front}")

    if not st.session_state["quiz_show_answer"]:
        if st.button("Show Answer", type="primary", width="stretch"):
            st.session_state["quiz_show_answer"] = True
            st.rerun()
        return

    st.markdown(f"**Word:** {card['word']}")
    if card["pronunciation"]:
        st.caption(card["pronunciation"])
    if card["sentence_text"] and card["sentence_text"] != card["word"]:
        st.markdown(f"**Original sentence:** {card['sentence_text']}")
    meaning = card["translation"] or card["meaning"]
    if meaning:
        st.markdown(f"**Meaning:** {meaning}")

    audio_path = audio_path_for_card(card["card_id"])
    if not os.path.exists(audio_path):
        audio_path = generate_audio(card["card_id"], card["word"], card["language"]) or audio_path
    if os.path.exists(audio_path):
        st.audio(audio_path)
    else:
        st.caption("🔇 Pronunciation audio unavailable (needs an internet connection for gTTS).")

    st.write("How well did you know this?")
    cols = st.columns(4)
    for col, label in zip(cols, ("Again", "Hard", "Good", "Easy")):
        if col.button(label, key=f"grade_{label}_{index}", width="stretch"):
            _grade(card, label)
            st.rerun()
