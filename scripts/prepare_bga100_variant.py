"""Build an isolated STM32H725VGH6 project, preserving the original signal nets.

Run with tools/venv/Scripts/python.exe. The native board synchronization is
dispatched to bundled KiCad Python; the source project is never saved.
"""
import argparse
import collections
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'candidates/bga100-base'
NAME = 'STM32H725VGH6_TFBGA100'
MPN = 'STM32H725VGH6'
FP = 'TFBGA-100_8x8mm_Layout10x10_P0.8mm'
ASSETS = ROOT / 'reports/bga100-assets'
DATASHEET = 'https://www.st.com/resource/en/datasheet/stm32h725ag.pdf'
DESCRIPTION = 'STM32H725VGH6, TFBGA100 8x8 mm, ten GPIO remaps; firmware changes required'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_board():
    import pcbnew as pcb
    statuspath = OUT / 'bga100-status.json'
    status = json.loads(statuspath.read_text())
    board = pcb.LoadBoard(str(OUT / 'pcbgolf.kicad_pcb'))
    old = next(fp for fp in board.GetFootprints() if fp.GetReference() == 'U3')
    position, angle, flipped = old.GetPosition(), old.GetOrientationDegrees(), old.IsFlipped()
    nets_before = {p.GetNetname() for f in board.GetFootprints() for p in f.Pads()
                   if p.GetNetname() and not p.GetNetname().startswith('unconnected-')}
    for row in status['original_pin_rows']:
        oldpad = next(p for p in old.Pads() if p.GetNumber() == row['original_pin'])
        if row['connected']:
            assert oldpad.GetNetname() == row['net'], (row, oldpad.GetNetname())
    new = pcb.PCB_IO_KICAD_SEXPR().FootprintLoad(str(OUT / 'pcbgolf.pretty'), NAME, False)
    new.SetReference('U3')
    new.SetValue(MPN)
    new.SetFPIDAsString('pcbgolf:' + NAME)
    new.SetPath(old.GetPath())
    new.SetUuid(old.m_Uuid)
    new.SetAttributes(old.GetAttributes())
    board.Remove(old)
    board.Add(new)
    new.SetPosition(position)
    if flipped:
        new.Flip(position, pcb.FLIP_DIRECTION_TOP_BOTTOM)
    new.SetOrientationDegrees(angle)
    assignments = {r['ball']: r for r in status['ball_assignments']}
    assert len(assignments) == len(list(new.Pads())) == 100
    for pad in new.Pads():
        row = assignments[pad.GetNumber()]
        if row['connected']:
            net = board.FindNet(row['net'])
            if not net:
                raise ValueError('Missing source circuit net ' + row['net'])
        else:
            netname = f'unconnected-(U3-{row["function"]}-Pad{row["ball"]})'
            net = pcb.NETINFO_ITEM(board, netname)
            board.Add(net)
        pad.SetNet(net)
    new.Reference().SetVisible(False)
    new.Value().SetVisible(False)
    board.GetDesignSettings().SetBoardThickness(pcb.FromMM(1.6))
    board.BuildConnectivity()
    for zone in board.Zones():
        zone.UnFill()
    nets_after = {p.GetNetname() for f in board.GetFootprints() for p in f.Pads()
                  if p.GetNetname() and not p.GetNetname().startswith('unconnected-')}
    assert nets_before == nets_after, (nets_before - nets_after, nets_after - nets_before)
    assert len(board.GetFootprints()) == 239
    pcb.SaveBoard(str(OUT / 'pcbgolf.kicad_pcb'), board)
    status.update(status='Isolated schematic and 100-ball PCB synchronized; parity/DRC pending',
                  board_sha256=sha(OUT / 'pcbgolf.kicad_pcb'),
                  source_signal_net_count=len(nets_before), all_original_signal_net_names_preserved=True,
                  u3_placement=dict(x_mm=pcb.ToMM(position.x), y_mm=pcb.ToMM(position.y),
                                    angle_degrees=angle, bottom=flipped),
                  tracks=len(board.GetTracks()), zones=len(board.Zones()))
    statuspath.write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps({k: status[k] for k in ('status', 'u3_placement', 'source_signal_net_count')}))


def prepare():
    import sexpdata as sx
    from inventory import children, first, props
    from circuit_corrections import blocks
    from score_assembly import measure_step

    files = ['pcbgolf.kicad_pcb', 'pcbgolf.kicad_pro', 'pcbgolf.kicad_dru',
             'pcbgolf.kicad_sch', 'pcbgolf_2.kicad_sch', 'pcbgolf_3.kicad_sch',
             'pcbgolf_4.kicad_sch', 'pcbgolf_5.kicad_sch', 'pcbgolf.kicad_sym',
             'fp-lib-table', 'sym-lib-table']
    source_hashes = {name: sha(ROOT / name) for name in files}
    OUT.mkdir(parents=True, exist_ok=True)
    for name in files:
        shutil.copy2(ROOT / name, OUT / name)
    for name in ['pcbgolf.pretty', 'pcbgolf.3dshapes']:
        shutil.copytree(ROOT / name, OUT / name, dirs_exist_ok=True)

    feasibility = json.loads((ROOT / 'reports/mcu-bga100-feasibility.json').read_text())
    original = json.loads((ROOT / 'reports/mcu-bga-remap.json').read_text())['pin_remap']
    targets = feasibility['ball_assignments']
    assert len(targets) == 100 and sum(r['connected'] for r in targets) == 82
    by_ball = {r['ball']: r for r in targets}
    official_xml = ET.parse(ROOT / 'reports/stm32-pin-data/STM32H725VGHx.xml')
    official_pins = {p.get('Position'): p.get('Name').split('(')[0].split('-')[0]
                     for p in official_xml.getroot() if p.tag.split('}')[-1] == 'Pin'}
    assert len(official_pins) == 100
    for ball, row in by_ball.items():
        assert official_pins[ball] == row['function'], (ball, official_pins[ball], row)
    moves = {r['original_function']: r['target_function'] for r in feasibility['firmware_pin_changes']}
    remaining = dict(by_ball)
    mapping, removed = {}, []
    # Connected signals must claim remapped GPIO balls before the old NC GPIOs.
    for row in sorted(original, key=lambda r: not r['connected']):
        function = row['function'].split('(')[0]
        desired = moves.get(function, function) if row['connected'] else function
        candidates = [r for r in remaining.values()
                      if r['function'] == desired and r['connected'] == row['connected']
                      and (not row['connected'] or r['net'] == row['net'])]
        if candidates:
            target = candidates[0]
            mapping[row['original_pin']] = target['ball']
            del remaining[target['ball']]
        else:
            mapping[row['original_pin']] = None
            removed.append(row)
            if row['connected']:
                assert function in ('VSS', 'VDD', 'VCAP', 'VDDLDO', 'VDD50USB'), row
                assert any(t['net'] == row['net'] and t['connected'] for t in targets), row
    assert not remaining, 'Unmapped target balls: ' + repr(remaining)
    assert len({v for v in mapping.values() if v is not None}) == 100

    path = OUT / 'pcbgolf_2.kicad_sch'
    text = path.read_text()
    tree = sx.loads(text)
    oldinstance = next(s for s in children(tree, 'symbol') if props(s).get('Reference') == 'U3')
    oldid = first(oldinstance, 'lib_id')[1]
    oldsymbol = next(s for s in children(first(tree, 'lib_symbols'), 'symbol') if s[1] == oldid)
    newsymbol = copy.deepcopy(oldsymbol)
    newsymbol[1] = 'pcbgolf:' + NAME

    def properties(node):
        values = {'Value': MPN, 'MPN': MPN, 'Footprint': 'pcbgolf:' + NAME,
                  'Datasheet': DATASHEET, 'Description': DESCRIPTION}
        for prop in children(node, 'property'):
            if prop[1] in values:
                prop[2] = values[prop[1]]

    properties(newsymbol)
    removed_positions, retained_positions = set(), set()
    instance_x, instance_y, instance_angle = first(oldinstance, 'at')[1:]
    assert instance_angle == 0, 'Schematic transformation currently handles zero-rotation U3 only'
    for unit in children(newsymbol, 'symbol'):
        unit[1] = NAME + '_' + unit[1].rsplit('_', 2)[1] + '_' + unit[1].rsplit('_', 1)[1]
        for pin in list(children(unit, 'pin')):
            oldnumber = first(pin, 'number')[1]
            x, y = first(pin, 'at')[1:3]
            world = (round(instance_x + x, 5), round(instance_y - y, 5))
            target_ball = mapping[oldnumber]
            if target_ball is None:
                unit.remove(pin)
                removed_positions.add(world)
            else:
                first(pin, 'number')[1] = target_ball
                # GPIO identity changes, not merely package pad numbering.
                first(pin, 'name')[1] = by_ball[target_ball]['function']
                retained_positions.add(world)
    newinstance = copy.deepcopy(oldinstance)
    first(newinstance, 'lib_id')[1] = 'pcbgolf:' + NAME
    properties(newinstance)
    for pin in list(children(newinstance, 'pin')):
        number = mapping[pin[1]]
        if number is None:
            newinstance.remove(pin)
        else:
            pin[1] = number

    edits = []
    for a, b, block in blocks(text):
        if block.startswith('(lib_symbols'):
            for c, d, symbol in reversed(list(blocks(block))):
                if symbol.startswith('(symbol "' + oldid + '"'):
                    block = block[:c] + sx.dumps(newsymbol) + block[d:]
            edits.append((a, b, block))
        elif block.startswith('(symbol\n') and '(property "Reference" "U3"' in block:
            edits.append((a, b, sx.dumps(newinstance)))
        elif block.startswith('(no_connect'):
            at = first(sx.loads(block), 'at')[1:3]
            if tuple(round(float(v), 5) for v in at) in removed_positions - retained_positions:
                edits.append((a, b, ''))
    assert len([e for e in edits if e[2].startswith('(symbol ')]) == 1
    for a, b, block in reversed(edits):
        text = text[:a] + block + text[b:]
    sx.loads(text)
    path.write_text(text)
    standalone = copy.deepcopy(newsymbol)
    standalone[1] = NAME
    libpath = OUT / 'pcbgolf.kicad_sym'
    libtext = libpath.read_text()
    libtext = libtext[:libtext.rfind(')')] + sx.dumps(standalone) + '\n)\n'
    sx.loads(libtext)
    libpath.write_text(libtext)

    footprint = (ASSETS / (FP + '.kicad_mod')).read_text()
    footprint = footprint.replace('(footprint "' + FP + '"', '(footprint "' + NAME + '"', 1)
    footprint, replacements = re.subn(r'\$\{KICAD\d+_3DMODEL_DIR\}/Package_BGA\.3dshapes/'
                                      + re.escape(FP) + r'\.(wrl|step)',
                                      '${KIPRJMOD}/pcbgolf.3dshapes/Package_BGA.3dshapes/' + FP + '.step', footprint)
    assert replacements == 1
    fp_tree = sx.loads(footprint)
    assert {p[1] for p in children(fp_tree, 'pad')} == set(by_ball)
    assert all(first(p, 'size')[1:] == [0.4, 0.4] for p in children(fp_tree, 'pad'))
    (OUT / 'pcbgolf.pretty' / (NAME + '.kicad_mod')).write_text(footprint)
    modelpath = OUT / 'pcbgolf.3dshapes/Package_BGA.3dshapes' / (FP + '.step')
    modelpath.parent.mkdir(exist_ok=True)
    shutil.copy2(ASSETS / (FP + '.step'), modelpath)

    status = dict(status='Schematic package remap prepared; board synchronization pending',
                  target_mpn=MPN, footprint='pcbgolf:' + NAME, part_count_expected=239,
                  board_thickness_mm=1.6, source_hashes=source_hashes,
                  source_root_unmodified=True, old_to_new_symbol_pin_mapping=mapping,
                  original_pin_rows=original, removed_source_pin_rows=removed,
                  ball_assignments=targets, counts=feasibility['counts'],
                  firmware_pin_changes=feasibility['firmware_pin_changes'],
                  remaining_validation=feasibility['remaining_validation'],
                  model=measure_step(modelpath),
                  model_note='Official KiCad model kept unchanged; nominal 8x8 mm body, 1.112 mm overall model height. Use ST 1.20 mm maximum package height for clearance review.',
                  sources=feasibility['sources'] + [DATASHEET,
                    'https://gitlab.com/kicad/libraries/kicad-footprints/-/raw/master/Package_BGA.pretty/' + FP + '.kicad_mod',
                    'https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master/Package_BGA.3dshapes/' + FP + '.step'],
                  assets_sha256={p.name: sha(p) for p in ASSETS.iterdir() if p.is_file()},
                  routing_started=False, submission_ready=False)
    (OUT / 'bga100-status.json').write_text(json.dumps(status, indent=2) + '\n')
    shutil.copy2(ROOT / 'reports/mcu-bga100-feasibility.json', OUT / 'mcu-bga100-feasibility.json')
    subprocess.run([str(ROOT / 'tools/kicad/bin/python.exe'), str(Path(__file__).resolve()), '--sync-board'],
                   cwd=ROOT, check=True)
    assert {name: sha(ROOT / name) for name in files} == source_hashes, 'Source changed during preparation'
    print('Source project hashes unchanged. Running merged five-sheet parity and native DRC.')
    validate()


def validate():
    """Validate the prepared copy without rebuilding or changing its PCB."""
    import sexpdata as sx
    from inventory import children, first
    statuspath = OUT / 'bga100-status.json'
    status = json.loads(statuspath.read_text())
    schematic = sx.loads((OUT / 'pcbgolf_2.kicad_sch').read_text())
    symbol = next(s for s in children(first(schematic, 'lib_symbols'), 'symbol')
                  if s[1] == 'pcbgolf:' + NAME)
    actual_functions = {first(p, 'number')[1]: first(p, 'name')[1]
                        for unit in children(symbol, 'symbol') for p in children(unit, 'pin')}
    wanted_functions = {r['ball']: r['function'] for r in status['ball_assignments']}
    xml = ET.parse(ROOT / 'reports/stm32-pin-data/STM32H725VGHx.xml')
    official_functions = {p.get('Position'): p.get('Name').split('(')[0].split('-')[0]
                          for p in xml.getroot() if p.tag.split('}')[-1] == 'Pin'}
    assert len(actual_functions) == 100 and actual_functions == wanted_functions == official_functions
    parity_path = ROOT / 'reports/bga100-connectivity.json'
    drc_path = ROOT / 'reports/bga100-native-drc.json'
    subprocess.run([str(ROOT / 'tools/venv/Scripts/python.exe'), str(ROOT / 'scripts/validate_connectivity.py'),
                    '--board', str(OUT / 'pcbgolf.kicad_pcb'), '--project', str(OUT / 'pcbgolf.kicad_pro'),
                    '--netlist-dir', str(ROOT / 'reports/bga100-netlists'), '--output', str(parity_path)],
                   cwd=ROOT, check=True)
    board_hash = sha(OUT / 'pcbgolf.kicad_pcb')
    subprocess.run([str(ROOT / 'tools/kicad/bin/kicad-cli.exe'), 'pcb', 'drc', '--format', 'json',
                    '--severity-all', '--all-track-errors', '--refill-zones', '--output', str(drc_path),
                    str(OUT / 'pcbgolf.kicad_pcb')], cwd=ROOT, check=True)
    assert board_hash == sha(OUT / 'pcbgolf.kicad_pcb')
    parity = json.loads(parity_path.read_text())
    drc = json.loads(drc_path.read_text())
    from score_assembly import inspect_drc
    drc_summary = inspect_drc(drc)
    errors = [r for r in drc['violations'] if r['severity'] == 'error']
    status.update(status='Isolated BGA100 package variant: merged parity passed; routing/firmware unfinished',
                  board_sha256=board_hash, logical_parity=dict(path=str(parity_path), sha256=sha(parity_path),
                  status=parity['status'], component_differences=len(parity['component_differences']),
                  pin_net_differences=len(parity['pin_net_differences'])),
                  native_drc=dict(path=str(drc_path), sha256=sha(drc_path),
                  nonrouting_error_count=len(errors), warning_counts=dict(collections.Counter(
                  r['type'] for r in drc['violations'] if r['severity'] == 'warning')),
                  summary=drc_summary), submission_ready=False)
    status['symbol_pin_function_audit'] = dict(status='passed', pins_checked=100,
        source=str(ROOT / 'reports/stm32-pin-data/STM32H725VGHx.xml'),
        source_sha256=sha(ROOT / 'reports/stm32-pin-data/STM32H725VGHx.xml'),
        note='All pin numbers and normalized GPIO/supply names match official ST XML; GPIO names change with the ten remaps.')
    statuspath.write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps(dict(parity=parity['status'], nonrouting_errors=len(errors),
                         warnings=len(drc['violations']) - len(errors),
                         unconnected_records=len(drc['unconnected_items']))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sync-board', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--validate-only', action='store_true', help='Validate existing isolated variant without rebuilding it')
    args = parser.parse_args()
    sync_board() if args.sync_board else validate() if args.validate_only else prepare()
