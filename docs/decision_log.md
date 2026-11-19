# Decision log

| # | Decision | Why | Alternative considered |
|---|---|---|---|
| 1 | Compare **weekday** ridership only | Both datasets publish weekday figures; weekday is the standard planning and reporting unit | Saturday/Sunday — smaller, noisier, fewer service days |
| 2 | "Fall YYYY" monthly figure = **day-weighted average of Sep–Dec weekday months** | Reproduces the Feb 2025 forum post's Fall 2023 numbers exactly, so results are comparable and verifiable | Simple Sep–Nov average — tried first; gave slightly different numbers that did not match the forum |
| 3 | Stop-level line total = **sum of average weekday `ons` across all stops, directions and time periods** | `ons` are boardings, which is what an unlinked-trip ridership count measures | `average_flow` — measures load on the train, not riders |
| 4 | Gate taps averaged over **Sep–Dec weekdays, federal holidays and the day after Thanksgiving excluded** | Matches the weekday definition; holidays have abnormal ridership | Including holidays — would bias averages down |
| 5 | Station-level test uses **raw gate taps** as the proxy for Dataset A | Dataset A is published only at line level; gate taps are its documented input | No station-level comparison — would leave the cause unexplained |
| 6 | Treat **State and Government Center** as the Blue Line transfer stations | They are the only Blue Line stations with behind-the-gate transfers to other subway lines | Bowdoin — no transfer |
| 7 | Report the transfer allowance as **inferred**, not proven | OPMI does not publish the exact scaling factors in Dataset A | Claiming a precise split — would overstate what the data supports |
| 8 | Dropped the claim that Dataset A was revised after Feb 2025 | Once the forum's window (decision 2) was used, the numbers matched exactly — no revision | — |
| 9 | Treat the March 2019 Government Center swap as a **data quality finding, not a driver of the gap** | The monthly-vs-stop-level gap shrank from 2018 (-15.1%) to 2019 (-10.6%), so the swap in the tap data did not widen it; an earlier draft wrongly listed it as a cause | Keeping it as a "method change that widened the gap" — not supported by the numbers |
