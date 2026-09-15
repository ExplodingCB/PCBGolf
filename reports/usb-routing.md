# Critical USB routing handoff

## Frozen result

`candidates/compact-v6-usb/pcbgolf.kicad_pcb` contains all six USB2 differential pairs on the 45 × 37 mm BGA100 placement. Its SHA-256 is `26e415a34c48df2f99a4949cb7b7c267e3b41954c95b710ab42058513fc0015e`.

Source: `candidates/bga100-power-escape-usb-reserved/pcbgolf.kicad_pcb`, SHA-256 `5782dc9af71da970fa03c2ad8e56940334bf2bed77e5315e483b365e95a40fde`. The prepared candidate preserves all non-USB BGA escape copper. It regenerates the two reserved STM USB vias at their exact original positions; it contains no duplicate STM vias.

Merge `reports/usb-paired-routes.json`: **223 locked USB track segments, 40 signal vias, 17 ground return vias, and 10 In2 GND reference patches**. Net names and native layer IDs are explicit. The full file/hash/fabrication inventory is `reports/usb-critical-manifest.json`. Placement remains that of the frozen source.

## Validation

- Native KiCad custom manufacturing DRC: **zero error-severity physical violations and zero USB unconnected items** after refilling zones. The rest of the board remains unfinished: 499 unconnected items and 604 non-error DRC warnings remain in this isolated candidate.
- Five-sheet schematic parity: **239 components, zero component or pin-net differences**, `reports/usb-connectivity-parity.json`.
- Every USB track and every newly added signal/return via is locked. Non-octilinear segments must retain their exact coordinates through DSN export/import.
- Every signal path has equal P/N layer-transition counts, including both reversible contact groups.

| Pair | A orientation mismatch | B orientation mismatch | P/N vias on each path |
|---|---:|---:|---|
| Host USB | 1.150 mm | 1.150 mm | 2 / 2 in either orientation |
| CH1 | 0.610 mm | 0.960 mm | A: 2 / 2; B: 4 / 4 |
| CH2 | 0.440 mm | 1.130 mm | A: 2 / 2; B: 4 / 4 |
| CH3 | 0.597 mm | 0.973 mm | A: 2 / 2; B: 4 / 4 |
| CH4 | 0.538 mm | 1.032 mm | A: 2 / 2; B: 4 / 4 |
| STM MCU | 0.569 mm | — | 1 / 1 |

Lengths are native connectivity graph centerline measurements, excluding travel inside pads. Full-thickness F↔B barrel estimates cancel between P/N because transitions are balanced. This is a geometry audit, not an electromagnetic simulation or USB compliance test. Detailed paths, endpoint resolution and uncoupled-length estimates are in `reports/usb-native-path-analysis.json`. The 1.25 mm mismatch target comes from [Microchip AN26.2](https://ww1.microchip.com/downloads/en/Appnotes/AN26.2-Application-Note-DS00001876C.pdf).

## Stackup and fabrication

Use **JLC04161H-3313, 1.6 mm, four copper layers**. Long paired traces use **0.11 mm width / 0.10 mm copper-edge gap**. The official JLC coated differential-microstrip calculator returned **90.158064 Ω** for this geometry, using 0.0994 mm outer-to-adjacent-plane dielectric and Er 4.1. Evidence: `reports/jlc-usb-width011-gap010.json`, [JLC impedance calculator](https://jlcpcb.com/impedance). Short connector fanouts and layer transitions are explicitly uncoupled and need final SI review.

All new through vias use **0.40 mm copper diameter / 0.20 mm drill**. The manifest explicitly flags **14 vias requiring POFV: resin fill, planarization and copper cap** where a drill intersects a component pad. That includes 13 USB signal vias and one ground return via. Apply these requirements in the fabrication output; a JSON flag alone does not instruct the manufacturer. Existing BGA and power via-in-pad requirements remain additional to this inventory.

## Actual reference copper

Top USB references the In1 GND plane. Short bottom branches reference **priority-100 In2 GND patches**, agreed with the power agent so VDDLDO priority-40 regions cannot replace their reference copper.

`scripts/usb_zone_geometry.py` exports the **actual filled polygons including holes**, and uses native connectivity to check each return via on In1 and In2. `scripts/usb_reference_audit.py` checks a **±0.25 mm corridor around every one of the 223 conductor segments** against the filled reference copper. All segments pass outside explicitly enumerated signal/plated-hole/NPTH antipads and the zone's 0.15 mm minimum-copper-neck removals. Numeric tolerances are recorded: 0.003 mm fill comparison and 0.012 mm antipad polygon allowance. The short 0.6 mm balancing bridges have merged endpoint antipad openings; they are launch exceptions rather than continuously plane-backed lines.

All **17** ground return vias have native direct connectivity on **both In1 and In2**. Every signal via is within **1.4731 mm** of one of these returns. The 1.5 mm placement target is a design choice, not a cited standards limit. Full results, exception coordinates and native return checks are in `reports/usb-reference-audit.json` and `reports/usb-filled-zones.json`.

## Integration requirements

1. Merge the exact USB JSON onto the latest power candidate, deduplicating the two already reserved STM vias and any coincident ground vias.
2. Preserve all locked track coordinates, vias and priority-100 reference outlines during routing. Reserve their inner-layer filled copper against generic signal routing and power regions.
3. Refill zones and rerun native manufacturing DRC, all-sheet parity, USB path analysis and the filled-reference audit **on the final integrated board**. Added vias and inner-layer tracks can interrupt an otherwise valid reference even when ordinary copper clearance passes.
4. Recheck actual filled power connectivity after the GND patches are merged. This isolated USB validation does not prove regulator, CAN or whole-board completion.

Reproduction order: prepare the frozen source with `route_usb_pairs.py --prepare --preserve-existing`; export native geometry with `usb_geometry.py`; run `usb_route_plan.py`, `usb_reference_planes.py`, and `finalize_usb_manifest.py`; apply the plan with `route_usb_pairs.py --plan`; refill native DRC; rerun connectivity/path/reference audits and refresh the manifest hashes. Each script owns only the isolated USB candidate or USB reports.
