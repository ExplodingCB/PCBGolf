# PCBGolf engineering checkpoint

Saved September 14, 2026. **Incomplete, not fabrication-ready, and not submitted to the leaderboard. No valid challenge score is claimed.** Work and parallel agents were stopped at the owner's request to conserve usage. Resume engineering only when requested.

## Current design

- 45 × 37 mm outline, four copper layers, 1.6 mm PCB thickness, 239 components.
- STM32H725VGH6 in an 8 × 8 mm TFBGA100 package, with corresponding schematic and GPIO changes.
- Project-local schematic symbols, footprints and 3D models are included. Open `pcbgolf.kicad_pro` here; the repository-root project is an earlier placement baseline.
- This snapshot combines the BGA100 power-routing candidate with the frozen USB-routing candidate. `pcbgolf.merge.json` records source hashes and merge details.

## Known blockers

- `net-groups.json` reports **519 missing connections between connected pad groups across 173 nets**. The DRC unconnected list is capped and understates remaining work.
- `drc.json` contains **four physical error records and three hole-spacing warnings**: a VDDLDO via conflicts with the STM32 USB pair, and three connector VBUS via pairs violate hole spacing. Other warnings also need review.
- Six USB pairs were routed and checked in an isolated candidate. Integration still needs conflict repair and another connectivity/reference-plane check.
- The isolated CAN bus trial is documented in `../reports/can-routing-trial.md`; it has not been merged into this board. Additional CAN circuit branches remain unconnected.
- Power distribution, current capacity, final manufacturing checks and firmware/hardware validation remain unfinished. Some vias require filled and capped via-in-pad processing.

## Preserved work

Engineering scripts and reports are in `../scripts/` and `../reports/`. Reports describe their named candidates and must not be read as passing results for this combined snapshot. Experimental candidate directories and installed toolchains remain local and are excluded from Git.

Firmware source changes and the local build driver are in `../firmware/pcbgolf/`. Bootstub and application compiled and linked locally; neither was hardware-tested. No flashable binaries are included in this checkpoint.
