"""Export actual filled reference polygons and native return connectivity."""
import json,sys
from pathlib import Path
import pcbnew as pcb
b=pcb.LoadBoard(sys.argv[1]);b.BuildConnectivity();c=b.GetConnectivity()
plan=json.loads(Path(sys.argv[2]).read_text())
def xy(p):return [pcb.ToMM(p.x),pcb.ToMM(p.y)]
def chain(o):return [xy(o.CPoint(i)) for i in range(o.PointCount())]
zones=[]
for z in b.Zones():
 if z.GetNetname()!='GND' or z.GetLayer() not in (pcb.In1_Cu,pcb.In2_Cu):continue
 poly=z.GetFilledPolysList(z.GetLayer())
 zones.append(dict(name=z.GetZoneName(),layer=z.GetLayer(),priority=z.GetAssignedPriority(),polygons=[dict(shell=chain(poly.COutline(i)),holes=[chain(poly.CHole(i,j)) for j in range(poly.HoleCount(i))]) for i in range(poly.OutlineCount())]))
returns=[]
for r in plan['vias']:
 if r['net']!='GND':continue
 v=next(v for v in b.GetTracks() if isinstance(v,pcb.PCB_VIA) and v.GetNetname()=='GND' and all(abs(a-z)<1e-5 for a,z in zip(xy(v.GetPosition()),r['pos'])))
 joined=[dict(layer=x.GetLayer(),name=x.GetZoneName()) for x in c.GetConnectedItems(v) if isinstance(x,pcb.ZONE) and x.GetNetname()=='GND']
 returns.append(dict(pos=r['pos'],native_connected_in1=c.IsConnectedOnLayer(v,pcb.In1_Cu),native_connected_in2=c.IsConnectedOnLayer(v,pcb.In2_Cu),connected_gnd_zones=joined))
Path(sys.argv[3]).write_text(json.dumps(dict(board=sys.argv[1],zones=zones,returns=returns),indent=2))
print(json.dumps(dict(zones=len(zones),returns=len(returns),bad_returns=[x for x in returns if not x['native_connected_in1'] or not x['native_connected_in2']]),indent=2))
