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

data = {
    "line": clean(line[["fall", "line", "stop_level", "monthly", "gap_pct"]].to_dict("records")),
    "stations": clean(stations[["fall", "station", "taps", "odx"]].round(0).to_dict("records")),
    "summary": clean(summary.to_dict("records")),
    "factor": clean(factor.round(3).to_dict("records")),
    "green": clean(green.to_dict("records")),
}
html = (ROOT / "site" / "template.html").read_text()
html = html.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")))
(ROOT / "index.html").write_text(html)
print("index.html written")
