"""
db.py — Database connection for Kiribati Grain Monitor
"""

import os
import psycopg2
import pandas as pd
import streamlit as st


def get_conn():
    # Read the secret
    url = None
    try:
        url = st.secrets["DATABASE_URL"]
    except Exception as e:
        st.error(f"❌ Could not read DATABASE_URL from secrets: `{e}`")
        st.stop()

    if not url:
        url = os.environ.get("DATABASE_URL")

    if not url:
        st.error("❌ DATABASE_URL is empty or not set in Streamlit Secrets.")
        st.stop()

    # Show first 40 chars so we can verify format (hides password)
    st.info(f"🔌 Connecting with URL starting: `{url[:40]}...`")

    try:
        conn = psycopg2.connect(url)
        return conn
    except Exception as e:
        st.error(f"❌ Connection failed. Full error:\n\n`{e}`")
        st.stop()


@st.cache_data(ttl=30)
def q(sql, params=None):
    conn = get_conn()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()
    return df


def run(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
    finally:
        conn.close()
