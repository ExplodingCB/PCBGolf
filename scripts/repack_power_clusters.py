"""Repack displaced small parts and eFuse sense resistors; preserve USB bridge strips."""
import json
import math
from pathlib import Path
import pcbnew as pcb

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'candidates/power-base'
board=pcb.LoadBoard(str(OUT/'pcbgolf.kicad_pcb'))
refs={f.GetReference():f for f in board.GetFootprints()}
def mm(v):return pcb.ToMM(v)
def rect(fp):
    boxes=[s.GetBoundingBox() for s in fp.GraphicalItems() if s.GetLayer() in (pcb.F_CrtYd,pcb.B_CrtYd)]
    boxes.extend(p.GetBoundingBox() for p in fp.Pads())
    return (min(mm(b.GetX()) for b in boxes),min(mm(b.GetY()) for b in boxes),max(mm(b.GetRight()) for b in boxes),max(mm(b.GetBottom()) for b in boxes))
def overlaps(a,b,gap=.21):return a[0]<b[2]+gap and a[2]>b[0]-gap and a[1]<b[3]+gap and a[3]>b[1]-gap
critical={f'U{i}' for i in range(13,17)}
reserved=[]
for j in range(5,9):
    xy=refs[f'J{j}'].GetPosition();x,y=mm(xy.x),mm(xy.y)
    reserved.append((x-.65,y-.9,x+.65,y+.9))
initial={r:{'x_mm':mm(f.GetPosition().x),'y_mm':mm(f.GetPosition().y),'rotation_deg':f.GetOrientationDegrees(),'side':'bottom' if f.IsFlipped() else 'top'} for r,f in refs.items()}
movable={f'R{i}' for i in range(66,74)}
for r,f in refs.items():
    if r in critical or not f.IsFlipped():continue
    if any(overlaps(rect(f),rect(refs[c])) for c in critical) or any(overlaps(rect(f),b) for b in reserved):movable.add(r)
assert not any(r in movable for r in ['U3','J1','J2','J3','J4','J5','J6','J7','J8','U1','U2','Q1'])
holes=[]
for fp in refs.values():
    for pad in fp.Pads():
        d=pad.GetDrillSize()
        if d.x or d.y:
            pos=pad.GetPosition();radius=max(mm(d.x),mm(d.y))/2+.2
            bb=pad.GetBoundingBox()
            holes.append((min(mm(pos.x)-radius,mm(bb.GetX())-.15),min(mm(pos.y)-radius,mm(bb.GetY())-.15),max(mm(pos.x)+radius,mm(bb.GetRight())+.15),max(mm(pos.y)+radius,mm(bb.GetBottom())+.15)))
placed={r:(f.IsFlipped(),rect(f)) for r,f in refs.items() if r not in movable}
def legal(box,side):
    if box[0]<.4 or box[1]<.4 or box[2]>44.6 or box[3]>36.6:return False
    if any(other==side and overlaps(box,b) for other,b in placed.values()):return False
    if any(overlaps(box,b,0) for b in holes):return False
    if side and any(overlaps(box,b,.10) for b in reserved):return False
    # Keep all new front placements out of the USB agent's upper fanout region.
    if not side and overlaps(box,(.3,.3,31.5,14.3),0):return False
    return True
def area(r):
    a=rect(refs[r]);return (a[2]-a[0])*(a[3]-a[1])
local={f'R{i+66}':f'U{i+13}' for i in range(4)}|{f'R{i+70}':f'U{i+13}' for i in range(4)}
order=sorted(movable,key=lambda r:(0 if r in local else 1,-area(r)))
moved=[]
for r in order:
    f=refs[r];original=initial[r]
    if r in local:
        ic=refs[local[r]];pos=ic.GetPosition();anchor=(mm(pos.x)-2.9,mm(pos.y)+(2.45 if int(r[1:])<70 else -2.45))
    else:anchor=(original['x_mm'],original['y_mm'])
    best=None
    # Existing face first; small parts may use the other face below the USB corridor.
    for side in [True,False]:
        if f.IsFlipped()!=side:f.Flip(f.GetPosition(),pcb.FLIP_DIRECTION_TOP_BOTTOM)
        for angle in [original['rotation_deg'],(original['rotation_deg']+90)%360]:
            f.SetOrientationDegrees(angle);f.SetPosition(pcb.VECTOR2I(0,0));localbox=rect(f)
            for radius in [4,8,16,40]:
                options=[]
                for iy in range(max(2,round((anchor[1]-radius)*4)),min(146,round((anchor[1]+radius)*4))+1):
                    y=iy/4
                    for ix in range(max(2,round((anchor[0]-radius)*4)),min(178,round((anchor[0]+radius)*4))+1):
                        x=ix/4;dist=(x-anchor[0])**2+(y-anchor[1])**2
                        if best and dist>=best[0]:continue
                        box=(localbox[0]+x,localbox[1]+y,localbox[2]+x,localbox[3]+y)
                        if legal(box,side):options.append((dist,x,y,box))
                if options:
                    choice=min(options,key=lambda p:p[0])
                    if best is None or choice[0]<best[0]:best=(*choice,side,angle)
                    break
        if best:break
    if best is None:raise RuntimeError('No placement for '+r)
    _,x,y,box,side,angle=best
    if f.IsFlipped()!=side:f.Flip(f.GetPosition(),pcb.FLIP_DIRECTION_TOP_BOTTOM)
    f.SetOrientationDegrees(angle);f.SetPosition(pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y)))
    placed[r]=(side,rect(f));moved.append({'ref':r,'old':original,'new':{'x_mm':x,'y_mm':y,'rotation_deg':angle,'side':'bottom' if side else 'top'}})
board.BuildConnectivity()
pcb.SaveBoard(str(OUT/'pcbgolf.kicad_pcb'),board)
plan=json.loads((ROOT/'reports/placement-45x37-mating.json').read_text())
plan['placements']={r:{'x_mm':mm(f.GetPosition().x),'y_mm':mm(f.GetPosition().y),'rotation_deg':f.GetOrientationDegrees(),'side':'bottom' if f.IsFlipped() else 'top'} for r,f in refs.items()}
plan['warnings'].append('Power revision: all eFuses on B.Cu, 3.0 mm right of their assigned connector, y=4.75; bottom USB bridge strips reserved. Sense and ILIM resistors relocated nearby; displaced small parts repacked.')
plan['power_repacking']={'moved':moved,'critical_refs':sorted(critical),'reserved_bottom_usb_bridge_boxes':reserved}
(OUT/'placement.json').write_text(json.dumps(plan,indent=2))
(ROOT/'reports/placement-power-clusters.json').write_text(json.dumps(plan,indent=2))
print(json.dumps({'moved_count':len(moved),'refs':[m['ref'] for m in moved],'plan':str(OUT/'placement.json')}))
