"""Reduce unlocked low-current signal vias to JLC's .30/.15 mm process.

Power, ground, USB and locked critical escape vias retain their dimensions.
The unchanged native manufacturing rules and post-change DRC remain required.
"""
import argparse,json,shutil
from pathlib import Path
import pcbnew as p
from audit_net_connectivity import audit

ap=argparse.ArgumentParser();ap.add_argument('board',type=Path);ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args();assert a.board.resolve()!=a.out.resolve()
b=p.LoadBoard(str(a.board));before=audit(b);records=[]
plan=json.loads((Path(__file__).resolve().parents[1]/'reports/usb-paired-routes.json').read_text())
protected={t['net'] for t in plan['tracks']}|{'GND','VDDLDO','VLXSMPS','Net-(J1-PWR)','Net-(U1-SW)','Net-(U2-SW)'}
for v in b.GetTracks():
    if not isinstance(v,p.PCB_VIA) or v.IsLocked():continue
    net=v.GetNetname()
    if not net or net in protected or net.startswith('+') or 'VBUS' in net:continue
    if v.GetViaType()!=p.VIATYPE_THROUGH or p.ToMM(v.GetWidth(p.F_Cu))>.450001:continue
    if p.ToMM(v.GetWidth(p.F_Cu))<=.3:continue
    records.append({'uuid':v.m_Uuid.AsString(),'net':net,'old_diameter_mm':p.ToMM(v.GetWidth(p.F_Cu)),'old_drill_mm':p.ToMM(v.GetDrillValue())})
    v.SetWidth(p.FromMM(.3));v.SetDrill(p.FromMM(.15))
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones());after=audit(b)
worse={n:(r['group_count'],after['nets'][n]['group_count']) for n,r in before['nets'].items() if after['nets'][n]['group_count']>r['group_count']}
if worse:raise RuntimeError('Shrinking broke connected pad groups; refusing save: '+str(worse))
p.SaveBoard(str(a.out),b)
for suffix in ('.kicad_pro','.kicad_dru'):shutil.copy2(a.board.with_suffix(suffix),a.out.with_suffix(suffix))
result={'source':str(a.board),'vias_reduced':records,'new_diameter_mm':.3,'new_drill_mm':.15,
        'opens_before':before['missing_pad_group_connections'],'opens_after':after['missing_pad_group_connections'],
        'native_drc_required':True,'fabrication_source':'https://jlcpcb.com/capabilities/pcb-capabilities'}
a.out.with_suffix('.signal-vias.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='vias_reduced'}|{'vias_reduced':len(records)}))
