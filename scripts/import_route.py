"""Import a FreeRouting session into a NEW board; retain the original candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import pcbnew

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('board',type=Path)
    ap.add_argument('session',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--preflight',type=Path,help='Hash-linked router preparation report')
    args=ap.parse_args()
    if args.board.resolve()==args.out.resolve():
        raise ValueError('Use a new output filename so the pre-route candidate is retained')
    if args.preflight:
        expected=json.loads(args.preflight.read_text())['source_sha256']
        actual=hashlib.sha256(args.board.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Board changed since DSN export; refusing an incompatible SES import')
    board=pcbnew.LoadBoard(str(args.board.resolve()))
    placements={f.GetReference():(f.GetPosition(),f.GetOrientationDegrees()) for f in board.GetFootprints()}
    if not pcbnew.ImportSpecctraSES(board,str(args.session.resolve())):
        raise RuntimeError('KiCad could not import the SES routing')
    for f in board.GetFootprints():
        pos,angle=placements[f.GetReference()]
        if abs(f.GetPosition().x-pos.x)>100 or abs(f.GetPosition().y-pos.y)>100 or abs(f.GetOrientationDegrees()-angle)>.000001:
            raise ValueError('Unexpected placement change during SES import: '+f.GetReference())
        f.SetPosition(pos)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(args.out.resolve()),board)
    for suffix in ('.kicad_pro','.kicad_dru'):
        source=args.board.with_suffix(suffix)
        if source.exists():shutil.copy2(source,args.out.with_suffix(suffix))
    tracks=list(board.GetTracks())
    print('Saved',args.out,'tracks',sum(not isinstance(t,pcbnew.PCB_VIA) for t in tracks),
          'vias',sum(isinstance(t,pcbnew.PCB_VIA) for t in tracks))

if __name__=='__main__':main()
