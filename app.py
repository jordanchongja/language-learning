"""
Main Streamlit entry point: sign-in, global sidebar, page router.

Sign-in depends on which secrets are set (first match wins):
- `[auth]` section → Google sign-in, limited to ALLOWED_EMAILS. The
  login cookie lasts 30 days, so a phone stays signed in.
- APP_PASSWORD → a password prompt, remembered for the browser session.
- neither → no sign-in (plain local use).

Then it initializes the database, renders the global sidebar (Active
Environment toggle + page navigation), and routes to the pages.
"""
import hmac

import streamlit as st

import config
from src.database.db_setup import get_db, initialize_database
from src.ui_components import (
    page_dashboard,
    page_ingestion,
    page_overview,
    page_quiz,
    page_vocabulary,
)

st.set_page_config(page_title="Language Learning Studio", page_icon="🗣️", layout="wide")

PAGES = {
    "Overview": page_overview,
    "Study": page_quiz,
    "Add Words": page_ingestion,
    "Vocabulary": page_vocabulary,
    "Dashboard": page_dashboard,
}


def _google_auth_configured() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False  # no secrets.toml at all


def _google_ok() -> bool:
    """Google sign-in, restricted to the comma-separated ALLOWED_EMAILS.
    With ALLOWED_EMAILS unset nobody gets in — any Google account can
    complete the sign-in, so the allowlist is what keeps others out."""
    if not st.user.is_logged_in:
        st.title("🔒 Language Learning Studio")
        st.button("Sign in with Google", type="primary", on_click=st.login)
        return False

    allowed = {e.strip().lower() for e in config.get_secret("ALLOWED_EMAILS").split(",") if e.strip()}
    if (st.user.email or "").lower() in allowed:
        return True

    st.title("🔒 Language Learning Studio")
    if allowed:
        st.error(f"{st.user.email} isn't allowed to use this app.")
    else:
        st.error("No one is allowed in yet — add your address to ALLOWED_EMAILS in the app's secrets.")
    st.button("Sign out", on_click=st.logout)
    return False


def _password_ok() -> bool:
    """Password prompt until APP_PASSWORD is entered; lasts for this
    browser session."""
    expected = config.get_secret("APP_PASSWORD")
    if st.session_state.get("authenticated"):
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


if _google_auth_configured():
    signed_in = _google_ok()
elif config.get_secret("APP_PASSWORD"):
    signed_in = _password_ok()
else:
    signed_in = True
if not signed_in:
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

page = st.sidebar.radio("Navigate", options=list(PAGES), key="active_page")

# Coming back to Study should pick up words added since the queue was
# last loaded, so drop the cached queue whenever the page changes.
if st.session_state.get("_prev_page") != page:
    st.session_state.pop("quiz_language", None)
st.session_state["_prev_page"] = page

st.sidebar.divider()
st.sidebar.caption("☁️ Turso cloud database" if get_db().is_remote else f"💾 Local database: `{config.DB_PATH}`")
if _google_auth_configured():
    st.sidebar.caption(f"Signed in as {st.user.email}")
    st.sidebar.button("Sign out", on_click=st.logout)

# ---------------------------------------------------------------------------
# Main area — route to the active page
# ---------------------------------------------------------------------------
language = st.session_state["language"]
st.title(active_env_label)
PAGES[page].render(language)
