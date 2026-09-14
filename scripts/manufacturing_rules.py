"""Validate draft JLC rules in an isolated board copy; calculate copper screens.

Writes only beneath --output-dir, never changes the input board or project.
Track widths use the documented IPC-2221 expression as a screening estimate,
not a thermal certification. Via values below are electrical resistance only.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess


def trace_width_mm(current_a, copper_um=35.0, rise_c=10.0, external=True):
    k = 0.048 if external else 0.024
    area_mils2 = (current_a / (k * rise_c ** 0.44)) ** (1 / 0.725)
    return area_mils2 / (copper_um / 25.4) * 0.0254


def via_resistance_mohm(finished_hole_mm, plating_um=18.0, board_mm=1.6, copper_temp_c=35.0):
    # Hollow copper cylinder, copper resistivity at 20 C = 1.724e-8 ohm.m.
    # Finished hole is the inner bore; no solder fill or spreading credit.
    d, t = finished_hole_mm / 1000, plating_um / 1e6
    area = math.pi * ((d / 2 + t) ** 2 - (d / 2) ** 2)
    rho = 1.724e-8 * (1 + 0.00393 * (copper_temp_c - 20))
    return rho * (board_mm / 1000) / area * 1000


PROJECT_RULES = {
    'min_clearance': 0.10,
    'min_track_width': 0.10,
    'min_copper_edge_clearance': 0.30,
    'min_hole_clearance': 0.20,
    'min_hole_to_hole': 0.20,
    'min_through_hole_diameter': 0.15,
    'min_via_diameter': 0.25,
    'min_via_annular_width': 0.05,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', type=Path, default=Path('candidates/compact-v2-4l/pcbgolf.kicad_pcb'))
    parser.add_argument('--rules', type=Path, default=Path('reports/jlc4layer.kicad_dru'))
    parser.add_argument('--kicad-cli', type=Path, default=Path('tools/kicad/bin/kicad-cli.exe'))
    parser.add_argument('--output-dir', type=Path, default=Path('reports/manufacturing-rule-validation'))
    args = parser.parse_args()
    board, rules, outdir = args.board.resolve(), args.rules.resolve(), args.output_dir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / 'rulecheck.kicad_pcb'
    if target == board or outdir == board.parent:
        raise ValueError('Output must be an isolated directory, not the input board directory')
    original_hash = hashlib.sha256(board.read_bytes()).hexdigest()
    shutil.copy2(board, target)
    project = json.loads(board.with_suffix('.kicad_pro').read_text(encoding='utf-8-sig'))
    project['board']['design_settings']['rules'].update(PROJECT_RULES)
    target.with_suffix('.kicad_pro').write_text(json.dumps(project, indent=2), encoding='utf-8')
    shutil.copy2(rules, target.with_suffix('.kicad_dru'))
    drc = outdir / 'drc.json'
    command = [str(args.kicad_cli.resolve()), 'pcb', 'drc', '--format', 'json',
               '--severity-all', '--all-track-errors', '--output', str(drc), str(target)]
    run = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (outdir / 'cli.log').write_text(run.stdout + '\n' + run.stderr, encoding='utf-8')
    data = json.loads(drc.read_text(encoding='utf-8-sig')) if drc.is_file() else {}
    counts = collections.Counter(v['type'] for v in data.get('violations', []))
    all_text = (run.stdout + run.stderr).lower()
    parse_errors = [phrase for phrase in ('error loading', 'parse error', 'unrecognized', 'syntax error', 'unknown rule', 'invalid rule') if phrase in all_text]
    named_examples = [v for v in data.get('violations', []) if 'JLC' in v.get('description', '') or 'Project routed' in v.get('description', '')]
    currents = [0.5, 1.0, 2.0, 3.0, 3.18, 3.5, 5.0, 6.36, 7.0, 10.0]
    report = dict(command=command, returncode=run.returncode,
                  native_drc_json_created=bool(data), parse_error_indicators=parse_errors,
                  syntax_validation_passed=run.returncode == 0 and bool(data) and not parse_errors,
                  candidate_is_fabrication_valid=False, violations_by_type=dict(counts),
                  custom_rule_violation_examples=named_examples[:20],
                  input_board_sha256=original_hash,
                  input_board_unchanged=hashlib.sha256(board.read_bytes()).hexdigest() == original_hash,
                  project_rule_recommendations=PROJECT_RULES,
                  copper_assumptions=dict(outer_copper_um=35, inner_copper_um=17.5, temperature_rise_c=10,
                                          track_model='IPC-2221 I=k*dT^0.44*A^0.725, k=0.048 external / 0.024 internal; A in mil^2'),
                  track_width_screens=[dict(current_a=i, outer_width_mm=trace_width_mm(i),
                                            drawn_outer_width_with_20pct_width_loss_mm=trace_width_mm(i)/0.8,
                                            inner_width_mm=trace_width_mm(i,17.5,external=False),
                                            inner_within_10mm_model_range=trace_width_mm(i,17.5,external=False)<=10) for i in currents],
                  via_assumptions=dict(plating_um=18, board_thickness_mm=1.6, copper_temperature_c=35,
                                       model='Hollow copper cylinder resistance only; no ampacity or temperature guarantee'),
                  via_resistance_screens=[dict(finished_hole_mm=d, resistance_mohm=via_resistance_mohm(d)) for d in (0.2,0.3,0.4)])
    (outdir / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('syntax_validation_passed','returncode','parse_error_indicators','input_board_unchanged','violations_by_type')},indent=2))
    return 0 if report['syntax_validation_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
