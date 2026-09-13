# Custom Multi-Language Learning Pipeline: Technical Implementation Plan

This document serves as the architectural blueprint and phased implementation plan for your custom language learning application. It is designed to be fully self-contained, running locally without paid APIs. It specifically caters to your two primary goals:
1. **Business Chinese:** An automated pipeline for ingesting specialized vocabulary related to the dairy industry, futures markets, and supply chain logistics.
2. **Beginner Korean:** A flexible workflow relying on manual entry and CSV bulk-uploads to support foundational learning.

## 1. System Architecture Overview

The application follows a modular, three-tier architecture tailored for local execution:

*   **Frontend (Presentation Layer):** Built with **Streamlit**. It handles the UI, routing between different views (Ingestion, Study, Dashboard), rendering media (audio playback), and global state (active language toggle in the sidebar).
*   **Business Logic (Service Layer):** Pure Python modules that handle:
    *   **Text Processing (Chinese):** Using `jieba` (an essential, free local Python library for Chinese word segmentation) to tokenize pasted text and identify words.
    *   **Cloze Generation (Chinese):** Algorithms to locate target words in context sentences and replace them with blanks (e.g., `___`).
    *   **Manual/Bulk Entry (Korean):** Handlers for parsing CSV files and manual form submissions for basic card creation.
    *   **SRS Engine:** A Python implementation of the SuperMemo-2 (SM-2) algorithm to calculate the next review date based on user feedback.
    *   **Audio Generation:** Using `gTTS` (requires internet but is free) or `pyttsx3` (fully offline) to generate `.mp3` files for pronunciation.
*   **Data Access Layer (Database):** **SQLite**. A local database file (`app.db`) that stores all vocabulary, context sentences, SRS review states, and study logs for both languages.

## 2. Database Schema

The SQLite database will consist of four primary tables to manage the vocabulary and SRS states. Importantly, the `words` table includes a `language` tag to cleanly separate your decks.

```sql
-- Table: words (Tracks individual vocabulary items)
CREATE TABLE words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT NOT NULL,        -- 'Chinese' or 'Korean'
    word TEXT NOT NULL,            -- Unique per language can be enforced via constraints
    pronunciation TEXT,            -- Pinyin for Chinese, Romanization for Korean
    meaning TEXT,
    domain TEXT DEFAULT 'General', -- e.g., 'Dairy Futures', 'Basics'
    status TEXT DEFAULT 'New',     -- 'New', 'Learning', 'Known'
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(language, word)
);

-- Table: cards (Tracks the flashcards/cloze sentences for the SRS)
CREATE TABLE cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER,
    sentence_text TEXT NOT NULL,       -- Original sentence (or just word if no context)
    cloze_text TEXT NOT NULL,          -- Sentence with the target word blanked out (or basic card front)
    translation TEXT,
    source_article TEXT,               -- Where this was scraped/pasted from
    FOREIGN KEY (word_id) REFERENCES words(id)
);

-- Table: srs_reviews (Tracks the SuperMemo-2 state for each card)
CREATE TABLE srs_reviews (
    card_id INTEGER PRIMARY KEY,
    repetition_number INTEGER DEFAULT 0,
    easiness_factor REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 0,
    next_review_date DATE DEFAULT CURRENT_DATE,
    last_review_date DATE,
    FOREIGN KEY (card_id) REFERENCES cards(id)
);

-- Table: study_logs (For the Analytics Dashboard)
CREATE TABLE study_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT NOT NULL,
    study_date DATE DEFAULT CURRENT_DATE,
    cards_reviewed INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    session_duration_seconds INTEGER DEFAULT 0
);
```

## 3. Recommended Folder Structure

This structure separates concerns, making it easy for the Lead Developer (Claude) to build and maintain the codebase.

```text
language-learning-app/
│
├── app.py                    # Main Streamlit entry point (Global Sidebar & Navigation)
├── requirements.txt          # Dependencies (streamlit, sqlite3, jieba, gTTS, plotly, pandas)
├── config.py                 # Global constants (DB paths, domain categories, supported languages)
│
├── data/                     # Local storage
│   └── language.db           # SQLite Database file
│
├── assets/                   # Static files
│   └── audio/                # Temporary directory for generated TTS mp3 files
│
└── src/                      # Source Code modules
    ├── database/
    │   ├── __init__.py
    │   ├── db_setup.py       # Functions to initialize tables
    │   └── queries.py        # CRUD operations (insert words, get due cards by language)
    │
    ├── core/
    │   ├── __init__.py
    │   ├── nlp_processor.py  # Chinese text ingestion, jieba segmentation
    │   ├── cloze_maker.py    # logic to parse sentences and generate clozes
    │   └── srs_engine.py     # SM-2 algorithm implementation
    │
    ├── utils/
    │   ├── __init__.py
    │   └── audio_gen.py      # Wrapper for gTTS/pyttsx3
    │
    └── ui_components/
        ├── __init__.py
        ├── page_ingestion.py # Streamlit UI for Chinese text pasting & Korean manual/CSV entry
        ├── page_quiz.py      # Streamlit UI for the SRS Review session
        └── page_dashboard.py # Streamlit UI for Plotly/Altair metrics
```

## 4. Phased Implementation Plan

Provide these exact instructions to Claude to ensure structured, incremental development.

### Phase 1: Foundation, Global Sidebar & Data Layer
**Goal:** Set up the environment, database, and the Streamlit shell with language toggling.
*   **Step 1:** Create the folder structure and `requirements.txt`. Ensure `jieba` is included for Chinese tokenization.
*   **Step 2:** Write `src/database/db_setup.py` to execute the SQLite schema (creating `words`, `cards`, `srs_reviews`, and `study_logs` tables). Ensure the `language` column is implemented.
*   **Step 3:** Create `app.py`. Implement a **global sidebar** that includes a dropdown/radio button to toggle the "Active Environment" between `Business Chinese` and `Beginner Korean`. Store this selection in `st.session_state`.
*   **Step 4:** Write basic wrapper functions in `src/database/queries.py` to `add_word()`, `get_all_words(language)`, and `mark_word_known()`.

### Phase 2: Dual Content Ingestion Pipeline
**Goal:** Build the UI and logic for adding new vocabulary, adapting to the selected language.
*   **Step 1 (Chinese Pipeline):** Develop `src/core/nlp_processor.py`. Write a function that takes Chinese text, tokenizes it using `jieba`, filters out punctuation, and queries the DB to filter out known words. Build the UI in `page_ingestion.py` for this text pasting workflow when Chinese is active.
*   **Step 2 (Korean Pipeline):** Build the alternative UI in `page_ingestion.py` for when Korean is active. This should include:
    *   A simple form for manual card creation (Word, Romanization, Meaning).
    *   A file uploader (`st.file_uploader`) accepting `.csv` files for bulk vocabulary import.
*   **Step 3:** For both pipelines, allow the user to review the pending words, specify their Domain, and save them to the `words` table with the correct `language` tag.

### Phase 3: Automated Cloze & Audio Generation
**Goal:** Automatically create context-rich flashcards (for Chinese) and basic flashcards (for Korean), alongside pronunciation audio.
*   **Step 1:** Develop `src/core/cloze_maker.py`. For Chinese, write a function that splits the pasted article into sentences, finds the target words, and creates a `cloze_text` string. For Korean manual entries, simply map the word/meaning to a basic front/back flashcard format in the `cards` table.
*   **Step 2:** Save these sentences/cards into the `cards` table, and initialize their SRS state in the `srs_reviews` table.
*   **Step 3:** Implement `src/utils/audio_gen.py` using `gTTS` (or `pyttsx3`). Create a function that detects the language, generates an `.mp3`, and saves it to `assets/audio/`.

### Phase 4: Custom SRS & Quiz UI
**Goal:** Build the SuperMemo-2 logic and the daily study interface.
*   **Step 1:** Implement the SM-2 algorithm in `src/core/srs_engine.py`. It should take an `easiness_factor`, `interval`, `repetition_number`, and a user grade (0-5 or Hard/Good/Easy) and return the `next_review_date`.
*   **Step 2:** Build `src/ui_components/page_quiz.py`. Query the database for cards where `next_review_date <= CURRENT_DATE` **and** the language matches the active `st.session_state` language.
*   **Step 3:** Display the `cloze_text` (or basic Korean word). Add a "Show Answer" button. When clicked, reveal the original text, translation, and play the generated audio using `st.audio()`.
*   **Step 4:** Display "Hard", "Good", and "Easy" buttons. On click, update the card's SRS state in the DB and move to the next card.

### Phase 5: Dashboard & Analytics
**Goal:** Visualize progress to maintain a learning streak, segmented by language.
*   **Step 1:** Ensure that every completed quiz session logs the count of reviewed cards to the `study_logs` table, tagging the language studied.
*   **Step 2:** Build `src/ui_components/page_dashboard.py` using `Plotly` via Streamlit. Ensure all metrics filter by the currently active language in the sidebar.
*   **Step 3:** Create visualizations:
    *   A line chart showing "Cards Reviewed per Day" over the last 30 days.
    *   A pie chart or bar graph grouping the `words` table by `domain` to show the size of the vocabulary in specific areas (e.g., "Dairy Futures", "Korean Basics").
    *   A metric showing the total number of "Known" words.

> [!TIP]
> **Important Note for Claude:** When parsing Chinese sentences for clozes, ensure you account for full-width punctuation (e.g., `。`, `，`, `、`) when splitting the source article into manageable sentences. For Korean, fallback gracefully to basic front/back cards since there is no source article context.
