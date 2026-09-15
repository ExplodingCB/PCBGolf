"""Compact placement feasibility from source pad/body geometry; never mutates source."""
from pathlib import Path
import itertools, json, math, collections
import numpy as np
import sexpdata as sx
from scipy.spatial.transform import Rotation
ROOT=Path(__file__).resolve().parents[1]
def tag(x):return str(x[0]) if isinstance(x,list) and x else None
def children(x,t):return [v for v in x if tag(v)==t]
def first(x,t,default=None):return next((v for v in x if tag(v)==t),default)
def property_map(x):return {v[1]:v[2] for v in children(x,'property')}
def xyz(x,t,default):
 a=first(x,t)
 return np.array(first(a,'xyz')[1:],float) if a else np.array(default,float)
def rot2(points,deg):
 r=math.radians(deg);m=np.array([[math.cos(r),math.sin(r)],[-math.sin(r),math.cos(r)]])
 return np.asarray(points)@m.T

def inspect():
 board=sx.loads((ROOT/'pcbgolf.kicad_pcb').read_text(encoding='utf-8'))
 models=json.loads((ROOT/'reports/model-bounds.json').read_text())
 result=[]
 for fp in children(board,'footprint'):
  p=property_map(fp);ref=p['Reference']; body=[]; copper=[]; drills=[]; outline=[]; model_z=[]
  for model in children(fp,'model'):
   key=model[1].replace('${KIPRJMOD}/','')
   if key not in models:continue
   b=models[key]['bounds'];points=np.array(list(itertools.product(*[(b[i],b[i+3]) for i in range(3)])))
   # KiCad uses clockwise model rotations. Reverse Euler composition as well.
   points=Rotation.from_euler('ZYX',-xyz(model,'rotate',[0,0,0])[::-1],degrees=True).apply(points*xyz(model,'scale',[1,1,1]))+xyz(model,'offset',[0,0,0])
   points[:,1]*=-1
   body.extend(points[:,:2]);model_z.extend(points[:,2])
  for pad in children(fp,'pad'):
   at=first(pad,'at',[None,0,0]);size=first(pad,'size',[None,0,0]);w,h=map(float,size[1:]);pos=np.array(at[1:3],float)
   pts=rot2([[-w/2,-h/2],[-w/2,h/2],[w/2,-h/2],[w/2,h/2]],float(at[3]) if len(at)>3 else 0)+pos
   copper.extend(pts)
   if str(pad[2]) in ('thru_hole','np_thru_hole'):drills.append({'at':pos.tolist(),'size':[w,h],'type':str(pad[2]),'pad':str(pad[1])})
  for shape in fp:
   if tag(shape) not in ('fp_line','fp_rect','fp_arc','fp_circle'):continue
   layer=first(shape,'layer',[None,''])[1]
   if layer not in ('F.CrtYd','B.CrtYd','F.Fab','B.Fab','F.SilkS','B.SilkS'):continue
   for t in ('start','end','mid'):
    a=first(shape,t)
    if a:outline.append(a[1:3])
  def bbox(points):
   if not len(points):return None
   a=np.asarray(points);return np.round(np.r_[a.min(axis=0),a.max(axis=0)],5).tolist()
  # Prefer physical model and pads; use outline for missing model/header.
  envelope=bbox(body+copper+(outline if not body else []))
  row={'ref':ref,'value':p['Value'],'footprint':fp[1],'body_bounds':bbox(body),'pad_bounds':bbox(copper),'outline_bounds':bbox(outline),'envelope':envelope,'z':[round(min(model_z),5),round(max(model_z),5)] if model_z else None,'drills':drills,'nets':{str(a[1]):first(a,'net',[None,None])[-1] for a in children(fp,'pad') if first(a,'net')}}
  row['size']=[round(envelope[2]-envelope[0],5),round(envelope[3]-envelope[1],5)]
  result.append(row)
 (ROOT/'reports/placement-geometry.json').write_text(json.dumps(result,indent=2))
 groups=collections.defaultdict(list)
 for r in result:groups[r['footprint']].append(r)
 print('Bare occupied pad/body rectangle areas:')
 total=0
 for k,rs in sorted(groups.items(),key=lambda kv:-kv[1][0]['size'][0]*kv[1][0]['size'][1]*len(kv[1])):
  r=rs[0];area=math.prod(r['size'])*len(rs);total+=area
  print(k,len(rs),r['size'],'area',round(area,2),'z',r['z'])
 print('TOTAL',total)
 return result
if __name__=='__main__':inspect()
