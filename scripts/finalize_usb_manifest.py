"""Record exact critical-USB fabrication reservations and evidence hashes."""
import json,hashlib,collections
from pathlib import Path
from shapely.geometry import Point,Polygon
from shapely.ops import unary_union
ROOT=Path(__file__).resolve().parents[1]
planpath=ROOT/'reports/usb-paired-routes.json';p=json.loads(planpath.read_text())
g=json.loads((ROOT/'reports/usb-native-permuted.json').read_text())
for v in p['vias']:
 hits=[];hole=Point(v['pos']).buffer(v['drill']/2)
 for pad in g['pads']:
  if any(hole.intersects(Polygon(poly)) for l in ['0','2'] for poly in pad['polygons'].get(l,[])):
   hits.append(dict(reference=pad['ref'],pad=pad['pad'],net=pad['net']))
 v['filled_and_capped']=bool(v.get('filled_and_capped') or hits)
 v['overlapping_component_pads']=hits
p['source']='candidates/bga100-power-escape-usb-reserved/pcbgolf.kicad_pcb'
p['reference_audit']['reference_layers']['bottom']='In2.Cu priority100 local GND'
p['fabrication']=dict(stackup='JLC04161H-3313',board_thickness_mm=1.6,track_width_mm=.11,edge_gap_mm=.10,calculated_differential_ohms=90.158064,via_diameter_mm=.40,via_drill_mm=.20,filled_and_capped_required_count=sum(v['filled_and_capped'] for v in p['vias']),process='POFV: resin-filled, planarized, copper-capped through vias at every flagged location',reference_zones_priority=100)
p['limits']=['Geometry and logical connectivity validated; whole-board routing remains incomplete.','Centerline length audit omits travel within pads and is not an electromagnetic simulation.','Every listed via-in-pad requires filled and copper-capped fabrication.','Any later copper or placement changes require native DRC, path analysis, and filled-reference audit again.']
planpath.write_text(json.dumps(p,indent=2))
paths=['candidates/bga100-power-escape-usb-reserved/pcbgolf.kicad_pcb','candidates/compact-v6-usb/pcbgolf.kicad_pcb','reports/usb-paired-routes.json','reports/usb-native-path-analysis.json','reports/usb-reference-audit.json','candidates/compact-v6-usb/drc-usb.json']
manifest=dict(hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in paths},usb_track_segments=len(p['tracks']),signal_vias=sum(v['net']!='GND' for v in p['vias']),ground_return_vias=sum(v['net']=='GND' for v in p['vias']),in2_reference_patches=len(p['zones']),filled_and_capped_required=[v for v in p['vias'] if v['filled_and_capped']],fabrication=p['fabrication'])
(ROOT/'reports/usb-critical-manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps({k:v for k,v in manifest.items() if k!='filled_and_capped_required'},indent=2))
