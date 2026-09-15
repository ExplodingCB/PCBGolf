"""Isolated, clearance-screened BGA100 dogbone experiment; run with KiCad Python.

Uses existing BGA100 pad/net assignments unchanged. Native DRC and merged parity
run after saving. Fanout access does not constitute completion of signal routes.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import subprocess

import pcbnew as pcb
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
from route_ground import xy, copper_shape, hole_shape, track_shape, COPPER

ROOT = Path(__file__).resolve().parents[1]
MM = pcb.FromMM
WIDTH, DIAMETER, DRILL = .12, .45, .20
MARGIN = .002


def vec(p):
    return pcb.VECTOR2I(MM(p[0]), MM(p[1]))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def annotate_blockers(board, report):
    """Identify native pad geometry that blocks each rejected dogbone site."""
    obstacles=[]
    for pad in board.GetPads():
        shapes={l:copper_shape(pad,l) for l in COPPER if pad.IsOnLayer(l)}
        obstacles.append((pad,shapes,hole_shape(pad) if pad.HasHole() else None))
    needs={r['ball']:r['net'] for r in report['unescaped']}
    totals=collections.Counter()
    for name,net in needs.items():
        for rejected in report['candidate_rejections'][name]:
            point=Point(rejected['site_mm']);found=[]
            for pad,shapes,hole in obstacles:
                ref=pad.GetParentFootprint().GetReference();label=ref+'.'+pad.GetNumber()
                pth=pad.GetAttribute()==pcb.PAD_ATTRIB_PTH
                if pad.GetNetname()!=net:
                    minimum=max(.10+DIAMETER/2,(.30 if pth else .20)+DRILL/2)+MARGIN
                    for layer,shape in shapes.items():
                        distance=point.distance(shape)
                        if distance<minimum:
                            found.append(dict(pad=label,net=pad.GetNetname(),layer=board.GetLayerName(layer),
                                              reason='via copper/hole clearance to pad',
                                              center_to_copper_mm=round(distance,6),minimum_mm=minimum))
                if pad.GetAttribute()==pcb.PAD_ATTRIB_SMD:
                    for layer,shape in shapes.items():
                        if point.distance(shape)<DRILL/2+.05+MARGIN:
                            found.append(dict(pad=label,net=pad.GetNetname(),layer=board.GetLayerName(layer),
                                              reason='ordinary dogbone drill too close to solderable land'))
                if hole is not None and point.distance(hole)<DRILL/2+.20+MARGIN:
                    found.append(dict(pad=label,reason='mechanical hole spacing'))
            rejected['pad_blockers']=found
            for ref in {row['pad'].split('.')[0] for row in found}:totals[ref]+=1
    report['unescaped_candidate_blocking_components']=dict(totals.most_common())


def run(board, direct_rings=1):
    u3 = next(f for f in board.GetFootprints() if f.GetReference() == 'U3')
    assert u3.GetValue() == 'STM32H725VGH6' and u3.GetLayer() == pcb.B_Cu
    assert board.GetCopperLayerCount() == 4
    assert len(board.GetTracks()) == 0, 'Experiment expects the untouched unrouted base'
    pads = list(board.GetPads())
    balls = {p.GetNumber(): p for p in u3.Pads()}
    assert len(balls) == 100
    connected = {n: p for n, p in balls.items() if p.GetNetCode() and not p.GetNetname().startswith('unconnected-')}
    assert len(connected) == 82
    locations = {n: xy(p.GetPosition()) for n, p in balls.items()}
    xs, ys = sorted({p[0] for p in locations.values()}), sorted({p[1] for p in locations.values()})
    assert len(xs) == len(ys) == 10
    assert all(abs(xs[i+1]-xs[i]-.8) < .00001 for i in range(9))
    perimeter = {n for n, (x, y) in locations.items() if x in (xs[0], xs[-1]) or y in (ys[0], ys[-1])}
    ring_index={n:min(xs.index(x),9-xs.index(x),ys.index(y),9-ys.index(y)) for n,(x,y) in locations.items()}
    records = []
    for pad in pads:
        copper = {layer: copper_shape(pad, layer) for layer in COPPER if pad.IsOnLayer(layer)}
        records.append(dict(net=pad.GetNetname(), copper=copper,
                            smd=pad.GetAttribute() == pcb.PAD_ATTRIB_SMD,
                            hole=hole_shape(pad) if pad.HasHole() else None,
                            pth=pad.GetAttribute() == pcb.PAD_ATTRIB_PTH,
                            label=pad.GetParentFootprint().GetReference()+'.'+pad.GetNumber()))
    geometry_cache = {}

    def geometry(net):
        if net in geometry_cache:
            return geometry_cache[net]
        copper = {l: [] for l in COPPER}
        holes = []
        via_blocks = []
        for item in records:
            if item['net'] != net:
                for layer, shape in item['copper'].items():
                    copper[layer].append(shape.buffer(.10 + WIDTH/2 + MARGIN))
                    # Via copper-to-pad and via drilled hole-to-pad on every layer.
                    gap = max(.10 + DIAMETER/2, (.30 if item['pth'] else .20) + DRILL/2)
                    via_blocks.append(shape.buffer(gap + MARGIN))
                if item['hole'] is not None:
                    gap = .30 if item['pth'] else .20
                    holes.append(item['hole'].buffer(gap + WIDTH/2 + MARGIN))
                    via_blocks.append(item['hole'].buffer(gap + DIAMETER/2 + MARGIN))
            if item['hole'] is not None:
                # New drill to every existing drill, including same-net holes.
                via_blocks.append(item['hole'].buffer(.20 + DRILL/2 + MARGIN))
            if item['smd']:
                # Keep ordinary dogbone drills away from all solderable lands.
                for shape in item['copper'].values():
                    via_blocks.append(shape.buffer(DRILL/2 + .05 + MARGIN))
        geometry_cache[net] = dict(track={l: unary_union(copper[l] + holes) for l in COPPER},
                                   via=unary_union(via_blocks))
        return geometry_cache[net]

    added_tracks, added_vias = [], []
    added_shapes = []

    def clear_track(net, points):
        line = LineString(points)
        if geometry(net)['track'][pcb.B_Cu].intersects(line):
            return False
        return all(other_net == net or line.distance(shape) >= WIDTH/2 + .10 + MARGIN
                   for other_net, shape in added_shapes)

    def track(net, points, pins, role):
        for a, b in zip(points, points[1:]):
            item = pcb.PCB_TRACK(board)
            item.SetStart(vec(a)); item.SetEnd(vec(b)); item.SetWidth(MM(WIDTH))
            item.SetLayer(pcb.B_Cu); item.SetNet(board.FindNet(net)); board.Add(item)
            added_tracks.append(dict(uuid=item.m_Uuid.AsString(), net=net, pins=pins,
                                     start_mm=a, end_mm=b, width_mm=WIDTH, role=role))
        added_shapes.append((net, LineString(points).buffer(WIDTH/2, quad_segs=32)))

    report = dict(perimeter_access=[], supply_direct_access=[], failed_direct_access=[],
                  candidate_rejections={}, unescaped=[], ground_connections=[], limitations=[])
    # Critical switching and feedback terminals remain direct on B.Cu. Their
    # local passives must be moved beside these access points in the final layout.
    direct = {'D2', 'E2'}
    direct_eligible={n for n in connected if ring_index[n]<direct_rings and connected[n].GetNetname()!='GND'} | direct
    direct_order=sorted(direct_eligible,key=lambda n:(0 if n in direct else 1 if n in perimeter else 2,n))
    for name in direct_order:
        pad = connected[name]; net = pad.GetNetname(); x, y = locations[name]
        if name in direct:
            options = [[(x,y),(x-.4,y+dy),(xs[0]-.8,y+dy)] for dy in (-.4,.4)]
        elif name in perimeter:
            directions = []
            if x == xs[0]: directions.append((-1,0))
            if x == xs[-1]: directions.append((1,0))
            if y == ys[0]: directions.append((0,-1))
            if y == ys[-1]: directions.append((0,1))
            options = [[(x,y),(x+dx*.8,y+dy*.8)] for dx,dy in directions]
        else:
            options=[]
            if x==xs[1]:
                # VBAT C2 exits above C1, leaving the C1/D1 ground-via cell
                # open beside the direct D2 switching escape below it.
                offsets=(.4,-.4) if name=='C2' else (-.4,.4)
                options += [[(x,y),(x-.4,y+dy),(xs[0]-.8,y+dy)] for dy in offsets]
            if x==xs[-2]:
                options += [[(x,y),(x+.4,y+dy),(xs[-1]+.8,y+dy)] for dy in (-.4,.4)]
            if y==ys[1]:
                options += [[(x,y),(x+dx,y-.4),(x+dx,ys[0]-.8)] for dx in (-.4,.4)]
            if y==ys[-2]:
                options += [[(x,y),(x+dx,y+.4),(x+dx,ys[-1]+.8)] for dx in (-.4,.4)]
        selected = next((p for p in options if clear_track(net,p)), None)
        if selected:
            track(net, selected, [name], 'supply_access' if name in direct else 'perimeter_access')
            report['supply_direct_access' if name in direct else 'perimeter_access'].append(
                dict(ball=name,net=net,path_mm=selected,via_count=0,ring_index=ring_index[name]))
        else:
            report['failed_direct_access'].append(dict(ball=name,net=net))

    direct_done = {r['ball'] for r in report['perimeter_access'] + report['supply_direct_access']}
    needs = {n:p for n,p in connected.items() if n not in direct_done}
    candidates = {}
    for name, pad in needs.items():
        x,y = locations[name]; net=pad.GetNetname(); candidates[name]=[]; rejected=[]
        for dx,dy in ((-.4,-.4),(-.4,.4),(.4,-.4),(.4,.4)):
            site = (round(x+dx,6),round(y+dy,6)); line=[(x,y),site]
            reasons=[]
            if geometry(net)['via'].intersects(Point(site)):
                reasons.append('existing_all_layer_copper_or_drill')
            if not clear_track(net,line):
                reasons.append('dogbone_track_clearance')
            if any(other_net != net and Point(site).distance(shape) < max(DIAMETER/2+.10,DRILL/2+.20)+MARGIN
                   for other_net,shape in added_shapes):
                reasons.append('direct_access_trace_clearance')
            if reasons:rejected.append(dict(site_mm=site,reasons=reasons))
            else:candidates[name].append(site)
        report['candidate_rejections'][name]=rejected

    # A maximum bipartite match gets each ball a legal site. Reassign same-net
    # balls to an existing compatible site afterward to share ordinary dogbones.
    best = None
    for seed in range(48):
        rng=random.Random(seed)
        order=list(needs);rng.shuffle(order);order.sort(key=lambda n:len(candidates[n]))
        options={n:list(candidates[n]) for n in needs}
        for value in options.values():rng.shuffle(value)
        site_owner={}
        def augment(name,seen):
            for site in options[name]:
                if site in seen:continue
                seen.add(site)
                if site not in site_owner or augment(site_owner[site],seen):
                    site_owner[site]=name;return True
            return False
        for name in order:augment(name,set())
        allocation={name:site for site,name in site_owner.items()}
        while True:
            changed=False
            for name in order:
                if name not in allocation:continue
                oldsite=allocation[name];net=needs[name].GetNetname()
                groups=collections.defaultdict(list)
                for member,site in allocation.items():groups[site].append(member)
                if len(groups[oldsite])>1:continue
                alternatives=[s for s in options[name] if s!=oldsite and s in groups
                              and all(needs[m].GetNetname()==net for m in groups[s])]
                if alternatives:
                    allocation[name]=alternatives[0];changed=True
            if not changed:break
        score=(len(allocation),-len(set(allocation.values())))
        if best is None or score>best[0]:best=(score,allocation)
    allocation=best[1]
    grouped=collections.defaultdict(list)
    for name,site in allocation.items():grouped[site].append(name)
    for site,names in sorted(grouped.items()):
        net=needs[names[0]].GetNetname()
        via=pcb.PCB_VIA(board);via.SetPosition(vec(site));via.SetWidth(MM(DIAMETER));via.SetDrill(MM(DRILL))
        via.SetViaType(pcb.VIATYPE_THROUGH);via.SetLayerPair(pcb.F_Cu,pcb.B_Cu)
        via.SetNet(board.FindNet(net));board.Add(via)
        added_vias.append(dict(uuid=via.m_Uuid.AsString(),net=net,balls=names,at_mm=site,
                               diameter_mm=DIAMETER,drill_mm=DRILL,
                               destination='In1.Cu GND plane' if net=='GND' else 'layer access only; continuation required'))
        for name in names:track(net,[locations[name],site],[name],'dogbone')
        if net=='GND':report['ground_connections'].append(dict(balls=names,via_uuid=via.m_Uuid.AsString()))
    report['unescaped']=[dict(ball=n,net=p.GetNetname(),legal_sites=candidates[n])
                         for n,p in needs.items() if n not in allocation]
    # Fill the real zones; do not fabricate a +3V3/VDDLDO connection to +12V.
    board.BuildConnectivity()
    pcb.ZONE_FILLER(board).Fill(board.Zones())
    ground_zones=[z for z in board.Zones() if z.GetLayer()==pcb.In1_Cu and z.GetNetname()=='GND']
    for connection in report['ground_connections']:
        via=next(v for v in added_vias if v['uuid']==connection['via_uuid'])
        connection['inside_filled_In1_GND']=any(z.HitTestFilledArea(pcb.In1_Cu,vec(via['at_mm']))
                                               for z in ground_zones)
        assert connection['inside_filled_In1_GND'], 'Ground via did not meet filled reference plane'
    report.update(vias=added_vias,tracks=added_tracks,direct_rings=direct_rings,
                  counts=dict(total_balls=100,connected_balls=82,no_connect_balls=18,
                              perimeter_or_direct_without_vias=len(direct_done),
                              balls_with_dogbones=len(allocation),vias=len(added_vias),
                              shared_vias=sum(len(v['balls'])>1 for v in added_vias),
                              unescaped=len(report['unescaped']),track_segments=len(added_tracks)),
                  limitations=[
                      'Signal dogbones expose another layer but are not end-to-end routes.',
                      'Native hole/copper DRC is authoritative; no fabrication-rule waiver is used.',
                      'In2 remains +12V; MCU +3V3/VDDLDO/VDDA fanouts require dedicated local supply copper and decoupling.',
                      'D2 VLXSMPS and E2 VFBSMPS stay on B.Cu; L4 and local capacitors still need relocation beside U3.',
                      '.12mm supply access tracks are geometric experiments, not final current/inductance sizing.',
                      'Ground plane attachment is checked geometrically; return-current/thermal performance is not certified.'])
    annotate_blockers(board,report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'candidates/bga100-base')
    parser.add_argument('--output',type=Path,default=ROOT/'candidates/bga100-escape')
    parser.add_argument('--refresh-known-escape',action='store_true',
                        help='Remove only prior escape-report track/via UUIDs in the output copy before rebuilding')
    parser.add_argument('--mcu-x',type=float,help='MCU center x in mm in the isolated output')
    parser.add_argument('--mcu-y',type=float,help='MCU center y in mm in the isolated output')
    parser.add_argument('--direct-rings',type=int,choices=(1,2),default=1,
                        help='Try one or two perimeter rows directly on B.Cu before dogbones')
    args=parser.parse_args();source=args.source.resolve();out=args.output.resolve()
    assert source!=out and source not in out.parents and out not in source.parents
    source_hashes={p.name:sha(p) for p in source.glob('*.kicad_*') if p.is_file()}
    settings=json.loads((source/'pcbgolf.kicad_pro').read_text())['board']['design_settings']
    assert not settings.get('drc_exclusions'), 'Experiment requires zero pre-existing DRC exclusions'
    shutil.copytree(source,out,dirs_exist_ok=True)
    boardpath=out/'pcbgolf.kicad_pcb';board=pcb.LoadBoard(str(boardpath))
    removed=[];removed_native=[]
    if args.refresh_known_escape:
        previous=json.loads((source/'escape-report.json').read_text())
        uuids={row['uuid'] for row in previous['tracks']+previous['vias']}
        for item in list(board.GetTracks()):
            if item.m_Uuid.AsString() in uuids:
                removed.append(item.m_Uuid.AsString());removed_native.append(item);board.RemoveNative(item)
        assert len(removed)==len(uuids), 'Some prior escape UUIDs are missing; refuse ambiguous refresh'
    mcu=next(f for f in board.GetFootprints() if f.GetReference()=='U3')
    original_pose=xy(mcu.GetPosition())
    pose=(args.mcu_x if args.mcu_x is not None else original_pose[0],
          args.mcu_y if args.mcu_y is not None else original_pose[1])
    mcu.SetPosition(vec(pose))
    report=run(board,args.direct_rings);pcb.SaveBoard(str(boardpath),board)
    assert source_hashes=={p.name:sha(p) for p in source.glob('*.kicad_*') if p.is_file()}
    report.update(source=str(source),source_hashes=source_hashes,source_unchanged=True,
                  board=str(boardpath),board_sha256=sha(boardpath),submission_ready=False,
                  prior_escape_items_removed_in_copy=removed,mcu_pose_mm=pose,original_mcu_pose_mm=original_pose)
    drcpath=out/'escape-drc.json'
    subprocess.run([str(ROOT/'tools/kicad/bin/kicad-cli.exe'),'pcb','drc','--format','json',
                    '--severity-all','--all-track-errors','--refill-zones','--output',str(drcpath),str(boardpath)],check=True)
    drc=json.loads(drcpath.read_text());errors=[r for r in drc['violations'] if r['severity']=='error']
    physical_types={'hole_to_hole','holes_co_located','clearance','hole_clearance','shorting_items',
                    'annular_width','drill_out_of_range','track_width','copper_edge_clearance',
                    'courtyards_overlap','solder_mask_bridge','connection_width','starved_thermal'}
    physical=[r for r in drc['violations'] if r['severity']=='error' or r['type'] in physical_types]
    report['native_drc']=dict(nonrouting_errors=len(errors),errors=errors,
        physical_violations_including_warnings=len(physical),physical_violations=physical,
        warning_types=dict(collections.Counter(r['type'] for r in drc['violations'] if r['severity']=='warning')),
        unconnected_records=len(drc['unconnected_items']),
        unconnected_count_is_lower_bound=len(drc['unconnected_items'])>=499)
    paritypath=out/'connectivity.json'
    subprocess.run([str(ROOT/'tools/venv/Scripts/python.exe'),str(ROOT/'scripts/validate_connectivity.py'),
                    '--board',str(boardpath),'--project',str(out/'pcbgolf.kicad_pro'),
                    '--netlist-dir',str(out/'netlists'),'--output',str(paritypath)],cwd=ROOT,check=True)
    report['logical_parity']=json.loads(paritypath.read_text())['status']
    report['status']='DRC-clean fanout experiment; full routing unfinished' if not physical else 'Fanout experiment has physical DRC violations'
    (out/'escape-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],counts=report['counts'],drc=report['native_drc'],
                         unescaped=report['unescaped']),indent=2))


if __name__=='__main__':main()
