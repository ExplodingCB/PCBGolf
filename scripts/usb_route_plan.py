"""Obstacle-aware USB differential routing on native KiCad pad polygons.

This module uses the workspace venv; route_usb_pairs.py applies its JSON with
native pcbnew. Every generated conductor is checked against actual copper and
hole geometry, followed by KiCad DRC. Unfinished pairs are explicit failures.
"""
import json,math,heapq,itertools,time
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,LineString,Point,box
from shapely.ops import unary_union,substring,nearest_points
from shapely import contains_xy
from scipy.ndimage import distance_transform_edt
ROOT=Path(__file__).resolve().parents[1]
G=json.loads((ROOT/'reports/usb-native-permuted.json').read_text())
F=G['layers']['F.Cu'];B=G['layers']['B.Cu']
WIDTH=.11;GAP=.10;PITCH=WIDTH+GAP;GRID=.02
TRACKS=[];VIAS=[];RESULTS=[]
def polychain(points):return Polygon(points).buffer(0)
def pads_for(net):return [p for p in G['pads'] if p['net']==net]
def obstacle(netnames,layer,radius,include_tracks=True):
 items=[]
 for p in G['pads']:
  if p['net'] in netnames:continue
  for pts in p['polygons'].get(str(layer),[]):items.append(polychain(pts).buffer(radius+.09999))
  for pts in p['hole']:items.append(polychain(pts).buffer(radius+(.29999 if p['net'] else .19999)))
 if include_tracks:
  for t in G['tracks']+TRACKS:
   if t['net'] in netnames:continue
   if t.get('type','track')=='track' and t['layer']==layer:items.append(LineString([t['a'],t['b']]).buffer(t['width']/2+radius+.09999))
   elif t.get('type')=='via':items.append(Point(t['pos']).buffer(t['width']/2+radius+.09999))
 for v in VIAS:
  if v['net'] not in netnames:items.append(Point(v['pos']).buffer(v['diameter']/2+radius+.09999))
 items.extend([box(-5,-5,0.3005+radius,42),box(45-.3005-radius,-5,50,42),box(-5,-5,50,.3005+radius),box(-5,37-.3005-radius,50,42)])
 return unary_union(items)
def length(coords):return sum(math.dist(a,b) for a,b in zip(coords,coords[1:]))
def add_path(coords,net,width=WIDTH,layer=F):
 for a,b in zip(coords,coords[1:]):
  if math.dist(a,b)>1e-7:TRACKS.append(dict(net=net,a=list(map(float,a)),b=list(map(float,b)),width=width,layer=layer))
def checked_path(coords,net,width=WIDTH,layer=F):
 obs=obstacle({net},layer,width/2)
 l=LineString(coords)
 if l.intersects(obs):return False,l.intersection(obs).length
 return True,0
def astar(start,end,obs,step=GRID):
 nx=int(45/step)+1;ny=int(37/step)+1
 xs=np.arange(nx)*step;ys=np.arange(ny)*step
 blocked=contains_xy(obs,xs[None,:],ys[:,None])
 def node(p):return (int(round(p[0]/step)),int(round(p[1]/step)))
 s=node(start);e=node(end)
 for n in [s,e]:
  if blocked[n[1],n[0]]:return None,{'reason':'blocked endpoint','point':[n[0]*step,n[1]*step]}
 # Slightly reward routes through open space and avoid diagonal corner cuts.
 clearance=distance_transform_edt(~blocked)
 directions=[(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)]
 def h(n):return math.hypot(n[0]-e[0],n[1]-e[1])
 q=[(h(s),0,s)];cost={s:0};prev={};seen=0
 while q:
  _,g,n=heapq.heappop(q)
  if g>cost.get(n,1e99)+1e-9:continue
  seen+=1
  if n==e:break
  for dx,dy in directions:
   nn=(n[0]+dx,n[1]+dy)
   if nn[0]<0 or nn[0]>=nx or nn[1]<0 or nn[1]>=ny or blocked[nn[1],nn[0]]:continue
   if dx and dy and (blocked[n[1],nn[0]] or blocked[nn[1],n[0]]):continue
   ng=g+math.hypot(dx,dy)+.015/max(clearance[nn[1],nn[0]],1)
   if ng+1e-9<cost.get(nn,1e99):cost[nn]=ng;prev[nn]=n;heapq.heappush(q,(ng+h(nn),ng,nn))
  if seen>700000:return None,{'reason':'search limit','seen':seen}
 else:return None,{'reason':'no path','seen':seen}
 nodes=[e]
 while nodes[-1]!=s:nodes.append(prev[nodes[-1]])
 pts=[(x*step,y*step) for x,y in reversed(nodes)]
 pts[0]=start;pts[-1]=end
 # Remove straight subdivisions, then visibility shortcuts. Clearance geometry
 # includes the full pair bundle, so this simplification cannot clip a pad.
 keep=[pts[0]]
 for i in range(1,len(pts)-1):
  a=np.array(pts[i])-pts[i-1];b=np.array(pts[i+1])-pts[i]
  if abs(a[0]*b[1]-a[1]*b[0])>1e-7:keep.append(pts[i])
 keep.append(pts[-1]);simple=[keep[0]];i=0
 while i<len(keep)-1:
  j=len(keep)-1
  while j>i+1 and LineString([keep[i],keep[j]]).intersects(obs):j-=1
  simple.append(keep[j]);i=j
 return simple,{'seen':seen,'length':length(simple)}
def branch_port(ch,cx):
 """Short mirrored-contact crossover: one N bottom bridge, P stays top.

 Both N transitions are close to the contacts. Main P/N leave together inside
 the socket at y=6.25. The tiny bottom bridge needs a local In2 GND reference.
 """
 n=f'CH{ch}_D_N';p=f'CH{ch}_D_P';cy=4.75-0.00001
 # Coordinates are relative to the common 0.50 mm connector contact pitch.
 paths=[(p,[(cx+.83,cy-.25),(cx+.21,4.25),(cx+.21,3.90),(cx,3.60)],F),
        (p,[(cx-.83,cy+.25),(cx-.75,3.95),(cx,3.60)],B),
        (n,[(cx-.83,cy-.25),(cx-.15,cy-.40)],F),
        (n,[(cx+.83,cy+.25),(cx+.15,cy+.35)],F),
        (n,[(cx-.15,cy-.40),(cx+.15,cy+.35)],B)]
 vias=[dict(net=n,pos=[cx-.15,cy-.40],diameter=.40,drill=.20),dict(net=n,pos=[cx+.15,cy+.35],diameter=.40,drill=.20),dict(net=p,pos=[cx-.83,cy+.25],diameter=.40,drill=.20,filled_and_capped=True),dict(net=p,pos=[cx,3.60],diameter=.40,drill=.20)]
 pending=[]
 for v in vias:
  for layer in [F,B]:
   if obstacle({v['net']},layer,v['diameter']/2).contains(Point(v['pos'])):
    if layer==B:pending.append({'reason':'branch via obstructed','via':v,'layer':layer})
    else:return False,{'reason':'branch via obstructed','via':v,'layer':layer}
 for net,pts,layer in paths:
  good,intersection=checked_path(pts,net,layer=layer)
  if not good:
   if layer==B:pending.append({'reason':'branch track obstructed','net':net,'path':pts,'layer':layer,'intersection':intersection})
   else:return False,{'reason':'branch track obstructed','net':net,'path':pts,'layer':layer,'intersection':intersection}
 # Check the two nets together before committing.
 for l in [F,B]:
  pgeom=unary_union([LineString(pts).buffer(WIDTH/2) for net,pts,layer in paths if net==p and layer==l]+[Point(v['pos']).buffer(v['diameter']/2) for v in vias if v['net']==p])
  ngeom=unary_union([LineString(pts).buffer(WIDTH/2) for net,pts,layer in paths if net==n and layer==l]+[Point(v['pos']).buffer(v['diameter']/2) for v in vias if v['net']==n])
  if pgeom.distance(ngeom)<.10-1e-6:return False,{'reason':'branch pair clearance','layer':l,'distance':pgeom.distance(ngeom)}
 for net,pts,layer in paths:
  if layer==F or not pending:add_path(pts,net,layer=layer)
 if not pending:VIAS.extend(vias)
 return True,{'bridge_length_mm':length(paths[-1][1]),'pending_branches':pending}
def route_port(ch,cx):
 p=f'CH{ch}_D_P';n=f'CH{ch}_D_N';before=len(TRACKS);vbefore=len(VIAS)
 ok,details=branch_port(ch,cx)
 if not ok:return dict(pair=f'CH{ch}',status='failed',**details)
 hubp=next(pad for pad in pads_for(p) if pad['ref']=='U4')['pos'];hubn=next(pad for pad in pads_for(n) if pad['ref']=='U4')['pos'];hx=(hubp[0]+hubn[0])/2
 start=(cx+1.50,4.74999)
 # Leave the connector's right contact row horizontally. The lower central
 # strip is mechanically sealed by the locating peg and diagonal shell pads.
 obs=obstacle({p,n},F,PITCH/2+WIDTH/2+.002)
 if ch==2:
  center=[(20.05,4.74999),(21.38,6.08),(21.38,8.38),(23.14,10.14),(23.16,12.32),(23.84,13.0),(24.0,13.0)];search={'seen':0,'length':length(center),'reserved_via_corridor':True}
  if LineString(center).intersects(obs):center=None;search={'reason':'reserved CH2 corridor obstructed'}
 else:center,search=astar((cx+1.80,4.74999),(hx,13.00),obs)
 if center is None:
  del TRACKS[before:];del VIAS[vbefore:];return dict(pair=f'CH{ch}',status='failed',**search)
 center=[start]+center+[(hx,13.98)]
 line=LineString(center)
 pline=line.offset_curve(-PITCH/2,join_style=2);nline=line.offset_curve(PITCH/2,join_style=2)
 routes={p:list(pline.coords),n:list(substring(nline,0,nline.length-.30).coords)}
 for net,pts in routes.items():
  hp=hubp if net==p else hubn
  cp=(cx+.83,4.49999 if net==p else 4.99999)
  pts=[cp]+pts
  if net==p:pts.append(hp)
  else:pts.append((hx-.30,13.68))
  routes[net]=pts
  good,intersection=checked_path(pts,net)
  if not good:
   del TRACKS[before:];del VIAS[vbefore:];return dict(pair=f'CH{ch}',status='failed',reason='offset path collision',net=net,intersection=intersection,centerline=center)
 if LineString(routes[p]).distance(LineString(routes[n]))<PITCH-1e-6:
  # Endpoint fans can taper, but conductor clearance never drops below 0.10.
  if LineString(routes[p]).distance(LineString(routes[n]))<WIDTH+.10-1e-6:
   del TRACKS[before:];del VIAS[vbefore:];return dict(pair=f'CH{ch}',status='failed',reason='paired offsets self-crowd',centerline=center)
 # A short N crossover under the hub exchanges the contact-row ordering.
 # The load via is in the QFN pad and must be epoxy filled and copper capped.
 hubvias=[dict(net=n,pos=[hx-.30,13.68],diameter=.40,drill=.20),dict(net=n,pos=[hubn[0]-.05,hubn[1]],diameter=.40,drill=.20,filled_and_capped=True,ref='U4')]
 for v in hubvias:
  for layer in [F,B]:
   if obstacle({n},layer,v['diameter']/2).contains(Point(v['pos'])):
    del TRACKS[before:];del VIAS[vbefore:];return dict(pair=f'CH{ch}',status='failed',reason='hub crossover via obstructed',via=v,layer=layer,centerline=center)
 bottom=[hubvias[0]['pos'],[hx-.6,14.10],[hx-.6,14.30],hubvias[1]['pos']]
 good,intersection=checked_path(bottom,n,layer=B)
 if not good:
  del TRACKS[before:];del VIAS[vbefore:];return dict(pair=f'CH{ch}',status='failed',reason='hub crossover obstructed',intersection=intersection,centerline=center)
 # Also account for the enlarged via land against the partner trace.
 if any(Point(v['pos']).distance(LineString(routes[p]))<v['diameter']/2+WIDTH/2+.1001 for v in hubvias):
  del TRACKS[before:];del VIAS[vbefore:];return dict(pair=f'CH{ch}',status='failed',reason='hub crossover partner clearance',centerline=center)
 for net,pts in routes.items():add_path(pts,net)
 add_path(bottom,n,layer=B);VIAS.extend(hubvias)
 return dict(pair=f'CH{ch}',status='routed',centerline=center,lengths_mm={net:length(pts) for net,pts in routes.items()},**details,**search)
def balance_main_vias(ch):
 """Give P the same two through-layer transitions as the hub N crossover.

 Select a clear segment of the long top run and place a short parallel bottom
 excursion with two0.40/0.20 vias. Equal via count applies in BOTH plug
 orientations because both duplicate-contact branches also have two vias.
 """
 p=f'CH{ch}_D_P';n=f'CH{ch}_D_N';ngeom=unary_union([LineString([t['a'],t['b']]) for t in TRACKS if t['net']==n and t['layer']==F])
 candidates=[(length([t['a'],t['b']]),i,t) for i,t in enumerate(TRACKS) if t['net']==p and t['layer']==F and min(t['a'][1],t['b'][1])>4.7 and length([t['a'],t['b']])>1.4]
 for seglen,i,t in sorted(candidates,reverse=True):
  a=np.array(t['a']);b=np.array(t['b']);direction=(b-a)/seglen
  for frac in [.5,.35,.65,.25,.75]:
   mid=a+(b-a)*frac
   if min(frac,1-frac)*seglen<.65:continue
   nearest=np.array(nearest_points(Point(mid),ngeom)[1].coords[0]);normal=mid-nearest
   if np.linalg.norm(normal)<1e-6:continue
   normal/=np.linalg.norm(normal)
   for offset in [.25,.30,.35,.45]:
    q1=mid-direction*.60;q2=mid+direction*.60
    v1=mid-direction*.30+normal*offset;v2=mid+direction*.30+normal*offset
    vias=[dict(net=p,pos=v.tolist(),diameter=.40,drill=.20) for v in [v1,v2]]
    if any(obstacle({p},l,.2).contains(Point(v['pos'])) for v in vias for l in [F,B]):continue
    paths=[(F,[a,q1,v1]),(B,[v1,v2]),(F,[v2,q2,b])]
    if not all(checked_path(pts,p,layer=l)[0] for l,pts in paths):continue
    TRACKS.pop(i)
    for l,pts in paths:add_path(pts,p,layer=l)
    VIAS.extend(vias)
    return {'status':'balanced','vias':vias,'bottom_segment_mm':math.dist(v1,v2),'planar_length_added_mm':sum(length(pts) for l,pts in paths)-seglen}
 return {'status':'failed','reason':'no clear balanced P via excursion'}
def simple_pair(label,p,n,start,departure,arrival,end,src,dst,positive_side=1,tail_waypoints=None):
 before=len(TRACKS)
 obs=obstacle({p,n},F,PITCH/2+WIDTH/2+.002)
 center,search=astar(departure,arrival,obs)
 if center is None:return dict(pair=label,status='failed',**search)
 center=[start]+center+[end];line=LineString(center)
 routes={p:list(line.offset_curve(positive_side*PITCH/2,join_style=2).coords),n:list(line.offset_curve(-positive_side*PITCH/2,join_style=2).coords)}
 for net,pts in routes.items():
  pts[:0]=[src[net]];pts.extend((tail_waypoints or {}).get(net,[]));pts.append(dst[net]);good,intersection=checked_path(pts,net)
  if not good:return dict(pair=label,status='failed',reason='paired path collision',net=net,intersection=intersection,centerline=center)
 if LineString(routes[p]).distance(LineString(routes[n]))<WIDTH+.1-1e-6:return dict(pair=label,status='failed',reason='paired paths self-crowd',centerline=center)
 for net,pts in routes.items():add_path(pts,net)
 return dict(pair=label,status='routed',centerline=center,lengths_mm={net:length(pts) for net,pts in routes.items()},**search)
def route_stm():
 p='STM_D_P';n='STM_D_N';src={net:next(x['pos'] for x in pads_for(net) if x['ref']=='U4') for net in [p,n]};dst={net:next(x['pos'] for x in pads_for(net) if x['ref']=='U3') for net in [p,n]}
 before=len(TRACKS);vbefore=len(VIAS)
 if any(x['ref']=='U3' and x['pad']=='D9' for x in G['pads']):
  landing={p:dst[p],n:[13.7,20.7]}
  vias=[dict(net=net,pos=landing[net],diameter=.40,drill=.20,filled_and_capped=(net==p),ref='U3') for net in [p,n]]
  for v in vias:
   for l in [F,B]:
    if obstacle({v['net']},l,.2).contains(Point(v['pos'])):return dict(pair='STM',status='failed',reason='BGA load via obstructed',via=v,layer=l)
  if not checked_path([landing[n],dst[n]],n,layer=B)[0]:return dict(pair='STM',status='failed',reason='BGA N dogbone blocked')
  r=simple_pair('STM',p,n,(26.35,19.50),(26.55,19.50),(13.70,22.30),(13.70,21.80),src,landing,positive_side=-1,tail_waypoints={n:[[13.85,21.8]]})
  if r['status']=='routed':add_path([landing[n],dst[n]],n,layer=B);VIAS.extend(vias)
  return r
 vias=[dict(net=net,pos=dst[net],diameter=.40,drill=.20,filled_and_capped=True,ref='U3') for net in [p,n]]
 for v in vias:
  for l in [F,B]:
   if obstacle({v['net']},l,.2).contains(Point(v['pos'])):return dict(pair='STM',status='failed',reason='load via obstructed',via=v,layer=l)
 tail={p:[26.70,25.95],n:[26.125,24.9]}
 r=simple_pair('STM',p,n,(26.35,19.50),(26.55,19.50),(26.50,24.70),(26.50,24.90),src,tail,positive_side=-1)
 if r['status']=='routed':
  tails={p:[tail[p],dst[p]],n:[tail[n],[26.125,25.3],dst[n]]}
  if not all(checked_path(pts,net)[0] for net,pts in tails.items()):
   del TRACKS[before:];return dict(pair='STM',status='failed',reason='load tail clearance')
  for net,pts in tails.items():add_path(pts,net)
  VIAS.extend(vias)
 return r
def route_host():
 p='USB_D_P';n='USB_D_N';before=len(TRACKS);vbefore=len(VIAS)
 contacts=[x for x in G['pads'] if x['ref']=='J3' and x['net'] in [p,n]]
 vias=[dict(net=x['net'],pos=x['pos'],diameter=.40,drill=.20,filled_and_capped=True,ref='J3') for x in contacts]
 output={p:[36.45,31.00],n:[36.5,31.75]}
 vias.extend(dict(net=net,pos=xy,diameter=.40,drill=.20) for net,xy in output.items())
 for v in vias:
  for l in [F,B]:
   if obstacle({v['net']},l,.2).contains(Point(v['pos'])):return dict(pair='USB',status='failed',reason='connector branch via obstructed',via=v,layer=l)
 branches=[(p,[[37.645,31.25],[37.05,31.25],[37.05,30.25],[37.645,30.25]]),
           (p,[[37.05,31.25],[36.82756992,30.93883219],output[p]]),
           (n,[[37.645,30.75],[37.915,30.99],[38.015,31.15],[38.015,31.35],[37.915,31.51],[37.645,31.75]]),
           (n,[[37.645,31.75],output[n]])]
 for net,pts in branches:
  ok,intersect=checked_path(pts,net,layer=B)
  if not ok:return dict(pair='USB',status='failed',reason='connector branch blocked',net=net,path=pts,intersection=intersect)
 for net in [p,n]:
  geom=unary_union([LineString(pts).buffer(WIDTH/2) for nn,pts in branches if nn==net]+[Point(v['pos']).buffer(.2) for v in vias if v['net']==net])
  other=unary_union([LineString(pts).buffer(WIDTH/2) for nn,pts in branches if nn!=net]+[Point(v['pos']).buffer(.2) for v in vias if v['net']!=net])
  if geom.distance(other)<.09999:return dict(pair='USB',status='failed',reason='connector branch mutual clearance',distance=geom.distance(other))
 for net,pts in branches:add_path(pts,net,layer=B)
 VIAS.extend(vias)
 dst={net:next(x['pos'] for x in pads_for(net) if x['ref']=='U4') for net in [p,n]}
 r=simple_pair('USB',p,n,(35.15,31.375),(34.80,31.375),(26.55,18.0),(26.35,18.0),output,dst,positive_side=1)
 if r['status']!='routed':del TRACKS[before:];del VIAS[vbefore:]
 return r
def render():
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.patches import Polygon as MP
 fig,ax=plt.subplots(figsize=(13,11));ax.set_facecolor('#101921')
 for p in G['pads']:
  for pts in p['polygons'].get(str(F),[]):ax.add_patch(MP(pts,color='#777777',alpha=.55))
  if p['ref'] in ('U4','J5','J6','J7','J8','J3','U3') and p['pad'] in ('1','A6','100'):ax.text(*p['pos'],p['ref'],color='white',fontsize=8)
 for i,t in enumerate(TRACKS):
  c=('#fa746b' if t['net'].endswith('_P') else '#53cfef');ax.plot([t['a'][0],t['b'][0]],[t['a'][1],t['b'][1]],color=c,lw=t['width']*5,ls='-' if t['layer']==F else '--')
 for v in VIAS:ax.add_patch(plt.Circle(v['pos'],v['diameter']/2,color='#fdc751'))
 for r in RESULTS:
  if 'centerline' in r:
   x,y=zip(*r['centerline']);ax.plot(x,y,color='#ffac43',lw=.4,ls=':')
 ax.set_xlim(0,45);ax.set_ylim(37,0);ax.set_aspect('equal');ax.set_title('USB copper planning — red P, cyan N, yellow vias');fig.tight_layout();fig.savefig(ROOT/'reports/usb-paired-routes.png',dpi=160)
def main():
 for ch,cx in [(4,3.25),(3,10.75),(2,18.25),(1,25.75)]:
  start=time.time();r=route_port(ch,cx);RESULTS.append(r);print(json.dumps(r),flush=True)
 RESULTS.sort(key=lambda r:r['pair'])
 for ch,r in enumerate(RESULTS,1):
  if r['status']=='routed':r['via_balance']=balance_main_vias(ch);print(json.dumps({'pair':r['pair'],'via_balance':r['via_balance']}),flush=True)
 for method in [route_stm,route_host]:
  r=method();RESULTS.append(r);print(json.dumps(r),flush=True)
 plan=dict(source=G['board'],width_mm=WIDTH,gap_mm=GAP,tracks=TRACKS,vias=VIAS,pairs=RESULTS,limits=['Only successfully routed pairs are emitted. Native DRC and reference-plane validation required.'])
 (ROOT/'reports/usb-paired-routes.json').write_text(json.dumps(plan,indent=2));render()
if __name__=='__main__':main()
