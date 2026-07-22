"""
hash_password.py — generate a login account for the Grain Monitoring System

Run this on your own computer (NOT on Streamlit Cloud), e.g.:

    pip install bcrypt
    python tools/hash_password.py

It will ask for a username, full name, role, and password, then print a
ready-to-run SQL statement. Copy that statement into the Supabase SQL editor
to create (or update) the account. Your plain-text password is never sent
anywhere or saved to disk — only the hash is.
"""

import getpass
import bcrypt


def main():
    print("=== Create / update a Grain Monitor login ===\n")
    username = input("Username: ").strip()
    full_name = input("Full name: ").strip()

    print("\nAccess levels:")
    print("  admin       — full access, including Data Entry")
    print("  data_entry  — same as admin, including Data Entry")
    print("  viewer      — reporting tabs only, Data Entry tab hidden")
    role = input("Role [admin/data_entry/viewer] (default: viewer): ").strip() or "viewer"
    if role not in ("admin", "data_entry", "viewer"):
        print(f"\n❌ '{role}' is not a valid role. Use admin, data_entry, or viewer.")
        return

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("\n❌ Passwords did not match. Please run the script again.")
        return
    if len(password) < 8:
        print("\n❌ Please use a password of at least 8 characters.")
        return

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    print("\n✅ Run this in the Supabase SQL editor:\n")
    print(
        "INSERT INTO app_users (username, password_hash, full_name, role)\n"
        f"VALUES ('{username}', '{hashed}', '{full_name}', '{role}')\n"
        "ON CONFLICT (username) DO UPDATE\n"
        "SET password_hash = EXCLUDED.password_hash,\n"
        "    full_name = EXCLUDED.full_name,\n"
        "    role = EXCLUDED.role;\n"
    )


if __name__ == "__main__":
    main()
