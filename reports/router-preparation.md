# Router input preparation and limits

`scripts/prepare_router.py` produces a fresh DSN from a source PCB without saving the PCB. It first runs native KiCad DRC and stops on physical error-severity violations. It records a source SHA256; import any resulting SES only into the matching source PCB. Local generation example:

```powershell
tools/venv/Scripts/python.exe scripts/prepare_router.py --board candidates/compact-v8-45degrees/ground.kicad_pcb --output reports/router-preflight/v8-prepared.dsn
```

The adjacent `.preflight.json`, `.native-drc.json`, `.geometry.json` and `.raw.dsn` files retain the transformation evidence. Existing tracks are checked for non-octilinear segments; a listed segment is a routing-stability screen, not a physical DRC failure.

## Geometry-preserving transformations

- Clears only generated `unconnected-*` no-connect pad assignments in the in-memory router copy. All native pad/net assignments remain unchanged.
- Deduplicates coincident or contained same-net SMD lands only when the retained copper covers the removed land. J3's four overlapping GND/VBUS contact pairs are examples.
- Retains partly overlapping same-net lands as their original DSN pads. Q1's drain lands 5–9 remain intact. Their router self-overlap reports are accepted only because native KiCad confirms the physical same-net geometry.
- Removes only the redundant router pin references from DSN net lists. The original PCB and schematics keep every physical numbered pad.

Both KiCad and FreeRouting's DSN paths convex-hull custom pad polygons, so a concave custom pad is not an exact representation. The earlier fixed-wire-polygon substitute was also unsafe: FreeRouting imports these as **non-obstacle conduction areas**, despite `type fix`. The v8 post-import native check exposed three Q1 shorts and one clearance error. The exporter now retains the original partly overlapping pads. All earlier inputs using converted Q1 polygons are superseded. [KiCad exporter documentation](https://docs.kicad.org/doxygen/specctra__export_8cpp.html), [FreeRouting2.4.1 wire import](https://github.com/freerouting/freerouting/blob/v2.4.1/src/main/java/app/freerouting/io/specctra/parser/Wiring.java)

## Historical v8 input diagnosis (superseded)

Source `compact-v8-45degrees/ground.kicad_pcb`, SHA256 `cd2a79df0559fb58b395fc0a50975ad76326d69450160bec9066380c2f8ddf75`: native physical errors0, unconnected436, non-octilinear straight segments0. Fresh raw DSN router DRC reported101 violations; the original prepared DSN reported93. Removing all8 Q1/J3 self-overlap reports was not sufficient proof of correct obstacle behavior. The corrected DSN only deduplicates the four contained J3 pairs. No native PCB changes were made by either export.

The remaining router reports comprise:

| Reports | Finding |
| --- | --- |
| 88 | Same-net Pin/Via attachment reports. FreeRouting's via `attachAllowed` and pin drill-attachment rules are stricter than copper connectivity; its DRC calls every Pin a hole, including SMT pins. These are not 88 independently measured drill-spacing failures. |
| 4 | One NPTH keepout reported on four layers. KiCad exports its0.66 mm hole with a1.06 mm keepout, already including0.20 mm radial hole clearance; the router adds0.10 mm more. |
| 1 | A foreign-net via/pad copper gap reported as0.0997 mm against0.1000 mm. Native checks pass the original curved geometry; inspect rounding/shape approximation if the final route touches that margin. |

Do not silently ignore all future router reports because this particular input is understood. Do not globally enable via-in-SMD attachment to hide these reports: it can let the router propose new via-in-pad geometry requiring a different assembly process. [Pin behavior](https://github.com/freerouting/freerouting/blob/v2.4.1/src/main/java/app/freerouting/board/model/items/Pin.java), [via behavior](https://github.com/freerouting/freerouting/blob/v2.4.1/src/main/java/app/freerouting/board/model/items/Via.java), [DRC classification](https://github.com/freerouting/freerouting/blob/v2.4.1/src/main/java/app/freerouting/drc/DesignRulesChecker.java)

## Hole clearance mapping

DSN copper spacing does not directly express every KiCad custom hole constraint. For a centred circular/oval through pad, hole-to-foreign-copper clearance equals copper-edge clearance plus the pad's minimum annular ring. In this v8 board:

- Nominal connector pad dimensions suggested at least0.20 mm annular rings, but the imported result produced16 hole-clearance reports at four via/connector locations. That deduction did not hold for every effective DSN/native shape and layer. Native hole-clearance checks must decide acceptance; the exporter does not yet fully encode these constraints.
- The0.45/0.20 mm vias have0.125 mm nominal annular rings. Thus0.10 mm copper spacing implies0.225 mm via-hole-to-foreign-copper spacing, exceeding0.20 mm.
- NPTH keepouts already encode0.20 mm hole clearance and are further enlarged by the router's copper clearance, as above.

These deductions do not apply automatically after changing via size, pad offsets, inner annuli or footprint geometry. A0.25/0.15 mm via has only0.05 mm annular ring and would require at least0.15 mm copper spacing to meet0.20 mm hole clearance. A PTH ring of0.15 mm would require0.15 mm copper spacing to meet0.30 mm hole clearance. Native post-import hole and annular DRC is mandatory.

FreeRouting supports `wire`, `via`, `pin`, `smd` and `area` clearance classes; the parser explicitly does not implement a class-pair suffix such as `smd_via_same_net`. No nonexistent same-net exception flag has been added. [Verified class parser](https://github.com/freerouting/freerouting/blob/v2.4.1/src/main/java/app/freerouting/io/specctra/parser/Structure.java)

## Locked critical routes

KiCad10 exports tracks and vias with `SetLocked(True)` as DSN `type fix`. Verified by exporting all472 v8 track/via elements locked and counting472 `fix` records. USB, oscillator, switching-power and already checked local copper must be locked before handing remaining routing to FreeRouting. Copper zones are not protected physical obstacles by this mechanism.

## Normalization stability

Version2.4.1 includes per-net suppression once trace normalization hits2000 iterations, but clones reset that suppression and the all-trace normalization path has its own loop. Clean, nonoverlapping octilinear pre-routes reduce one known source of split/combine oscillation. [Normalization fix PR741](https://github.com/freerouting/freerouting/pull/741), [current implementation](https://github.com/freerouting/freerouting/blob/v2.4.1/src/main/java/app/freerouting/board/facade/BasicBoard.java)

Do not switch to2.2.4 for this symptom: a reported regression crashed on pre-routed KiCad DSN files in that version. The same reporter found2.1.0 and1.9.0 handled their test file, making2.1.0 a justified comparison baseline if2.4.1 still stalls. That is not a performance or correctness guarantee for PCBGolf. [Upstream issue759](https://github.com/freerouting/freerouting/issues/759)

## Commands

Route with `-de input.dsn -do output.ses -mp 3 --router.optimizer.enabled=false --router.fanout.enabled=false`. Supply `-da`, `--gui.enabled=false`, `--api_server.enabled=false` and a task-local profile, as `tools/freerouting/route.ps1` does. `--router.scoring.via_costs` is the verified setting path; `--router.via_costs` is invalid in2.4.1. `-mt 0` sets the optimizer thread count and does **not** disable its stage: the explicit `--router.optimizer.enabled=false` flag is required for routing-only trials, verified against pinned `GlobalSettings.java` and `RouterSettings.java` and the v8 run.

**`-drc output.json` performs DRC only and exits.** Never append it to a routing run. In2.4.1 the DRC filename is written in the process working directory even when a directory was supplied, so use the intended output directory as the working directory.
