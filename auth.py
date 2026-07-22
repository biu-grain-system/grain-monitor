"""
auth.py — Login portal for the Kiribati BIU Grain Monitoring System

Accounts live in the `app_users` table in the same Supabase database the
app already uses (see sql/003_create_users_table.sql). Passwords are never
stored in plain text — only a bcrypt hash.

To add a user, run tools/hash_password.py locally, then run the printed
INSERT statement in the Supabase SQL editor. See README.md → "Managing
user accounts".
"""

import bcrypt
import streamlit as st
from datetime import datetime, timezone

from db import q_fresh, run


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _fetch_user(username: str):
    df = q_fresh(
        "SELECT id, username, password_hash, full_name, role, is_active "
        "FROM app_users WHERE lower(username) = lower(%s)",
        (username,),
    )
    if df.empty:
        return None
    return df.iloc[0]


def _record_login(user_id: int):
    try:
        run("UPDATE app_users SET last_login = %s WHERE id = %s",
            (datetime.now(timezone.utc), user_id))
    except Exception:
        # Non-critical — never block a login over a logging failure.
        pass


def _render_login_form():
    st.sidebar.image(
        "https://upload.wikimedia.org/wikipedia/commons/d/d3/Flag_of_Kiribati.svg",
        width=150)
    st.title("🌾 Kiribati - MTCIC Grain Monitor")
    st.caption("Cargo Update Information — please sign in to continue")
    st.markdown("---")

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.form("login_form", clear_on_submit=False):
            st.subheader("🔐 Sign in")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("Please enter both a username and password.")
                return

            user = _fetch_user(username.strip())
            if user is None or not user["is_active"]:
                st.error("Invalid username or password.")
                return

            if _verify_password(password, user["password_hash"]):
                st.session_state["auth_user"] = {
                    "id": int(user["id"]),
                    "username": user["username"],
                    "full_name": user["full_name"],
                    "role": user["role"],
                }
                _record_login(int(user["id"]))
                st.rerun()
            else:
                st.error("Invalid username or password.")


def require_login():
    """Call once at the top of app.py. Blocks the rest of the page from
    rendering until someone is signed in."""
    if "auth_user" not in st.session_state:
        _render_login_form()
        st.stop()


def current_user():
    return st.session_state.get("auth_user")


def render_logout_sidebar():
    user = current_user()
    if not user:
        return
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"👤 **{user['full_name'] or user['username']}**  \n"
                         f"<span style='color:#9aa;font-size:.8rem'>{user['role'].title()}</span>",
                         unsafe_allow_html=True)
    if st.sidebar.button("🚪 Log out", use_container_width=True):
        del st.session_state["auth_user"]
        st.rerun()
