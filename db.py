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
    url = os.environ.get("DATABASE_URL") or st.secrets.get("DATABASE_URL")
    if not url:
        st.error("❌ DATABASE_URL secret is not set. Please add it in Streamlit Cloud → Settings → Secrets.")
        st.stop()
    return psycopg2.connect(url, sslmode="require")

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
