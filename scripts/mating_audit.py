"""Conservative 3D mating-envelope audit; elevated plugs can overhang short components."""
from pathlib import Path
import sys,json,itertools,math
import numpy as np
planpath=Path(sys.argv[1]);plan=json.loads(planpath.read_text());placements=plan['placements']
plug_width,plug_thickness=12.5,7.;plug_z=1.595+8.6
plugs=[]
for ref in ('J5','J6','J7','J8'):
 p=placements[ref];a=math.radians(p['rotation_deg']);w=abs(math.cos(a))*plug_width+abs(math.sin(a))*plug_thickness;h=abs(math.sin(a))*plug_width+abs(math.cos(a))*plug_thickness
 plugs.append({'name':ref+' mating plug','ref':ref,'bounds':[p['x_mm']-w/2,p['y_mm']-h/2,plug_z,p['x_mm']+w/2,p['y_mm']+h/2,plug_z+40]})
def signed_gap(a,b):
 a=np.array(a);b=np.array(b);sep=np.maximum(b[:3]-a[3:],a[:3]-b[3:]);return float(np.max(sep))
pair_gaps=[{'refs':[a['ref'],b['ref']],'separation_mm':signed_gap(a['bounds'],b['bounds'])} for a,b in itertools.combinations(plugs,2)]
model_conflicts=[];closest=None
if len(sys.argv)>2:
 models=json.loads(Path(sys.argv[2]).read_text())
 for plug in plugs:
  for model in models:
   if model['name']==plug['ref'] or model['name'] not in placements:continue
   b=model['bounds'];b=[b[0],-b[4],b[2],b[3],-b[1],b[5]];gap=signed_gap(plug['bounds'],b)
   item={'plug':plug['ref'],'component':model['name'],'separation_mm':gap}
   if closest is None or gap<closest['separation_mm']:closest=item
   if gap<-.001:model_conflicts.append(item)
result={'placement':str(planpath),'source':'https://www.usb.org/sites/default/files/USB%20Type-C_Compliance%20Document_Rev_2_1b_June_2021.pdf','source_table':'Table B-1, printed page49','usb_if_maximum_overmold_cross_section_mm':[12.35,6.5],'audit_overmold_cross_section_mm':[plug_width,plug_thickness],'overmold_z_min_global_mm':plug_z,'plugs':plugs,'pair_gaps':pair_gaps,'plug_pair_conflicts':[g for g in pair_gaps if g['separation_mm']<0],'actual_model_conflicts':model_conflicts,'closest_actual_component':closest,'limits':['Nominal exported component positions checked. Drawing/manufacturing tolerances and representative physical insertion/retention test remain required.','No comma-specific overmold drawing was found. Audit uses USB-IF full-featured Type-C maximum enlarged to12.5x7mm; custom oversized or unusual right-angle cable housings require their actual dimensions.','Cable bend space and the optional DNP J4 populated mating header are not represented by these straight-plug prisms.']}
out=Path('reports')/(planpath.stem+'-mating-audit.json');out.write_text(json.dumps(result,indent=2));print(json.dumps({'output':str(out),'pair_gaps':pair_gaps,'model_conflicts':model_conflicts,'closest_actual_component':closest},indent=2))
