"""Add local In2 GND references and short ground returns to a USB route plan."""
import json,math
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point,LineString,Polygon
from shapely.ops import unary_union
from shapely import contains_xy
import usb_route_plan as u
p=json.loads((u.ROOT/'reports/usb-paired-routes.json').read_text())
u.TRACKS[:]=p['tracks'];u.VIAS[:]=[v for v in p['vias'] if v['net']!='GND']
signal=u.VIAS.copy();xyz=np.array([v['pos'] for v in signal]);tree=cKDTree(xyz)
obs=unary_union([u.obstacle({'GND'},l,.2) for l in [u.F,u.B]]+[u.polychain(q).buffer(.30) for pad in u.G['pads'] for q in pad['hole']])
region=unary_union([Point(v['pos']).buffer(1.5) for v in signal])
xs=np.arange(.5,44.5,.05);ys=np.arange(.5,36.5,.05);xx,yy=np.meshgrid(xs,ys)
mask=contains_xy(region,xx,yy)&~contains_xy(obs,xx,yy);candidates=np.column_stack([xx[mask],yy[mask]])
covers=tree.query_ball_point(candidates,1.5);remaining=set(range(len(signal)));selected=[];assignments={}
while remaining:
 best=None
 for i,c in enumerate(candidates):
  if any(math.dist(c,s)<.401 for s in selected):continue
  served=remaining.intersection(covers[i])
  if not served:continue
  score=(-len(served),sum(math.dist(c,xyz[j]) for j in served)/len(served))
  if best is None or score<best[0]:best=(score,c,served)
 if best is None:break
 _,c,served=best;selected.append(c);assignments[len(selected)-1]=sorted(served);remaining-=served
grounds=[dict(net='GND',pos=c.tolist(),diameter=.40,drill=.20,purpose='USB reference return') for c in selected]
shapes=[LineString([t['a'],t['b']]).buffer(.9) for t in p['tracks'] if t['layer']==u.B]
shapes += [Point(v['pos']).buffer(.8) for v in signal]
for i,c in enumerate(selected):
 shapes.append(Point(c).buffer(.4))
 shapes.extend(LineString([c,xyz[j]]).buffer(.5) for j in assignments[i])
merged=unary_union(shapes).buffer(0).simplify(.02,preserve_topology=True)
parts=[merged] if isinstance(merged,Polygon) else list(merged.geoms)
p['vias']=signal+grounds
p['zones']=[dict(net='GND',layer=u.G['layers']['In2.Cu'],priority=100,name=f'USB In2 reference {i+1}',outline=[list(xy) for xy in shape.exterior.coords[:-1]],clearance_mm=.1) for i,shape in enumerate(parts)]
p['reference_audit']=dict(ground_vias=len(grounds),patches=len(parts),uncovered_signal_vias=[signal[j] for j in sorted(remaining)],max_return_distance_mm=max((math.dist(selected[i],xyz[j]) for i,js in assignments.items() for j in js),default=None),return_limit_mm=1.5,reference_layers={'top':'In1.Cu continuous GND','bottom':'In2.Cu priority100 local GND'},limits=['Native refill and connectivity check must verify that every GND patch joins In1 through the placed return vias.','The 1.5 mm return-via distance is a design target, not a standards-derived limit.','Final full-board field/USB compliance validation remains necessary.'])
(u.ROOT/'reports/usb-paired-routes.json').write_text(json.dumps(p,indent=2));print(json.dumps(p['reference_audit'],indent=2))
