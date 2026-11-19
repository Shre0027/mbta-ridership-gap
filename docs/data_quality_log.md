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
