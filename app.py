"""
Main Streamlit entry point: global sidebar + page router.

Initializes the SQLite database on every startup, renders the global
sidebar (Active Environment toggle + page navigation), and routes to
the Ingestion / Study / Dashboard pages.
"""
import streamlit as st

import config
from src.database.db_setup import initialize_database
from src.ui_components import page_dashboard, page_ingestion, page_quiz

st.set_page_config(page_title="Language Learning Studio", page_icon="🗣️", layout="wide")

# Safe to call on every run — only creates tables that don't exist yet.
initialize_database()

# ---------------------------------------------------------------------------
# Global sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("🗣️ Language Learning Studio")

active_env_label = st.sidebar.radio(
    "Active Environment",
    options=list(config.LANGUAGES.keys()),
    key="active_env_label",
)
# DB-facing language code ('Chinese' / 'Korean'), read by every page/query.
st.session_state["language"] = config.LANGUAGES[active_env_label]

st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    options=["Ingestion", "Study", "Dashboard"],
    key="active_page",
)

st.sidebar.divider()
st.sidebar.caption(f"Database: `{config.DB_PATH}`")

# ---------------------------------------------------------------------------
# Main area — route to the active page
# ---------------------------------------------------------------------------
language = st.session_state["language"]
st.title(active_env_label)

if page == "Ingestion":
    page_ingestion.render(language)
elif page == "Study":
    page_quiz.render(language)
elif page == "Dashboard":
    page_dashboard.render(language)
