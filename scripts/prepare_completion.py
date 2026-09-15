"""Remove four conflicting redundant fanout vias before completing one fixed layout."""
from pathlib import Path
import json
import shutil
import pcbnew as p
from route_ground import connect_ground

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'candidates/integrated-v1'
OUT = ROOT / 'candidates/completion'
OUT.mkdir(exist_ok=True)
for source in SOURCE.iterdir():
    if source.is_dir() and source.suffix in ('.pretty', '.3dshapes'):
        shutil.copytree(source, OUT/source.name, dirs_exist_ok=True)
    elif source.suffix in ('.kicad_pro', '.kicad_sch', '.kicad_dru', '.kicad_sym') or source.name in ('fp-lib-table', 'sym-lib-table'):
        shutil.copy2(source, OUT/source.name)
b = p.LoadBoard(str(SOURCE/'pcbgolf.kicad_pcb'))
remove_ids = {
    '0f0407e8-544a-449d-819d-a1cc4947346b',
    'bc9d33c8-f12c-4091-83ed-c4dbe633897c',
    '6e63fc67-f2dc-4ead-87c1-85a93494234e',
    '2fcc28a5-e98f-41bb-986d-cee74f62c1e5',
}
removed = []
for item in list(b.GetTracks()):
    if item.m_Uuid.AsString() in remove_ids:
        assert isinstance(item, p.PCB_VIA)
        removed.append(item)
        b.Remove(item)
assert len(removed) == len(remove_ids)
b.BuildConnectivity()
p.ZONE_FILLER(b).Fill(b.Zones())
p.SaveBoard(str(OUT/'repaired.kicad_pcb'), b)
report = connect_ground(b)
for item in b.GetTracks():
    item.SetLocked(True)
p.SaveBoard(str(OUT/'pcbgolf.kicad_pcb'), b)
(OUT/'ground-report.json').write_text(json.dumps(report, indent=2))
print(json.dumps({'removed_conflicting_vias': len(removed), 'ground_vias_added': report['vias_added'],
                  'ground_islands_unresolved': len(report['unresolved_islands'])}))
