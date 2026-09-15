"""Checked same-side local switching paths. Refuse long feedback reroutes."""
import argparse,heapq,json,math
from pathlib import Path
import pcbnew as pcb
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from shapely.prepared import prep
from route_ground import xy,copper_shape,hole_shape,track_shape,COPPER
from preconnect import octilinear_paths
MM=pcb.FromMM
def vec(v):return pcb.VECTOR2I(MM(v[0]),MM(v[1]))
def run(b, links=None, endpoints=None):
    refs={f.GetReference():f for f in b.GetFootprints()};report={'routed':[],'unresolved':[]}
    is_bga=any(q.GetNumber()=='D2' for q in refs['U3'].Pads())
    cx,cy=xy(refs['U3'].GetPosition())
    ends={('U3','D2'):(cx-4.4,cy+.8),('U3','E2'):(cx-4.4,cy)} if is_bga else {}
    if endpoints:ends.update(endpoints)
    def pad(ref,n):return next(q for q in refs[ref].Pads() if q.GetNumber()==n)
    def link(a,z,width,margin=2.0,maxlength=12):
        p,q=pad(*a),pad(*z);net=p.GetNetname();layer=p.GetParentFootprint().GetLayer()
        assert q.GetNetname()==net and q.IsOnLayer(layer)
        start,end=ends.get(a,xy(p.GetPosition())),ends.get(z,xy(q.GetPosition()));obstacles=[]
        if math.dist(start,end)>maxlength:
            report['unresolved'].append({'pads':[a,z],'net':net,'reason':'local placement needed','straight_distance_mm':math.dist(start,end)});return
        for t in b.GetPads():
            if t.GetNetname()==net:continue
            if t.IsOnLayer(layer):obstacles.append(copper_shape(t,layer).buffer(width/2+.102))
            if t.HasHole():obstacles.append(hole_shape(t).buffer(width/2+(.302 if t.GetAttribute()==pcb.PAD_ATTRIB_PTH else .202)))
        for t in b.GetTracks():
            if t.GetNetname()==net:continue
            if isinstance(t,pcb.PCB_VIA):
                obstacles.append(track_shape(t).buffer(width/2+.102));obstacles.append(Point(xy(t.GetPosition())).buffer(pcb.ToMM(t.GetDrill())/2+width/2+.202))
            elif t.GetLayer()==layer:obstacles.append(track_shape(t).buffer(width/2+.102))
        shape=unary_union(obstacles);blocked=prep(shape)
        allowed=box(max(.31,min(start[0],end[0])-margin),max(.31,min(start[1],end[1])-margin),min(44.69,max(start[0],end[0])+margin),min(36.69,max(start[1],end[1])+margin))
        def legal(path):return allowed.covers(LineString(path)) and not blocked.intersects(LineString(path))
        paths=[v for v in octilinear_paths(start,end) if legal(v)]
        route=min(paths,key=lambda v:sum(math.dist(s,e) for s,e in zip(v,v[1:]))) if paths else None
        if route is None:
            step=.05;origin=start;seen={};came={};best={(0,0):0};queue=[(math.dist(start,end),0,(0,0))];terminal=None
            def point(k):return origin[0]+step*k[0],origin[1]+step*k[1]
            while queue and len(seen)<60000:
                _,cost,k=heapq.heappop(queue)
                if k in seen:continue
                seen[k]=cost;s=point(k)
                if math.dist(s,end)<.25:
                    final=[v for v in octilinear_paths(s,end) if legal(v)]
                    if final:terminal=(k,min(final,key=lambda v:sum(math.dist(x,y) for x,y in zip(v,v[1:]))));break
                for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)]:
                    kk=(k[0]+dx,k[1]+dy);e=point(kk);cc=cost+step*math.hypot(dx,dy)
                    if cc>maxlength or cc>=best.get(kk,1e9) or not legal([s,e]):continue
                    best[kk]=cc;came[kk]=k;heapq.heappush(queue,(cc+math.dist(e,end),cc,kk))
            if terminal:
                k,tail=terminal;route=[]
                while k!=(0,0):route.append(point(k));k=came[k]
                route=[start]+route[::-1]+tail[1:]
                simple=[route[0]]
                for i in range(1,len(route)-1):
                    a0,a1,a2=simple[-1],route[i],route[i+1]
                    if abs((a1[0]-a0[0])*(a2[1]-a1[1])-(a1[1]-a0[1])*(a2[0]-a1[0]))>1e-8:simple.append(a1)
                route=simple+[route[-1]]
        if route is None:
            report['unresolved'].append({'pads':[a,z],'net':net,'reason':'no short same-side clearance-safe path','width_mm':width});return
        for s,e in zip(route,route[1:]):
            if math.dist(s,e)<.000001:continue
            t=pcb.PCB_TRACK(b);t.SetStart(vec(s));t.SetEnd(vec(e));t.SetWidth(MM(width));t.SetLayer(layer);t.SetNet(p.GetNet());t.SetLocked(True);b.Add(t)
        report['routed'].append({'pads':[a,z],'net':net,'width_mm':width,'length_mm':sum(math.dist(s,e) for s,e in zip(route,route[1:])),'path_mm':route})
    for a,z,w,maxlen in (links if links is not None else [
        (('U3','D2' if is_bga else '15'),('L4','2'),.30,6),(('L4','2'),('C25','1'),.20,5),
        (('L4','1'),('U3','E2' if is_bga else '17'),.25,8),
        (('U3','E1' if is_bga else '16'),('C23','1'),.30,6),
        (('U1','2'),('C4','2'),.127,8),(('U2','2'),('L2','1'),.45,8),(('U2','2'),('C9','2'),.127,8),
        (('U1','3'),('C1','1'),.5,8),(('U1','3'),('C2','1'),.35,8),
        (('U2','3'),('C3','1'),.5,8),(('U2','3'),('C5','1'),.35,8),
        (('U1','4'),('R3','1'),.127,4),(('U1','4'),('R4','2'),.127,4),
        (('U2','4'),('R9','1'),.127,4),(('U2','4'),('R10','1'),.127,4),
        (('L1','2'),('C8','1'),.6,7),(('L2','2'),('C12','1'),.6,7),
        (('U1','4'),('C6','1'),.127,6),(('U2','4'),('C10','1'),.127,6),
        (('L4','1'),('C21','1'),.5,5),(('L4','1'),('C15','1'),.5,5),
    ]):link(a,z,w,maxlength=maxlen)
    b.BuildConnectivity();pcb.ZONE_FILLER(b).Fill(b.Zones());return report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('board');ap.add_argument('--out',required=True);ap.add_argument('--report',type=Path,required=True);a=ap.parse_args()
    if Path(a.board).resolve()==Path(a.out).resolve():raise ValueError('separate output required')
    b=pcb.LoadBoard(a.board);r=run(b);pcb.SaveBoard(a.out,b);a.report.write_text(json.dumps(r,indent=2));print(json.dumps(r))
