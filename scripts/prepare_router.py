"""Export fresh DSN, deduplicating only contained same-net SMD lands.

The native PCB is never saved. Partly overlapping pads remain pads: FreeRouting
imports wire polygons as non-obstacle conduction areas, even with type=fix, so
such polygons cannot safely stand in for physical SMD copper. Native DRC remains
authoritative and all physical copper/hole geometry remains.
"""
import argparse
import collections
import copy
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def native_export(board_path,dsn_path,geometry_path):
    import pcbnew
    board=pcbnew.LoadBoard(str(board_path));pads=[];nc=0;tracks=[]
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname().startswith('unconnected-'):
                pad.SetNetCode(0);nc+=1
            layers=list(pad.GetLayerSet().CuStack())
            if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD or len(layers)!=1 or not pad.GetNetCode():continue
            poly=pcbnew.SHAPE_POLY_SET()
            pad.TransformShapeToPolygon(poly,layers[0],0,1000,pcbnew.ERROR_OUTSIDE)
            if poly.OutlineCount()!=1:continue
            coords=[[poly.Outline(0).CPoint(i).x/1000,-poly.Outline(0).CPoint(i).y/1000]
                    for i in range(poly.Outline(0).PointCount())]
            pads.append(dict(reference=fp.GetReference(),pin=pad.GetNumber(),net=pad.GetNetname(),
                             layer=board.GetLayerName(layers[0]),polygon_um=coords,
                             rectangular=pad.GetShape()==pcbnew.PAD_SHAPE_RECT,
                             uuid=pad.m_Uuid.AsString()))
    for item in board.GetTracks():
        if isinstance(item,pcbnew.PCB_TRACK) and not isinstance(item,(pcbnew.PCB_VIA,pcbnew.PCB_ARC)):
            a,b=item.GetStart(),item.GetEnd();dx=abs(a.x-b.x);dy=abs(a.y-b.y)
            if min(dx,dy)>2 and abs(dx-dy)>2:tracks.append(item.m_Uuid.AsString())
    if not pcbnew.ExportSpecctraDSN(board,str(dsn_path)):raise RuntimeError('Native DSN export failed')
    protected=[]
    def chain_um(outline):
        return [[outline.CPoint(i).x/1000,-outline.CPoint(i).y/1000] for i in range(outline.PointCount())]
    for z in board.Zones():
        if not z.GetIsRuleArea() or not z.GetDoNotAllowTracks():continue
        poly=z.Outline()
        for layer in z.GetLayerSet().CuStack():
            for i in range(poly.OutlineCount()):
                protected.append(dict(layer=board.GetLayerName(layer),shell=chain_um(poly.COutline(i)),
                    holes=[chain_um(poly.CHole(i,j)) for j in range(poly.HoleCount(i))]))
    geometry_path.write_text(json.dumps(dict(pads=pads,nc_pads_cleared=nc,non_octilinear_tracks=tracks,
        protected_reference_regions=protected)),encoding='utf-8')


def children(node,key):return [r for r in node if isinstance(r,list) and r and str(r[0])==key]
def child(node,key):return next(iter(children(node,key)),None)


def parse_dsn(text):
    """DSN identifiers may contain [], which sexpdata treats as delimiters."""
    import sexpdata as sx
    text=text.replace('(string_quote ")','(string_quote QUOTE)')
    stack=[];root=None
    for token in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text):
        if token=='(':
            row=[]
            if stack:stack[-1].append(row)
            else:root=row
            stack.append(row)
        elif token==')':stack.pop()
        elif token.startswith('"'):
            stack[-1].append(token[1:-1].replace('\\"','"').replace('\\\\','\\'))
        elif re.fullmatch(r'[+-]?\d+',token):stack[-1].append(int(token))
        elif re.fullmatch(r'[+-]?(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?',token):stack[-1].append(float(token))
        else:stack[-1].append(sx.Symbol(token))
    if stack:raise ValueError('Unbalanced DSN')
    return root


def dump_dsn(node):
    import sexpdata as sx
    if isinstance(node,list):return '('+' '.join(dump_dsn(item) for item in node)+')'
    if isinstance(node,sx.Symbol):return str(node)
    if isinstance(node,str):return json.dumps(node,ensure_ascii=False)
    return str(node)


def sanitize(raw,geometry,allow_filled_via_in_pad=False):
    import sexpdata as sx
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    S=sx.Symbol
    # Specctra's quote declaration is not a conventional quoted S-expression.
    tree=parse_dsn(raw)
    structure=child(tree,'structure')
    for region in geometry.get('protected_reference_regions',[]):
        def polygon(points):return [S('polygon'),region['layer'],0]+[v for xy in points for v in xy]
        structure.append([S('keepout'),polygon(region['shell'])]+[
            [S('window'),polygon(h)] for h in region['holes']])
    library=child(tree,'library');network=child(tree,'network');placement=child(tree,'placement')
    if allow_filled_via_in_pad:
        control=child(structure,'control')
        if control is None:control=[S('control')];structure.append(control)
        setting=child(control,'via_at_smd')
        if setting is None:control.append([S('via_at_smd'),S('on')])
        else:setting[1]=S('on')
        for stack in children(library,'padstack'):
            if str(stack[1]).startswith('Via'):
                attach=child(stack,'attach')
                if attach is not None:attach[1]=S('on')
        # A through-via drill must clear foreign PTH copper by .30 mm.
        # .20 mm copper spacing plus >=.10 mm via ring satisfies that rule.
        rule=child(structure,'rule')
        rule.append([S('clearance'),200,[S('type'),S('via_pin')]])
    wiring=child(tree,'wiring')
    if wiring is None:wiring=[S('wiring')];tree.append(wiring)
    images={str(row[1]):row for row in children(library,'image')}
    instance={str(p[1]):(comp,p) for comp in children(placement,'component') for p in children(comp,'place')}
    netpins={str(pin):str(net[1]) for net in children(network,'net') for pins in children(net,'pins') for pin in pins[1:]}
    groups=collections.defaultdict(list)
    for pad in geometry['pads']:groups[(pad['reference'],pad['net'],pad['layer'])].append(pad)
    removed=collections.defaultdict(set);events=[]
    for (ref,net,layer),pads in groups.items():
        polys=[Polygon(p['polygon_um']) for p in pads]
        used=set()
        for i in sorted(range(len(pads)),key=lambda i:polys[i].area,reverse=True):
            if i in used:continue
            indices={i};pending=[i]
            while pending:
                a=pending.pop()
                for j,p in enumerate(polys):
                    if j not in indices and j not in used and polys[a].intersection(p).area>1e-4:
                        indices.add(j);pending.append(j)
            if len(indices)<2:continue
            originals=[pads[j] for j in indices]
            if len({p['pin'] for p in originals})!=len(originals):
                events.append(dict(reference=ref,status='skipped_duplicate_pin_numbers'));continue
            if any(netpins.get(ref+'-'+p['pin'])!=net for p in originals):
                raise ValueError(f'Native/DSN pin net mismatch for {ref}')
            anchor=i;representations=[polys[anchor]];conversions=[]
            for j in sorted(indices-{anchor}):
                if polys[anchor].covers(polys[j]):
                    conversions.append((j,'contained_identical_or_smaller'))
                else:
                    events.append(dict(reference=ref,net=net,status='retained_partial_overlap',
                                       reason='Wire polygons are not routing obstacles in FreeRouting.'))
                    used.update(indices)
                    conversions=[];break
            if not conversions:continue
            before=unary_union([polys[j] for j in indices]);after=unary_union(representations)
            delta=before.symmetric_difference(after).area
            if delta>1e-5:raise ValueError(f'Copper union changed for {ref}: {delta} square micrometres')
            for j,kind in conversions:
                removed[ref].add(pads[j]['pin'])
            events.append(dict(reference=ref,net=net,layer=layer,anchor_pin=pads[anchor]['pin'],
                               removed_pins=[pads[j]['pin'] for j,_ in conversions],
                               copper_union_symmetric_difference_um2=delta,status='sanitized'))
            used.update(indices)
    for ref,pins in removed.items():
        comp,place=instance[ref];image=copy.deepcopy(images[str(comp[1])]);newname=str(comp[1])+'__router_'+ref
        image[1]=newname
        def pin_number(row):
            atoms=[x for x in row[1:] if not isinstance(x,list)]
            return str(atoms[1])
        image[:]=[r for r in image if not (isinstance(r,list) and r and str(r[0])=='pin' and pin_number(r) in pins)]
        library.append(image);comp.remove(place)
        placement.append([S('component'),newname,place])
        for net in children(network,'net'):
            for pinrow in children(net,'pins'):
                pinrow[:]=[pinrow[0]]+[pin for pin in pinrow[1:] if str(pin) not in {ref+'-'+p for p in pins}]
    placement[:]=[r for r in placement if not (isinstance(r,list) and r and str(r[0])=='component' and not children(r,'place'))]
    text=dump_dsn(tree).replace('(string_quote QUOTE)','(string_quote ")')+'\n'
    return text,events


def main():
    if '--native-export' in sys.argv:
        native_export(*map(Path,sys.argv[-3:]));return 0
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--board',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--kicad-python',type=Path,default=Path('tools/kicad/bin/python.exe'))
    ap.add_argument('--kicad-cli',type=Path,default=Path('tools/kicad/bin/kicad-cli.exe'))
    ap.add_argument('--allow-filled-via-in-pad',action='store_true',help='Require filled and capped processing for every new via overlapping an SMD land')
    args=ap.parse_args();board=args.board.resolve();out=args.output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
    before=digest(board);raw=out.with_suffix('.raw.dsn');geo=out.with_suffix('.geometry.json');drc=out.with_suffix('.native-drc.json')
    run=subprocess.run([str(args.kicad_cli.resolve()),'pcb','drc','--format','json','--severity-all','--all-track-errors',
                        '--refill-zones','--output',str(drc),str(board)],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if run.returncode not in (0,5):raise RuntimeError('Native DRC failed: '+run.stdout+run.stderr)
    data=json.loads(drc.read_text(encoding='utf-8-sig'))
    errors=[v for v in data['violations'] if v.get('severity')=='error']
    if errors:raise RuntimeError('Native physical DRC errors must be fixed before preparing router input: '+str(collections.Counter(v['type'] for v in errors)))
    subprocess.run([str(args.kicad_python.resolve()),str(Path(__file__).resolve()),'--native-export',str(board),str(raw),str(geo)],check=True)
    geometry=json.loads(geo.read_text());text,events=sanitize(raw.read_text(encoding='utf-8'),geometry,args.allow_filled_via_in_pad)
    if digest(board)!=before:raise RuntimeError('Source board changed during export; discard and rerun')
    out.write_text(text,encoding='utf-8')
    report=dict(source_board=str(board),source_sha256=before,source_board_unchanged=True,dsn=str(out),dsn_sha256=digest(out),
                filled_capped_via_in_pad_enabled=args.allow_filled_via_in_pad,
                native_physical_errors=0,native_drc_unconnected_reported=len(data['unconnected_items']),
                native_drc_unconnected_count_may_be_capped=len(data['unconnected_items'])>=499,
                nc_pads_cleared_in_router_only=geometry['nc_pads_cleared'],non_octilinear_tracks=geometry['non_octilinear_tracks'],
                edits=events,limitations=['All source PCB pads, geometry and custom DRC rules are retained in the native board.',
                  'Router DSN does not express all native hole, netclass and manufacturing constraints; native post-import DRC is required.',
                  'Partly overlapping same-net pads remain original DSN pads; known router self-overlap reports are not native clearance errors.',
                  'Import SES only into the source board matching source_sha256; native schematic/pad connectivity remains authoritative.'])
    out.with_suffix('.preflight.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
