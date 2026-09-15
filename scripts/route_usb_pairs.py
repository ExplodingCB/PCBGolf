"""Native KiCad preparation/application for explicitly planned USB copper.

Run with tools/kicad/bin/python.exe. All mutations are isolated to --out.
The planner and its JSON retain individual nets, widths, layers and vias.
"""
import argparse,json,shutil,math
from pathlib import Path
import pcbnew as pcb
ROOT=Path(__file__).resolve().parents[1]
RETIRED=[]
def pos(xy):return pcb.VECTOR2I(*(pcb.FromMM(x) for x in xy))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=ROOT/'candidates/compact-v6-preconnect/pcbgolf.kicad_pcb');ap.add_argument('--out',type=Path,default=ROOT/'candidates/compact-v6-usb');ap.add_argument('--plan',type=Path);ap.add_argument('--prepare',action='store_true');ap.add_argument('--preserve-existing',action='store_true');a=ap.parse_args()
 a.out.mkdir(parents=True,exist_ok=True)
 if a.prepare:
  for f in a.source.parent.iterdir():
   if f.is_file() and f.suffix in ('.kicad_pcb','.kicad_pro','.kicad_dru','.kicad_sch','.kicad_sym'):shutil.copy2(f,a.out/f.name)
  b=pcb.LoadBoard(str(a.source));fps={f.GetReference():f for f in b.GetFootprints()}
  for ref,x in {'J8':3.25,'J7':10.75,'J6':18.25,'J5':25.75}.items():
   p=fps[ref].GetPosition();p.x=pcb.FromMM(x);fps[ref].SetPosition(p);fps[ref].SetOrientationDegrees(270)
  for t in list(b.GetTracks()):
   if not a.preserve_existing or '_D_' in t.GetNetname():b.Remove(t);RETIRED.append(t)
  # USB routing has priority; generic local joins are regenerated after the
  # critical routes, so no stale connector crossings survive this preparation.
  local=[]
  pcb.SaveBoard(str(a.out/'pcbgolf.kicad_pcb'),b)
  print(json.dumps({'board':str(a.out/'pcbgolf.kicad_pcb'),'connector_permutation':{'J8':3.25,'J7':10.75,'J6':18.25,'J5':25.75},'local_tracks':len(local)}))
 if a.plan:
  b=pcb.LoadBoard(str(a.out/'pcbgolf.kicad_pcb'));plan=json.loads(a.plan.read_text())
  for t in list(b.GetTracks()):
   if '_D_' in t.GetNetname():b.Remove(t);RETIRED.append(t)
  for r in plan['tracks']:
   t=pcb.PCB_TRACK(b);t.SetStart(pos(r['a']));t.SetEnd(pos(r['b']));t.SetWidth(pcb.FromMM(r['width']));t.SetLayer(r['layer']);t.SetNet(b.FindNet(r['net']));t.SetLocked(True);b.Add(t)
  for r in plan.get('vias',[]):
   t=pcb.PCB_VIA(b);t.SetPosition(pos(r['pos']));t.SetWidth(pcb.FromMM(r.get('diameter',.40)));t.SetDrill(pcb.FromMM(r.get('drill',.2)));t.SetViaType(pcb.VIATYPE_THROUGH);t.SetLayerPair(pcb.F_Cu,pcb.B_Cu);t.SetNet(b.FindNet(r['net']));t.SetLocked(True);b.Add(t)
  for old in list(b.Zones()):
   if old.GetZoneName().startswith('USB In2 reference'):b.Remove(old);RETIRED.append(old)
  for r in plan.get('zones',[]):
   z=pcb.ZONE(b);z.SetLayer(r['layer']);z.SetNet(b.FindNet(r['net']));z.SetAssignedPriority(r['priority']);z.SetZoneName(r['name']);z.SetLocalClearance(pcb.FromMM(r['clearance_mm']));z.SetMinThickness(pcb.FromMM(.15));z.SetPadConnection(pcb.ZONE_CONNECTION_FULL)
   poly=z.Outline();poly.NewOutline()
   for xy in r['outline']:poly.Append(pos(xy))
   b.Add(z)
  pcb.SaveBoard(str(a.out/'pcbgolf.kicad_pcb'),b)
  print(json.dumps({'board':str(a.out/'pcbgolf.kicad_pcb'),'usb_tracks':len(plan['tracks']),'usb_vias':len(plan.get('vias',[]))}))
if __name__=='__main__':main()
