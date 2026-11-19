"""Step 7: test a proposed fix, out of sample.

Question: if the monthly (tap-based) method recalibrated its factor each fall against the trip model,
how close would it land to the model the following fall, compared with today's monthly dataset?

For each pair of consecutive comparable falls (calibrate on A, test on B) and each heavy-rail line:
  single factor   F = model_A / taps_A                     -> predict taps_B x F
  station factors f_s = model_A,s / taps_A,s per station   -> predict sum_s taps_B,s x f_s
  monthly today   the published monthly dataset for fall B
Errors are against the trip model for fall B. Writes outputs/fix_test.csv.
"""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
spec = importlib.util.spec_from_file_location("an", ROOT / "scripts" / "02_analyze.py")
an = importlib.util.module_from_spec(spec)
spec.loader.exec_module(an)

PAIRS = [(2017, 2018), (2018, 2019), (2019, 2023), (2023, 2024), (2024, 2025)]
LINES = ["Red Line", "Orange Line", "Blue Line"]  # Green excluded: most surface stops have no gates


def main():
    stop, mon = an.load_stop_level(), an.load_monthly()
    taps = {y: an.load_taps(y) for y in sorted({y for p in PAIRS for y in p})}

    def table(y, line):
        t = taps[y].loc[line] if line in taps[y].index.get_level_values(0) else pd.Series(dtype=float)
        o = stop[(stop["fall"] == y) & (stop["route_name"] == line)].groupby("station")["average_ons"].sum()
        return pd.concat([t.rename("taps"), o.rename("odx")], axis=1).fillna(0)

    rows = []
    for a, b in PAIRS:
        for line in LINES:
            A, B = table(a, line), table(b, line)
            F = A["odx"].sum() / A["taps"].sum()
            f = (A["odx"] / A["taps"]).where(A["taps"] > 0).reindex(B.index)
            pred_station = (B["taps"] * f).fillna(B["taps"] * F).sum()
            pred_single = B["taps"].sum() * F
            act, m = B["odx"].sum(), mon.get((b, line))
            rows.append({"calibrate_on": a, "test_on": b, "line": line, "model": round(act),
                         "refreshed_single_err_pct": (pred_single - act) / act * 100,
                         "refreshed_station_err_pct": (pred_station - act) / act * 100,
                         "monthly_today_err_pct": (m - act) / act * 100 if pd.notna(m) else None})
    r = pd.DataFrame(rows).round(1)
    r.to_csv(OUT / "fix_test.csv", index=False)
    summ = r.groupby("line")[["monthly_today_err_pct", "refreshed_single_err_pct", "refreshed_station_err_pct"]].apply(lambda d: d.abs().mean()).round(1)
    print(r.to_string(index=False))
    print("\nmean absolute error (%)\n", summ.to_string())


if __name__ == "__main__":
    main()
