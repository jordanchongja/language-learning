"""
Vocabulary browser: search, filter, edit, delete, and export.

Edits cover pronunciation, meaning, and domain. Status is managed by
the SRS (New → Learning → Known) so it's read-only here. Deleting a
word also deletes its card and review history.
"""
import io
import json
import zipfile

import pandas as pd
import streamlit as st

import config
from src.core.dictionary import chinese_meaning, chinese_pinyin, korean_romanization
from src.database.queries import delete_words, export_all_tables, get_vocabulary, update_words
from src.utils.time_utils import local_today

_EDITABLE = ["pronunciation", "meaning", "domain"]


def _flash(message: str):
    st.session_state["vocab_flash"] = message


def _fill_missing(language: str, rows: list) -> int:
    """Fill blank pronunciations (and, for Chinese, meanings) from the
    offline dictionaries. Returns how many words changed."""
    changes = []
    for r in rows:
        pron, meaning = r["pronunciation"] or "", r["meaning"] or ""
        if language == "Chinese":
            pron = pron or chinese_pinyin(r["word"])
            meaning = meaning or chinese_meaning(r["word"])
        else:
            pron = pron or korean_romanization(r["word"])
        if pron != (r["pronunciation"] or "") or meaning != (r["meaning"] or ""):
            changes.append({"id": r["id"], "pronunciation": pron, "meaning": meaning, "domain": r["domain"]})
    update_words(changes)
    return len(changes)


def _render_export(language: str, rows: list):
    st.markdown("#### 💾 Export & backup")
    c1, c2 = st.columns(2)

    # Columns match the CSV importer, so this file can be re-imported.
    csv = pd.DataFrame(rows)[["word", "pronunciation", "meaning", "domain", "status", "added_at"]]
    c1.download_button(
        f"Download {language} words (CSV)",
        csv.to_csv(index=False).encode("utf-8-sig"),  # BOM so Excel shows Chinese/Korean correctly
        file_name=f"{language.lower()}_vocabulary_{local_today().isoformat()}.csv",
        mime="text/csv",
        width="stretch",
    )

    if c2.button("Prepare full backup (all languages)", width="stretch"):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for table, table_rows in export_all_tables().items():
                zf.writestr(f"{table}.json", json.dumps(table_rows, ensure_ascii=False, indent=1, default=str))
        st.session_state["vocab_backup"] = buffer.getvalue()
    if "vocab_backup" in st.session_state:
        c2.download_button(
            "⬇️ Download backup (.zip)",
            st.session_state["vocab_backup"],
            file_name=f"language_app_backup_{local_today().isoformat()}.zip",
            mime="application/zip",
            width="stretch",
        )
    st.caption("The full backup has every table — words, cards, review history, and settings.")


def render(language: str):
    st.subheader("📖 Vocabulary")
    flash = st.session_state.pop("vocab_flash", None)
    if flash:
        st.success(flash)

    rows = get_vocabulary(language)
    if not rows:
        st.info("No words yet — add some on the Add Words page.")
        return

    search = st.text_input("🔍 Search", placeholder="word, pronunciation, or meaning")
    c1, c2 = st.columns(2)
    statuses = c1.multiselect("Status", config.WORD_STATUSES)
    domains_present = sorted({r["domain"] for r in rows if r["domain"]})
    domains = c2.multiselect("Domain", domains_present)

    df = pd.DataFrame(rows)
    if search:
        needle = search.strip().lower()
        haystack = (df["word"].fillna("") + " " + df["pronunciation"].fillna("") + " " + df["meaning"].fillna(""))
        df = df[haystack.str.lower().str.contains(needle, regex=False)]
    if statuses:
        df = df[df["status"].isin(statuses)]
    if domains:
        df = df[df["domain"].isin(domains)]

    counts = pd.DataFrame(rows)["status"].value_counts()
    st.caption(
        f"Showing {len(df)} of {len(rows)} · "
        + " · ".join(f"{s}: {counts.get(s, 0)}" for s in config.WORD_STATUSES)
    )

    original = df.reset_index(drop=True)
    table = original.copy()
    table.insert(0, "delete", False)
    domain_options = list(dict.fromkeys(config.DEFAULT_DOMAINS[language] + domains_present))
    edited = st.data_editor(
        table,
        column_config={
            "id": None,  # hidden
            "delete": st.column_config.CheckboxColumn("🗑️", width="small", help="Tick to delete"),
            "word": st.column_config.TextColumn("Word", disabled=True),
            "pronunciation": st.column_config.TextColumn("Pronunciation"),
            "meaning": st.column_config.TextColumn("Meaning", width="large"),
            "domain": st.column_config.SelectboxColumn("Domain", options=domain_options),
            "status": st.column_config.TextColumn("Status", disabled=True),
            "added_at": st.column_config.TextColumn("Added", disabled=True),
            "next_review_date": st.column_config.TextColumn("Next review", disabled=True),
        },
        hide_index=True,
        width="stretch",
        # Fresh key per filter combo so edits never attach to the wrong row.
        key=f"vocab_editor_{language}_{search}_{statuses}_{domains}",
    )

    changed_mask = (edited[_EDITABLE].fillna("") != original[_EDITABLE].fillna("")).any(axis=1)
    changes = edited[changed_mask & ~edited["delete"]][["id"] + _EDITABLE].to_dict("records")
    to_delete = edited[edited["delete"]]

    if changes or len(to_delete):
        confirm_delete = True
        if len(to_delete):
            st.warning(
                f"{len(to_delete)} word(s) will be deleted with their review history: "
                + ", ".join(to_delete["word"].head(10))
                + ("…" if len(to_delete) > 10 else "")
            )
            confirm_delete = st.checkbox("Yes, delete them")
        label = f"Save changes ({len(changes)} edited, {len(to_delete)} to delete)"
        if st.button(label, type="primary", disabled=not confirm_delete):
            update_words(changes)
            delete_words([int(i) for i in to_delete["id"]])
            _flash(f"Saved {len(changes)} edit(s), deleted {len(to_delete)} word(s).")
            st.rerun()

    missing = [r for r in rows if not r["pronunciation"] or (language == "Chinese" and not r["meaning"])]
    if missing:
        what = "pinyin/meanings" if language == "Chinese" else "romanizations"
        if st.button(f"✨ Fill in missing {what} ({len(missing)} word(s))"):
            with st.spinner("Looking up..."):
                n = _fill_missing(language, missing)
            _flash(f"Filled in {n} word(s).")
            st.rerun()

    st.divider()
    _render_export(language, rows)
