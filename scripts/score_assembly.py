"""Audit and score a PCBGolf board and its complete assembly STEP (millimetres).

Examples (run with tools/venv/Scripts/python.exe):
  scripts/score_assembly.py --board pcbgolf.kicad_pcb --output reports/source-score.json
  scripts/score_assembly.py --board candidates/tiny.kicad_pcb --step candidates/tiny.step \
      --kicad-cli tools/kicad/bin/kicad-cli.exe --export-step --output reports/tiny-score.json

The raw arithmetic is `candidate_score`, never a claim of challenge eligibility.
`validated_score` is null unless all automated evidence is complete and passes.
Even then electrical, assembly, mating access and fabrication review are required.
OCP reads STEP units and measures the axis-aligned bounding box of actual BREP
geometry, NOT the material/solid volume. No footprint/model envelope estimate
is substituted when the final STEP is absent. DNP footprints are audited and
reported separately; their interface/functionality implications need review.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import sexpdata as sx


def tag(node):
    return str(node[0]) if isinstance(node, list) and node else None


def children(node, name):
    return [v for v in node if tag(v) == name]


def first(node, name, default=None):
    return next((v for v in node if tag(v) == name), default)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_model(raw, root, definitions):
    variables = {**os.environ, **definitions, 'KIPRJMOD': str(root)}
    expanded = re.sub(r'\$\{([^}]+)\}', lambda m: variables.get(m[1], m[0]), raw)
    result = Path(expanded.replace('\\', '/'))
    return result if result.is_absolute() else root / result


def outline_audit(board):
    """Presence and endpoint-closure check; KiCad DRC validates topology."""
    shapes = []
    for item in board:
        if not isinstance(item, list):
            continue
        for shape in ([item] if tag(item) != 'footprint' else item):
            if (tag(shape) or '').startswith(('gr_', 'fp_')) and first(shape, 'layer') == [sx.Symbol('layer'), 'Edge.Cuts']:
                shapes.append(shape)
    endpoints, unsupported = [], []
    for shape in shapes:
        kind = tag(shape).split('_', 1)[1]
        if kind in ('line', 'arc'):
            start, end = first(shape, 'start'), first(shape, 'end')
            if start and end:
                endpoints.extend([tuple(float(v) for v in start[1:3]), tuple(float(v) for v in end[1:3])])
            else:
                unsupported.append(kind)
        elif kind not in ('rect', 'circle', 'poly'):
            unsupported.append(kind)
    # Endpoint coordinates in footprint-local outlines cannot be compared with
    # board coordinates safely; leave full topology validation to KiCad DRC.
    has_fp_edges = any((tag(x) or '').startswith('fp_') for x in shapes)
    unmatched = []
    if not has_fp_edges:
        for point in endpoints:
            neighbours = sum(math.dist(point, other) <= 0.001 for other in endpoints)
            if neighbours != 2:
                unmatched.append(point)
    return dict(shape_count=len(shapes), unmatched_endpoints=unmatched,
                unsupported_shapes=unsupported, footprint_edges=has_fp_edges,
                topology_requires_kicad_drc=True)


def measure_step(path):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise ValueError('OpenCascade could not read STEP')
    # STEPControl converts STEP-declared input units to its MM system length.
    reader.SetSystemLengthUnit(1.0)
    transferred = reader.TransferRoots()
    shape = reader.OneShape()
    if not transferred or shape.IsNull():
        raise ValueError('STEP has no transferable geometry')
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    if box.IsVoid() or box.IsOpen():
        raise ValueError('STEP bounding box is empty or unbounded')
    lo, hi = box.CornerMin(), box.CornerMax()
    bounds = [lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()]
    size = [bounds[i + 3] - bounds[i] for i in range(3)]
    if any(not math.isfinite(v) or v <= 0 for v in size):
        raise ValueError(f'Invalid 3D dimensions: {size}')
    explorer, solids = TopExp_Explorer(shape, TopAbs_SOLID), 0
    while explorer.More():
        solids += 1
        explorer.Next()
    return dict(path=str(path), sha256=digest(path), bounds_mm=bounds,
                size_mm=size, bounding_box_volume_mm3=math.prod(size),
                solid_count=solids, transferred_roots=transferred,
                method='OpenCascade BRepBndLib.AddOptimal; axis-aligned; target units mm')


def inspect_drc(data):
    expected = ('violations', 'unconnected_items')
    if any(not isinstance(data.get(key), list) for key in expected):
        raise ValueError('DRC JSON must contain violations and unconnected_items arrays')
    violations = data['violations']
    unconnected = data['unconnected_items']
    parity = data.get('schematic_parity', [])
    if not isinstance(parity, list):
        raise ValueError('Unrecognized schematic_parity structure')
    counts = collections.Counter(str(v.get('type', 'unknown')) for v in violations)
    # KiCad10.0.6 DRC_ENGINE::RunTests caps clearance/unconnected at499 and
    # every other error code at199, independently of --all-track-errors.
    # A count at the cap is a lower bound, not a useful exact progress metric.
    all_counts = counts + collections.Counter(str(v.get('type', 'unknown')) for v in unconnected + parity)
    saturated = {kind:dict(reported_count=count,per_type_limit=499 if kind in ('clearance','unconnected_items') else 199)
                 for kind,count in all_counts.items()
                 if count >= (499 if kind in ('clearance','unconnected_items') else 199)}
    return dict(violation_count=len(violations), violation_types=dict(counts),
                unconnected_count=len(unconnected), schematic_parity_count=len(parity),
                saturated_types=saturated,counts_are_complete=not bool(saturated),
                count_limitation='KiCad per-type caps:499 clearance/unconnected,199 other types; saturated values are lower bounds',
                count_limit_source='https://gitlab.com/kicad/code/kicad/-/blob/10.0.6/pcbnew/drc/drc_engine.cpp',
                warnings=sum(v.get('severity') == 'warning' for v in violations),
                source=data.get('source'), kicad_version=data.get('kicad_version'))


def reference_equivalence(board, reference_path):
    """Compare physical pin-to-net assignment and part value to source PCB.

    This checks preserved source PCB connectivity, not schematic validity. A
    purposeful circuit redesign needs an independent electrical review instead.
    """
    reference = sx.loads(reference_path.read_text(encoding='utf-8'))

    def mapping(parsed):
        result = {}
        definitions = {str(n[1]): str(n[2]) for n in children(parsed, 'net') if len(n) > 2}
        for fp in children(parsed, 'footprint'):
            props = {v[1]: v[2] for v in children(fp, 'property')}
            ref = props.get('Reference', '?')
            pinmap = collections.defaultdict(set)
            for pad in children(fp, 'pad'):
                if not pad[1]:
                    continue
                net = first(pad, 'net')
                name = str(net[-1]) if net else ''
                if net and len(net) == 2:
                    name = definitions.get(name, name)
                pinmap[str(pad[1])].add(name)
            result[ref] = dict(value=props.get('Value'), pins={k: sorted(v) for k, v in pinmap.items()},
                               dnp='dnp' in [str(v) for v in first(fp, 'attr', [])[1:]])
        return result

    wanted, actual = mapping(reference), mapping(board)
    added, removed = sorted(actual.keys() - wanted.keys()), sorted(wanted.keys() - actual.keys())
    changed = [dict(reference=ref, source=wanted[ref], candidate=actual[ref])
               for ref in sorted(wanted.keys() & actual.keys()) if wanted[ref] != actual[ref]]
    return dict(reference_board=str(reference_path), sha256=digest(reference_path),
                added=added, removed=removed, changed=changed, passed=not (added or removed or changed),
                scope='Reference PCB part values, DNP attributes, and numbered pad-to-net assignments')


def audit(args):
    board_path = args.board.resolve()
    root = (args.project_root or board_path.parent).resolve()
    board = sx.loads(board_path.read_text(encoding='utf-8'))
    if tag(board) != 'kicad_pcb':
        raise ValueError('Input is not a KiCad PCB')
    issues, pending = [], []
    project_path = board_path.with_suffix('.kicad_pro')
    multi_root_project = False
    if project_path.is_file():
        project = json.loads(project_path.read_text(encoding='utf-8-sig'))
        multi_root_project = len(project.get('schematic', {}).get('top_level_sheets', [])) > 1
    footprints = children(board, 'footprint')
    layers = [row[1] for row in (first(board, 'layers', [])[1:]) if isinstance(row, list) and len(row) > 1 and str(row[1]).endswith('.Cu')]
    vias = children(board, 'via')
    tracks = children(board, 'segment') + children(board, 'arc')
    zones = children(board, 'zone')
    outline = outline_audit(board)
    if not layers:
        issues.append('No enabled copper layers found')
    if not outline['shape_count']:
        issues.append('No Edge.Cuts outline: board is not manufacturable')
    if outline['unmatched_endpoints']:
        issues.append('Open or branching Edge.Cuts endpoints')
    if outline['unsupported_shapes'] or outline['footprint_edges']:
        pending.append('Outline contains shapes requiring KiCad topology verification')

    definitions = {}
    for definition in args.define_var:
        key, value = definition.split('=', 1)
        definitions[key] = value
    missing, dnp, models, invalid_models = [], [], [], []
    net_pads = collections.Counter()
    for fp in footprints:
        props = {v[1]: v[2] for v in children(fp, 'property')}
        ref = props.get('Reference', '?')
        is_dnp = 'dnp' in [str(v) for v in first(fp, 'attr', [])[1:]]
        fp_models = children(fp, 'model')
        if is_dnp:
            dnp.append(dict(reference=ref, value=props.get('Value'), has_model=bool(fp_models)))
        elif not fp_models:
            missing.append(ref)
        for model in fp_models:
            path = resolve_model(model[1], root, definitions)
            hidden = first(model, 'hide') is not None or any(str(x) == 'hide' for x in model[2:] if not isinstance(x, list))
            row = dict(reference=ref, path=str(path), exists=path.is_file(), dnp=is_dnp, hidden=hidden)
            models.append(row)
            if not is_dnp and (not path.is_file() or hidden):
                missing.append(ref)
            if not is_dnp and path.is_file() and path.suffix.lower() not in ('.step', '.stp', '.igs', '.iges'):
                invalid_models.append(ref)
        for pad in children(fp, 'pad'):
            net = first(pad, 'net')
            if net and net[-1] and net[-1] != 0:
                net_pads[str(net[-1])] += 1
    if missing:
        issues.append('Missing or hidden populated-component models: ' + ', '.join(sorted(set(missing))))
    if invalid_models:
        pending.append('Non-STEP/IGES component models require verified substitution: ' + ', '.join(sorted(set(invalid_models))))
    if not tracks and not vias and not zones and any(count > 1 for count in net_pads.values()):
        issues.append('Board has multi-pad nets and no routing or copper zones')

    report = dict(board=str(board_path), board_sha256=digest(board_path),
                  board_thickness_mm=first(first(board, 'general', []), 'thickness', [None, None])[1],
                  footprint_count=len(footprints), enabled_copper_layers=layers,
                  copper_layer_count=len(layers), via_count=len(vias),
                  via_types=dict(collections.Counter(str(v[1]) if len(v) > 1 and not isinstance(v[1], list) else 'through' for v in vias)),
                  track_segment_count=len(tracks), zone_count=len(zones),
                  outline=outline, model_audit=dict(missing_populated=sorted(set(missing)), dnp=dnp, models=models))
    if args.reference_board:
        report['reference_equivalence'] = reference_equivalence(board, args.reference_board.resolve())
        if not report['reference_equivalence']['passed']:
            issues.append('Component or pin-to-net assignment differs from reference PCB; review reference_equivalence')
    connectivity_valid = False
    if args.connectivity_json:
        evidence = json.loads(args.connectivity_json.read_text(encoding='utf-8-sig'))
        report['connectivity'] = dict(path=str(args.connectivity_json), sha256=digest(args.connectivity_json), status=evidence.get('status'))
        stale = evidence.get('board_sha256') != digest(board_path)
        for source in evidence.get('sources', []):
            path = Path(source['path'])
            stale |= not path.is_file() or digest(path) != source['sha256']
        if stale:
            pending.append('Combined schematic connectivity evidence is stale or references a different board')
        elif evidence.get('status') != 'passed':
            issues.append('Combined schematic connectivity parity failed')
        else:
            connectivity_valid = True

    with tempfile.TemporaryDirectory(prefix='pcbgolf-score-') as temp:
        drc_path = args.drc_json
        if args.kicad_cli:
            drc_path = Path(temp) / 'drc.json'
            command = [str(args.kicad_cli.resolve()), 'pcb', 'drc', '--format', 'json',
                       '--output', str(drc_path), '--severity-all', '--severity-exclusions',
                       '--all-track-errors', '--refill-zones']
            if not args.reference_board and not connectivity_valid and not multi_root_project:
                command.append('--schematic-parity')
            command.append(str(board_path))
            run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
            report['drc_command'] = command
            report['drc_process'] = dict(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
            if run.returncode != 0:
                pending.append('KiCad DRC process failed; see drc_process')
        if drc_path and drc_path.is_file():
            try:
                report['drc'] = inspect_drc(json.loads(drc_path.read_text(encoding='utf-8-sig')))
                report['drc']['sha256'] = digest(drc_path)
                dependencies = [board_path] + [p for p in root.glob('*.kicad_*') if p.suffix in ('.kicad_pro', '.kicad_dru', '.kicad_sch')]
                if not args.kicad_cli and drc_path.stat().st_mtime < max(p.stat().st_mtime for p in dependencies):
                    pending.append('DRC JSON is older than the board/project/schematic')
                for field in ('unconnected_count', 'violation_count'):
                    if report['drc'][field]:
                        qualification=' (reported; one or more types may be capped)' if report['drc']['saturated_types'] else ''
                        issues.append(f'DRC {field}: {report["drc"][field]}{qualification}')
                if report['drc']['schematic_parity_count'] and not multi_root_project and not connectivity_valid:
                    issues.append(f'DRC schematic_parity_count: {report["drc"]["schematic_parity_count"]}')
                if multi_root_project:
                    report['drc']['schematic_parity_limitation'] = 'KiCad CLI may load only the primary sheet of a multiple-top-level-sheet project'
                    if not args.reference_board and not connectivity_valid:
                        pending.append('Multi-root schematic parity requires merged sheet validation or --reference-board source connectivity preservation')
            except (ValueError, TypeError) as exc:
                pending.append(f'DRC evidence cannot be interpreted: {exc}')
        else:
            pending.append('Routing/clearance/outline validation missing: run with --kicad-cli or supply current --drc-json')

        step_path = (args.step or board_path.with_suffix('.step')).resolve()
        exported = False
        if args.export_step:
            if not args.kicad_cli:
                raise ValueError('--export-step requires --kicad-cli')
            step_path.parent.mkdir(parents=True, exist_ok=True)
            command = [str(args.kicad_cli.resolve()), 'pcb', 'export', 'step', '--force', '--no-dnp', '--subst-models',
                       '--output', str(step_path), '-D', f'KIPRJMOD={root}']
            for key, value in definitions.items():
                command.extend(['-D', f'{key}={value}'])
            command.append(str(board_path))
            run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
            exported = run.returncode == 0
            report['step_export_command'] = command
            report['step_export_process'] = dict(returncode=run.returncode, stdout=run.stdout, stderr=run.stderr)
            if not exported:
                issues.append('STEP export failed')
            if any(word in (run.stdout + run.stderr).lower() for word in ('could not', 'failed', 'unable', 'error:')):
                pending.append('STEP exporter reported a potential omitted model or geometry problem; inspect export log')
        if step_path.is_file():
            try:
                report['assembly'] = measure_step(step_path)
                report['candidate_score'] = report['assembly']['bounding_box_volume_mm3'] + 50 * len(vias) + 5000 * len(layers)
                if not exported:
                    pending.append('Supplied STEP completeness/provenance unverified; use --export-step for a fresh complete export')
                if report['assembly']['solid_count'] < 1:
                    issues.append('Assembly STEP contains no solids')
            except Exception as exc:
                issues.append(f'Cannot measure assembly STEP: {exc}')
        else:
            pending.append('Final assembly STEP missing; no volume or score can be calculated')
    report.setdefault('candidate_score', None)
    report['score_terms'] = dict(bounding_box_volume_mm3=report.get('assembly', {}).get('bounding_box_volume_mm3'),
                                 via_penalty=50 * len(vias), copper_layer_penalty=5000 * len(layers))
    report['issues'] = issues
    report['incomplete_checks'] = pending
    report['status'] = 'invalid' if issues else ('incomplete' if pending else 'automated_checks_passed')
    report['validated_score'] = report['candidate_score'] if report['status'] == 'automated_checks_passed' else None
    report['submission_ready'] = False
    report['manual_review_required'] = [
        'Functional/electrical equivalence to the source schematic, power/thermal and high-speed signal integrity',
        'Current JLCPCB stackup-specific fabrication capabilities and complete DFM review',
        'Model fidelity, part collision, solder access, tolerances, assembly sequence and connector/card/button access',
        'DNP interfaces retained with the intended electrical and mechanical usability',
        'Challenge organizer acceptance; automated checks are not eligibility approval']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--board', type=Path, default=Path('pcbgolf.kicad_pcb'))
    parser.add_argument('--step', type=Path)
    parser.add_argument('--project-root', type=Path, help='Root for KIPRJMOD (defaults to board directory)')
    parser.add_argument('--drc-json', type=Path, help='Existing KiCad DRC JSON, checked for freshness')
    parser.add_argument('--reference-board', type=Path, help='Verify preserved source PCB components/pad nets; avoids multi-root CLI parity limitation')
    parser.add_argument('--connectivity-json', type=Path, help='Combined multi-sheet parity report from validate_connectivity.py (hash-verified)')
    parser.add_argument('--kicad-cli', type=Path, help='Run fresh all-severity DRC and schematic parity')
    parser.add_argument('--export-step', action='store_true', help='Export complete board + all populated components to --step')
    parser.add_argument('--define-var', action='append', default=[], metavar='KEY=VALUE')
    parser.add_argument('--output', type=Path, help='Write full JSON audit')
    args = parser.parse_args()
    try:
        report = audit(args)
    except Exception as exc:
        print(json.dumps(dict(status='error', error=str(exc)), indent=2))
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    brief = {k: report[k] for k in ('status', 'candidate_score', 'validated_score', 'score_terms', 'copper_layer_count', 'via_count', 'issues', 'incomplete_checks')}
    if report.get('assembly'):
        brief['assembly_size_mm'] = report['assembly']['size_mm']
    print(json.dumps(brief, indent=2))
    return 0 if report['status'] == 'automated_checks_passed' else 2


if __name__ == '__main__':
    sys.exit(main())
