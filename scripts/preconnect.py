"""Join nearby same-net pads with collision-screened, zero-via straight traces.

Native KiCad DRC remains authoritative. This is a routing bootstrap, not a
substitute for current sizing, reference-plane or differential-pair review.
"""
import math
import pcbnew as pcb

def octilinear_paths(a,b):
    """The DSN router requires orthogonal/45-degree segments for stable cleanup."""
    dx,dy=b[0]-a[0],b[1]-a[1]
    if abs(dx)<0.00001 or abs(dy)<0.00001 or abs(abs(dx)-abs(dy))<0.00001:
        return [[a,b]]
    diagonal=min(abs(dx),abs(dy))
    step=(math.copysign(diagonal,dx),math.copysign(diagonal,dy))
    return [[a,(round(a[0]+step[0],6),round(a[1]+step[1],6)),b],
            [a,(round(b[0]-step[0],6),round(b[1]-step[1],6)),b]]

def intersects_box(a,b,box):
    t0,t1=0.,1.
    dx,dy=b[0]-a[0],b[1]-a[1]
    for p,q in [(-dx,a[0]-box[0]),(dx,box[2]-a[0]),
                (-dy,a[1]-box[1]),(dy,box[3]-a[1])]:
        if abs(p)<1e-12:
            if q<0:return False
        else:
            r=q/p
            if p<0:t0=max(t0,r)
            else:t1=min(t1,r)
            if t0>t1:return False
    return True

def point_distance(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    n=dx*dx+dy*dy
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/n)) if n else 0
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)

def segment_distance(a,b,c,d):
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:return 0
    return min(point_distance(a,c,d),point_distance(b,c,d),point_distance(c,a,b),point_distance(d,a,b))

def connect_nearby(board,max_length=1.75):
    pads=list(board.GetPads())
    positions=[(pcb.ToMM(p.GetPosition().x),pcb.ToMM(p.GetPosition().y)) for p in pads]
    groups={}
    for i,pad in enumerate(pads):
        net=pad.GetNetname()
        if pad.GetNetCode()>0 and not net.startswith('unconnected-'):
            groups.setdefault(net,[]).append(i)
    added=[]
    for layer in (pcb.F_Cu,pcb.B_Cu):
        obstacles=[]
        for i,pad in enumerate(pads):
            if not pad.IsOnLayer(layer):continue
            box=pad.GetBoundingBox()
            bounds=[pcb.ToMM(box.GetX()),pcb.ToMM(box.GetY()),pcb.ToMM(box.GetRight()),pcb.ToMM(box.GetBottom())]
            obstacles.append((i,pad.GetNetname(),bounds))
        candidates=[]
        parent=list(range(len(pads)))
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for net,indices in groups.items():
            active=[i for i in indices if pads[i].IsOnLayer(layer)]
            for k,i in enumerate(active):
                for j in active[k+1:]:
                    length=math.dist(positions[i],positions[j])
                    if length<=max_length:candidates.append((length,i,j,net))
        for length,i,j,net in sorted(candidates):
            if find(i)==find(j):continue
            if length<0.01:parent[find(i)]=find(j);continue
            a,b=positions[i],positions[j]
            width=0.25 if net=='GND' or net.startswith('+') or net.endswith('_12V') else 0.127
            margin=width/2+0.101
            accepted=None
            for path in octilinear_paths(a,b):
                blocked=False
                for start,end in zip(path,path[1:]):
                    for k,other,box in obstacles:
                        if other==net:continue
                        if intersects_box(start,end,[box[0]-margin,box[1]-margin,box[2]+margin,box[3]+margin]):
                            blocked=True;break
                    if blocked:break
                    for old in added:
                        if old['layer']!=layer or old['net']==net:continue
                        if segment_distance(start,end,old['a'],old['b'])<(width+old['width'])/2+0.101:
                            blocked=True;break
                    if blocked:break
                if not blocked:
                    accepted=path;break
            if accepted is None:continue
            for start,end in zip(accepted,accepted[1:]):
                track=pcb.PCB_TRACK(board)
                track.SetStart(pcb.VECTOR2I(pcb.FromMM(start[0]),pcb.FromMM(start[1])))
                track.SetEnd(pcb.VECTOR2I(pcb.FromMM(end[0]),pcb.FromMM(end[1])))
                track.SetWidth(pcb.FromMM(width));track.SetLayer(layer);track.SetNet(pads[i].GetNet())
                board.Add(track)
                added.append(dict(a=start,b=end,net=net,layer=layer,width=width,length=math.dist(start,end)))
            parent[find(i)]=find(j)
    return added
