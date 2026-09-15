"""Report native KiCad connected pad groups without the DRC report count cap.

Run using portable KiCad Python. This read-only diagnostic does not replace
native DRC: orphan copper and manufacturing errors remain separate checks.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import pcbnew as pcb


def audit(board):
    board.BuildConnectivity();connectivity=board.GetConnectivity()
    pads={p.m_Uuid.AsString():p for p in board.GetPads()}
    bynet=collections.defaultdict(list)
    for uid,pad in pads.items():
        net=pad.GetNetname()
        if net and not net.startswith('unconnected-'):bynet[net].append(uid)
    results={}
    for net,ids in sorted(bynet.items()):
        visited=set();groups=[]
        for uid in ids:
            if uid in visited:continue
            connected=list(connectivity.GetConnectedItems(pads[uid]))
            members={item.m_Uuid.AsString() for item in connected}|{uid}
            pad_ids=members.intersection(ids)
            visited.update(pad_ids)
            rows=[]
            for item_id in sorted(pad_ids):
                pad=pads[item_id]
                rows.append(dict(ref=pad.GetParentFootprint().GetReference(),pin=pad.GetNumber(),
                                 uuid=item_id,x=pcb.ToMM(pad.GetPosition().x),y=pcb.ToMM(pad.GetPosition().y),
                                 layers=[board.GetLayerName(l) for l in pad.GetLayerSet().CuStack()]))
            groups.append(dict(pads=rows,connected_item_count=len(members)))
        results[net]=dict(pad_count=len(ids),group_count=len(groups),groups=groups)
    return dict(nets=results,missing_pad_group_connections=sum(max(0,r['group_count']-1) for r in results.values()),
                incomplete_nets=[n for n,r in results.items() if r['group_count']>1],
                limitations=['Connected-pad group count excludes orphan copper, DRC violations and functional checks.',
                             'Uses native GetConnectedItems after BuildConnectivity on the saved board.'])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('board',type=Path);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();before=hashlib.sha256(args.board.read_bytes()).hexdigest()
    report=audit(pcb.LoadBoard(str(args.board.resolve())))
    report.update(board=str(args.board),board_sha256=before,board_unchanged=hashlib.sha256(args.board.read_bytes()).hexdigest()==before)
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(missing_pad_group_connections=report['missing_pad_group_connections'],incomplete_nets=len(report['incomplete_nets']),
                         groups={n:r['group_count'] for n,r in report['nets'].items() if n=='GND' or n.startswith('CAN') and n.endswith(('_H','_L'))})))


if __name__=='__main__':main()
