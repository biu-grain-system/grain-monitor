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
        st.error(f"❌ Secret read error: `{e}`")
        st.stop()

    if not url or url.strip() == "" or "[YOUR-PASSWORD]" in url:
        st.error(
            "❌ **DATABASE_URL is blank or still has `[YOUR-PASSWORD]` in it.**\n\n"
            "Go to Streamlit Cloud → your app → ⋮ → Settings → Secrets\n\n"
            "Paste this (with your real password):\n\n"
            "```\nDATABASE_URL = \"postgresql://postgres:YOURPASSWORD@db.xfdoybhalkpsnaaxamt.supabase.co:5432/postgres\"\n```\n\n"
            f"Current value starts with: `{str(url)[:60]}`"
        )
        st.stop()

    try:
        conn = psycopg2.connect(url)
        return conn
    except Exception as e:
        st.error(
            f"❌ **Connection failed.**\n\n"
            f"URL prefix: `{str(url)[:50]}...`\n\n"
            f"Error: `{e}`"
        )
        st.stop()


# NOTE: No @st.cache_data here — caching hides error messages
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
