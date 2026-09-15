"""Export native KiCad geometry for isolated USB route planning."""
import json,sys
from pathlib import Path
import pcbnew as pcb

board=pcb.LoadBoard(sys.argv[1]); out=Path(sys.argv[2])
def xy(v):return [pcb.ToMM(v.x),pcb.ToMM(v.y)]
def polygons(s):
 result=[]
 for i in range(s.OutlineCount()):
  o=s.COutline(i);result.append([xy(o.CPoint(j)) for j in range(o.PointCount())])
 return result
pads=[]
for p in board.GetPads():
 layers=[l for l in [pcb.F_Cu,pcb.In1_Cu,pcb.In2_Cu,pcb.B_Cu] if p.IsOnLayer(l)]
 poly={str(l):polygons(p.GetEffectivePolygon(l,pcb.ERROR_OUTSIDE)) for l in layers}
 hole=pcb.SHAPE_POLY_SET();p.TransformHoleToPolygon(hole,0,1000,pcb.ERROR_OUTSIDE)
 pads.append(dict(ref=p.GetParentFootprint().GetReference(),pad=p.GetNumber(),net=p.GetNetname(),pos=xy(p.GetPosition()),size=xy(p.GetSize()),angle=p.GetOrientationDegrees(),layers=layers,polygons=poly,hole=polygons(hole),drill=xy(p.GetDrillSize()),attribute=int(p.GetAttribute())))
tracks=[]
for t in board.GetTracks():
 if isinstance(t,pcb.PCB_VIA):tracks.append(dict(type='via',net=t.GetNetname(),pos=xy(t.GetPosition()),width=pcb.ToMM(t.GetWidth(pcb.F_Cu)),drill=pcb.ToMM(t.GetDrillValue())))
 else:tracks.append(dict(type='track',net=t.GetNetname(),a=xy(t.GetStart()),b=xy(t.GetEnd()),width=pcb.ToMM(t.GetWidth()),layer=t.GetLayer()))
result=dict(board=str(sys.argv[1]),pads=pads,tracks=tracks,layers={'F.Cu':pcb.F_Cu,'In1.Cu':pcb.In1_Cu,'In2.Cu':pcb.In2_Cu,'B.Cu':pcb.B_Cu})
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
print(json.dumps({'pads':len(pads),'tracks':len(tracks),'output':str(out)}))
