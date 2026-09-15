"""USB pair endpoint positions and hub orientation cost for a placement plan."""
import sys
from placement_analysis import *
from pathlib import Path
planpath=Path(sys.argv[1]);plan=json.loads(planpath.read_text());pl=plan['placements'];board=sx.loads((ROOT/'pcbgolf.kicad_pcb').read_text());fps={property_map(fp)['Reference']:fp for fp in children(board,'footprint')}
def endpoints(override=None):
 nets=collections.defaultdict(list)
 for ref,p in pl.items():
  if ref not in fps:continue
  for pad in children(fps[ref],'pad'):
   net=first(pad,'net',[None,None])[-1]
   if net not in names:continue
   pos=np.array(first(pad,'at',[None,0,0])[1:3]);
   if p['side']=='bottom':pos[1]*=-1
   angle=override if ref=='U4' and override is not None else p['rotation_deg'];xy=rot2([pos],angle)[0]+[p['x_mm'],p['y_mm']]
   nets[net].append({'ref':ref,'pad':str(pad[1]),'x_mm':round(float(xy[0]),5),'y_mm':round(float(xy[1]),5),'side':p['side']})
 return nets
names=['USB_D_P','USB_D_N','STM_D_P','STM_D_N']+[f'CH{i}_D_{pn}' for i in range(1,5) for pn in ('P','N')]
ep=endpoints();out={'placement':str(planpath),'nets':dict(ep),'u4_rotation_costs':{}}
for angle in (0,90,180,270):
 cost=0
 for net,ee in endpoints(angle).items():
  hub=[e for e in ee if e['ref']=='U4'];other=[e for e in ee if e['ref']!='U4']
  if hub and other:
   xy=np.mean([[e['x_mm'],e['y_mm']] for e in other],0);cost+=sum(abs(np.array([h['x_mm'],h['y_mm']])-xy).sum() for h in hub)
 out['u4_rotation_costs'][str(angle)]=round(float(cost),3)
# Group bus endpoint clusters for human route-order planning.
out['pair_groups']=[]
for basename in ['USB_D','STM_D']+[f'CH{i}_D' for i in range(1,5)]:
 centers=collections.defaultdict(list)
 for net in [basename+'_P',basename+'_N']:
  for e in ep[net]:centers[e['ref']].append([e['x_mm'],e['y_mm']])
 out['pair_groups'].append({'pair':basename,'centers_mm':{r:np.mean(pts,0).tolist() for r,pts in centers.items()}})
output=ROOT/'reports/usb-route-corridors.json';output.write_text(json.dumps(out,indent=2));print(json.dumps({'pair_groups':out['pair_groups'],'u4_rotation_costs':out['u4_rotation_costs']},indent=2))
