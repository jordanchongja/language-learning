"""
Overview / home page: today's status for each language plus a guide
to how the app is meant to be used.
"""
import streamlit as st

import config
from src.database.queries import get_study_dates
from src.ui_components.page_dashboard import current_streak, due_today_count
from src.utils.time_utils import local_today


def _go(env_label: str, page: str):
    # Runs as a button callback, i.e. before the sidebar widgets are
    # drawn on the next run, so their values can still be changed.
    st.session_state["active_env_label"] = env_label
    st.session_state["active_page"] = page


def _render_today():
    st.markdown("### Today")
    today = local_today()
    cols = st.columns(len(config.LANGUAGES))
    for col, (label, language) in zip(cols, config.LANGUAGES.items()):
        with col.container(border=True):
            due = due_today_count(language, today)
            streak = current_streak(get_study_dates(language), today)
            st.markdown(f"**{label}**")
            st.markdown(f"📚 **{due}** card(s) due · 🔥 {streak}-day streak")
            if due:
                st.button(
                    f"Study {label.split()[-1]} now",
                    key=f"go_study_{language}",
                    type="primary",
                    width="stretch",
                    on_click=_go,
                    args=(label, "Study"),
                )
            else:
                st.button(
                    "Add new words",
                    key=f"go_add_{language}",
                    width="stretch",
                    on_click=_go,
                    args=(label, "Add Words"),
                )


_GUIDE = """
### How to use this app

The app is a **flashcard system with spaced repetition**: you add words once, then review a
few minutes a day. Each card comes back just before you'd forget it — soon for new or hard
words, weeks or months later for ones you know well.

#### The daily routine (5–15 minutes)
1. Open **Study** and clear the cards due today.
2. When you come across useful vocabulary (a news article, a work email, a lesson), add it on
   **Add Words**.
3. Glance at **Dashboard** now and then to keep your streak going.

Switch pages with the tabs at the top. Pick the language in the **sidebar** (» at the top left on a
phone), or use the buttons under **Today** — every page only shows the selected language.

---

#### 📥 Add Words
**Business Chinese — paste real text.**
1. Choose a **Domain** (e.g. Dairy Futures) so you can track vocabulary by topic.
2. Paste an article or paragraph and tap **Find new words**. The text is split into words, and
   anything already in your vocabulary is skipped.
3. Pinyin and English meanings are filled in automatically from a built-in dictionary. Check
   them — for compound terms the meaning is pieced together (e.g. 期货 futures · 市场 market) —
   and fix anything that's off.
4. Untick words you don't want. One-character words and fillers (的, 我们, 因为…) are hidden by
   default; switch the toggles off to see them.
5. **Save to Vocabulary.** Each word becomes a fill-in-the-blank card using its sentence from
   the article, so you learn it in context.

**Beginner Korean — enter words directly.**
- **Manual Entry:** type the word and meaning. Leave romanization blank to fill it in
  automatically (it follows spelling, so double-check pronunciation changes).
- **CSV Upload:** import a list at once. Columns: `word` (required), `meaning`,
  `romanization`, `domain`. Example:
  ```
  word,meaning,domain
  안녕하세요,hello,Korean Basics
  감사합니다,thank you,Korean Basics
  ```

#### 📚 Study
1. Read the front of the card. For Chinese it's a sentence with the word blanked out (___) —
   try to recall the missing word. For Korean it's the word — recall its meaning.
2. Tap **Show Answer** to see the word, pronunciation, meaning, and audio (🔊 Sentence audio
   plays the whole sentence).
3. Grade yourself honestly — this is what makes the scheduling work:

| Button | When to use it | What happens |
|---|---|---|
| **Again** | You didn't remember it | Shown again later today, and starts over tomorrow |
| **Hard** | Remembered, but with real effort | Next gap grows a little |
| **Good** | Remembered normally | Next gap grows (1 day → 6 days → ~2 weeks → …) |
| **Easy** | Instant, no effort | Next gap grows the most |

- **New cards per day** (⚙️ on the Study page, default 20) limits how many never-seen cards
  you get each day, so pasting a long article doesn't swamp you. Reviews are never limited.
- A word counts as **Known** once it isn't due for 3+ weeks.
- Every grade is saved immediately, so stopping halfway is fine.

#### 📖 Vocabulary
- Search and filter your words, fix pronunciations or meanings, change domains, or tick 🗑️ to
  delete words.
- **✨ Fill in missing** looks up pinyin/meanings (or romanizations) for words that have none.
- **Export:** download your words as a CSV (can be re-imported), or a full backup of everything
  — worth doing every few weeks.

#### 📊 Dashboard
Your streak, cards due today, known and total words, reviews per day for the last month, and
how your vocabulary splits across domains.

---

#### Tips
- **On your phone:** open the app in your browser and use *Add to Home Screen* so it opens like
  an app.
- **Little and often beats cramming.** A few minutes every day is what the scheduling is built
  around; missed days just mean a bigger pile of reviews next time.
- **Audio** needs an internet connection (it uses Google's free text-to-speech).
"""


def render(language: str):
    st.subheader("👋 Welcome")
    _render_today()
    st.markdown(_GUIDE)
