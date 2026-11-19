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
# Gated Station Entries - Historical (raw, unscaled fare-gate taps), zip of yearly CSVs
GSE_HIST_ITEM = "7859894afb5641ce91a2bb03599fdf5b"
GSE_YEARS = [2017, 2018, 2019, 2023, 2024, 2025]


def get_json(url, params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=120) as r:
        return json.load(r)


def fetch_layer(url, out):
    rows, offset = [], 0
    while True:
        d = get_json(url + "/query", {"where": "1=1", "outFields": "*", "f": "json",
                                       "resultOffset": offset, "resultRecordCount": 2000,
                                       "returnGeometry": "false"})
        feats = [f["attributes"] for f in d.get("features", [])]
        rows += feats
        if len(feats) < 2000 and not d.get("exceededTransferLimit"):
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
    for name, item in FILES.items():
        (RAW / name).write_bytes(download(item))
        print(f"{name}: downloaded")
    z = zipfile.ZipFile(io.BytesIO(download(GSE_HIST_ITEM)))
    out = RAW / "gse_hist"
    for yr in GSE_YEARS:
        z.extract(f"GSE_by_year/GSE_{yr}.csv", out)
        print(f"GSE_{yr}.csv: extracted")


if __name__ == "__main__":
    main()
