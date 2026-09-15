# Shared connector CAN bus routing trial

The frozen `candidates/canbus-vip-inner/pcbgolf.kicad_pcb` connects every CAN bus
between all four device ports and J4. It is an isolated routing experiment on
the earlier power placement, not the final integrated board.

## Verified result

- All 32 requested connector-to-connector links routed across eight nets:
  CAN0_H/L through CAN3_H/L.
- Native KiCad `GetConnectedItems` confirms J4/J5/J6/J7/J8 belong to one copper
  group on each of the eight nets. Chokes, termination and sensing branches
  still need their routes.
- Native all-track DRC has zero physical errors and no hole-spacing warnings.
- Connector fanout uses 32 vias, of which 28 are in pads and require filled,
  copper-capped fabrication. Bus continuation adds 15 vias. All use 0.45 mm
  copper and 0.20 mm drills; the local fabrication floor was not relaxed.
- Routing uses F.Cu, B.Cu and In2.Cu on the existing four-layer board. In1 stays
  the ground reference. In2 signals cut the +12V fill; final power continuity
  and copper-neck capacity must be rechecked after integration.

The two-outer-layer control trial reached only 15 of 32 links on this placement.
The lower-side eFuses and other parts block several connector bus corridors.
Moving the eFuses below the connector row is a separate optimization to examine
after the integrated four-layer candidate works.

## Reproduce

`escape_can_ports.py` runs with native KiCad Python and supports an explicit
`--allow-filled-via-in-pad` mode. Its adjacent `.escape.json` maps every added
via UUID to its contact and required fill/cap process.

`route_can_bus.py` runs with the workspace venv. Pass the escaped board and
`--fanout` report; `--inner-signal` enables the existing In2 layer for signals.
The script uses a 0.05 mm grid, explicit copper/drill obstacles and octilinear
tracks. Existing copper is retained, and the output is a separate board.

`audit_net_connectivity.py` uses native connected-item groups without KiCad's
DRC reporting cap. It reproduced the earlier v8 result of exactly 199 missing
pad-group connections, independently agreeing with its uncapped DRC report.
This count excludes orphan copper and all manufacturing/functionality checks.

Evidence resides beside the frozen candidate: `can-plan.json`, `drc.json` and
`native-net-groups.json`. The source snapshot hash is recorded in the plan.
The input's old MCU/power placement means the routes must be regenerated or
rechecked against the final BGA, power and USB copper before use.
