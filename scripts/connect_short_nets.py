"""Close short same-side pad groups with exact native copper/hole obstacles."""
import argparse,json,math,shutil
from pathlib import Path
import pcbnew as p
from audit_net_connectivity import audit
from route_critical_power import run
ap=argparse.ArgumentParser();ap.add_argument('board',type=Path);ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args();assert a.out.resolve()!=a.board.resolve()
b=p.LoadBoard(str(a.board));groups=audit(b)['nets'];links=[]
for net,d in groups.items():
    if d['group_count']<=1 or '_D_' in net or net in ('Net-(U3-PH0)','Net-(U3-PH1)','VLXSMPS'):continue
    candidates=[]
    for i,g in enumerate(d['groups']):
        for j,h in enumerate(d['groups'][i+1:],i+1):
            for s in g['pads']:
                for e in h['pads']:
                    if not set(s['layers']).intersection(e['layers']).intersection({'F.Cu','B.Cu'}):continue
                    length=math.hypot(s['x']-e['x'],s['y']-e['y'])
                    if .01<length<5.0:candidates.append((length,i,j,(s['ref'],s['pin']),(e['ref'],e['pin'])))
    parents=list(range(d['group_count']))
    def find(i):
        while parents[i]!=i:i=parents[i]
        return i
    for dist,i,j,s,e in sorted(candidates):
        if find(i)==find(j):continue
        parents[find(i)]=find(j)
        width=.4 if net.startswith('+') or 'VBUS-Pad' in net or net=='Net-(J1-PWR)' else (.2 if net in ('GND','VDDLDO') else .1)
        links.append((s,e,width,8))
report=run(b,links)
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA):t.SetIsFree(True)
p.SaveBoard(str(a.out),b)
for suffix in ('.kicad_pro','.kicad_dru'):shutil.copy2(a.board.with_suffix(suffix),a.out.with_suffix(suffix))
a.out.with_suffix('.short-links.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'attempted':len(links),'connected':len(report['routed']),'unresolved':len(report['unresolved'])}))
