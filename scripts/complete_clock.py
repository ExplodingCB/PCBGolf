"""Bring the crystal and its load capacitors beside the MCU's clock escape."""
import argparse,json,shutil
from pathlib import Path
import pcbnew as p
from route_ground import xy,copper_shape,track_shape
from route_critical_power import run
ap=argparse.ArgumentParser();ap.add_argument('board',type=Path);ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args();assert a.board.resolve()!=a.out.resolve()
b=p.LoadBoard(str(a.board));refs={f.GetReference():f for f in b.GetFootprints()}
moves={'C19':(4.05,24.3,0),'Y1':(3.6,15.35,180),'C14':(3.6,17.4,0),'C17':(1.0,16.3,90)}
retired=[];removed=[]
oldpads=[(q.GetNetname(),f.GetLayer(),copper_shape(q,f.GetLayer())) for r in moves for f in [refs[r]] for q in f.Pads()]
for t in list(b.GetTracks()):
    if isinstance(t,p.PCB_VIA):
        if t.GetNetname()=='GND' and abs(xy(t.GetPosition())[0]-3.1)<1e-5 and abs(xy(t.GetPosition())[1]-14.1)<1e-5:
            removed.append(t.m_Uuid.AsString());retired.append(t);b.Remove(t)
        continue
    # Preserve the prechecked BGA escape. Remove external clock routing and
    # copper attached to the four pads that are about to move.
    clock=t.GetNetname() in ('Net-(U3-PH0)','Net-(U3-PH1)') and min(xy(t.GetStart())[0],xy(t.GetEnd())[0])<6.09
    attached=any(t.GetNetname()==n and t.GetLayer()==l and track_shape(t).intersects(s) for n,l,s in oldpads)
    if clock or attached:
        removed.append(t.m_Uuid.AsString());retired.append(t);b.Remove(t)
for r,(x,y,theta) in moves.items():
    f=refs[r];f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));f.SetOrientationDegrees(theta)
links=[(('U3','G2'),('Y1','3'),.127,10),(('Y1','3'),('C17','1'),.127,5),
       (('U3','G1'),('Y1','1'),.127,9),(('Y1','1'),('C14','1'),.127,5)]
report=run(b,links,{('U3','G1'):(6.1,18.7),('U3','G2'):(6.1,18.3)})
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(a.out),b)
for suffix in ('.kicad_pro','.kicad_dru'):shutil.copy2(a.board.with_suffix(suffix),a.out.with_suffix(suffix))
report.update(moved=moves,removed_tracks=removed)
a.out.with_suffix('.clock.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'routed_clock_links':len(report['routed']),'unresolved':report['unresolved']}))
