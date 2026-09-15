"""Build a separate, reviewable MCU package remap; never edit main U3."""
import collections
import hashlib
import json
from pathlib import Path
import sexpdata as sx
from inventory import children, first, props
from circuit_corrections import blocks

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports'
source = sx.loads((ROOT / 'pcbgolf_2.kicad_sch').read_text())
instance = next(s for s in children(source, 'symbol') if props(s).get('Reference') == 'U3')
old = next(s for s in children(first(source, 'lib_symbols'), 'symbol') if s[1] == first(instance, 'lib_id')[1])
library_path = REPORTS / 'MCU_ST_STM32H7.kicad_sym'
library_text = library_path.read_text()
library = sx.loads(library_text)
new = next(s for s in children(library, 'symbol') if s[1] == 'STM32H725AGIx')

def pins(symbol):
    return {first(p, 'number')[1]: first(p, 'name')[1]
            for unit in children(symbol, 'symbol') for p in children(unit, 'pin')}

old_pins, new_pins = pins(old), pins(new)
assert len(old_pins) == 144 and len(new_pins) == 169
footprint_name = 'UFBGA-169_7x7mm_Layout13x13_P0.5mm'
footprint = sx.loads((REPORTS / (footprint_name + '.kicad_mod')).read_text())
pad_geometry = {p[1]: {'at_mm': first(p, 'at')[1:3], 'size_mm': first(p, 'size')[1:3]}
                for p in children(footprint, 'pad')}
assert set(new_pins) == set(pad_geometry)
inv = json.loads((REPORTS / 'source-inventory.json').read_text())
old_nets = {ep.split('.')[1]: net for net, endpoints in inv['nets'].items()
            for ep in endpoints if ep.startswith('U3.')}
by_function = collections.defaultdict(list)
for ball, function in new_pins.items():
    by_function[function].append(ball)

rows = []
for pin in sorted(old_pins, key=int):
    function = old_pins[pin]
    assert function in by_function, (pin, function)
    net = old_nets.get(pin)
    connected = bool(net and not net.startswith('unconnected'))
    rows.append({'original_pin': pin, 'function': function, 'net': net,
                 'connected': connected, 'target_balls': by_function[function],
                 'mapping_type': 'all_same_function_supply_balls' if len(by_function[function]) > 1 else 'one_to_one'})

ball_assignments = []
for ball, function in new_pins.items():
    source_pins = [p for p, f in old_pins.items() if f == function]
    source_nets = {old_nets[p] for p in source_pins if old_nets.get(p) and not old_nets[p].startswith('unconnected')}
    assert len(source_nets) <= 1, (ball, function, source_nets)
    net = next(iter(source_nets), None)
    ball_assignments.append({'ball': ball, 'function': function, 'net': net,
                             'original_pins': source_pins,
                             'disposition': 'connect' if net else 'no_connect',
                             **pad_geometry[ball]})

# Spot checks against ST DS13311 Rev 5 Table 8 and package Figure 10.
datasheet_checks = {'122': 'C8', '123': 'A8', '100': 'F13', '101': 'E13',
                    '15': 'E1', '14': 'E2', '16': 'F1', '17': 'F2',
                    '25': 'H1', '26': 'H2', '27': 'G6', '30': 'K2',
                    '31': 'K1', '34': 'J3', '35': 'L2', '36': 'L1',
                    '110': 'B11', '111': 'A11', '142': 'C4'}
for pin, ball in datasheet_checks.items():
    assert new_pins[ball] == old_pins[pin]

package = {'mpn': 'STM32H725AGI6', 'symbol': 'MCU_ST_STM32H7:STM32H725AGIx',
           'body_nominal_mm': [7, 7, .53], 'body_maximum_mm': [7.05, 7.05, .6],
           'pitch_mm': .5, 'array': '13 x 13, rows A B C D E F G H J K L M N',
           'pad_diameter_mm': .27, 'recommended_mask_opening_mm': .35,
           'footprint_file': 'reports/' + footprint_name + '.kicad_mod',
           'step_file': 'reports/' + footprint_name + '.step',
           'step_status': 'Official legacy KiCad model measures 7 x 7 x 0.75625 mm, z -0.00625 to +0.75. Its height exceeds the current ST package drawing; do not claim it is exact. Safe conservative placement envelope only until accurate model replaces it.'}

result = {
    'schema': 1, 'date': '2026-09-14', 'status': 'separate package branch; main U3 unchanged',
    'source': {'ref': 'U3', **props(instance)}, 'target': package,
    'counts': {'original_pins': len(rows), 'connected_original_pins': sum(r['connected'] for r in rows),
               'target_balls': len(ball_assignments), 'connected_target_balls': sum(bool(r['net']) for r in ball_assignments)},
    'mapping_policy': 'Preserve GPIO identity and every net. Repeated supply functions map as a group: connect every target ball to its function net; do not interpret a repeated source row as an independent ball allocation. NC pins and newly available GPIO balls remain NC.',
    'pin_remap': rows, 'ball_assignments': ball_assignments,
    'datasheet_spot_checks': datasheet_checks,
    'critical_notes': [
        'The exact mapping comes from the official KiCad 9.0.4 STM32H725AGIx symbol, with selected critical pins corroborated against ST Table 8 / Figure 10. All 169 symbol balls match the official footprint pads.',
        'All original functions exist. Added PA0_C/PA1_C and PC2/PC3 pins are separate analog/digital terminals; leave them NC and preserve original PC2_C/PC3_C on K2/K1.',
        'VCAP A4/D13/N10, VDDLDO B4/D12/M10, and VFBSMPS F2 all retain source VDDLDO net. Do not join that net to +3V3.',
        'VDD33USB G13 and VDD50USB G12 both retain source +3V3. VSSSMPS E2 and VSSA J3 retain GND; VDDA L1 and VREF+ L2 retain source VDDA.',
        'Existing decoupling must be redistributed to new power balls. Preserve required direct-SMPS firmware supply configuration and L3 switch loop.',
        'PG9 C8 / PG10 A8 preserve CAN2 TX/RX. The MCU still has three FDCAN controllers, not four independent controllers.',
        'At 0.50 mm pitch with 0.27 mm pads, a straight track between adjacent pads at 0.10 mm copper clearance can be only 0.03 mm wide. Escape strategy needs diagonal fanout, access through NC cells, and/or finer selected fabricator rules. Do not assume the footprint area saving automatically yields a routable smaller board.',
        'No main-board or main-schematic MCU replacement has been performed.'
    ],
    'sources': [
        {'url': 'https://www.st.com/resource/en/datasheet/stm32h725ag.pdf', 'details': 'DS13311 Rev 5: Figure 10 top-view ballout; Table 8 functions; Tables 134 and 135 dimensions and 0.27 mm NSMD pads.'},
        {'url': 'https://www.st.com/en/microcontrollers-microprocessors/stm32h725ag.html', 'details': 'Manufacturer lists STM32H725AGI6 active.'},
        {'url': 'https://gitlab.com/kicad/libraries/kicad-symbols/-/raw/9.0.4/MCU_ST_STM32H7.kicad_sym', 'sha256': hashlib.sha256(library_path.read_bytes()).hexdigest()},
        {'url': 'https://gitlab.com/kicad/libraries/kicad-footprints/-/raw/9.0.4/Package_BGA.pretty/' + footprint_name + '.kicad_mod'},
        {'url': 'https://raw.githubusercontent.com/KiCad/kicad-packages3D/master/Package_BGA.3dshapes/' + footprint_name + '.step', 'warning': 'Legacy generic STEP height differs from current manufacturer drawing.'}
    ]
}
(REPORTS / 'mcu-bga-remap.json').write_text(json.dumps(result, indent=2))
# Keep a focused reviewable symbol, avoiding loading the 15 MB full library into an implementation branch.
symbol_block = next(s for _, _, s in blocks(library_text) if s.startswith('(symbol "STM32H725AGIx"'))
(REPORTS / 'STM32H725AGIx.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n' + symbol_block + '\n)\n')
print(json.dumps(result['counts']))
