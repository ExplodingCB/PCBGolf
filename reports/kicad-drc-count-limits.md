# KiCad10 DRC counts are capped

KiCad10.0.6's `DRC_ENGINE::RunTests` assigns a per-error-code limit of **499** for clearance and unconnected items, and **199** for every other error code. `ReportViolation` enforces each cap atomically. `--all-track-errors` does not remove these limits. [Official tagged source](https://gitlab.com/kicad/code/kicad/-/blob/10.0.6/pcbnew/drc/drc_engine.cpp)

Therefore499 unconnected reports means **at least499**, not an exact remaining-route count. Two substantially different partial layouts can both display499. A count below the cap is useful for that error code, and a completed zero-unconnected native check remains an essential acceptance condition.

`scripts/score_assembly.py` now adds `saturated_types`, `counts_are_complete` and `count_limitation` to its DRC summary. Saturated categories are labelled lower bounds in issue text. Verified against v4's499 unconnected report and v8's436 report; the former is flagged capped and the latter is not.
