# Solo completion status — September 14, 2026

The owner requested a WIP push followed by continued work without subagents. All three agents are stopped. Continue toward a valid submission; do not restart size optimization or claim the active challenge goal is complete.

## Current checked checkpoint

`candidates/completion/finish.kicad_pcb`, copied into `work-in-progress/pcbgolf.kicad_pcb`: 45 × 37 mm, four layers, 239 components, 2,297 track segments and 417 vias. Native DRC: 220 opens, zero physical errors, zero hole-spacing warnings. No valid score or submission yet.

The original merged snapshot had 519 missing pad-group connections. Three USB ground-return vias had been reassigned to connector VBUS during zone integration. They were restored and set to free vias to preserve explicit net assignments. New ground fanout, local SMPS links, a front 3.3 V pour, and partial CAN routing are included.

The crystal is now at (3.6,15.35), C14 at (3.6,17.4), C17 at (1.0,16.3), and C19 at (4.05,24.3). The four clock links route on the bottom, with lengths 7.408/2.851 and 3.469/2.097 mm in the earlier validated clock result; the exact C17 move subsequently updated its short branch. `complete_clock.py` reproduces the layout and `repair_route_import.py` restores the checked clock geometry while removing only newly imported copper that violates native rules.

Five-sheet parity passed before these placement-only changes. Final parity must be rerun against the submission artifact. Earlier STEP bounds were 45 × 37 × 14.23 mm with no component AABB collisions; the WIP STEP is freshly exported after the clock move, but final geometry checks remain required.

USB's 17 return vias connect to both inner ground layers. Reference copper passed after removing 34 intruding CAN segments and adding inner track keepouts. One small reference gap reappeared after subsequent general routing; rerun the reference audit against the final board. `prepare_router.py` explicitly exports these keepouts because KiCad omitted track-only rule areas from its DSN.

## Router progress and next action

The current job uses `candidates/completion/flexible-bus.kicad_pcb`, with long CAN bus copper unlocked but the 32 checked connector escape vias preserved. Its input is `pofv.dsn`, its output will be `pofv.ses`, and its log is `pofv-router.log`. Native import must use the matching `pofv.preflight.json` source hash. The job is bounded to five minutes.

Filled/capped SMD vias require both `(attach on)` in via padstacks **and** `(control (via_at_smd on))` in the DSN structure. The earlier `finish` and `flexible` runs lacked the latter control; `pofv` enables both. Native DRC and a full filled/capped via map remain mandatory.

The local router JAR has only its existing normalization-loop limit reduced from 2,000 to 64, preventing long cleanup oscillations. `bound_router_cleanup.py` reproduces this isolated copy and records its hash; the official JAR is retained. No clearance or routing correctness checks are removed. Commands also use a five-minute job timeout, disabled optimizer, a 0.10 mm neck-width floor, 0.20 mm hole clearance and 0.30 mm copper-edge clearance.

## Remaining acceptance work

Complete all signals and power pad groups, repair any imported physical errors, recheck USB geometry/reference copper and clock preservation, verify power distribution and current capacity, final five-sheet parity, complete assembly and mating checks, final score and self-contained ZIP, then the official submission form. The form requires Google authentication; no submission has been made.

Experimental firmware compiled and linked. The new `audit_firmware_pinmap.py` checks 44 GPIO/ADC/CAN allocations against the schematic allocation and official ST pin data; all pass. `firmware/pcbgolf/pinmap.json` holds the results. Hardware operation and unimplemented peripheral behavior remain untested.
