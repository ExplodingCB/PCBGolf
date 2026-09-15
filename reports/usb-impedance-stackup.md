# Verified JLC USB differential geometry

Checked 2026-09-14 with JLC's current anonymous calculator backend, using the same model, parameter configuration and WebSocket result channel as the [official impedance calculator](https://jlcpcb.com/pcb-impedance-calculator). The browser surface was unavailable; the reproducible API query is `scripts/jlc_impedance_query.py`.

## Selected stackup

**JLC04161H-3313**, nominal 1.6 mm, four copper layers, outer 1 oz, inner 0.5 oz. The selected stackup provides 0.09940 mm prepreg between either outside signal layer and its adjacent inside plane, with dielectric constant 4.1. Its core is 1.265 mm, inner copper 0.0152 mm, and outside plane copper 0.035 mm. Select this exact stackup in fabrication; the default 7628 stackup has a different spacing and needs a different calculation. [JLC stackup specifications](https://jlcpcb.com/impedance)

The live calculator's current etched-trace model for 1 oz outside copper uses a trapezoid with lower width W1 equal to the drawn width, upper width W2 = W1 − 0.5 mil, and trace thickness 1.6 mil. Its current solder-mask profile is C1 = C3 = 1.0 mil, C2 = 0.6 mil, coating Er = 3.8. These live configuration values differ from some static descriptive pages. Responses and selected material data are preserved under `reports/jlc-calculator-source/`.

## Forward-verified options

Model: `DiffEdgeCoupledCoatedMicrostrip1B`, non-coplanar differential pair, outside layer above its adjacent solid reference plane.

| Drawn trace width | Copper-edge pair gap | Calculated differential impedance | Evidence |
| --- | --- | --- | --- |
| **0.11 mm** | **0.10 mm** | **90.1581 Ω** | `jlc-usb-width011-gap010.json` |
| 0.14 mm | 0.15 mm | 90.3849 Ω | `jlc-usb-width014-gap015.json` |

The narrower option supports the USB connector escape throat. The reverse calculation for exactly 90 Ω returned 0.11079375 mm at 0.10 mm gap, within its configured ±0.5 Ω solver tolerance; using 0.11 mm was then checked independently by a forward calculation. Raw responses report `dResultValid = 1` and no calculation error. These are manufacturer-model nominal results, not measured production coupons.

## Routing application

- Route F.Cu USB over uninterrupted In1.Cu GND. Avoid slots, voids and power-plane boundaries under the pair.
- B.Cu needs its own continuous adjacent In2.Cu GND corridor. An In2.Cu +12 V plane alone does not establish the intended same-ground reference transition. Add a ground reference region and nearby ground stitching at any F/B transition.
- This model excludes adjacent same-layer coplanar copper. Keep surrounding copper sufficiently distant; if nearby pours shape the field, calculate the actual coplanar geometry instead. A practical initial clearance is at least three times the 0.0994 mm dielectric height, subject to a layout review.
- Keep connector escape width transitions short and symmetric. Do not use summed branched-net lengths as exact pair skew; use `scripts/analyze_routes.py` endpoint estimates plus native DRC.
- Encode the chosen width/gap in the USB netclass, then run native minimum copper/hole clearance checks after routing. The 0.10 mm gap is at the selected conservative trace-spacing limit, so no further narrowing is assumed.

Reproduce either result:

```powershell
tools/venv/Scripts/python.exe scripts/jlc_impedance_query.py --width 0.11 --gap 0.10 --output reports/jlc-usb-width011-gap010.json
```

The query sends only geometric calculator parameters. It does not upload board files, submit a fabrication order, or authenticate to an account.
