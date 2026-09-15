# PCBGolf handoff

**Owner: [ExplodingCB](https://github.com/ExplodingCB). Branch: `work/compact-pcba`. Stopped September 14, 2026 at the owner's request.** All three subagents are interrupted and the router has exited. The latest instruction is to push the work and plan for another engineer, not to continue automatically.

## Start here

Open **[work-in-progress/pcbgolf.kicad_pro](work-in-progress/pcbgolf.kicad_pro)**. The repository-root project is an older placement. All five schematics, symbols, footprints, models, rules and assembly STEP are included.

**This is not a valid leaderboard entry.** There has been no submission, upstream PR, fabrication order or hardware test. Open connections prevent the current board from working.

| Check | Latest result |
| --- | --- |
| PCB | 45 × 37 mm, four layers, 1.6 mm thick |
| Assembly bounds | 45.0000001 × 37 × 14.2300002 mm |
| Components | 239; 236 populated model instances |
| Copper | 2,715 track segments, 484 through vias |
| Missing connections | **184 pad-group connections across 113 nets** |
| Native physical DRC | **0 errors**, 399 other warnings, 184 unconnected items |
| Five-sheet schematic parity | Passed: 0 component differences, 0 pin/net differences |
| Mechanical screen | No component AABB collisions |
| USB reference screen | 17/17 return vias connected; **1 flagged reference gap** |
| Firmware | Bootstub/application compile and link; untested on hardware |

Current evidence is in `work-in-progress/drc.json`, `net-groups.json`, `connectivity-parity.json`, `usb-reference-audit.json`, `step-component-bounds.json`, and `reports/checked-wip-mechanical-audit.json`. All 239 component placements exactly match the existing assembly STEP; only routing changed after export. Cable access is separately screened in `reports/actual-placement-mating-audit.json`: 0.5 mm between conservative USB-C overmold envelopes and a 0.35 mm closest plug-to-J1 envelope gap.

## Exact saved state

- **Main checked result:** `work-in-progress/pcbgolf.kicad_pcb`, the last completed `via400` router output.
- **Exact pre-route source:** `work-in-progress/routing-source.kicad_pcb` plus matching project/rules, 191 missing connections.
- **Reproduction:** `work-in-progress/routing-handoff/via400.dsn`, `.ses`, `.preflight.json`, and `via400-router.log`. Original absolute paths identify the producing machine; the hash matches the included source copy.
- **Earlier small-via experiment:** `work-in-progress/small-via-trial.*`, 190 opens, zero physical DRC errors. It shrank 130 unlocked low-current signal vias to 0.30/0.15 mm without breaking connected pad groups. This predates the last main result. Reapply its script to the main board rather than reverting to this older trial.
- `pcbgolf.merge.json` records only the initial critical-route merge, not the current final routing state.

The last router run finished at 22:01 local with a ten-minute timeout. Native opens improved **191 → 184**; router-internal counts were **184 → 177**. Native KiCad is authoritative. No 0.30/0.15 mm autorouting run was started. **No six-layer conversion was implemented.** All other candidates remain locally under ignored `candidates/`.

## Proposed continuation plan — not executed

1. Prioritize a complete working entry over further size optimization. Keep the current mechanical envelope initially. Use `net-groups.json` to find isolated pads and incomplete power/CAN branches. Repeating unchanged four-layer routing settings has produced only small gains.
2. The last proposed direction was **six layers**, accepting +10,000 layer penalty for routing capacity and reference/power planes. JLC's [JLC06161H-3313](https://jlcpcb.com/impedance) has the same nominal 0.09940 mm outer prepreg as the current four-layer impedance model. Signal / ground / signal / mixed power-and-signal / ground / signal is a starting point, not a finished design. Map all existing inner copper explicitly, protect USB references and recheck connectivity. `stackup_trial.py` is an older experiment that refuses already-routed inner layers; do not run it blindly. Many helpers hardcode four layers.
3. A smaller alternative is `compact_signal_vias.py` on the latest main board, followed by `prepare_router.py --allow-filled-via-in-pad --routing-via-mm .3 --route-width-mm .1`. The prior shrink experiment passed native physical DRC. Review filled/capped processing and actual drill clearances. Thin router search widths do not qualify power current capacity.
4. Complete every signal and power/ground pad group. Preserve checked USB, MCU SMPS and crystal geometry. Engineer power trunks, return paths and thermal connections. Clean up dangling copper, library mismatches and silkscreen after routing stabilizes.
5. On one final artifact, run native full DRC, uncapped connectivity, five-sheet parity, USB endpoint/skew/reference checks, power/current review, firmware review and final mechanical/mating checks. Regenerate the complete STEP, calculate score from the exact PCB/STEP, and package the self-contained KiCad project plus STEP ZIP.
6. Submit through the official form under the owner's identity. Organizers review competitive entries before posting; submitting does not instantly place a score on the leaderboard.

## Critical electrical details

- MCU is **STM32H725VGH6**, 8 × 8 mm TFBGA100, 0.8 mm pitch, bottom side. The schematic package/pin remap matches the latest board. There are 82 connected and 18 NC MCU pins.
- MCU Y1 is **25 MHz**, matching firmware. Preserve the checked PH0/PH1 clock routes. Cluster positions: Y1 (3.6,15.35), C14 (3.6,17.4), C17 (1.0,16.3), C19 (4.05,24.3). U4 has its own **24 MHz Y2**. Its XTAL2 path was about 18.25 mm with two vias in the earlier checked input and needs separate layout review.
- Important repaired integration bug: USB GND return vias at **(3.2,5.6), (18.2,5.6), (25.7,5.6)** had been assigned to VBUS. They are restored and set free (`SetIsFree(True)`) to preserve explicit nets during zone fills. Keep this behavior when copying/adding vias.
- Frozen USB manifest: `reports/usb-paired-routes.json`, 223 segments, 40 signal vias, 17 ground return vias and reference patches. Native DSN export omits track-only keepouts; `prepare_router.py` explicitly exports them.
- Remaining USB reference flag: track 142, `CH3_D_P`, bottom, approximately **0.01114 mm²** near x=19.98–20.21 / y=9.20–9.28, between two signal-via antipads. It has not been resolved or waived. All 17 returns connect to both original inner layers. Nominal pair impedance was 90.16 ohms with 0.11 mm width / 0.10 mm gap and JLC04161H-3313; final compliance is not established.
- J1 **PJ-002AH-SMT-TR is 5 A total**. Four TPS25944A trips are about 3.18 A each; their sum is not an allowed input load. Power/return copper and thermal spreading remain unqualified.
- U1/U2 AP62300 ICs are rated 3 A, but existing inductors are approximately 1.8 A saturation / 2 A thermal. Do not claim usable 3 A rails. The 3.3 V buck is fed from 5 V. Feedback, TVS, op-amp footprint and IMON values were corrected; see circuit reports. R70–73 are 10 kΩ.
- Local `VLXSMPS` loop and part of `VDDLDO` are connected; decoupling/supply connections still need review. `audit_power_copper.py` checks geometric connectivity, not ampacity.
- Four CAN transceivers use three MCU controllers with alternate FDCAN2 allocation. J4 DNP header pads remain.
- Some vias overlap SMD lands and need **filled and capped via-in-pad processing**. A complete final processing map is missing. Generic tenting defaults do not constitute sufficient fabrication instructions.
- Native DRC has two library-footprint mismatch warnings and numerous silkscreen/dangling-copper warnings. Do not disable manufacturing checks to obtain a clean report.

## Firmware

`firmware/pcbgolf/` includes the board header, patch, build driver and pinmap. Panda revision `78cf69904c332c599a297fcc2a09c08d10d429d5`, opendbc `057aee25b5eee7530f0b95b5b508c8c3247b0cd7`, Arm GNU 12.3.Rel1. Bootstub/application compile and link. `audit_firmware_pinmap.py` checked 44 GPIO/ADC/CAN allocations against schematic allocation and ST data.

Both images require `PCBGOLF_BGA100`: this **H725 uses SMPS**, overriding panda's historical TFBGA100 supply heuristic. USB 3.3 V is external; this package has no VDD50USB ball. Hardware behavior, peripheral coverage including microSD/hub, timing and analog calibration remain unverified. No qualified firmware binaries are published.

## Tools and reproduction

Original workspace: `D:\Projects\PCBGolf`. Installed toolchains remain locally in ignored `tools/` and are not pushed.

- KiCad **10.0.6**: `tools/kicad/bin/kicad-cli.exe` and `tools/kicad/bin/python.exe` (Python 3.11, pcbnew, Shapely).
- Python **3.12** venv: `tools/venv/Scripts/python.exe`; numpy 2.5.3, scipy 1.18.1, Shapely 2.1.2, sexpdata 1.0.2, cadquery-ocp 8.0.1.0.0.
- Java **25**: `tools/java/jdk-25.0.4.1+1-jre/bin/java.exe`.
- FreeRouting **2.4.1**: retained original plus bounded JAR. `bound_router_cleanup.py` changes only two existing normalization guards from 2000 to 64 to prevent oscillation stalls. Original SHA-256: `251101c3eeac22d7e7dfcf6796603279e5d1000283eb82d8f093780f7afc6aa9`; bounded SHA-256: `af6a1e173349957b94580b6b8893c212c08502ca9afdb144569c439202d5f21e`.

From repository root, adjusting executable paths on another machine:

```powershell
tools/kicad/bin/kicad-cli.exe pcb drc --format json --severity-all --all-track-errors --refill-zones --output review-drc.json work-in-progress/pcbgolf.kicad_pcb
tools/kicad/bin/python.exe scripts/audit_net_connectivity.py work-in-progress/pcbgolf.kicad_pcb --out review-net-groups.json
tools/venv/Scripts/python.exe scripts/validate_connectivity.py --board work-in-progress/pcbgolf.kicad_pcb --project work-in-progress/pcbgolf.kicad_pro --output review-parity.json
tools/kicad/bin/python.exe scripts/import_route.py work-in-progress/routing-source.kicad_pcb work-in-progress/routing-handoff/via400.ses --out work-in-progress/reimport.kicad_pcb --preflight work-in-progress/routing-handoff/via400.preflight.json
```

Use the custom five-sheet parity check, not the single-top-level KiCad parity flag. Native pad-group counting excludes orphan copper and cannot replace DRC. SES import checks the source hash and restores tiny footprint-coordinate rounding; never import into a different-placement source.

Last router settings: `-mp 10`, `--router.job_timeout=00:10:00`, optimizer/fanout disabled, neck width 100 µm, hole clearance 200 µm, edge clearance 300 µm, `--router.scoring.unrouted_net_penalty=100000000`. Both DSN `(attach on)` and `(control (via_at_smd on))` are required for via-in-pad routing. Router scores are higher-is-better and unrelated to the challenge score. See the saved log and `reports/SOLO_COMPLETION.md` for history.

## Submission and identity

[Rules/ZIP requirements](https://github.com/commaai/PCBGolf#submission), [leaderboard](https://comma.ai/leaderboard#pcbgolf_challenge), [official form](https://docs.google.com/forms/d/e/1FAIpQLSc_Qsh5egoseXKr8vI2TIlsskd6nNZLNVuMJBjkogZzLe79KQ/viewform).

The form requires Google authentication. GitHub identity **ExplodingCB** is authorized, but no prize-contact email has been verified. Do not use the GitHub noreply commit address as contact email. Local `gh` was authenticated as ExplodingCB; the connected GitHub MCP was a different identity and was not used for publishing.

**Latest instruction: push the current work and plan for another engineer. This session is stopped.**
