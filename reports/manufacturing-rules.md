# Draft fabrication rules and power-copper recommendations

## Result and scope

`reports/jlc4layer.kicad_dru` is a syntax-checked draft for **four-layer rigid FR4, 1 oz outer copper, through vias**. It is not a fabrication approval or electrical/thermal certification. Only isolated copies under `reports/manufacturing-rule-validation/` were changed. Source and active candidate boards were not modified.

KiCad 10.0.6 accepted the file and completed native DRC without parsing errors. On the older compact-v2-4l candidate it found 12 component-pad annular-ring failures, 15 hole-spacing failures and 17 hole-to-copper failures. These are useful findings, not a clean-board claim. A separate probe confirmed that a **0.075 mm via annular ring passes**, while the component PTH minimum still rejects the old J3 rings near 0.10 mm. Logs, JSON and the isolated test boards are retained in the validation directory.

## Fabrication constraints in the draft

The source is the current [JLCPCB rigid capabilities table](https://jlcpcb.com/capabilities/pcb-capabilities), checked September 14, 2026.

| Item | Draft requirement | Interpretation |
|---|---:|---|
| Copper trace/space | 0.10/0.10 mm | Conservative relative to published 4-layer 1 oz capability |
| Copper to routed edge | 0.30 mm | Project margin above the published 0.20 mm |
| Via hole to foreign-net copper | 0.20 mm | Applies from the hole perimeter |
| Component PTH hole to foreign-net copper | 0.30 mm | Covers 0.28 mm outside and 0.30 mm inside conservatively |
| Mechanical hole separation | 0.20 mm | Default, including via pairs |
| PTH component hole to another PTH component hole | 0.45 mm | Separate condition from vias |
| Via drill / pad diameter | 0.15 / 0.25 mm minimum | Smallest process has extra cost; defaults remain 0.20 / 0.45 mm |
| Via annular ring | 0.05 mm minimum | Does not relax the component-pad rule |
| Component PTH annular ring | 0.15 mm minimum | **Four-layer only**; use 0.18 mm for two-layer 1 oz |
| Plated slot minor dimension | 0.35 mm | Four-layer process |
| NPTH round hole / routed slot | 0.50 / 1.00 mm | Mechanical minima |
| Different-net SMD pad gap | 0.15 mm | Distinct from ordinary track clearance |

Blind, buried and microvias are disallowed in this draft because no corresponding manufacturing process has been qualified. Same-net solder wicking, mask webs, castellations, edge plating and assembly access require additional application-specific checks.

## KiCad integration

The [KiCad 10 custom-rule documentation](https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom_design_rules) defines version 1 syntax. More specific conditions appear later because matching rules are evaluated in reverse order. The file uses `A.Type == 'Via'` separately from `A.Type == 'Pad' && A.isPlated()`. `hole_to_hole` measures edge-to-edge drill separation; `hole_clearance` checks different-net copper from the drilled perimeter. It must not be replaced with a same-net physical clearance rule that would reject the pad surrounding its own plated hole.

For an adopted candidate, place the draft beside the board using the same basename, for example `pcbgolf.kicad_dru`. Recommended `.kicad_pro` values in `board.design_settings.rules`:

```json
{
  "min_clearance": 0.10,
  "min_track_width": 0.10,
  "min_copper_edge_clearance": 0.30,
  "min_hole_clearance": 0.20,
  "min_hole_to_hole": 0.20,
  "min_through_hole_diameter": 0.15,
  "min_via_diameter": 0.25,
  "min_via_annular_width": 0.05
}
```

The `.kicad_dru` is essential: the project-wide annular-ring floor alone cannot express both via and component-pad requirements. Preserve error reporting for annular width, drill size, hole separation, hole clearance, copper clearance, edge clearance and track width. Refill zones before the final DRC. Netclass trace widths are routing defaults; they are not a proof of current capacity.

Reproduce the isolated syntax check and numerical calculations:

```powershell
tools/venv/Scripts/python.exe scripts/manufacturing_rules.py --board candidates/compact-v2-4l/pcbgolf.kicad_pcb
```

## Actual supply constraints

The [PJ-002AH-SMT-TR manufacturer datasheet](https://www.sameskydevices.com/product/resource/pj-002ah-smt-tr.pdf) rates the input jack at **5 A total**. The four channel limits cannot be added to claim a 12.72 A board input rating. The upstream supply, mating plug, jack, reverse-polarity FET, copper and return path all have to support the selected aggregate load. The design currently has no demonstrated aggregate 5 A enforcement; the source must be current-limited or an appropriate board-level protection change must be designed.

For a 28 kΩ current-limit resistor, the [TPS25942/44 datasheet](https://www.ti.com/lit/ds/symlink/tps25944l.pdf) gives about **3.18 A nominal per channel**. Use 3.5 A as a provisional tolerance allowance until the exact resistor/device limits are closed. Its layout guidance calls for power paths capable of at least twice full-load current, so a 7 A copper screen is included below. It also requires short power paths, local bypassing, a controlled signal-ground connection and thermal copper/vias under the exposed pad. A successful router run does not establish these properties.

The [AP62300 datasheet](https://www.diodes.com/datasheet/download/AP62300.pdf) rates the IC for 3 A, but also recommends 2 oz outer copper, ground layers, and thermal vias for its full-load layout. The current **1 oz** draft needs its own thermal validation. The circuit review found that source L1/L2 (MEKK2520T3R3M, alias LSENC2520KKT3R3M) have about 1.8 A saturation and 2.0 A thermal ratings; thus sustained 3 A outputs are **not established**. The 5 V regulator feeds the 3.3 V regulator, so the 5 V load budget must include that conversion load. OBD-C 12 V power bypasses these bucks.

## Width calculations and proposed netclasses

These are screening calculations with **35 µm outer copper, 17.5 µm inner copper, and a 10°C trace temperature-rise target**. The historical IPC-2221 expression used by [KiCad's track-width calculator](https://docs.kicad.org/10.0/en/pcb_calculator/pcb_calculator.html) is:

`I = k × ΔT^0.44 × A^0.725`, with cross-section `A` in mil² and `k = 0.048` outside or `0.024` inside.

`scripts/manufacturing_rules.py` solves for width. This estimate is not an IPC-2152 thermal model: trace length, neighboring copper, copper thickness tolerance, thermal coupling, ambient temperature and pad/plane connections can materially change the result. The selected widths below include a 25% drawn-width increase to cover a possible 20% width reduction. Verify actual finished copper and loading before release. Widths are for continuous trunk sections; short pad escapes and parallel pad fingers need explicit current-sharing and heat-spreading assessment.

| Proposed class / path | Screening current | Calculated outer width | Proposed drawn trunk width |
|---|---:|---:|---:|
| POWER_INPUT_5A: jack power and common +12V trunk | 5.0 A | 2.766 mm | 3.5 mm or wider pour |
| POWER_CHANNEL: normal per-channel current allowance | 3.5 A | 1.691 mm | 2.2 mm normal-current screen |
| POWER_CHANNEL: 2× margin from TI layout guidance | 7.0 A | 4.399 mm | **5.5 mm effective main-path copper** |
| POWER_5V_3A: L2 output to shared 5 V load | 3.0 A | 1.367 mm | 1.8 mm, conditional on inductor/thermal redesign |
| POWER_3V3_3A: L1 output rail trunk | 3.0 A | 1.367 mm | 1.8 mm, conditional on actual rail rating |
| MCU_BRANCH_1A: provisional MCU supply branch budget | 1.0 A | 0.300 mm | 0.4 mm; 1 A is a planning budget, not measured MCU demand |
| SIGNAL: ordinary low-current logic | Application-dependent | Not evaluated as a power path | 0.127 mm default; 0.10 mm fabrication floor |

The local TPS input path also needs the TI current margin. A common input segment carrying the full 5 A has a 10 A margin screen of 7.194 mm finished, or 9.0 mm drawn; use a broad, short plane connection where practical and review the connector/FET bottlenecks. This conservative screen is an indication to engineer the power distribution, not a requirement to route every small power pin with a 9 mm trace.

Avoid long power paths on the default half-ounce inner layers. At 3 A the same simplified inner-layer calculation needs about 7.11 mm; above 5 A it predicts more than 10 mm and leaves the documented width range of the expression. Keep a continuous ground return plane and verify actual local plane neck widths. Give the return path the same current/thermal scrutiny as the supply.

Net assignments to review:

- POWER_INPUT_5A: `Net-(J1-PWR)` and `+12V` (confirm any renamed jack net).
- POWER_CHANNEL: the four `Net-(J5-VBUS-PadA4)` through `Net-(J8-VBUS-PadA4)` output nets; derive exact names from the current candidate.
- POWER_5V_3A and POWER_3V3_3A: `+5V` and `+3V3` trunks. Branches share these net names, so use reviewed geometry/regions rather than blindly applying one enormous width to every decoupling stub.
- GND: a continuous return plane and broad power returns, not a universal 0.127 mm autorouted tree.
- `Net-(U1-SW)` and `Net-(U2-SW)`: short buck switch-node copper according to the reference layout; do not include them in a global wide-plane pour or expand them without EMI review.

## Via planning

Use **0.60 mm pad / 0.30 mm finished drill** as the initial power-via geometry; use 0.45/0.20 mm for ordinary signal vias. The smaller fabrication floor is not a power-via rating. Keep high-current routes on one outer layer when practical to avoid many current-sharing vias and their score penalty.

For a 1.6 mm board, assumed 18 µm barrel copper and 35°C copper temperature, a hollow-cylinder resistance calculation gives approximately:

| Finished drill | Calculated barrel resistance |
|---|---:|
| 0.20 mm | 2.37 mΩ |
| 0.30 mm | 1.62 mΩ |
| 0.40 mm | 1.24 mΩ |

The model uses copper resistivity 1.724×10⁻⁸ Ω·m at 20°C and coefficient 0.00393/°C; it follows the basic cylindrical conductor approach used in [KiCad's via calculator source](https://docs.kicad.org/doxygen/panel__via__size_8cpp_source.html). JLC's 18 µm figure is an average plating figure, **not a verified minimum for this order**. Resistance alone does not establish a permissible temperature rise or reliable current sharing.

Until the via/plane thermal model is validated, a conservative planning cap is **0.5 A per 0.30 mm power via**, with symmetrical placement and wide connections on both ends. That suggests at least 10 vias for a 5 A transition, 6 for a 3 A rail, and 14 for a 7 A channel-margin transition. This is an explicit engineering planning assumption, not a manufacturer ampacity specification. Reducing via counts needs a justified thermal/current-sharing analysis or a larger cross-section; do not silently route a whole power path through one small signal via.

Thermal-via requirements at the regulator/eFuse exposed pads remain separate from this current-sharing count. Unfilled via-in-pad may wick solder; placement, fill/tent process and assembly must be specified. Low score never substitutes for measured load, rail-voltage, temperature-rise and fault-response validation.
