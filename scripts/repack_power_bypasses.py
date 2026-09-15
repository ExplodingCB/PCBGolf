"""Place supply bypasses beside the power switches and MCU SMPS loop."""
import json,math
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'candidates/power-base'
b=p.LoadBoard(str(OUT/'pcbgolf.kicad_pcb'));refs={f.GetReference():f for f in b.GetFootprints()}
def rect(f):
    v=[s.GetBoundingBox() for s in f.GraphicalItems() if s.GetLayer() in (p.F_CrtYd,p.B_CrtYd)]+[s.GetBoundingBox() for s in f.Pads()]
    return min(p.ToMM(t.GetX()) for t in v),min(p.ToMM(t.GetY()) for t in v),max(p.ToMM(t.GetRight()) for t in v),max(p.ToMM(t.GetBottom()) for t in v)
def hit(a,b,g=.051):return a[0]<b[2]+g and a[2]>b[0]-g and a[1]<b[3]+g and a[3]>b[1]-g
def place(r,x,y,a):
    f=refs[r]
    if f.GetLayer()!=p.B_Cu:f.Flip(f.GetPosition(),False)
    f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));f.SetOrientationDegrees(a)
fixed_moves={'C53':(30.15,7.75,0),'C52':(22.65,7.75,0),'C51':(15.15,7.75,0),'C50':(7.65,7.75,0),
             'C49':(27.35,8,0),'C48':(19.85,8,0),'C47':(12.35,8,0),'C46':(4.85,8,0),
             'C21':(2.65,25.4,270),'C23':(2.65,20.4,180),'C25':(.9,22.9,90)}
old={r:(p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y),f.GetOrientationDegrees(),f.GetLayer()) for r,f in refs.items()}
for r,xyz in fixed_moves.items():place(r,*xyz)
movable=set()
for r in fixed_moves:
    for s,f in refs.items():
        if r==s or f.GetLayer()!=p.B_Cu:continue
        if hit(rect(refs[r]),rect(f)):
            if s in fixed_moves:raise RuntimeError(('fixed collision',r,s))
            if s.startswith(('J','U','L')):raise RuntimeError(('critical collision',r,s))
            movable.add(s)
fixed={r:rect(f) for r,f in refs.items() if f.GetLayer()==p.B_Cu and r not in movable}
holes=[]
for f in refs.values():
    for q in f.Pads():
        if q.HasHole():
            t=q.GetBoundingBox();holes.append((p.ToMM(t.GetX())-.2,p.ToMM(t.GetY())-.2,p.ToMM(t.GetRight())+.2,p.ToMM(t.GetBottom())+.2))
for r in fixed_moves:
    if any(hit(rect(refs[r]),h,0) for h in holes):raise RuntimeError(('fixed hole collision',r))
reserved=[]
for j in range(5,9):
    q=refs['J'+str(j)].GetPosition();x,y=p.ToMM(q.x),p.ToMM(q.y)
    reserved.append((x-.65,y-.9,x+.65,y+.9))
for r in sorted(movable,key=lambda r:-(rect(refs[r])[2]-rect(refs[r])[0])*(rect(refs[r])[3]-rect(refs[r])[1])):
    f=refs[r];ox,oy,angle,_=old[r];best=None
    for a in [angle,angle+90]:
        place(r,0,0,a);local=rect(f)
        for iy in range(2,147):
            y=iy/4
            for ix in range(2,179):
                x=ix/4;t=(local[0]+x,local[1]+y,local[2]+x,local[3]+y)
                if t[0]<.35 or t[1]<.35 or t[2]>44.65 or t[3]>36.65:continue
                if any(hit(t,v) for v in fixed.values()) or any(hit(t,v,0) for v in holes+reserved):continue
                score=(x-ox)**2+(y-oy)**2
                if best is None or score<best[0]:best=(score,x,y,a,t)
    if best is None:raise RuntimeError('No site '+r)
    _,x,y,a,t=best;place(r,x,y,a);fixed[r]=t
changes={r:{'x_mm':p.ToMM(refs[r].GetPosition().x),'y_mm':p.ToMM(refs[r].GetPosition().y),'rotation_deg':refs[r].GetOrientationDegrees(),'side':'bottom'} for r in set(fixed_moves)|movable}
p.SaveBoard(str(OUT/'pcbgolf.kicad_pcb'),b)
plan=json.loads((OUT/'placement.json').read_text());plan['placements'].update(changes);plan['power_repacking']['bypass_moves']=changes
for file in [OUT/'placement.json',ROOT/'reports/placement-power-clusters.json']:file.write_text(json.dumps(plan,indent=2))
print(json.dumps(changes))
