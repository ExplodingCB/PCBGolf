"""Preserve USB reference copper with track keepouts on adjacent inner layers."""
import argparse,json,shutil
from pathlib import Path
import pcbnew as p
from shapely.geometry import LineString
from shapely.ops import unary_union
from route_ground import track_shape,xy
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('board',type=Path);ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args();assert a.board.resolve()!=a.out.resolve()
b=p.LoadBoard(str(a.board));plan=json.loads((ROOT/'reports/usb-paired-routes.json').read_text())
regions={layer:unary_union([LineString([t['a'],t['b']]).buffer(.26,quad_segs=8)
    for t in plan['tracks'] if (p.In1_Cu if t['layer']==p.F_Cu else p.In2_Cu)==layer])
    for layer in (p.In1_Cu,p.In2_Cu)}
retired=[];removed=[]
for t in list(b.GetTracks()):
    if isinstance(t,p.PCB_VIA):
        t.SetIsFree(True)
        continue
    if t.GetLayer() in regions and track_shape(t).buffer(.102).intersects(regions[t.GetLayer()]):
        removed.append({'uuid':t.m_Uuid.AsString(),'net':t.GetNetname(),'a':xy(t.GetStart()),'b':xy(t.GetEnd())})
        retired.append(t);b.Remove(t)
for layer,region in regions.items():
    shapes=list(region.geoms) if region.geom_type=='MultiPolygon' else [region]
    for i,shape in enumerate(shapes):
        z=p.ZONE(b);z.SetLayer(layer);z.SetIsRuleArea(True)
        z.SetZoneName('USB adjacent ground reference '+str(layer)+'-'+str(i))
        z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(False);z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False);z.SetDoNotAllowZoneFills(False)
        poly=z.Outline();poly.NewOutline()
        for x,y in list(shape.exterior.coords)[:-1]:poly.Append(p.FromMM(x),p.FromMM(y))
        for ring in shape.interiors:
            hole=poly.NewHole(0)
            for x,y in list(ring.coords)[:-1]:poly.Append(p.FromMM(x),p.FromMM(y),0,hole)
        b.Add(z)
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(a.out),b)
for suffix in ('.kicad_pro','.kicad_dru'):
    shutil.copy2(a.board.with_suffix(suffix),a.out.with_suffix(suffix))
a.out.with_suffix('.reference-repair.json').write_text(json.dumps({'removed_tracks':removed},indent=2))
print(json.dumps({'tracks_removed_from_reference_copper':len(removed)}))
