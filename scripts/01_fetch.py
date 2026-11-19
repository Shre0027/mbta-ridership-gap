"""Step 1: download the raw MBTA datasets from the MBTA Open Data Portal (ArcGIS).

Sources are all published by the MBTA Office of Performance Management & Innovation (OPMI).
Raw files land in data/raw/ (git-ignored, re-creatable by running this script).
"""
import csv
import io
import json
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
SVC = "https://services1.arcgis.com/ceiitspzDAHrdGO1/arcgis/rest/services"
ITEM = "https://www.arcgis.com/sharing/rest/content/items"

# Feature services (queried page by page)
LAYERS = {
    # Dataset A: monthly ridership by line (factor-scaled fare taps; also what MBTA reports to the NTD)
    "monthly_by_mode_line.csv": f"{SVC}/NTD_Reporting/FeatureServer/0",
    # Dataset B: stop-level ridership from the ODX trip model, by season
    "rail_stop_season.csv": f"{SVC}/Rail_Ridership_by_Season_Time_Period_RouteLine_and_Stop/FeatureServer/0",  # Fall 2017-2019
    "fall2023_stop.csv": f"{SVC}/Fall_2023_MBTA_Rail_Ridership_Data_by_SDP_Time_Period_Route_Line_and_Stop/FeatureServer/0",
    "fall2024_stop.csv": f"{SVC}/Fall_2024_MBTA_Rail_Ridership_by_SDP_Time_Period_Route_Line_and_Stop/FeatureServer/0",
}
# CSV items (downloaded as files)
FILES = {
    "fall2025_hour.csv": "6494749a29c648018820d0e49636205c",  # Fall 2025 stop-level, by hour (ODX)
}
# MBTA 2025 System-Wide Passenger Survey (rider census), all rows
SURVEY = f"{SVC}/MBTA_2025_System-Wide_Passenger_Survey/FeatureServer/0"
# Official GTFS route shapes and stops (MassDOT "MBTA Systemwide GTFS Map")
GTFS_MAP = f"{SVC}/MBTA_Systemwide_GTFS_Map_WFL1/FeatureServer"
GEO_LAYERS = {"rt_routes.geojson": 2, "cr_routes.geojson": 4, "rt_stops.geojson": 6}
# MassGIS town boundaries around Boston (land shape for the map background)
TOWNS = "https://services.arcgis.com/kbDdtKcFi2adamXa/arcgis/rest/services/Massachusetts_Town_Boundaries/FeatureServer/3"
# Gated Station Entries - Historical (raw, unscaled fare-gate taps), zip of yearly CSVs
GSE_HIST_ITEM = "7859894afb5641ce91a2bb03599fdf5b"
GSE_FIRST_YEAR = 2017  # every yearly file from here to the latest is extracted


def get_json(url, params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=120) as r:
        return json.load(r)


def fetch_layer(url, out, page=2000):
    rows, offset = [], 0
    while True:
        d = get_json(url + "/query", {"where": "1=1", "outFields": "*", "f": "json",
                                       "resultOffset": offset, "resultRecordCount": page,
                                       "returnGeometry": "false"})
        feats = [f["attributes"] for f in d.get("features", [])]
        rows += feats
        if not feats or (len(feats) < page and not d.get("exceededTransferLimit")):
            break
        offset += len(feats)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{out.name}: {len(rows):,} rows")


def download(item_id):
    with urllib.request.urlopen(f"{ITEM}/{item_id}/data", timeout=600) as r:
        return r.read()


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in LAYERS.items():
        fetch_layer(url, RAW / name)
    fetch_layer(SURVEY, RAW / "survey2025.csv", page=1000)
    (RAW / "geo").mkdir(exist_ok=True)
    for name, layer in GEO_LAYERS.items():
        with urllib.request.urlopen(f"{GTFS_MAP}/{layer}/query?" + urllib.parse.urlencode(
                {"where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson", "geometryPrecision": 5}), timeout=300) as r:
            (RAW / "geo" / name).write_bytes(r.read())
        print(f"geo/{name}: downloaded")
    with urllib.request.urlopen(f"{TOWNS}/query?" + urllib.parse.urlencode(
            {"where": "1=1", "geometry": "-71.33,42.15,-70.90,42.50", "geometryType": "esriGeometryEnvelope", "inSR": 4326,
             "spatialRel": "esriSpatialRelIntersects", "outFields": "TOWN", "outSR": 4326, "maxAllowableOffset": 0.0004,
             "geometryPrecision": 5, "f": "geojson"}), timeout=300) as r:
        (RAW / "geo" / "towns.geojson").write_bytes(r.read())
    print("geo/towns.geojson: downloaded")
    for name, item in FILES.items():
        (RAW / name).write_bytes(download(item))
        print(f"{name}: downloaded")
    z = zipfile.ZipFile(io.BytesIO(download(GSE_HIST_ITEM)))
    out = RAW / "gse_hist"
    for name in sorted(z.namelist()):
        if name.startswith("GSE_by_year/GSE_") and name.endswith(".csv") and int(name[-8:-4]) >= GSE_FIRST_YEAR:
            z.extract(name, out)
            print(f"{name}: extracted")


if __name__ == "__main__":
    main()
