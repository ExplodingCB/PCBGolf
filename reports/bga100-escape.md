# BGA100 through-via escape experiment

The recommended isolated candidate is **`candidates/bga100-power-escape/pcbgolf.kicad_pcb`**. It uses the new power placement and reaches every connected MCU ball with **32 vias**, while preserving all 18 no-connects. Both the original `bga100-base` and the source `bga100-power-base` are unchanged. This is complete MCU fanout access, not completed end-to-end board routing.

## Measured result

| Item | Count |
|---|---:|
| Actual MCU balls | 100 |
| Connected balls / retained no-connects | 82 / 18 |
| First/second-row or critical supply access on B.Cu, without vias | 47 |
| Balls with through-via dogbones | 35 |
| Added through vias | **32** |
| Shared same-net vias | 3 |
| Total balls with access | **82 / 82** |
| Balls still without access | **0** |
| Added track segments | 102 |

Native KiCad DRC reports **zero physical violations**, including warning-level hole-spacing checks, with no DRC exclusions or rule changes. The 27 dangling-via and 47 dangling-track warnings identify intentionally unfinished signal routes. Five GND vias connect all six ground balls into filled In1 GND copper, checked using native filled-zone geometry. Five-sheet logical parity passes with zero component or pin-net differences across all 239 parts. Unconnected records are capped at 499, so this number is a lower bound. Remaining silk/text warnings and two existing footprint-library mismatches need final cleanup.

Every via is a **0.45 mm copper / 0.20 mm through drill**, reached by a **0.12 mm B.Cu track** at ±0.4 mm x/y offsets from a ball. Candidates screen copper and drills on every layer, including opposite-side SMD pads, before native DRC. No via-in-pad, microvia, blind via or clearance waiver is assumed. The 0.45 mm component-PTH-to-component-PTH and 0.20 mm generic drilled-hole separation rules remain in the copied project.

## Placement and via reduction

| Experiment | MCU center | Accessible balls | Vias | Physical DRC |
|---|---|---:|---:|---|
| Original pose, one direct row | 15.6, 19.9 | 66/82 | 36 | Passed |
| Shifted pose, one direct row | 10.5, 19.9 | 82/82 | 50 | Passed |
| Shifted pose, two direct rows | 10.5, 19.9 | 82/82 | 32 | Passed |
| New power placement, two direct rows | 10.5, 19.9 | 82/82 | **32** | **Passed** |

At the original pose, opposite-side U7, C35, U4, C33 and C30 blocked the dogbone grid. Moving the MCU left resolved all blocked sites without moving the hub or transceiver. X=9.5 and x=11.5 at y=19.9 also passed complete one-row escapes; x=10.5 was chosen for the power placement. The second direct row removed **18 vias**, saving **900 challenge score points** relative to the first complete 50-via fanout, before any later routing changes.

Final MCU pose is **x=10.5, y=19.9 mm, B.Cu, 0°**. Balls occupy x=6.9–14.1 and y=16.3–23.5 mm. The original 10 × 10 mm BGA courtyard is retained. Bottom direct-access stubs reach x=6.1/14.9 and y=15.5/24.3; subsequent placement must include trace copper and clearance beyond these centerlines.

Shared vias are C1/D1 GND at (6.5,21.5), D6/E5 +3V3 at (10.5,20.7), and G6/F7 VDDLDO at (11.3,19.1). C2/VBAT exits through the gap above C1, preserving the shared ground-via cell beside the switching escape.

## Reserved MCU supply access

- D2/VLXSMPS: (7.7,21.1) → (7.3,20.7) → (6.1,20.7), B.Cu.
- E2/VFBSMPS: (7.7,20.3) → (7.3,19.9) → (6.1,19.9), B.Cu.
- E1/VDDSMPS reaches (6.1,20.3) on B.Cu.

These keep switching and feedback access direct. The new power placement brings L4's switching pad to (5.07,20.7); its bulk/bypass parts are nearby. Actual supply interconnects remain for the power-routing stage. The 0.12 mm stubs demonstrate geometric access and are not final current/inductance sizing. In2 stays +12V; MCU +3V3, VDDLDO and VDDA require correctly named local supply copper and decoupling. No fanout is connected to the wrong plane. Supply requirements are in `reports/mcu-bga100-supply-check.md`. USB fanout access has not been certified for differential impedance or skew.

## Reproduce or refresh

```powershell
tools/kicad/bin/python.exe scripts/escape_bga100.py --source candidates/bga100-power-base --output candidates/bga100-power-escape --direct-rings 2
```

For a copy that already contains a prior escape and its matching `escape-report.json`, remove only the listed old escape UUIDs in another output copy before rebuilding:

```powershell
tools/kicad/bin/python.exe scripts/escape_bga100.py --source candidates/your-placement-copy --output candidates/your-refreshed-escape --refresh-known-escape --direct-rings 2
```

The refreshed input must contain only the known escape tracks/vias; other newly routed copper is rejected until that use case is explicitly supported. This prevents silently omitting existing routing obstacles. The script saves its report, native DRC JSON and merged connectivity report beside its output board.

## Assembly spacing

The BGA courtyard was kept at its official size. KiCad specifies a 1.0 mm BGA courtyard allowance. JLC's current recommended minimum component spacing is 1.0 mm between a BGA and chip passives, and 1.5 mm to QFN/QFP. Reducing the courtyard does not establish assembly-process acceptance. The native copper/hole checks above are separate from the final assembly and mechanical review. [KiCad KLC F5.3](https://klc.kicad.org/footprint/f5/f5.3.html), [JLC SMD spacing](https://jlcpcb.com/help/article/minimum-spacing-for-smd-components)

## USB integration reservation

`candidates/bga100-power-escape-usb-reserved` preserves the generic fanout reference above and replaces only its three STM_D_P/N access tracks. It adds the USB routing agent's two 0.40/0.20 mm vias: P at U3.D9 (13.3,21.1), and N at (13.7,20.7) with a 0.11 mm B.Cu diagonal from D10 (14.1,21.1). This snapshot has **34 total vias and 100 track segments**, zero physical DRC violations and passing five-sheet parity. Its `usb-reservation.json` records every removed/added UUID for integration.

The P via is **via-in-pad and requires filled, copper-capped POFV**. The reserved USB path is not yet a completed differential route; the USB agent will retain these vias and add its matched continuation. Do not duplicate them when combining candidates. The original 32-via generic fanout remains unchanged for evidence.
