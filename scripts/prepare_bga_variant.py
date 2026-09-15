"""Create isolated BGA schematics/libraries and package geometry from corrected root."""
import collections
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid
import sexpdata as sx
from inventory import children, first, props
from circuit_corrections import blocks, setprop

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'candidates/bga-base'
NAME = 'STM32H725AGI6_UFBGA169'
MPN = 'STM32H725AGI6'
FOOTPRINT = 'UFBGA-169_7x7mm_Layout13x13_P0.5mm'
OUT.mkdir(parents=True, exist_ok=True)
for name in ['pcbgolf.kicad_pcb', 'pcbgolf.kicad_pro', 'pcbgolf.kicad_dru',
             'pcbgolf.kicad_sch', 'pcbgolf_2.kicad_sch', 'pcbgolf_3.kicad_sch',
             'pcbgolf_4.kicad_sch', 'pcbgolf_5.kicad_sch', 'pcbgolf.kicad_sym',
             'fp-lib-table', 'sym-lib-table']:
    shutil.copy2(ROOT / name, OUT / name)
for name in ['pcbgolf.pretty', 'pcbgolf.3dshapes']:
    shutil.copytree(ROOT / name, OUT / name, dirs_exist_ok=True)

mapping = json.loads((ROOT / 'reports/mcu-bga-remap.json').read_text())
queues = collections.defaultdict(list)
for row in mapping['ball_assignments']:
    queues[row['function']].append(row['ball'])
old_to_new = {}
for row in mapping['pin_remap']:
    targets = queues[row['function']]
    old_to_new[row['original_pin']] = targets.pop(0) if targets else None
extras = [r for r in mapping['ball_assignments'] if not r['original_pins']]
assert len(extras) == 26
assert [k for k, v in old_to_new.items() if v is None] == ['141']
path = OUT / 'pcbgolf_2.kicad_sch'
text = path.read_text()
tree = sx.loads(text)
oldinstance = next(s for s in children(tree, 'symbol') if props(s).get('Reference') == 'U3')
oldid = first(oldinstance, 'lib_id')[1]
oldsym = next(s for s in children(first(tree, 'lib_symbols'), 'symbol') if s[1] == oldid)
newsym = copy.deepcopy(oldsym)
newsym[1] = 'pcbgolf:' + NAME
for prop in children(newsym, 'property'):
    if prop[1] == 'Value': prop[2] = MPN
    elif prop[1] == 'Footprint': prop[2] = 'pcbgolf:' + NAME
    elif prop[1] == 'Datasheet': prop[2] = 'https://www.st.com/resource/en/datasheet/stm32h725ag.pdf'
    elif prop[1] == 'Description': prop[2] = 'STM32H725AGI6 7x7 mm UFBGA169; original signals in unit A, additional unused package pins in unit B'
oldgraphic = next(u for u in children(newsym, 'symbol') if u[1].endswith('_0_1'))
mainunit = next(u for u in children(newsym, 'symbol') if u[1].endswith('_1_1'))
mainunit[1] = NAME + '_1_1'
mainunit.extend(copy.deepcopy(oldgraphic[2:]))
newsym.remove(oldgraphic)
for pin in list(children(mainunit, 'pin')):
    number = first(pin, 'number')[1]
    if old_to_new[number] is None: mainunit.remove(pin)
    else: first(pin, 'number')[1] = old_to_new[number]

official = sx.loads((ROOT / 'reports/STM32H725AGIx.kicad_sym').read_text())
officialsym = children(official, 'symbol')[0]
officialpins = {first(p, 'number')[1]: p for u in children(officialsym, 'symbol') for p in children(u, 'pin')}
extraunit = sx.loads(f'(symbol "{NAME}_2_1" (rectangle (start -15 35.56) (end 15 -35.56) (stroke (width 0.254) (type default)) (fill (type background))))')
extra_positions = {}
for index, row in enumerate(extras):
    pin = copy.deepcopy(officialpins[row['ball']])
    y = round(31.75 - index * 2.54, 5)
    first(pin, 'at')[1:] = [-20.32, y, 0]
    first(pin, 'length')[1] = 5.32
    extraunit.append(pin)
    extra_positions[row['ball']] = (-20.32, y)
newsym.append(extraunit)

maininstance = copy.deepcopy(oldinstance)
first(maininstance, 'lib_id')[1] = 'pcbgolf:' + NAME
for prop in children(maininstance, 'property'):
    if prop[1] == 'Value': prop[2] = MPN
    elif prop[1] == 'MPN': prop[2] = MPN
    elif prop[1] == 'Footprint': prop[2] = 'pcbgolf:' + NAME
    elif prop[1] == 'Datasheet': prop[2] = 'https://www.st.com/resource/en/datasheet/stm32h725ag.pdf'
    elif prop[1] == 'Description': prop[2] = 'STM32H725AGI6 7x7 mm UFBGA169'
for pin in list(children(maininstance, 'pin')):
    if old_to_new[pin[1]] is None: maininstance.remove(pin)
    else: pin[1] = old_to_new[pin[1]]

otherinstance = copy.deepcopy(maininstance)
first(otherinstance, 'at')[1:] = [250, 100, 0]
first(otherinstance, 'unit')[1] = 2
first(otherinstance, 'uuid')[1] = str(uuid.uuid4())
for pin in list(children(otherinstance, 'pin')): otherinstance.remove(pin)
for number in extra_positions:
    otherinstance.append(sx.loads(f'(pin "{number}" (uuid "{uuid.uuid4()}"))'))
for project in children(first(otherinstance, 'instances'), 'project'):
    for instancepath in children(project, 'path'):
        first(instancepath, 'unit')[1] = 2
for prop in children(otherinstance, 'property'):
    first(prop, 'at')[1:] = [250, 61.9 if prop[1] == 'Reference' else 64.44, 0]

edits = []
for a, b, block in blocks(text):
    if block.startswith('(lib_symbols'):
        for c, d, symbol in reversed(list(blocks(block))):
            if symbol.startswith('(symbol "' + oldid + '"'):
                block = block[:c] + sx.dumps(newsym) + block[d:]
        edits.append((a, b, block))
    elif block.startswith('(symbol\n') and '(property "Reference" "U3"' in block:
        edits.append((a, b, sx.dumps(maininstance)))
for a, b, block in reversed(edits): text = text[:a] + block + text[b:]
additional = '\n' + sx.dumps(otherinstance) + '\n'
for x, y in extra_positions.values():
    additional += f'(no_connect (at {250+x:.5f} {100-y:.5f}) (uuid "{uuid.uuid4()}"))\n'
text = text[:text.rfind(')')] + additional + ')\n'
sx.loads(text)
path.write_text(text)
standalone = copy.deepcopy(newsym)
standalone[1] = NAME
libpath = OUT / 'pcbgolf.kicad_sym'
libtext = libpath.read_text()
libtext = libtext[:libtext.rfind(')')] + sx.dumps(standalone) + '\n)\n'
sx.loads(libtext)
libpath.write_text(libtext)

# The downloaded official footprint follows ST Table 135's 0.27 mm pads.
fp = (ROOT / 'reports' / (FOOTPRINT + '.kicad_mod')).read_text()
fp = fp.replace('(footprint "' + FOOTPRINT + '"', '(footprint "' + NAME + '"', 1)
fp = fp.replace('${KICAD9_3DMODEL_DIR}/Package_BGA.3dshapes/' + FOOTPRINT + '.step', '${KIPRJMOD}/pcbgolf.3dshapes/Package_BGA.3dshapes/' + NAME + '.step')
fp = fp.replace('(attr smd)', '(attr smd)\n\t(solder_mask_margin 0.04)')
(OUT / 'pcbgolf.pretty' / (NAME + '.kicad_mod')).write_text(fp)

# Parametric nominal package, dimensions from ST DS13311 Rev 5 Table 134.
# Body 7 x 7, z 0.08..0.53. Nominal 0.28 mm balls start at z=0;
# embedded ball portions overlap the package body within this mechanical model.
from OCP.BRep import BRep_Builder
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeSphere
from OCP.TopoDS import TopoDS_Compound
from OCP.gp import gp_Pnt
from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone
builder = BRep_Builder()
compound = TopoDS_Compound()
builder.MakeCompound(compound)
builder.Add(compound, BRepPrimAPI_MakeBox(gp_Pnt(-3.5, -3.5, .08), 7, 7, .45).Shape())
for row in mapping['ball_assignments']:
    x, y = row['at_mm']
    builder.Add(compound, BRepPrimAPI_MakeSphere(gp_Pnt(x, -y, .14), .14).Shape())
modelpath = OUT / 'pcbgolf.3dshapes/Package_BGA.3dshapes' / (NAME + '.step')
modelpath.parent.mkdir(exist_ok=True)
writer = STEPControl_Writer()
writer.Transfer(compound, STEPControl_AsIs)
assert writer.Write(str(modelpath)) == IFSelect_RetDone

status = {'status': 'schematic and libraries prepared; board sync and parity pending',
          'source_board_sha256': hashlib.sha256((ROOT / 'pcbgolf.kicad_pcb').read_bytes()).hexdigest(),
          'source_root_u3_changed': False, 'part_count_expected': 239,
          'board_thickness_mm': 1.6, 'mpn': MPN, 'footprint': 'pcbgolf:' + NAME,
          'old_to_new_symbol_pin_mapping': old_to_new,
          'package_only_nc_balls': [r['ball'] for r in extras],
          'model': {'type': 'parametric nominal manufacturer-dimension package model',
                    'provenance': 'https://www.st.com/resource/en/datasheet/stm32h725ag.pdf Table 134',
                    'nominal_bounds_mm': [-3.5, -3.5, 0, 3.5, 3.5, .53],
                    'maximum_component_dimensions_mm': [7.05, 7.05, .60],
                    'note': 'Nominal mechanical representation with embedded spherical balls, not a manufacturer detailed CAD model. Use maximum dimensions for clearance review.'},
          'routing_started': False,
          'fabrication_escape_status': 'Awaiting exact JLC capability review; no finer rule or via-in-pad process assumed.'}
(OUT / 'bga-status.json').write_text(json.dumps(status, indent=2))
shutil.copy2(ROOT / 'reports/mcu-bga-remap.json', OUT / 'mcu-bga-remap.json')
print(json.dumps({k: status[k] for k in ('status','part_count_expected','board_thickness_mm','mpn')}))
