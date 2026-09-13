"""
Analytics dashboard — Plotly charts filtered by the active language.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from src.database.queries import get_daily_review_counts, get_known_word_count, get_word_counts_by_domain


def render(language: str):
    st.subheader("📊 Progress Dashboard")

    st.metric("Known Words", get_known_word_count(language))

    st.markdown("#### Cards Reviewed per Day (last 30 days)")
    daily_rows = get_daily_review_counts(language, days=30)
    if daily_rows:
        df = pd.DataFrame([dict(r) for r in daily_rows])
        df["study_date"] = pd.to_datetime(df["study_date"])
        fig = px.line(df, x="study_date", y="cards_reviewed", markers=True)
        fig.update_layout(xaxis_title="Date", yaxis_title="Cards Reviewed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No study sessions logged yet — complete a quiz in Study to see your trend here.")

    st.markdown("#### Vocabulary by Domain")
    domain_rows = get_word_counts_by_domain(language)
    if domain_rows:
        df = pd.DataFrame([dict(r) for r in domain_rows])
        fig = px.pie(df, names="domain", values="word_count")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No vocabulary yet — add some words in Ingestion to see the domain breakdown here.")
