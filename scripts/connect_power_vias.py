"""Connect isolated power pads to existing pours using checked filled/capped vias.

After filling, prune every proposed via whose removal preserves pad-group count.
All proposals still require native DRC and final power/return-current review.
"""
import argparse,json,shutil,math
from pathlib import Path
import pcbnew as p
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.prepared import prep
from route_ground import COPPER,xy,copper_shape,hole_shape,track_shape
from audit_net_connectivity import audit
ap=argparse.ArgumentParser();ap.add_argument('board',type=Path);ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args();assert a.board.resolve()!=a.out.resolve()
b=p.LoadBoard(str(a.board));initial=audit(b);pads=list(b.GetPads());padmap={q.m_Uuid.AsString():q for q in pads}
records=[];retired=[];added=[]
def fill():
    b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones())
def count():return audit(b)['missing_pad_group_connections']
for net,info in initial['nets'].items():
    if info['group_count']<=1 or not (net in ('GND','+12V','+5V','+3V3','VDDLDO','Net-(J1-PWR)') or 'VBUS-PadA4' in net):continue
    shapes=[];holes=[]
    for q in pads:
        if q.GetNetname()!=net:
            for layer in COPPER:
                if q.IsOnLayer(layer):
                    margin=.402 if q.GetAttribute()==p.PAD_ATTRIB_PTH else .302
                    shapes.append(copper_shape(q,layer).buffer(margin))
        if q.HasHole():
            h=hole_shape(q);holes.append(h.buffer(.301))
            if q.GetNetname()!=net:shapes.append(h.buffer(.502 if q.GetAttribute()==p.PAD_ATTRIB_PTH else .402))
    for t in b.GetTracks():
        if t.GetNetname()!=net:shapes.append(track_shape(t).buffer(.302))
        if isinstance(t,p.PCB_VIA):
            h=Point(xy(t.GetPosition())).buffer(p.ToMM(t.GetDrillValue())/2)
            holes.append(h.buffer(.301))
            if t.GetNetname()!=net:shapes.append(h.buffer(.402))
    blocked=prep(unary_union(shapes+holes));new=[]
    for group in info['groups']:
        candidate=None
        for row in sorted(group['pads'],key=lambda q:(q['ref'].startswith('U'),q['ref'])):
            q=padmap[row['uuid']]
            if q.GetAttribute()!=p.PAD_ATTRIB_SMD:continue
            land=copper_shape(q,q.GetParentFootprint().GetLayer());x,y=xy(q.GetPosition())
            for dx,dy in [(0,0),(.15,0),(-.15,0),(0,.15),(0,-.15)]:
                point=Point(x+dx,y+dy)
                if not (.502<point.x<44.498 and .502<point.y<36.498):continue
                if not land.covers(point.buffer(.105)) or blocked.intersects(point):continue
                if any(point.distance(Point(xy(v.GetPosition())))<.401 for v in new):continue
                candidate=(point,q);break
            if candidate:break
        if candidate is None:continue
        point,q=candidate
        v=p.PCB_VIA(b);v.SetPosition(p.VECTOR2I(p.FromMM(point.x),p.FromMM(point.y)))
        v.SetWidth(p.FromMM(.4));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH)
        v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(b.FindNet(net));v.SetIsFree(True);v.SetLocked(True);b.Add(v)
        new.append(v);added.append(v)
        records.append({'uuid':v.m_Uuid.AsString(),'net':net,'at_mm':xy(v.GetPosition()),'pad':q.GetParentFootprint().GetReference()+'.'+q.GetNumber(),'filled_and_capped_required':True})
    print(json.dumps({'net':net,'proposed':len(new)}),flush=True)
fill();best=count();kept=set(v.m_Uuid.AsString() for v in added)
for v in reversed(added):
    b.Remove(v);fill();now=count()
    if now<=best:
        retired.append(v);kept.remove(v.m_Uuid.AsString());best=now
    else:b.Add(v);fill()
report={'initial_missing_connections':initial['missing_pad_group_connections'],'final_missing_connections':best,
        'kept_vias':[r for r in records if r['uuid'] in kept],'rejected_vias':[r for r in records if r['uuid'] not in kept],
        'native_drc_required':True}
p.SaveBoard(str(a.out),b)
for suffix in ('.kicad_pro','.kicad_dru'):shutil.copy2(a.board.with_suffix(suffix),a.out.with_suffix(suffix))
a.out.with_suffix('.power-vias.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'connections_before':initial['missing_pad_group_connections'],'connections_after':best,'vias_retained':len(kept)}))
