"""Conservative two-layer maze routing of the shared connector CAN buses.

Run with the workspace venv. Native KiCad exports and applies exact geometry.
This experiment preserves existing copper and never claims completed routing.
"""
import argparse
import hashlib
import heapq
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STEP = .05
WIDTH = .127
VIA = .45
DRILL = .20
NX, NY = 901, 741
DIRS = [(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)]


def native_apply(source, planpath, output):
    import pcbnew as pcb
    board = pcb.LoadBoard(str(source))
    plan = json.loads(planpath.read_text())
    for row in plan['tracks']:
        t = pcb.PCB_TRACK(board)
        t.SetStart(pcb.VECTOR2I(*(pcb.FromMM(v) for v in row['a'])))
        t.SetEnd(pcb.VECTOR2I(*(pcb.FromMM(v) for v in row['b'])))
        t.SetLayer(row['layer']); t.SetWidth(pcb.FromMM(row['width']))
        t.SetNet(board.FindNet(row['net'])); t.SetLocked(True); board.Add(t)
    for row in plan['vias']:
        v = pcb.PCB_VIA(board)
        v.SetPosition(pcb.VECTOR2I(*(pcb.FromMM(x) for x in row['pos'])))
        v.SetWidth(pcb.FromMM(VIA)); v.SetDrill(pcb.FromMM(DRILL))
        v.SetViaType(pcb.VIATYPE_THROUGH); v.SetLayerPair(pcb.F_Cu,pcb.B_Cu)
        v.SetNet(board.FindNet(row['net'])); v.SetLocked(True); board.Add(v)
    board.BuildConnectivity(); pcb.ZONE_FILLER(board).Fill(board.Zones())
    pcb.SaveBoard(str(output),board)


def maze(start, target, blocked, via_blocked, allow_vias=True, limit=450000):
    """A* with eight in-plane directions and explicitly checked through vias."""
    import numpy as np
    end = (round(target[0]/STEP),round(target[1]/STEP),target[2] if len(target)>2 else 0)
    begin = (round(start[0]/STEP),round(start[1]/STEP),start[2] if len(start)>2 else 0)
    def heuristic(n):
        dx,dy=abs(n[0]-end[0]),abs(n[1]-end[1])
        return max(dx,dy)+(math.sqrt(2)-1)*min(dx,dy)+(80 if n[2]!=end[2] else 0)
    if blocked[begin[2],begin[1],begin[0]] or blocked[end[2],end[1],end[0]]:
        return None,dict(reason='blocked endpoint')
    layer_count=len(blocked)
    costs=np.full((layer_count,NY,NX),np.inf,dtype=np.float32)
    costs[begin[2],begin[1],begin[0]]=0
    prev={}; q=[(heuristic(begin),0.,begin)]; expanded=0
    while q:
        _,cost,node=heapq.heappop(q)
        x,y,layer=node
        if cost>float(costs[layer,y,x])+1e-3:continue
        if node==end:
            path=[end]
            while path[-1]!=begin:path.append(prev[path[-1]])
            return list(reversed(path)),dict(expanded=expanded,cost=cost)
        expanded+=1
        if expanded>limit:return None,dict(reason='search limit',expanded=expanded)
        neighbors=[]
        for dx,dy in DIRS:
            xx,yy=x+dx,y+dy
            if xx<0 or yy<0 or xx>=NX or yy>=NY or blocked[layer,yy,xx]:continue
            if dx and dy and (blocked[layer,y,xx] or blocked[layer,yy,x]):continue
            neighbors.append(((xx,yy,layer),math.hypot(dx,dy)))
        if allow_vias and not via_blocked[y,x]:
            neighbors +=[((x,y,other),80.) for other in range(layer_count) if other!=layer and not blocked[other,y,x]]
        for nxt,weight in neighbors:
            xx,yy,ll=nxt;new=cost+weight
            if new+1e-3<float(costs[ll,yy,xx]):
                costs[ll,yy,xx]=new;prev[nxt]=node
                heapq.heappush(q,(new+heuristic(nxt),new,nxt))
    return None,dict(reason='no path',expanded=expanded)


def plan_routes(geometry,fanout=None,inner_signal=False):
    import numpy as np
    from shapely import contains_xy
    from shapely.geometry import Polygon,LineString,Point,box
    from shapely.ops import unary_union
    pads=geometry['pads']; base=geometry['tracks']; layers=[geometry['layers']['F.Cu'],geometry['layers']['B.Cu']]
    if inner_signal:layers.append(geometry['layers']['In2.Cu'])
    tracks=[];vias=[];results=[]
    def poly(points):return Polygon(points).buffer(0)
    obstacles=[];holes=[];smd=[];pth_copper=[]
    for pad in pads:
        for layer in layers:
            for polygon in pad['polygons'].get(str(layer),[]):
                shape=poly(polygon)
                obstacles.append((pad['net'],layer,shape))
                if not pad['hole']:smd.append(shape)
                elif pad['net']:pth_copper.append((pad['net'],shape))
        for h in pad['hole']:holes.append((pad['net'],poly(h),.301 if pad['net'] else .201))
    for t in base:
        if t['type']=='via':
            for layer in layers:obstacles.append((t['net'],layer,Point(t['pos']).buffer(t['width']/2)))
            holes.append((t['net'],Point(t['pos']).buffer(t['drill']/2),.201))
        else:obstacles.append((t['net'],t['layer'],LineString([t['a'],t['b']]).buffer(t['width']/2)))
    xs=np.arange(NX)*STEP;ys=np.arange(NY)*STEP
    def raster(shape):return contains_xy(shape,xs[None,:],ys[:,None])
    border=box(-1,-1,46,38).difference(box(.301+WIDTH/2,.301+WIDTH/2,44.699-WIDTH/2,36.699-WIDTH/2))
    via_border=box(-1,-1,46,38).difference(box(.301+VIA/2,.301+VIA/2,44.699-VIA/2,36.699-VIA/2))
    # Ordinary vias remain outside solderable lands, so this stage adds no new
    # filled/capped assembly requirements. Hole spacing remains explicit.
    via_lands=unary_union(smd).buffer(DRILL/2+.011)
    for net in ['CAN0_H','CAN0_L','CAN3_H','CAN3_L','CAN1_H','CAN1_L','CAN2_H','CAN2_L']:
        current=obstacles+[(t['net'],t['layer'],LineString([t['a'],t['b']]).buffer(t['width']/2)) for t in tracks]
        current +=[(v['net'],l,Point(v['pos']).buffer(VIA/2)) for v in vias for l in layers]
        current_holes=holes+[(v['net'],Point(v['pos']).buffer(DRILL/2),.201) for v in vias]
        blocked=[]
        for layer in layers:
            shapes=[s.buffer(.101+WIDTH/2) for n,l,s in current if n!=net and l==layer]
            shapes +=[s.buffer(c+WIDTH/2) for n,s,c in current_holes if n!=net]
            blocked.append(raster(unary_union(shapes+[border])))
        blocked=np.array(blocked)
        vshapes=[s.buffer(.101+VIA/2) for n,l,s in current if n!=net]
        vshapes +=[s.buffer(c+VIA/2) for n,s,c in current_holes if n!=net]
        vshapes +=[s.buffer(DRILL/2+(.451 if c>.25 else .201)) for n,s,c in current_holes]
        # KiCad evaluates the PTH-pair rule symmetrically: it also requires
        # .30mm from the VIA drill to PTH pad copper, not just vice versa.
        vshapes +=[s.buffer(DRILL/2+.301) for n,s in pth_copper if n!=net]
        # Via drill to foreign copper must satisfy .20mm, including every
        # through pad; .45/.20 copper geometry is already more conservative.
        via_blocked=raster(unary_union(vshapes+[via_lands,via_border]))
        for via in (t for t in base if t['type']=='via' and t['net']==net):
            x,y=[round(v/STEP) for v in via['pos']]
            if not blocked[0,y,x] and not blocked[1,y,x]:via_blocked[y,x]=False
        pp=[p for p in pads if p['net']==net and p['ref'] in ('J8','J7','J6','J5','J4')]
        if fanout:
            new=[]
            for pad in pp:
                escaped=fanout.get(pad['ref']+'.'+pad['pad'])
                pos=escaped['via_mm']+[1] if escaped else pad['pos']+([1] if pad['ref']=='J4' else [0])
                new.append(dict(pad,pos=pos))
            pp=new
        pp.sort(key=lambda p:p['pos'][0])
        for a,b in zip(pp,pp[1:]):
            begun=time.monotonic()
            path,status=maze(a['pos'],b['pos'],blocked,via_blocked,False,70000)
            if path is None:path,status=maze(a['pos'],b['pos'],blocked,via_blocked,True)
            record=dict(net=net,source=a['ref']+'.'+a['pad'],target=b['ref']+'.'+b['pad'],seconds=time.monotonic()-begun,**status)
            if path is None:
                record['status']='unrouted';results.append(record);print(json.dumps(record),flush=True);continue
            record['status']='routed';results.append(record)
            segments=[];run=[path[0]]
            for prev,nxt in zip(path,path[1:]):
                if prev[2]!=nxt[2]:
                    segments.append(run);run=[nxt]
                    pos=[nxt[0]*STEP,nxt[1]*STEP]
                    old=[v for v in base if v['type']=='via' and v['net']==net]
                    if not any(v['net']==net and math.dist(v['pos'],pos)<.04 for v in vias+old):vias.append(dict(net=net,pos=pos,diameter=VIA,drill=DRILL))
                else:run.append(nxt)
            segments.append(run)
            for run in segments:
                if len(run)<2:continue
                simple=[run[0]]
                for k in range(1,len(run)-1):
                    p,q,r=run[k-1:k+2]
                    if (q[0]-p[0],q[1]-p[1])!=(r[0]-q[0],r[1]-q[1]):simple.append(q)
                simple.append(run[-1])
                for p,q in zip(simple,simple[1:]):tracks.append(dict(net=net,a=[p[0]*STEP,p[1]*STEP],b=[q[0]*STEP,q[1]*STEP],width=WIDTH,layer=layers[p[2]]))
            for v in (v for v in vias if v['net']==net):
                via_blocked |= raster(Point(v['pos']).buffer(DRILL+.201))
                # Reusing the same physical via is permitted.
                via_blocked[round(v['pos'][1]/STEP),round(v['pos'][0]/STEP)]=False
            print(json.dumps(record),flush=True)
    return dict(tracks=tracks,vias=vias,results=results,grid_mm=STEP,inner_signal_experiment=inner_signal,
                limitations=['Only connector-to-connector CAN buses are targeted.',
                             'Native DRC is required after application and merging.',
                             'Power zone necks and connectivity require rechecking after these routes; In2 may cut the +12V pour.'])


def main():
    if '--native-apply' in sys.argv:
        native_apply(*map(Path,sys.argv[-3:]));return
    ap=argparse.ArgumentParser();ap.add_argument('--board',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--fanout',type=Path)
    ap.add_argument('--inner-signal',action='store_true')
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    source=args.board.resolve();before=hashlib.sha256(source.read_bytes()).hexdigest()
    geometry=args.out/'geometry.json'
    subprocess.run([str(ROOT/'tools/kicad/bin/python.exe'),str(ROOT/'scripts/usb_geometry.py'),str(source),str(geometry)],check=True,timeout=120)
    fanout={r['ref']:r for r in json.loads(args.fanout.read_text())['results'] if r['status']=='escaped'} if args.fanout else None
    plan=plan_routes(json.loads(geometry.read_text()),fanout,args.inner_signal);plan['source_sha256']=before;plan['source_board']=str(source)
    planpath=args.out/'can-plan.json';planpath.write_text(json.dumps(plan,indent=2))
    if hashlib.sha256(source.read_bytes()).hexdigest()!=before:raise RuntimeError('Source changed while planning')
    output=args.out/'pcbgolf.kicad_pcb'
    subprocess.run([str(ROOT/'tools/kicad/bin/python.exe'),str(Path(__file__).resolve()),'--native-apply',str(source),str(planpath.resolve()),str(output.resolve())],check=True,timeout=120)
    for suffix in ['.kicad_pro','.kicad_dru']:
        path=source.with_suffix(suffix)
        if path.exists() and path.resolve()!=output.with_suffix(suffix).resolve():
            shutil.copy2(path,output.with_suffix(suffix))
    print(json.dumps(dict(board=str(output),tracks=len(plan['tracks']),vias=len(plan['vias']),routed=sum(r['status']=='routed' for r in plan['results']))))


if __name__=='__main__':main()
