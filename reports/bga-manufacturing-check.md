# STM32H725AGI6 BGA manufacturing screen

Checked 2026-09-14 against JLCPCB primary sources. Target: UFBGA169, 0.50 mm pitch, 0.27 mm NSMD lands, nominal 1.60 mm FR-4. This is a process feasibility screen, not fabrication acceptance.

## Decision

The exact combination is **not yet established as manufacturable under the published generic rules**. A compact BGA experiment can proceed in isolation, but a score or successful autoroute must not be treated as fabrication qualification. The two unresolved points are dense BGA escape clearance and the actual drilling process for 0.15 mm design holes through 1.60 mm material.

## Published capability and selected process

JLC lists 0.15 mm via holes with 0.25 mm copper diameter, giving a nominal 0.05 mm annular ring. It prefers 0.20 mm holes and a diameter difference of 0.15 mm. Generic via-hole-to-track and inner via-hole-to-copper clearance are both 0.20 mm. Multilayer 1 oz trace/space is 0.09/0.09 mm; local 3 mil BGA fanout traces are permitted, while BGA pad-to-trace clearance is at least 0.09 mm. These minima are separate from the much larger component-PTH annular-ring requirement. [JLC manufacturing capabilities](https://jlcpcb.com/capabilities/pcb-capabilities)

For a via inside a solder land, specify **epoxy-filled and copper-capped POFV**, or copper-paste-filled and capped. JLC's covering guide identifies those processes as suitable for BGA/SMT holes, gives a maximum 0.50 mm plugging-hole size, and requires order remarks identifying the holes to fill. Ink plugging is unsuitable for holes in pads or within 0.35 mm of pad openings. Free resin filling is offered on six-layer and higher boards; a four-layer experiment must explicitly obtain that process in its quote rather than assume ordinary tenting is sufficient. [JLC via covering, updated September 9, 2026](https://jlcpcb.com/help/article/pcb-via-covering)

Use ENIG for this experiment. Preserve the manufacturer land pattern; shrinking solder lands to create route channels also requires an assembly/land-pattern justification.

## Calculated escape geometry

The calculations below are geometric deductions, not additional manufacturer rules. All distances are millimetres.

| Pattern | Available geometry | Result against generic rules |
| --- | --- | --- |
| Trace between 0.27 lands on 0.50 pitch | Gap = 0.50 − 0.27 = **0.23** | 0.09 trace + two 0.09 gaps needs **0.27**; fails |
| Local 3 mil trace between those lands | 0.0762 + 2 × 0.09 = **0.2562** | Still exceeds **0.23** gap |
| 0.25-diameter dogbone via centred between four balls | Diagonal centre distance = 0.50 / √2; copper gap = distance − 0.135 − 0.125 = **0.09355** | Below conservative 0.10 via-copper gap; drill-to-land gap with 0.15 hole is only **0.14355**, below generic 0.20 |
| 0.09 trace between 0.15 holes on 0.50 pitch | Hole-edge clearance on either side = (0.50 − 0.15 − 0.09) / 2 = **0.13** | Below generic **0.20** hole-to-track clearance |
| Same route using a 0.20 hole | (0.50 − 0.20 − 0.09) / 2 = **0.105** | Larger drilling does not solve the routing gap |

Deleting unused inner-layer copper annuli cannot remove a through-hole barrel or relax the drill-to-copper clearance. Sparse fanout may still be feasible if the actual assigned pins leave larger channels; assess the exact ball map and routed geometry, not only the grid pitch.

JLC's September BGA guide illustrates 0.15/0.25 mm filled vias and 0.09 mm inner traces after removing unused inner pads. It simultaneously recommends trying for outer via diameters of at least 0.35 mm. The dense-grid example does not state an exception to the generic 0.20 mm hole clearance. Therefore it cannot by itself authorize a custom 0.13 mm DRC limit. [JLC BGA design guidelines, updated September 9, 2026](https://jlcpcb.com/help/article/bga-design-guidelines---pcb-layout-recommendations-for-bga-packages)

The same conflict appears in a customer question on JLC's site; the publicly returned page contains no answer. It is evidence of ambiguity, not evidence of approval. [Unanswered inner-layer BGA clearance question](https://jlcpcb.com/help/answers/detail/943-0.5mm-BGA-copper-to-hole-clearance-on-inner-layers)

## Board thickness and drill interpretation

JLC's aspect-ratio article specifies the **pre-plating mechanical drill diameter** as the denominator and states a 10:1 limit in its own capability guidance. For a literal 0.15 mm mechanical drill, 1.60 / 0.15 = **10.67:1**; 0.20 mm gives **8:1**. A 1.20 mm board and literal 0.15 mm drill would also be 8:1, but board thickness must remain compatible with the selected connectors and stackup. [JLC via aspect ratio, updated April 22, 2026](https://jlcpcb.com/blog/via-aspect-ratio-critical-pcb-reliability)

The design hole value may be treated differently from the production drill, because copper plating reduces hole diameter and fabricators can apply compensation. Do not infer the compensated drill, or claim rejection solely from the nominal ratio. Obtain the selected process's actual drill/finished-hole interpretation and approved thickness together. The public generic table does not prove the simultaneous 1.60 mm / 0.15 mm combination.

## Evidence needed to close the screen

For a layout using the dense pattern, a manufacturing review must identify the actual layer count/stackup, 1.60 mm thickness, 0.15 mm design-hole convention, production drill, 0.25 mm via copper, 0.27 mm BGA lands, removal of unused inner annuli, and the smallest **actual** hole-to-track and hole-to-plane gaps. It must explicitly accept the filled/capped process and any clearance below 0.20 mm. Retain that acceptance with the final fabrication package. No such acceptance has been obtained in this task.

Until then, keep the generic 0.20 mm hole clearance enabled. Do not waive BGA DRC failures or silently assign a smaller region-specific hole clearance merely to let the router finish.
