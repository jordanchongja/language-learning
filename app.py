"""
Main Streamlit entry point: password gate, global sidebar, page router.

If APP_PASSWORD is set (Streamlit secrets or env var), the app asks
for it before showing anything or touching the database. Then it
initializes the database, renders the global sidebar (Active
Environment toggle + page navigation), and routes to the Ingestion /
Study / Dashboard pages.
"""
import hmac

import streamlit as st

import config
from src.database.db_setup import get_db, initialize_database
from src.ui_components import page_dashboard, page_ingestion, page_quiz

st.set_page_config(page_title="Language Learning Studio", page_icon="🗣️", layout="wide")


def _password_ok() -> bool:
    """Show a password prompt until the right password is entered.
    With no APP_PASSWORD configured (e.g. a plain local run), there's
    no gate. Unlocking lasts for this browser session."""
    expected = config.get_secret("APP_PASSWORD")
    if not expected or st.session_state.get("authenticated"):
        return True

    st.title("🔒 Language Learning Studio")
    with st.form("login"):
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Unlock", type="primary"):
            if hmac.compare_digest(password.encode(), expected.encode()):
                st.session_state["authenticated"] = True
                st.rerun()
            st.error("Incorrect password.")
    return False


if not _password_ok():
    st.stop()

# Runs the schema once per process; a no-op on later reruns.
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

# Coming back to Study should pick up words added since the queue was
# last loaded, so drop the cached queue whenever the page changes.
if st.session_state.get("_prev_page") != page:
    st.session_state.pop("quiz_language", None)
st.session_state["_prev_page"] = page

st.sidebar.divider()
st.sidebar.caption("☁️ Turso cloud database" if get_db().is_remote else f"💾 Local database: `{config.DB_PATH}`")

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
