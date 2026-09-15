"""Audit actual filled copper connectivity; does not infer an ampacity rating."""
import argparse,json
from pathlib import Path
import pcbnew as pcb
from shapely.geometry import Polygon,Point
from shapely.ops import unary_union
from route_ground import xy,copper_shape,track_shape,hole_shape,COPPER

def filled_shape(poly):
    shapes=[]
    for i in range(poly.OutlineCount()):
        ring=poly.Outline(i)
        outer=[xy(ring.CPoint(j)) for j in range(ring.PointCount())]
        holes=[]
        for h in range(poly.HoleCount(i)):
            ring=poly.Hole(i,h)
            holes.append([xy(ring.CPoint(j)) for j in range(ring.PointCount())])
        if len(outer)>=3:shapes.append(Polygon(outer,holes).buffer(0))
    return unary_union(shapes)

def audit(b):
    result={};pads=list(b.GetPads());tracks=list(b.GetTracks())
    nets={'+12V','+5V','+3V3','VDDLDO','VLXSMPS','Net-(J1-PWR)','Net-(U1-SW)','Net-(U2-SW)'}|{p.GetNetname() for p in pads if p.GetParentFootprint().GetReference() in ['J5','J6','J7','J8'] and p.GetNumber()=='A4'}
    for net in sorted(nets):
        pp=[p for p in pads if p.GetNetname()==net];tt=[t for t in tracks if t.GetNetname()==net]
        parts=[];layer_ids={}
        for layer in COPPER:
            shapes=[copper_shape(p,layer) for p in pp if p.IsOnLayer(layer)]
            shapes +=[track_shape(t) for t in tt if isinstance(t,pcb.PCB_VIA) or t.GetLayer()==layer]
            shapes +=[filled_shape(z.GetFilledPolysList(layer)) for z in b.Zones() if z.GetNetname()==net and z.IsOnLayer(layer)]
            union=unary_union(shapes).buffer(.000005)
            geoms=list(union.geoms) if union.geom_type=='MultiPolygon' else ([union] if not union.is_empty else [])
            layer_ids[layer]=list(range(len(parts),len(parts)+len(geoms)))
            parts +=[(layer,g) for g in geoms]
        parent=list(range(len(parts)))
        def find(a):
            while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
            return a
        for item in pp+tt:
            if not (isinstance(item,pcb.PCB_VIA) or isinstance(item,pcb.PAD) and item.HasHole()):continue
            pt=Point(xy(item.GetPosition()));ids=[i for i,(l,s) in enumerate(parts) if s.intersects(pt)]
            for i in ids[1:]:parent[find(i)]=find(ids[0])
        groups={}
        for p in pp:
            layer=p.GetParentFootprint().GetLayer();pt=Point(xy(p.GetPosition()))
            ids=[i for i in layer_ids[layer] if parts[i][1].intersects(pt)]
            key=str(find(ids[0])) if ids else 'missing'
            groups.setdefault(key,[]).append(p.GetParentFootprint().GetReference()+'.'+p.GetNumber())
        result[net]={'pad_groups':list(groups.values()),'connected_pad_group_count':len(groups),'filled_area_by_layer_mm2':{b.GetLayerName(l):sum(parts[i][1].area for i in ids) for l,ids in layer_ids.items()}}
    thermal=[]
    for t in tracks:
        if not isinstance(t,pcb.PCB_VIA) or t.GetNetname()!='GND' or abs(pcb.ToMM(t.GetDrill())-.2)>.0001:continue
        if not any(p.GetParentFootprint().GetReference() in ['U13','U14','U15','U16'] and p.GetNumber()=='PAD' and copper_shape(p,p.GetParentFootprint().GetLayer()).contains(Point(xy(t.GetPosition()))) for p in pads):continue
        h=Point(xy(t.GetPosition())).buffer(.1)
        distances=[(h.distance(hole_shape(p)),p.GetParentFootprint().GetReference()+'.'+p.GetNumber()) for p in pads if p.HasHole()]
        d,ref=min(distances)
        thermal.append({'uuid':str(t.m_Uuid),'at_mm':xy(t.GetPosition()),'hole_mm':.2,'pad_mm':.4,'nearest_component_hole':ref,'hole_edge_separation_mm':d,'greater_than_0_45_mm':d>.45})
    return {'status':'geometry connectivity screen, not thermal qualification','nets':result,'pofv_thermal_via_map':thermal}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('board');a.add_argument('--out',type=Path,required=True);args=a.parse_args()
    b=pcb.LoadBoard(args.board);report=audit(b);args.out.write_text(json.dumps(report,indent=2))
    print(json.dumps({n:len(d['pad_groups']) for n,d in report['nets'].items()}))
