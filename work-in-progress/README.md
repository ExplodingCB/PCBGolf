# PCBGolf engineering checkpoint

Updated September 14, 2026. **Incomplete, not fabrication-ready, and not submitted to the leaderboard. No valid challenge score is claimed.** The owner requested a public checkpoint and continued work by one agent. All subagents remain stopped. Work now focuses on completing and checking this layout.

## Current design

- 45 × 37 mm outline, four copper layers, 1.6 mm PCB thickness, 239 components.
- STM32H725VGH6 in an 8 × 8 mm TFBGA100 package, with corresponding schematic and GPIO changes.
- Project-local schematic symbols, footprints and 3D models are included. Open `pcbgolf.kicad_pro` here; the repository-root project is an earlier placement baseline.
- This snapshot is the current `candidates/completion/finish.kicad_pcb` result: merged USB/power routing, ground connections, partial CAN routing, completed local MCU power paths and crystal routing, followed by bounded general routing. `pcbgolf.merge.json` records the earlier initial merge only.
- `assembly.step` was freshly exported from this checkpoint with all populated components.

## Known blockers

- `net-groups.json` reports **220 missing connections between connected pad groups across 131 nets**.
- `drc.json` contains **zero physical error records and zero hole-spacing warnings**. Unconnected items and other warnings still require completion and review.
- Six USB pairs were routed and checked in an isolated candidate. Integration still needs conflict repair and another connectivity/reference-plane check.
- CAN bus routing is partly integrated; connector and transceiver branches still require connections. The older isolated trial is documented separately in `../reports/can-routing-trial.md`.
- Power distribution, current capacity, final manufacturing checks and firmware/hardware validation remain unfinished. Some vias require filled and capped via-in-pad processing.

## Preserved work

Engineering scripts and reports are in `../scripts/` and `../reports/`. Reports describe their named candidates and must not be read as passing results for this combined snapshot. Experimental candidate directories and installed toolchains remain local and are excluded from Git.

Firmware source changes and the local build driver are in `../firmware/pcbgolf/`. Bootstub and application compiled and linked locally; neither was hardware-tested. No flashable binaries are included in this checkpoint.
