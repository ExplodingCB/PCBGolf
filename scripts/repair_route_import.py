"""Restore verified clock copper and remove only new copper failing native DRC."""
import argparse,json,shutil,subprocess
from pathlib import Path
import pcbnew as p
from merge_critical_routes import track_key,footprint_signature
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('board',type=Path);ap.add_argument('--trusted',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args();assert a.out.resolve() not in (a.board.resolve(),a.trusted.resolve())
b=p.LoadBoard(str(a.board));trusted=p.LoadBoard(str(a.trusted))
original={f.GetReference():f for f in trusted.GetFootprints()}
for f in b.GetFootprints():
    other=original[f.GetReference()]
    assert abs(f.GetPosition().x-other.GetPosition().x)<=100 and abs(f.GetPosition().y-other.GetPosition().y)<=100,'Placement mismatch beyond SES rounding'
    f.SetPosition(other.GetPosition())
assert {f.GetReference():footprint_signature(f) for f in b.GetFootprints()}=={f.GetReference():footprint_signature(f) for f in trusted.GetFootprints()},'Placement mismatch'
protected={track_key(t) for t in trusted.GetTracks()};retired=[];removed=[]
clock_nets={'Net-(U3-PH0)','Net-(U3-PH1)'}
for t in list(b.GetTracks()):
    if t.GetNetname() in clock_nets:retired.append(t);b.Remove(t)
for t in trusted.GetTracks():
    if t.GetNetname() not in clock_nets:continue
    assert not isinstance(t,p.PCB_VIA)
    new=p.PCB_TRACK(b);new.SetStart(t.GetStart());new.SetEnd(t.GetEnd());new.SetWidth(t.GetWidth())
    new.SetLayer(t.GetLayer());new.SetNet(b.FindNet(t.GetNetname()));new.SetLocked(True);b.Add(new)
for t in b.GetTracks():
    if isinstance(t,p.PCB_VIA):t.SetIsFree(True)
for suffix in ('.kicad_pro','.kicad_dru'):shutil.copy2(a.board.with_suffix(suffix),a.out.with_suffix(suffix))
drc=a.out.with_suffix('.drc.json')
for iteration in range(5):
    b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(a.out),b)
    result=subprocess.run([str(ROOT/'tools/kicad/bin/kicad-cli.exe'),'pcb','drc','--format','json','--severity-all',
        '--all-track-errors','--refill-zones','--output',str(drc),str(a.out)],capture_output=True,text=True)
    assert result.returncode in (0,5),result.stderr
    data=json.loads(drc.read_text(encoding='utf-8-sig'))
    errors=[v for v in data['violations'] if v['severity']=='error' or v['type']=='hole_to_hole']
    if not errors:break
    items={t.m_Uuid.AsString():t for t in b.GetTracks()}
    selected={}
    for error in errors:
        candidates=[items[i['uuid']] for i in error['items'] if i['uuid'] in items and track_key(items[i['uuid']]) not in protected]
        if not candidates:raise RuntimeError('Violation requires manual repair: '+str(error))
        pick=min(candidates,key=lambda t:(0 if isinstance(t,p.PCB_VIA) else 1,t.m_Uuid.AsString()))
        selected[pick.m_Uuid.AsString()]=pick
    for uid,t in selected.items():
        removed.append({'uuid':uid,'net':t.GetNetname(),'kind':'via' if isinstance(t,p.PCB_VIA) else 'track'})
        retired.append(t);b.Remove(t)
else:raise RuntimeError('Physical violations remain after five cleanup rounds')
a.out.with_suffix('.repair.json').write_text(json.dumps({'removed_new_copper':removed,'physical_errors':0,
    'unconnected_items':len(data['unconnected_items']),'trusted_clock_source':str(a.trusted)},indent=2))
print(json.dumps({'removed_new_copper':len(removed),'physical_errors':0,'unconnected_items':len(data['unconnected_items'])}))
