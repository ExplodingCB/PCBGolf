# Power implementation and handoff

## Concrete candidate

Use `candidates/power-base/power-critical.kicad_pcb`, with its matching `.kicad_pro` and `.kicad_dru`. The placement-only base is `candidates/power-base/pcbgolf.kicad_pcb`; `reports/placement-power-clusters.json` records all239 positions. This is an isolated45×37×1.6mm four-layer candidate. Root and the USB agent's active board were not overwritten.

The board contains58 power/thermal vias and143 track segments. All201 copper items are locked. Sixteen vias are0.20mm holes/0.40mm copper in eFuse exposed pads and require epoxy-filled, copper-capped POFV. Their closest component-hole edge gap is2.019mm, exceeding the conservative0.45mm requirement. The exact UUID/coordinate map is in `candidates/power-base/power-audit.json`. Paid four-layer POFV is documented in `reports/pofv-four-layer.md`.

Native KiCad10.0.6 DRC reports zero error-severity violations,285 warnings, and499 reported unconnected items. The unconnected list reaches the report limit; this is an incomplete board. Combined five-sheet logical parity passes for all239 parts with zero component or pin/net differences. Reports: `critical-drc.json`, `connectivity.json` in the candidate directory.

## Electrically connected power paths

The audit unions actual filled polygons with tracks/pads on every layer, including polygon holes, then connects layers only through actual vias/PTHs. It confirms:

- Both J1 power lands, D1 and every Q1 drain pad share one copper group.
- Q1 source pads, all20 eFuse VIN pads, U2 VIN, C3 and C5 share the+12V group through In2.Cu.
- Each eFuse's five output pads connect to all four corresponding connector VBUS contacts. The four output nets remain separate. LED-series resistors R74–R77 still need their low-current branches.
- U1 SW, L1 input and C4 switch side connect together. U3 VLXSMPS→L4→C25 has a2.681mm,0.30mm main route and1.286mm,0.20mm snubber branch.

Local output pours occupy both outer layers and leave the USB center/right exit reservations. The supply transition banks use parallel vias; short pin escapes are0.20–0.80mm wide. These facts establish electrical continuity, not an ampacity rating. Filled-copper neck widths, via current sharing and return-path temperature still need calculation and hardware validation after USB/general routing.

## Limits that must remain explicit

J1 is a5A total input jack. Each TPS25944A has a nominal3.18A trip setting with28kΩ ILIM; simultaneous channel maxima exceed the jack rating. AP62300 is a3A IC, but both selected3.3µH inductors have1.8A saturation/2A thermal ratings. Do not rate either assembled rail3A from the IC name alone. The existing+3V3 rail is cascaded from+5V, so combined regulator loading matters.

The preliminary1oz/10°C screen uses3.5mm drawn input trunk width and5.5mm channel trunk width for the TI twice-full-load copper recommendation. The current pours have not demonstrated these widths at every bottleneck. No thermal or load rating is asserted.

## Required next changes

1. Move eFuse input10µF/100nF capacitors near each VIN bank. C50–C52 and several small bypasses are remote. Connector shield holes and the LQFP courtyard block the convenient lower row; the BGA100 branch frees that area. Proposed bypass repack script currently refuses this collision and has not changed the saved placement.
2. Repack U1/U2 dividers and bootstrap capacitors beside the respective pins. R3/R4 are13.65/10.31mm from U1 FB; R9/R10 are6.06/8.40mm from U2 FB. These require placement correction. The5.75mm bootstrap paths are provisional and should shorten with the move. U2SW→L2 and U1VIN→C1 remain open.
3. Complete MCU direct-SMPS input/output loop. L4 output→VFBSMPS/VCAP/VDDLDO and bulk C21/C15 remain unconnected; the bulk caps are26.14/28.04mm away and must move. U3VDDSMPS→C23 also needs a short path. L3 is the analog ferrite, not the SMPS inductor.
4. Add eFuse/MCU/regulator ground returns and general GND fanout with the parent's ground script after final placement. Exposed-pad thermal vias are already present; avoid duplicates. No ground copper ampacity claim is made.
5. Merge USB geometry, refill all zones, repeat actual connected-group and copper-neck checks, native DRC and locked-copper preservation after DSN routing. Lock flags alone do not prove an autorouter preserved copper.

## Reproduction

`route_power.py` creates local pours and parallel transitions from a separate input board; `route_critical_power.py` adds checked local switching paths. `audit_power_copper.py` audits actual filled geometry. All operate on explicitly named files. `place_power_clusters.py` is an earlier setup script and should not be rerun on the finished candidate, because it resets placement. The latest placement JSON is the integration source of truth.
