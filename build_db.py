"""
build_db.py  —  Kiribati Grain Monitoring System
Builds SQLite database from cargo_update_June_2026.xlsx data.
"""

import sqlite3, os

DB = os.path.join(os.path.dirname(__file__), "grain_monitor.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    contact_person TEXT,
    phone          TEXT,
    email          TEXT,
    address        TEXT,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS cargo_arrivals (
    id              INTEGER PRIMARY KEY,
    report_month    TEXT NOT NULL,        -- e.g. 'February 2026'
    report_date     TEXT NOT NULL,        -- ISO date
    supplier_id     INTEGER REFERENCES suppliers(id),
    rice_fcl        INTEGER DEFAULT 0,
    rice_bags       INTEGER DEFAULT 0,
    sugar_fcl       INTEGER DEFAULT 0,
    sugar_bags      INTEGER DEFAULT 0,
    flour_fcl       INTEGER DEFAULT 0,
    flour_bags      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS s_tarawa_analysis (
    id              INTEGER PRIMARY KEY,
    report_month    TEXT NOT NULL,
    report_date     TEXT NOT NULL,
    commodity       TEXT NOT NULL,        -- 'Rice','Sugar','Flour'
    unit_kg         REAL NOT NULL,
    manifest_bags   INTEGER DEFAULT 0,
    quota_daily     INTEGER DEFAULT 0,
    remaining_stock INTEGER DEFAULT 0,
    total_stock     INTEGER DEFAULT 0,
    est_days        REAL DEFAULT 0,
    last_date       TEXT,
    comments        TEXT
);

CREATE TABLE IF NOT EXISTS outer_island_stock (
    id              INTEGER PRIMARY KEY,
    island          TEXT NOT NULL,
    commodity       TEXT NOT NULL,
    UNIQUE(island, commodity),
    stock_bags      INTEGER DEFAULT 0,
    daily_quota     INTEGER DEFAULT 0,
    est_days        REAL DEFAULT 0,
    current_date    TEXT,
    last_date       TEXT,
    comments        TEXT
);

CREATE TABLE IF NOT EXISTS annual_incoming (
    id          INTEGER PRIMARY KEY,
    year        INTEGER NOT NULL,
    month       TEXT NOT NULL,
    rice_bags   INTEGER DEFAULT 0,
    sugar_bags  INTEGER DEFAULT 0,
    flour_bags  INTEGER DEFAULT 0,
    UNIQUE(year, month)
);

CREATE TABLE IF NOT EXISTS cargo_outer_islands (
    id          INTEGER PRIMARY KEY,
    island      TEXT NOT NULL UNIQUE,
    rice_bags   INTEGER DEFAULT 0,
    sugar_bags  INTEGER DEFAULT 0,
    flour_bags  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shipping_schedule (
    id              INTEGER PRIMARY KEY,
    shipping_agency TEXT NOT NULL,
    vessel_name     TEXT,
    voyage_no       TEXT,
    origin_port     TEXT,
    destination_port TEXT,
    etd_date        TEXT,                 -- estimated time of departure
    eta_date        TEXT NOT NULL,        -- estimated time of arrival
    commodity       TEXT,                 -- 'Rice','Sugar','Flour','Mixed'
    qty_bags        INTEGER DEFAULT 0,
    qty_fcl         INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'Scheduled',  -- Scheduled, In Transit, Delayed, Arrived, Cancelled
    remarks         TEXT
);

CREATE VIEW IF NOT EXISTS island_status AS
SELECT
    island,
    commodity,
    stock_bags,
    daily_quota,
    est_days,
    current_date,
    last_date,
    CASE
        WHEN LOWER(comments) LIKE '%crisis%' THEN 'CRISIS'
        WHEN LOWER(comments) LIKE '%not enough%' THEN 'LOW'
        WHEN LOWER(comments) LIKE '%finish%' THEN 'EMPTY'
        WHEN est_days = 0 THEN 'NO DATA'
        WHEN est_days < 10 THEN 'CRITICAL'
        WHEN est_days < 20 THEN 'LOW'
        ELSE 'OKAY'
    END AS status
FROM outer_island_stock;
"""

# Excel serial date 46072 = 2026-02-10, 46192 = 2026-06-10 (approx)
# Suppliers
SUPPLIERS = [
    (1,  "Taotin Trading"),
    (2,  "Moel Trading"),
    (3,  "Betty Trading"),
    (4,  "Punjas"),
    (5,  "DI Joren Trading"),
    (6,  "King Holdings"),
    (7,  "Wishing Star"),
    (8,  "Paradise"),
    (9,  "Lees Trading"),
    (10, "The Favourite"),
    (11, "Lyke IT Trading"),
    (12, "Triple Tee"),
    (13, "The Rainbow"),
    (14, "Hanan"),
    (15, "Slim Price"),
    (16, "FHC"),
    (17, "Henicki"),
    (18, "M&A Enterprises"),
    (19, "IslandFrontline Ent"),
    (20, "TT Endeavors Services"),
    (21, "KFM"),
    (22, "Rainbow Company"),
    (23, "Ellan Enterprice"),
]

# Cargo arrivals — February 2026
FEB_CARGO = [
    # (report_month, date, supplier_id, rice_fcl, rice_bags, sugar_fcl, sugar_bags, flour_fcl, flour_bags)
    ("February 2026", "2026-02-10", 4,  0, 0,    10, 10000, 8, 8320),
    ("February 2026", "2026-02-10", 6,  6, 8928,  0, 0,     0, 0),
    ("February 2026", "2026-02-10", 14, 0, 0,     1, 900,   0, 0),
    ("February 2026", "2026-02-10", 15, 1, 1488,  0, 0,     0, 0),
    ("February 2026", "2026-02-10", 18, 3, 3750,  0, 0,     0, 0),
    ("February 2026", "2026-02-10", 19, 1, 1250,  0, 0,     0, 0),
    ("February 2026", "2026-02-10", 21, 2, 2500,  0, 0,     0, 0),
]

# Cargo arrivals — May 2026
MAY_CARGO = [
    ("May 2026", "2026-05-11", 2,  0, 0,     5, 9000,  0, 0),
    ("May 2026", "2026-05-11", 4,  8, 11024, 10,10000, 0, 0),
    ("May 2026", "2026-05-11", 6,  5, 7440,  0, 0,     0, 0),
    ("May 2026", "2026-05-11", 7,  3, 4134,  0, 0,     0, 0),
    ("May 2026", "2026-05-11", 14, 0, 0,     1, 1000,  0, 0),
    ("May 2026", "2026-05-11", 18, 2, 3000,  0, 0,     0, 0),
    ("May 2026", "2026-05-11", 22, 2, 2756,  0, 0,     0, 0),
    ("May 2026", "2026-05-11", 21, 2, 2756,  0, 0,     0, 0),
]

CARGO_ARRIVALS = FEB_CARGO + MAY_CARGO

# S.Tarawa analysis
S_TARAWA = [
    # (report_month, date, commodity, unit_kg, manifest, quota_daily, remaining, total, est_days, last_date, comments)
    ("February 2026","2026-02-10","Rice",  18.14,17916,1926,80505,98421, 51.10,"2026-04-02","Okay"),
    ("February 2026","2026-02-10","Sugar", 25.0, 10900,925,  0,   10900, 11.78,"2026-02-21","Okay"),
    ("February 2026","2026-02-10","Flour", 25.0, 8320, 771,  0,   8320,  10.79,"2026-02-20","Okay"),
    ("May 2026",     "2026-05-13","Rice",  18.14,31110,1975,49375,80485, 40.75,"2026-06-23","Okay"),
    ("May 2026",     "2026-05-13","Sugar", 25.0, 20000,573, 5730, 25730, 44.90,"2026-06-27","Okay"),
    ("May 2026",     "2026-05-13","Flour", 25.0, 0,    478, 6692, 6692,  14.00,"2026-05-27","Okay"),
]

# Outer island stock (from Outer Island stock sheet)
# (island, commodity, stock_bags, daily_quota, est_days, current_date, last_date, comments)
OUTER = [
    # Makin
    ("Makin","Rice",  0,  31, 0,    "2026-01-27","2026-01-27","okay"),
    ("Makin","Sugar", 0,  12, 0,    "2026-01-27","2026-01-27","okay"),
    ("Makin","Flour", 0,  15, 0,    "2026-01-27","2026-01-27","okay"),
    # Butaritari
    ("Butaritari","Rice",  1927, 52, 37.06, "2026-03-17","2026-04-23",""),
    ("Butaritari","Sugar", 681,  21, 32.43, "2026-03-17","2026-04-18",""),
    ("Butaritari","Flour", 70,   25, 2.80,  "2026-03-17","2026-03-19",""),
    # Marakei
    ("Marakei","Rice",  1002, 44, 22.77, "2026-01-28","2026-02-19","okay"),
    ("Marakei","Sugar", 815,  18, 45.28, "2026-01-28","2026-03-14","okay"),
    ("Marakei","Flour", 90,   21, 4.29,  "2026-01-28","2026-02-01","crisis"),
    # Abaiang
    ("Abaiang","Rice",  0, 94, 0, "2025-12-03","2025-12-03",""),
    ("Abaiang","Sugar", 0, 38, 0, "2025-07-24","2025-07-24",""),
    ("Abaiang","Flour", 0, 45, 0, "2025-07-24","2025-07-24",""),
    # N.Tarawa (ETC)
    ("N.Tarawa","Rice",  0, 113, 0, "2025-07-24","2025-07-24",""),
    ("N.Tarawa","Sugar", 0, 45,  0, "2025-07-24","2025-07-24",""),
    ("N.Tarawa","Flour", 0, 54,  0, "2025-07-24","2025-07-24",""),
    # Maiana
    ("Maiana","Rice",  0, 38, 0, "2025-07-26","2025-07-26",""),
    ("Maiana","Sugar", 0, 15, 0, "2025-07-26","2025-07-26",""),
    ("Maiana","Flour", 0, 18, 0, "2025-07-26","2025-07-26",""),
    # Kuria
    ("Kuria","Rice",  487, 19, 25.63, "2026-04-05","2026-04-30","Okay"),
    ("Kuria","Sugar", 353, 8,  44.13, "2026-04-05","2026-05-19","Okay"),
    ("Kuria","Flour", 17,  9,  1.89,  "2026-04-05","2026-04-06","Okay"),
    # Aranuka
    ("Aranuka","Rice",  0, 20, 0, "2025-07-26","2025-07-26",""),
    ("Aranuka","Sugar", 0, 8,  0, "2025-07-26","2025-07-26",""),
    ("Aranuka","Flour", 0, 9,  0, "2025-07-26","2025-07-26",""),
    # Abemama
    ("Abemama","Rice",  0, 53, 0, "2025-07-24","2025-07-24",""),
    ("Abemama","Sugar", 0, 25, 0, "2025-07-24","2025-07-24",""),
    ("Abemama","Flour", 0, 21, 0, "2025-07-24","2025-07-24",""),
    # Nonouti
    ("Nonouti","Rice",  0, 45, 0, "2026-03-04","2026-03-04",""),
    ("Nonouti","Sugar", 0, 13, 0, "2026-03-04","2026-03-04",""),
    ("Nonouti","Flour", 0, 11, 0, "2026-03-04","2026-03-04",""),
    # Tab-North
    ("Tab-North","Rice",  0, 67, 0, "2026-01-01","2026-01-01","okay"),
    ("Tab-North","Sugar", 0, 27, 0, "2026-01-01","2026-01-01","okay"),
    ("Tab-North","Flour", 0, 32, 0, "2026-01-01","2026-01-01","not enough"),
    # Tab-South
    ("Tab-South","Rice",  0, 22, 0, "2025-09-09","2025-09-09","not enough"),
    ("Tab-South","Sugar", 0, 9,  0, "2025-09-09","2025-09-09","not enough"),
    ("Tab-South","Flour", 0, 10, 0, "2025-09-09","2025-09-09","crisis"),
    # Onotoa
    ("Onotoa","Rice",  1436, 23, 62.43, "2026-03-18","2026-05-19",""),
    ("Onotoa","Sugar", 419,  9,  46.56, "2026-03-18","2026-05-03",""),
    ("Onotoa","Flour", 164,  11, 14.91, "2026-03-18","2026-04-01",""),
    # Beru
    ("Beru","Rice",  0, 36, 0, "2025-11-17","2025-11-17",""),
    ("Beru","Sugar", 0, 14, 0, "2025-11-17","2025-11-17",""),
    ("Beru","Flour", 0, 17, 0, "2025-11-17","2025-11-17",""),
    # Nikunau
    ("Nikunau","Rice",  0, 34, 0, "2026-03-03","2026-03-03","ok"),
    ("Nikunau","Sugar", 0, 10, 0, "2026-03-03","2026-03-03","ok"),
    ("Nikunau","Flour", 0, 8,  0, "2026-03-03","2026-03-03","ok"),
    # Tamana
    ("Tamana","Rice",  481, 17, 28.29, "2026-04-05","2026-05-03","okay"),
    ("Tamana","Sugar", 515, 7,  73.57, "2026-04-05","2026-06-17","okay"),
    ("Tamana","Flour", 136, 8,  17.00, "2026-04-05","2026-04-22","okay"),
    # Arorae
    ("Arorae","Rice",  609, 16, 38.06, "2026-04-05","2026-05-13","okay"),
    ("Arorae","Sugar", 500, 5,  100.0, "2026-04-05","2026-07-14","okay"),
    ("Arorae","Flour", 0,   4,  0,     "2026-04-05","2026-04-05","okay"),
    # Banaba
    ("Banaba","Rice",  0, 5, 0, "2026-01-22","2026-01-22","okay"),
    ("Banaba","Sugar", 0, 3, 0, "2026-01-22","2026-01-22","okay"),
    ("Banaba","Flour", 0, 2, 0, "2026-01-22","2026-01-22","finish"),
    # Kiritimati (Christmas Island)
    ("Kiritimati","Rice",  0, 0, 0, "", "", "no data"),
    ("Kiritimati","Sugar", 0, 0, 0, "", "", "no data"),
    ("Kiritimati","Flour", 0, 0, 0, "", "", "no data"),
    # Kanton (Phoenix Islands)
    ("Kanton","Rice",  0, 0, 0, "", "", "no data"),
    ("Kanton","Sugar", 0, 0, 0, "", "", "no data"),
    ("Kanton","Flour", 0, 0, 0, "", "", "no data"),
    # Tabuaeran (Fanning Island)
    ("Tabuaeran","Rice",  0, 0, 0, "", "", "no data"),
    ("Tabuaeran","Sugar", 0, 0, 0, "", "", "no data"),
    ("Tabuaeran","Flour", 0, 0, 0, "", "", "no data"),
    # Teraina (Washington Island)
    ("Teraina","Rice",  0, 0, 0, "", "", "no data"),
    ("Teraina","Sugar", 0, 0, 0, "", "", "no data"),
    ("Teraina","Flour", 0, 0, 0, "", "", "no data"),
    # Betio
    ("Betio","Rice",  0, 0, 0, "", "", "no data"),
    ("Betio","Sugar", 0, 0, 0, "", "", "no data"),
    ("Betio","Flour", 0, 0, 0, "", "", "no data"),
]

# Annual incoming grains
ANNUAL = [
    (2024,"Jan",   35967,  7325,  7200),
    (2024,"Feb",  108587, 30165, 14500),
    (2024,"March",111950, 14200,  9900),
    (2024,"April", 46310,  7880, 16585),
    (2024,"May",   26460, 18840, 13520),
    (2024,"June",  82540, 12580, 13479),
    (2024,"July",  74083, 25000, 11700),
    (2024,"Aug",   73199, 13270, 12440),
    (2024,"Sept",  32753,  2170,  3188),
    (2024,"Oct",   58325, 19650, 12400),
    (2024,"Nov",   75775, 40600, 16779),
    (2024,"Dec",   86619, 25900,  3480),
    (2025,"Jan",   51131, 11800, 10000),
    (2025,"Feb",   26137, 13100,  3500),
    (2025,"March", 60352, 35920,  6200),
    (2025,"April", 68946, 35850, 13600),
    (2025,"May",  116671, 11000,  6000),
    (2025,"June",      0,     0, 10657),
    (2025,"July", 112852, 16500, 20480),
    (2025,"Aug",   76020, 11800, 26760),
    (2025,"Sept",  58325, 20800,  2520),
    (2025,"Oct",   92126, 18700, 14560),
    (2025,"Nov",  129333, 19500, 24960),
    (2025,"Dec",   84560, 21000, 14020),
]

# Cargo to outer islands (from Cargo to outer islands sheet)
CARGO_OI = [
    ("Makin",0,0,0),("Butaritari",0,0,0),("Marakei",0,0,0),
    ("Abaiang",0,0,0),("Maiana",0,0,0),("Kuria",0,0,0),
    ("Aranuka",0,0,0),("Abemama",0,0,0),("Nonouti",0,0,0),
    ("Tab-North",0,0,0),("Tab-South",0,0,0),("Onotoa",0,0,0),
    ("Beru",0,0,0),("Nikunau",0,0,0),("Tamana",0,0,0),
    ("Arorae",0,0,0),("Banaba",0,0,0),("Kanton",15,9,10),
    ("Kiritimati",0,0,0),("Tabuaeran",0,0,0),("Teraina",0,0,0),("Betio",0,0,0),
]

# Upcoming shipping schedule — shipping agencies
# (agency, vessel, voyage_no, origin_port, destination_port, etd_date, eta_date, commodity, qty_bags, qty_fcl, status, remarks)
SHIPPING_SCHEDULE = [
    ("Kiribati Shipping Services Ltd", "MV Moana Pacific", "KSS-2607", "Suva, Fiji", "Betio, Tarawa", "2026-06-22", "2026-07-01", "Rice",  18000, 10, "Scheduled", ""),
    ("Pacific Forum Line",             "MV Southern Cross", "PFL-1142", "Auckland, NZ", "Betio, Tarawa", "2026-06-18", "2026-06-29", "Sugar", 9000,  6,  "In Transit", ""),
    ("Neptune Pacific Line",           "MV Reef Islander",  "NPL-0588", "Brisbane, AU", "Betio, Tarawa", "2026-06-25", "2026-07-06", "Mixed", 12500, 9,  "Scheduled", "Rice + Flour combined load"),
]

def build():
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)
    con.executemany("INSERT OR IGNORE INTO suppliers VALUES(?,?)", SUPPLIERS)
    con.executemany(
        "INSERT INTO cargo_arrivals(report_month,report_date,supplier_id,rice_fcl,rice_bags,sugar_fcl,sugar_bags,flour_fcl,flour_bags) VALUES(?,?,?,?,?,?,?,?,?)",
        CARGO_ARRIVALS)
    con.executemany(
        "INSERT INTO s_tarawa_analysis(report_month,report_date,commodity,unit_kg,manifest_bags,quota_daily,remaining_stock,total_stock,est_days,last_date,comments) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        S_TARAWA)
    con.executemany(
        "INSERT OR REPLACE INTO outer_island_stock(island,commodity,stock_bags,daily_quota,est_days,current_date,last_date,comments) VALUES(?,?,?,?,?,?,?,?)",
        OUTER)
    con.executemany(
        "INSERT OR IGNORE INTO annual_incoming(year,month,rice_bags,sugar_bags,flour_bags) VALUES(?,?,?,?,?)",
        ANNUAL)
    con.executemany(
        "INSERT OR IGNORE INTO cargo_outer_islands(island,rice_bags,sugar_bags,flour_bags) VALUES(?,?,?,?)",
        CARGO_OI)
    con.executemany(
        "INSERT INTO shipping_schedule(shipping_agency,vessel_name,voyage_no,origin_port,destination_port,etd_date,eta_date,commodity,qty_bags,qty_fcl,status,remarks) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        SHIPPING_SCHEDULE)
    con.commit()
    con.close()
    print(f"✅  DB built: {DB}")
    print(f"    {len(SUPPLIERS)} suppliers | {len(CARGO_ARRIVALS)} cargo records")
    print(f"    {len(S_TARAWA)} S.Tarawa analysis | {len(OUTER)} outer island records")
    print(f"    {len(ANNUAL)} annual records | {len(CARGO_OI)} cargo-to-OI records")
    print(f"    {len(SHIPPING_SCHEDULE)} shipping schedule records")

if __name__ == "__main__":
    build()
