# PCBGolf engineering log

## Objective
Minimize a valid, manufacturable and usable PCBA score; validate and submit
the complete KiCad project plus assembly STEP through the official form.
No valid score or leaderboard submission has been claimed yet.

## Reference
- Official source commit: `7210bdb5049c5b7fdf4900a34928e2736767292a`
- Source is KiCad 10: 245 footprints, 302 named nets, no board outline,
  no tracks or vias. Initial DRC reports 499 unconnected items.
- Source has five top-level schematic sheets. CLI schematic parity against
  only the power sheet is incomplete and must not be used as a full audit.

## Local tools
- `tools/kicad/bin/kicad-cli.exe` and `tools/kicad/bin/python.exe`: KiCad10.0.6.
  Official installer SHA256 verified:
  `9e24dc47119f7c472128c2f293c5e3f35569274a44c905e60a7514d47c16ce48`.
  Extracted as portable files with official7-Zip26.03 under WSL.
- `tools/venv/Scripts/python.exe`: analytical Python with sexpdata, NumPy,
  SciPy, Shapely, Matplotlib, OCP and OR-Tools.
- FreeRouting2.4.1 and portable Temurin25 are ready in `tools/`.
- Tools stay inside this workspace and are excluded from git.

## Active work
- Main: reproducible board generator, routing integration, native DRC.
- Circuit audit agent: verified schematic/BOM/footprint corrections.
- Placement agent: concrete compact two-sided placement.
- Validation agent: strict assembly scorer, submission requirements,
  portable autorouter and netlist comparison.

## Submission gates
Complete electrical connectivity, manufacturing DRC, exact schematic parity,
power/current/thermal checks, USB routing checks, collision and mating access,
complete assembly STEP, reproducible packaged project and truthful score.

## First compact candidates
- `reports/placement-45x42*.json` and `scripts/build_candidate.py` reproduce
  candidates. Source schematic and library corrections are encoded in
  `reports/circuit-patches.json` and applied to candidate boards automatically.
- V2:239 components, exact combined5-sheet netlist parity passes. Physical
  assembly STEP measures45×42×15.005mm;28,359.45mm³ volume. This is NOT a
  valid entry score: routing is incomplete and source connector needs replacement.
- V3: uses actual courtyards and has zero native pre-routing DRC errors under
  the trial rule set. It excludes111 unused symbol pins from the router only,
  preserving their logical net assignments in the saved KiCad PCB.
- Native KiCad10 SWIG caveat: retain detached footprint wrappers until exit;
  dropping them can invalidate subsequent plugin return types. Builder handles it.
- V2 router trials used inefficient unused-pin fanout and an invalid source
  connector; stopped as superseded. V3 four-layer no-fanout routing is running.
- The originalJ3 signalPTH geometry fails JLCPCB's separate component-hole
  annular ring and hole-spacing requirements. A USB2-compatible surface-mount
  replacement is being verified; current candidates must not be submitted.
- Current-monitor resistor change33k→10k requires3.3× current-conversion
  scale adjustment, explicitly recorded in the circuit report and patch JSON.

## Current working project (V5)
- Root `pcbgolf.kicad_pcb` is now the corrected239-part45×37mm placement,
  matching the five root schematic sheets. It is **not routed**.
- Root `.kicad_pro` and `.kicad_dru` use the tested four-layer JLC draft rules.
- USB4105-GF-A host connector replaces the invalid hybrid signal-hole design;
  its four ground landing pads use the manufacturer's rounded-end shape to
  maintain>=0.22mm clearance to the unchanged locating holes.
- Native pre-route DRC: zero geometric/fabrication errors;499 unconnected
  items remain and254 warnings (mostly inherited silk/text) need cleanup.
- Fresh assembly dimensions45×37×14.23mm, volume23,692.95mm³. Arithmetic
  baseline43,692.95 plus50per eventual via is **not a valid challenge score**.
- V4 plane-routing trial runs in `candidates/compact-v4-planes`; V3 all-signal
  trial runs independently. Candidate imports must be checked with native DRC,
  power-current constraints, USB coupling/skew, and combined schematic parity.

## Claude
Computer Use was stopped by the user with Escape. No further UI input was
sent in that turn. Local analysis and explicitly requested subagents continued.
