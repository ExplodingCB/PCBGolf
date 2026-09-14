"""Import a FreeRouting session into a NEW board; retain the original candidate."""
import argparse
from pathlib import Path
import pcbnew

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('board',type=Path)
    ap.add_argument('session',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    if args.board.resolve()==args.out.resolve():
        raise ValueError('Use a new output filename so the pre-route candidate is retained')
    board=pcbnew.LoadBoard(str(args.board.resolve()))
    if not pcbnew.ImportSpecctraSES(board,str(args.session.resolve())):
        raise RuntimeError('KiCad could not import the SES routing')
    pcbnew.SaveBoard(str(args.out.resolve()),board)
    tracks=list(board.GetTracks())
    print('Saved',args.out,'tracks',sum(not isinstance(t,pcbnew.PCB_VIA) for t in tracks),
          'vias',sum(isinstance(t,pcbnew.PCB_VIA) for t in tracks))

if __name__=='__main__':main()
