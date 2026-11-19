# MBTA Ridership Gap

**Two official MBTA ridership datasets disagree about how many people ride the Blue Line — by up to 23%. This project reconciles them and finds where the gap comes from.**

**→ Read the interactive data story: [shre0027.github.io/mbta-ridership-gap](https://shre0027.github.io/mbta-ridership-gap/)**

## The problem

The MBTA publishes two "official" ridership numbers for the same subway lines:

| | Dataset A — Monthly Ridership by Mode and Line | Dataset B — Rail Ridership by Season, Route and Stop |
|---|---|---|
| Built from | Fare-gate taps × fixed scaling factors | ODX trip model (taps + trip chaining + faregate passenger counters) |
| Grain | Line × month | Stop × direction × time period, one fall season |
| Used for | National Transit Database (NTD) reporting | Service planning |

In February 2025 a developer [asked on the MBTA Developers forum](https://groups.google.com/g/massdotdevelopers/c/u_JG__eP_ME) why Fall 2023 Blue Line ridership differed by 23.4%. MBTA's Office of Performance Management & Innovation (OPMI) replied that the methods differ, that **East Boston development** was the likely Blue Line driver, and that aligning the datasets is ongoing work.

## What I found

**1. The gap is not a one-off.** It appears in every fall season both datasets cover (weekday riders, monthly vs stop-level):

| Fall | Red | Orange | Blue | Green |
|---|---|---|---|---|
| 2018 | -6.5% | +3.0% | **-15.1%** | +6.5% |
| 2019 | -0.2% | +9.8% | **-10.6%** | +23.7% |
| 2023 | -7.4% | +5.2% | **-23.4%** | -16.1% |
| 2024 | -15.6% | -1.1% | **-21.9%** | +15.4% |
| 2025 | -10.4% | +1.8% | **-19.7%** | +15.9% |

The Blue Line is the only line the monthly dataset undercounts every single year.

**2. The Blue Line gap sits downtown, not in East Boston.** Comparing raw gate taps (the input to Dataset A) with modeled boardings (Dataset B), station by station:

- At every regular Blue Line station — Maverick, Airport, Wonderland, Revere Beach — the model is a steady **~1.03–1.24× the taps**. That is the normal allowance for riders who don't tap.
- At the two transfer stations, **State and Government Center**, the model counts **~21,000–29,000 Blue Line boardings a day against only ~1,200–8,300 taps.** Riders transferring from Orange or Green never tap again, and the fixed survey "split factor" credits Blue with only ~10% of Government Center entries.
- These two stations hold **34–38% of all Blue Line boardings in every year from 2017 to 2025.**

**3. One real shift over time, and one silent swap.**
- **After COVID (helps explain the gap):** the model's uplift at regular stations rose from ~1.03–1.07× (2017–19) to ~1.16–1.24× (2023–25), consistent with OPMI's note that the model now uses faregate passenger counters to catch riders who don't tap. A fixed factor in the monthly method would not follow it — which fits the gap roughly doubling after 2019.
- **March 6, 2019 (data quality finding):** in the Gated Station Entries data, the Government Center split flipped overnight from **90% Blue / 10% Green to 10% Blue / 90% Green**, with no note in the data or documentation. Taps credited to the Blue Line there fell from ~6,700–7,000/day to ~400–800/day. This changes the tap data, not the gap between the two ridership datasets (the gap actually shrank from 2018 to 2019) — but anyone trending station entries across that date would see a ridership collapse that never happened.

**4. The bridge: the gap, split exactly into two parts.** Dividing the monthly Blue Line number by Blue Line gate taps gives the single factor it effectively applies (1.21–1.43×). With it, every season's gap splits exactly:

| Fall | Monthly (A) | + State & Gov Center | − Regular stations | = Stop-level (B) |
|---|---|---|---|---|
| 2018 | 65,961 | +18,303 | −6,616 | 77,647 |
| 2019 | 70,171 | +25,765 | −17,454 | 78,483 |
| 2023 | 48,385 | +19,609 | −4,801 | 63,193 |
| 2024 | 52,059 | +21,429 | −6,841 | 66,647 |
| 2025 | 50,339 | +19,864 | −7,507 | 62,695 |

The transfer stations always push the model up by 18–26k. The monthly method's blanket factor over-credits regular stations, partly offsetting it; as the model's uplift grew after COVID, that offset shrank from ~17k to ~5–8k, and the gap widened. *(This treats the monthly dataset as one factor on all taps — a model of OPMI's method, not their published breakdown.)*

**5. The Green Line swing comes from the monthly factor, not riders.** The stop-level model's Green Line factor (boardings ÷ taps) holds near 2.3–2.4× in 2018 and 2023–25. The monthly dataset's factor drops to mostly 1.7–2.0× from July 2023 to June 2024, then jumps to mostly 2.4–2.8× from August 2024 — so Fall 2023 lands below the model (−16%) and Fall 2024–25 above it (+15–16%). Red, Orange and Blue factors barely move. Separately, Fall 2019 stop-level data counts about half as many boardings at ungated surface stops as Fall 2018 (21k vs 44k), which is why the 2019 Green gap looks so large.

**Bottom line:** on the Blue Line, the datasets disagree mainly because of behind-the-gate transfers at State and Government Center, plus a larger non-tap allowance in the model after COVID. East Boston stations scale consistently and are not the driver. On the Green Line, the swing tracks shifts in the monthly dataset's own scaling. Along the way, the analysis surfaced three unflagged breaks in the public data.

**Caveat:** OPMI does not publish the exact factors behind Dataset A, so the transfer-allowance part of this decomposition is inferred from the published data, not confirmed by the MBTA.

## Reproduce it

```bash
pip install -r requirements.txt
python scripts/01_fetch.py     # downloads raw data from the MBTA Open Data Portal into data/raw/
python scripts/02_analyze.py   # writes reconciliation tables to outputs/
python scripts/03_build_page.py # builds index.html (the data story) from outputs/ and site/template.html
```

**Auto-refresh:** a GitHub Action (`.github/workflows/refresh.yml`) reruns the pipeline on the 8th of every month and commits updated outputs. The published page loads `outputs/story_data.json` live, so it picks up new monthly data without a redeploy. A new fall stop-level season is added with one line in `scripts/01_fetch.py`.

Validation: with the comparison window used here, Fall 2023 results reproduce the forum post's figures exactly.

## Repo map

- `scripts/` — fetch and analysis pipeline
- `index.html`, `site/template.html` — the interactive data story
- `outputs/` — reconciliation tables (line gap, Blue Line stations, Blue Line summary and bridge, monthly factor by month, Green Line summary)
- `docs/data_dictionary.md` — every field used, from both datasets
- `docs/decision_log.md` — analysis decisions and why
- `docs/data_quality_log.md` — issues found in the source data

Data: MBTA Open Data Portal, published by MBTA OPMI under the MassDOT Developers License Agreement.

*Shreyas Tayde · [shre0027.github.io](https://shre0027.github.io)*
