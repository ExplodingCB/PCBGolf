"""Build a reproducible placement/routing candidate using KiCad's own API.

Run with tools/kicad/bin/python.exe. A candidate is NOT submission-ready
until electrical, mechanical, and manufacturing validation has passed.
"""
import argparse
import json
from pathlib import Path
import shutil
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
MM = pcb.FromMM
FOOTPRINT_LOADER = pcb.PCB_IO_KICAD_SEXPR()
# Keep detached SWIG wrappers alive until process exit (KiCad10 Windows binding).
RETIRED_FOOTPRINTS = []

def point(x,y):
    return pcb.VECTOR2I(MM(x),MM(y))

def copy_project(out):
    out.mkdir(parents=True, exist_ok=True)
    for name in ['pcbgolf.kicad_pro','pcbgolf.kicad_sch','pcbgolf.kicad_sym',
                 'pcbgolf_2.kicad_sch','pcbgolf_3.kicad_sch','pcbgolf_4.kicad_sch',
                 'pcbgolf_5.kicad_sch','fp-lib-table','sym-lib-table']:
        shutil.copy2(ROOT/name,out/name)
    for name in ['pcbgolf.pretty','pcbgolf.3dshapes']:
        shutil.copytree(ROOT/name,out/name,dirs_exist_ok=True)

def configure_project(out, layers):
    path=out/'pcbgolf.kicad_pro'
    pro=json.loads(path.read_text())
    rules=pro['board']['design_settings']['rules']
    rules.update(min_clearance=0.1,min_copper_edge_clearance=0.3,
                 min_hole_clearance=0.2,min_hole_to_hole=0.25,
                 min_track_width=0.1,min_via_annular_width=0.1,
                 min_via_diameter=0.4,min_through_hole_diameter=0.2)
    base=pro['net_settings']['classes'][0]
    base.update(clearance=0.1,track_width=0.127,via_diameter=0.45,via_drill=0.2,
                diff_pair_width=0.15,diff_pair_gap=0.15)
    pro['net_settings']['classes']=[base]
    pro['net_settings']['netclass_patterns']=[]
    # Power route sizing is deliberately deferred to a separate validated pass.
    # This first export measures placement routability, not power integrity.
    path.write_text(json.dumps(pro,indent=2)+'\n')

def replace_footprint(board, old, name):
    new=FOOTPRINT_LOADER.FootprintLoad(str(ROOT/'pcbgolf.pretty'),name,False)
    if not new: raise RuntimeError(f'Missing footprint {name}')
    new.SetReference(old.GetReference()); new.SetValue(old.GetValue())
    new.SetFPIDAsString('pcbgolf:'+name)
    new.SetPath(old.GetPath()); new.SetAttributes(old.GetAttributes())
    new.SetUuid(old.m_Uuid)
    new.SetPosition(old.GetPosition())
    new.SetOrientationDegrees(old.GetOrientationDegrees())
    nets={p.GetNumber():p.GetNet() for p in old.Pads()}
    for pad in new.Pads():
        if pad.GetNumber() in nets: pad.SetNet(nets[pad.GetNumber()])
    board.Remove(old); RETIRED_FOOTPRINTS.append(old); board.Add(new)
    return new

def apply_verified_patches(board):
    """Only changes for which a corresponding schematic edit exists."""
    patchfile=ROOT/'reports/circuit-patches.json'
    if not patchfile.exists(): return []
    patches=json.loads(patchfile.read_text())
    refs={fp.GetReference():fp for fp in board.GetFootprints()}
    for ref in patches.get('remove_refs',[]):
        if ref in refs:
            removed=refs.pop(ref)
            board.Remove(removed); RETIRED_FOOTPRINTS.append(removed)
    for ref, change in patches.get('footprint_changes',{}).items():
        if ref not in refs: raise ValueError(f'Missing changed component {ref}')
        refs[ref]=replace_footprint(board,refs[ref],change['new'].split(':')[-1])
        for pad in refs[ref].Pads():
            number=pad.GetNumber()
            if number in change.get('net_assignments',{}):
                pad.SetNet(board.FindNet(change['net_assignments'][number]))
    for change in patches.get('updates',[]):
        fp=refs[change['ref']]
        for key,value in change['new'].items():
            if key=='Value': fp.SetValue(value)
            elif key=='Footprint': fp.SetFPIDAsString(value)
            elif key!='Reference': fp.SetField(key,value)
        for pad in fp.Pads():
            number=pad.GetNumber()
            if number in change.get('pad_nets',{}):
                name=change['pad_nets'][number]
                net=board.FindNet(name)
                if not net: raise ValueError(f'Missing net {name}')
                pad.SetNet(net)
    return patches

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('placement',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--layers',type=int,choices=[2,4],default=4)
    ap.add_argument('--thickness',type=float,default=1.6)
    ap.add_argument('--ground-plane',action='store_true')
    ap.add_argument('--power-plane',help='Net assigned to the second internal plane')
    ap.add_argument('--manufacturing-rules',type=Path)
    args=ap.parse_args()
    placement=json.loads(args.placement.read_text())
    copy_project(args.out); configure_project(args.out,args.layers)
    if args.manufacturing_rules:
        shutil.copy2(args.manufacturing_rules,args.out/'pcbgolf.kicad_dru')
    shutil.copy2(ROOT/'pcbgolf.kicad_pcb',args.out/'pcbgolf.kicad_pcb')
    board=pcb.LoadBoard(str(args.out/'pcbgolf.kicad_pcb'))
    apply_verified_patches(board)
    board.SetCopperLayerCount(args.layers)
    board.GetDesignSettings().SetBoardThickness(MM(args.thickness))
    default=board.GetDesignSettings().m_NetSettings.GetDefaultNetclass()
    default.SetClearance(MM(0.1)); default.SetTrackWidth(MM(0.127))
    default.SetViaDiameter(MM(0.45)); default.SetViaDrill(MM(0.2))
    for item in list(board.GetTracks()):
        board.Remove(item); RETIRED_FOOTPRINTS.append(item)
    for zone in list(board.Zones()):
        board.Remove(zone); RETIRED_FOOTPRINTS.append(zone)
    for item in list(board.GetDrawings()):
        if item.GetLayer()==pcb.Edge_Cuts:
            board.Remove(item); RETIRED_FOOTPRINTS.append(item)
    for fp in list(board.GetFootprints()):
        ref=fp.GetReference()
        if ref not in placement['placements']:
            raise ValueError(f'Missing placement for {ref}')
        p=placement['placements'][ref]
        if p.get('remove',False):
            raise ValueError('Removal requires verified schematic patch')
        if (p['side']=='bottom') != fp.IsFlipped():
            fp.Flip(fp.GetPosition(),pcb.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetOrientationDegrees(p['rotation_deg'])
        fp.SetPosition(point(p['x_mm'],p['y_mm']))
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
    width,height=placement['width_mm'],placement['height_mm']
    for start,end in [((0,0),(width,0)),((width,0),(width,height)),
                      ((width,height),(0,height)),((0,height),(0,0))]:
        edge=pcb.PCB_SHAPE();edge.SetShape(pcb.SHAPE_T_SEGMENT)
        edge.SetStart(point(*start));edge.SetEnd(point(*end))
        edge.SetLayer(pcb.Edge_Cuts);edge.SetWidth(MM(0.05));board.Add(edge)
    planes=[]
    if args.ground_plane: planes.append((pcb.In1_Cu,'GND'))
    if args.power_plane: planes.append((pcb.In2_Cu,args.power_plane))
    for layer,net_name in planes:
        if args.layers!=4: raise ValueError('Ground plane requires four layers')
        zone=pcb.ZONE(board);zone.SetLayer(layer)
        zone.SetNet(board.FindNet(net_name));zone.SetLocalClearance(MM(0.2))
        zone.SetMinThickness(MM(0.1));zone.SetPadConnection(pcb.ZONE_CONNECTION_FULL)
        polygon=zone.Outline();polygon.NewOutline()
        for x,y in [(0.3,0.3),(width-0.3,0.3),(width-0.3,height-0.3),(0.3,height-0.3)]:
            polygon.Append(MM(x),MM(y))
        board.Add(zone)
    if planes: pcb.ZONE_FILLER(board).Fill(board.Zones())
    pcb.SaveBoard(str(args.out/'pcbgolf.kicad_pcb'),board)
    # KiCad names unused symbol pins as singleton unconnected-* nets. They must
    # remain in the delivered PCB for parity, but must not acquire fanout vias.
    ignored_nc_pads=0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname().startswith('unconnected-'):
                pad.SetNetCode(0);ignored_nc_pads+=1
    exported=pcb.ExportSpecctraDSN(board,str(args.out/'pcbgolf.dsn'))
    if not exported: raise RuntimeError('DSN export failed')
    status=dict(stage='placement_only',submission_ready=False,width_mm=width,
                height_mm=height,layers=args.layers,thickness_mm=args.thickness,
                component_count=len(list(board.GetFootprints())),
                no_connect_pads_excluded_from_router=ignored_nc_pads,
                internal_planes=[net_name for _,net_name in planes],
                notes=['No power-current or USB-impedance validation yet.',
                       'No completed routing or mechanical approval yet.'])
    (args.out/'candidate-status.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status,indent=2))

if __name__=='__main__':main()
