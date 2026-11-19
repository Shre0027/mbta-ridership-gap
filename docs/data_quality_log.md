# Data quality log

Issues found while reconciling the source datasets, and how each was handled.

| # | Issue | Where | Impact | Handling |
|---|---|---|---|---|
| 1 | Same station has two names: **"State"** vs **"State Street"** | ODX stop files vs Gated Station Entries | Station join silently drops the busiest Blue Line station | Normalized to "State" before joining |
| 2 | **Green Line split into branches** (Green Line B/C/D/E) in Fall 2025 only; earlier seasons use one "Green Line" | Fall 2025 stop-level file | Line totals for 2025 miss Green entirely | Rolled branches up to "Green Line" |
| 3 | **Government Center split flipped on March 6, 2019**: entries were split 90% Blue / 10% Green through March 5, then 10% Blue / 90% Green from March 6, with no note in the data or its documentation (which describes 90% Green). State Street stays 10% Blue / 90% Orange throughout | Gated Station Entries | Taps credited to Blue at Government Center drop ~90% overnight; station trends across that date show a collapse that never happened | Reported, not "corrected"; station-level Blue comparisons for 2017–2018 read with this in mind |
| 4 | Field names differ between seasons (`direction_id`/`stop_id` vs `dir_id`/`parent_station`; time periods vs hours) | Stop-level files | Combining seasons needs care | Analysis uses only fields common to all files |
| 5 | Stop-level files exist only for Fall 2017–2019 and 2023–2025 | MBTA Open Data Portal | No comparison possible for 2020–2022 | Years without both datasets are excluded |
| 6 | Gate taps include employee taps and miss held-open gates (special events, emergencies) | Gated Station Entries documentation | Taps are an imperfect proxy | Used only for station-level ratios, not as ridership |
| 7 | **Green Line ungated-stop boardings halve in Fall 2019** (21k vs 44k in Fall 2018; 15% vs 25% of Green Line boardings) with no documented method change | Stop-level (ODX) Fall 2019 | 2019 Green Line gap looks unusually large (+24%) | Reported; not adjusted |
| 8 | **Monthly Green Line factor shifts regime**: monthly riders ÷ gate taps runs mostly 1.7–2.0× from Jul 2023 to Jun 2024, then mostly 2.4–2.8× from Aug 2024; Red/Orange/Blue stay ~1.3–1.45× | Monthly Ridership by Mode and Line | Green Line monthly totals jump ~22% Aug→Sep 2024 independent of taps; drives the Green gap's sign flip | Reported; explained as the cause of the Green swing |
