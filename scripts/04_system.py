"""Step 4: system-wide station test (Fall 2025) + rider-survey triangulation + hourly boardings.

Outputs (outputs/):
  system_stations_2025.csv  - every subway station x line: gate taps vs modeled boardings, plus survey transfer share
  station_hourly_2025.csv   - modeled weekday boardings per station and hour (for the animated map)
  station_hourly_taps_2025.csv - weekday gate taps per station and hour (30-minute periods rolled up)
  survey_transfer_check.csv - stations where both the survey and the tap/model test are available
"""
from pathlib import Path
import re

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "outputs"
YEAR = 2025


def open_station_days(g):
    """Keep only days each station was open (drop shutdown/diversion days with almost no taps)."""
    daily = g.groupby(["stop_id", "d"])["gated_entries"].sum()
    typical = daily.groupby("stop_id").transform("median")
    keep = daily[daily >= 0.2 * typical].reset_index()[["stop_id", "d"]]
    return g.merge(keep, on=["stop_id", "d"])


def taps_by_station_hour():
    g = pd.read_csv(RAW / "gse_hist" / "GSE_by_year" / f"GSE_{YEAR}.csv",
                    usecols=["service_date", "time_period", "gated_entries", "stop_id"])
    g["d"] = pd.to_datetime(g["service_date"])
    hol = set(USFederalHolidayCalendar().holidays(f"{YEAR}-01-01", f"{YEAR}-12-31"))
    hol |= {h + pd.Timedelta(days=1) for h in hol if h.month == 11 and h.day >= 22}
    g = g[(g["d"].dt.month >= 9) & (g["d"].dt.day_of_week < 5) & ~g["d"].isin(hol)]
    g = open_station_days(g)
    days = g.groupby("stop_id")["d"].nunique()
    g["hour"] = g["time_period"].str.slice(1, 3).astype(int)  # 30-minute periods rolled up to the hour
    t = g.groupby(["stop_id", "hour"])["gated_entries"].sum().unstack(fill_value=0)
    return t.div(days, axis=0)


def taps_by_station():
    g = pd.read_csv(RAW / "gse_hist" / "GSE_by_year" / f"GSE_{YEAR}.csv",
                    usecols=["service_date", "route_or_line", "gated_entries", "stop_id", "station_name"])
    g["d"] = pd.to_datetime(g["service_date"])
    hol = set(USFederalHolidayCalendar().holidays(f"{YEAR}-01-01", f"{YEAR}-12-31"))
    hol |= {h + pd.Timedelta(days=1) for h in hol if h.month == 11 and h.day >= 22}
    g = g[(g["d"].dt.month >= 9) & (g["d"].dt.day_of_week < 5) & ~g["d"].isin(hol)]
    g = open_station_days(g)
    days = g.groupby("stop_id")["d"].nunique()
    t = g.groupby(["stop_id", "route_or_line"])["gated_entries"].sum()
    t = t / t.index.get_level_values("stop_id").map(days).values
    return t.rename("taps")


def model_by_station():
    s = pd.read_csv(RAW / "fall2025_hour.csv")
    s = s[s["day_type_name"].str.lower() == "weekday"].copy()
    s["line"] = s["route_name"].str.replace(r"^Green Line [B-E]$", "Green Line", regex=True)
    names = s.groupby("parent_station")["stop_name"].first()
    odx = s.groupby(["parent_station", "line"])["average_ons"].sum().rename("odx")
    # hourly boardings per station (all lines), service hours 03:00..02:59
    s["hour"] = s["hour_of_service"].str.slice(0, 2).astype(int)
    hourly = s.groupby(["parent_station", "hour"])["average_ons"].sum().unstack(fill_value=0)
    return odx, names, hourly


def survey_transfer_share():
    d = pd.read_csv(RAW / "survey2025.csv")
    d = d[(d["aggregation_level"] == "Reporting Group") & d["service_mode"].str.contains("Rapid Transit")
          & (d["measure"] == "Access to Each MBTA Trip Leg") & (d["category"] == "Subway or Light Rail")].copy()
    d["line"] = d["service_mode"].str.replace("Rapid Transit or Bus Rapid Transit - ", "", regex=False)
    return d[["line", "reporting_group", "weighted_percent", "n", "margin_of_error"]]


def norm(x):
    return re.sub(r"[^a-z0-9]", "", str(x).lower().replace("street", "st").replace("square", "sq"))


def main():
    taps = taps_by_station()
    odx, names, hourly = model_by_station()
    t = pd.concat([taps, odx], axis=1).reset_index()
    t.columns = ["stop_id", "line", "taps", "odx"]
    t = t[t["line"].isin(["Red Line", "Orange Line", "Blue Line", "Green Line", "Mattapan Line"])]
    t["station"] = t["stop_id"].map(names)
    lines_per_station = t[(t["odx"] > 0)].groupby("stop_id")["line"].nunique()
    t["transfer_station"] = t["stop_id"].map(lines_per_station).fillna(1) > 1
    t["model_per_tap"] = t["odx"] / t["taps"].where(t["taps"] > 0)

    # Survey join: reporting groups are station names (heavy rail) or branches (light rail)
    sv = survey_transfer_share()
    sv["key"] = sv["line"].str.replace(" Line", "") + "|" + sv["reporting_group"].map(norm)
    t["key"] = t["line"].str.replace(" Line", "") + "|" + t["station"].map(norm)
    t = t.merge(sv[["key", "weighted_percent", "n", "margin_of_error"]], on="key", how="left")
    t = t.rename(columns={"weighted_percent": "survey_arrived_by_subway", "n": "survey_n", "margin_of_error": "survey_moe"})
    t = t.drop(columns="key").sort_values(["line", "odx"], ascending=[True, False])
    t.round(3).to_csv(OUT / "system_stations_2025.csv", index=False)

    chk = t.dropna(subset=["survey_arrived_by_subway", "model_per_tap"])
    chk = chk[chk["line"] != "Green Line"]  # Green surface stops are ungated; keep heavy rail for a clean test
    chk.round(3).to_csv(OUT / "survey_transfer_check.csv", index=False)
    r = chk["survey_arrived_by_subway"].corr(chk["model_per_tap"])
    rs = chk["survey_arrived_by_subway"].rank().corr(chk["model_per_tap"].rank())  # Spearman without scipy

    hourly.index.name = "stop_id"
    hourly.to_csv(OUT / "station_hourly_2025.csv")
    th = taps_by_station_hour()
    th.index.name = "stop_id"
    th.round(1).to_csv(OUT / "station_hourly_taps_2025.csv")

    print(f"stations x lines: {len(t)}, survey-matched heavy rail: {len(chk)}, pearson r={r:.2f}, spearman={rs:.2f}")
    print(t.sort_values("odx", ascending=False).head(25)[["station", "line", "taps", "odx", "model_per_tap",
                                                           "transfer_station", "survey_arrived_by_subway"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
