"""Find low-displacement landing pockets for balanced USB P transitions."""
import usb_route_plan as u
import json,math
from shapely.ops import unary_union
p=json.loads((u.ROOT/'reports/usb-paired-routes.json').read_text());u.TRACKS[:]=p['tracks'];u.VIAS[:]=p['vias']
result=[]
for ch in range(1,5):
 net=f'CH{ch}_D_P';n=f'CH{ch}_D_N';candidates=[]
 ngeom=unary_union([u.LineString([t['a'],t['b']]) for t in u.TRACKS if t['net']==n and t['layer']==u.F])
 for t in u.TRACKS:
  if t['net']!=net or t['layer']!=u.F:continue
  a=u.np.array(t['a']);b=u.np.array(t['b']);length=math.dist(a,b)
  if length<1.4 or min(a[1],b[1])<4.7:continue
  direction=(b-a)/length
  for frac in [.25,.35,.5,.65,.75]:
   if min(frac,1-frac)*length<.65:continue
   mid=a+(b-a)*frac;near=u.np.array(u.nearest_points(u.Point(mid),ngeom)[1].coords[0]);normal=mid-near;normal/=u.np.linalg.norm(normal)
   for offset in [.25,.35,.5]:
    q1=mid-direction*.6;q2=mid+direction*.6;v1=mid-direction*.3+normal*offset;v2=mid+direction*.3+normal*offset
    shapeF=unary_union([u.LineString([q1,v1]).buffer(.055),u.LineString([v2,q2]).buffer(.055),u.Point(v1).buffer(.2),u.Point(v2).buffer(.2)])
    shapeB=unary_union([u.LineString([v1,v2]).buffer(.055),u.Point(v1).buffer(.2),u.Point(v2).buffer(.2)])
    refs=set();track_bad=False
    for l,s in [(u.F,shapeF),(u.B,shapeB)]:
     for pad in u.G['pads']:
      if pad['net']==net:continue
      if any(s.intersects(u.polychain(pts).buffer(.101)) for pts in pad['polygons'].get(str(l),[])):refs.add(pad['ref'])
      if any(s.intersects(u.polychain(pts).buffer(.301 if pad['net'] else .201)) for pts in pad['hole']):refs.add(pad['ref'])
     for tt in u.TRACKS:
      if tt['net']==net or tt['layer']!=l:continue
      if s.distance(u.LineString([tt['a'],tt['b']]).buffer(tt['width']/2))<.09999:track_bad=True
     for vv in u.VIAS:
      if vv['net']!=net and s.distance(u.Point(vv['pos']).buffer(vv['diameter']/2))<.1001:track_bad=True
    if track_bad or any(r in ['U3','U4'] or r.startswith('J') for r in refs):continue
    candidates.append(dict(ch=ch,via_positions=[v1.tolist(),v2.tolist()],refs_to_clear=sorted(refs),offset=offset,top_approach=[q1.tolist(),q2.tolist()],segment=t))
 candidates.sort(key=lambda x:(len(x['refs_to_clear']),sum(3 if r.startswith('U') else 1 for r in x['refs_to_clear']),x['offset']))
 result.extend(candidates[:4])
(u.ROOT/'reports/usb-balanced-via-reservations.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
