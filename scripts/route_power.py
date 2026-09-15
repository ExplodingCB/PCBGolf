"""Create isolated power pours, parallel layer transitions and thermal connections.

Run with portable KiCad Python. Filled/capped thermal vias are an explicit
fabrication requirement. Native DRC and copper-neck review remain mandatory.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import pcbnew as pcb
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
from shapely.prepared import prep
from route_ground import xy, copper_shape, hole_shape, track_shape, COPPER
from preconnect import octilinear_paths

MM=pcb.FromMM
def vec(p):return pcb.VECTOR2I(MM(p[0]),MM(p[1]))
def power_track_shape(track):
    if isinstance(track,pcb.PCB_VIA):return Point(xy(track.GetPosition())).buffer(pcb.ToMM(track.GetWidth(pcb.F_Cu))/2,quad_segs=24)
    return track_shape(track)

def add_zone(board,netname,layer,geometry,priority,label):
    if geometry.is_empty:return []
    parts=list(geometry.geoms) if geometry.geom_type=='MultiPolygon' else [geometry]
    zones=[]
    for shape in parts:
        if shape.area<.01:continue
        z=pcb.ZONE(board);z.SetLayer(layer);z.SetNet(board.FindNet(netname))
        z.SetLocalClearance(MM(.20));z.SetMinThickness(MM(.10))
        z.SetPadConnection(pcb.ZONE_CONNECTION_FULL);z.SetAssignedPriority(priority)
        poly=z.Outline();poly.NewOutline()
        for x,y in list(shape.exterior.coords)[:-1]:poly.Append(MM(x),MM(y))
        for ring in shape.interiors:
            hole=poly.NewHole(0)
            for x,y in list(ring.coords)[:-1]:poly.Append(MM(x),MM(y),0,hole)
        board.Add(z);zones.append(z)
    return zones

def run(board):
    refs={f.GetReference():f for f in board.GetFootprints()}
    pads=list(board.GetPads());report={'zones':[],'vias':[],'tracks':[],'unresolved':[]}
    usb_file=Path(__file__).resolve().parents[1]/'reports/usb-paired-routes.json'
    usb_reserved=json.loads(usb_file.read_text()) if usb_file.exists() else {'tracks':[],'vias':[]}
    keepouts={pcb.F_Cu:[],pcb.B_Cu:[]}
    for j in range(5,9):
        x,y=xy(refs[f'J{j}'].GetPosition())
        keepouts[pcb.F_Cu].append(box(x+.50,y-.60,x+3.10,y+.60))
        keepouts[pcb.B_Cu].append(box(x-.65,y-.90,x+.65,y+.90))
    keepouts={l:unary_union(s) for l,s in keepouts.items()}
    allowed=box(.61,.61,44.39,36.39)

    def zone(net,layer,shape,priority,label):
        shape=shape.intersection(box(.31,.31,44.69,36.69))
        if layer in keepouts:shape=shape.difference(keepouts[layer])
        added=add_zone(board,net,layer,shape,priority,label)
        report['zones'].append({'net':net,'layer':board.GetLayerName(layer),'label':label,'zone_count':len(added),'nominal_area_mm2':shape.area})

    def via(net,pos,diameter=.6,drill=.3,thermal=False):
        v=pcb.PCB_VIA(board);v.SetPosition(vec(pos));v.SetWidth(MM(diameter));v.SetDrill(MM(drill))
        v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNet(board.FindNet(net));v.SetLocked(True);board.Add(v)
        report['vias'].append({'net':net,'at_mm':pos,'copper_mm':diameter,'drill_mm':drill,'filled_and_capped_required':thermal})
        return v

    # Each channel gets both outer-layer output copper in its local connector cell.
    output_shapes={}
    for channel in range(1,5):
        ic=refs[f'U{channel+12}'];connector=refs[f'J{channel+4}']
        x,y=xy(connector.GetPosition());net=next(p.GetNetname() for p in connector.Pads() if p.GetNumber()=='A4')
        region=box(x-1.90,1.0,x+5.40,y+2.20);output_shapes[net]=region
        for layer in (pcb.F_Cu,pcb.B_Cu):zone(net,layer,region,10,f'channel_{channel}_local_output')
        inp=[copper_shape(p,ic.GetLayer()) for p in ic.Pads() if p.GetNetname()=='+12V']
        zone('+12V',ic.GetLayer(),unary_union(inp).convex_hull.buffer(.50,join_style=2),20,f'channel_{channel}_input_bus')
        ep=next(p for p in ic.Pads() if p.GetNumber()=='PAD')
        ep_shape=copper_shape(ep,ic.GetLayer())
        zone('GND',ic.GetLayer(),ep_shape.buffer(.035,join_style=2),30,f'channel_{channel}_thermal_pad')
        cx,cy=xy(ep.GetPosition())
        # Rotated package pad is 2.6 x 1.6 mm. Four filled/capped vias.
        for dx in (.45,.95):
            for dy in (-.30,.30):via('GND',(cx+dx,cy+dy),.40,.20,True)

    # Broad local copper on both faces for jack -> MOSFET drain -> TVS.
    raw='Net-(J1-PWR)'
    rawpads=[p for f in (refs['J1'],refs['Q1'],refs['D1']) for p in f.Pads() if p.GetNetname()==raw]
    for layer in (pcb.F_Cu,pcb.B_Cu):
        shapes=[copper_shape(p,p.GetParentFootprint().GetLayer()) for p in rawpads]
        if shapes:zone(raw,layer,unary_union(shapes).convex_hull.buffer(.8,join_style=2),10,'raw_input_copper')
    # Q1 output ties to the existing wide +12V inner plane through parallel vias.
    qout=[p for p in refs['Q1'].Pads() if p.GetNetname()=='+12V']
    zone('+12V',refs['Q1'].GetLayer(),unary_union([copper_shape(p,refs['Q1'].GetLayer()) for p in qout]).convex_hull.buffer(.6,join_style=2),20,'protected_input_source_bus')
    for net,names in [('+5V',['L2','C1','C2','C10','C11','C12','C13','U1']),('+3V3',['L1','C7','C8','C6'])]:
        shapes=[copper_shape(p,pcb.B_Cu) for ref in names for p in refs[ref].Pads() if p.GetNetname()==net]
        zone(net,pcb.B_Cu,unary_union(shapes).convex_hull.buffer(.45,join_style=2),16 if net=='+5V' else 17,'regulator_local_'+net)
    is_bga=any(p.GetNumber()=='D2' for p in refs['U3'].Pads())
    if is_bga:
        # Core distribution reaches all supply escape vias and local caps.
        # USB's small back-layer launch has a separate ground-reference patch.
        core=box(.31,14.4,17.2,26.2).difference(box(12.8,20.35,14.85,22.1))
        zone('VDDLDO',pcb.In2_Cu,core,40,'MCU_core_distribution')
        zone('GND',pcb.In2_Cu,box(12.8,20.35,14.85,22.1),50,'MCU_USB_launch_reference')
        front3=box(.31,14.4,15.2,26.2).union(box(14.8,15.45,26.1,16.3))
        zone('+3V3',pcb.F_Cu,front3,20,'MCU_io_and_SMPS_input_distribution')

    def obstacles(net,layer,width,diameter,drill):
        other={l:[] for l in COPPER};lands=[];holes=[];pth_via_blocks=[]
        for pad in pads:
            for l in COPPER:
                if not pad.IsOnLayer(l):continue
                shape=copper_shape(pad,l)
                if pad.GetNetname()!=net:other[l].append(shape)
                if l in (pcb.F_Cu,pcb.B_Cu) and pad.GetAttribute()==pcb.PAD_ATTRIB_SMD:lands.append(shape)
            if pad.HasHole():
                h=hole_shape(pad)
                holes.append(h.buffer(drill/2+.201))
                if pad.GetNetname()!=net:
                    hole_clear=.301 if pad.GetAttribute()==pcb.PAD_ATTRIB_PTH else .201
                    for l in COPPER:other[l].append(h.buffer(hole_clear))
                    if pad.GetAttribute()==pcb.PAD_ATTRIB_PTH:
                        pth_via_blocks.append(copper_shape(pad,pcb.F_Cu).buffer(drill/2+.301))
        for t in usb_reserved['tracks']:
            if t['net']!=net:other[t['layer']].append(LineString([t['a'],t['b']]).buffer(t['width']/2))
        for v in usb_reserved['vias']:
            if v['net']==net:continue
            copper=Point(v['pos']).buffer(v['diameter']/2);h=Point(v['pos']).buffer(v['drill']/2)
            for l in COPPER:other[l].extend([copper,h.buffer(.201)])
            holes.append(h.buffer(drill/2+.201))
        for t in board.GetTracks():
            active=COPPER if isinstance(t,pcb.PCB_VIA) else [t.GetLayer()]
            if t.GetNetname()!=net:
                for l in active:other[l].append(power_track_shape(t))
            if isinstance(t,pcb.PCB_VIA):
                h=Point(xy(t.GetPosition())).buffer(pcb.ToMM(t.GetDrill())/2)
                holes.append(h.buffer(drill/2+.201))
                if t.GetNetname()!=net:
                    for l in COPPER:other[l].append(h.buffer(.201))
        shapes={l:unary_union(s) for l,s in other.items()}
        lineblock=prep(shapes[layer].buffer(width/2+.102).union(keepouts[layer]))
        allother=unary_union(list(shapes.values()))
        viablock=allother.buffer(diameter/2+.102).union(allother.buffer(drill/2+.202))
        viablock=viablock.union(unary_union(lands).buffer(drill/2+.055)).union(unary_union(holes)).union(unary_union(pth_via_blocks))
        viablock=viablock.union(keepouts[pcb.F_Cu]).union(keepouts[pcb.B_Cu])
        return lineblock,prep(viablock)

    def fanout(pad,width=.30,diameter=.60,drill=.30,maxradius=2.8,region=None):
        net=pad.GetNetname();layer=pad.GetParentFootprint().GetLayer();start=xy(pad.GetPosition())
        lineblock,viablock=obstacles(net,layer,width,diameter,drill)
        choices=[]
        for radius in (.6,.8,1.0,1.2,1.5,1.8,2.2,2.6,2.8):
            if radius>maxradius:continue
            for degrees in range(0,360,45):
                angle=math.radians(degrees);end=(round(start[0]+radius*math.cos(angle),6),round(start[1]+radius*math.sin(angle),6))
                point=Point(end)
                if not allowed.contains(point) or viablock.intersects(point):continue
                if region is not None and not region.buffer(-diameter/2-.02).contains(point):continue
                for path in octilinear_paths(start,end):
                    if not lineblock.intersects(LineString(path)):
                        choices.append((sum(math.dist(a,b) for a,b in zip(path,path[1:])),path))
            if choices:break
        ref=pad.GetParentFootprint().GetReference()+'.'+pad.GetNumber()
        if not choices:
            report['unresolved'].append({'pad':ref,'net':net,'task':'parallel power fanout'});return False
        length,path=min(choices,key=lambda t:t[0])
        for a,b in zip(path,path[1:]):
            if math.dist(a,b)<.00001:continue
            t=pcb.PCB_TRACK(board);t.SetStart(vec(a));t.SetEnd(vec(b));t.SetWidth(MM(width));t.SetLayer(layer);t.SetNet(pad.GetNet());t.SetLocked(True);board.Add(t)
        via(net,path[-1],diameter,drill)
        report['tracks'].append({'pad':ref,'net':net,'layer':board.GetLayerName(layer),'width_mm':width,'length_mm':length,'path_mm':path,'role':'short package/connector escape; not a full-current trunk'})
        return True

    # Four separately fed connector VBUS contacts prevent a thin shared escape.
    for j in range(5,9):
        connector=refs[f'J{j}']
        for number in ('A4','A9','B4','B9'):
            p=next(p for p in connector.Pads() if p.GetNumber()==number)
            fanout(p,.30,.60,.30,2.8,output_shapes[p.GetNetname()])
    # Each 5-pin eFuse input bank receives multiple parallel through transitions.
    for u in range(13,17):
        ic=refs[f'U{u}']
        for number in ('4','5','6','7','8'):
            op=next(p for p in ic.Pads() if p.GetNumber()==number)
            fanout(op,.25,.60,.30,2.2,output_shapes[op.GetNetname()])
        for number in ('9','10','11','12','13'):
            fanout(next(p for p in ic.Pads() if p.GetNumber()==number),.20,.60,.30,2.2)
    for p in qout:fanout(p,.40,.70,.40,2.6)
    for number in ('5','6','7','8','9'):
        fanout(next(p for p in refs['Q1'].Pads() if p.GetNumber()==number),.50,.70,.40,2.6)
    # Multiple input transitions are placed from each large jack power land.
    for p in [p for p in refs['J1'].Pads() if p.GetNumber()=='PWR1']:
        for _ in range(3):fanout(p,.8,.70,.40,2.8)
    # Regulator power terminals are protected against a narrow generic route.
    for ref,number in [('U1','3'),('U2','3')]:fanout(next(p for p in refs[ref].Pads() if p.GetNumber()==number),.45,.60,.30,2.2)
    for ref in [f'C{i}' for i in range(46,54)]+['C1','C2','C3','C5','C7','C8','C11','C12','C13']:
        for p in refs[ref].Pads():
            if p.GetNetname() in ['+12V','+5V','+3V3','GND']:fanout(p,.35,.60,.30,2.2)
    for ref in ['U1','U2']:fanout(next(p for p in refs[ref].Pads() if p.GetNumber()=='1'),.4,.60,.30,2.2)
    if is_bga:
        for ref in ['C19','C23','C21','C15','C16','C18','C24']:
            for p in refs[ref].Pads():
                if p.GetNetname() in ['+3V3','VDDLDO','GND']:fanout(p,.3,.50,.25,2.2)
        for number in ['E1','C2']:
            fanout(next(p for p in refs['U3'].Pads() if p.GetNumber()==number),.20,.45,.20,1.2)
        # Both external regulator output rails need outer/front access as well.
        for ref in ['L1','L2']:
            fanout(next(p for p in refs[ref].Pads() if p.GetNumber()=='2'),.45,.60,.30,2.2)

    def connect(a,b,width,paths=None):
        p=next(p for p in refs[a[0]].Pads() if p.GetNumber()==a[1]);q=next(p for p in refs[b[0]].Pads() if p.GetNumber()==b[1])
        assert p.GetNetname()==q.GetNetname(),(a,b)
        layer=p.GetParentFootprint().GetLayer();assert q.IsOnLayer(layer)
        start,end=xy(p.GetPosition()),xy(q.GetPosition())
        blocked,_=obstacles(p.GetNetname(),layer,width,.60,.30)
        paths=list(paths or [])+list(octilinear_paths(start,end))
        valid=[path for path in paths if not blocked.intersects(LineString(path))]
        if not valid:
            report['unresolved'].append({'pads':[a,b],'net':p.GetNetname(),'task':'local regulator loop'});return
        path=min(valid,key=lambda path:sum(math.dist(x,y) for x,y in zip(path,path[1:])))
        for x,y in zip(path,path[1:]):
            if math.dist(x,y)<.00001:continue
            t=pcb.PCB_TRACK(board);t.SetStart(vec(x));t.SetEnd(vec(y));t.SetWidth(MM(width));t.SetLayer(layer);t.SetNet(p.GetNet());t.SetLocked(True);board.Add(t)
        report['tracks'].append({'pads':[a,b],'net':p.GetNetname(),'layer':board.GetLayerName(layer),'width_mm':width,'path_mm':path,'role':'local regulator loop'})
    for u,l,c in [('U1','L1','C4'),('U2','L2','C9')]:
        connect((u,'2'),(l,'1'),.45)
        connect((u,'6'),(c,'1'),.127)
        up={p.GetNumber():xy(p.GetPosition()) for p in refs[u].Pads()}
        cp={p.GetNumber():xy(p.GetPosition()) for p in refs[c].Pads()}
        midx=(up['5'][0]+up['6'][0])/2
        route=[up['2'],(midx,up['2'][1]),(midx,cp['2'][1]),cp['2']]
        connect((u,'2'),(c,'2'),.127,[route])

    board.BuildConnectivity();pcb.ZONE_FILLER(board).Fill(board.Zones())
    report.update(status='partial power copper candidate; current/thermal qualification incomplete',
                  source_limits={'jack_total_A':5,'efuse_nominal_trip_A':89/28,'inductor_saturation_A':1.8,'inductor_thermal_A':2.0},
                  copper_basis={'outer_copper_um':35,'inner_copper_um':17.5,'screen_delta_T_C':10,'input_drawn_trunk_screen_mm':3.5,'channel_double_load_drawn_trunk_screen_mm':5.5},
                  fabrication=['Four epoxy-filled-and-copper-capped 0.20/0.40 mm thermal vias per eFuse exposed pad. Select the explicitly available paid four-layer POFV process; see reports/pofv-four-layer.md.','All other added vias are ordinary dogbones outside solderable lands.'],
                  limitations=['Local pours can contain narrower clearances around pads and other nets. Minimum conducting neck width and plane connectivity must be measured after final routing.','Short parallel connector and package escapes do not by themselves establish a thermal rating.','Regulator switch/boot/feedback loops and decoupling remain for the next routing pass.','Native DRC, connected-current-path audit and hardware load/temperature validation are required.'])
    return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('board',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--report',type=Path,required=True);args=ap.parse_args()
    if args.board.resolve()==args.out.resolve():raise ValueError('Use a separate output file')
    digest=hashlib.sha256(args.board.read_bytes()).hexdigest();board=pcb.LoadBoard(str(args.board));report=run(board)
    pcb.SaveBoard(str(args.out),board);assert hashlib.sha256(args.board.read_bytes()).hexdigest()==digest
    report['source_board_sha256']=digest;report['source_unmodified']=True
    args.report.write_text(json.dumps(report,indent=2));print(json.dumps({'zones':len(report['zones']),'vias':len(report['vias']),'short_escapes':len(report['tracks']),'unresolved':report['unresolved']}))

if __name__=='__main__':main()
