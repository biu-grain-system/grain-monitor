# 🌾 Kiribati BIU Grain Monitoring System

Built from `cargo_update_June_2026.xlsx` — Ministry of Commerce, Industry & Cooperatives, Kiribati.

## Data Covered
| Sheet | Content |
|-------|---------|
| Analysis Data (2) | S.Tarawa cargo & analysis — February 2026 |
| Analysis Data | S.Tarawa cargo & analysis — May 2026 |
| Outer Island stock | 23 outer island stock levels |
| Graph Report | Annual incoming grains 2024–2026 |
| Cargo to outer islands | Cargo dispatched to islands |

## Commodities
- **Rice** — 18.14 kg/bag
- **Sugar** — 25 kg/bag
- **Flour** — 25 kg/bag

## Setup

```bash
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Build database
python build_db.py

# 3. Run the app
python -m streamlit run app.py
```

Opens at **http://localhost:8501**

## 🔐 Login Portal

The app now requires signing in before any data is shown. Accounts are
stored in a new `app_users` table in your Supabase database (same DB the
app already uses via `DATABASE_URL`) — passwords are never stored in plain
text, only a bcrypt hash.

**Access levels:**
| Role | Reporting tabs (Dashboard, Analysis, Islands, Cargo, Annual Report) | ✏️ Data Entry tab |
|------|---|---|
| `admin` | ✅ | ✅ |
| `data_entry` | ✅ | ✅ |
| `viewer` | ✅ | 🚫 hidden entirely — not just disabled |

**One-time setup:**
1. In Supabase → your project → **SQL Editor**, run `sql/003_create_users_table.sql`.
2. On your own computer (not Streamlit Cloud), run:
   ```bash
   pip install bcrypt
   python tools/hash_password.py
   ```
   Answer the prompts (username, full name, role, password). Choose the
   role that matches what that person should be able to do. It prints an
   `INSERT` statement — copy/paste it into the Supabase SQL editor and run
   it. That creates your first login (make this one `admin`).
3. Repeat step 2 for each additional staff member who needs access.

**Managing user accounts:** to change someone's password, re-run
`tools/hash_password.py` with the same username — the `ON CONFLICT` clause
updates the existing account instead of creating a duplicate. To disable an
account without deleting it, run:
```sql
UPDATE app_users SET is_active = FALSE WHERE username = 'someuser';
```

## ⚡ Performance

Previously the app opened a brand-new connection to Supabase for *every*
query, which is the main reason it felt slow — each one pays a network
round-trip + SSL handshake before the query even runs. It now keeps a small
pool of warm connections open (`db.py`) and caches read queries for 5
minutes, clearing the cache automatically the moment any data is added or
edited so nobody ever sees stale numbers after a change.

## Dashboard Tabs
| Tab | Content |
|-----|---------|
| 📊 Dashboard | KPI cards, alert summary, cargo totals |
| 🏙️ S.Tarawa Analysis | Feb vs May 2026 analysis, est. days, shipments |
| 🏝️ Outer Islands | Heatmaps, bar charts, status table |
| 🚢 Cargo Arrivals | Supplier breakdown per period, upcoming shipping schedule |
| 📈 Annual Report | 2024–2026 monthly incoming grain charts |
| ✏️ Data Entry | Add cargo, stock, analysis, annual, shipping schedule records |
