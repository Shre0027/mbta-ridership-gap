"""Bus baseline: do the two MBTA datasets agree when both use the same counting source?

Bus ridership in BOTH the monthly dataset and the stop-level dataset comes from Automatic
Passenger Counters (APC) on the buses (OPMI Ridership Guide). So this is not an independent
test of the transfer explanation. It answers a narrower question: when the source is the same,
do the two publications agree? If yes, the rail gap is about the rail method (taps x factors vs
the ODX model), not about a general mismatch between how the two datasets are published.

Input : data/raw/bus_dl/<zip folder>/*Fall_20*.csv  (Fall 2016-2025, APC, per trip and stop)
Output: outputs/bus_baseline.csv     (bus: APC stop-level vs monthly All Bus, two date windows)
        outputs/window_sensitivity.csv (rail lines: gap with Sep-Dec vs Sep-Nov monthly window)
"""
import glob
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs"

import importlib.util
spec = importlib.util.spec_from_file_location("an", ROOT / "scripts" / "02_analyze.py")


def load_fall(path):
    head = pd.read_csv(path, nrows=0).columns.str.replace("﻿", "").str.strip()
    cols = {c.lower(): c for c in head}
    route = cols.get("route_id") or cols.get("gtfs route_id")
    day = cols.get("day_type_name") or cols.get("day type")
    board = cols.get("boardings")
    d = pd.read_csv(path, usecols=lambda c: c.replace("﻿", "").strip() in (route, day, board), low_memory=False)
    d.columns = d.columns.str.replace("﻿", "").str.strip()
    d = d.rename(columns={route: "route", day: "day", board: "boardings"})
    d = d[d["day"].astype(str).str.lower().isin(["weekday", "wkdy"])]
    r = d["route"].astype(str).str.upper().str.strip()
    silver = r.str.startswith("SL") | r.isin(["741", "742", "743", "746", "749", "751"])
    return {"apc_all": d["boardings"].sum(), "apc_silver": d.loc[silver, "boardings"].sum(), "routes": r.nunique()}


def main():
    an = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(an)
    monthly = an.load_monthly()
    rows = []
    for f in sorted(glob.glob(str(RAW / "bus_dl" / "*" / "*Fall_20*.csv"))):
        yr = int(f[-8:-4])
        r = load_fall(f)
        row = {"fall": yr, **{k: round(v) if k != "routes" else v for k, v in r.items()}}
        for k in ["Bus", "All Bus", "Silver Line", "Trackless Trolley"]:
            v = monthly.get((yr, k))
            row["monthly_" + k.lower().replace(" ", "_")] = round(v) if v is not None and v == v else None
        rows.append(row)
    df = pd.DataFrame(rows)
    # Two date windows for the monthly side. The stop-level fall season is ~15 weeks (e.g. 73 weekdays in
    # Fall 2025, roughly Sep to mid-Dec), so it leaves out the late-December holiday weeks; full monthly
    # months Sep-Dec include them. Sep-Nov leaves December out entirely. The truth sits between the two.
    sepnov = monthly_window(an, [9, 10, 11])
    df["monthly_all_bus_sepnov"] = df["fall"].map(lambda y: sepnov.get((y, "All Bus"))).round()
    df["gap_sepdec_pct"] = (100 * (df["monthly_all_bus"] - df["apc_all"]) / df["apc_all"]).round(1)
    df["gap_sepnov_pct"] = (100 * (df["monthly_all_bus_sepnov"] - df["apc_all"]) / df["apc_all"]).round(1)
    df.to_csv(OUT / "bus_baseline.csv", index=False)
    print(df[["fall", "apc_all", "monthly_all_bus", "monthly_all_bus_sepnov", "gap_sepdec_pct", "gap_sepnov_pct"]].to_string(index=False))

    # Same window test on the rail lines
    line = pd.read_csv(OUT / "line_gap_by_year.csv").dropna(subset=["gap_pct"])
    line["monthly_sepnov"] = [sepnov.get((f, l)) for f, l in zip(line["fall"], line["line"])]
    line["gap_sepnov_pct"] = (100 * (line["monthly_sepnov"] - line["stop_level"]) / line["stop_level"]).round(1)
    line = line.rename(columns={"gap_pct": "gap_sepdec_pct"})[["fall", "line", "stop_level", "gap_sepdec_pct", "gap_sepnov_pct"]]
    line.to_csv(OUT / "window_sensitivity.csv", index=False)
    print(line.to_string(index=False))


def monthly_window(an, months):
    m = pd.read_csv(RAW / "monthly_by_mode_line.csv")
    m["month"] = pd.to_datetime(m["month_of_service"], unit="ms")
    m = m[(m["daytype"] == "Weekday") & m["month"].dt.month.isin(months)].copy()
    m["fall"] = m["month"].dt.year
    g = m.groupby(["fall", "route_or_line"])
    return (g["ridership_total"].sum() / g["daycount"].sum()).to_dict()


if __name__ == "__main__":
    main()
