"""
db.py — Database connection for Kiribati Grain Monitor
Connects to Supabase PostgreSQL via DATABASE_URL secret.
"""

import os
import psycopg2
import psycopg2.extras
import pandas as pd
import streamlit as st


def get_conn():
    """Return a psycopg2 connection using the DATABASE_URL secret."""
    # Try Streamlit secrets first, then environment variable
    url = None
    try:
        url = st.secrets["DATABASE_URL"]
    except Exception:
        pass

    if not url:
        url = os.environ.get("DATABASE_URL")

    if not url:
        st.error(
            "❌ **DATABASE_URL is not set.**\n\n"
            "Go to your Streamlit Cloud app → ⋮ menu → Settings → Secrets "
            "and add:\n\n"
            "```\nDATABASE_URL = \"postgresql://postgres:yourpassword@db.xxxx.supabase.co:5432/postgres\"\n```"
        )
        st.stop()

    try:
        # sslmode is already in the URL from Supabase — don't pass it again
        conn = psycopg2.connect(url)
        return conn
    except psycopg2.OperationalError as e:
        st.error(
            f"❌ **Could not connect to the database.**\n\n"
            f"Check that your DATABASE_URL secret is correct in Streamlit Cloud → Settings → Secrets.\n\n"
            f"Error details: `{e}`"
        )
        st.stop()


@st.cache_data(ttl=30)
def q(sql, params=None):
    """Run a SELECT and return a DataFrame."""
    conn = get_conn()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()
    return df


def run(sql, params=None):
    """Run an INSERT / UPDATE / DELETE."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
    finally:
        conn.close()
