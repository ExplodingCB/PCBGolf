"""Compare an exported assembly with a placement plan; exact conservative 3D boxes."""
from pathlib import Path
import sys,json,itertools,numpy as np
step_bounds=Path(sys.argv[1]);plan=Path(sys.argv[2]);j=json.loads(step_bounds.read_text());p=json.loads(plan.read_text());details={r['ref']:r for r in p['placement_details']};outside=[];collisions=[]
for r in j:
 ref=r['name'];b=r['bounds'];r['pcb_bounds']=[b[0],-b[4],b[3],-b[1]]
 if ref not in details:continue
 q=details[ref]['bounds'];xy=r['pcb_bounds'];over=[max(0,q[0]-xy[0]),max(0,q[1]-xy[1]),max(0,xy[2]-q[2]),max(0,xy[3]-q[3])]
 if max(over)>.02:outside.append({'ref':ref,'actual_xy':xy,'planned_xy':q,'excess_mm':over})
for a,b in itertools.combinations(j,2):
 if a['name'] not in details or b['name'] not in details:continue
 ba=np.array(a['bounds']);bb=np.array(b['bounds']);span=np.minimum(ba[3:],bb[3:])-np.maximum(ba[:3],bb[:3])
 if np.all(span>.001):collisions.append({'refs':[a['name'],b['name']],'bbox_intersection_mm':span.tolist()})
lo=np.min([r['bounds'][:3] for r in j],0);hi=np.max([r['bounds'][3:] for r in j],0);size=hi-lo
result={'candidate':str(step_bounds.parent),'global_bounds_mm':np.r_[lo,hi].tolist(),'size_mm':size.tolist(),'volume_mm3':float(np.prod(size)),'exported_models':len(j)-1,'outside_planned_envelopes':outside,'bbox_collisions':collisions,'scope':'AABB separation proves no intercomponent solid collisions for separated boxes. PCB/component lead penetration not checked because intended solder and plated-hole geometry overlaps board. Cable-plug clearance and mounting are separate functional checks.'}
out=Path('reports')/(step_bounds.parent.name+'-mechanical-audit.json');out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
