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
- Native pre-route DRC: zero geometric/fabrication errors; **at least499**
  unconnected items remain and254 warnings (mostly inherited silk/text) need
  cleanup. KiCad caps this category at499; see the count-limit report.
- Fresh assembly dimensions45×37×14.23mm, volume23,692.95mm³. Arithmetic
  baseline43,692.95 plus50per eventual via is **not a valid challenge score**.
- V4 plane-routing trial runs in `candidates/compact-v4-planes`; V3 all-signal
  trial runs independently. Candidate imports must be checked with native DRC,
  power-current constraints, USB coupling/skew, and combined schematic parity.

## Claude
Computer Use was stopped by the user with Escape. No further UI input was
sent in that turn. Local analysis and explicitly requested subagents continued.
The installed Claude CLI was subsequently tried for a read-only Fable review;
it returned an expired OAuth session before making any model call. No review
was obtained and no Claude findings are claimed.

## September14 routing and topology work
- Public entry identity is ExplodingCB, supplied by the user; local gh matches.
  No verified contact email is available yet. No submission has been sent.
- `reports/placement-45x37-mating.json` reserves simultaneous compliant cable
  clearance. The original working root remains V5 until the topology changes
  below can be merged as one checked candidate; do not submit its old port row.
- `reports/placement-power-clusters.json` and `candidates/power-base` put all
  four eFuses on the back beneath the ports, moving40 small parts. Placement
  remains45x37mm with239 parts, zero native physical errors and exact parity.
- The USB agent is reversing channel positions to match hub pin order and
  prerouting all six pairs. J8/J7/J6/J5 run left-to-right. Rotation270 preserves
  mechanical envelopes. The first CH1 pair passes native DRC with no missing
  pair connections; all six pairs and ground references remain in progress.
- JLC04161H-3313 four-layer impedance calculation gives90.1581ohm for0.11mm
  traces with0.10mm gap; source details in `usb-impedance-stackup.md`.
- `scripts/preconnect.py` now uses only orthogonal/45-degree copper. Arbitrary
  straight angles triggered FreeRouting trace-normalization oscillations.
- `scripts/route_ground.py` adds shared, collision-checked signal-ground
  transitions without assuming unfilled via-in-pad assembly. The V8 trial has
  89 ground vias, zero native physical errors and436 uncapped missing routes.
- `scripts/prepare_router.py` exports fresh, hash-linked DSNs and removes eight
  false self-overlap reports by preserving the exact same-net copper union.
  Router DRC is not interchangeable with native KiCad manufacturing DRC.
- Old V3/V4/V7 routing trials were stopped as superseded; none produced a
  finished design. V8 four-layer and six-layer three-pass comparisons run in
  `candidates/v8-route-test` and `candidates/v8-sixlayer-test` respectively.
  The six-layer version is a routing-capacity experiment with no validated
  fabrication stackup or impedance claim.
- `reports/mcu-bga100-feasibility.json` uses ST's official pin database to show
  a complete STM32H725VGH6 allocation:82 connected balls,18 NC,10 GPIO changes.
  This 8x8mm0.8pitch package is a separate optimization branch. Schematic,
  firmware, supply scheme and real escape validation are still required.
- Paid4-layer filled/capped POFV is supported by JLC and is being specified
  for thermal pads and unavoidable hub crossovers. Use0.20mm drilled holes on
  1.6mm board;0.15mm drill is not assumed to satisfy the published10:1 ratio.

## Current measured routing results (20:20 local)

- V8 four-layer imported trial: 2,047 track segments,301 vias,199 native
  missing connections. Native physical errors:3 shorts,1 copper clearance,
  16 hole-clearance records and4 solder-mask bridges. This is incomplete.
- V8 six-layer imported trial:2,422 segments,362 vias,167 native missing
  connections. The extra2 layers and61 vias cost13,050 points while closing
  only32 more connections. Continue the smaller MCU/four-layer branch.
- Q1's fixed-wire-polygon router substitute proved unsafe after import:
  FreeRouting treats those polygons as non-obstacle conduction areas. The
  exporter now retains partly overlapping Q1 pads and only deduplicates
  fully contained J3 pads. Old polygon-based DSNs are superseded.
- KiCad10 verified locked tracks/vias export as DSN `type fix`. Critical
  USB and power routes must be locked before general autorouting.
- `analyze_routes.py` now uses layer-qualified via width (avoids a native
  assertion/hang), has a subprocess timeout, and models direct via-to-pad
  contacts. It finds all four manually routed USB port paths; CH2's final
  via balancing, the host pair and MCU pair remain in progress.
- `candidates/power-base/power-critical.kicad_pcb` has143 locked power
  segments and58 locked vias, including16 thermal vias. Native physical DRC
  has zero errors and five-sheet parity passes. Filled-copper connectivity
  confirms input/eFuse/port power paths. Local bulk caps, MCU decoupling and
  feedback placement still require the BGA placement; see power report.
- `candidates/bga100-base` retains239 parts and191 connected net names,
  matches all100 ST package pins, passes five-sheet parity and has zero
  native nonrouting errors. Initial escape routes66 of82 connected balls
  with36 vias;16 balls are blocked by opposite-side components. The power
  and escape agents are coordinating the needed placement changes.
- Local historical panda firmware is checked out read-only for analysis
  in `tools/panda-firmware` at78cf69904c332c599a297fcc2a09c08d10d429d5.
  No firmware port, public repository push, or challenge submission exists.

## September 14, 2026 — owner-requested stop
All three subagents and optimization work stopped to conserve usage. Saved the merged incomplete BGA100 board in work-in-progress and experimental firmware source in firmware/pcbgolf. This is a WIP GitHub checkpoint, not a leaderboard entry. Resume only on owner request.

