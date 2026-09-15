"""Repair integration net assignment and close short MCU power connections."""
from pathlib import Path
import json, math, shutil
import pcbnew as p
from shapely.geometry import box
from route_ground import xy
from route_power import add_zone
ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/'candidates/completion'
b=p.LoadBoard(str(DIR/'bus.kicad_pcb'))
plan=json.loads((ROOT/'reports/usb-paired-routes.json').read_text())
retired=[];repairs=[]
for t in list(b.GetTracks()):
    if isinstance(t,p.PCB_VIA):
        t.SetIsFree(True)
        for v in plan['vias']:
            if math.dist(xy(t.GetPosition()),v['pos'])<1e-5 and t.GetNetname()!=v['net']:
                repairs.append({'at':xy(t.GetPosition()),'old':t.GetNetname(),'new':v['net']})
                t.SetNet(b.FindNet(v['net']))
    if t.m_Uuid.AsString() in {
        '4cd354c7-a209-4e90-8b2f-5b2d271174dd',
        'e2fac0fe-f807-4630-97ba-0689ae0d6fa8',
        '8760b1a2-fc75-4b11-80d4-c68393879e12',
    }:
        retired.append(t);b.Remove(t)
add_zone(b,'+3V3',p.F_Cu,box(.31,.31,44.69,36.69),1,'front_3v3_distribution')
def track(net,a,z,width,layer=p.B_Cu):
    t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(*(p.FromMM(x) for x in a)))
    t.SetEnd(p.VECTOR2I(*(p.FromMM(x) for x in z)));t.SetWidth(p.FromMM(width))
    t.SetLayer(layer);t.SetNet(b.FindNet(net));t.SetLocked(True);b.Add(t)
track('VLXSMPS',(6.1,20.7),(5.9,20.7),.22)
track('VLXSMPS',(5.9,20.7),(5.07,20.7),.30)
track('VDDLDO',(6.1,19.9),(5.7,19.5),.24)
v=p.PCB_VIA(b);v.SetPosition(p.VECTOR2I(p.FromMM(5.7),p.FromMM(19.5)))
v.SetWidth(p.FromMM(.45));v.SetDrill(p.FromMM(.2));v.SetViaType(p.VIATYPE_THROUGH)
v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(b.FindNet('VDDLDO'));v.SetIsFree(True);v.SetLocked(True);b.Add(v)
b.BuildConnectivity();p.ZONE_FILLER(b).Fill(b.Zones())
p.SaveBoard(str(DIR/'local-power.kicad_pcb'),b)
for suffix in ('.kicad_pro','.kicad_dru'):
    shutil.copy2(DIR/('pcbgolf'+suffix),DIR/('local-power'+suffix))
(DIR/'integration-net-repairs.json').write_text(json.dumps(repairs,indent=2))
print(json.dumps({'repaired_via_net_assignments':repairs}))
