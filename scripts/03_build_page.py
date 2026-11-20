"""Step 3: build the data story page (index.html) from outputs/ and site/template.html."""
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def clean(records):
    return [{k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()} for r in records]


line = pd.read_csv(OUT / "line_gap_by_year.csv").dropna(subset=["gap_pct"])
stations = pd.read_csv(OUT / "blue_stations_by_year.csv")
summary = pd.read_csv(OUT / "blue_summary_by_year.csv")
factor = pd.read_csv(OUT / "monthly_factor_by_month.csv")
green = pd.read_csv(OUT / "green_summary_by_year.csv")
daytype = pd.read_csv(OUT / "line_gap_by_daytype.csv")
fix = pd.read_csv(OUT / "fix_test.csv")
bus = pd.read_csv(OUT / "bus_baseline.csv").dropna(subset=["gap_sepdec_pct"]) if (OUT / "bus_baseline.csv").exists() else pd.DataFrame()
win = pd.read_csv(OUT / "window_sensitivity.csv") if (OUT / "window_sensitivity.csv").exists() else pd.DataFrame()
mapdata = json.loads((OUT / "map.json").read_text())
chk = pd.read_csv(OUT / "survey_transfer_check.csv")
base = chk[chk["survey_arrived_by_subway"] < 0.05]
K = float(base["odx"].sum() / base["taps"].sum())  # normal non-tap uplift at stations with almost no transfers
HUBS = ["Downtown Crossing", "Park Street", "State", "Government Center"]
three = []
for st in mapdata["stations"]:
    if st["name"] in HUBS:
        three.append({"name": st["name"], "lines": st["lines"], "taps": st["taps"], "odx": st["odx"], "survey": st["survey"],
                      "taps_est": round(K * st["taps"]), "transfer_est": round(K * st["taps"] / (1 - st["survey"]) - K * st["taps"])})
three.sort(key=lambda r: -r["odx"])

def annual_block():
    """Blue Line riders between the two counts, as a daily and a rough yearly figure.
    Yearly = latest fall's weekday / Saturday / Sunday gaps x that year's day counts (holidays as Sundays).
    Fall is usually a busier season, so this is an upper-leaning, rough figure, and the page says so."""
    from pandas.tseries.holiday import USFederalHolidayCalendar
    b = daytype[daytype["line"] == "Blue Line"].copy()
    y = int(b["fall"].max())
    r = b[b["fall"] == y].set_index("day_type")
    g = r["stop_level"] - r["monthly"]
    days = pd.date_range(f"{y}-01-01", f"{y}-12-31")
    hol = set(USFederalHolidayCalendar().holidays(f"{y}-01-01", f"{y}-12-31"))
    wk = sum(1 for d in days if d.dayofweek < 5 and d not in hol)
    sat = sum(1 for d in days if d.dayofweek == 5)
    sun = sum(1 for d in days if d.dayofweek == 6) + len(hol)
    total = g["weekday"] * wk + g["saturday"] * sat + g["sunday"] * sun
    return {"fall": y, "weekday_riders": int(round(g["weekday"], -2)), "per_year": round(float(total) / 1e6, 1)}


def disruption_block():
    fs, fd = OUT / "disruption_summary.csv", OUT / "disruption_days.csv"
    if not fs.exists():
        return {}
    from pandas.tseries.holiday import USFederalHolidayCalendar
    sm = pd.read_csv(fs).dropna(subset=["gap_all_pct"])
    dd = pd.read_csv(fd)
    out = {"rows": clean(sm.to_dict("records")), "days": {}, "headers": {}}
    for y in sorted(sm["fall"].unique()):
        hol = set(USFederalHolidayCalendar().holidays(f"{y}-01-01", f"{y}-12-31").strftime("%Y-%m-%d"))
        hol.add((pd.Timestamp(f"{y}-11-01") + pd.offsets.WeekOfMonth(week=3, weekday=3) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
        wk = [d.strftime("%Y-%m-%d") for d in pd.date_range(f"{y}-09-01", f"{y}-12-31") if d.dayofweek < 5 and d.strftime("%Y-%m-%d") not in hol]
        out["days"][str(y)] = {"weekdays": wk}
        for l in sm["line"].unique():
            sel = dd[(dd["line"] == l) & dd["date"].isin(wk)]
            out["days"][str(y)][l] = [wk.index(d) for d in sel["date"]]
            out["headers"].update({f"{l}|{d}": h for d, h in zip(sel["date"], sel["header"])})
    return out


data = {
    "schema": 3,
    "build": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
    "updated": pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d"),
    "latest_month": str(factor["month"].max()),
    "line": clean(line[["fall", "line", "stop_level", "monthly", "gap_pct"]].to_dict("records")),
    "stations": clean(stations[["fall", "station", "taps", "odx"]].round(0).to_dict("records")),
    "summary": clean(summary.to_dict("records")),
    "factor": clean(factor.round(3).to_dict("records")),
    "green": clean(green.to_dict("records")),
    "k": round(K, 3),
    "fix": clean(fix.to_dict("records")),
    "daytype": clean(daytype[daytype["line"] == "Blue Line"][["fall", "day_type", "gap_pct"]].to_dict("records")),
    "three": three,
    "disrupt": disruption_block(),
    "annual": annual_block(),
    "preview": json.loads((OUT / "preview_summary.json").read_text()) if (OUT / "preview_summary.json").exists() else {},
    "bus": clean(bus[["fall", "apc_all", "monthly_all_bus", "monthly_all_bus_sepnov", "gap_sepdec_pct", "gap_sepnov_pct"]].to_dict("records")) if len(bus) else [],
    "window": clean(win.to_dict("records")) if len(win) else [],
}
(OUT / "story_data.json").write_text(json.dumps(data, separators=(",", ":")))
html = (ROOT / "site" / "template.html").read_text()
html = html.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
html = html.replace("/*__MAP__*/null", json.dumps(mapdata, separators=(",", ":")))
(ROOT / "index.html").write_text(html)
if (OUT / "trains.json").exists():  # served next to the page; loaded at runtime
    (ROOT / "trains.json").write_text((OUT / "trains.json").read_text())
print("index.html written")
