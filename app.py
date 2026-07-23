"""
app.py — Kiribati Grain Monitoring System
Database: Supabase PostgreSQL (persistent)
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from db import q, run
from auth import require_login, render_logout_sidebar, current_user

st.set_page_config(
    page_title="MTCIC-BIU Grain Monitor",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Block everything below until the user signs in.
require_login()

# ── colours ───────────────────────────────────────────────────────────────────
COMM_COL = {"Rice": "#e67e22", "Sugar": "#2ecc71", "Flour": "#3498db"}
STATUS_COL = {
    "OKAY": "#27ae60", "LOW": "#f39c12", "CRITICAL": "#e74c3c",
    "CRISIS": "#c0392b", "EMPTY": "#8e44ad", "NO DATA": "#7f8c8d",
}

def status_badge(s):
    c = STATUS_COL.get(s, "#7f8c8d")
    return (f'<span style="background:{c};color:white;padding:2px 8px;'
            f'border-radius:4px;font-size:.75rem;font-weight:700">{s}</span>')

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
[data-testid="stMetricValue"]{font-size:1.5rem!important}
.kcard{background:#1e2a3a;border-radius:10px;padding:.9rem 1.1rem;
       border-left:4px solid #e67e22;margin-bottom:.5rem}
.note{background:#2c3e50;border-radius:8px;padding:.6rem 1rem;
      font-size:.8rem;color:#aab;margin-bottom:.8rem}
.section-title{font-size:1.1rem;font-weight:700;color:#e67e22;
               margin:1rem 0 .4rem}

/* Give the sidebar a bit more room so period names never get clipped */
section[data-testid="stSidebar"]{ width: 340px !important; }
section[data-testid="stSidebar"] > div:first-child{ width: 340px !important; }

/* Stop the closed Report Period box from truncating text with "..." */
section[data-testid="stSidebar"] [data-baseweb="select"] > div{
    white-space: normal !important;
    height: auto !important;
    min-height: 2.6rem;
}
section[data-testid="stSidebar"] [data-baseweb="select"] span{
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: unset !important;
}

/* Let the open dropdown list grow tall enough to show every period
   without needing to scroll for a handful of items */
ul[role="listbox"]{
    max-height: 320px !important;
}
ul[role="listbox"] li{
    white-space: normal !important;
}
</style>""", unsafe_allow_html=True)

# ── island_status helper (replaces SQLite VIEW) ───────────────────────────────
ISLAND_STATUS_SQL = """
SELECT
    island, commodity, stock_bags, daily_quota, est_days,
    data_date, last_date,
    CASE
        WHEN LOWER(comments) LIKE '%crisis%'     THEN 'CRISIS'
        WHEN LOWER(comments) LIKE '%not enough%' THEN 'LOW'
        WHEN LOWER(comments) LIKE '%finish%'     THEN 'EMPTY'
        WHEN est_days = 0                         THEN 'NO DATA'
        WHEN est_days < 10                        THEN 'CRITICAL'
        WHEN est_days < 20                        THEN 'LOW'
        ELSE 'OKAY'
    END AS status
FROM outer_island_stock
"""

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
st.sidebar.image(
    "https://upload.wikimedia.org/wikipedia/commons/d/d3/Flag_of_Kiribati.svg",
    width=150)
st.sidebar.title("🌾 Kiribati - MTCIC Grain Monitor")
st.sidebar.caption("Cargo Update Information")
st.sidebar.markdown("---")
st.sidebar.markdown("""**Commodities**
- 🟠 Rice — 18.14 kg/bag
- 🟢 Sugar — 25 kg/bag
- 🔵 Flour — 25 kg/bag
""")
render_logout_sidebar()
st.sidebar.markdown("---")

# Pull the list of report periods straight from the data (was hardcoded before,
# so newly entered months like "June 2026" never showed up in this dropdown).
_month_rows = q("""
    SELECT report_month FROM s_tarawa_analysis
    UNION
    SELECT report_month FROM cargo_arrivals
""")

def _month_sort_key(m):
    try:
        return datetime.strptime(m, "%B %Y")
    except Exception:
        return datetime.min

_available_months = sorted(_month_rows["report_month"].dropna().unique().tolist(), key=_month_sort_key)
report_months = ["All"] + _available_months
sel_month = st.sidebar.selectbox("Report Period", report_months)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
_role = (current_user() or {}).get("role", "viewer")
_can_edit = _role in ("admin", "data_entry")  # viewers never get the Data Entry tab

if _can_edit:
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard", "🏙️ S.Tarawa Analysis", "🏝️ Outer Islands",
        "🚢 Cargo Arrivals", "📈 Annual Report", "✏️ Data Entry",
    ])
else:
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard", "🏙️ S.Tarawa Analysis", "🏝️ Outer Islands",
        "🚢 Cargo Arrivals", "📈 Annual Report",
    ])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.title("🌾 Kiribati - MTCIC Grain Monitoring System")
    st.markdown("**Source:** cargo_update &nbsp;|&nbsp; Ministry of Tourism, Commerce, Industry & Cooperatives, Kiribati")
    st.markdown("---")

    # Determine which S.Tarawa report month to show: respect the sidebar filter,
    # otherwise fall back to the latest month actually on record (was hardcoded to "May 2026").
    if sel_month != "All":
        dash_sta_month = sel_month
    else:
        latest_month_row = q("SELECT report_month FROM s_tarawa_analysis ORDER BY report_date DESC LIMIT 1")
        dash_sta_month = latest_month_row.iloc[0]["report_month"] if not latest_month_row.empty else None

    st.markdown(
        f'<div class="section-title">📦 S.Tarawa Current Stock — {dash_sta_month or "No data"}</div>',
        unsafe_allow_html=True)
    latest_sta = q("""
        SELECT commodity, total_stock, quota_daily, est_days, last_date, comments
        FROM s_tarawa_analysis WHERE report_month=%s
    """, (dash_sta_month,)) if dash_sta_month else pd.DataFrame()

    cols = st.columns(3)
    for i, row in latest_sta.iterrows():
        col = COMM_COL.get(row["commodity"], "#aaa")
        with cols[i]:
            st.markdown(f"""<div class="kcard" style="border-left-color:{col}">
            <div style="color:#aab;font-size:.8rem">{row['commodity']}</div>
            <div style="font-size:1.5rem;font-weight:700;color:{col}">{int(row['total_stock']):,} bags</div>
            <div style="font-size:.78rem;color:#ccc">Est. days: <b>{row['est_days']:.1f}</b> &nbsp;|&nbsp; Last to: <b>{row['last_date']}</b></div>
            <div style="font-size:.75rem;color:#aab">Daily quota: {int(row['quota_daily']):,} bags/day</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-title">🏝️ Outer Island Alert Summary</div>', unsafe_allow_html=True)
    oi_status = q(ISLAND_STATUS_SQL + " ORDER BY island, commodity")

    status_counts = oi_status["status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]

    col_a, col_b = st.columns([1, 2])
    with col_a:
        for _, row in status_counts.iterrows():
            colour = STATUS_COL.get(row["Status"], "#aaa")
            st.markdown(f"""<div style="display:flex;align-items:center;gap:.6rem;margin:.3rem 0">
            <span style="background:{colour};color:white;padding:2px 10px;border-radius:4px;
                font-weight:700;font-size:.8rem">{row['Status']}</span>
            <span style="font-size:1.1rem;font-weight:700">{row['Count']}</span>
            <span style="color:#aab;font-size:.8rem">island-commodity records</span>
            </div>""", unsafe_allow_html=True)
    with col_b:
        fig_s = px.bar(status_counts, x="Status", y="Count", color="Status",
                       color_discrete_map=STATUS_COL, template="plotly_dark",
                       height=260, title="Outer Island Stock Status")
        fig_s.update_layout(showlegend=False, margin=dict(t=40, b=10))
        st.plotly_chart(fig_s, use_container_width=True)

    crisis = oi_status[oi_status["status"].isin(["CRISIS", "CRITICAL", "EMPTY", "LOW"])]
    if not crisis.empty:
        st.markdown('<div class="section-title">⚠️ Islands Needing Attention</div>', unsafe_allow_html=True)
        for _, row in crisis.iterrows():
            st.markdown(
                f'&nbsp;&nbsp;{status_badge(row["status"])} &nbsp; '
                f'<b>{row["island"]}</b> — {row["commodity"]} &nbsp; '
                f'({int(row["stock_bags"]):,} bags, {row["est_days"]:.1f} days left)',
                unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-title">🚢 Total Cargo Received by Period</div>', unsafe_allow_html=True)
    cargo_summary = q("""
        SELECT report_month,
               SUM(rice_bags) AS rice_bags, SUM(sugar_bags) AS sugar_bags, SUM(flour_bags) AS flour_bags
        FROM cargo_arrivals GROUP BY report_month
    """)
    cargo_m = cargo_summary.melt("report_month", var_name="Commodity", value_name="Bags")
    cargo_m["Commodity"] = cargo_m["Commodity"].str.replace("_bags", "").str.title()
    fig_c = px.bar(cargo_m, x="report_month", y="Bags", color="Commodity",
                   color_discrete_map={"Rice": COMM_COL["Rice"], "Sugar": COMM_COL["Sugar"], "Flour": COMM_COL["Flour"]},
                   barmode="group", template="plotly_dark", height=320,
                   labels={"report_month": "Period"},
                   title="Total Bags Received per Shipment Period")
    fig_c.update_layout(margin=dict(t=40, b=10))
    st.plotly_chart(fig_c, use_container_width=True)

    # ── Linked summary: Upcoming Shipping Schedule (brief) ──────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">🗓️ Next Shipments (Upcoming Schedule)</div>', unsafe_allow_html=True)
    dash_sched = q("""
        SELECT shipping_agency, vessel_name, eta_date, commodity, qty_bags, status
        FROM shipping_schedule WHERE status NOT IN ('Arrived','Cancelled')
        ORDER BY eta_date LIMIT 3
    """)
    if dash_sched.empty:
        st.info("No upcoming shipments scheduled. Add one in the ✏️ Data Entry tab.")
    else:
        sc1, sc2, sc3 = st.columns(3)
        for col, (_, r) in zip([sc1, sc2, sc3], dash_sched.iterrows()):
            with col:
                st.markdown(f"""<div class="kcard" style="border-left-color:#3498db">
                <div style="color:#aab;font-size:.8rem">{r['shipping_agency']} — {r['vessel_name'] or 'TBA'}</div>
                <div style="font-size:1.1rem;font-weight:700;color:#3498db">ETA: {r['eta_date']}</div>
                <div style="font-size:.78rem;color:#ccc">{r['commodity'] or '—'} — {int(r['qty_bags']):,} bags</div>
                <div style="margin-top:.3rem">{status_badge(r['status'])}</div>
                </div>""", unsafe_allow_html=True)
        st.caption("See the full schedule in the 🚢 Cargo Arrivals tab.")

    # ── Linked summary: Cargo Dispatched to Outer Islands (brief) ───────────
    st.markdown("---")
    st.markdown('<div class="section-title">🏝️ Cargo Dispatched to Outer Islands (Totals)</div>', unsafe_allow_html=True)
    dash_coi = q("SELECT rice_bags, sugar_bags, flour_bags FROM cargo_outer_islands")
    if dash_coi.empty:
        st.info("No dispatch records yet.")
    else:
        dc1, dc2, dc3 = st.columns(3)
        for col, label, val, colour in [
            (dc1, "Rice", int(dash_coi["rice_bags"].sum()), COMM_COL["Rice"]),
            (dc2, "Sugar", int(dash_coi["sugar_bags"].sum()), COMM_COL["Sugar"]),
            (dc3, "Flour", int(dash_coi["flour_bags"].sum()), COMM_COL["Flour"]),
        ]:
            with col:
                st.markdown(f"""<div class="kcard" style="border-left-color:{colour}">
                <div style="color:#aab;font-size:.8rem">{label} dispatched</div>
                <div style="font-size:1.4rem;font-weight:700;color:{colour}">{val:,} bags</div>
                </div>""", unsafe_allow_html=True)
        st.caption("Full island-by-island breakdown in the 🏝️ Outer Islands tab.")

    # ── Linked summary: Annual Trend Snapshot ────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">📈 Annual Trend Snapshot</div>', unsafe_allow_html=True)
    dash_annual = q("SELECT year, rice_bags, sugar_bags, flour_bags FROM annual_incoming")
    if dash_annual.empty:
        st.info("No annual data yet.")
    else:
        yr_tot = dash_annual.groupby("year").agg(
            Rice=("rice_bags", "sum"), Sugar=("sugar_bags", "sum"), Flour=("flour_bags", "sum")
        ).reset_index()
        yr_tot["Total"] = yr_tot["Rice"] + yr_tot["Sugar"] + yr_tot["Flour"]
        yr_tot = yr_tot.sort_values("year")
        cur_yr = yr_tot.iloc[-1]
        ac1, ac2 = st.columns([1, 2])
        with ac1:
            delta = None
            if len(yr_tot) > 1:
                prev_total = yr_tot.iloc[-2]["Total"]
                delta = f"{cur_yr['Total'] - prev_total:+,.0f} bags vs {int(yr_tot.iloc[-2]['year'])}"
            st.metric(f"{int(cur_yr['year'])} Total Incoming", f"{int(cur_yr['Total']):,} bags", delta)
        with ac2:
            yr_m = yr_tot.melt("year", ["Rice", "Sugar", "Flour"], var_name="Commodity", value_name="Bags")
            fig_yr_mini = px.bar(yr_m, x="year", y="Bags", color="Commodity",
                                 color_discrete_map={"Rice": COMM_COL["Rice"], "Sugar": COMM_COL["Sugar"], "Flour": COMM_COL["Flour"]},
                                 template="plotly_dark", height=220, labels={"year": "Year"})
            fig_yr_mini.update_layout(margin=dict(t=10, b=10), showlegend=True)
            st.plotly_chart(fig_yr_mini, use_container_width=True)
        st.caption("Full monthly breakdown in the 📈 Annual Report tab.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — S.TARAWA ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("🏙️ South Tarawa Grain Analysis")
    month_f = sel_month if sel_month != "All" else None
    if month_f:
        sta = q("SELECT * FROM s_tarawa_analysis WHERE report_month=%s ORDER BY commodity", (month_f,))
    else:
        sta = q("SELECT * FROM s_tarawa_analysis ORDER BY report_month, commodity")

    if sta.empty:
        st.info("No data for selected period.")
    else:
        for period in sta["report_month"].unique():
            st.markdown(f'<div class="section-title">📅 {period}</div>', unsafe_allow_html=True)
            sub = sta[sta["report_month"] == period]
            cols = st.columns(3)
            for i, (_, row) in enumerate(sub.iterrows()):
                col = COMM_COL.get(row["commodity"], "#aaa")
                with cols[i % 3]:
                    st.markdown(f"""<div class="kcard" style="border-left-color:{col}">
                    <div style="color:#aab;font-size:.8rem">{row['commodity']} ({row['unit_kg']} kg/bag)</div>
                    <div style="font-size:1.4rem;font-weight:700;color:{col}">{int(row['total_stock']):,} bags</div>
                    <div style="font-size:.78rem;color:#ccc;margin-top:.3rem">
                      Manifest: <b>{int(row['manifest_bags']):,}</b> bags incoming<br>
                      Remaining stock: <b>{int(row['remaining_stock']):,}</b> bags<br>
                      Daily quota: <b>{int(row['quota_daily']):,}</b> bags/day<br>
                      Est. days: <b>{row['est_days']:.1f}</b> days<br>
                      Last date: <b>{row['last_date']}</b>
                    </div>
                    <div style="margin-top:.4rem;font-size:.75rem;color:#27ae60">{row['comments']}</div>
                    </div>""", unsafe_allow_html=True)

        if len(sta["report_month"].unique()) > 1:
            st.markdown("---")
            st.subheader("Feb 2026 vs May 2026 — Total Stock Comparison")
            fig_comp = px.bar(sta, x="commodity", y="total_stock", color="report_month",
                              barmode="group", template="plotly_dark", height=350,
                              labels={"total_stock": "Total Stock (bags)", "commodity": "Commodity", "report_month": "Period"},
                              color_discrete_sequence=["#3498db", "#e67e22"],
                              title="S.Tarawa Total Stock: February vs May 2026")
            st.plotly_chart(fig_comp, use_container_width=True)

            fig_days = px.bar(sta, x="commodity", y="est_days", color="report_month",
                              barmode="group", template="plotly_dark", height=320,
                              labels={"est_days": "Estimated Days", "commodity": "Commodity", "report_month": "Period"},
                              color_discrete_sequence=["#3498db", "#e67e22"])
            fig_days.add_hline(y=30, line_dash="dot", line_color="white", annotation_text="30-day threshold")
            st.plotly_chart(fig_days, use_container_width=True)

        st.markdown("---")
        st.subheader("Detailed Analysis Table")
        disp = sta[["report_month", "commodity", "manifest_bags", "remaining_stock",
                    "total_stock", "quota_daily", "est_days", "last_date", "comments"]].copy()
        disp.columns = ["Period", "Commodity", "Manifest (bags)", "Remaining Stock",
                        "Total Stock", "Daily Quota", "Est. Days", "Last Date", "Status"]
        st.dataframe(disp, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — OUTER ISLANDS
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("🏝️ Outer Islands Stock Status")
    oi = q(ISLAND_STATUS_SQL + " ORDER BY island, commodity")
    islands_list = sorted(oi["island"].unique())

    col_filter1, col_filter2 = st.columns(2)
    sel_isl = col_filter1.multiselect("Filter Islands", islands_list, default=islands_list)
    sel_sta = col_filter2.multiselect("Filter Status",
        ["OKAY", "LOW", "CRITICAL", "CRISIS", "EMPTY", "NO DATA"],
        default=["OKAY", "LOW", "CRITICAL", "CRISIS", "EMPTY", "NO DATA"])

    oi_f = oi[oi["island"].isin(sel_isl) & oi["status"].isin(sel_sta)]

    st.markdown("---")
    st.subheader("Stock Bags by Island & Commodity")
    if not oi_f.empty:
        pivot = oi_f.pivot_table(index="island", columns="commodity", values="stock_bags", aggfunc="sum").fillna(0)
        fig_h = px.imshow(pivot, color_continuous_scale="YlOrRd_r",
                          labels={"color": "Stock (bags)"}, template="plotly_dark",
                          aspect="auto", height=560, title="Current Stock Bags per Island")
        fig_h.update_xaxes(side="top")
        st.plotly_chart(fig_h, use_container_width=True)

    st.subheader("Estimated Days Remaining")
    if not oi_f.empty:
        pivot_d = oi_f.pivot_table(index="island", columns="commodity", values="est_days", aggfunc="mean").fillna(0)
        fig_hd = px.imshow(pivot_d, color_continuous_scale="RdYlGn", zmin=0, zmax=60,
                           labels={"color": "Est. Days"}, template="plotly_dark",
                           aspect="auto", height=560, title="Estimated Days of Stock Remaining")
        fig_hd.update_xaxes(side="top")
        st.plotly_chart(fig_hd, use_container_width=True)

    st.markdown("---")
    for comm in ["Rice", "Sugar", "Flour"]:
        sub = oi_f[oi_f["commodity"] == comm].sort_values("stock_bags", ascending=True)
        if sub.empty:
            continue
        sub = sub.copy()
        sub["colour"] = sub["status"].map(STATUS_COL)
        fig_b = go.Figure(go.Bar(
            x=sub["stock_bags"], y=sub["island"], orientation="h",
            marker_color=sub["colour"],
            text=sub["stock_bags"].apply(lambda x: f"{int(x):,}"),
            textposition="outside",
        ))
        fig_b.update_layout(
            title=f"{comm} — Stock Bags per Island", xaxis_title="Bags",
            template="plotly_dark", height=max(300, len(sub) * 26),
            margin=dict(t=50, b=10, r=80, l=120))
        st.plotly_chart(fig_b, use_container_width=True)

    st.markdown("---")
    st.subheader("Full Outer Island Table")
    oi_disp = oi_f[["island", "commodity", "stock_bags", "daily_quota", "est_days",
                     "data_date", "last_date", "status"]].copy()
    oi_disp.columns = ["Island", "Commodity", "Stock (bags)", "Daily Quota",
                       "Est. Days", "Data Date", "Last Date", "Status"]

    def colour_status(val):
        c = STATUS_COL.get(val, "")
        return f"background-color:{c};color:white;font-weight:bold" if c else ""

    st.dataframe(oi_disp.style.map(colour_status, subset=["Status"]),
                 use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download CSV", oi_disp.to_csv(index=False),
                       "outer_island_stock.csv", "text/csv")

    st.markdown("---")
    st.subheader("📦 Cargo Dispatched to Outer Islands")
    coi = q("SELECT island, rice_bags, sugar_bags, flour_bags FROM cargo_outer_islands ORDER BY island")
    coi_m = coi.melt("island", var_name="Commodity", value_name="Bags")
    coi_m["Commodity"] = coi_m["Commodity"].str.replace("_bags", "").str.title()
    coi_nz = coi_m[coi_m["Bags"] > 0]
    if not coi_nz.empty:
        fig_coi = px.bar(coi_nz, x="island", y="Bags", color="Commodity",
                         color_discrete_map={"Rice": COMM_COL["Rice"], "Sugar": COMM_COL["Sugar"], "Flour": COMM_COL["Flour"]},
                         template="plotly_dark", height=300, title="Bags Dispatched to Outer Islands")
        st.plotly_chart(fig_coi, use_container_width=True)
    else:
        st.info("No cargo dispatched to outer islands in current record.")
    st.dataframe(coi, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — CARGO ARRIVALS
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("🚢 Cargo Arrivals by Supplier")

    if sel_month != "All":
        cargo = q("""
            SELECT ca.report_month, ca.report_date, s.name AS supplier,
                   ca.rice_fcl, ca.rice_bags, ca.sugar_fcl, ca.sugar_bags,
                   ca.flour_fcl, ca.flour_bags
            FROM cargo_arrivals ca JOIN suppliers s ON s.id=ca.supplier_id
            WHERE ca.report_month=%s ORDER BY ca.report_month, s.name
        """, (sel_month,))
    else:
        cargo = q("""
            SELECT ca.report_month, ca.report_date, s.name AS supplier,
                   ca.rice_fcl, ca.rice_bags, ca.sugar_fcl, ca.sugar_bags,
                   ca.flour_fcl, ca.flour_bags
            FROM cargo_arrivals ca JOIN suppliers s ON s.id=ca.supplier_id
            ORDER BY ca.report_month, s.name
        """)

    if cargo.empty:
        st.info("No cargo records for selected period.")
    else:
        totals = cargo.groupby("report_month").agg(
            rice_bags=("rice_bags", "sum"), sugar_bags=("sugar_bags", "sum"),
            flour_bags=("flour_bags", "sum"), rice_fcl=("rice_fcl", "sum"),
            sugar_fcl=("sugar_fcl", "sum"), flour_fcl=("flour_fcl", "sum"),
        ).reset_index()

        for _, t in totals.iterrows():
            st.markdown(f'<div class="section-title">📅 {t["report_month"]} — Totals</div>', unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            for col, label, bags, fcl, colour in [
                (c1, "Rice (18.14 kg/bag)", t["rice_bags"], t["rice_fcl"], COMM_COL["Rice"]),
                (c2, "Sugar (25 kg/bag)", t["sugar_bags"], t["sugar_fcl"], COMM_COL["Sugar"]),
                (c3, "Flour (25 kg/bag)", t["flour_bags"], t["flour_fcl"], COMM_COL["Flour"]),
            ]:
                with col:
                    st.markdown(f"""<div class="kcard" style="border-left-color:{colour}">
                    <div style="color:#aab;font-size:.8rem">{label}</div>
                    <div style="font-size:1.4rem;font-weight:700;color:{colour}">{int(bags):,} bags</div>
                    <div style="font-size:.78rem;color:#ccc">{int(fcl)} FCL containers</div>
                    </div>""", unsafe_allow_html=True)

        st.markdown("---")
        for period in cargo["report_month"].unique():
            sub = cargo[cargo["report_month"] == period]
            st.subheader(f"Supplier Breakdown — {period}")
            c1, c2 = st.columns(2)
            with c1:
                rice_sup = sub[sub["rice_bags"] > 0].sort_values("rice_bags", ascending=True)
                if not rice_sup.empty:
                    fig = px.bar(rice_sup, x="rice_bags", y="supplier", orientation="h",
                                 color_discrete_sequence=[COMM_COL["Rice"]], template="plotly_dark",
                                 height=max(200, len(rice_sup) * 35), title="Rice (bags by supplier)",
                                 labels={"rice_bags": "Bags", "supplier": "Supplier"})
                    fig.update_layout(margin=dict(t=40, b=10, l=10, r=10))
                    st.plotly_chart(fig, use_container_width=True, key=f"rice_{period}")
            with c2:
                sug_sup = sub[sub["sugar_bags"] > 0].sort_values("sugar_bags", ascending=True)
                if not sug_sup.empty:
                    fig2 = px.bar(sug_sup, x="sugar_bags", y="supplier", orientation="h",
                                  color_discrete_sequence=[COMM_COL["Sugar"]], template="plotly_dark",
                                  height=max(200, len(sug_sup) * 35), title="Sugar (bags by supplier)",
                                  labels={"sugar_bags": "Bags", "supplier": "Supplier"})
                    fig2.update_layout(margin=dict(t=40, b=10, l=10, r=10))
                    st.plotly_chart(fig2, use_container_width=True, key=f"sugar_{period}")

            flour_sup = sub[sub["flour_bags"] > 0].sort_values("flour_bags", ascending=True)
            if not flour_sup.empty:
                fig3 = px.bar(flour_sup, x="flour_bags", y="supplier", orientation="h",
                              color_discrete_sequence=[COMM_COL["Flour"]], template="plotly_dark",
                              height=max(200, len(flour_sup) * 35), title="Flour (bags by supplier)",
                              labels={"flour_bags": "Bags", "supplier": "Supplier"})
                fig3.update_layout(margin=dict(t=40, b=10, l=10, r=10))
                st.plotly_chart(fig3, use_container_width=True, key=f"flour_{period}")
            else:
                st.caption("No flour records for this period yet.")

        st.markdown("---")
        st.subheader("Full Cargo Table")
        disp = cargo.rename(columns={
            "report_month": "Period", "report_date": "Date", "supplier": "Supplier",
            "rice_fcl": "Rice FCL", "rice_bags": "Rice Bags",
            "sugar_fcl": "Sugar FCL", "sugar_bags": "Sugar Bags",
            "flour_fcl": "Flour FCL", "flour_bags": "Flour Bags"})
        st.dataframe(disp, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download CSV", disp.to_csv(index=False), "cargo_arrivals.csv", "text/csv")

    # Shipping Schedule
    st.markdown("---")
    st.markdown('<div class="section-title">🗓️ Upcoming Shipping Schedule</div>', unsafe_allow_html=True)
    sched = q("""
        SELECT shipping_agency, vessel_name, voyage_no, origin_port, destination_port,
               etd_date, eta_date, commodity, qty_bags, qty_fcl, status, remarks
        FROM shipping_schedule WHERE status NOT IN ('Arrived','Cancelled') ORDER BY eta_date
    """)

    if sched.empty:
        st.info("No upcoming shipments scheduled.")
    else:
        STATUS_SCHED_COL = {"Scheduled": "#3498db", "In Transit": "#f39c12",
                             "Delayed": "#e74c3c", "Arrived": "#27ae60", "Cancelled": "#7f8c8d"}
        for _, r in sched.iterrows():
            colour = STATUS_SCHED_COL.get(r["status"], "#aaa")
            st.markdown(f"""<div class="kcard" style="border-left-color:{colour}">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <div><b>{r['shipping_agency']}</b> &nbsp;—&nbsp; {r['vessel_name'] or 'TBA'} ({r['voyage_no'] or '—'})</div>
                {status_badge(r['status'])}
            </div>
            <div style="font-size:.82rem;color:#ccc;margin-top:.3rem">
                {r['origin_port'] or '—'} → {r['destination_port'] or '—'} &nbsp;|&nbsp;
                ETD: <b>{r['etd_date'] or '—'}</b> &nbsp;|&nbsp; ETA: <b>{r['eta_date']}</b>
            </div>
            <div style="font-size:.8rem;color:#aab;margin-top:.2rem">
                {r['commodity'] or '—'} — {int(r['qty_bags']):,} bags / {int(r['qty_fcl'])} FCL
                {f" &nbsp;|&nbsp; {r['remarks']}" if r['remarks'] else ""}
            </div>
            </div>""", unsafe_allow_html=True)

        disp_sched = sched.rename(columns={
            "shipping_agency": "Shipping Agency", "vessel_name": "Vessel", "voyage_no": "Voyage No",
            "origin_port": "Origin", "destination_port": "Destination", "etd_date": "ETD",
            "eta_date": "ETA", "commodity": "Commodity", "qty_bags": "Qty (Bags)",
            "qty_fcl": "Qty (FCL)", "status": "Status", "remarks": "Remarks"})
        st.dataframe(disp_sched, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download CSV", disp_sched.to_csv(index=False), "shipping_schedule.csv", "text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — ANNUAL REPORT
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("📈 Annual Incoming Grains Report")
    annual = q("SELECT * FROM annual_incoming ORDER BY year, id")

    sel_years = st.multiselect("Select Years", [2024, 2025, 2026], default=[2024, 2025])
    annual_f = annual[annual["year"].isin(sel_years)]

    if not annual_f.empty:
        annual_m = annual_f.melt(["year", "month", "id"], var_name="Commodity", value_name="Bags")
        annual_m["Commodity"] = annual_m["Commodity"].str.replace("_bags", "").str.title()
        annual_m["Period"] = annual_m["year"].astype(str) + " " + annual_m["month"]

        fig_line = px.line(annual_m[annual_m["Bags"] > 0],
                           x="Period", y="Bags", color="Commodity",
                           color_discrete_map={"Rice": COMM_COL["Rice"], "Sugar": COMM_COL["Sugar"], "Flour": COMM_COL["Flour"]},
                           markers=True, template="plotly_dark", height=420,
                           title="Monthly Incoming Grains (bags)")
        fig_line.update_layout(margin=dict(t=50, b=20), xaxis_tickangle=-45)
        st.plotly_chart(fig_line, use_container_width=True)

        st.subheader("Annual Totals")
        ann_tot = annual_f.groupby("year").agg(
            Rice=("rice_bags", "sum"), Sugar=("sugar_bags", "sum"), Flour=("flour_bags", "sum")
        ).reset_index()
        ann_tot["Total"] = ann_tot["Rice"] + ann_tot["Sugar"] + ann_tot["Flour"]

        c1, c2, c3, c4 = st.columns(4)
        for col, label, val, colour in [
            (c1, "Rice (bags)", int(ann_tot["Rice"].sum()), COMM_COL["Rice"]),
            (c2, "Sugar (bags)", int(ann_tot["Sugar"].sum()), COMM_COL["Sugar"]),
            (c3, "Flour (bags)", int(ann_tot["Flour"].sum()), COMM_COL["Flour"]),
            (c4, "Total (bags)", int(ann_tot["Total"].sum()), "#9b59b6"),
        ]:
            with col:
                st.markdown(f"""<div class="kcard" style="border-left-color:{colour}">
                <div style="color:#aab;font-size:.8rem">{label}</div>
                <div style="font-size:1.4rem;font-weight:700;color:{colour}">{val:,}</div>
                </div>""", unsafe_allow_html=True)

        ann_m2 = ann_tot.melt("year", ["Rice", "Sugar", "Flour"], var_name="Commodity", value_name="Bags")
        fig_yr = px.bar(ann_m2, x="year", y="Bags", color="Commodity",
                        color_discrete_map={"Rice": COMM_COL["Rice"], "Sugar": COMM_COL["Sugar"], "Flour": COMM_COL["Flour"]},
                        template="plotly_dark", height=320, title="Annual Totals by Commodity",
                        labels={"year": "Year"})
        fig_yr.update_layout(margin=dict(t=50, b=10))
        st.plotly_chart(fig_yr, use_container_width=True)

        st.markdown("---")
        st.subheader("Monthly Data Table")
        disp_a = annual_f[["year", "month", "rice_bags", "sugar_bags", "flour_bags"]].copy()
        disp_a.columns = ["Year", "Month", "Rice (bags)", "Sugar (bags)", "Flour (bags)"]
        st.dataframe(disp_a, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download CSV", disp_a.to_csv(index=False), "annual_grains.csv", "text/csv")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — DATA ENTRY
# ══════════════════════════════════════════════════════════════════════════════
if _can_edit:
    with tab6:
        st.subheader("✏️ Data Entry")
        entry_type = st.radio("What would you like to add/update?",
            ["Cargo Arrival", "S.Tarawa Analysis", "Outer Island Stock",
             "Annual Incoming", "Cargo to Outer Island", "Upcoming Shipping Schedule", "Supplier"],
            horizontal=True)
        st.markdown("---")

        # ── Cargo Arrival ─────────────────────────────────────────────────────────
        if entry_type == "Cargo Arrival":
            st.markdown("**Add New Cargo Arrival**")
            suppliers_list = q("SELECT id, name FROM suppliers ORDER BY name")
            sup_map = dict(zip(suppliers_list["name"], suppliers_list["id"]))
            c1, c2, c3 = st.columns(3)
            rmonth = c1.text_input("Report Month", "June 2026")
            rdate  = c2.date_input("Report Date", value=date.today())
            sup    = c3.selectbox("Supplier", list(sup_map.keys()))
            c4, c5, c6 = st.columns(3)
            r_fcl  = c4.number_input("Rice FCL", 0, step=1)
            r_bags = c4.number_input("Rice Bags", 0, step=100)
            s_fcl  = c5.number_input("Sugar FCL", 0, step=1)
            s_bags = c5.number_input("Sugar Bags", 0, step=100)
            f_fcl  = c6.number_input("Flour FCL", 0, step=1)
            f_bags = c6.number_input("Flour Bags", 0, step=100)
            if st.button("💾 Save Cargo Arrival"):
                run("""INSERT INTO cargo_arrivals
                    (report_month,report_date,supplier_id,rice_fcl,rice_bags,sugar_fcl,sugar_bags,flour_fcl,flour_bags)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (rmonth, str(rdate), sup_map[sup], r_fcl, r_bags, s_fcl, s_bags, f_fcl, f_bags))
                st.success(f"✅ Cargo arrival saved for {sup} — {rmonth}")
                st.cache_data.clear(); st.rerun()

        # ── S.Tarawa Analysis ─────────────────────────────────────────────────────
        elif entry_type == "S.Tarawa Analysis":
            st.markdown("**Add S.Tarawa Analysis Record**")
            c1, c2, c3 = st.columns(3)
            rmonth   = c1.text_input("Report Month", "June 2026")
            rdate    = c2.date_input("Report Date", value=date.today())
            comm     = c3.selectbox("Commodity", ["Rice", "Sugar", "Flour"])
            unit_kg  = {"Rice": 18.14, "Sugar": 25.0, "Flour": 25.0}[comm]
            c4, c5, c6 = st.columns(3)
            manifest  = c4.number_input("Manifest Bags (incoming)", 0, step=100)
            remaining = c5.number_input("Remaining Stock (bags)", 0, step=100)
            quota_d   = c6.number_input("Daily Quota (bags/day)", 0, step=10)
            total = manifest + remaining
            est_d = round(total / quota_d, 2) if quota_d > 0 else 0
            last_d = str((datetime.strptime(str(rdate), "%Y-%m-%d") + timedelta(days=est_d)).date()) if est_d > 0 else ""
            st.info(f"Total Stock: **{total:,} bags** | Est. Days: **{est_d:.1f}** | Last Date: **{last_d}**")
            comments = st.text_input("Comments", "Okay")
            if st.button("💾 Save Analysis"):
                run("""INSERT INTO s_tarawa_analysis
                    (report_month,report_date,commodity,unit_kg,manifest_bags,quota_daily,remaining_stock,total_stock,est_days,last_date,comments)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(report_month,commodity) DO UPDATE SET
                        report_date=EXCLUDED.report_date, unit_kg=EXCLUDED.unit_kg,
                        manifest_bags=EXCLUDED.manifest_bags, quota_daily=EXCLUDED.quota_daily,
                        remaining_stock=EXCLUDED.remaining_stock, total_stock=EXCLUDED.total_stock,
                        est_days=EXCLUDED.est_days, last_date=EXCLUDED.last_date, comments=EXCLUDED.comments""",
                    (rmonth, str(rdate), comm, unit_kg, manifest, quota_d, remaining, total, est_d, last_d, comments))
                st.success(f"✅ S.Tarawa {comm} analysis saved/updated for {rmonth}")
                st.cache_data.clear(); st.rerun()

        # ── Outer Island Stock ────────────────────────────────────────────────────
        elif entry_type == "Outer Island Stock":
            st.markdown("**Update Outer Island Stock**")
            islands_list2 = q("SELECT DISTINCT island FROM outer_island_stock ORDER BY island")["island"].tolist()
            c1, c2, c3 = st.columns(3)
            island  = c1.selectbox("Island", islands_list2)
            comm2   = c2.selectbox("Commodity", ["Rice", "Sugar", "Flour"])
            cur_dt  = c3.date_input("Current Date", value=date.today())
            c4, c5 = st.columns(2)
            stock  = c4.number_input("Stock (bags)", 0, step=10)
            dquota = c5.number_input("Daily Quota (bags/day)", 0, step=1)
            est2  = round(stock / dquota, 2) if dquota > 0 else 0
            last2 = str((datetime.strptime(str(cur_dt), "%Y-%m-%d") + timedelta(days=est2)).date()) if est2 > 0 else ""
            st.info(f"Est. Days: **{est2:.1f}** | Last Date: **{last2}**")
            comm2_s = st.text_input("Comments", "")
            if st.button("💾 Update Island Stock"):
                run("""INSERT INTO outer_island_stock
                    (island,commodity,stock_bags,daily_quota,est_days,data_date,last_date,comments)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(island,commodity) DO UPDATE SET
                        stock_bags=EXCLUDED.stock_bags, daily_quota=EXCLUDED.daily_quota,
                        est_days=EXCLUDED.est_days, data_date=EXCLUDED.data_date,
                        last_date=EXCLUDED.last_date, comments=EXCLUDED.comments""",
                    (island, comm2, stock, dquota, est2, str(cur_dt), last2, comm2_s))
                st.success(f"✅ {island} — {comm2} updated")
                st.cache_data.clear(); st.rerun()

        # ── Annual Incoming ───────────────────────────────────────────────────────
        elif entry_type == "Annual Incoming":
            st.markdown("**Add Annual Incoming Record**")
            MONTHS = ["Jan","Feb","March","April","May","June","July","Aug","Sept","Oct","Nov","Dec"]
            c1, c2 = st.columns(2)
            yr   = c1.selectbox("Year", [2024, 2025, 2026], index=2)
            mon  = c2.selectbox("Month", MONTHS)
            c3, c4, c5 = st.columns(3)
            rice_a  = c3.number_input("Rice (bags)", 0, step=100)
            sugar_a = c4.number_input("Sugar (bags)", 0, step=100)
            flour_a = c5.number_input("Flour (bags)", 0, step=100)
            if st.button("💾 Save Annual Record"):
                run("""INSERT INTO annual_incoming(year,month,rice_bags,sugar_bags,flour_bags)
                    VALUES(%s,%s,%s,%s,%s)
                    ON CONFLICT(year,month) DO UPDATE SET
                        rice_bags=EXCLUDED.rice_bags, sugar_bags=EXCLUDED.sugar_bags,
                        flour_bags=EXCLUDED.flour_bags""",
                    (yr, mon, rice_a, sugar_a, flour_a))
                st.success(f"✅ Annual record saved: {mon} {yr}")
                st.cache_data.clear(); st.rerun()

        # ── Cargo to Outer Island ─────────────────────────────────────────────────
        elif entry_type == "Cargo to Outer Island":
            st.markdown("**Update Cargo Dispatched to Outer Island**")
            coi_islands = q("SELECT island FROM cargo_outer_islands ORDER BY island")["island"].tolist()
            c1, c2, c3, c4 = st.columns(4)
            coi_isl  = c1.selectbox("Island", coi_islands)
            coi_rice = c2.number_input("Rice (bags)", 0, step=1)
            coi_sug  = c3.number_input("Sugar (bags)", 0, step=1)
            coi_fl   = c4.number_input("Flour (bags)", 0, step=1)
            if st.button("💾 Update Cargo to Island"):
                run("""INSERT INTO cargo_outer_islands(island,rice_bags,sugar_bags,flour_bags)
                    VALUES(%s,%s,%s,%s)
                    ON CONFLICT(island) DO UPDATE SET
                        rice_bags=EXCLUDED.rice_bags, sugar_bags=EXCLUDED.sugar_bags,
                        flour_bags=EXCLUDED.flour_bags""",
                    (coi_isl, coi_rice, coi_sug, coi_fl))
                st.success(f"✅ Cargo to {coi_isl} updated")
                st.cache_data.clear(); st.rerun()

        # ── Upcoming Shipping Schedule ────────────────────────────────────────────
        elif entry_type == "Upcoming Shipping Schedule":
            st.markdown("**Add Upcoming Shipping Schedule Record**")
            c1, c2, c3 = st.columns(3)
            agency = c1.text_input("Shipping Agency", "")
            vessel = c2.text_input("Vessel Name", "")
            voyage = c3.text_input("Voyage No.", "")
            c4, c5 = st.columns(2)
            origin = c4.text_input("Origin Port", "")
            dest   = c5.text_input("Destination Port", "Betio, Tarawa")
            c6, c7 = st.columns(2)
            etd = c6.date_input("ETD (Estimated Departure)", value=date.today())
            eta = c7.date_input("ETA (Estimated Arrival)", value=date.today())
            c8, c9, c10 = st.columns(3)
            comm_s   = c8.selectbox("Commodity", ["Rice", "Sugar", "Flour", "Mixed"])
            qty_b    = c9.number_input("Quantity (Bags)", 0, step=100)
            qty_f    = c10.number_input("Quantity (FCL)", 0, step=1)
            c11, c12 = st.columns(2)
            status_s  = c11.selectbox("Status", ["Scheduled", "In Transit", "Delayed", "Arrived", "Cancelled"])
            remarks_s = c12.text_input("Remarks", "")
            if st.button("💾 Save Shipping Schedule"):
                if not agency:
                    st.error("Shipping Agency is required.")
                else:
                    run("""INSERT INTO shipping_schedule
                        (shipping_agency,vessel_name,voyage_no,origin_port,destination_port,
                         etd_date,eta_date,commodity,qty_bags,qty_fcl,status,remarks)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (agency, vessel, voyage, origin, dest, str(etd), str(eta),
                         comm_s, qty_b, qty_f, status_s, remarks_s))
                    st.success(f"✅ Shipping schedule saved — {agency} ({vessel or 'TBA'}), ETA {eta}")
                    st.cache_data.clear(); st.rerun()

        # ── Supplier ──────────────────────────────────────────────────────────────
        elif entry_type == "Supplier":
            sup_mode = st.radio("Action", ["➕ Add New Supplier", "✏️ Edit / Update Supplier"], horizontal=True)
            st.markdown("---")

            if sup_mode == "➕ Add New Supplier":
                st.markdown('<div class="section-title">➕ New Supplier Details</div>', unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                sup_name    = c1.text_input("Supplier Name *", placeholder="e.g. SAOK, One Stop")
                sup_contact = c2.text_input("Contact Person", placeholder="e.g. John Smith")
                c3, c4 = st.columns(2)
                sup_phone   = c3.text_input("Phone", placeholder="e.g. +686 12345")
                sup_email   = c4.text_input("Email", placeholder="e.g. supplier@example.com")
                sup_address = st.text_input("Address", placeholder="e.g. Betio, Tarawa, Kiribati")
                sup_notes   = st.text_area("Notes", height=80)
                if st.button("💾 Save New Supplier"):
                    if not sup_name.strip():
                        st.error("⚠️ Supplier Name is required.")
                    else:
                        try:
                            run("INSERT INTO suppliers(name,contact_person,phone,email,address,notes) VALUES(%s,%s,%s,%s,%s,%s)",
                                (sup_name.strip(), sup_contact.strip(), sup_phone.strip(),
                                 sup_email.strip(), sup_address.strip(), sup_notes.strip()))
                            st.success(f"✅ Supplier '{sup_name.strip()}' added.")
                            st.cache_data.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
            else:
                existing_sups = q("SELECT id, name, contact_person, phone, email, address, notes FROM suppliers ORDER BY name")
                if existing_sups.empty:
                    st.info("No suppliers yet.")
                else:
                    selected_name = st.selectbox("Select Supplier to Edit", existing_sups["name"].tolist())
                    sel_row = existing_sups[existing_sups["name"] == selected_name].iloc[0]
                    sel_id  = int(sel_row["id"])
                    st.markdown(f'<div class="section-title">✏️ Editing: {selected_name}</div>', unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    edit_name    = c1.text_input("Supplier Name *", value=sel_row["name"] or "")
                    edit_contact = c2.text_input("Contact Person", value=sel_row["contact_person"] or "")
                    c3, c4 = st.columns(2)
                    edit_phone = c3.text_input("Phone", value=sel_row["phone"] or "")
                    edit_email = c4.text_input("Email", value=sel_row["email"] or "")
                    edit_address = st.text_input("Address", value=sel_row["address"] or "")
                    edit_notes   = st.text_area("Notes", value=sel_row["notes"] or "", height=80)
                    col_save, col_del = st.columns(2)
                    with col_save:
                        if st.button("💾 Update Supplier"):
                            try:
                                run("UPDATE suppliers SET name=%s,contact_person=%s,phone=%s,email=%s,address=%s,notes=%s WHERE id=%s",
                                    (edit_name.strip(), edit_contact.strip(), edit_phone.strip(),
                                     edit_email.strip(), edit_address.strip(), edit_notes.strip(), sel_id))
                                st.success(f"✅ '{edit_name.strip()}' updated.")
                                st.cache_data.clear(); st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error: {e}")
                    with col_del:
                        if st.button("🗑️ Delete Supplier", type="secondary"):
                            st.session_state["confirm_delete_sup"] = sel_id
                    if st.session_state.get("confirm_delete_sup") == sel_id:
                        st.warning(f"⚠️ Delete **{selected_name}**? This cannot be undone.")
                        cc1, cc2 = st.columns(2)
                        if cc1.button("✅ Yes, Delete"):
                            run("DELETE FROM suppliers WHERE id=%s", (sel_id,))
                            st.session_state.pop("confirm_delete_sup", None)
                            st.success(f"🗑️ '{selected_name}' deleted.")
                            st.cache_data.clear(); st.rerun()
                        if cc2.button("❌ Cancel"):
                            st.session_state.pop("confirm_delete_sup", None)
                            st.rerun()

            st.markdown("---")
            st.markdown('<div class="section-title">📋 All Suppliers on Record</div>', unsafe_allow_html=True)
            all_sups = q("SELECT id, name, contact_person, phone, email, address, notes FROM suppliers ORDER BY name")
            if not all_sups.empty:
                all_sups.columns = ["ID", "Name", "Contact Person", "Phone", "Email", "Address", "Notes"]
                st.dataframe(all_sups, use_container_width=True, hide_index=True)
                st.download_button("⬇️ Download CSV", all_sups.to_csv(index=False), "suppliers.csv", "text/csv")

    # ── Footer ────────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""<div style="text-align:center;color:#555;font-size:.78rem">
    Kiribati BIU Grain Monitoring System &nbsp;|&nbsp;
    Ministry of Commerce, Industry &amp; Cooperatives &nbsp;|&nbsp;
    Data: cargo_update &nbsp;|&nbsp; DB: PostgreSQL
    </div>""", unsafe_allow_html=True)
