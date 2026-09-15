# USB route and power-width analyzer

Run after importing a routing session into its matching PCB:

```powershell
tools/venv/Scripts/python.exe scripts/analyze_routes.py --board candidates/compact-v4-planes/pcbgolf.kicad_pcb --output candidates/compact-v4-planes/route-analysis.json
```

The script reads the board without saving changes. It uses bundled KiCad Python to obtain native pad positions/polygons, copper layers and track/arc lengths; graph and proximity analysis run in the local Python environment.

It reports all six pairs from `reports/circuit-constraints.md`: `USB_D_N/P`, `CH1_D_N/P` through `CH4_D_N/P`, and `STM_D_N/P`.

If a package variant changes the MCU endpoint pin number, the analyzer can resolve a unique pad on the same MCU component and net. Every such remap is recorded in `endpoint_resolution`. Ambiguous or missing endpoints remain incomplete. Connector A/B contact numbers are always preserved. This supports the MCU BGA experiment without asserting that the schematic/package remap is correct; validate that separately.

- **Total track length per net:** all routed segments and branches, plus via counts and occupied layers. This is **never labelled exact skew**.
- **Endpoint paths:** shortest connected centerline path from the hub pin to each corresponding connector A/B contact, or the MCU pin. Duplicate connector pins have separate paths. Missing routes produce null lengths.
- **Pair mismatch:** differences between corresponding N/P endpoint paths. Travel within pad copper and copper zones is omitted; these are geometric estimates, not electrical-delay measurements.
- **Layer changes:** vias and plated component pads traversed by each shortest path. A separate barrel-length estimate assumes evenly spaced copper layers across nominal board thickness.
- **Obvious uncoupled routing:** sampled same-layer proximity and parallelism. Defaults are a maximum 0.50 mm copper-edge gap, 15° direction difference and 0.25 mm sampling interval. These are screening thresholds, not a controlled-impedance specification. Tune with `--max-pair-gap`, `--max-parallel-angle` and `--sample-spacing`.
- **Power copper:** minimum/maximum/distinct track widths, lengths, layers, via dimensions and zone counts for `+12V`, `+5V`, `+3V3`, `CH1_12V` through `CH4_12V`, plus discovered legacy channel-output names.

Zones are counted but are not traversed by the route graph. Power-plane neck widths, thermal spokes, current-sharing and copper thickness require separate analysis. Arc centerlines are sampled to at most 0.001 mm chord error; native arc lengths set the corresponding graph weights. Overlapping copper joins and pad connections can introduce small geometric shortcuts, so preserve the report's qualifications.

Verification: a synthetic branched net showed distinct hub-to-A and hub-to-B path lengths while retaining the larger total net length; a separate via transition reported the correct count/layers; parallel and widely separated test pairs produced the expected uncoupling results. The initial v4 board correctly reports incomplete USB paths while it is unrouted. Run KiCad DRC and combined-sheet connectivity validation separately before using the results for a final design review.
