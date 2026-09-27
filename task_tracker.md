# Project Task Tracker

This tracker aligns with the 5 phases defined in `implementation_plan.md`. Use this to track progress.

- [x] **Phase 1: Foundation, Global Sidebar & Data Layer**
  - [x] Create folder structure and `requirements.txt` (include `jieba`).
  - [x] Write `src/database/db_setup.py` (ensure `language` column exists).
  - [x] Create `app.py` with global sidebar (toggle for Chinese/Korean).
  - [x] Write basic CRUD functions in `src/database/queries.py`.

- [x] **Phase 2: Dual Content Ingestion Pipeline**
  - [x] Implement `src/core/nlp_processor.py` (Chinese `jieba` tokenization).
  - [x] Build Chinese UI in `page_ingestion.py` (text pasting).
  - [x] Build Korean UI in `page_ingestion.py` (manual form + CSV upload).
  - [x] Save pending words to the DB with the correct language tag.

- [x] **Phase 3: Automated Cloze & Audio Generation**
  - [x] Implement `src/core/cloze_maker.py` (context sentences for Chinese, basic for Korean).
  - [x] Save sentences to `cards` table and initialize SRS state.
  - [x] Implement `src/utils/audio_gen.py` (gTTS/pyttsx3) and save `.mp3`.

- [x] **Phase 4: Custom SRS & Quiz UI**
  - [x] Implement SuperMemo-2 algorithm in `src/core/srs_engine.py`.
  - [x] Build `src/ui_components/page_quiz.py` filtering by language.
  - [x] Implement Show Answer, Audio Playback, and grading buttons (Hard/Good/Easy).

- [x] **Phase 5: Dashboard & Analytics**
  - [x] Update session logging in `study_logs` with language tags.
  - [x] Build `src/ui_components/page_dashboard.py` (Plotly charts filtered by language).
  - [x] Visualize Cards Reviewed per Day, Vocabulary by Domain, Total Known Words.

- [x] **Cloud & Accuracy Fixes**
  - [x] Turso cloud database (falls back to local SQLite when unconfigured).
  - [x] Password gate via `APP_PASSWORD`.
  - [x] "Again" grade that resets a forgotten card and re-queues it in the session.
  - [x] Words auto-promote to Learning / Known (Known at a 21+ day interval).
  - [x] Reviews logged per grade, so partial sessions count on the dashboard.
  - [x] Due dates use local time (UTC+8), not UTC.
  - [x] Study reloads due cards when opened; "Saved N words" message survives the rerun.

- [x] **Features**
  - [x] Overview page: today's due cards per language + how-to guide.
  - [x] Auto-fill pinyin (`pypinyin`) and meanings (CC-CEDICT) for Chinese.
  - [x] Auto-fill romanization for Korean (`korean-romanizer`).
  - [x] Stop-word / single-character filter for tokenized words.
  - [x] Daily new-card limit (per language, saved in a `settings` table).
  - [x] Vocabulary page: search, filter, edit, delete, fill missing pinyin/meanings.
  - [x] CSV export + full backup (.zip).
  - [x] Study streak, due-today, and total-word metrics.
  - [x] Sentence audio; audio cache keyed by text.
  - [x] Google sign-in (`st.login`) restricted to `ALLOWED_EMAILS`.
