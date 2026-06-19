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

## Dashboard Tabs
| Tab | Content |
|-----|---------|
| 📊 Dashboard | KPI cards, alert summary, cargo totals |
| 🏙️ S.Tarawa Analysis | Feb vs May 2026 analysis, est. days, shipments |
| 🏝️ Outer Islands | Heatmaps, bar charts, status table |
| 🚢 Cargo Arrivals | Supplier breakdown per period, upcoming shipping schedule |
| 📈 Annual Report | 2024–2026 monthly incoming grain charts |
| ✏️ Data Entry | Add cargo, stock, analysis, annual, shipping schedule records |
