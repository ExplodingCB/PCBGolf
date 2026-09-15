# Isolated STM32H725VGH6 variant

`candidates/bga100-base` contains the five-sheet project, board, local symbol/footprint libraries and STEP models. It changes U3 to an 8 × 8 mm TFBGA100 on 0.8 mm pitch. It remains an unrouted engineering candidate with firmware work outstanding.

## Validation completed

- All **239 components** retained; all **191 original connected PCB net names** retained.
- **100 distinct package balls:** 82 connected, 18 deliberately no-connect.
- Exact merged five-sheet schematic-to-board parity **passed**, with zero component differences and zero pin-net differences. Fifteen automatically generated net-name differences are electrically equivalent; the comparison checks actual peer connections.
- All 100 symbol pin numbers and normalized function names match [ST's official STM32H725VGHx pin XML](https://github.com/STMicroelectronics/STM32_open_pin_data/blob/master/mcu/STM32H725VGHx.xml). The ten moved GPIOs have their **names and numbers** changed in the symbol.
- Native KiCad 10 DRC under the copied JLC four-layer custom rules found **zero error-severity nonrouting violations**. It reported 250 warnings: 247 silk/text, two existing local footprint-library mismatches (J3/D1), and one isolated +12V plane region. It reported 499 unconnected records, which is KiCad's per-type cap and therefore a lower bound.
- Root project file hashes were unchanged during preparation. The 169-ball experiment and active routing candidates were not modified.

Evidence: `reports/bga100-connectivity.json`, `reports/bga100-native-drc.json`, and `candidates/bga100-base/bga100-status.json`. The board hash in the status and parity reports identifies the tested copy.

## Mapping policy

Connected signals claim their required target balls first. Unused original GPIOs are assigned only after these claims; this prevents an old no-connect such as PE5 from stealing its newly assigned BTN signal. Then remaining target no-connects retain matching functions. The smaller package drops redundant source supply terminals; every actual target supply ball is connected. No original connected signal net is deleted.

| Original GPIO | New GPIO / ball | Preserved net |
|---|---|---|
| PF7 | PA2 / H3 | Net-(U3-PF7) |
| PF8 | PA3 / G5 | Net-(U3-PF8) |
| PF9 | PA7 / K3 | Net-(U3-PF9) |
| PF10 | PC5 / J4 | Net-(U3-PF10) |
| PF11 | PB0 / K4 | CH3_IMON |
| PE15 | PE5 / A2 | BTN |
| PD12 | PE6 / A1 | CH3_SBU1_IGN |
| PD13 | PE7 / H5 | CH3_SBU2_RELAY |
| PG9 | PD13 / H10 | CAN2_TX |
| PG10 | PD12 / H9 | CAN2_RX |

Required alternate functions and ADC channels are recorded in `reports/mcu-bga100-feasibility.json`. Existing firmware is not binary compatible: pin definitions, ADC selection/channels, timing/DMA and startup supply configuration need implementation and build verification.

## Package and assembly geometry

The official [KiCad footprint](https://gitlab.com/kicad/libraries/kicad-footprints/-/blob/master/Package_BGA.pretty/TFBGA-100_8x8mm_Layout10x10_P0.8mm.kicad_mod) uses 0.400 mm copper pads, 0.035 mm radial solder-mask expansion and 0.8 mm pitch. These agree with ST's TFBGA100 recommendations. ST specifies a 0.400 mm stencil opening, 0.100–0.125 mm stencil thickness and a 0.120 mm pad escape trace example. Maximum package height is 1.20 mm. [ST DS13311 Rev 5, Tables 127–128](https://www.st.com/resource/en/datasheet/stm32h725ag.pdf)

The [official KiCad STEP model](https://gitlab.com/kicad/libraries/kicad-packages3D/-/blob/master/Package_BGA.3dshapes/TFBGA-100_8x8mm_Layout10x10_P0.8mm.step) is included unchanged. OpenCascade measures bounds x/y ±4 mm, z −0.010 to +1.102 mm: 8 × 8 × 1.112 mm. The small negative ball extent is part of that model. Use ST's 1.20 mm maximum height for clearance review. Downloaded files and SHA-256 hashes are recorded in the status file; cached originals are in `reports/bga100-assets`.

## Escape feasibility, still to route

Unlike the 0.5 mm-pitch option, the 0.8 mm grid leaves 0.40 mm between adjacent 0.40 mm pads, enough for one 0.12 mm trace with two 0.10 mm clearances. A centered 0.45 mm copper / 0.20 mm through-drill dogbone between four balls has about 0.141 mm copper-to-pad clearance and 0.266 mm hole-to-pad clearance. These calculations meet the current generic project rules without assuming via-in-pad, microvias or a special BGA exception. A 1.6 mm board / 0.20 mm nominal drill gives an 8:1 ratio. This is geometric feasibility, not a completed escape or fabricator acceptance.

Actual routes must still satisfy hole-to-copper and hole-spacing rules on every layer, continuous USB return reference, power/decoupling placement and all native DRC checks. Through-via count and usable routing space remain to be measured.

## MCU supplies

TFBGA100 exposes **VDD33USB at E8 and no VDD50USB ball**. E8 remains on +3V3; no new 5 V input is required. The external USB 3.3 V supply scheme is documented by ST. VLXSMPS remains on the L4 switch-inductor net; VFBSMPS, VCAP and VDDLDO stay on VDDLDO; VDDSMPS stays on +3V3 and VSSSMPS on GND. L3 is the separate analog ferrite. The direct-SMPS scheme applies to BGA packages; local decoupling placement and firmware startup configuration still need implementation. [ST DS13311, Table 8 and §3.7](https://www.st.com/resource/en/datasheet/stm32h725ag.pdf), [ST AN5419](https://www.st.com/resource/en/application_note/an5419-getting-started-with-stm32h723733-stm32h725735-and-stm32h730-value-line-hardware-development-stmicroelectronics.pdf)

The independent package-supply review is recorded in `reports/mcu-bga100-supply-check.md`. It confirms no extra 5 V supply terminal should be invented and calls for reallocated local decoupling around the reduced supply-ball count.

## Reproduce

Rebuild the isolated copy from the then-current root project and run parity/DRC:

```powershell
tools/venv/Scripts/python.exe scripts/prepare_bga100_variant.py
```

Validate the existing copy without replacing it:

```powershell
tools/venv/Scripts/python.exe scripts/prepare_bga100_variant.py --validate-only
```

The script does not launch routing, alter the root project or submit the design.
