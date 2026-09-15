"""Isolated BGA100 power placement; preserve all source candidates."""
import json,shutil,sys
from pathlib import Path
import pcbnew as p
from shapely.geometry import box,Point,LineString
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'candidates/bga100-power-base';SOURCE=ROOT/'candidates/bga100-base'
if (OUT/'placement.json').exists() and '--revise' not in sys.argv:raise RuntimeError('Refuse to overwrite completed power placement without --revise')
if not OUT.exists():shutil.copytree(SOURCE,OUT)
b=p.LoadBoard(str(OUT/'pcbgolf.kicad_pcb'));refs={f.GetReference():f for f in b.GetFootprints()}
plan=json.loads((ROOT/'reports/placement-power-clusters.json').read_text())
def place(r,x,y,a,side='bottom'):
    f=refs[r];target=p.B_Cu if side=='bottom' else p.F_Cu
    if f.GetLayer()!=target:f.Flip(f.GetPosition(),False)
    f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));f.SetOrientationDegrees(a)
for r,row in plan['placements'].items():
    if r!='U3':place(r,row['x_mm'],row['y_mm'],row['rotation_deg'],row['side'])
# Retain official KiCad1mm BGA courtyard for assembly spacing.
u=refs['U3'];ux,uy=p.ToMM(u.GetPosition().x),p.ToMM(u.GetPosition().y)
for s in u.GraphicalItems():
    if s.GetLayer() in (p.F_CrtYd,p.B_CrtYd):
        s.SetStart(p.VECTOR2I(p.FromMM(ux-5),p.FromMM(uy-5)));s.SetEnd(p.VECTOR2I(p.FromMM(ux+5),p.FromMM(uy+5)))
def rect(f):
    v=[s.GetBoundingBox() for s in f.GraphicalItems() if s.GetLayer() in (p.F_CrtYd,p.B_CrtYd)]+[s.GetBoundingBox() for s in f.Pads()]
    return min(p.ToMM(t.GetX()) for t in v),min(p.ToMM(t.GetY()) for t in v),max(p.ToMM(t.GetRight()) for t in v),max(p.ToMM(t.GetBottom()) for t in v)
def hit(a,b,g=.051):return a[0]<b[2]+g and a[2]>b[0]-g and a[1]<b[3]+g and a[3]>b[1]-g
fixed_moves={
 'U3':(10.5,19.9,0),
 'U1':(25,20.9,0),'L1':(25,17.4,90),'C8':(22.2,17.4,90),'C7':(22.2,19.6,0),'C1':(27.6,18.15,0),'C2':(27,20.2,90),'C4':(22.95,21.4,90),
 'R4':(26.5,23.3,0),'R3':(26.5,24.55,180),'C6':(24.25,24.55,0),'R1':(23,23.3,0),
 'U2':(32.5,20.9,0),'L2':(32.5,17.4,90),'C12':(29.7,17.4,90),'C11':(29.7,19.6,0),'C3':(35.5,18.15,0),'C5':(34.5,20.2,90),'C9':(30.45,21.4,90),
 'R10':(34,23.3,0),'R9':(34,24.55,180),'C10':(31.75,24.55,0),'R7':(30.5,23.3,0),'R8':(30.5,26.0,0),'C13':(29.7,14.4,90),
 'L4':(4.17,20.7,0),'C21':(1.62,20.7,180),'C19':(4.05,17.9,0),'C23':(4.05,19.25,0),'C25':(4.05,22.5,0),
 'C50':(7.0,9.5,270),'C51':(14.5,9.5,270),'C52':(22.0,9.5,270),'C53':(29.5,9.5,270),
 'C46':(7.0,11.65,0),'C47':(14.5,11.65,0),'C48':(22.0,11.65,0),'C49':(29.5,11.65,0),
 'C15':(16.3,22.2,90),'C16':(16.7,20.0,0),'C18':(11.0,25.7,0),'C24':(9.0,14.15,0),
}
old={r:(p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y),f.GetOrientationDegrees()) for r,f in refs.items()}
for r,xyz in fixed_moves.items():place(r,*xyz)
collisions=[]
for i,r in enumerate(fixed_moves):
    for s in list(fixed_moves)[i+1:]:
        if hit(rect(refs[r]),rect(refs[s])):collisions.append((r,s))
if collisions:raise RuntimeError(('fixed collisions',collisions))
movable=set()
for r in fixed_moves:
    for s,f in refs.items():
        if s==r or s in fixed_moves or f.GetLayer()!=p.B_Cu:continue
        if hit(rect(refs[r]),rect(f)):
            if s.startswith('J') or s in ['U13','U14','U15','U16']:raise RuntimeError(('connector/power switch collision',r,s))
            movable.add(s)
fixed={r:rect(f) for r,f in refs.items() if f.GetLayer()==p.B_Cu and r not in movable}
holes=[]
for f in refs.values():
    for q in f.Pads():
        if q.HasHole():
            t=q.GetBoundingBox();holes.append((p.ToMM(t.GetX())-.2,p.ToMM(t.GetY())-.2,p.ToMM(t.GetRight())+.2,p.ToMM(t.GetBottom())+.2))
usb=json.loads((ROOT/'reports/usb-paired-routes.json').read_text())
usbshape=unary_union([LineString([t['a'],t['b']]).buffer(t['width']/2+.202) for t in usb['tracks'] if t['layer']==p.B_Cu]+[Point(v['pos']).buffer(max(v['diameter']/2+.102,v['drill']/2+.202)) for v in usb['vias']])
reserved=[(6.0,15.3,15.0,24.5),(36.2,29.9,38.5,32.2)]
for j in range(5,9):
    q=refs['J'+str(j)].GetPosition();x,y=p.ToMM(q.x),p.ToMM(q.y);reserved.append((x-.65,y-.9,x+.65,y+.9))
for r in fixed_moves:
    if any(hit(rect(refs[r]),h,0) for h in holes):raise RuntimeError(('fixed hole collision',r))
    if box(*rect(refs[r])).intersects(usbshape):raise RuntimeError(('fixed USB collision',r))
for r in sorted(movable,key=lambda r:-(rect(refs[r])[2]-rect(refs[r])[0])*(rect(refs[r])[3]-rect(refs[r])[1])):
    f=refs[r];ox,oy,angle=old[r];best=None
    for a in [angle,angle+90]:
        place(r,0,0,a);local=rect(f)
        for iy in range(2,147):
            y=iy/4
            for ix in range(2,179):
                x=ix/4;t=(local[0]+x,local[1]+y,local[2]+x,local[3]+y)
                if t[0]<.35 or t[1]<.35 or t[2]>44.65 or t[3]>36.65:continue
                if any(hit(t,v) for v in fixed.values()) or any(hit(t,v,0) for v in holes+reserved) or box(*t).intersects(usbshape):continue
                cost=(x-ox)**2+(y-oy)**2
                if best is None or cost<best[0]:best=(cost,x,y,a,t)
    if best is None:raise RuntimeError('No site '+r)
    _,x,y,a,t=best;place(r,x,y,a);fixed[r]=t
plan['placements']={r:{'x_mm':p.ToMM(f.GetPosition().x),'y_mm':p.ToMM(f.GetPosition().y),'rotation_deg':f.GetOrientationDegrees(),'side':'bottom' if f.GetLayer()==p.B_Cu else 'top'} for r,f in refs.items()}
plan['bga_power_repacking']={'critical_refs':list(fixed_moves),'displaced_refs':sorted(movable),'top_changes':['C47 moved to bottom','C51 moved to bottom'],'escape_status':'BGA100 escape must be regenerated at new pose; no old escape tracks copied'}
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(OUT/'pcbgolf.kicad_pcb'),b)
(OUT/'placement.json').write_text(json.dumps(plan,indent=2));print(json.dumps(plan['bga_power_repacking']))
