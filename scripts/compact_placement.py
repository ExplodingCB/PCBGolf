"""Greedy, net-attracted physical placement. JSON uses KiCad Flip(pos, False) then angle."""
from placement_analysis import *
from scipy.linalg import solve
PITCH=.25;W=45.;H=42.;GAP=.30;EDGE=.40

def main():
 rows=json.loads((ROOT/'reports/placement-geometry.json').read_text());rows={r['ref']:r for r in rows}
 # Proposed corrected package from NCS20071XV datasheet; circuit agent's library is authoritative.
 for ref in ['U9','U10','U11','U12']:
  rows[ref]['envelope']=[-.925,-.65,.925,.65];rows[ref]['size']=[1.85,1.3];rows[ref]['body_bounds']=[-.6,-.425,.6,.425]
  rows[ref]['footprint']='pcbgolf:SOT-553';rows[ref]['requires_footprint_correction']=True
 refs=sorted(r for r in rows if not r.startswith('BH') and r not in ('R5','R6'));idx={r:i for i,r in enumerate(refs)}
 # source-local envelope after flip and rotation
 def envelope(ref,angle,side):
  b=rows[ref]['envelope'];p=np.array([[b[0],b[1]],[b[0],b[3]],[b[2],b[1]],[b[2],b[3]]])
  if side=='B.Cu':p[:,1]*=-1
  p=rot2(p,angle);return np.r_[p.min(0),p.max(0)]
 placed={};obstacles={'F.Cu':[],'B.Cu':[]}
 def put(ref,x,y,angle=0,side='F.Cu',by_origin=False):
  b=envelope(ref,angle,side);offset=(b[:2]+b[2:])/2
  origin=np.array([x,y]) if by_origin else np.array([x,y])-offset
  rect=b+np.r_[origin,origin];center=(rect[:2]+rect[2:])/2
  placed[ref]={'ref':ref,'x':round(float(origin[0]),5),'y':round(float(origin[1]),5),'rotation':angle,'side':side,'center':center.tolist(),'bounds':rect.tolist(),'fixed':ref in fixed}
  obstacles[side].append((ref,rect))
  for d in rows[ref]['drills']:
   point=np.array(d['at']);
   if side=='B.Cu':point[1]*=-1
   point=rot2([point],angle)[0]+origin
   w,h=d['size'];a=math.radians(angle);size=np.array([abs(math.cos(a))*w+abs(math.sin(a))*h,abs(math.sin(a))*w+abs(math.cos(a))*h]);rr=np.r_[point-size/2,point+size/2]
   obstacles['B.Cu' if side=='F.Cu' else 'F.Cu'].append((ref+'.drill',rr))
 fixed={'U3','J1','J2','J3','J4','J5','J6','J7','J8','SW1','U4'}
 put('U3',13.,22.5)
 for ref,x in zip(['J5','J6','J7','J8'],[5.,16.7,28.3,40.]):put(ref,x,4.)
 put('J1',39.5,17.5,180,by_origin=True) # open barrel faces right edge
 put('J3',37.,33.15,0,by_origin=True) # USB-C mouth exactly at bottom outline
 put('J4',7.,38.5)
 put('SW1',22.5,38.5)
 put('J2',1.31074,15.125,90,'B.Cu',True) # microSD mouth reaches left edge
 put('U4',22.,20.,0,'B.Cu')
 # Connectivity Laplacian anchors free components; exclude ubiquitous rails.
 netrefs=collections.defaultdict(set)
 for ref in refs:
  for net in rows[ref]['nets'].values():
   if net and not net.startswith('unconnected-'):netrefs[net].add(ref)
 weights=np.zeros((len(refs),len(refs)))
 for net,rr in netrefs.items():
  if len(rr)>15 or net in ('GND','+3V3','+5V','+12V','VBUS'):continue
  rr=list(rr);weight=1/max(1,len(rr)-1)
  for a,b in itertools.combinations(rr,2):weights[idx[a],idx[b]]+=weight;weights[idx[b],idx[a]]+=weight
 # Rail-only decouplers receive their actual functional block as an attraction anchor.
 caps={**{f'C{i}':'U1' for i in [3,4,5,6,7,8]},**{f'C{i}':'U2' for i in [1,2,9,10,11,12,13]},**{f'C{i}':'U3' for i in range(14,26)},**{f'C{i}':'U4' for i in list(range(26,29))+list(range(30,38))},'C29':'J3'}
 for i in range(38,46):caps[f'C{i}']=f'U{5+(i-38)%4}'
 for i in range(46,54):caps[f'C{i}']=f'U{13+(i-46)%4}'
 for c,u in caps.items():weights[idx[c],idx[u]]+=3;weights[idx[u],idx[c]]+=3
 anchor_centers={'U1':(33,26),'U2':(39,26),'U5':(8,33),'U6':(14,33),'U7':(20,33),'U8':(26,33),'U9':(7,9),'U10':(17,9),'U11':(28,9),'U12':(39,9),'U13':(7,11),'U14':(17,11),'U15':(28,11),'U16':(39,11)}
 targets=np.tile([W/2,H/2],(len(refs),1));fixed_refs=set(placed)|set(anchor_centers)
 for ref,p in placed.items():targets[idx[ref]]=p['center']
 for ref,xy in anchor_centers.items():targets[idx[ref]]=xy
 known=[idx[r] for r in fixed_refs];unknown=[idx[r] for r in refs if r not in fixed_refs]
 lap=np.diag(weights.sum(1)+.01)-weights
 targets[unknown]=solve(lap[np.ix_(unknown,unknown)],-lap[np.ix_(unknown,known)]@targets[known]+.01*np.tile([W/2,H/2],(len(unknown),1)))
 # Place large critical ICs first then local networks, LEDs top to keep visible.
 unplaced=set(refs)-set(placed)
 grids=np.meshgrid(np.arange(EDGE,W-EDGE+.01,PITCH),np.arange(EDGE,H-EDGE+.01,PITCH));xs,ys=grids
 while unplaced:
  def priority(ref):
   r=rows[ref];area=math.prod(r['size']);connected=sum(weights[idx[ref],idx[p]] for p in placed)
   return (1000 if ref in anchor_centers else 0)+(100 if area>9 else 0)+connected*4+area
  ref=max(unplaced,key=priority);unplaced.remove(ref);r=rows[ref]
  prefs=['F.Cu'] if ref.startswith('LED') else ['B.Cu','F.Cu']
  # underside bypass capacitors may sit directly below their MCU pads; low via count wins later routing.
  target=targets[idx[ref]].copy();attract=[]
  for other,p in placed.items():
   wgt=weights[idx[ref],idx[other]]
   if wgt:attract.append((wgt,np.array(p['center'])))
  best=None
  for side in prefs:
   for angle in (0,90,180,270):
    env=envelope(ref,angle,side);size=env[2:]-env[:2];lo_x=xs-size[0]/2;hi_x=xs+size[0]/2;lo_y=ys-size[1]/2;hi_y=ys+size[1]/2
    good=(lo_x>=EDGE)&(lo_y>=EDGE)&(hi_x<=W-EDGE)&(hi_y<=H-EDGE)
    for _,b in obstacles[side]:good &= (hi_x+GAP<=b[0])|(lo_x-GAP>=b[2])|(hi_y+GAP<=b[1])|(lo_y-GAP>=b[3])
    if not good.any():continue
    cost=1.5*(abs(xs-target[0])+abs(ys-target[1]))
    for wgt,xy in attract:cost+=wgt*(abs(xs-xy[0])+abs(ys-xy[1]))/max(1,len(attract))
    if side=='F.Cu' and not ref.startswith('LED'):cost+=2.0
    cost=np.where(good,cost,np.inf);k=np.argmin(cost);v=float(cost.flat[k])
    if best is None or v<best[0]:best=(v,float(xs.flat[k]),float(ys.flat[k]),angle,side)
  if best is None:raise RuntimeError('No room for '+ref)
  _,x,y,angle,side=best;put(ref,x,y,angle,side)
 # Collision audit, checking physical pad/body rectangles and cross-side drill pads.
 overlaps=[]
 for side,obs in obstacles.items():
  for (a,aa),(b,bb) in itertools.combinations(obs,2):
   if a.split('.')[0]==b.split('.')[0]:continue
   dx=min(aa[2],bb[2])-max(aa[0],bb[0]);dy=min(aa[3],bb[3])-max(aa[1],bb[1])
   if dx>1e-5 and dy>1e-5:overlaps.append([side,a,b,dx,dy])
 output={'board':{'width':W,'height':H,'thickness':1.6,'layers':4},'convention':'Original F.Cu footprint local coordinates; for B.Cu call Flip(position, False) then SetOrientationDegrees(rotation); x/y is footprint origin in mm. Confirm actual transformed bbox because KiCad API orientation convention can differ.','clearance_between_envelopes_mm':GAP,'warnings':['Placement-only; no routing or electrical signoff. J4 has no STEP in source. U9-U12 require corrected SOT553; official copper envelope 1.85x1.30mm used.','Four mounting holes omitted: no electrical nets or required mounting interface. R5/R6 removed with approved equivalent R4=31.2k divider.','OBD-C ports have >=11.3mm center spacing; mating overmold dimensions must be checked against the actual required cable.','J1/J2/J3 model transformations and connector mouths require STEP visual verification.'],'width_mm':W,'height_mm':H,'placements':{r:{'x_mm':placed[r]['x'],'y_mm':placed[r]['y'],'rotation_deg':placed[r]['rotation'],'side':'top' if placed[r]['side']=='F.Cu' else 'bottom'} for r in sorted(placed)},'placement_details':[placed[r] for r in sorted(placed)],'omitted':[{'ref':r,'reason':'Unconnected M2 mounting hole; no required mounting-pattern interface documented.'} for r in rows if r.startswith('BH')]+[{'ref':r,'reason':'Approved equivalent R4=31.2k divider removes parallel100k parts.'} for r in ('R5','R6')],'overlaps':overlaps,'summary':{'placed_count':len(placed),'side_counts':dict(collections.Counter(p['side'] for p in placed.values())),'occupied_envelope_area':sum(math.prod(rows[r]['size']) for r in placed)}}
 (ROOT/'reports/placement-45x42.json').write_text(json.dumps(output,indent=2));print(output['summary']);print('overlaps',overlaps)
 # standalone SVG plan with readable major labels; output no media manipulation.
 colors={'F.Cu':'#ef8354','B.Cu':'#4f9da6'};svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1150" height="600" viewBox="-2 -6 98 51"><rect x="-2" y="-6" width="98" height="51" fill="#101826"/>']
 for side,offset in [('F.Cu',0),('B.Cu',49)]:
  svg.append(f'<text x="{offset}" y="-2" fill="white" font-family="sans-serif" font-size="2">{side} · 45 × 42 mm</text><rect x="{offset}" y="0" width="45" height="42" fill="#182d38" stroke="#fff" stroke-width=".1"/>')
  for ref,p in placed.items():
   if p['side']!=side:continue
   b=p['bounds'];x,y=b[:2];w,h=np.array(b[2:])-b[:2]
   svg.append(f'<rect x="{x+offset}" y="{y}" width="{w}" height="{h}" fill="{colors[side]}" fill-opacity=".65" stroke="{colors[side]}" stroke-width=".08"><title>{ref}</title></rect>')
   if w*h>7:svg.append(f'<text x="{x+w/2+offset}" y="{y+h/2+.35}" text-anchor="middle" font-family="sans-serif" font-size=".9" fill="white">{ref}</text>')
  for ref,b in obstacles[side]:
   if '.drill' not in ref:continue
   svg.append(f'<rect x="{b[0]+offset}" y="{b[1]}" width="{b[2]-b[0]}" height="{b[3]-b[1]}" fill="#ff4455"/>')
 svg.append('</svg>');(ROOT/'reports/placement-45x42.svg').write_text(''.join(svg))
if __name__=='__main__':main()
