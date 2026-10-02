"""
Analytics dashboard — metrics and Plotly charts filtered by the active
language.
"""
from datetime import date, timedelta
from typing import List

import pandas as pd
import plotly.express as px
import streamlit as st

from src.database.queries import (
    count_new_cards_started,
    get_daily_review_counts,
    get_due_cards,
    get_known_word_count,
    get_new_card_limit,
    get_study_dates,
    get_word_counts_by_domain,
)
from src.utils.time_utils import local_today


def current_streak(study_dates: List[str], today: date) -> int:
    """Consecutive days with reviews, ending today — or yesterday, so
    the streak isn't shown as broken before you've studied today."""
    days = {date.fromisoformat(d) for d in study_dates}
    day = today if today in days else today - timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def due_today_count(language: str, today: date) -> int:
    """Reviews due plus new cards still allowed today."""
    t = today.isoformat()
    remaining_new = max(0, get_new_card_limit(language) - count_new_cards_started(language, t))
    return len(get_due_cards(language, t, remaining_new))


def render(language: str):
    st.subheader("📊 Progress Dashboard")
    today = local_today()

    domain_rows = get_word_counts_by_domain(language)
    total_words = sum(r["word_count"] for r in domain_rows)
    streak = current_streak(get_study_dates(language), today)

    m1, m2 = st.columns(2)
    m1.metric("🔥 Streak", f"{streak} day{'s' if streak != 1 else ''}")
    m2.metric("📚 Due today", due_today_count(language, today))
    m3, m4 = st.columns(2)
    m3.metric("✅ Known words", get_known_word_count(language))
    m4.metric("📖 Total words", total_words)

    st.markdown("#### Cards Reviewed per Day (last 30 days)")
    start = today - timedelta(days=29)
    daily_rows = get_daily_review_counts(language, start.isoformat())
    if daily_rows:
        # Plot every day in the window, zero-filled. With only the days
        # that have reviews, Plotly zooms one day's point down to a
        # sub-second axis ("23:59:59.999") and gaps vanish from view.
        counts = {r["study_date"]: r["cards_reviewed"] for r in daily_rows}
        days = [start + timedelta(days=i) for i in range(30)]
        df = pd.DataFrame({"date": days, "cards_reviewed": [counts.get(d.isoformat(), 0) for d in days]})
        fig = px.bar(df, x="date", y="cards_reviewed")
        fig.update_layout(xaxis_title=None, yaxis_title="Cards reviewed", margin=dict(t=10, b=10))
        fig.update_xaxes(tickformat="%b %d", dtick=7 * 24 * 60 * 60 * 1000)  # a label each week
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No reviews logged yet — grade some cards in Study to see your trend here.")

    st.markdown("#### Vocabulary by Domain")
    if domain_rows:
        fig = px.pie(pd.DataFrame(domain_rows), names="domain", values="word_count")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No vocabulary yet — add some words to see the domain breakdown here.")
