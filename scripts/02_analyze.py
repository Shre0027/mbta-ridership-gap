"""Step 2: reconcile the two MBTA ridership datasets.

Outputs (outputs/):
  line_gap_by_year.csv          - weekday riders per subway line: monthly dataset vs stop-level (ODX) dataset
  blue_stations_by_year.csv     - Blue Line, per station: raw gate taps vs ODX boardings
  blue_summary_by_year.csv      - Blue Line decomposition and bridge by fall season
  monthly_factor_by_month.csv   - effective scaling factor in the monthly dataset (monthly riders / gate taps), by line and month
  green_summary_by_year.csv     - Green Line: monthly factor vs model factor, gated vs ungated boardings

Bridge (exact identity, per fall season):
  stop_level - monthly = [regular-station boardings - regular taps x F] + [transfer-station boardings - transfer taps x F]
  where F = monthly / total taps is the effective factor the monthly dataset applies to Blue Line taps.

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


def load_taps_by_month(year):
    g = pd.read_csv(RAW / "gse_hist" / "GSE_by_year" / f"GSE_{year}.csv",
                    usecols=["service_date", "route_or_line", "gated_entries"])
    g["d"] = pd.to_datetime(g["service_date"])
    hol = set(USFederalHolidayCalendar().holidays(f"{year}-01-01", f"{year}-12-31"))
    g = g[(g["d"].dt.dayofweek < 5) & ~g["d"].isin(hol)]
    g["month"] = g["d"].dt.to_period("M")
    days = g.groupby("month")["d"].nunique()
    t = g.groupby(["month", "route_or_line"])["gated_entries"].sum().unstack()
    return t.div(days, axis=0)


def monthly_weekday_avg():
    m = pd.read_csv(RAW / "monthly_by_mode_line.csv")
    m["month"] = pd.to_datetime(m["month_of_service"], unit="ms").dt.to_period("M")
    return m[m["daytype"] == "Weekday"].pivot_table(index="month", columns="route_or_line", values="ridership_average")


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
        if pd.notna(mon):
            F = mon / t["taps"].sum()
            summary[-1].update({
                "monthly_factor": F,
                "bridge_transfer_stations": x["odx"].sum() - x["taps"].sum() * F,
                "bridge_regular_stations": reg["odx"].sum() - reg["taps"].sum() * F,
                "bridge_total": t["odx"].sum() - mon,
            })
    pd.concat(station_rows).round(2).to_csv(OUT / "blue_stations_by_year.csv", index=False)
    s = pd.DataFrame(summary).round(2)
    s.to_csv(OUT / "blue_summary_by_year.csv", index=False)

    # 3) Effective monthly factor by month (monthly riders / gate taps)
    mw = monthly_weekday_avg()
    gse_years = sorted(int(f.stem[-4:]) for f in (RAW / "gse_hist" / "GSE_by_year").glob("GSE_*.csv") if int(f.stem[-4:]) >= 2018)
    taps_m = pd.concat([load_taps_by_month(y) for y in gse_years])
    fac = (mw[LINES] / taps_m[LINES]).dropna(how="all")
    fac.index = fac.index.astype(str)
    fac.round(3).rename_axis("month").to_csv(OUT / "monthly_factor_by_month.csv")

    # 4) Green Line: monthly factor vs model factor, gated vs ungated stops
    green = []
    for yr in [y for y in FALLS if y != 2017]:
        taps = load_taps(yr).loc["Green Line"]
        odx = stop[(stop["fall"] == yr) & (stop["route_name"] == "Green Line")].groupby("station")["average_ons"].sum()
        t = pd.concat([taps, odx.rename("odx")], axis=1).fillna(0)
        mon = monthly.get((yr, "Green Line"))
        gated = t[t["taps"] > 0]
        green.append({"fall": yr, "monthly": mon, "stop_level_total": t["odx"].sum(), "taps_total": t["taps"].sum(),
                      "monthly_factor": mon / t["taps"].sum(), "model_factor": t["odx"].sum() / t["taps"].sum(),
                      "gated_stations": len(gated), "ungated_stations": int((t["taps"] == 0).sum()),
                      "ungated_share_of_boardings_pct": t.loc[t["taps"] == 0, "odx"].sum() / t["odx"].sum() * 100})
    gs = pd.DataFrame(green).round(3)
    gs.to_csv(OUT / "green_summary_by_year.csv", index=False)

    pd.set_option("display.width", 200)
    print(line.round(1).to_string(index=False))
    print()
    print(s.to_string(index=False))
    print()
    print(gs.to_string(index=False))


if __name__ == "__main__":
    main()
