"""Export every KiCad 10 top-level schematic and compare all pins to the PCB.

Avoids `kicad-cli pcb drc --schematic-parity` loading only the primary sheet.
Checks parts, values, footprint names, DNP state, and exact numbered-pad nets.
This is logical connectivity parity; physical routing still requires KiCad DRC.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import sexpdata as sx


def tag(node):
    return str(node[0]) if isinstance(node, list) and node else None


def children(node, name):
    return [v for v in node if tag(v) == name]


def first(node, name, default=None):
    return next((v for v in node if tag(v) == name), default)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(args):
    project = args.project.resolve()
    root = project.parent
    definitions = json.loads(project.read_text(encoding='utf-8-sig'))
    sheets = definitions.get('schematic', {}).get('top_level_sheets', [])
    if not sheets:
        sheets = [dict(filename=project.with_suffix('.kicad_sch').name)]
    outdir = args.netlist_dir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    components, pins = {}, collections.defaultdict(set)
    sources, export_errors, conflicts = [], [], []
    for sheet in sheets:
        path = root / sheet['filename']
        source_hash = sha(path)
        xml = outdir / (path.stem + '.xml')
        command = [str(args.kicad_cli.resolve()), 'sch', 'export', 'netlist', '--format', 'kicadxml', '--output', str(xml), str(path)]
        run = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace')
        sources.append(dict(path=str(path), sha256=source_hash, xml=str(xml), returncode=run.returncode, stderr=run.stderr))
        if run.returncode != 0 or not xml.is_file():
            export_errors.append(str(path))
            continue
        tree = ET.parse(xml)
        for comp in tree.findall('./components/comp'):
            ref = comp.get('ref')
            props = {p.get('name'): p.get('value', '') for p in comp.findall('property')}
            row = dict(value=comp.findtext('value', ''), footprint=comp.findtext('footprint', ''), dnp='dnp' in props,
                       exclude_from_board='exclude_from_board' in props)
            if ref in components and components[ref] != row:
                conflicts.append(dict(reference=ref, previous=components[ref], current=row))
            components[ref] = row
        for net in tree.findall('./nets/net'):
            name = net.get('name')
            for node in net.findall('node'):
                pins[(node.get('ref'), node.get('pin'))].add(name)
    boardpath = args.board.resolve()
    board = sx.loads(boardpath.read_text(encoding='utf-8'))
    pcbcomponents, pcbpins = {}, collections.defaultdict(set)
    netnames = {str(n[1]): str(n[2]) for n in children(board, 'net') if len(n) > 2}
    for fp in children(board, 'footprint'):
        props = {v[1]: v[2] for v in children(fp, 'property')}
        ref = props.get('Reference', '?')
        pcbcomponents[ref] = dict(value=props.get('Value', ''), footprint=fp[1],
                                  dnp='dnp' in [str(v) for v in first(fp, 'attr', [])[1:]])
        for pad in children(fp, 'pad'):
            if not pad[1]:
                continue
            net = first(pad, 'net')
            name = str(net[-1]) if net else ''
            if net and len(net) == 2:
                name = netnames.get(name, name)
            pcbpins[(ref, str(pad[1]))].add(name)
    expected_components = {ref: c for ref, c in components.items() if not c['exclude_from_board'] and c['footprint']}
    missing = sorted(expected_components.keys() - pcbcomponents.keys())
    extra = sorted(pcbcomponents.keys() - expected_components.keys())
    differences = []
    for ref in sorted(expected_components.keys() & pcbcomponents.keys()):
        for field in ('value', 'footprint', 'dnp'):
            if expected_components[ref][field] != pcbcomponents[ref][field]:
                differences.append(dict(reference=ref, field=field, schematic=expected_components[ref][field], pcb=pcbcomponents[ref][field]))
    def connected_peers(assignments):
        nets = collections.defaultdict(set)
        for key, names in assignments.items():
            for name in names:
                if name:
                    nets[name.replace('{slash}', '/')].add(key)
        peers = collections.defaultdict(set)
        for members in nets.values():
            for member in members:
                peers[member].update(members - {member})
        return peers

    wanted_peers, actual_peers = connected_peers(pins), connected_peers(pcbpins)
    pin_errors, no_net_pads, harmless_renames = [], [], []
    for key in sorted(pins.keys() | pcbpins.keys()):
        if key[0] not in expected_components:
            continue
        expected, actual = pins.get(key, set()), pcbpins.get(key, set())
        # Numbered mechanical pads and a schematic pin intentionally lacking a
        # net both have no electrical assignment. Do not invent a mismatch.
        if not expected and actual == {''}:
            no_net_pads.append('.'.join(key))
            continue
        if key not in pcbpins or key not in pins or wanted_peers[key] != actual_peers[key]:
            pin_errors.append(dict(reference=key[0], pin=key[1], schematic=sorted(expected), pcb=sorted(actual),
                                   missing_connections=['.'.join(p) for p in sorted(wanted_peers[key] - actual_peers[key])],
                                   extra_connections=['.'.join(p) for p in sorted(actual_peers[key] - wanted_peers[key])]))
        elif expected != actual:
            harmless_renames.append(dict(reference=key[0], pin=key[1], schematic=sorted(expected), pcb=sorted(actual)))
    changed_sources = [s['path'] for s in sources if sha(Path(s['path'])) != s['sha256']]
    return dict(status='passed' if not (export_errors or conflicts or missing or extra or differences or pin_errors or changed_sources) else 'failed',
                scope='Combined exported schematics vs PCB logical net assignments; not physical routing or functional proof',
                board=str(boardpath), board_sha256=sha(boardpath), project=str(project), project_sha256=sha(project),
                sources=sources, sources_changed_during_export=changed_sources,
                schematic_components=len(expected_components), board_components=len(pcbcomponents),
                schematic_electrical_pins=len(pins), board_numbered_pads=len(pcbpins), export_errors=export_errors,
                conflicting_schematic_components=conflicts, missing_components=missing, extra_components=extra,
                component_differences=differences, pin_net_differences=pin_errors,
                electrically_equivalent_net_names=harmless_renames, numbered_unassigned_pads=no_net_pads)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', type=Path, default=Path('pcbgolf.kicad_pcb'))
    parser.add_argument('--project', type=Path, default=Path('pcbgolf.kicad_pro'))
    parser.add_argument('--kicad-cli', type=Path, default=Path('tools/kicad/bin/kicad-cli.exe'))
    parser.add_argument('--netlist-dir', type=Path, default=Path('reports/validation-netlists'))
    parser.add_argument('--output', type=Path, default=Path('reports/connectivity-parity.json'))
    args = parser.parse_args()
    report = validate(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    brief = {k: report[k] for k in ('status', 'board', 'schematic_components', 'board_components', 'export_errors', 'missing_components', 'extra_components', 'sources_changed_during_export')}
    for key in ('component_differences', 'pin_net_differences', 'electrically_equivalent_net_names'):
        brief[key + '_count'] = len(report[key])
    brief['component_differences'] = report['component_differences'][:12]
    brief['pin_net_difference_sample'] = report['pin_net_differences'][:3]
    print(json.dumps(brief, indent=2))
    return 0 if report['status'] == 'passed' else 2


if __name__ == '__main__':
    sys.exit(main())
