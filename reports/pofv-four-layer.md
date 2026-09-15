# Four-layer thermal via-in-pad process

JLCPCB explicitly offers paid POFV on four-layer PCBs; the free default applies to six and higher layers. This is stated both in its [POFV product announcement](https://jlcpcb.com/news/free-via-in-pad-6-20-layer-pcbs-pofv) and its current [via filling guide](https://jlcpcb.com/blog/via-filling-guide). Checked 2026-09-14. No order or manufacturer acceptance of our finished layout has been obtained.

The proposed thermal via is **0.20 mm design hole / 0.40 mm copper diameter**, giving a nominal 0.10 mm annular ring. This exceeds the POFV announcement's 0.05 mm minimum and 0.075 mm preferred ring; its hole is within the stated 0.20–0.50 mm range. Maintain more than 0.45 mm separation from regular component PTH and NPTH holes, as that POFV page specifies. Four vias per eFuse exposed ground pad are a layout proposal; this process check does not establish device thermal performance.

At nominal 1.60 mm thickness, a literal 0.20 mm drill gives an 8:1 aspect ratio, within JLC's published maximum 10:1 guidance. The actual fabrication drill/finished-hole convention is still set during manufacturing preparation. [JLC aspect-ratio guidance](https://jlcpcb.com/blog/via-aspect-ratio-critical-pcb-reliability)

Use **epoxy-filled and copper-capped**, with a flat solderable plated surface. Copper-paste-filled and capped is an available alternative if thermal analysis needs it. Ordinary solder-mask tenting or ink plugging does not provide the same via-in-pad surface. JLC requests explicit notes or an image showing which vias need filling and recommends reviewing production files. [JLC via covering instructions](https://jlcpcb.com/help/article/pcb-via-covering)

## Fabrication note draft

> Four-layer nominal 1.60 mm FR-4. Select the paid epoxy-filled and copper-capped POFV option. Fill and copper-cap the 0.20 mm thermal via holes located in the exposed ground pads of U13, U14, U15 and U16, identified in the accompanying via map. Preserve a flat solderable pad surface and the specified ENIG finish. Do not fill component connector PTH slots, plated mounting holes or NPTH mechanical holes. Confirm production files before manufacture.

Update references and via map to match the final board. If other same-diameter vias should also be filled, explicitly say so; do not ask the manufacturer to infer the distinction from hole diameter alone.
