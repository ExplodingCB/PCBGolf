"""Apply narrowly scoped, audited corrections without reformatting KiCad sources."""
from pathlib import Path
import re, json, hashlib
import sexpdata as sx

ROOT = Path(__file__).resolve().parents[1]

def blocks(text):
    """Yield direct-child s-expression ranges of the file root."""
    level=0; quoted=False; escaped=False; start=None
    for i,c in enumerate(text):
        if quoted:
            if escaped: escaped=False
            elif c=='\\': escaped=True
            elif c=='"': quoted=False
        elif c=='"': quoted=True
        elif c=='(':
            level+=1
            if level==2: start=i
        elif c==')':
            if level==2: yield start,i+1,text[start:i+1]
            level-=1

def setprop(text,name,value):
    pat=r'(\(property "'+re.escape(name)+r'" ")[^"]*(")'
    result,n=re.subn(pat,lambda m:m[1]+value+m[2],text,count=1)
    if n!=1: raise ValueError(name)
    return result

def main():
    updates={
      'U1':{'Value':'AP62300','MPN':'AP62300WU-7','Datasheet':'https://www.diodes.com/datasheet/download/AP62300.pdf'},
      'U2':{'Value':'AP62300','MPN':'AP62300WU-7','Datasheet':'https://www.diodes.com/datasheet/download/AP62300.pdf'},
      'R3':{'MPN':'RC0402FR-0710KL'},
      'R4':{'Value':'31k2','MPN':'RC0402FR-0731K2L'},
      **{f'U{i}':{'Value':'NCS20071XV53T2G','MPN':'NCS20071XV53T2G','Footprint':'pcbgolf:SOT-553','Datasheet':'https://www.onsemi.com/download/data-sheet/pdf/ncs20071-d.pdf'} for i in range(9,13)},
    }
    removed=['R5','R6']
    # Only branch wires leading to the removed parallel resistors; capacitor bus remains intact.
    wire_ids={'384a97bf-43c6-48a0-b6a8-c5afc560945e','3ee36215-f5ad-444f-be0b-50102bc0fb19','481db3de-acd8-4dcd-b07d-e37cdce936b0','5b0a97ff-c624-48fb-ae86-991b154a6145'}
    junction_ids={'2b3cdb56-08d0-4f79-b757-2a7977750698','2df1fdca-8ed3-4af7-a1d5-476120397896','37f7cf61-021c-4501-af63-785d0d7f8faa','6f505635-8564-49c3-a67e-90f449d89634'}
    patches=[]
    for path in ROOT.glob('*.kicad_sch'):
        text=path.read_text(encoding='utf-8'); edits=[]
        for start,end,block in blocks(text):
            ref=re.search(r'\(property "Reference" "([^"]+)"',block)
            if block.startswith('(symbol\n') and ref:
                ref=ref[1]
                if ref in removed: edits.append((start,end,'')); continue
                if ref in updates:
                    old={p[1]:p[2] for p in sx.loads(block) if isinstance(p,list) and str(p[0])=='property'}
                    new=block
                    for name,value in updates[ref].items(): new=setprop(new,name,value)
                    if ref in ['U1','U2']:new=new.replace('pcbgolf:comma.ai_11112255_AP62300T','pcbgolf:AP62300')
                    patches.append({'ref':ref,'file':path.name,'old':old,'new':updates[ref]})
                    edits.append((start,end,new))
            elif block.startswith('(wire') and any(f'"{u}"' in block for u in wire_ids):edits.append((start,end,''))
            elif block.startswith('(junction') and any(f'"{u}"' in block for u in junction_ids):edits.append((start,end,''))
        for start,end,new in reversed(edits):text=text[:start]+new+text[end:]
        # Embedded library symbol follows corrected regulator's identity.
        if path.name=='pcbgolf.kicad_sch':
            text=text.replace('pcbgolf:comma.ai_11112255_AP62300T','pcbgolf:AP62300').replace('"comma.ai_11112255_AP62300T_','"AP62300_')
        # All cached amplifier footprints must agree with instances.
        if path.name=='pcbgolf_4.kicad_sch':text=text.replace('pcbgolf:SOIC-8_3.9x4.9mm_P1.27mm','pcbgolf:SOT-553')
        sx.loads(text)
        if edits:path.write_text(text,encoding='utf-8')
    path=ROOT/'pcbgolf.kicad_sym'; text=path.read_text(encoding='utf-8')
    edits=[]
    for start,end,block in blocks(text):
        if block.startswith('(symbol "NCS20071XV"'):
            new=setprop(block,'Footprint','pcbgolf:SOT-553')
            new=setprop(new,'Datasheet','https://www.onsemi.com/download/data-sheet/pdf/ncs20071-d.pdf')
            edits.append((start,end,new))
        if block.startswith('(symbol "comma.ai_11112255_AP62300T"'):
            new=block.replace('"comma.ai_11112255_AP62300T','"AP62300')
            edits.append((start,end,block+'\n\t'+new))
    for start,end,new in reversed(edits):text=text[:start]+new+text[end:]
    sx.loads(text);path.write_text(text,encoding='utf-8')
    footprint=ROOT/'pcbgolf.pretty/SOT-553.kicad_mod'
    text=footprint.read_text().replace('${KISYS3DMOD}/Package_TO_SOT_SMD.3dshapes/SOT-553.wrl','${KIPRJMOD}/pcbgolf.3dshapes/Package_TO_SOT_SMD.3dshapes/SOT-553.step')
    footprint.write_text(text,encoding='utf-8')
    inv=json.loads((ROOT/'reports/source-inventory.json').read_text())
    for row in patches:
        row['pad_nets']={endpoint.split('.')[1]:net for net,pads in inv['nets'].items() for endpoint in pads if endpoint.startswith(row['ref']+'.')}
    result={'schema':1,'status':'schematics and local libraries patched; PCB synchronization owned by root agent','updates':patches,'remove_refs':removed,'footprint_changes':{f'U{i}':{'old':'pcbgolf:SOIC-8_3.9x4.9mm_P1.27mm','new':'pcbgolf:SOT-553','pin_map':{str(k):str(k) for k in range(1,6)}} for i in range(9,13)},'regulator':{'U1_vout_nominal':0.8*(1+31.2/10),'R3_tolerance_percent':1,'R4_tolerance_percent':1,'vout_resistor_tolerance_only':[0.8*(1+31.2*.99/(10*1.01)),0.8*(1+31.2*1.01/(10*.99))],'U2_vout_nominal':0.8*(1+52.3/10)},'unpatched':['J1 PWR2 net/footprint mismatch requires physical drawing resolution','D1 MPN SMAJ16CA versus SMB footprint','R70-R73 33k IMON ADC overvoltage concern','U13-U16 value TPS25942 versus MPN TPS25944ARVCR; behavior differs'],'provenance':[{'path':'pcbgolf.pretty/SOT-553.kicad_mod','url':'https://raw.githubusercontent.com/KiCad/kicad-footprints/master/Package_TO_SOT_SMD.pretty/SOT-553.kicad_mod','sha256_download':'e5744336b5435fe4564c67f43997ccbc7c11e90e8aff6066d2b1d8fbb32aed96'},{'path':'pcbgolf.3dshapes/Package_TO_SOT_SMD.3dshapes/SOT-553.step','url':'https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master/Package_TO_SOT_SMD.3dshapes/SOT-553.step','sha256_download':'2219d28dc74f980a4614180a52f390c2a095740e92ee987e4ac96f80edf01c52'}]}
    (ROOT/'reports/circuit-patches.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'updated_refs':[p['ref'] for p in patches],'removed_refs':removed,'regulator':result['regulator']},indent=2))

if __name__=='__main__':main()
