# Language Learning Studio

A local, no-paid-API multi-language flashcard app (Business Chinese +
Beginner Korean) built with Streamlit and SQLite, using a custom SM-2
spaced-repetition engine.

## Features
- **Chinese**: paste an article, tokenize it with `jieba`, and build context-aware cloze cards automatically.
- **Korean**: manual word entry or bulk CSV import, with basic front/back cards.
- **SRS**: SuperMemo-2 scheduling with Hard / Good / Easy grading.
- **Audio**: pronunciation playback via `gTTS` (needs internet at review time; the app degrades gracefully offline).
- **Dashboard**: Plotly charts for daily review activity, vocabulary by domain, and known-word count — filtered by the active language.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

With no configuration, data goes to a local SQLite file (`data/language.db`).

## Cloud database + password (use it from your phone)
Create `.streamlit/secrets.toml` (gitignored — never commit it):

```toml
TURSO_DATABASE_URL = "libsql://<your-db>.turso.io"
TURSO_AUTH_TOKEN = "<token from `turso db tokens create <db>`>"
APP_PASSWORD = "<anything you like>"
```

- With the two `TURSO_*` keys set, the app stores everything in [Turso](https://turso.tech)
  (hosted SQLite, free tier), so your computer and phone share the same vocabulary and progress.
- With `APP_PASSWORD` set, the app asks for it before showing anything.

## Deploying to Streamlit Community Cloud
1. Deploy `app.py` from this repo at [share.streamlit.io](https://share.streamlit.io).
2. In the app's **Settings → Secrets**, paste the same three keys as `secrets.toml`.

Without the Turso keys, a Streamlit Cloud deploy falls back to local SQLite, which is
wiped whenever the app restarts. Generated audio lives on local disk either way; it's just
regenerated when needed.
