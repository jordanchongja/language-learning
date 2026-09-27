# Language Learning Studio

A local, no-paid-API multi-language flashcard app (Business Chinese +
Beginner Korean) built with Streamlit and SQLite, using a custom SM-2
spaced-repetition engine.

## Features
- **Overview**: today's due cards and streak per language, plus a guide to using the app.
- **Chinese**: paste an article, tokenize it with `jieba`, and get context cloze cards. Pinyin
  (`pypinyin`) and English meanings (CC-CEDICT) are pre-filled offline; one-character and filler
  words can be filtered out.
- **Korean**: manual entry or bulk CSV import with automatic romanization, basic front/back cards.
- **SRS**: SuperMemo-2 scheduling with Again / Hard / Good / Easy grading and a daily new-card limit.
- **Vocabulary**: search, filter, edit, delete, CSV export, and a full backup download.
- **Audio**: word and sentence pronunciation via `gTTS` (needs internet; degrades gracefully offline).
- **Dashboard**: streak, cards due, known/total words, daily reviews, and vocabulary by domain.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

With no configuration, data goes to a local SQLite file (`data/language.db`).

## Cloud database + sign-in (use it from your phone)
Create `.streamlit/secrets.toml` (gitignored — never commit it):

```toml
TURSO_DATABASE_URL = "libsql://<your-db>.turso.io"
TURSO_AUTH_TOKEN = "<token from `turso db tokens create <db>`>"
APP_PASSWORD = "<anything you like>"
```

- With the two `TURSO_*` keys set, the app stores everything in [Turso](https://turso.tech)
  (hosted SQLite, free tier), so your computer and phone share the same vocabulary and progress.
- With `APP_PASSWORD` set, the app asks for it before showing anything (once per browser session).

### Google sign-in (stays signed in for 30 days)
1. In [Google Cloud Console](https://console.cloud.google.com), create a project, then under
   **Google Auth Platform**: configure the consent screen (External) and add yourself as a test user.
2. **Clients → Create client → Web application.** Authorized redirect URIs:
   `https://<your-app>.streamlit.app/oauth2callback` and `http://localhost:8501/oauth2callback`.
3. Add to secrets (top-level keys must come before `[auth]`):

```toml
ALLOWED_EMAILS = "you@gmail.com"   # comma-separated; nobody else can get in

[auth]
redirect_uri = "https://<your-app>.streamlit.app/oauth2callback"  # localhost URL for local runs
cookie_secret = "<long random string>"
client_id = "<from Google>"
client_secret = "<from Google>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

When `[auth]` is present it replaces the password prompt.

## Deploying to Streamlit Community Cloud
1. Deploy `app.py` from this repo at [share.streamlit.io](https://share.streamlit.io).
2. In the app's **Settings → Secrets**, paste the same keys as `secrets.toml` (with the
   Streamlit Cloud `redirect_uri` if you use Google sign-in).

Without the Turso keys, a Streamlit Cloud deploy falls back to local SQLite, which is
wiped whenever the app restarts. Generated audio lives on local disk either way; it's just
regenerated when needed.

## Credits
Chinese–English definitions from [CC-CEDICT](https://www.mdbg.net/chinese/dictionary?page=cedict)
(`assets/dict/cedict_ts.u8.gz`), licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
