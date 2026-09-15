"""Audit USB routes and power widths without changing a KiCad board.

Run using tools/venv/Scripts/python.exe. A read-only subprocess uses the bundled
KiCad Python for exact pad placement/shapes and native arc/track lengths.
Shortest route lengths exclude travel within pads/zones; they are estimates of
trace-centerline path length, not field-solved delay or exact electrical skew.
"""
import argparse
import collections
import hashlib
import heapq
import itertools
import json
import math
from pathlib import Path
import re
import subprocess
import sys


PAIR_MAP = {
    'USB_D': {'N': ('U4','58','J3',{'A':'A7','B':'B7'}), 'P': ('U4','59','J3',{'A':'A6','B':'B6'})},
    'CH1_D': {'N': ('U4','1','J5',{'A':'A7','B':'B7'}), 'P': ('U4','2','J5',{'A':'A6','B':'B6'})},
    'CH2_D': {'N': ('U4','3','J6',{'A':'A7','B':'B7'}), 'P': ('U4','4','J6',{'A':'A6','B':'B6'})},
    'CH3_D': {'N': ('U4','6','J7',{'A':'A7','B':'B7'}), 'P': ('U4','7','J7',{'A':'A6','B':'B6'})},
    'CH4_D': {'N': ('U4','8','J8',{'A':'A7','B':'B7'}), 'P': ('U4','9','J8',{'A':'A6','B':'B6'})},
    'STM_D': {'N': ('U4','55','U3',{'MCU':'100'}), 'P': ('U4','56','U3',{'MCU':'101'})},
}
USB_NETS = {f'{pair}_{pol}' for pair in PAIR_MAP for pol in ('N','P')}


def native_extract(path):
    import pcbnew
    board = pcbnew.LoadBoard(str(path))
    enabled = list(board.GetEnabledLayers().CuStack())
    layers = [board.GetLayerName(layer) for layer in enabled]
    xy = lambda v: [v.x/1e6, v.y/1e6]
    tracks, vias, pads = [], [], []
    for item in board.GetTracks():
        is_via = isinstance(item, pcbnew.PCB_VIA)
        width = item.GetWidth(pcbnew.F_Cu) if is_via else item.GetWidth()
        row = dict(uuid=item.m_Uuid.AsString(), net=item.GetNetname(), width_mm=width/1e6)
        if isinstance(item, pcbnew.PCB_VIA):
            row.update(position=xy(item.GetPosition()), drill_mm=item.GetDrillValue()/1e6,
                       layers=[board.GetLayerName(layer) for layer in item.GetLayerSet().CuStack() if layer in enabled])
            vias.append(row)
        else:
            row.update(start=xy(item.GetStart()), end=xy(item.GetEnd()), layer=item.GetLayerName(), length_mm=item.GetLength()/1e6)
            if isinstance(item, pcbnew.PCB_ARC):
                row['mid'] = xy(item.GetMid())
            tracks.append(row)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() not in USB_NETS:
                continue
            polygons = {}
            for layer in pad.GetLayerSet().CuStack():
                if layer not in enabled:
                    continue
                poly = pcbnew.SHAPE_POLY_SET()
                pad.TransformShapeToPolygon(poly, layer, 0, pcbnew.FromMM(.001), pcbnew.ERROR_OUTSIDE)
                polygons[board.GetLayerName(layer)] = [[xy(poly.Outline(i).CPoint(j)) for j in range(poly.Outline(i).PointCount())] for i in range(poly.OutlineCount())]
            pads.append(dict(uuid=pad.m_Uuid.AsString(), reference=fp.GetReference(), number=pad.GetNumber(),
                             net=pad.GetNetname(), position=xy(pad.GetPosition()), polygons=polygons))
    zones = collections.Counter(z.GetNetname() for z in board.Zones())
    print(json.dumps(dict(layers=layers, thickness_mm=board.GetDesignSettings().GetBoardThickness()/1e6,
                         tracks=tracks, vias=vias, pads=pads, zone_counts=dict(zones))))


def line_points(track):
    if 'mid' not in track:
        return [track['start'],track['end']]
    ax,ay = track['start']; bx,by = track['mid']; cx,cy = track['end']
    den = 2*(ax*(by-cy)+bx*(cy-ay)+cx*(ay-by))
    if abs(den)<1e-12:
        return [track['start'],track['mid'],track['end']]
    ux=((ax*ax+ay*ay)*(by-cy)+(bx*bx+by*by)*(cy-ay)+(cx*cx+cy*cy)*(ay-by))/den
    uy=((ax*ax+ay*ay)*(cx-bx)+(bx*bx+by*by)*(ax-cx)+(cx*cx+cy*cy)*(bx-ax))/den
    a,b,c = [math.atan2(y-uy,x-ux) for x,y in (track['start'],track['mid'],track['end'])]
    sweep=(c-a)%(2*math.pi)
    if (b-a)%(2*math.pi)>sweep+1e-9:
        sweep-=2*math.pi
    radius=math.hypot(ax-ux,ay-uy)
    count=max(4,math.ceil(abs(sweep)/max(.001,2*math.acos(max(-1,1-.001/max(radius,.001))))))
    return [[ux+radius*math.cos(a+sweep*i/count),uy+radius*math.sin(a+sweep*i/count)] for i in range(count+1)]


def representative_points(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Point':
        return [geometry]
    if geometry.geom_type in ('LineString','LinearRing'):
        from shapely.geometry import Point
        return [Point(geometry.coords[0]), Point(geometry.coords[-1])]
    if hasattr(geometry,'geoms'):
        return [p for g in geometry.geoms for p in representative_points(g)]
    return []


class RouteGraph:
    def __init__(self, data, net, tolerance=.002):
        from shapely.geometry import LineString, Point, Polygon
        from shapely.ops import nearest_points, unary_union
        self.graph=collections.defaultdict(list)
        self.pad_nodes=collections.defaultdict(list)
        self.net=net; self.data=data; self.tolerance=tolerance
        self.rows=[t for t in data['tracks'] if t['net']==net]
        self.lines=[LineString(line_points(t)) for t in self.rows]
        cuts=[{0.,line.length} for line in self.lines]
        links=[]; pad_shapes=[]
        # Actual same-layer centerline crossings, T junctions and touching-width
        # joins. Tiny copper-only bridges get zero length, recorded as estimates.
        for i,a in enumerate(self.lines):
            for j in range(i):
                b=self.lines[j]
                if self.rows[i]['layer']!=self.rows[j]['layer']:
                    continue
                points=representative_points(a.intersection(b))
                if points:
                    for p in points:
                        cuts[i].add(a.project(p)); cuts[j].add(b.project(p))
                elif a.distance(b)<=(self.rows[i]['width_mm']+self.rows[j]['width_mm'])/2+tolerance:
                    pa,pb=nearest_points(a,b)
                    cuts[i].add(a.project(pa)); cuts[j].add(b.project(pb))
                    links.append((self.point_node(pa,self.rows[i]['layer']),self.point_node(pb,self.rows[j]['layer']),0.,'copper_touch',None))
        for pad in (p for p in data['pads'] if p['net']==net):
            nodes=[]
            for layer,polys in pad['polygons'].items():
                valid=[Polygon(p) for p in polys if len(p)>=3]
                if not valid:
                    continue
                shape=unary_union(valid).buffer(tolerance)
                anchor=('pad',pad['uuid'],layer); nodes.append(anchor)
                pad_shapes.append((shape,anchor,layer,pad['uuid']))
                self.pad_nodes[(pad['reference'],pad['number'])].append(anchor)
                for i,line in enumerate(self.lines):
                    if self.rows[i]['layer']!=layer:
                        continue
                    contact=line.intersection(shape.buffer(self.rows[i]['width_mm']/2))
                    for point in representative_points(contact):
                        cuts[i].add(line.project(point))
                        links.append((anchor,self.point_node(point,layer),0.,'pad_contact',pad['uuid']))
            for a,b in itertools.combinations(nodes,2):
                links.append((a,b,0.,'plated_pad',pad['uuid']))
        for via in (v for v in data['vias'] if v['net']==net):
            p=Point(via['position']); nodes=[]
            for layer in via['layers']:
                node=self.point_node(p,layer);nodes.append(node)
                # A filled/capped via can touch an SMD pad directly, with no
                # same-layer track between their centres. Preserve that
                # copper contact in the graph instead of reporting an open.
                for shape,anchor,pad_layer,pad_uuid in pad_shapes:
                    if pad_layer==layer and shape.distance(p)<=via['width_mm']/2:
                        links.append((node,anchor,0.,'via_pad_contact',pad_uuid))
                for i,line in enumerate(self.lines):
                    if self.rows[i]['layer']==layer and line.distance(p)<=via['width_mm']/2+self.rows[i]['width_mm']/2+tolerance:
                        q=line.interpolate(line.project(p));cuts[i].add(line.project(q))
                        links.append((node,self.point_node(q,layer),p.distance(q),'via_contact',via['uuid']))
            for a,b in itertools.combinations(nodes,2):
                links.append((a,b,0.,'via',via['uuid']))
        for i,line in enumerate(self.lines):
            positions=sorted(cuts[i]); scale=self.rows[i]['length_mm']/line.length if line.length else 1
            for a,b in zip(positions,positions[1:]):
                if b-a<1e-9:
                    continue
                links.append((self.point_node(line.interpolate(a),self.rows[i]['layer']),
                              self.point_node(line.interpolate(b),self.rows[i]['layer']),
                              (b-a)*scale,'track',self.rows[i]['uuid']))
        for a,b,length,kind,uuid in links:
            if a==b:
                continue
            self.graph[a].append((b,length,kind,uuid));self.graph[b].append((a,length,kind,uuid))

    def point_node(self,p,layer):
        # Native KiCad coordinates have nm precision. Quantize to 1um for joins.
        return ('point',round(p.x,3),round(p.y,3),layer)

    def path(self,source,target):
        starts=self.pad_nodes.get(source,[]); ends=set(self.pad_nodes.get(target,[]))
        if not starts or not ends:
            return dict(status='missing_endpoint_pad',source='.'.join(source),target='.'.join(target),length_mm=None)
        queue=[]; serial=itertools.count(); distances={};previous={}
        for node in starts:
            distances[node]=0.;heapq.heappush(queue,(0.,next(serial),node))
        finish=None
        while queue:
            distance,_,node=heapq.heappop(queue)
            if distance!=distances[node]:
                continue
            if node in ends:
                finish=node;break
            for other,length,kind,uuid in self.graph[node]:
                new=distance+length
                if new<distances.get(other,math.inf)-1e-10:
                    distances[other]=new;previous[other]=(node,length,kind,uuid)
                    heapq.heappush(queue,(new,next(serial),other))
        if finish is None:
            return dict(status='unrouted_or_graph_gap',source='.'.join(source),target='.'.join(target),length_mm=None)
        transitions=[];via_ids=set();track_ids=set();bridges=0;node=finish
        layer_order=self.data['layers'];vertical=0.
        while node in previous:
            prev,length,kind,uuid=previous[node]
            if kind=='track': track_ids.add(uuid)
            if kind=='via': via_ids.add(uuid)
            if kind=='copper_touch': bridges+=1
            if kind in ('via','plated_pad'):
                la,lb=prev[-1],node[-1]
                transitions.append(dict(from_layer=la,to_layer=lb,kind=kind,uuid=uuid))
                vertical+=abs(layer_order.index(la)-layer_order.index(lb))*self.data['thickness_mm']/max(1,len(layer_order)-1)
            node=prev
        return dict(status='path_found',source='.'.join(source),target='.'.join(target),length_mm=distances[finish],
                    length_definition='Shortest connected track-centerline XY path, travel within pads omitted',
                    via_count=len(via_ids),layer_change_count=len(transitions),layer_changes=list(reversed(transitions)),
                    via_barrel_estimate_mm=vertical,barrel_estimate_assumption='Nominal board thickness and evenly spaced copper layers',
                    route_plus_barrel_estimate_mm=distances[finish]+vertical,track_items_on_path=len(track_ids),
                    zero_length_copper_touch_bridges=bridges)


def uncoupled_estimate(rows,other_rows,max_gap=.5,angle_deg=15,sample_mm=.25):
    from shapely.geometry import LineString
    targets=[(r,LineString(line_points(r))) for r in other_rows]
    suspect=[];unmatched=0.;total=0.
    for row in rows:
        line=LineString(line_points(row));length=row['length_mm'];total+=length
        if line.length<1e-9:
            continue
        count=max(1,math.ceil(line.length/sample_mm));bad=0
        for i in range(count):
            s=(i+.5)*line.length/count;p=line.interpolate(s)
            a=line.interpolate(max(0,s-.01));b=line.interpolate(min(line.length,s+.01))
            vx,vy=b.x-a.x,b.y-a.y;norm=math.hypot(vx,vy);coupled=False
            for other,target in targets:
                if other['layer']!=row['layer'] or target.distance(p)>(row['width_mm']+other['width_mm'])/2+max_gap:
                    continue
                t=target.project(p);c=target.interpolate(max(0,t-.01));d=target.interpolate(min(target.length,t+.01))
                wx,wy=d.x-c.x,d.y-c.y;den=norm*math.hypot(wx,wy)
                if den and abs((vx*wx+vy*wy)/den)>=math.cos(math.radians(angle_deg)):
                    coupled=True;break
            bad+=not coupled
        fraction=bad/count;unmatched+=length*fraction
        if fraction>=.8 and length>=.5:
            suspect.append(dict(uuid=row['uuid'],layer=row['layer'],length_mm=length,uncoupled_fraction=fraction,start=row['start'],end=row['end']))
    return dict(estimated_uncoupled_length_mm=unmatched,fraction=unmatched/total if total else None,
                obvious_segments=suspect,criteria=dict(max_copper_edge_gap_mm=max_gap,max_parallel_angle_deg=angle_deg,sample_spacing_mm=sample_mm),
                interpretation='Heuristic same-layer proximity and parallelism only; not differential impedance validation')


def resolve_endpoint(data,net,reference,expected_pin,allow_remap=False):
    """Keep named endpoints, allowing uniquely identifiable package remaps.

    A BGA variant renumbers MCU pins. Resolve only within the same component and
    net, and expose the remap in the report; this is not schematic validation.
    """
    pins=sorted({p['number'] for p in data['pads'] if p['net']==net and p['reference']==reference})
    if expected_pin in pins:
        return expected_pin,dict(status='expected_pin',reference=reference,pin=expected_pin)
    if allow_remap and len(pins)==1:
        return pins[0],dict(status='unique_same_component_net_remap',reference=reference,
                           expected_pin=expected_pin,pin=pins[0])
    return expected_pin,dict(status='missing_or_ambiguous_endpoint',reference=reference,
                             expected_pin=expected_pin,candidate_pins=pins)


def analyze(data,path,args):
    results={}
    for name,endpoints in PAIR_MAP.items():
        pair={}
        for polarity in ('N','P'):
            net=f'{name}_{polarity}';graph=RouteGraph(data,net)
            origin_ref,origin_pin,dest_ref,dest_pins=endpoints[polarity]
            origin_pin,origin_resolution=resolve_endpoint(data,net,origin_ref,origin_pin)
            paths={};endpoint_resolution={'origin':origin_resolution,'targets':{}}
            for label,pin in dest_pins.items():
                pin,resolution=resolve_endpoint(data,net,dest_ref,pin,allow_remap=label=='MCU')
                endpoint_resolution['targets'][label]=resolution
                paths[label]=graph.path((origin_ref,origin_pin),(dest_ref,pin))
            vias=[v for v in data['vias'] if v['net']==net]
            pair[polarity]=dict(net=net,track_count=len(graph.rows),total_track_length_mm=sum(t['length_mm'] for t in graph.rows),
                               via_count=len(vias),via_layers=[v['layers'] for v in vias],
                               track_layers=sorted({t['layer'] for t in graph.rows}),
                               endpoint_paths=paths,has_multiple_target_pads=len(dest_pins)>1,
                               endpoint_resolution=endpoint_resolution,
                               zone_count=data['zone_counts'].get(net,0),
                               branch_junction_count=sum(sum(e[2]=='track' for e in links)>2 for node,links in graph.graph.items()),
                               uncoupled=uncoupled_estimate(graph.rows,[r for r in data['tracks'] if r['net']==f'{name}_{"P" if polarity=="N" else "N"}'],args.max_pair_gap,args.max_parallel_angle,args.sample_spacing))
        mismatches={}
        for label in pair['N']['endpoint_paths'].keys() & pair['P']['endpoint_paths'].keys():
            n,p=pair['N']['endpoint_paths'][label],pair['P']['endpoint_paths'][label]
            delta=n['length_mm']-p['length_mm'] if n['length_mm'] is not None and p['length_mm'] is not None else None
            mismatches[label]=dict(n_minus_p_path_mm=delta,absolute_path_mismatch_mm=abs(delta) if delta is not None else None,
                                   n_minus_p_route_plus_barrel_estimate_mm=n['route_plus_barrel_estimate_mm']-p['route_plus_barrel_estimate_mm'] if delta is not None else None)
        pair['endpoint_path_mismatches']=mismatches
        pair['total_net_length_difference_mm']=pair['N']['total_track_length_mm']-pair['P']['total_track_length_mm']
        pair['total_length_is_exact_electrical_skew']=False
        pair['status']='paths_found' if all(p['status']=='path_found' for pol in ('N','P') for p in pair[pol]['endpoint_paths'].values()) else 'incomplete_paths'
        results[name]=pair
    power={}
    allnets={r['net'] for r in data['tracks']+data['vias']}|set(data['zone_counts'])
    powernames={'+12V','+5V','+3V3'}|{f'CH{i}_12V' for i in range(1,5)}|{n for n in allnets if re.fullmatch(r'Net-\(J[5-8]-VBUS-PadA4\)',n)}
    for net in sorted(powernames):
        tracks=[r for r in data['tracks'] if r['net']==net];vias=[r for r in data['vias'] if r['net']==net]
        widths=sorted({r['width_mm'] for r in tracks})
        power[net]=dict(track_count=len(tracks),total_track_length_mm=sum(r['length_mm'] for r in tracks),
                        minimum_track_width_mm=min(widths) if widths else None,maximum_track_width_mm=max(widths) if widths else None,
                        distinct_track_widths_mm=widths,via_count=len(vias),
                        minimum_via_drill_mm=min((v['drill_mm'] for v in vias),default=None),
                        minimum_via_pad_mm=min((v['width_mm'] for v in vias),default=None),
                        track_layers=sorted({r['layer'] for r in tracks}),zone_count=data['zone_counts'].get(net,0))
    return dict(board=str(path),board_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                copper_layers=data['layers'],board_thickness_mm=data['thickness_mm'],usb_pairs=results,power_nets=power,
                limitations=[
                    'Total net length includes all branches; never interpret it as exact differential skew.',
                    'Path calculations use sampled centerlines (arcs <=0.001mm chord error) and native pad copper polygons.',
                    'Travel inside pad copper and zones is omitted; copper-overlap joins can introduce zero-length shortcuts.',
                    'Via barrel estimates assume evenly spaced layers, not a verified fabrication stackup.',
                    'Zones are counted but not traversed. A route through a zone may be reported disconnected.',
                    'Uncoupled segments are geometric screening flags, not impedance or timing sign-off.',
                    'Power widths exclude zone necks, thermal spokes, copper thickness and current sharing.'])


def main():
    if '--native-extract' in sys.argv:
        native_extract(Path(sys.argv[-1]));return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board',type=Path,default=Path('candidates/compact-v4-planes/pcbgolf.kicad_pcb'))
    parser.add_argument('--kicad-python',type=Path,default=Path('tools/kicad/bin/python.exe'))
    parser.add_argument('--output',type=Path,default=Path('reports/route-analysis.json'))
    parser.add_argument('--max-pair-gap',type=float,default=.5)
    parser.add_argument('--max-parallel-angle',type=float,default=15.)
    parser.add_argument('--sample-spacing',type=float,default=.25)
    args=parser.parse_args();path=args.board.resolve()
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    command=[str(args.kicad_python.resolve()),str(Path(__file__).resolve()),'--native-extract',str(path)]
    run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    if run.returncode:
        raise RuntimeError(run.stderr or run.stdout)
    data=json.loads(run.stdout);report=analyze(data,path,args)
    report['board_unchanged_during_analysis']=report['board_sha256']==before
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    brief={name:dict(status=p['status'],total_n_mm=round(p['N']['total_track_length_mm'],4),total_p_mm=round(p['P']['total_track_length_mm'],4),vias_n=p['N']['via_count'],vias_p=p['P']['via_count'],path_mismatches=p['endpoint_path_mismatches']) for name,p in report['usb_pairs'].items()}
    print(json.dumps(dict(board=str(path),usb=brief,power={n:{k:v for k,v in row.items() if k in ('track_count','minimum_track_width_mm','maximum_track_width_mm','via_count','zone_count')} for n,row in report['power_nets'].items()}),indent=2))
    return 0 if report['board_unchanged_during_analysis'] else 2


if __name__=='__main__':
    raise SystemExit(main())
