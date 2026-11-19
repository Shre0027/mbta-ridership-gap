"""Step 6: real scheduled train positions from the MBTA GTFS feed, for the animated map.

For one representative weekday in the current schedule, every rapid-transit trip (Red, Mattapan, Orange,
Blue, Green B/C/D/E) is turned into a list of (time, distance-along-track) points using its own GTFS
shape and the scheduled stop times. The page interpolates between them, so each dot on the map is an
actual scheduled train at its scheduled position.

Writes outputs/trains.json.
"""
import datetime as dt
import importlib.util
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw" / "gtfs", ROOT / "outputs"
spec = importlib.util.spec_from_file_location("geo", ROOT / "scripts" / "05_geo.py")
geo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geo)

ROUTES = {"Red": "#DA291C", "Mattapan": "#DA291C", "Orange": "#ED8B00", "Blue": "#003DA5",
          "Green-B": "#00843D", "Green-C": "#00843D", "Green-D": "#00843D", "Green-E": "#00843D"}


def pick_date():
    """First Tuesday in the feed that runs regular (non-exception) weekday service."""
    cal = pd.read_csv(RAW / "calendar.txt", dtype={"start_date": str, "end_date": str})
    start = dt.datetime.strptime(str(cal["start_date"].min()), "%Y%m%d").date()
    d = start + dt.timedelta(days=(1 - start.weekday()) % 7 + 14)  # a Tuesday two weeks in, clear of holiday weeks
    cd = pd.read_csv(RAW / "calendar_dates.txt", dtype={"date": str})
    while d.strftime("%Y%m%d") in set(cd["date"]):  # skip dates with schedule exceptions
        d += dt.timedelta(days=7)
    return d


def active_services(d):
    cal = pd.read_csv(RAW / "calendar.txt", dtype={"start_date": str, "end_date": str})
    ds = d.strftime("%Y%m%d")
    day = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][d.weekday()]
    on = set(cal[(cal[day] == 1) & (cal["start_date"] <= ds) & (cal["end_date"] >= ds)]["service_id"])
    ex = pd.read_csv(RAW / "calendar_dates.txt", dtype={"date": str})
    ex = ex[ex["date"] == ds]
    on |= set(ex[ex["exception_type"] == 1]["service_id"])
    on -= set(ex[ex["exception_type"] == 2]["service_id"])
    return on


def secs(t):
    h, m, s = (int(x) for x in t.split(":"))
    return h * 3600 + m * 60 + s


def project_onto(poly, cum, x, y, start_seg=0):
    """Distance along poly of the closest point to (x, y), searching forward from start_seg."""
    best, best_d, best_seg = None, 1e18, start_seg
    for i in range(start_seg, len(poly) - 1):
        (x1, y1), (x2, y2) = poly[i], poly[i + 1]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy or 1e-9
        t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / L2))
        px, py = x1 + t * dx, y1 + t * dy
        dd = (px - x) ** 2 + (py - y) ** 2
        if dd < best_d:
            best_d, best, best_seg = dd, cum[i] + t * math.sqrt(L2), i
    return best, best_seg


def main():
    d = pick_date()
    services = active_services(d)
    trips = pd.read_csv(RAW / "trips.txt", low_memory=False, dtype=str)
    trips = trips[trips["route_id"].isin(ROUTES) & trips["service_id"].isin(services)]
    st = pd.read_csv(RAW / "stop_times.txt", dtype=str, usecols=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"])
    st = st[st["trip_id"].isin(set(trips["trip_id"]))].copy()
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    stops = pd.read_csv(RAW / "stops.txt", dtype=str, usecols=["stop_id", "stop_lat", "stop_lon"]).set_index("stop_id")
    shp = pd.read_csv(RAW / "shapes.txt", dtype={"shape_id": str})
    shp = shp[shp["shape_id"].isin(set(trips["shape_id"]))].sort_values(["shape_id", "shape_pt_sequence"])

    shapes, shape_idx = [], {}
    for sid, g in shp.groupby("shape_id"):
        pts = geo.rdp([geo.proj(lon, lat) for lon, lat in zip(g["shape_pt_lon"], g["shape_pt_lat"])], 0.4)
        cum = [0.0]
        for i in range(1, len(pts)):
            cum.append(cum[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
        shape_idx[sid] = len(shapes)
        shapes.append({"pts": pts, "cum": cum})

    out_trips = []
    tinfo = trips.set_index("trip_id")
    for tid, g in st.sort_values(["trip_id", "stop_sequence"]).groupby("trip_id"):
        sid = tinfo.loc[tid, "shape_id"]
        if sid not in shape_idx:
            continue
        sh = shapes[shape_idx[sid]]
        seg, pts = 0, []
        for _, r in g.iterrows():
            x, y = geo.proj(float(stops.loc[r["stop_id"], "stop_lon"]), float(stops.loc[r["stop_id"], "stop_lat"]))
            dist, seg = project_onto(sh["pts"], sh["cum"], x, y, seg)
            a, b = secs(r["arrival_time"]), secs(r["departure_time"])
            pts.append((a, dist))
            if b - a >= 30:
                pts.append((b, dist))  # dwell only when it is long enough to see
        t0 = pts[0][0]
        L = sh["cum"][-1] or 1
        # compact: [shape, route, start (s), dt1, dd1, dt2, dd2, ...] with time deltas in seconds
        # and distance deltas in permille of the shape length
        flat, pt, pd_ = [], t0, 0
        for t, dd in pts:
            q = round(dd / L * 1000)
            flat += [t - pt, q - pd_]
            pt, pd_ = t, q
        out_trips.append([shape_idx[sid], list(ROUTES).index(tinfo.loc[tid, "route_id"]), t0] + flat)

    payload = {
        "date": d.isoformat(), "feed": "MBTA GTFS (current schedule)",
        "routes": list(ROUTES), "colors": list(ROUTES.values()),
        "shapes": [s["pts"] for s in shapes],
        "trips": out_trips,
    }
    (OUT / "trains.json").write_text(json.dumps(payload, separators=(",", ":")))
    dur = [t[2] + sum(t[3::2]) for t in out_trips]
    peak = max(sum(1 for t, e in zip(out_trips, dur) if t[2] <= s <= e) for s in range(5 * 3600, 25 * 3600, 300))
    print(f"trains.json: {d} · {len(out_trips)} trips · {len(shapes)} shapes · peak {peak} trains running · {len(json.dumps(payload))/1024:.0f} KB")


if __name__ == "__main__":
    main()
