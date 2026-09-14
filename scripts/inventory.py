"""Inspect the authoritative source without modifying it."""
import collections
import csv
import json
from pathlib import Path
import sexpdata as sx

ROOT = Path(__file__).resolve().parents[1]

def tag(x):
    return str(x[0]) if isinstance(x, list) and x else None

def children(x, name):
    return [v for v in x if tag(v) == name]

def first(x, name, default=None):
    return next((v for v in x if tag(v) == name), default)

def props(x):
    return {v[1]: v[2] for v in children(x, 'property')}

def main():
    board = sx.loads((ROOT/'pcbgolf.kicad_pcb').read_text(encoding='utf-8'))
    footprints = []
    nets = collections.defaultdict(list)
    for fp in children(board, 'footprint'):
        p = props(fp)
        pads = children(fp, 'pad')
        row = dict(ref=p['Reference'], value=p.get('Value'), footprint=fp[1],
                   at=first(fp, 'at')[1:], layer=first(fp, 'layer')[1], pads=len(pads),
                   sheet=p.get('Sheetname'), path=first(fp, 'path'), models=[v[1] for v in children(fp, 'model')])
        footprints.append(row)
        for pad in pads:
            net = first(pad, 'net')
            if net:
                nets[net[-1]].append(f"{p['Reference']}.{pad[1]}")
    out = dict(counts=dict(collections.Counter(tag(x) for x in board if isinstance(x, list))),
               footprints=footprints, nets=dict(nets))
    (ROOT/'reports/source-inventory.json').write_text(json.dumps(out, indent=2))
    with (ROOT/'reports/source-bom.csv').open('w', newline='') as f:
        fields=['ref','value','footprint','at','layer','pads','sheet']
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(footprints)
    print(json.dumps(out['counts'],indent=2))
    for row in sorted(footprints,key=lambda r:r['ref']):
        if row['ref'].startswith(('U','J','L','D','Y','Q')):
            print(row['ref'],row['value'],row['footprint'],row['at'],row['sheet'])
    print('Nets:',len(nets),'connected pads:',sum(map(len,nets.values())))

if __name__=='__main__':
    main()
