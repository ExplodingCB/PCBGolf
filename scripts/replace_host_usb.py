"""Replace only host J3 with verified USB4105-GF-A USB2 receptacle."""
import json,re,hashlib
import sexpdata as sx
from circuit_corrections import ROOT,blocks,setprop
from inventory import first,children,props

name='USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal'
new_id='USB4105-GF-A_USB2'
drop={'A2','A3','A10','A11','B2','B3','B10','B11'}
path=ROOT/'pcbgolf_3.kicad_sch';text=path.read_text();tree=sx.loads(text)
instance=next(s for s in children(tree,'symbol') if props(s).get('Reference')=='J3')
at=first(instance,'at')[1:3]
symold=next(s for s in children(first(tree,'lib_symbols'),'symbol') if s[1]=='pcbgolf:comma.ai_11112255_USB-C-FEMALE')
shell_keep={};dropped_nc=[]
for unit in children(symold,'symbol'):
    for pin in children(unit,'pin'):
        num=first(pin,'number')[1];point=first(pin,'at')[1:3]
        if num in drop:dropped_nc.append((round(at[0]+point[0],5),round(at[1]-point[1],5)))
        if num.startswith('S'):shell_keep.setdefault(tuple(point),num)
keep_shell=set(shell_keep.values())

def convert_symbol(block):
    edits=[]
    for a,b,unit in blocks(block):
        if not unit.startswith('(symbol '):continue
        sub=[]
        for c,d,pin in blocks(unit):
            if not pin.startswith('(pin '):continue
            m=re.search(r'\(number "([^"]+)"',pin)
            if not m:continue
            num=m[1]
            if num in drop or (num.startswith('S') and num not in keep_shell):sub.append((c,d,''))
            elif num in keep_shell:sub.append((c,d,pin.replace(f'(number "{num}"','(number "SH"',1)))
        for c,d,new in reversed(sub):unit=unit[:c]+new+unit[d:]
        edits.append((a,b,unit))
    for a,b,new in reversed(edits):block=block[:a]+new+block[b:]
    block=block.replace('comma.ai_11112255_USB-C-FEMALE',new_id)
    block=setprop(block,'Footprint','pcbgolf:'+name)
    block=setprop(block,'Value','USB4105-GF-A')
    block=setprop(block,'Datasheet','https://gct.co/files/drawings/usb4105.pdf')
    return block

edits=[];standalone=None
for a,b,block in blocks(text):
    if block.startswith('(lib_symbols'):
        sub=[]
        for c,d,symbol in blocks(block):
            if symbol.startswith('(symbol "pcbgolf:comma.ai_11112255_USB-C-FEMALE"'):
                new=convert_symbol(symbol);standalone=new.replace('"pcbgolf:'+new_id+'"','"'+new_id+'"',1);sub.append((c,d,new))
        for c,d,new in reversed(sub):block=block[:c]+new+block[d:]
        edits.append((a,b,block))
    elif block.startswith('(symbol\n') and '(property "Reference" "J3"' in block:
        old=props(sx.loads(block));sub=[]
        for c,d,pin in blocks(block):
            m=re.match(r'\(pin "([^"]+)"',pin)
            if m:
                num=m[1]
                if num in drop or(num.startswith('S') and num not in keep_shell):sub.append((c,d,''))
                elif num in keep_shell:sub.append((c,d,pin.replace(f'(pin "{num}"','(pin "SH"',1)))
        for c,d,new in reversed(sub):block=block[:c]+new+block[d:]
        newprops={'Value':'USB4105-GF-A','MPN':'USB4105-GF-A','Footprint':'pcbgolf:'+name,'Datasheet':'https://gct.co/files/drawings/usb4105.pdf'}
        for k,v in newprops.items():block=setprop(block,k,v)
        block=block.replace('pcbgolf:comma.ai_11112255_USB-C-FEMALE','pcbgolf:'+new_id)
        edits.append((a,b,block))
    elif block.startswith('(no_connect'):
        p=first(sx.loads(block),'at')[1:3]
        if tuple(round(z,5) for z in p) in dropped_nc:edits.append((a,b,''))
for a,b,new in reversed(edits):text=text[:a]+new+text[b:]
sx.loads(text);path.write_text(text,encoding='utf-8')
path=ROOT/'pcbgolf.kicad_sym';text=path.read_text();assert standalone
text=text[:text.rfind(')')]+'\n\t'+standalone+'\n)\n';sx.loads(text);path.write_text(text,encoding='utf-8')
path=ROOT/'pcbgolf.pretty'/f'{name}.kicad_mod';text=path.read_text();download_hash=hashlib.sha256(path.read_bytes()).hexdigest();text=text.replace('${KICAD10_3DMODEL_DIR}/Connector_USB.3dshapes/','${KIPRJMOD}/pcbgolf.3dshapes/Connector_USB.3dshapes/');path.write_text(text,encoding='utf-8')
r=ROOT/'reports/circuit-patches.json';result=json.loads(r.read_text())
result['updates'].append({'ref':'J3','file':'pcbgolf_3.kicad_sch','old':old,'new':newprops})
result['footprint_changes']['J3']={'old':'pcbgolf:DX07S024XJ1R1100','new':'pcbgolf:'+name,'pin_map':{**{p:p for p in ['A1','A4','A5','A6','A7','A8','A9','A12','B1','B4','B5','B6','B7','B8','B9','B12']},**{f'B{i}T':f'B{i}' for i in [1,4,5,6,7,8,9,12]},**{f'S{i}{suffix}':'SH' for i in range(1,5) for suffix in ['B','T','TH']}},'remove_old_pads':sorted(drop|{n+'T' for n in drop if n.startswith('B')}),'net_assignments':{'SH':'GND'},'notes':'ReplacementUSB2Type-C hostinterface; allusedfunctionsretained.16SMTsignalcontacts plus4largePTHshellslots. SourceSuperspeedcontacts wereNC; obsolete0.62mm JAEpadfix superseded. Default0.95mm shellstakevariant.'}
result['provenance'] += [{'path':str(path.relative_to(ROOT)).replace('\\','/'),'url':'https://gitlab.com/kicad/libraries/kicad-footprints/-/raw/master/Connector_USB.pretty/'+name+'.kicad_mod','sha256_download':download_hash},{'path':'pcbgolf.3dshapes/Connector_USB.3dshapes/'+name+'.step','url':'https://gitlab.com/kicad/libraries/kicad-packages3D/-/raw/master/Connector_USB.3dshapes/'+name+'.step','sha256_download':hashlib.sha256((ROOT/'pcbgolf.3dshapes/Connector_USB.3dshapes'/f'{name}.step').read_bytes()).hexdigest()},{'path':'reports/USB4105.pdf','url':'https://gct.co/files/drawings/usb4105.pdf'}]
r.write_text(json.dumps(result,indent=2));print('J3replaced; removedNCpositions',dropped_nc,'shellpinskept',keep_shell)
