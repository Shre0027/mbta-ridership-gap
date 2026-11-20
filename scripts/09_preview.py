"""Early read on the newest fall, before its stop-level data is published.

Fall stop-level (ODX) data comes out months after the season ends, but monthly ridership and gate
taps are updated every month. So for the newest fall we can already ask: has the monthly method
changed, and what gap would we expect?

Method (per line, Sep-Oct weekdays, the months available first):
  expected stop-level(Y) = [stop-level(Y-1) / taps(Y-1)] x taps(Y)
  expected gap(Y)        = (monthly(Y) - expected stop-level(Y)) / expected stop-level(Y)
Backtest: run the same rule for every fall that DOES have stop-level data, and report the error.
That error is the honest +/- on the preview.

Output: outputs/preview.csv (backtest rows + preview rows), outputs/preview_summary.json
"""
import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
RAW = ROOT / "data" / "raw"
LINES = ["Red Line", "Orange Line", "Blue Line", "Green Line"]

spec = importlib.util.spec_from_file_location("an", ROOT / "scripts" / "02_analyze.py")
an = importlib.util.module_from_spec(spec)
spec.loader.exec_module(an)


def sep_oct(df, y):
    idx = [pd.Period(f"{y}-09"), pd.Period(f"{y}-10")]
    if not all(i in df.index for i in idx):
        return None
    return df.loc[idx, LINES].mean()


def main():
    stop = pd.read_csv(OUT / "line_gap_by_year.csv").dropna(subset=["stop_level"]).set_index(["fall", "line"])["stop_level"]
    falls = sorted(stop.index.get_level_values(0).unique())
    gse_years = sorted(int(p.stem[-4:]) for p in (RAW / "gse_hist" / "GSE_by_year").glob("GSE_*.csv"))
    mw = an.monthly_weekday_avg()
    taps, mon = {}, {}
    for y in sorted(set(falls) | set(gse_years)):
        if y < 2018 or y not in gse_years:
            continue
        t, m = sep_oct(an.load_taps_by_month(y), y), sep_oct(mw, y)
        if t is not None and m is not None:
            taps[y], mon[y] = t, m
    rows = []
    for y in sorted(taps):
        prev = y - 1
        if prev not in taps or prev not in falls or (y not in falls and y <= max(falls)):
            continue  # a preview only for falls newer than the latest published stop-level season
        for l in LINES:
            r = stop[(prev, l)] / taps[prev][l]
            exp = r * taps[y][l]
            act = stop.get((y, l))
            rows.append({"fall": y, "line": l, "kind": "backtest" if act is not None else "preview",
                         "model_factor_prev": round(r, 3), "monthly_factor": round(mon[y][l] / taps[y][l], 3),
                         "monthly_sepoct": round(mon[y][l]), "expected_stop": round(exp),
                         "expected_gap_pct": round(100 * (mon[y][l] - exp) / exp, 1),
                         "actual_stop": None if act is None else round(act),
                         "actual_gap_sepoct_pct": None if act is None else round(100 * (mon[y][l] - act) / act, 1)})
    df = pd.DataFrame(rows)
    df["error_pts"] = (df["expected_gap_pct"] - df["actual_gap_sepoct_pct"]).round(1)
    df.to_csv(OUT / "preview.csv", index=False)
    bt = df[df["kind"] == "backtest"]
    pv = df[df["kind"] == "preview"]
    summary = {}
    if len(pv):
        y = int(pv["fall"].iloc[0])
        mf_prev = {l: round(mon[y - 1][l] / taps[y - 1][l], 3) for l in LINES}
        summary = {"fall": y, "through": str(max(p for p in mw.index if p.year == y)),
                   "lines": {r.line: {"expected_gap_pct": r.expected_gap_pct, "monthly_factor": r.monthly_factor,
                                      "monthly_factor_prev": mf_prev[r.line],
                                      "backtest_mae_pts": round(bt.loc[bt["line"] == r.line, "error_pts"].abs().mean(), 1),
                                      "backtest_n": int((bt["line"] == r.line).sum())} for r in pv.itertuples()}}
    (OUT / "preview_summary.json").write_text(json.dumps(summary, indent=1))
    print(df.to_string(index=False))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
