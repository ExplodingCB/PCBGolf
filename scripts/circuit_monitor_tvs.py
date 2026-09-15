"""Audited monitor range and same-MPN TVS footprint corrections."""
import json,re
import sexpdata as sx
from circuit_corrections import ROOT,blocks,setprop

updates={**{f'R{i}':{'Value':'10k','MPN':'RC0402FR-0710KL'} for i in range(70,74)},**{f'U{i}':{'Value':'TPS25944A','Datasheet':'https://www.ti.com/lit/ds/symlink/tps25944a.pdf'} for i in range(13,17)},'D1':{'Value':'SMAJ16CA','Footprint':'pcbgolf:D_SMA'}}
p=ROOT/'reports/circuit-patches.json';result=json.loads(p.read_text())
for fn in ['pcbgolf.kicad_sch','pcbgolf_5.kicad_sch']:
    path=ROOT/fn;text=path.read_text();edits=[]
    for a,b,block in blocks(text):
        ref=re.search(r'\(property "Reference" "([^"]+)"',block)
        if block.startswith('(symbol\n') and ref and ref[1] in updates:
            ref=ref[1];old={z[1]:z[2] for z in sx.loads(block) if isinstance(z,list) and str(z[0])=='property'}
            for name,value in updates[ref].items():block=setprop(block,name,value)
            edits.append((a,b,block));result['updates'].append({'ref':ref,'file':fn,'old':old,'new':updates[ref]})
    for a,b,new in reversed(edits):text=text[:a]+new+text[b:]
    if fn=='pcbgolf.kicad_sch':text=text.replace('pcbgolf:DO-214AA(SMB)','pcbgolf:D_SMA')
    sx.loads(text);path.write_text(text,encoding='utf-8')
path=ROOT/'pcbgolf.kicad_sym';text=path.read_text();edits=[]
for a,b,block in blocks(text):
    if block.startswith('(symbol "comma.ai_11112255_TVS-BI-DO214AA"') or block.startswith('(symbol "TVS-BI-DO214AA"'):
        edits.append((a,b,setprop(block,'Footprint','pcbgolf:D_SMA')))
for a,b,new in reversed(edits):text=text[:a]+new+text[b:]
sx.loads(text);path.write_text(text,encoding='utf-8')
path=ROOT/'pcbgolf.pretty/D_SMA.kicad_mod';text=path.read_text().replace('${KISYS3DMOD}/Diode_SMD.3dshapes/D_SMA.wrl','${KIPRJMOD}/pcbgolf.3dshapes/Diode_SMD.3dshapes/D_SMA.step');path.write_text(text,encoding='utf-8')
result['footprint_changes']['D1']={'old':'pcbgolf:DO-214AA(SMB)','new':'pcbgolf:D_SMA','pin_map':{'1':'1','2':'2'},'notes':'Same SMAJ16CA-13-F MPN; correct DO-214AC package. Bidirectional TVS so pad polarity arbitrary; original endpoint assignments retained.'}
result['current_monitor']={'refs':['R70','R71','R72','R73'],'resistance_ohm':10000,'resistor_tolerance_percent':1,'nominal_tps25944_imon_gain_uA_per_A':52.3,'volts_per_ampere':0.523,'amperes_per_volt':1/0.523,'firmware_scale_multiplier_vs_source_33k':3.3,'formula':'I_A = V_ADC_V / (52.3e-6 * 10000)','calibration_required':True,'note':'Update ADC current conversion for10k burden resistor; validate with known load. Source33k overloads3.3V ADC above~1.91A.'}
result['unpatched']=[]
result['provenance'] += [{'path':'pcbgolf.pretty/D_SMA.kicad_mod','url':'https://raw.githubusercontent.com/KiCad/kicad-footprints/master/Diode_SMD.pretty/D_SMA.kicad_mod','sha256_download':'4806e1c384f374a6c7ebe2da466c8861b31683031bea42889cbb873c2937bd56'},{'path':'pcbgolf.3dshapes/Diode_SMD.3dshapes/D_SMA.step','url':'https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master/Diode_SMD.3dshapes/D_SMA.step','sha256_download':'1cfddd4e3b1bf22b8fc6ee3258c2aade882ed7b85b528e23b9db42437775a1db'}]
p.write_text(json.dumps(result,indent=2))
print('Updated',', '.join(updates))
