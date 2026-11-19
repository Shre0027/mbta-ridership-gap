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

**Bottom line:** the datasets disagree mainly because of behind-the-gate transfers at State and Government Center, which the tap-based method has to estimate with fixed factors, plus a larger non-tap allowance in the model after COVID. East Boston stations scale consistently and are not the driver. Along the way, the analysis surfaced an unflagged split-factor swap in the public tap data.

**Caveat:** OPMI does not publish the exact factors behind Dataset A, so the transfer-allowance part of this decomposition is inferred from the published data, not confirmed by the MBTA.

## Reproduce it

```bash
pip install -r requirements.txt
python scripts/01_fetch.py     # downloads raw data from the MBTA Open Data Portal into data/raw/
python scripts/02_analyze.py   # writes reconciliation tables to outputs/
python scripts/03_build_page.py # builds index.html (the data story) from outputs/ and site/template.html
```

Validation: with the comparison window used here, Fall 2023 results reproduce the forum post's figures exactly.

## Repo map

- `scripts/` — fetch and analysis pipeline
- `index.html`, `site/template.html` — the interactive data story
- `outputs/` — reconciliation tables (line gap, Blue Line stations, Blue Line summary)
- `docs/data_dictionary.md` — every field used, from both datasets
- `docs/decision_log.md` — analysis decisions and why
- `docs/data_quality_log.md` — issues found in the source data

Data: MBTA Open Data Portal, published by MBTA OPMI under the MassDOT Developers License Agreement.

*Shreyas Tayde · [shre0027.github.io](https://shre0027.github.io)*
