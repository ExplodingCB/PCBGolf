"""Move small front parts out of thermal-via and hub USB exit regions."""
import json
from pathlib import Path
import pcbnew as pcb
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'candidates/power-base'
board=pcb.LoadBoard(str(OUT/'pcbgolf.kicad_pcb'));refs={f.GetReference():f for f in board.GetFootprints()}
def rect(fp):
    boxes=[s.GetBoundingBox() for s in fp.GraphicalItems() if s.GetLayer() in (pcb.F_CrtYd,pcb.B_CrtYd)]+[p.GetBoundingBox() for p in fp.Pads()]
    return (min(pcb.ToMM(b.GetX()) for b in boxes),min(pcb.ToMM(b.GetY()) for b in boxes),max(pcb.ToMM(b.GetRight()) for b in boxes),max(pcb.ToMM(b.GetBottom()) for b in boxes))
def hit(a,b,g=.21):return a[0]<b[2]+g and a[2]>b[0]-g and a[1]<b[3]+g and a[3]>b[1]-g
reserved=[(20.9,12.9,25.7,14.3)]
for u in range(13,17):
    f=refs[f'U{u}'];x,y=pcb.ToMM(f.GetPosition().x),pcb.ToMM(f.GetPosition().y)
    reserved.append((x+.13,y-.62,x+1.27,y+.62))
moving={'R26','C37'}|{r for r,f in refs.items() if f.GetLayer()==pcb.F_Cu and not r.startswith('J') and any(hit(rect(f),b,0) for b in reserved[1:])}
fixed={r:rect(f) for r,f in refs.items() if f.GetLayer()==pcb.F_Cu and r not in moving}
holes=[]
for f in refs.values():
    for p in f.Pads():
        if p.HasHole():
            b=p.GetBoundingBox();holes.append((pcb.ToMM(b.GetX())-.2,pcb.ToMM(b.GetY())-.2,pcb.ToMM(b.GetRight())+.2,pcb.ToMM(b.GetBottom())+.2))
changes=[]
for r in sorted(moving,key=lambda r:0 if r in ['R26','C37'] else 1):
    f=refs[r];old=(pcb.ToMM(f.GetPosition().x),pcb.ToMM(f.GetPosition().y));angle=f.GetOrientationDegrees()
    anchor={'R26':(29.,13.),'C37':(27.,16.)}.get(r,old)
    f.SetPosition(pcb.VECTOR2I(0,0));local=rect(f);choices=[]
    for iy in range(2,147):
        y=iy/4
        for ix in range(2,179):
            x=ix/4;b=(local[0]+x,local[1]+y,local[2]+x,local[3]+y)
            if b[0]<.4 or b[1]<.4 or b[2]>44.6 or b[3]>36.6:continue
            if any(hit(b,c) for c in fixed.values()) or any(hit(b,c,0) for c in reserved+holes):continue
            if r not in ['R26','C37'] and hit(b,(.3,.3,31.5,14.3),0):continue
            choices.append(((x-anchor[0])**2+(y-anchor[1])**2,x,y,b))
    if not choices:raise RuntimeError('No legal position for '+r)
    _,x,y,b=min(choices);f.SetPosition(pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y)));fixed[r]=b
    changes.append({'ref':r,'x_mm':x,'y_mm':y,'rotation_deg':angle,'side':'top','old':old})
pcb.SaveBoard(str(OUT/'pcbgolf.kicad_pcb'),board)
power=OUT/'power-routed.kicad_pcb'
if power.exists():
    b=pcb.LoadBoard(str(power));ps={f.GetReference():f for f in b.GetFootprints()}
    for row in changes:ps[row['ref']].SetPosition(pcb.VECTOR2I(pcb.FromMM(row['x_mm']),pcb.FromMM(row['y_mm'])))
    b.BuildConnectivity();pcb.ZONE_FILLER(b).Fill(b.Zones());pcb.SaveBoard(str(power),b)
plan=json.loads((OUT/'placement.json').read_text())
for row in changes:plan['placements'][row['ref']]={k:row[k] for k in ('x_mm','y_mm','rotation_deg','side')}
plan['power_repacking']['additional_front_moves']=changes
for p in [OUT/'placement.json',ROOT/'reports/placement-power-clusters.json']:p.write_text(json.dumps(plan,indent=2))
print(json.dumps(changes))
