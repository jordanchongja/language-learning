"""
Content ingestion UI — adapts to the active language.

Chinese: paste an article, tokenize it with jieba, review the new
candidate words (pinyin and meanings pre-filled offline, filler words
filtered out), then save. Saving builds a context cloze card for each
word from the pasted article and initializes its SRS state.

Korean: manual single-word entry or bulk CSV upload, with romanization
filled in automatically when left blank. There's no source article, so
each word gets a basic front/back card instead of a cloze.
"""
import pandas as pd
import streamlit as st

import config
from src.core.cloze_maker import build_chinese_card, build_korean_card
from src.core.dictionary import chinese_meaning, chinese_pinyin, korean_romanization
from src.core.nlp_processor import apply_filters, filter_new_words, tokenize_chinese_text
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

    msg = f"Saved {added} word(s) — they're ready in Study."
    if skipped:
        msg += f" Skipped {skipped} already in your vocabulary."
    return msg


def _render_chinese(language: str):
    st.subheader("📰 Paste Chinese Text")
    st.caption(
        "Paste an article or passage. It's split into words so you can pick which to learn — "
        "each saved word gets a fill-in-the-blank card built from its sentence in this text."
    )

    domain = st.selectbox("Domain for this batch", options=config.DEFAULT_DOMAINS[language], key="cn_domain")
    text = st.text_area("Source text", height=200, key="cn_source_text")

    if st.button("Find new words"):
        with st.spinner("Looking up words..."):
            words = filter_new_words(language, tokenize_chinese_text(text))
            # Look up pinyin/meanings once here rather than on every rerun.
            st.session_state["cn_candidates"] = [
                {"word": w, "pinyin": chinese_pinyin(w), "meaning": chinese_meaning(w)} for w in words
            ]
        st.session_state["cn_source_text_saved"] = text
        st.session_state["cn_batch"] = st.session_state.get("cn_batch", 0) + 1

    if "cn_candidates" not in st.session_state:
        return
    candidates = st.session_state["cn_candidates"]
    if not candidates:
        st.info("No new words found — everything in that text is already in your vocabulary.")
        return

    c1, c2 = st.columns(2)
    skip_single = c1.toggle("Hide single-character words", value=True, key="cn_skip_single")
    skip_stop = c2.toggle("Hide common filler words (的, 我们, 因为…)", value=True, key="cn_skip_stop")
    kept_words, hidden = apply_filters([c["word"] for c in candidates], skip_single, skip_stop)
    kept = [c for c in candidates if c["word"] in set(kept_words)]

    st.write(
        f"**{len(kept)}** new word(s) to review"
        + (f" ({hidden} hidden by filters)" if hidden else "")
        + ". Untick any you don't want, and edit pinyin/meanings if needed."
    )
    if not kept:
        return

    table = pd.DataFrame(
        {
            "include": True,
            "word": [c["word"] for c in kept],
            "pinyin": [c["pinyin"] for c in kept],
            "meaning": [c["meaning"] for c in kept],
        }
    )
    edited = st.data_editor(
        table,
        column_config={
            "include": st.column_config.CheckboxColumn("Add?", width="small"),
            "word": st.column_config.TextColumn("Word", disabled=True),
            "pinyin": st.column_config.TextColumn("Pinyin"),
            "meaning": st.column_config.TextColumn("Meaning", width="large"),
        },
        hide_index=True,
        # Filters change the rows, so give the editor a fresh key to
        # stop edits from sticking to the wrong row.
        key=f"cn_editor_{st.session_state['cn_batch']}_{skip_single}_{skip_stop}",
    )

    if st.button("Save to Vocabulary", type="primary"):
        entries = [
            {
                "word": _clean(row["word"]),
                "pronunciation": _clean(row["pinyin"]),
                "meaning": _clean(row["meaning"]),
                "domain": domain,
            }
            for _, row in edited.iterrows()
            if row["include"] and _clean(row["word"])
        ]
        _flash(_save(language, entries, st.session_state.get("cn_source_text_saved", "")))
        for key in ("cn_candidates", "cn_source_text_saved"):
            st.session_state.pop(key, None)
        st.rerun()


def _render_korean(language: str):
    tab_manual, tab_csv = st.tabs(["✍️ Manual Entry", "📄 CSV Upload"])

    with tab_manual:
        with st.form("korean_manual_form", clear_on_submit=True):
            # 2×2 rather than 4 across, so it stays usable on a phone.
            r1c1, r1c2 = st.columns(2)
            word = r1c1.text_input("Word")
            meaning = r1c2.text_input("Meaning")
            r2c1, r2c2 = st.columns(2)
            romanization = r2c1.text_input("Romanization", placeholder="Leave blank to auto-fill")
            domain = r2c2.selectbox("Domain", options=config.DEFAULT_DOMAINS[language])
            submitted = st.form_submit_button("Add Word", type="primary")

            if submitted:
                if not word.strip():
                    st.error("Word is required.")
                else:
                    entry = {
                        "word": word.strip(),
                        "pronunciation": romanization.strip() or korean_romanization(word.strip()),
                        "meaning": meaning,
                        "domain": domain,
                    }
                    st.success(_save(language, [entry]))

    with tab_csv:
        st.caption(
            "Columns (case-insensitive): **word** (required), meaning, romanization/pronunciation, domain. "
            "Blank romanizations are filled in automatically."
        )
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
                entries = []
                for _, row in df.iterrows():
                    word = _clean(row.get("word"))
                    if not word:
                        continue
                    pron = _clean(row.get("romanization")) or _clean(row.get("pronunciation"))
                    entries.append(
                        {
                            "word": word,
                            "pronunciation": pron or korean_romanization(word),
                            "meaning": _clean(row.get("meaning")),
                            "domain": _clean(row.get("domain")) or default_domain,
                        }
                    )
                st.success(_save(language, entries))


def render(language: str):
    st.subheader("📥 Add Words")
    flash = st.session_state.pop("ingestion_flash", None)
    if flash:
        st.success(flash)

    if language == "Chinese":
        _render_chinese(language)
    else:
        _render_korean(language)
