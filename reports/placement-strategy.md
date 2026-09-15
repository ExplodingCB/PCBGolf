# Compact placement strategy and measured candidates

## Current recommendation

Use `reports/placement-45x42-courtyards.json` as the next native KiCad placement. It places **239 footprints on a 45 × 42 mm PCB** and preserves the actual source and corrected-library assembly courtyards. The plan includes every remaining electrically required reference after the separately verified removal of four unconnected mounting holes and redundant R5/R6 divider resistors. JSON contains native footprint origins, rotations, and sides, plus conservative occupied bounds.

This is a placement candidate, not a completed submission. Routing, current capacity, USB impedance, electrical checks, connector insertion clearance, and final assembly checks remain required.

## Measured bounds and scoring

The native STEP exports of `compact-v1-4l` and `compact-v2-4l` measure **45 × 42 × 15.005 mm**, giving **28,359.45 mm³** of assembly volume. These measurements come from the actual exported assembly using OpenCascade, not a sum of nominal package heights. J1 sets the top height; the bottom CAN chokes set the lower extent. The exported assemblies contain 236 populated component models plus the PCB; C6, C10, and J4 are DNP in the corrected project.

At this measured size:

- Two-layer score before vias: 38,359.45.
- Four-layer score before vias: 48,359.45.
- Every 100 vias adds 5,000.
- Shrinking board width by 1 mm at fixed height saves about 630 score.
- Shrinking board height by 1 mm saves about 675 score.
- Lowering the assembly by 1 mm saves 1,890 score.
- A two-layer design may use **200 additional vias** before it loses its 10,000-point copper-layer advantage, assuming the same physical volume.

The original pad/body rectangle sum was 2,229.61 mm². Its optimistic two-sided area floor was 1,114.81 mm², before routing, courtyards, connector insertion, thermal clearance, and packing waste. Correcting oversized SOIC-8 footprints to the actual SOT-553 part and removing the approved unnecessary items lowers physical occupied area, but J1's corrected 17 mm pad span increases it. V3's actual courtyard/body envelope sum is 2,432.47 mm², about 64% of the available two-sided 3,780 mm² surface.

## Fixed interface arrangement

Coordinates are millimetres. Rotations follow KiCad; bottom footprints are flipped top-to-bottom before applying the listed angle.

| Reference | Side | Footprint origin | Angle | Access |
|---|---|---:|---:|---|
| U3 | Top | (13.0, 22.5) | 180° | Rotation puts oscillator pins on the free right side and SD pins toward the left |
| J1 | Top | (39.5, 17.5) | 180° | Barrel opening faces the right board edge |
| J2 | Bottom | (1.31074, 15.125) | 90° | microSD opening faces the left edge |
| J3 | Top | (37.0, 33.15) | 0° | Host USB-C opening reaches the bottom edge |
| J4 | Top | (7.0, 38.5) | 0° | Original 2×4 CAN pad interface retained, DNP |
| J5–J8 | Top | X = 5.0, 16.7, 28.3, 40.0; Y = 4.0 | 0° | Vertical OBD-C insertion from above |
| SW1 | Top | (22.5, 38.5) | 0° | Finger access from above |
| U4 | Bottom | (22.0, 20.0) | 0° | Consider 270° in the next route-focused revision |

The OBD-C sockets are spaced 11.3–11.7 mm apart. Their bare sockets do not intersect. The **actual required cable overmold width** still needs verification; a plug wider than the socket spacing can invalidate this arrangement. Connector cable bodies are not included in the bare PCBA STEP score and cannot be ignored when checking usability.

## Placement constraints and verification

- Native KiCad STEP positions match the planner's mirrored-Y bottom-side transform, including the asymmetric microSD socket. The convention was checked on exported models rather than assumed.
- V2 has no pair of component 3D bounding boxes intersecting by more than 0.001 mm. Separated boxes prove separated solid models. PCB/lead insertion intersections are intentionally excluded from this test.
- Actual SOT-553 model size is 1.6 × 1.6 × 0.63 mm; the original pad-only estimate missed 0.15 mm of body extent per Y side. V3 preserves the full 2.36 × 2.20 mm library courtyard.
- Actual U3 courtyard is 23.3 × 23.3 mm, and the source-board 0402 courtyards are 1.946 × 0.966 mm. These are larger than the bare pad rectangles and were the cause of V2's courtyard errors. V3 incorporates them directly, with a further 0.05 mm gap. No courtyard was artificially reduced.
- J1 requires the corrected `PJ-002AH-SMT-TR` footprint. Its copper bounding box is local X [-1.25, 7.25], Y [-8.5, 8.5], and its full courtyard is [-5.3, -8.75, 10.2, 8.75]. The first bootstrap placement used the supplied incorrect footprint; V2 and V3 reserve the corrected physical pad span.
- The planner reserves through-hole and locating-hole obstacles on the opposite side as well as the component's own side.
- MCU crystal and bypass capacitors stay on the MCU side. Hub crystal and bypass capacitors stay on the hub side. Both switching regulators, their inductors, bootstrap/input/output capacitors, and feedback parts stay on the bottom side together. Placement priorities use actual relevant IC pin locations when available.

## USB routing priorities

`reports/usb-route-corridors.json` records the native pad endpoint coordinates for all six USB differential pairs. Route these before general signals and preserve pair spacing, a continuous reference plane, and equivalent via transitions. An unrestricted autorouter trial only establishes reachability; it does not establish USB signal integrity.

With U4 at (22,20), rotating it from 0° to **270°** reduces the sum of 12 USB-net Manhattan endpoint distances from **331.9 to 288.5 mm**, and turns its four OBD-C pair groups toward the top port row. The hub crystal and local bypass capacitors must be repacked if this change is adopted. For the present 0° orientation, route the four OBD-C pairs around the left/top hub side, the host pair toward the lower-right connector, and the MCU pair toward the lower-left MCU edge. Avoid crossing the microSD socket's routing escape with all four port pairs on the same layer.

## Files

- `scripts/placement_analysis.py`: source pad/model geometry inventory.
- `scripts/compact_placement.py`: first net-attracted bootstrap placement.
- `scripts/refined_placement.py`: same-side critical loops and enlarged J1.
- `scripts/courtyard_placement.py`: current courtyard-preserving placement.
- `scripts/render_placement.py`: PNG review renderer.
- `scripts/inspect_assembly.py`: actual STEP component names and bounds.
- `scripts/audit_assembly.py`: 3D separation and measured volume report.
- `scripts/usb_corridors.py`: exact USB endpoint coordinates and hub rotation comparison.
- `reports/compact-v2-4l-mechanical-audit.json`: native V2 model separation and dimensions.
