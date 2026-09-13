"""
SRS quiz/review session UI.

Loads every due card for the active language, shows the cloze/basic
front, reveals the answer + pronunciation audio on request, and
grades the card via SM-2 (Hard/Good/Easy) to schedule its next
review. Logs the finished session to `study_logs` for the dashboard.
"""
import os
import time

import streamlit as st

from src.core.srs_engine import grade_review
from src.database.queries import get_due_cards, log_study_session, update_srs_review
from src.utils.audio_gen import audio_path_for_card, generate_audio


def _load_queue(language: str):
    st.session_state["quiz_language"] = language
    st.session_state["quiz_queue"] = list(get_due_cards(language))
    st.session_state["quiz_index"] = 0
    st.session_state["quiz_show_answer"] = False
    st.session_state["quiz_reviewed"] = 0
    st.session_state["quiz_correct"] = 0
    st.session_state["quiz_started_at"] = time.time()
    st.session_state["quiz_logged"] = False


def _log_if_needed(language: str):
    """Log the session exactly once, the first time the queue empties."""
    if st.session_state.get("quiz_logged"):
        return
    reviewed = st.session_state.get("quiz_reviewed", 0)
    if reviewed == 0:
        return
    duration = int(time.time() - st.session_state.get("quiz_started_at", time.time()))
    log_study_session(language, reviewed, st.session_state.get("quiz_correct", 0), duration)
    st.session_state["quiz_logged"] = True


def render(language: str):
    st.subheader("📚 Study Session")

    # (Re)load the due-card queue on first visit or whenever the
    # active language changes.
    if st.session_state.get("quiz_language") != language:
        _load_queue(language)

    queue = st.session_state["quiz_queue"]
    index = st.session_state["quiz_index"]

    if index >= len(queue):
        _log_if_needed(language)
        reviewed = st.session_state.get("quiz_reviewed", 0)
        if reviewed:
            st.success(f"Session complete — {reviewed} card(s) reviewed.")
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
        if st.button("Show Answer", type="primary"):
            st.session_state["quiz_show_answer"] = True
            st.rerun()
    else:
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
        c1, c2, c3 = st.columns(3)
        for col, label in zip((c1, c2, c3), ("Hard", "Good", "Easy")):
            if col.button(label, key=f"grade_{label}_{card['card_id']}", use_container_width=True):
                result = grade_review(
                    card["easiness_factor"], card["interval_days"], card["repetition_number"], label
                )
                update_srs_review(
                    card["card_id"],
                    result["repetition_number"],
                    result["easiness_factor"],
                    result["interval_days"],
                    result["next_review_date"],
                )
                st.session_state["quiz_reviewed"] += 1
                if label != "Hard":
                    st.session_state["quiz_correct"] += 1
                st.session_state["quiz_index"] += 1
                st.session_state["quiz_show_answer"] = False
                st.rerun()
