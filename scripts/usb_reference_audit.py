"""Audit actual filled copper under each USB trace, with explicit antipads."""
import argparse,json,math
from pathlib import Path
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser()
ap.add_argument('--geometry',type=Path,default=root/'reports/usb-native-permuted.json')
ap.add_argument('--plan',type=Path,default=root/'reports/usb-paired-routes.json')
ap.add_argument('--zones',type=Path,default=root/'reports/usb-filled-zones.json')
ap.add_argument('--output',type=Path,default=root/'reports/usb-reference-audit.json')
args=ap.parse_args()
g=json.loads(args.geometry.read_text());F=g['layers']['F.Cu']
p=json.loads(args.plan.read_text())
z=json.loads(args.zones.read_text())
fills={l:unary_union([Polygon(q['shell'],q['holes']).buffer(0) for zone in z['zones'] if zone['layer']==l for q in zone['polygons']]) for l in [4,6]}
antipads=[]
for v in g['tracks']+p['vias']:
 if v.get('type','via')!='via' or v['net']=='GND':continue
 radius=v.get('diameter',v.get('width'))/2+.10
 antipads.append(dict(kind='via',net=v['net'],pos=v['pos'],radius=radius,shape=Point(v['pos']).buffer(radius+.012)))
for pad in g['pads']:
 if not pad['hole']:continue
 if pad['net']=='GND':continue
 for poly in pad['hole']:
  shape=Polygon(poly).buffer(.30 if pad['net'] else .20)
  antipads.append(dict(kind='plated_pad' if pad['net'] else 'NPTH',ref=pad['ref'],pad=pad['pad'],net=pad['net'],pos=pad['pos'],shape=shape.buffer(.012)))
# KiCad removes copper necks below the configured 0.15 mm zone minimum.
# Close antipad gaps by half that width, retaining every exception explicitly.
exceptions=unary_union([a['shape'] for a in antipads]).buffer(.075).buffer(-.075);rows=[]
for i,t in enumerate(p['tracks']):
 ref=4 if t['layer']==F else 6
 line=LineString([t['a'],t['b']]);corridor=line.buffer(.25)
 missing=corridor.difference(fills[ref].buffer(.003));unexpected=missing.difference(exceptions)
 rows.append(dict(track_index=i,net=t['net'],layer=t['layer'],reference_layer=ref,length_mm=line.length,missing_area_mm2=missing.area,unexplained_missing_area_mm2=unexpected.area,unexplained_bounds=list(unexpected.bounds) if not unexpected.is_empty else None,exceptions=[{k:v for k,v in a.items() if k!='shape'} for a in antipads if a['shape'].intersects(missing)]))
bad=[r for r in rows if r['unexplained_missing_area_mm2']>.0001]
result=dict(board=z['board'],corridor_half_width_mm=.25,numeric_fill_tolerance_mm=.003,antipad_polygon_tolerance_mm=.012,zone_minimum_neck_width_mm=.15,tracks=len(rows),bad_track_count=len(bad),bad_tracks=bad,all_tracks=rows,return_vias=z['returns'],all_returns_connected=all(r['native_connected_in1'] and r['native_connected_in2'] for r in z['returns']))
args.output.write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('all_tracks','return_vias','bad_tracks')},indent=2))
