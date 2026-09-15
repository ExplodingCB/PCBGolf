"""Move only two approved resistors out of the CH2 USB via pocket."""
import json
from pathlib import Path
import pcbnew as p
from shapely.geometry import box,Point,LineString
from shapely.ops import unary_union
from route_ground import track_shape,xy
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'candidates/power-base'
b=p.LoadBoard(str(OUT/'power-critical.kicad_pcb'));refs={f.GetReference():f for f in b.GetFootprints()}
def rect(f):
 v=[s.GetBoundingBox() for s in f.GraphicalItems() if s.GetLayer() in (p.F_CrtYd,p.B_CrtYd)]+[s.GetBoundingBox() for s in f.Pads()]
 return min(p.ToMM(t.GetX()) for t in v),min(p.ToMM(t.GetY()) for t in v),max(p.ToMM(t.GetRight()) for t in v),max(p.ToMM(t.GetBottom()) for t in v)
def hit(a,b,g=.051):return a[0]<b[2]+g and a[2]>b[0]-g and a[1]<b[3]+g and a[3]>b[1]-g
reserved=[(21.18,6.28,22.24,8.09),(20.9,12.9,25.7,14.3)]
for j in range(5,9):
 x,y=xy(refs['J'+str(j)].GetPosition());reserved +=[(x-.65,y-.9,x+.65,y+.9),(x+.5,y-.6,x+3.1,y+.6),(x-.55,y-1.65,x+.55,y-.6)]
holes=[]
for f in refs.values():
 for q in f.Pads():
  if q.HasHole():
   t=q.GetBoundingBox();holes.append((p.ToMM(t.GetX())-.2,p.ToMM(t.GetY())-.2,p.ToMM(t.GetRight())+.2,p.ToMM(t.GetBottom())+.2))
changes={}
for r in ['R19']:
 f=refs[r];old=xy(f.GetPosition());layer=f.GetLayer();a=f.GetOrientationDegrees()
 fixed=[rect(q) for s,q in refs.items() if s!=r and q.GetLayer()==layer]
 usb=json.loads((ROOT/'reports/usb-paired-routes.json').read_text())
 usb_shapes=[LineString([t['a'],t['b']]).buffer(t['width']/2+.21) for t in usb['tracks'] if t['layer']==layer]
 usb_shapes +=[Point(v['pos']).buffer(v['diameter']/2+.21) for v in usb['vias']]
 copper=unary_union([track_shape(t).buffer(.21) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) or t.GetLayer()==layer]+usb_shapes)
 f.SetPosition(p.VECTOR2I(0,0));local=rect(f);best=None
 for iy in range(2,147):
  for ix in range(2,179):
   x,y=ix/4,iy/4;t=(local[0]+x,local[1]+y,local[2]+x,local[3]+y)
   if t[0]<.35 or t[1]<.35 or t[2]>44.65 or t[3]>36.65:continue
   if any(hit(t,v) for v in fixed) or any(hit(t,v,0) for v in holes+reserved) or box(*t).intersects(copper):continue
   cost=(x-old[0])**2+(y-old[1])**2
   if best is None or cost<best[0]:best=(cost,x,y)
 if best is None:raise RuntimeError('No site '+r)
 _,x,y=best;f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));changes[r]={'x_mm':x,'y_mm':y,'rotation_deg':a,'side':'top' if layer==p.F_Cu else 'bottom'}
for name in ['pcbgolf','power-routed','power-critical']:
 board=p.LoadBoard(str(OUT/(name+'.kicad_pcb')));fs={f.GetReference():f for f in board.GetFootprints()}
 for r,row in changes.items():fs[r].SetPosition(p.VECTOR2I(p.FromMM(row['x_mm']),p.FromMM(row['y_mm'])))
 board.BuildConnectivity();p.ZONE_FILLER(board).Fill(board.Zones());p.SaveBoard(str(OUT/(name+'.kicad_pcb')),board)
plan=json.loads((OUT/'placement.json').read_text());plan['placements'].update(changes);plan['power_repacking']['ch2_usb_exception']=changes
for file in [OUT/'placement.json',ROOT/'reports/placement-power-clusters.json']:file.write_text(json.dumps(plan,indent=2))
print(json.dumps(changes))
