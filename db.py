"""
db.py — Database connection for Kiribati Grain Monitor
Uses a pooled connection (kept alive across reruns) instead of opening a brand
new TLS connection to Supabase on every query — this is the #1 cause of a
Streamlit+Supabase app feeling slow, since each fresh connection costs a
network round-trip + SSL handshake before the query even starts.
"""

import psycopg2
import psycopg2.pool
import pandas as pd
import streamlit as st


@st.cache_resource(show_spinner=False)
def get_pool():
    """One small pool per app process, reused across reruns and users."""
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
        # minconn=1 keeps one connection warm at all times; maxconn=10 is
        # plenty for a small internal reporting tool with a handful of
        # concurrent users.
        return psycopg2.pool.ThreadedConnectionPool(1, 10, url, connect_timeout=10)
    except Exception as e:
        st.error(
            f"❌ **Connection failed.**\n\n"
            f"URL prefix: `{str(url)[:50]}...`\n\n"
            f"Error: `{e}`"
        )
        st.stop()


def _get_conn():
    return get_pool().getconn()


def _put_conn(conn):
    try:
        get_pool().putconn(conn)
    except Exception:
        pass


@st.cache_data(ttl=300, show_spinner=False)
def q(sql, params=None):
    """Cached read query. Cache is cleared by run() whenever data changes,
    so results are always fresh right after an edit, and fast otherwise."""
    conn = _get_conn()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        _put_conn(conn)
    return df


def q_fresh(sql, params=None):
    """Uncached read — use for anything security-sensitive (e.g. login
    lookups) where a stale cached row would be a problem."""
    conn = _get_conn()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        _put_conn(conn)
    return df


def run(sql, params=None):
    """Write query. Clears the read cache so every user immediately sees
    the change on their next rerun."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)
    q.clear()
