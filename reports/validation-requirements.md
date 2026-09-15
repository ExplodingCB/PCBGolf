# PCBGolf validation and submission requirements

Checked against official sources on 2026-09-14. This document describes validation requirements; it is not a claim that the current candidate is ready for fabrication or submission.

## Official acceptance and score

The challenge scores the assembled board's bounding-box volume in mm³, plus 50 per via and 5,000 per enabled copper layer. A compact layout must preserve the original interfaces and functionality, be manufacturable as a bare board by JLCPCB, be physically assembleable, work, and permit compatible mating connectors. A copper outline or board-area estimate alone is insufficient. Source: [official challenge](https://github.com/commaai/PCBGolf).

Submit a ZIP containing the finalized KiCad project and a complete assembly STEP through the [official submission form](https://forms.gle/US88Hg7UR6bBuW3BA). Multiple entries are allowed; reviewers publish competitive results. The prize deadline is October 12, 2026. The [leaderboard](https://comma.ai/leaderboard#pcbgolf_challenge) has no visible PCBGolf score rows in the retrieved page as of this check. Form fields and authentication requirements have not been verified; do not infer submission success from creating the ZIP.

## Fabrication limits to configure

The current [JLCPCB rigid capabilities table](https://jlcpcb.com/capabilities/pcb-capabilities) gives these useful limits for 1 oz copper:

| Feature | Published capability |
|---|---|
| Trace/space, 1–2 layers | 0.10/0.10 mm |
| Trace/space, multilayer | 0.09/0.09 mm |
| Via hole/diameter | 0.15/0.25 mm, added cost; 0.20 mm drill preferred |
| Via drill to another via drill | 0.20 mm |
| Via hole to track/inner copper | 0.20 mm |
| SMD pad to another-net pad | 0.15 mm |
| Routed board edge to copper | 0.20 mm |
| PTH annular ring, 2 layers/multilayer | 0.18/0.15 mm absolute minimum |
| Standard FR4 thickness options | Start at 0.4 mm; verify the selected layer stack |

The small via ring limit does not remove drill-to-copper spacing. Thin boards require compatible finish and sufficient connector stiffness. The same page's FAQ and detailed table disagree about blind/buried vias; use through-vias unless a specific advanced process is confirmed. These are fabrication constraints, not minimum safe widths for power or controlled-impedance signals.

## Engineering review that geometry/DRC cannot replace

- Check 12 V input and each powered OBD-C channel for required current, copper width/temperature rise, connector ratings, protection and regulator stability.
- Verify USB and clock placement/routing against the component reference designs, actual stackup, differential geometry, return paths, stubs and matching requirements.
- Keep capacitors adjacent to their associated supply pins; preserve the analog current-sense loop and switch-mode power loop geometry.
- Check all component models against actual manufacturer package drawings. The model must represent body, leads, shield and every protruding part correctly.
- Test solder access, underside clearances, assembly sequence and physical collision in the complete 3D model, including drill and board-thickness tolerances.
- Provide clearance for all five USB/OBD-C plugs, the barrel plug, the microSD card's insertion/ejection envelope, and finger/tool operation of the push button. Close-packed receptacles can fit while their plugs do not.
- Audit J4 (CAN 2x04): source marks it DNP and has no 3D model. If the intended interface requires a fitted header, obtain the correct header model and include it in the assembly. The source's four mounting positions are also DNP; their removal needs to stay consistent between board and schematic.

## Repeatable local checks

The source project has **five top-level schematic sheets**. KiCad 10.0.6 `pcb drc --schematic-parity` can load only the primary sheet in this project, causing false extra-footprint reports. Exporting just `pcbgolf.kicad_sch` also captures only the power sheet.

`scripts/validate_connectivity.py` exports each top-level sheet to KiCad XML, merges component/pin connectivity, and compares it against the candidate PCB. It checks component presence, value, footprint, DNP state, and electrical peer groups for every numbered pin. Peer groups avoid treating harmless KiCad generated-net renames as rewiring. Reports include hashes to detect changed inputs.

```powershell
tools/venv/Scripts/python.exe scripts/validate_connectivity.py --board candidates/tiny.kicad_pcb --project pcbgolf.kicad_pro --output reports/tiny-connectivity.json
```

`scripts/score_assembly.py` counts top-level via objects and enabled layers by their `.Cu` names (not KiCad numeric IDs), checks outlines/model presence, consumes or runs DRC, and reads final STEP geometry with OpenCascade. It reports axis-aligned bounding-box dimensions and volume, never material volume. A raw arithmetic result is `candidate_score`; `validated_score` stays null when checks fail or evidence is incomplete. Automated success still requires the engineering review above.

```powershell
tools/venv/Scripts/python.exe scripts/score_assembly.py --board candidates/tiny.kicad_pcb --project-root . --step candidates/tiny.step --kicad-cli tools/kicad/bin/kicad-cli.exe --export-step --connectivity-json reports/tiny-connectivity.json --output reports/tiny-score.json
```

The export includes the board and all populated components. Source DNP components are separately listed in the audit and omitted with KiCad's `--no-dnp` flag. A supplied STEP without a fresh controlled export remains provisional because it might omit components. CAD-model fidelity, mating access and collisions still require review. Avoid `--board-only`, `--no-components`, and component filters when creating the submission STEP.

Scoring implementation verified using two separated known solid boxes: their aggregate bounding box measured 12 × 3 × 4 mm = 144 mm³, instead of the 48 mm³ material volume. The same check verified four copper-layer penalties, one via penalty, and invalidation for missing outline/model. A source capacitor model independently measured 2 × 1.25 × 1.25 mm as expected.

## Portable routing installation

Installed entirely under the project:

- `tools/freerouting/freerouting-2.4.1.jar` — [upstream release v2.4.1](https://github.com/freerouting/freerouting/releases/tag/v2.4.1), released September 3, 2026. SHA-256: `251101c3eeac22d7e7dfcf6796603279e5d1000283eb82d8f093780f7afc6aa9`.
- `tools/java/jdk-25.0.4.1+1-jre/` — [official Eclipse Temurin Java 25 archive](https://github.com/adoptium/temurin25-binaries/releases/tag/jdk-25.0.4.1%2B1). ZIP SHA-256: `4c95451cea98556def2c54f7782933f52a26d4a36bd85e1d59f0364464828b07`.
- `tools/freerouting/route.ps1` — wrapper selecting this JRE/JAR, disabling GUI, API server and anonymous analytics, and saving settings/logs under `tools/freerouting/profile`.

Both upstream archive checksums match. Java version and wrapper help invocation pass. No global installation, PATH modification, server or account is needed.

```powershell
& tools/freerouting/route.ps1 -de candidates/tiny.dsn -do candidates/tiny.ses -mp 20 -mt 4
```

Use the production DSN/SES exchange path and import the SES back into the matching placed board. Native KiCad Python provides `ExportSpecctraDSN` / `ImportSpecctraSES`. After import, refill copper zones and run KiCad DRC; router-local clearance checking does not cover every KiCad/JLCPCB rule.

The [upstream CLI documentation](https://github.com/freerouting/freerouting/blob/v2.4.1/docs/command_line_arguments.md) exposes pass limits (`-mp`), optimizer threads (`-mt`), selection/update strategies, and layer direction controls. **Empirical/source corrections for 2.4.1:** `-drc` runs DRC-only and exits, so omit it from a routing invocation. `-mt 0` only sets the optimizer thread count; it does **not** disable the optimizer. Use `--router.optimizer.enabled=false` for a bounded routing-only trial. The documented `--router.via_costs=150` flag is rejected as unknown; the verified path is `--router.scoring.via_costs=150`. These documentation examples were disproven by candidate runs and checked against the pinned source. Try bounded feasibility runs before long optimization. Do not ignore GND/power net classes unless they are deliberately handled separately and later verified connected. The router's internal optimization score is different from the challenge formula. Compare all candidates using the same final assembly scorer.

Actual 2.4.1 settings were subsequently verified against bundled bytecode and a DEBUG DRC-only run: `--router.fanout.enabled=false` disables the fanout phase, and `--router.scoring.via_costs=150` is the accepted nested scoring field. `reports/router-settings-verification.log` explicitly records both as applied CLI settings, taking priority over DSN settings, and confirms analytics are disabled. These can be added to routing comparisons; higher via cost does not guarantee a better final challenge score.

The initial compact-v2-4l candidate STEP measures 45.0 × 42.0000001 × 15.0050001 mm: 28,359.4503 mm³. Four copper layers add 20,000, before via penalties. This is only an unrouted candidate estimate: the report correctly rejects eligibility while 499 connections remain unconnected.

## Final packaging gate

1. Finish complete routing, zone fill, board DRC, combined-sheet connectivity parity and engineering review.
2. Confirm the actual stackup, drilling, copper, assembly and connector-access constraints.
3. Export the complete assembly STEP from the exact board being submitted; inspect its bounds and component inclusion.
4. Include the PCB, project, all five schematics, custom symbol/footprint libraries, library tables and referenced STEP assets in a self-contained project ZIP. Resolve `KIPRJMOD` paths inside that ZIP.
5. Save final score and validation reports with input hashes; inspect the ZIP contents before uploading.
6. Complete the official form and retain the form's confirmation. A submitted entry is distinct from a reviewed leaderboard listing.
