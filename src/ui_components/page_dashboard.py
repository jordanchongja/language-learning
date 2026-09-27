"""
Analytics dashboard — Plotly charts filtered by the active language.
"""
from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from src.database.queries import get_daily_review_counts, get_known_word_count, get_word_counts_by_domain
from src.utils.time_utils import local_today


def render(language: str):
    st.subheader("📊 Progress Dashboard")

    st.metric("Known Words", get_known_word_count(language))

    st.markdown("#### Cards Reviewed per Day (last 30 days)")
    since = (local_today() - timedelta(days=29)).isoformat()
    daily_rows = get_daily_review_counts(language, since)
    if daily_rows:
        df = pd.DataFrame(daily_rows)
        df["study_date"] = pd.to_datetime(df["study_date"])
        fig = px.line(df, x="study_date", y="cards_reviewed", markers=True)
        fig.update_layout(xaxis_title="Date", yaxis_title="Cards Reviewed")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No reviews logged yet — grade some cards in Study to see your trend here.")

    st.markdown("#### Vocabulary by Domain")
    domain_rows = get_word_counts_by_domain(language)
    if domain_rows:
        df = pd.DataFrame(domain_rows)
        fig = px.pie(df, names="domain", values="word_count")
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No vocabulary yet — add some words in Ingestion to see the domain breakdown here.")
