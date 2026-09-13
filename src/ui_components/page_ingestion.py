"""
Content ingestion UI — adapts to the active language.

Chinese: paste an article, tokenize it with jieba, review the new
candidate words, then save. Saving builds a context cloze card for
each word from the pasted article and initializes its SRS state, so
it's immediately reviewable in Study.

Korean: manual single-word entry or bulk CSV upload. There's no
source article, so each word gets a basic front/back card instead of
a cloze.
"""
import pandas as pd
import streamlit as st

import config
from src.core.cloze_maker import build_chinese_card, build_korean_card
from src.core.nlp_processor import filter_new_words, tokenize_chinese_text
from src.database.queries import add_card, add_word, init_srs_review


def _clean(value) -> str:
    """Coerce a CSV/dataframe cell to a trimmed string, treating
    NaN/None as empty."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _save_word_and_card(language, word, pronunciation, meaning, domain, source_text=""):
    """Add a word, build its card (cloze for Chinese / basic for
    Korean), and initialize its SRS state.

    Returns True if the word was newly added, False if it was a
    duplicate for this language (nothing is created in that case).
    """
    word_id = add_word(language, word, pronunciation, meaning, domain)
    if not word_id:
        return False

    if language == "Chinese":
        card_fields = build_chinese_card(word, source_text)
    else:
        card_fields = build_korean_card(word, meaning)

    card_id = add_card(
        word_id,
        card_fields["sentence_text"],
        card_fields["cloze_text"],
        translation=meaning,
        source_article=source_text,
    )
    init_srs_review(card_id)
    return True


def _render_chinese(language: str):
    st.subheader("🇨🇳 Paste Chinese Text")
    st.caption(
        "Paste an article or passage. It's tokenized with jieba so you can pick which words "
        "to add — each saved word gets a cloze card built from this text."
    )

    domain = st.selectbox("Domain for this batch", options=config.DEFAULT_DOMAINS[language], key="cn_domain")
    text = st.text_area("Source text", height=200, key="cn_source_text")

    if st.button("Tokenize"):
        candidates = tokenize_chinese_text(text)
        st.session_state["cn_candidates"] = filter_new_words(language, candidates)
        st.session_state["cn_source_text_saved"] = text

    candidates = st.session_state.get("cn_candidates", [])
    if candidates:
        st.write(f"Found **{len(candidates)}** new word(s) not already in your vocabulary:")
        table = pd.DataFrame({"include": True, "word": candidates, "meaning": ""})
        edited = st.data_editor(
            table,
            column_config={
                "include": st.column_config.CheckboxColumn("Add?"),
                "word": st.column_config.TextColumn("Word", disabled=True),
                "meaning": st.column_config.TextColumn("Meaning (optional)"),
            },
            hide_index=True,
            key="cn_editor",
        )

        if st.button("Save to Vocabulary", type="primary"):
            source_text = st.session_state.get("cn_source_text_saved", "")
            added, skipped = 0, 0
            for _, row in edited.iterrows():
                word = _clean(row["word"])
                if not row["include"] or not word:
                    continue
                ok = _save_word_and_card(language, word, "", _clean(row["meaning"]), domain, source_text)
                added += 1 if ok else 0
                skipped += 0 if ok else 1
            msg = f"Saved {added} word(s) with context cards."
            if skipped:
                msg += f" Skipped {skipped} duplicate(s)."
            st.success(msg)
            st.session_state.pop("cn_candidates", None)
            st.session_state.pop("cn_source_text_saved", None)
            st.rerun()
    elif "cn_candidates" in st.session_state:
        st.info("No new words found — everything in that text is already in your vocabulary.")


def _render_korean(language: str):
    tab_manual, tab_csv = st.tabs(["✍️ Manual Entry", "📄 CSV Upload"])

    with tab_manual:
        with st.form("korean_manual_form", clear_on_submit=True):
            cols = st.columns(4)
            word = cols[0].text_input("Word")
            romanization = cols[1].text_input("Romanization")
            meaning = cols[2].text_input("Meaning")
            domain = cols[3].selectbox("Domain", options=config.DEFAULT_DOMAINS[language])
            submitted = st.form_submit_button("Add Word", type="primary")

            if submitted:
                if not word.strip():
                    st.error("Word is required.")
                else:
                    ok = _save_word_and_card(language, word, romanization, meaning, domain)
                    st.success(f"Added '{word}'.") if ok else st.warning(f"'{word}' already exists.")

    with tab_csv:
        st.caption("Recognized columns (case-insensitive): word, romanization/pronunciation, meaning, domain.")
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded is not None:
            try:
                df = pd.read_csv(uploaded)
            except Exception as e:
                st.error(f"Couldn't read that CSV: {e}")
                return
            df.columns = [c.strip().lower() for c in df.columns]
            if "word" not in df.columns:
                st.error("CSV must include a 'word' column.")
                return

            st.dataframe(df, hide_index=True)
            default_domain = st.selectbox(
                "Fallback domain (used for rows without a 'domain' column)",
                options=config.DEFAULT_DOMAINS[language],
                key="csv_default_domain",
            )

            if st.button("Import CSV", type="primary"):
                added, skipped = 0, 0
                for _, row in df.iterrows():
                    word = _clean(row.get("word"))
                    if not word:
                        continue
                    pron = _clean(row.get("romanization")) or _clean(row.get("pronunciation"))
                    meaning = _clean(row.get("meaning"))
                    row_domain = _clean(row.get("domain")) or default_domain
                    ok = _save_word_and_card(language, word, pron, meaning, row_domain)
                    added += 1 if ok else 0
                    skipped += 0 if ok else 1
                msg = f"Imported {added} word(s)."
                if skipped:
                    msg += f" Skipped {skipped} duplicate(s)."
                st.success(msg)


def render(language: str):
    st.subheader("📥 Add Vocabulary")
    if language == "Chinese":
        _render_chinese(language)
    else:
        _render_korean(language)
