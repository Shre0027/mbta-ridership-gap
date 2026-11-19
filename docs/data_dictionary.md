# Data dictionary

Only the fields used in this analysis are listed.

## Dataset A — MBTA Monthly Ridership By Mode and Line
Feature service `NTD_Reporting`. Grain: one row per month × day type × line.

| Field | Type | Meaning |
|---|---|---|
| `month_of_service` | date (epoch ms) | First day of the service month |
| `daytype` | text | Weekday, Saturday, Sunday, Total |
| `daycount` | int | Number of service days of that type in the month |
| `route_or_line` | text | Line or mode (Red Line, Blue Line, Heavy Rail, Bus, ...) |
| `ridership_total` | int | Scaled ridership for the month and day type |
| `ridership_average` | int | `ridership_total` ÷ `daycount` |

## Dataset B — MBTA Rail Ridership by Season, Route/Line and Stop (ODX)
Fall 2017–2019 (one service), Fall 2023, Fall 2024 (SDP time periods), Fall 2025 (by hour). Grain: season × line × direction × day type × time period (or hour) × stop.

| Field | Type | Meaning |
|---|---|---|
| `season` | text | e.g. "Fall 2023" |
| `route_name` | text | Line (Fall 2025 splits Green into B/C/D/E) |
| `day_type_name` | text | weekday / saturday / sunday (case varies by file) |
| `stop_name` | text | Station name |
| `average_ons` | int | Average boardings per service day in the period |
| `number_service_days` | int | Days averaged |

## Gated Station Entries (GSE) — historical
Yearly CSVs. Grain: service date × 30-minute period × station × line.

| Field | Type | Meaning |
|---|---|---|
| `service_date` | date | Service day (3:00 AM–2:59 AM) |
| `station_name` | text | Station name |
| `route_or_line` | text | Line credited with the entry (transfer stations get one row per line using CTPS survey split factors) |
| `gated_entries` | number | Unscaled successful taps/ticket insertions at faregates (decimals at split stations) |

## Derived measures (outputs/)

| Measure | Definition |
|---|---|
| `stop_level` | Sum of `average_ons` across all stops, directions and periods for a line, weekday |
| `monthly` | Σ `ridership_total` ÷ Σ `daycount`, weekday, Sep–Dec |
| `gap_pct` | (monthly − stop_level) ÷ stop_level × 100 |
| `taps` | Σ `gated_entries` ÷ number of non-holiday weekdays, Sep–Dec |
| `model_per_tap` | ODX boardings ÷ taps at a station |
| `transfer_share_of_boardings_pct` | Blue boardings at State + Government Center ÷ all Blue boardings |
| `monthly_factor` | Dataset A riders ÷ gate taps for the same line and window — the effective scaling the monthly dataset applies |
| `model_factor` | Dataset B boardings ÷ gate taps (Green Line) |
| `bridge_transfer_stations` | Blue boardings at State + Government Center − their taps × `monthly_factor` |
| `bridge_regular_stations` | Blue boardings at all other stations − their taps × `monthly_factor` (the two bridge parts sum exactly to stop_level − monthly) |

## Added in v2

| Source / output | Field | Meaning |
|---|---|---|
| 2025 System-Wide Passenger Survey | `reporting_group`, `measure`, `category`, `weighted_percent`, `n`, `margin_of_error` | Weighted share of riders by answer; `measure = "Access to Each MBTA Trip Leg"`, `category = "Subway or Light Rail"` = share who arrived on another subway/light-rail line |
| GTFS map (MassDOT) | `shape_id`, `route_id`, `route_colo` | Official route shapes and colors; one canonical shape per service is drawn |
| GTFS map (MassDOT) | `stop_id` (`place-…`) | Parent station ID; joins to `parent_station` (ridership) and `stop_id` (gate entries) |
| `system_stations_2025.csv` | `taps`, `odx`, `model_per_tap`, `transfer_station`, `survey_arrived_by_subway` | Per station × line, Fall 2025 weekday |
| `station_hourly_2025.csv` | hour columns | Modeled weekday boardings per station and hour (drives the animated map) |
| `map.json` | `land`, `lines`, `cr`, `stations` | Projected, simplified geometry and station data for the page |

