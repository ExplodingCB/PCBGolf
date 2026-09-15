"""Create an isolated six-layer routing experiment from a four-layer candidate.

Layer arrangement: signal / ground / signal / power / ground / signal. This
tests routing capacity only; controlled impedance and final power copper must
be revalidated for an actual six-layer fabrication stackup.
"""
import argparse
import json
from pathlib import Path
import shutil
import pcbnew as pcb

RETIRED = []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.board.parent.resolve() == args.out.resolve():
        raise ValueError('Use a separate output directory')
    board = pcb.LoadBoard(str(args.board))
    for track in board.GetTracks():
        if not isinstance(track, pcb.PCB_VIA) and track.GetLayer() not in (pcb.F_Cu, pcb.B_Cu):
            raise ValueError('Internal signal routes must be mapped explicitly, refusing this input')
    args.out.mkdir(parents=True, exist_ok=True)
    for filename in ('pcbgolf.kicad_sch','pcbgolf_2.kicad_sch','pcbgolf_3.kicad_sch',
                     'pcbgolf_4.kicad_sch','pcbgolf_5.kicad_sch','pcbgolf.kicad_sym',
                     'fp-lib-table','sym-lib-table'):
        shutil.copy2(args.board.parent / filename, args.out / filename)
    for directory in ('pcbgolf.pretty','pcbgolf.3dshapes'):
        shutil.copytree(args.board.parent / directory, args.out / directory, dirs_exist_ok=True)
    shutil.copy2(args.board.with_suffix('.kicad_pro'), args.out / 'pcbgolf.kicad_pro')
    shutil.copy2(args.board.with_suffix('.kicad_dru'), args.out / 'pcbgolf.kicad_dru')
    for zone in list(board.Zones()):
        board.Remove(zone); RETIRED.append(zone)
    board.SetCopperLayerCount(6)
    bounds = board.GetBoardEdgesBoundingBox()
    # Bounds contain half the outline stroke, so keep a 0.35 mm inset here.
    x0,y0 = pcb.ToMM(bounds.GetX())+.35,pcb.ToMM(bounds.GetY())+.35
    x1,y1 = pcb.ToMM(bounds.GetRight())-.35,pcb.ToMM(bounds.GetBottom())-.35
    for layer, netname in ((pcb.In1_Cu,'GND'),(pcb.In3_Cu,'+12V'),(pcb.In4_Cu,'GND')):
        zone=pcb.ZONE(board);zone.SetLayer(layer);zone.SetNet(board.FindNet(netname))
        zone.SetLocalClearance(pcb.FromMM(.2));zone.SetMinThickness(pcb.FromMM(.1))
        zone.SetPadConnection(pcb.ZONE_CONNECTION_FULL)
        outline=zone.Outline();outline.NewOutline()
        for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):
            outline.Append(pcb.FromMM(x),pcb.FromMM(y))
        board.Add(zone)
    board.BuildConnectivity();pcb.ZONE_FILLER(board).Fill(board.Zones())
    pcb.SaveBoard(str(args.out/'pcbgolf.kicad_pcb'),board)
    report=dict(status='routing-capacity experiment',layers=6,
                source=str(args.board.resolve()),
                layer_nets={'In1.Cu':'GND','In3.Cu':'+12V','In4.Cu':'GND'},
                fabrication_stackup_and_impedance_validated=False,
                submission_ready=False)
    (args.out/'stackup-trial.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
