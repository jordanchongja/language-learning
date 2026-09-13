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

The SQLite database (`data/language.db`) and generated audio
(`assets/audio/*.mp3`) are created automatically on first run.

## ⚠️ Deploying to Streamlit Community Cloud
Community Cloud's filesystem is **ephemeral** — it resets on every
app restart (redeploy, waking from sleep, host maintenance). That
means `data/language.db` and any generated audio get wiped back to
whatever's in the git repo (i.e. empty) on restart. Fine for a demo;
**not** a reliable place to keep real study progress. Use a local run
(`streamlit run app.py`) for actual day-to-day studying.
