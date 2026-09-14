# Circuit audit and constraints

Audit date: 2026-09-14. Inputs: the official source schematics, original board pad nets in `source-inventory.json`, manufacturer documents, and official KiCad libraries. Main PCB edits remain with the routing agent. Machine-readable edits and pad remaps are in `circuit-patches.json`.

## Changes completed in schematics and local libraries

| References | Original defect or excess | Implemented correction |
|---|---|---|
| U9–U12 | Five-pin amplifier symbols attached to SOIC-8 footprints; MPN belonged to a different pinout | NCS20071XV53T2G, SOT-553 footprint and STEP; existing pins 1–5 retained |
| U1, U2 | AP62300T value conflicted with AP62300WU-7 MPN and feedback values | Standard AP62300WU-7 explicitly selected; U1 divider simplified as below |
| R3, R4 | U1 divider used three parallel 100k resistors and 10k | R4 becomes 31.2k 1%; R3 becomes 10k 1%; R5/R6 removed |
| R70–R73 | 33k current-monitor loads exceeded the 3.3V ADC range during valid port loading | 10k 1% loads, with documented firmware calibration change |
| U13–U16 | Value TPS25942 conflicted with actual MPN TPS25944ARVCR | Displayed value corrected to TPS25944A; MPN and functionality retained |
| D1 | SMAJ16CA-13-F MPN attached to SMB footprint/model | Correct SMA footprint and STEP, same diode MPN and nets |
| J1 | Generic footprint did not fit specified PJ-002AH-SMT-TR; second power land was netless | Manufacturer pad geometry; both power lands numbered PWR1 |
| J3 | Original hybrid USB-C connector had duplicate terminal nets and PTH hole spacing below the selected fabricator's minimum | GCT USB4105-GF-A host receptacle; all USB2 signal contacts are SMT; exact official KiCad footprint and STEP |
| BH1–BH4 | Optional mounting-only holes blocked compact packing | Removed with their isolated wires and GND symbols, as directed by root |
| J4 | DNP CAN header | Accessible 2×4 pad interface retained; no installed header model assumed |

### Amplifier correctness

The NCS20071 SOT-553 ordering variant has pin 1 IN+, 2 VSS, 3 IN−, 4 OUT, 5 VDD. The SOT23-5 variant instead puts OUT on 1, IN+ on 3, and IN− on 4. The imported source already used the SOT-553 mapping; merely shrinking to the source MPN's SOT23-5 would have made the circuit wrong. The corrected footprint preserves the existing input/output nets. [onsemi NCS20071 datasheet, Figure 1](https://www.onsemi.com/download/data-sheet/pdf/ncs20071-d.pdf).

Exact amplifier routing:

| Device | IN+ pin 1 | IN− pin 3 | OUT pin 4 | Power |
|---|---|---|---|---|
| U9 | `Net-(U9-+)`, R50.2 | `Net-(U9--)`, R51.2/R52.1 | `Net-(R62-Pad1)` | 2 GND; 5 +12V |
| U10 | `Net-(U10-+)`, R53.2 | `Net-(U10--)`, R54.2/R55.1 | `Net-(R63-Pad1)` | same |
| U11 | `Net-(U11-+)`, R56.2 | `Net-(U11--)`, R57.2/R58.1 | `Net-(R64-Pad1)` | same |
| U12 | `Net-(U12-+)`, R59.2 | `Net-(U12--)`, R60.2/R61.1 | `Net-(R65-Pad1)` | same |

These amplify/indicate CAN bus behavior. Do not remove the surrounding resistor networks as apparently redundant parts.

### Regulators

AP62300 has nominal 0.800V feedback; AP62300T uses 0.763V. The output equation is `Vout = Vfb × (1 + Rtop/Rbottom)`. U1 now computes to 3.296V. Its resistor-only worst-case range is approximately 3.247–3.346V; reference tolerance and load regulation also apply. U2 remains 52.3k/10k and computes to 4.984V. The original U1 combination of a non-T MPN and three parallel 100k top resistors computed to 3.467V. [Diodes AP62300 datasheet, output selection and ordering table](https://www.diodes.com/datasheet/download/AP62300.pdf).

Keep C4/C9 across BST/SW immediately at U1/U2. Keep input capacitors close to VIN/GND, L1/L2 close to SW, and feedback traces separate from switching copper. Output capacitors serve both stability and load transients. Do not shrink their effective capacitance without checking DC-bias derating. The 5V converter supplies the 3.3V converter; this is a cascade, not two independent 12V converters.

L1/L2 are 3.3µH MEKK2520T3R3M, now catalogued as LSENC2520KKT3R3M: 1.8A rated current, 1.8A specified saturation current at 30% inductance reduction, 2A thermal-rise rating, 0.144Ω maximum DCR. Retaining the part does **not** establish a 3A continuous output rating for the assembled regulator. At nominal 12V→5V, 3.3µH, 750kHz, computed ripple is about 1.18A peak-to-peak; a 1A load already reaches about 1.59A peak. Validate actual rail loading before further reducing inductors. [Taiyo Yuden current product page](https://ds.yuden.co.jp/TYCOMPAS/or/detail?pn=LSENC2520KKT3R3M&u=M).

### Port current sensing and protection

The specified TPS25944A uses circuit-breaker behavior; TPS25942 uses current limiting. Nominal trip setting is approximately `89/R_ILIM[kΩ]`; existing 28k gives 3.18A per channel. IMON nominal gain is 52.3µA/A. Old 33k burden resistance produced 1.726V/A; the corrected 10k produces 0.523V/A. [TI TPS25942/44 datasheet](https://www.ti.com/lit/ds/symlink/tps25944a.pdf).

**Firmware must use `current_A = adc_voltage_V / 0.523`**, equivalently approximately 1.912A/V. A conversion previously calibrated to the same IC with 33k must be multiplied by 3.3. Validate against known loads. The four channels remain independently enabled and independently measured. This change does not authorize raising the current limit or total input rating.

Exact monitor signals: U13.19→CH1_IMON→U3.47, U14.19→CH2_IMON→U3.50, U15.19→CH3_IMON→U3.52, U16.19→CH4_IMON→U3.45. Their loads R70/R71/R72/R73 terminate at GND. Keep quiet measurement returns separated from high-current voltage drops by placement and copper routing, while retaining one continuous ground reference.

The main +12V path runs J1→Q1→U13–U16→four OBD-C VBUS groups. Main input current is the sum of channel loads plus electronics, not one channel current. Use broad pours and multiple parallel vias wherever a layer transition is unavoidable. A tiny generic signal trace on this path is unacceptable. The source input jack is rated 5A total, so four 3.18A limits do not imply permission to draw 12.7A simultaneously. Q1 is SI7101DN, a low-resistance P-channel part; its current capability depends on thermal copper and temperature. [Vishay SI7101DN datasheet](https://www.vishay.com/docs/63232/si7101dn.pdf).

## Interface and routing constraints

### OBD-C is a proprietary full-contact Type-C interface

J5–J8 require **all signal contacts**, including the eight contacts normally used for SuperSpeed. A cheap USB2-only 6/12/16-pin connector is incompatible. Preserve this mapping on every OBD-C connector:

| Contacts | Function |
|---|---|
| A2/A3 | CAN0_H / CAN0_L |
| A11/A10 | CAN1_H / CAN1_L |
| B2/B3 | CAN2_H / CAN2_L |
| B11/B10 | CAN3_H / CAN3_L |
| A6+B6 / A7+B7 | Channel USB D+ / D− |
| A8 / B8 | Channel SBU1 / SBU2 ignition and relay circuitry |
| A4+A9+B4+B9 | Channel-switched +12V |
| A1+A12+B1+B12 and shield | GND |
| A5/B5 | Source NC; preserve |

Preserve the four CAN transceivers, common-mode chokes L5–L8, and common CAN buses across all four ports and J4. Keep connector access and plug overmold clearance; bare receptacle bodies fitting does not prove four cables can mate simultaneously.

### USB hub

USB2517 needs five downstream connections: four OBD-C ports plus the MCU on port 7. Ports 5/6 are unused. A four-port hub is not a replacement unless extra hub hardware is added. Preserve the +3V3 supply bypassing, 1.8V internal regulator output capacitors, R27 12k bias resistor, and 24MHz Y2 network. Do not drive other loads from the internal 1.8V outputs. Unused ports should be disabled in configuration. [Microchip USB2517 hardware checklist](https://ww1.microchip.com/downloads/en/DeviceDoc/USB2517-Hardware-Design-Checklist-00004211.pdf).

Exact differential pairs:

| Pair | Endpoints |
|---|---|
| USB_D_N/P | J3 A7/B7 and A6/B6 → U4.58/59 |
| CH1_D_N/P | U4.1/2 → J5 A7/B7 and A6/B6 |
| CH2_D_N/P | U4.3/4 → J6 |
| CH3_D_N/P | U4.6/7 → J7 |
| CH4_D_N/P | U4.8/9 → J8 |
| STM_D_N/P | U4.55/56 → U3.100/101 (PA11/PA12) |

Route each pair together over continuous ground. Use stackup-derived impedance, short matched paths, minimal layer changes, and short connector-pin joins rather than branched stubs. Keep switch-node copper away. A generic autorouter's successful connection report does not verify differential impedance or skew. J3 CC1 uses R31||R32=5k to GND; CC2 uses R44||R45=5k. They must remain separate. J3 VBUS is host-detect power only; never join it to the 12V OBD-C bus.

### Connector dimensions and thickness

J1 corrected footprint follows the manufacturer's drawing: four lands 2.5×4mm, 6mm row separation, 17mm outer span, and 1.7/1.8mm locating holes. Two lands are physical terminal 1. Nominal PCB thickness is 1.6mm; body height is 11mm. The source generic footprint was materially smaller. [Same Sky PJ-002AH-SMT-TR drawing](https://www.sameskydevices.com/product/resource/pj-002ah-smt-tr.pdf).

J5–J8 MPN 10132328-10011LF is an 8.8mm-high vertical receptacle, manufacturer-listed PCB thickness 1.57mm, rated 5A on VBUS/GND. Its board-side tail geometry must be respected. [Amphenol product](https://www.amphenol-cs.com/product/1013232810011lf.html), [manufacturer drawing](https://cdn.amphenol-cs.com/media/wysiwyg/files/drawing/10132328.pdf).

J3 is now **GCT USB4105-GF-A**, a USB2 Type-C top-mount receptacle. The original unused SuperSpeed contacts are omitted; CC1, CC2, USB D+/D−, VBUS, GND and grounded shell are preserved. This substitution applies only to host J3: J5–J8 still require 24 contacts. The standard GF-A variant has 0.95mm shell stakes, 3.31mm height, and 8.94mm width. The official KiCad footprint has a 10.64×8.94mm courtyard, 0.20mm minimum signal-pad gaps, and four 0.60mm-wide plated shell slots with 0.20mm annular rings. This avoids the original JAE's 0.40mm gap between plated holes, below JLCPCB's published 0.45mm minimum. [GCT manufacturer drawing](https://gct.co/files/drawings/usb4105.pdf), [official KiCad footprint](https://gitlab.com/kicad/libraries/kicad-footprints/-/blob/master/Connector_USB.pretty/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.kicad_mod), [JLCPCB capabilities](https://jlcpcb.com/capabilities/pcb-capabilities).

The downloaded GCT drawing was visually checked against the footprint. OpenCascade measures the matching STEP at x=±4.470mm, y=−3.675…4.105mm, z=−0.950…3.310mm. Retain the current 1.6mm PCB for the verified J1 and J5–J8 mounting geometry; J3 no longer creates an additional thickness restriction. The earlier JAE duplicate-pad repair is superseded and its footprint is unused.

Native DRC found the stock GCT shared outer ground lands only 0.1944mm from locating holes. Those four logical pads (A1/B12 and A12/B1) now use capsule ends, roundrect ratio 0.5, retaining their 0.60×1.15mm envelope and both 0.65mm holes. Calculated nominal copper-to-hole clearance is 0.23296mm. All other pads retain stock geometry.

## MCU miniaturization branch

Retaining every existing pin function is the low-risk electrical approach. UFBGA169, 7×7mm, is the leading replacement for the 20×20mm LQFP144 body. STM32H725AGI6 is an active orderable variant. PG9/PG10, used for CAN2 here, are absent from the 100-pin and WLCSP115 package pin tables; those packages require a redesigned pin allocation. The MCU has three FDCAN controllers; source CAN1 (PB5/PB6) and CAN3 (PB12/PB13) use alternative pins of FDCAN2. Do not claim four simultaneously independent MCU CAN controllers. Source behavior can select the transceivers. [ST datasheet](https://www.st.com/resource/en/datasheet/stm32h725zg.pdf), [ST product page](https://www.st.com/en/microcontrollers-microprocessors/stm32h725ag.html).

A BGA branch must preserve the SMPS/VCAP/VDDLDO topology, all power balls, PA11/PA12 USB, SDMMC pins, analog monitor inputs, and boot button. Escape routing, thermal ground connections, and a verified fabricator stackup determine whether its saved area outweighs via/layer penalties. The existing BOOT0 button and USB programming path should remain usable; the source does not expose SWD/NRST.

The separate `mcu-bga-remap.json` now records all 144 original pins, their exact functions/nets, and all 169 target ball assignments with pad coordinates. All original functions exist; 104 connected source pins become 103 connected target balls because the number of repeated supply pins differs. Repeated supply functions are assigned as groups. The official KiCad 9.0.4 symbol and footprint have been saved, and selected critical assignments were corroborated against ST Table 8. Main U3 remains unchanged.

The available legacy official KiCad STEP measures 7×7mm with top z=0.75mm, while the current ST drawing gives 0.53mm nominal/0.60mm maximum package height. It is flagged as a conservative placeholder, not an exact model. The 0.27mm pads match ST's recommendation; at 0.50mm pitch they leave only 0.23mm between adjacent pad edges. A route with 0.10mm clearance on each side would have just 0.03mm remaining width, so ordinary routing between adjacent balls is impossible. A branch must prove its fanout using diagonal dogbones, NC pad locations, and the selected fabricator's actual rules.

## Verification and remaining limits

All modified KiCad s-expressions parse. All five sheets export netlists using KiCad 10.0.6. The official files are five independent schematic roots, so **exporting only `pcbgolf.kicad_sch` exports the power section, not the full board**. Each sheet's exported netlist is in `reports/pcbgolf*.net.xml`.

Power-sheet ERC has zero reported violations under project settings. Separate other-sheet ERC reports include unresolved project-library context, isolated cross-sheet labels, undriven supplies, and VCAP power-output pin-type conflicts. This is not a whole-design clean ERC claim. Source PCB connectivity remains the reconciliation authority until sheets are integrated and all endpoint mappings are verified.

No prototype has been powered or signal-integrity tested. Required final evidence includes full connectivity/DRC, exact component-body and connector-clearance geometry, power-path widths and thermal assessment, hub enumeration, USB traffic, SD access, each port's enable/current readback, CAN operation, ignition/relay outputs, and simultaneous mating accessibility.
