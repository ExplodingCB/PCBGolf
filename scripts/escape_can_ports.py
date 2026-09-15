"""Place checked ordinary dogbones for the connector CAN contacts.

Run with native KiCad Python. All edits go to a new output board. FreeRouting
or the CAN bus maze planner can subsequently join the exposed bottom vias.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import pcbnew as pcb
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from route_ground import xy,copper_shape,hole_shape,track_shape,COPPER
from preconnect import octilinear_paths

MM=pcb.FromMM
WIDTH=.127
DIA=.45
DRILL=.20


def main():
    parser=argparse.ArgumentParser();parser.add_argument('board',type=Path);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--allow-filled-via-in-pad',action='store_true')
    args=parser.parse_args();board=pcb.LoadBoard(str(args.board.resolve()));pads=list(board.GetPads())
    pad_copper=[];holes=[];lands=[];existing=[]
    for pad in pads:
        for layer in COPPER:
            if not pad.IsOnLayer(layer):continue
            shape=copper_shape(pad,layer)
            pad_copper.append((pad.GetNetname(),layer,shape,pad.HasHole()))
            if pad.GetAttribute()==pcb.PAD_ATTRIB_SMD:lands.append((pad.m_Uuid.AsString(),shape))
        if pad.HasHole():holes.append((pad.GetNetname(),hole_shape(pad),pad.GetAttribute()==pcb.PAD_ATTRIB_PTH))
    for track in board.GetTracks():
        shape=track_shape(track)
        for layer in COPPER:
            if track.IsOnLayer(layer):existing.append((track.GetNetname(),layer,shape))
        if isinstance(track,pcb.PCB_VIA):holes.append((track.GetNetname(),Point(xy(track.GetPosition())).buffer(pcb.ToMM(track.GetDrillValue())/2),False))
    all_lands=unary_union([s for _,s in lands]).buffer(DRILL/2+.01)
    added=[];results=[]
    order=['CAN3_H','CAN0_H','CAN3_L','CAN0_L','CAN2_H','CAN1_H','CAN2_L','CAN1_L']
    targets=[p for p in pads if p.GetParentFootprint().GetReference() in ['J8','J7','J6','J5'] and p.GetNetname() in order]
    targets.sort(key=lambda p:(p.GetParentFootprint().GetPosition().x,order.index(p.GetNetname())))
    for pad in targets:
        net=pad.GetNetname();origin=xy(pad.GetPosition());ref=pad.GetParentFootprint().GetReference()+'.'+pad.GetNumber()
        trace_shapes=[s.buffer(.101+WIDTH/2) for n,l,s,_ in pad_copper if n!=net and l==pcb.F_Cu]
        trace_shapes +=[s.buffer(.101+WIDTH/2) for n,l,s in existing if n!=net and l==pcb.F_Cu]
        trace_shapes +=[s.buffer((.301 if plated else .201)+WIDTH/2) for n,s,plated in holes if n!=net]
        trace_obs=unary_union(trace_shapes)
        via_shapes=[s.buffer(max(.101+DIA/2,(.301 if plated else .201)+DRILL/2)) for n,l,s,plated in pad_copper if n!=net]
        via_shapes +=[s.buffer(.101+DIA/2) for n,l,s in existing if n!=net]
        via_shapes +=[s.buffer((.301 if plated else .201)+DIA/2) for n,s,plated in holes if n!=net]
        via_shapes +=[s.buffer(DRILL/2+(.451 if plated else .201)) for n,s,plated in holes]
        via_obs=unary_union(via_shapes+[all_lands])
        vip_obs=unary_union(via_shapes+[s.buffer(DRILL/2+.01) for uid,s in lands if uid!=pad.m_Uuid.AsString()])
        own=copper_shape(pad,pcb.F_Cu)
        candidate=[]
        center=xy(pad.GetParentFootprint().GetPosition())
        for dx in [i*.1 for i in range(-14,15)]:
            for dy in [i*.1 for i in range(-9,10)]:
                target=(round(origin[0]+dx,3),round(origin[1]+dy,3))
                vip=args.allow_filled_via_in_pad and own.covers(Point(target).buffer(DRILL/2+.005))
                if not vip and math.hypot(dx,dy)<.45:continue
                if not box(.526,.526,44.474,36.474).contains(Point(target)) or (vip_obs if vip else via_obs).intersects(Point(target)):continue
                if abs(target[0]-center[0])>2.1:continue
                for path in octilinear_paths(origin,target):
                    line=LineString(path)
                    if line.intersects(trace_obs):continue
                    # Prefer compact fanout and room between connector rows.
                    cost=line.length+.03*abs(target[0]-center[0])+(.2 if vip else 0.)
                    candidate.append((cost,target,path,vip));break
        if not candidate:
            results.append(dict(ref=ref,net=net,status='no legal ordinary via'));continue
        _,target,path,vip=min(candidate,key=lambda row:row[0])
        via=pcb.PCB_VIA(board);via.SetPosition(pcb.VECTOR2I(*(MM(v) for v in target)))
        via.SetWidth(MM(DIA));via.SetDrill(MM(DRILL));via.SetViaType(pcb.VIATYPE_THROUGH)
        via.SetLayerPair(pcb.F_Cu,pcb.B_Cu);via.SetNet(pad.GetNet());via.SetLocked(True);board.Add(via)
        shape=Point(target).buffer(DIA/2)
        existing +=[(net,l,shape) for l in COPPER];holes.append((net,Point(target).buffer(DRILL/2),False))
        for a,b in zip(path,path[1:]):
            if math.dist(a,b)<.000001:continue
            track=pcb.PCB_TRACK(board);track.SetStart(pcb.VECTOR2I(*(MM(v) for v in a)));track.SetEnd(pcb.VECTOR2I(*(MM(v) for v in b)))
            track.SetWidth(MM(WIDTH));track.SetLayer(pcb.F_Cu);track.SetNet(pad.GetNet());track.SetLocked(True);board.Add(track)
            existing.append((net,pcb.F_Cu,LineString([a,b]).buffer(WIDTH/2)))
        results.append(dict(ref=ref,net=net,status='escaped',via_mm=target,via_uuid=via.m_Uuid.AsString(),filled_and_capped_required=vip))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    board.BuildConnectivity();pcb.ZONE_FILLER(board).Fill(board.Zones());pcb.SaveBoard(str(args.out.resolve()),board)
    for suffix in ('.kicad_pro','.kicad_dru'):
        source=args.board.with_suffix(suffix)
        if source.exists():shutil.copy2(source,args.out.with_suffix(suffix))
    report=dict(source=str(args.board),source_sha256=hashlib.sha256(args.board.read_bytes()).hexdigest(),output=str(args.out),results=results)
    args.out.with_suffix('.escape.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(escaped=sum(r['status']=='escaped' for r in results),total=len(results),failures=[r for r in results if r['status']!='escaped'])))


if __name__=='__main__':main()
