import json,sys
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
input_path=Path(sys.argv[1] if len(sys.argv)>1 else 'reports/placement-45x42.json');j=json.loads(input_path.read_text());width=j['width_mm'];height=j['height_mm'];fig,axs=plt.subplots(1,2,figsize=(14,7));fig.patch.set_facecolor('#101826')
for ax,side in zip(axs,['F.Cu','B.Cu']):
 ax.set_facecolor('#182d38');ax.set_aspect('equal');ax.set_xlim(-1,width+1);ax.set_ylim(height+1,-2 if j.get('plug_envelopes') else -1);ax.set_title(f'{side} - {width:g} x {height:g} mm',color='white',fontsize=16);ax.tick_params(colors='white');ax.add_patch(Rectangle((0,0),width,height,fill=False,edgecolor='white',linewidth=2))
 for p in j['placement_details']:
  if p['side']!=side:continue
  b=p['bounds'];w=b[2]-b[0];h=b[3]-b[1];color='#ef8354' if side=='F.Cu' else '#4f9da6'
  ax.add_patch(Rectangle((b[0],b[1]),w,h,facecolor=color,edgecolor='#ddd',linewidth=.35,alpha=.8))
  if w*h>3:ax.text((b[0]+b[2])/2,(b[1]+b[3])/2,p['ref'],ha='center',va='center',color='white',fontsize=7 if w*h>8 else 4.5)
 if side=='F.Cu':
  for plug in j.get('plug_envelopes',[]):
   b=plug['bounds'];ax.add_patch(Rectangle((b[0],b[1]),b[2]-b[0],b[3]-b[1],fill=False,edgecolor='#ffdd65',linestyle='--',linewidth=1.5))
  if j.get('plug_envelopes'):ax.text(.5,height+.65,'Dashed: elevated 12.5 x 7 mm cable bodies',color='#ffdd65',fontsize=8)
 ax.set_xlabel('mm',color='white');ax.set_ylabel('mm',color='white')
fig.tight_layout();fig.savefig(input_path.with_suffix('.png'),dpi=160,facecolor=fig.get_facecolor());print(input_path.with_suffix('.png'))
