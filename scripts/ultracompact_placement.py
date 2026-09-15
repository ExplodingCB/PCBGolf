"""Greedy, net-attracted physical placement. JSON uses KiCad Flip(pos, False) then angle."""
from placement_analysis import *
from scipy.linalg import solve
PITCH=.25;W=45.;H=35.;GAP=.20;EDGE=.40

def main():
 rows=json.loads((ROOT/'reports/placement-geometry.json').read_text());rows={r['ref']:r for r in rows}
 rows['J1']['envelope']=[-5.,-8.5,9.9,8.5];rows['J1']['size']=[14.9,17.]
 # Proposed corrected package from NCS20071XV datasheet; circuit agent's library is authoritative.
 for ref in ['U9','U10','U11','U12']:
  rows[ref]['envelope']=[-.925,-.65,.925,.65];rows[ref]['size']=[1.85,1.3];rows[ref]['body_bounds']=[-.6,-.425,.6,.425]
  rows[ref]['footprint']='pcbgolf:SOT-553';rows[ref]['requires_footprint_correction']=True
  # Exact newly verified host USB2 and SMA TVS footprints/model envelopes.
 replacements={}
 replacement_models=json.loads((ROOT/'reports/replacement-model-bounds.json').read_text())
 for ref,name in {'J3':'USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal','D1':'D_SMA'}.items():
  fp=sx.loads((ROOT/'pcbgolf.pretty'/f'{name}.kicad_mod').read_text());replacements[ref]=fp
  oldnets=rows[ref]['nets'];points=[];drills=[];body=[]
  for model in children(fp,'model'):
   b=replacement_models[model[1].replace('${KIPRJMOD}/','')]['bounds'];body.extend([[b[0],-b[1]],[b[0],-b[4]],[b[3],-b[1]],[b[3],-b[4]]])
  for pad in children(fp,'pad'):
   a=first(pad,'at',[None,0,0]);xy=np.array(a[1:3]);wh=np.array(first(pad,'size')[1:]);pts=np.array([[-1,-1],[-1,1],[1,-1],[1,1]])*wh/2
   pts=rot2(pts,float(a[3]) if len(a)>3 else 0)+xy;points.extend(pts)
   if str(pad[2]) in ('thru_hole','np_thru_hole'):drills.append({'at':xy.tolist(),'size':wh.tolist(),'type':str(pad[2]),'pad':str(pad[1])})
   net='GND' if str(pad[1])=='SH' else oldnets.get(str(pad[1]))
   if net:pad.append([sx.Symbol('net'),net])
  pts=np.array(points+body);rows[ref]['envelope']=np.r_[pts.min(0),pts.max(0)].tolist();rows[ref]['size']=(pts.max(0)-pts.min(0)).tolist();rows[ref]['drills']=drills;rows[ref]['footprint']='pcbgolf:'+name
 # Preserve actual existing assembly courtyards, rather than shrinking DRC geometry.
 source_board=sx.loads((ROOT/'pcbgolf.kicad_pcb').read_text(encoding='utf-8'))
 originals={property_map(fp)['Reference']:fp for fp in children(source_board,'footprint')}
 for ref,row in rows.items():
  fp=replacements.get(ref,originals[ref])
  if ref in ('U9','U10','U11','U12'):fp=sx.loads((ROOT/'pcbgolf.pretty/SOT-553.kicad_mod').read_text())
  if ref=='J1':fp=sx.loads((ROOT/'pcbgolf.pretty/PJ-002AH-SMT-TR.kicad_mod').read_text())
  pts=[]
  for shape in fp:
   if tag(shape) not in ('fp_line','fp_rect','fp_arc'):continue
   if not str(first(shape,'layer',[None,''])[1]).endswith('CrtYd'):continue
   for name in ('start','end','mid'):
    a=first(shape,name)
    if a:pts.append(a[1:3])
  if pts:
   pts=np.array(pts);b=row['envelope'];row['physical_envelope']=b.copy();row['envelope']=np.r_[np.minimum(b[:2],pts.min(0)),np.maximum(b[2:],pts.max(0))].tolist();row['size']=(np.array(row['envelope'][2:])-row['envelope'][:2]).tolist()
  else:
   b=np.array(row['envelope']);b[:2]-=.125;b[2:]+=.125;row['envelope']=b.tolist();row['size']=(b[2:]-b[:2]).tolist()
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
 put('U3',15.6,18.6,0,'B.Cu')
 for ref,x in zip(['J5','J6','J7','J8'],[5.,16.7,28.3,40.]):put(ref,x,3.4 if ref in ('J7','J8') else 4.)
 put('J1',39.5,15.2,180,by_origin=True) # open barrel faces right edge
 put('J3',41.325,29.5,90,by_origin=True) # USB-C mouth exactly at bottom outline
 put('J4',30.,32.3)
 put('SW1',6.5,31.3)
 put('J2',1.31074,26.625,270,'F.Cu',True) # microSD mouth reaches left edge
 put('U4',21.5,19.,270,'F.Cu')
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
 caps={**{f'C{i}':'U1' for i in [1,2,4,6,7,8]},**{f'C{i}':'U2' for i in [3,5,9,10,11,12,13]},**{f'C{i}':'U3' for i in range(14,26)},**{f'C{i}':'U4' for i in list(range(26,29))+list(range(30,38))},'C29':'J3'}
 for i in range(38,46):caps[f'C{i}']=f'U{5+(i-38)%4}'
 for i in range(46,54):caps[f'C{i}']=f'U{13+(i-46)%4}'
 for c,u in caps.items():weights[idx[c],idx[u]]+=3;weights[idx[u],idx[c]]+=3
 anchor_centers={'U1':(33,21),'U2':(39,21),'U5':(17,27),'U6':(22,27),'U7':(27,27),'U8':(32,27),'U9':(7,9),'U10':(17,9),'U11':(28,9),'U12':(39,9),'U13':(7,9.4),'U14':(17,9.4),'U15':(25,9.4),'U16':(39,9.4)}
 targets=np.tile([W/2,H/2],(len(refs),1));fixed_refs=set(placed)|set(anchor_centers)
 for ref,p in placed.items():targets[idx[ref]]=p['center']
 for ref,xy in anchor_centers.items():targets[idx[ref]]=xy
 known=[idx[r] for r in fixed_refs];unknown=[idx[r] for r in refs if r not in fixed_refs]
 lap=np.diag(weights.sum(1)+.01)-weights
 targets[unknown]=solve(lap[np.ix_(unknown,unknown)],-lap[np.ix_(unknown,known)]@targets[known]+.01*np.tile([W/2,H/2],(len(unknown),1)))
 # Exact pad locations let decouplers seek their relevant power pins.
 source=sx.loads((ROOT/'pcbgolf.kicad_pcb').read_text(encoding='utf-8'))
 pads_by_ref={property_map(fp)['Reference']:children(fp,'pad') for fp in children(source,'footprint')}
 pads_by_ref.update({ref:children(fp,'pad') for ref,fp in replacements.items()})
 special_hosts={'L1':'U1','L2':'U2','Y1':'U3','Y2':'U4','L3':'U3','L4':'U3','C25':'U3','R11':'U3',**caps}
 forced_bottom=set(['U1','U2','Q1','D2','R2','L1','L2','R1','R3','R4','R7','R8','R9','R10']+[c for c,u in caps.items() if u in ('U1','U2')])
 pin_usage=collections.Counter()
 def desired_pad_target(ref,host):
  hp=placed[host];matching=[];other_nets=set(rows[ref]['nets'].values())-{'GND'}
  if ref in ('L4','C25'):other_nets={'VLXSMPS'}
  if ref=='L3':other_nets={'VDDA'}
  if ref=='L1':other_nets={'Net-(U1-SW)'}
  if ref=='L2':other_nets={'Net-(U2-SW)'}
  for pad in pads_by_ref[host]:
   net=first(pad,'net',[None,None])[-1]
   if net not in other_nets:continue
   a=first(pad,'at',[None,0,0]);xy=np.array(a[1:3],float)
   if hp['side']=='B.Cu':xy[1]*=-1
   xy=rot2([xy],hp['rotation'])[0]+[hp['x'],hp['y']]
   matching.append((pin_usage[(host,pad[1])],str(pad[1]),xy))
  if not matching:return np.array(hp['center'])
  _,pin,xy=min(matching,key=lambda p:(p[0],p[1]));pin_usage[(host,pin)]+=1
  delta=xy-np.array(hp['center']);axis=int(np.argmax(abs(delta)));xy[axis]+=math.copysign(1.3,delta[axis])
  return xy
 # Place large critical ICs first then local networks, LEDs top to keep visible.
 unplaced=set(refs)-set(placed)
 grids=np.meshgrid(np.arange(EDGE,W-EDGE+.01,PITCH),np.arange(EDGE,H-EDGE+.01,PITCH));xs,ys=grids
 while unplaced:
  def priority(ref):
   r=rows[ref];area=math.prod(r['size']);connected=sum(weights[idx[ref],idx[p]] for p in placed)
   return (4500 if ref in ('L1','L2') and special_hosts[ref] in placed else 0)+(5000 if ref in ('Y1','Y2','L4','L3') else 0)+(3000 if ref in special_hosts and special_hosts[ref] in placed else 0)+(2000 if ref in ('L5','L6','L7','L8','D1') else 0)+(1000 if ref in anchor_centers else 0)+(100 if area>9 else 0)+connected*4+area
  ref=max(unplaced,key=lambda r:(priority(r),r));unplaced.remove(ref);r=rows[ref]
  prefs=['F.Cu','B.Cu'] if ref.startswith('LED') else ['B.Cu','F.Cu']
  if ref in ('L5','L6','L7','L8','D1'):prefs=['F.Cu']
  if ref in forced_bottom:prefs=['B.Cu']
  if ref in special_hosts and special_hosts[ref] in placed:prefs=[placed[special_hosts[ref]]['side']]
  # underside bypass capacitors may sit directly below their MCU pads; low via count wins later routing.
  target=targets[idx[ref]].copy();attract=[]
  if ref in special_hosts and special_hosts[ref] in placed:target=desired_pad_target(ref,special_hosts[ref])
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
    cost=(10 if ref in special_hosts else 1.5)*(abs(xs-target[0])+abs(ys-target[1]))
    for wgt,xy in attract:cost+=wgt*(abs(xs-xy[0])+abs(ys-xy[1]))/max(1,len(attract))
    if side=='F.Cu' and not ref.startswith('LED'):cost+=2.0
    if side=='B.Cu' and ref.startswith('LED'):cost+=12.0
    cost=np.where(good,cost,np.inf);k=np.argmin(cost);v=float(cost.flat[k])
    if best is None or v<best[0]:best=(v,float(xs.flat[k]),float(ys.flat[k]),angle,side)
  if best is None:raise RuntimeError('No room for '+ref)
  _,x,y,angle,side=best;put(ref,x,y,angle,side)
 # Collision audit, checking physical pad/body rectangles and cross-side drill pads.
 overlaps=[];corner_exceptions=[]
 from shapely.geometry import LineString,box
 from shapely.ops import polygonize,unary_union
 lines=[];hp=placed['U3']
 for shape in originals['U3']:
  if tag(shape)!='fp_line' or str(first(shape,'layer',[None,''])[1])!='F.CrtYd':continue
  pts=np.array([first(shape,'start')[1:3],first(shape,'end')[1:3]])
  if hp['side']=='B.Cu':pts[:,1]*=-1
  pts=rot2(pts,hp['rotation'])+[hp['x'],hp['y']];lines.append(LineString(pts))
 true_mcu_courtyard=unary_union(list(polygonize(unary_union(lines)))).buffer(.025)

 for side,obs in obstacles.items():
  for (a,aa),(b,bb) in itertools.combinations(obs,2):
   if a.split('.')[0]==b.split('.')[0]:continue
   dx=min(aa[2],bb[2])-max(aa[0],bb[0]);dy=min(aa[3],bb[3])-max(aa[1],bb[1])
   if dx>1e-5 and dy>1e-5:
    if {a,b}=={'U3','J4.drill'}:
     rr=bb if b=='J4.drill' else aa
     if true_mcu_courtyard.disjoint(box(*rr).buffer(GAP)):
      corner_exceptions.append([side,a,b,'J4 plated pad lies in empty notched U3 courtyard corner; polygon separation verified.']);continue
    overlaps.append([side,a,b,dx,dy])
 output={'board':{'width':W,'height':H,'thickness':1.6,'layers':4},'convention':'Original F.Cu footprint local coordinates; for B.Cu call Flip(position, False) then SetOrientationDegrees(rotation); x/y is footprint origin in mm. Confirm actual transformed bbox because KiCad API orientation convention can differ.','clearance_between_envelopes_mm':GAP,'warnings':['Verified-library host J3 GCT USB4105 USB2, corrected D1 SMA; MCU bottom, hub/SD/chokes/TVS top. Some LEDs may be on bottom. Both regulators and local loops bottom.','Courtyard-aware placement preserves all source/corrected library courtyards and adds0.05mm gap. Refined placement with U3rotation180, same-side bypasses/crystals and same-side regulator loops. J1correctedPJ-002AH-SMT-TR17mm pad span from manufacturer drawing. Placement-only; no routing or electrical signoff. J4 has no STEP in source. U9-U12 require corrected SOT553; full corrected SOT553 courtyard used.','Four mounting holes omitted: no electrical nets or required mounting interface. R5/R6 removed with approved equivalent R4=31.2k divider.','OBD-C ports have >=11.3mm center spacing; mating overmold dimensions must be checked against the actual required cable.','J1/J2/J3 model transformations and connector mouths require STEP visual verification.'],'width_mm':W,'height_mm':H,'placements':{r:{'x_mm':placed[r]['x'],'y_mm':placed[r]['y'],'rotation_deg':placed[r]['rotation'],'side':'top' if placed[r]['side']=='F.Cu' else 'bottom'} for r in sorted(placed)},'placement_details':[placed[r] for r in sorted(placed)],'omitted':[{'ref':r,'reason':'Unconnected M2 mounting hole; no required mounting-pattern interface documented.'} for r in rows if r.startswith('BH')]+[{'ref':r,'reason':'Approved equivalent R4=31.2k divider removes parallel100k parts.'} for r in ('R5','R6')],'overlaps':overlaps,'corner_exceptions':corner_exceptions,'summary':{'placed_count':len(placed),'side_counts':dict(collections.Counter(p['side'] for p in placed.values())),'occupied_envelope_area':sum(math.prod(rows[r]['size']) for r in placed)}}
 (ROOT/'reports/placement-45x35-usb2.json').write_text(json.dumps(output,indent=2));print(output['summary']);print('overlaps',overlaps)
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
 svg.append('</svg>');(ROOT/'reports/placement-45x35-usb2.svg').write_text(''.join(svg))
if __name__=='__main__':main()
