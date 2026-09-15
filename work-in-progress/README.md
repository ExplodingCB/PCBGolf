# PCBGolf engineering checkpoint

Updated September 14, 2026. **Incomplete, not fabrication-ready, and not submitted.** Work stopped at the owner's request. Start with [../HANDOFF.md](../HANDOFF.md) for exact artifact provenance, remaining blockers, toolchain and proposed continuation plan. All subagents and routing jobs are stopped.

## Current design

- 45 × 37 mm outline, four copper layers, 1.6 mm PCB thickness, 239 components.
- STM32H725VGH6 in an 8 × 8 mm TFBGA100 package, with corresponding schematic and GPIO changes.
- Project-local schematic symbols, footprints and 3D models are included. Open `pcbgolf.kicad_pro` here; the repository-root project is an earlier placement baseline.
- This snapshot is the last completed `via400` routing result: 2,715 track segments and 484 through vias. `pcbgolf.merge.json` records the initial merge only.
- `assembly.step` contains the board and all 236 populated component models. All 239 component placements were compared and exactly match this latest PCB; only routing changed after the STEP export. Final fabrication artifacts should be exported again.

## Known blockers

- `net-groups.json` reports **184 missing connections between connected pad groups across 113 nets**.
- `drc.json` contains **zero physical error records and zero hole-spacing warnings**. Unconnected items and other warnings still require completion and review.
- `connectivity-parity.json` passes all five schematic sheets: 239 components, zero component or pin/net differences.
- `usb-reference-audit.json` verifies all 17 ground return vias connect to both original inner layers. One small reference-copper gap remains flagged among 223 USB segments.
- CAN bus routing is partly integrated; connector and transceiver branches still require connections. The older isolated trial is documented separately in `../reports/can-routing-trial.md`.
- Power distribution, current capacity, final manufacturing checks and firmware/hardware validation remain unfinished. Some vias require filled and capped via-in-pad processing.

## Preserved work

Engineering scripts and reports are in `../scripts/` and `../reports/`. Reports describe their named candidates. `routing-source.*` and `routing-handoff/via400*` preserve the exact source, DSN, SES, hash and log for the latest output. `small-via-trial.*` is a separate older 190-open experiment with 130 reduced signal vias; do not replace the latest main board with it. Other experiments and installed toolchains remain local and are excluded from Git. **No six-layer conversion was implemented.**

Firmware source changes and the local build driver are in `../firmware/pcbgolf/`. Bootstub and application compiled and linked locally; neither was hardware-tested. No flashable binaries are included in this checkpoint.
