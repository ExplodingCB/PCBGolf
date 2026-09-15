"""Refine isolated BGA power copper and restore a compact MCU clock cluster."""
import json,math
from pathlib import Path
import pcbnew as p
from shapely.geometry import box
from route_ground import xy
from route_power import add_zone
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'candidates/bga100-power'
b=p.LoadBoard(str(OUT/'power-routed.kicad_pcb'));refs={f.GetReference():f for f in b.GetFootprints()}
report=json.loads((OUT/'power-routing.json').read_text());changes={}
added_zones=add_zone(b,'+3V3',p.F_Cu,box(.31,.31,44.69,36.69),1,'front_3v3_distribution')
# A redundant C2 fanout crosses the short bootstrap route. C2 remains tied to
# U1 VIN and the U2 output copper by the explicit local power trace and pour.
remove=next(x for x in report['tracks'] if x.get('pad')=='C2.1')
path=remove['path_mm'];via_at=path[-1];removed=[];removed_objects=[]
for t in list(b.GetTracks()):
    if t.GetNetname()!=remove['net']:continue
    if isinstance(t,p.PCB_VIA) and math.dist(xy(t.GetPosition()),via_at)<1e-6:
        removed.append(str(t.m_Uuid.AsString()));removed_objects.append(t);b.Remove(t)
    elif not isinstance(t,p.PCB_VIA) and any((math.dist(xy(t.GetStart()),a)<1e-6 and math.dist(xy(t.GetEnd()),z)<1e-6) or (math.dist(xy(t.GetStart()),z)<1e-6 and math.dist(xy(t.GetEnd()),a)<1e-6) for a,z in zip(path,path[1:])):
        removed.append(str(t.m_Uuid.AsString()));removed_objects.append(t);b.Remove(t)
# Low-priority front+3V3 copper connects the regional MCU supply pour to the
# regulator across existing same-net power lands. Other power pours win.
# Move only the MCU input bulk and three clock parts; all front positions stay.
moves={'C19':(4.05,24.6,0),'Y1':(3.6,15.35,180),'C14':(3.6,17.4,0),'C17':(1.0,15.2,90)}
for ref,(x,y,a) in moves.items():
    f=refs[ref];ox,oy=xy(f.GetPosition());dx,dy=x-ox,y-oy
    if ref=='C19':
        for row in [z for z in report['tracks'] if z.get('pad','').startswith(ref+'.')]:
            route=row['path_mm']
            for t in b.GetTracks():
                if t.GetNetname()!=row['net']:continue
                if isinstance(t,p.PCB_VIA) and math.dist(xy(t.GetPosition()),route[-1])<1e-6:t.Move(p.VECTOR2I(p.FromMM(dx),p.FromMM(dy)))
                elif not isinstance(t,p.PCB_VIA) and any((math.dist(xy(t.GetStart()),v)<1e-6 and math.dist(xy(t.GetEnd()),w)<1e-6) or (math.dist(xy(t.GetStart()),w)<1e-6 and math.dist(xy(t.GetEnd()),v)<1e-6) for v,w in zip(route,route[1:])):t.Move(p.VECTOR2I(p.FromMM(dx),p.FromMM(dy)))
    f.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));f.SetOrientationDegrees(a)
    changes[ref]={'x_mm':x,'y_mm':y,'rotation_deg':a,'side':'bottom'}
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(OUT/'power-adjusted.kicad_pcb'),b)
plan=json.loads((OUT/'placement.json').read_text());plan['placements'].update(changes);plan['clock_refinement']=changes
(OUT/'placement.json').write_text(json.dumps(plan,indent=2));(OUT/'power-adjustments.json').write_text(json.dumps({'removed_redundant_C2_copper':removed,'moved_components':changes,'added_zone':'Low priority1 front+3V3 distribution'},indent=2))
print(json.dumps(changes))
