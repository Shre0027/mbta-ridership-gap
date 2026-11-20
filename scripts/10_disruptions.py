"""Service disruptions from the MBTA's own alert archive, matched against the ridership comparison.

Input : data/raw/alerts_dl/**  (MBTA GTFS-Realtime alerts archive, 2020-2025, OPMI)
        data/raw/gse_hist      (daily gate taps), outputs/monthly_factor_by_month.csv
Output: outputs/disruption_days.csv   one row per line and weekday with a daytime shuttle/suspension
        outputs/disruption_summary.csv per line and fall: share of weekdays disrupted, and the gap
                                       recomputed on undisrupted weekdays only

A weekday counts as disrupted for a line when an alert with effect SHUTTLE or SUSPENSION on that
line is active across the morning peak (8-9 AM local) and touches at least 2 of the line's stations.
Evening-only and weekend work doesn't count.

The monthly dataset is published only as monthly averages, so it can't be filtered by day. Instead:
monthly = taps x factor, and the factor for each month is known (monthly / taps). The undisrupted
version of the monthly figure = that month's factor x average taps on undisrupted weekdays.
The stop-level side can't be filtered either (the MBTA publishes season averages only), so the
"clean" gap is a sensitivity check, not a replacement.
"""
import glob
from pathlib import Path

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "outputs"
LINES = ["Red Line", "Orange Line", "Blue Line", "Green Line"]
TZ = "America/New_York"


def line_of(route):
    r = str(route)
    if r == "Red":
        return "Red Line"
    if r == "Orange":
        return "Orange Line"
    if r == "Blue":
        return "Blue Line"
    if r.startswith("Green"):
        return "Green Line"
    return None


def load_alerts():
    files = [f for f in glob.glob(str(RAW / "alerts_dl" / "**" / "*.csv"), recursive=True)
             if any(f"{y}" in Path(f).name for y in range(2020, 2030))]
    keep = ["alert_id", "effect_detail", "header", "last_modified_dt", "active_period_start_dt", "active_period_end_dt", "route_id", "route_type", "stop_id"]
    parts = []
    for f in sorted(files):
        mo = Path(f).name.replace("alerts_", "").replace("_ALERTS", "")[:7].replace("_", "-")
        if int(mo[5:7]) < 8:  # only fall months matter here (Aug for periods that start early)
            continue
        d = pd.read_csv(f, usecols=keep, low_memory=False)
        d = d[d["route_type"].isin([0, 1]) & d["effect_detail"].isin(["SHUTTLE", "SUSPENSION"])]
        parts.append(d)
    a = pd.concat(parts, ignore_index=True)
    a["line"] = a["route_id"].map(line_of)
    a = a.dropna(subset=["line", "active_period_start_dt", "active_period_end_dt"])
    a["s"] = pd.to_datetime(a["active_period_start_dt"], utc=True).dt.tz_convert(TZ)
    a["e"] = pd.to_datetime(a["active_period_end_dt"], utc=True).dt.tz_convert(TZ)
    # The archive carries "ghost" periods: alerts that ended long ago (e.g. a Feb 5-14 shuttle) still get a
    # daily 00:30-16:30 active period months later, with no edit since. Drop periods that start more than
    # 60 days after the alert was last modified; real planned work is re-edited as it approaches.
    lm = pd.to_datetime(a["last_modified_dt"], utc=True).dt.tz_convert(TZ)
    a["stale"] = (a["s"] - lm) > pd.Timedelta(days=60)
    # Same ghosts, edited more recently: a 00:30-01:59 local start that stops mid-afternoon (real all-day work
    # runs to end of service, ~1-2:30 AM).
    a["stale"] |= (a["s"].dt.hour <= 1) & ((a["e"] - a["s"]) < pd.Timedelta(hours=18))
    print(f"alert periods kept: {(~a['stale']).sum():,}; dropped as stale: {a['stale'].sum():,}")
    return a[~a["stale"]]


def station_map():
    st = pd.read_csv(RAW / "gtfs" / "stops.txt", usecols=["stop_id", "parent_station"], dtype=str)
    st["station"] = st["parent_station"].fillna(st["stop_id"])
    return dict(zip(st["stop_id"], st["station"]))


def disrupted_days(a):
    smap = station_map()
    a["station"] = a["stop_id"].astype(str).map(smap)
    rows = []
    for (aid, s, e, line), g in a.groupby(["alert_id", "s", "e", "line"]):
        n_st = g["station"].nunique()
        if n_st < 2:
            continue
        for day in pd.date_range(s.normalize(), e.normalize(), freq="D"):
            if day.dayofweek >= 5:
                continue
            if s <= day + pd.Timedelta(hours=8) and e >= day + pd.Timedelta(hours=9):
                rows.append({"date": day.date(), "line": line, "alert_id": aid, "stations": n_st, "header": g["header"].iloc[0][:160]})
    d = pd.DataFrame(rows)
    if d.empty:
        return d
    # one row per line-day: keep the widest alert that day
    return d.sort_values("stations", ascending=False).drop_duplicates(["date", "line"]).sort_values(["date", "line"])


def daily_line_taps(year):
    g = pd.read_csv(RAW / "gse_hist" / "GSE_by_year" / f"GSE_{year}.csv", usecols=["service_date", "route_or_line", "gated_entries"])
    g["date"] = pd.to_datetime(g["service_date"]).dt.date
    return g.groupby(["date", "route_or_line"])["gated_entries"].sum().unstack()


def main():
    a = load_alerts()
    dd = disrupted_days(a)
    dd.to_csv(OUT / "disruption_days.csv", index=False)
    bad = set(zip(dd["date"], dd["line"])) if len(dd) else set()
    factor = pd.read_csv(OUT / "monthly_factor_by_month.csv")
    factor["month"] = pd.PeriodIndex(factor["month"], freq="M")
    factor = factor.set_index("month")
    stop = pd.read_csv(OUT / "line_gap_by_year.csv").set_index(["fall", "line"])
    years = sorted({d.year for d in dd["date"]}) if len(dd) else []
    rows = []
    for y in years:
        hol = set(USFederalHolidayCalendar().holidays(f"{y}-01-01", f"{y}-12-31").date)
        hol |= {(pd.Timestamp(f"{y}-11-01") + pd.offsets.WeekOfMonth(week=3, weekday=3) + pd.Timedelta(days=1)).date()}
        days = [d.date() for d in pd.date_range(f"{y}-09-01", f"{y}-12-31") if d.dayofweek < 5 and d.date() not in hol]
        taps = daily_line_taps(y)
        for l in LINES:
            dis = [d for d in days if (d, l) in bad]
            clean = [d for d in days if (d, l) not in bad and d in taps.index]
            num_all = num_clean = n_all = n_clean = 0
            for m in range(9, 13):
                p = pd.Period(f"{y}-{m:02d}", freq="M")
                if p not in factor.index:
                    continue
                f = factor.loc[p, l]
                dm = [d for d in days if d.month == m and d in taps.index]
                cm = [d for d in clean if d.month == m]
                if dm:
                    num_all += f * taps.loc[dm, l].sum(); n_all += len(dm)
                if cm:
                    num_clean += f * taps.loc[cm, l].sum(); n_clean += len(cm)
            st = stop["stop_level"].get((y, l))
            row = {"fall": y, "line": l, "weekdays": len(days), "disrupted_weekdays": len(dis),
                   "disrupted_share_pct": round(100 * len(dis) / len(days), 1),
                   "monthly_equiv_all": round(num_all / n_all) if n_all else None,
                   "monthly_equiv_clean": round(num_clean / n_clean) if n_clean else None}
            if st == st and st is not None and n_all and n_clean:
                row["stop_level"] = round(st)
                row["gap_all_pct"] = round(100 * (row["monthly_equiv_all"] - st) / st, 1)
                row["gap_clean_pct"] = round(100 * (row["monthly_equiv_clean"] - st) / st, 1)
            rows.append(row)
    s = pd.DataFrame(rows)
    s.to_csv(OUT / "disruption_summary.csv", index=False)
    print(s.to_string(index=False))
    if len(dd):
        big = dd.merge(dd.groupby(["alert_id", "line"]).size().rename("n").reset_index(), on=["alert_id", "line"])
        print(big.drop_duplicates(["alert_id", "line"]).query("n >= 3").sort_values("date")[["date", "line", "n", "stations", "header"]].to_string(index=False))


if __name__ == "__main__":
    main()
