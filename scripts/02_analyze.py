"""Step 2: reconcile the two MBTA ridership datasets.

Outputs (outputs/):
  line_gap_by_year.csv      - weekday riders per subway line: monthly dataset vs stop-level (ODX) dataset
  blue_stations_by_year.csv - Blue Line, per station: raw gate taps vs ODX boardings
  blue_summary_by_year.csv  - Blue Line decomposition by fall season

Comparison window (see docs/decision_log.md):
  "Fall YYYY" = weekdays, September-December, holidays excluded.
  Monthly dataset: day-weighted average of Sep-Dec weekday months
  (this reproduces the figures in the Feb 2025 MBTA Developers forum post exactly).
"""
from pathlib import Path

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "outputs"
LINES = ["Red Line", "Orange Line", "Blue Line", "Green Line"]
FALLS = [2017, 2018, 2019, 2023, 2024, 2025]
TRANSFER = ["State", "Government Center"]  # Blue Line stations where riders can transfer behind the gate


def norm_station(name):
    # Data-quality fix: the same station is "State" in ODX files and "State Street" in gate-tap files
    return str(name).replace("State Street", "State").strip()


def load_stop_level():
    frames = [pd.read_csv(RAW / f) for f in
              ["rail_stop_season.csv", "fall2023_stop.csv", "fall2024_stop.csv", "fall2025_hour.csv"]]
    s = pd.concat(frames, ignore_index=True)
    s = s[s["day_type_name"].str.lower() == "weekday"].copy()
    s["fall"] = s["season"].str.extract(r"(\d{4})").astype(int)
    s["station"] = s["stop_name"].map(norm_station)
    # Data-quality fix: Fall 2025 splits the Green Line into branches (Green Line B/C/D/E); roll up to one line
    s["route_name"] = s["route_name"].str.replace(r"^Green Line [B-E]$", "Green Line", regex=True)
    return s


def load_monthly():
    m = pd.read_csv(RAW / "monthly_by_mode_line.csv")
    m["month"] = pd.to_datetime(m["month_of_service"], unit="ms")
    m = m[(m["daytype"] == "Weekday") & (m["month"].dt.month >= 9)].copy()
    m["fall"] = m["month"].dt.year
    g = m.groupby(["fall", "route_or_line"])
    return (g["ridership_total"].sum() / g["daycount"].sum()).rename("monthly")


def fall_weekdays(year):
    hol = set(USFederalHolidayCalendar().holidays(f"{year}-01-01", f"{year}-12-31"))
    hol |= {h + pd.Timedelta(days=1) for h in hol if h.month == 11 and h.day >= 22}  # day after Thanksgiving
    return hol


def load_taps(year):
    g = pd.read_csv(RAW / "gse_hist" / "GSE_by_year" / f"GSE_{year}.csv",
                    usecols=["service_date", "station_name", "route_or_line", "gated_entries"])
    g["d"] = pd.to_datetime(g["service_date"])
    hol = fall_weekdays(year)
    g = g[(g["d"].dt.month >= 9) & (g["d"].dt.dayofweek < 5) & ~g["d"].isin(hol)]
    days = g["d"].nunique()
    g["station"] = g["station_name"].map(norm_station)
    return (g.groupby(["route_or_line", "station"])["gated_entries"].sum() / days).rename("taps")


def main():
    OUT.mkdir(exist_ok=True)
    stop, monthly = load_stop_level(), load_monthly()

    # 1) Line-level gap
    odx_line = stop.groupby(["fall", "route_name"])["average_ons"].sum().rename("stop_level")
    line = pd.concat([odx_line, monthly], axis=1).reset_index()
    line.columns = ["fall", "line", "stop_level", "monthly"]
    line = line[line["line"].isin(LINES) & line["fall"].isin(FALLS)].dropna(subset=["stop_level"])
    line["gap_pct"] = (line["monthly"] - line["stop_level"]) / line["stop_level"] * 100
    line.round(1).to_csv(OUT / "line_gap_by_year.csv", index=False)

    # 2) Blue Line station-level test
    station_rows, summary = [], []
    for yr in FALLS:
        taps = load_taps(yr).loc["Blue Line"]
        odx = stop[(stop["fall"] == yr) & (stop["route_name"] == "Blue Line")].groupby("station")["average_ons"].sum()
        t = pd.concat([taps, odx.rename("odx")], axis=1).fillna(0)
        t["fall"], t["model_per_tap"] = yr, t["odx"] / t["taps"]
        station_rows.append(t.reset_index().rename(columns={"index": "station"}))
        reg = t.drop(TRANSFER)
        x = t.loc[TRANSFER]
        ratio = reg["odx"].sum() / reg["taps"].sum()
        mon = monthly.get((yr, "Blue Line"))
        summary.append({
            "fall": yr,
            "stop_level_total": t["odx"].sum(),
            "monthly": mon,
            "gap_pct": (mon - t["odx"].sum()) / t["odx"].sum() * 100 if pd.notna(mon) else None,
            "taps_total": t["taps"].sum(),
            "regular_station_model_per_tap": ratio,
            "transfer_station_boardings": x["odx"].sum(),
            "transfer_station_taps": x["taps"].sum(),
            "transfer_share_of_boardings_pct": x["odx"].sum() / t["odx"].sum() * 100,
            "gov_center_taps_credited_to_blue": t.loc["Government Center", "taps"],
        })
    pd.concat(station_rows).round(2).to_csv(OUT / "blue_stations_by_year.csv", index=False)
    s = pd.DataFrame(summary).round(2)
    s.to_csv(OUT / "blue_summary_by_year.csv", index=False)

    pd.set_option("display.width", 200)
    print(line.round(1).to_string(index=False))
    print()
    print(s.to_string(index=False))


if __name__ == "__main__":
    main()
