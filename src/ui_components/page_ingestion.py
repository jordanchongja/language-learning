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
from src.database.queries import save_words_with_cards
from src.utils.time_utils import local_today


def _clean(value) -> str:
    """Coerce a CSV/dataframe cell to a trimmed string, treating
    NaN/None as empty."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _flash(message: str):
    """Queue a success message to show after the next st.rerun() —
    anything rendered before a rerun is wiped."""
    st.session_state["ingestion_flash"] = message


def _save(language: str, entries: list, source_text: str = "") -> str:
    """Build a card for each entry (cloze for Chinese, basic for
    Korean), save them all in one go, and return a summary message.

    Each entry is a dict with word, pronunciation, meaning, domain.
    """
    items = []
    for e in entries:
        if language == "Chinese":
            card = build_chinese_card(e["word"], source_text)
        else:
            card = build_korean_card(e["word"], e["meaning"])
        items.append({**e, **card, "source_article": source_text})

    with st.spinner("Saving..."):
        added, skipped = save_words_with_cards(language, items, local_today().isoformat())

    msg = f"Saved {added} word(s)."
    if skipped:
        msg += f" Skipped {skipped} already in your vocabulary."
    return msg


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
            entries = [
                {"word": _clean(row["word"]), "pronunciation": "", "meaning": _clean(row["meaning"]), "domain": domain}
                for _, row in edited.iterrows()
                if row["include"] and _clean(row["word"])
            ]
            _flash(_save(language, entries, st.session_state.get("cn_source_text_saved", "")))
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
                    entry = {"word": word.strip(), "pronunciation": romanization, "meaning": meaning, "domain": domain}
                    st.success(_save(language, [entry]))

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
                entries = [
                    {
                        "word": _clean(row.get("word")),
                        "pronunciation": _clean(row.get("romanization")) or _clean(row.get("pronunciation")),
                        "meaning": _clean(row.get("meaning")),
                        "domain": _clean(row.get("domain")) or default_domain,
                    }
                    for _, row in df.iterrows()
                    if _clean(row.get("word"))
                ]
                st.success(_save(language, entries))


def render(language: str):
    st.subheader("📥 Add Vocabulary")
    flash = st.session_state.pop("ingestion_flash", None)
    if flash:
        st.success(flash)

    if language == "Chinese":
        _render_chinese(language)
    else:
        _render_korean(language)
