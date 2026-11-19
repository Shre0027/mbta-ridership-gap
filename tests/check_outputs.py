"""Sanity and reproducibility checks on the pipeline outputs. Run after the build:

  python tests/check_outputs.py

The monthly GitHub Action runs this before committing; any failure stops the refresh,
so a broken upstream file can't silently change the published numbers.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        fails.append(name)


line = pd.read_csv(OUT / "line_gap_by_year.csv")
f23 = line[line["fall"] == 2023].set_index("line")["gap_pct"].round(1).to_dict()
check("Fall 2023 reproduces the Feb 2025 forum figures exactly",
      f23 == {"Blue Line": -23.4, "Green Line": -16.1, "Orange Line": 5.2, "Red Line": -7.4}, str(f23))

blue = line[line["line"] == "Blue Line"].dropna(subset=["gap_pct"])
check("Blue Line monthly undercount in every compared fall", (blue["gap_pct"] < 0).all(), blue["gap_pct"].tolist())

s = pd.read_csv(OUT / "blue_summary_by_year.csv").dropna(subset=["monthly"])
resid = (s["bridge_transfer_stations"] + s["bridge_regular_stations"] - s["bridge_total"]).abs().max()
check("Bridge parts sum exactly to the gap (every season)", resid < 1, f"max residual {resid:.3f}")
check("Transfer stations always push the model up", (s["bridge_transfer_stations"] > 0).all())

d = json.loads((OUT / "story_data.json").read_text())
T = d["three"]
odx = sum(r["odx"] for r in T)
est = sum(r["taps_est"] + r["transfer_est"] for r in T)
check("Four hubs present in the survey test", len(T) == 4, [r["name"] for r in T])
check("Taps + survey within 10% of the model at the hubs", abs(est - odx) / odx < 0.10, f"{est} vs {odx}")
check("Normal uplift k in a plausible range (1.0-1.5)", 1.0 <= d["k"] <= 1.5, d["k"])

m = json.loads((OUT / "map.json").read_text())
gated = [x for x in m["stations"] if x["ratio"]]
check("Map has 100+ stations and 9 line shapes", len(m["stations"]) >= 100 and len(m["lines"]) == 9)
check("No gated station below 0.8x (would signal a broken join)", min(x["ratio"] for x in gated) >= 0.8,
      min((x["ratio"], x["name"]) for x in gated))
check("Every station has 24 hourly values", all(len(x["h"]) == 24 for x in m["stations"]))

tr = json.loads((ROOT / "trains.json").read_text())
trips = tr["trips"]
mono = all(all(v >= 0 for v in t[3::2]) for t in trips)
dur = [(t[2], t[2] + sum(t[3::2])) for t in trips]
peak = max(sum(1 for a, b in dur if a <= x <= b) for x in range(6 * 3600, 22 * 3600, 600))
check("Train schedule: 1,000+ trips, times never go backwards", len(trips) > 1000 and mono, len(trips))
check("Train schedule: 60-180 trains running at the busiest moment", 60 <= peak <= 180, peak)

print(f"\n{len(fails)} failed" if fails else "\nall checks passed")
sys.exit(1 if fails else 0)
