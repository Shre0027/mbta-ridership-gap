"""Step 5: prepare map geometry + station data for the animated system map.

Reads official GTFS shapes/stops (data/raw/geo) and outputs/system_stations_2025.csv, station_hourly_2025.csv.
Writes outputs/map.json: projected, simplified line paths in official MBTA colors, stations with
modeled boardings, gate taps, model/tap ratio and 24 hourly boardings.
"""
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / "data" / "raw", ROOT / "outputs"

# One canonical shape per service (GTFS "canonical-" shapes), drawn in official MBTA line colors
CANON = {
    "Red-Ashmont": ("canonical-931_0010", "#DA291C"), "Red-Braintree": ("canonical-933_0009", "#DA291C"),
    "Mattapan": ("canonical-899_0005", "#DA291C"), "Orange": ("canonical-903_0018", "#ED8B00"),
    "Blue": ("canonical-946_0014", "#003DA5"), "Green-B": ("canonical-8000012", "#00843D"),
    "Green-C": ("canonical-8000005", "#00843D"), "Green-D": ("canonical-8000009", "#00843D"),
    "Green-E": ("canonical-8000018", "#00843D"),
}
# Green Line Extension stations have no fare gates (riders validate at fare vending machines);
# their small "gated entry" counts are validations, so no tap ratio is computed for them.
UNGATED = {"place-lech", "place-unsqu", "place-esomr", "place-gilmn", "place-mgngl", "place-balsq", "place-mdftf"}
BBOX = (-71.275, 42.198, -70.965, 42.447)  # lon/lat window around the subway
W = 1000
LAT0 = math.radians((BBOX[1] + BBOX[3]) / 2)
SX = W / ((BBOX[2] - BBOX[0]) * math.cos(LAT0))
H = round((BBOX[3] - BBOX[1]) * SX)


def proj(lon, lat):
    return (round((lon - BBOX[0]) * math.cos(LAT0) * SX, 1), round((BBOX[3] - lat) * SX, 1))


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy) or 1e-9
    dmax, idx = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * pts[i][0] - dx * pts[i][1] + x2 * y1 - y2 * x1) / norm
        if d > dmax:
            dmax, idx = d, i
    if dmax > eps:
        return rdp(pts[: idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


def inside(lon, lat, pad=0.0):
    return BBOX[0] - pad <= lon <= BBOX[2] + pad and BBOX[1] - pad <= lat <= BBOX[3] + pad


def main():
    rt = json.loads((RAW / "geo" / "rt_routes.geojson").read_text())
    shapes = {f["properties"]["shape_id"]: f["geometry"]["coordinates"] for f in rt["features"]}
    lines = []
    for key, (sid, color) in CANON.items():
        pts = rdp([proj(*c) for c in shapes[sid]], 0.6)
        lines.append({"id": key, "color": color, "pts": pts})

    # Commuter rail (context only): clip each canonical shape to the window
    cr = json.loads((RAW / "geo" / "cr_routes.geojson").read_text())
    seen, cr_paths = set(), []
    for f in sorted(cr["features"], key=lambda f: -f["properties"].get("Shape_Leng", 0)):
        p = f["properties"]
        if not str(p.get("shape_id", "")).startswith("canonical") or p["route_id"] in seen:
            continue
        seen.add(p["route_id"])
        coords = f["geometry"]["coordinates"]
        coords = [c for seg in coords for c in seg] if f["geometry"]["type"] == "MultiLineString" else coords
        run = []
        for lon, lat in coords:
            if inside(lon, lat, 0.03):
                run.append(proj(lon, lat))
            elif run:
                if len(run) > 1:
                    cr_paths.append(rdp(run, 0.8))
                run = []
        if len(run) > 1:
            cr_paths.append(rdp(run, 0.8))

    # Land: town polygons (coastline-clipped), projected and simplified; rendered as one fill
    towns = json.loads((RAW / "geo" / "towns.geojson").read_text())
    land, names_pos = [], []
    for f in towns["features"]:
        g = f["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            for ring in poly:
                pts = rdp([proj(*c) for c in ring[:-1]], 0.9)  # open the closed ring so RDP keeps its shape
                if len(pts) > 3:
                    land.append(pts)

    # Stations
    stops = json.loads((RAW / "geo" / "rt_stops.geojson").read_text())
    pos = {f["properties"]["stop_id"]: (f["properties"]["stop_name"], *proj(f["properties"]["stop_lon"], f["properties"]["stop_lat"]))
           for f in stops["features"]}
    sysst = pd.read_csv(OUT / "system_stations_2025.csv")
    hourly = pd.read_csv(OUT / "station_hourly_2025.csv", index_col=0)
    hourly.columns = [int(c) for c in hourly.columns]
    htaps = pd.read_csv(OUT / "station_hourly_taps_2025.csv", index_col=0)
    htaps.columns = [int(c) for c in htaps.columns]
    order = list(range(3, 24)) + [0, 1, 2]  # service day 3am..2am
    stations = []
    for sid, grp in sysst.groupby("stop_id"):
        if sid not in pos:
            continue
        name, x, y = pos[sid]
        taps, odx = grp["taps"].fillna(0).sum(), grp["odx"].fillna(0).sum()
        if sid in UNGATED:
            taps = 0
        hrs = [int(hourly.loc[sid, h]) if sid in hourly.index and h in hourly.columns else 0 for h in order]
        stations.append({
            "id": sid, "name": name, "x": x, "y": y,
            "lines": sorted(grp.loc[grp["odx"] > 0, "line"].str.replace(" Line", "").tolist()),
            "taps": round(taps), "odx": round(odx),
            "ratio": round(odx / taps, 2) if taps > 0 and odx > 0 else None,  # Mattapan: taps exist, trolley not in stop-level data
            "survey": None if grp["survey_arrived_by_subway"].isna().all() else round(float((grp["survey_arrived_by_subway"] * grp["odx"]).sum() / grp.loc[grp["survey_arrived_by_subway"].notna(), "odx"].sum()), 2),
            "transfer": bool(grp["transfer_station"].any()),
            "h": hrs,
            "t": [0 if sid in UNGATED or sid not in htaps.index or h not in htaps.columns else round(float(htaps.loc[sid, h])) for h in order],
        })
    out = {"w": W, "h": H, "land": land, "lines": lines, "cr": cr_paths, "stations": stations, "hours": order}
    (OUT / "map.json").write_text(json.dumps(out, separators=(",", ":")))
    print(f"map.json: {len(lines)} lines, {len(cr_paths)} CR paths, {len(stations)} stations, {W}x{H}, {len(json.dumps(out))/1024:.0f} KB")


if __name__ == "__main__":
    main()
