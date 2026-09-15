"""One-shot follow-up library fixes and mounting-hole removal authorized by root."""
from pathlib import Path
import json,re
import sexpdata as sx
from circuit_corrections import blocks,setprop,ROOT

def drop_t_pins(block):
    # Each physical B-row terminal appears twice in the imported Eagle symbol.
    # One logical pin serves both SMT/PTH pads once the pad names are canonicalized.
    edits=[]
    for a,b,unit in blocks(block):
        if not unit.startswith('(symbol '):continue
        nested=[]
        for c,d,pin in blocks(unit):
            if pin.startswith('(pin ') and re.search(r'\(number "B(?:[1-9]|1[0-2])T"',pin):nested.append((c,d,''))
        for c,d,new in reversed(nested):unit=unit[:c]+new+unit[d:]
        edits.append((a,b,unit))
    for a,b,new in reversed(edits):block=block[:a]+new+block[b:]
    return block

def main():
    refs={f'BH{i}' for i in range(1,5)}|{f'#GND0{i}' for i in range(47,51)}
    wires={'8f80dd8c-6cdd-4485-8343-48e0367385d9','c0d5936a-ddc7-43a9-8350-220d2900205d','e64b1b06-055a-4483-8b7a-541e2841c5e0','f13158a8-6f5d-47e9-9293-5e4c4c3e96af'}
    p=ROOT/'pcbgolf.kicad_sch';text=p.read_text();edits=[]
    for a,b,block in blocks(text):
        ref=re.search(r'\(property "Reference" "([^"]+)"',block)
        if block.startswith('(symbol\n') and ref:
            if ref[1] in refs:edits.append((a,b,''))
            elif ref[1]=='J1':edits.append((a,b,setprop(block,'Footprint','pcbgolf:PJ-002AH-SMT-TR')))
        elif block.startswith('(wire') and any(f'"{w}"' in block for w in wires):edits.append((a,b,''))
    for a,b,new in reversed(edits):text=text[:a]+new+text[b:]
    p.write_text(text,encoding='utf-8');sx.loads(text)
    # Update the cached and standalone exact J3 symbol; other USB connectors unchanged.
    for fn in ['pcbgolf_3.kicad_sch','pcbgolf.kicad_sym']:
        p=ROOT/fn;text=p.read_text()
        if fn.endswith('.kicad_sch'):
            edits=[]
            for a,b,block in blocks(text):
                if block.startswith('(lib_symbols'):
                    sub=[]
                    for c,d,symbol in blocks(block):
                        if symbol.startswith('(symbol "pcbgolf:comma.ai_11112255_USB-C-FEMALE"'):sub.append((c,d,drop_t_pins(symbol)))
                    for c,d,new in reversed(sub):block=block[:c]+new+block[d:]
                    edits.append((a,b,block))
                elif block.startswith('(symbol\n') and '(property "Reference" "J3"' in block:
                    sub=[]
                    for c,d,pin in blocks(block):
                        if re.match(r'\(pin "B(?:[1-9]|1[0-2])T"',pin):sub.append((c,d,''))
                    for c,d,new in reversed(sub):block=block[:c]+new+block[d:]
                    edits.append((a,b,block))
        else:
            edits=[(a,b,drop_t_pins(block)) for a,b,block in blocks(text) if block.startswith('(symbol "comma.ai_11112255_USB-C-FEMALE"')]
        for a,b,new in reversed(edits):text=text[:a]+new+text[b:]
        sx.loads(text);p.write_text(text,encoding='utf-8')
    p=ROOT/'pcbgolf.pretty/DX07S024XJ1R1100.kicad_mod'
    text=p.read_text();text=re.sub(r'\(pad "(B(?:[1-9]|1[0-2]))T"',r'(pad "\1"',text);sx.loads(text);p.write_text(text,encoding='utf-8')
    # Manufacturer PJ-002AH-SMT-TR drawing,2024-09-12,page2. Keep original model/origin.
    src=ROOT/'pcbgolf.pretty/DCJACK_2MM_SMT.kicad_mod'; text=src.read_text().replace('"DCJACK_2MM_SMT"','"PJ-002AH-SMT-TR"');edits=[]
    for a,b,block in blocks(text):
        if not block.startswith('(pad '):continue
        obj=sx.loads(block);name=obj[1]
        if name in ['PWR1','PWR2','GND','GNDBREAK']:
            x=0 if name in ['PWR1','GND'] else 6
            y=-6.5 if name.startswith('PWR') else 6.5
            block=re.sub(r'\(at [^)]+\)',f'(at {x} {y})',block,count=1)
            block=re.sub(r'\(size [^)]+\)','(size 2.5 4)',block,count=1)
            if name=='PWR2':block=block.replace('(pad "PWR2"','(pad "PWR1"',1)
        elif name=='' and '(at 0 0)' in block:
            block=block.replace('(size 1.6 1.6)','(size 1.7 1.7)').replace('(drill 1.6)','(drill 1.7)')
        edits.append((a,b,block))
    for a,b,new in reversed(edits):text=text[:a]+new+text[b:]
    # Courtyard reflects recommended pad extents and physical body.
    before=text.rfind(')')
    lines='\n'.join(f'\t(fp_line (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.05) (type solid)) (layer "F.CrtYd"))' for x1,y1,x2,y2 in [(-5.3,-8.75,10.2,-8.75),(10.2,-8.75,10.2,8.75),(10.2,8.75,-5.3,8.75),(-5.3,8.75,-5.3,-8.75)])
    text=text[:before]+lines+'\n'+text[before:];sx.loads(text)
    (ROOT/'pcbgolf.pretty/PJ-002AH-SMT-TR.kicad_mod').write_text(text,encoding='utf-8')
    # Standalone J1 symbol's default footprint now resolves to its corrected MPN.
    for fn in ['pcbgolf.kicad_sch','pcbgolf.kicad_sym']:
        p=ROOT/fn;text=p.read_text().replace('pcbgolf:DCJACK_2MM_SMT','pcbgolf:PJ-002AH-SMT-TR');sx.loads(text);p.write_text(text,encoding='utf-8')
    p=ROOT/'reports/circuit-patches.json';result=json.loads(p.read_text())
    result['remove_refs'] += [f'BH{i}' for i in range(1,5)]
    result['footprint_changes']['J1']={'old':'pcbgolf:DCJACK_2MM_SMT','new':'pcbgolf:PJ-002AH-SMT-TR','pin_map':{'GND':'GND','GNDBREAK':'GNDBREAK','PWR1':'PWR1','PWR2':'PWR1'},'net_assignments':{'PWR1':'Net-(J1-PWR)'},'notes':'Both terminal1 lands use same pad number. Corrected recommended pads2.5x4mm centers(0,+/-6.5),(6,+/-6.5),NPTH1.7 atorigin,NPTH1.8 at(4.5,0). Existing same-MPN STEP kept.'}
    result['footprint_changes']['J3']={'old':'pcbgolf:DX07S024XJ1R1100','new':'pcbgolf:DX07S024XJ1R1100','pin_map':{f'B{i}T':f'B{i}' for i in range(1,13)},'notes':'Physical hybridSMT/PTH terminal duplicate IDs canonicalized toB1..B12; one logical symbolpin each. PCB duplicate pads must share canonical terminal net.'}
    result['unpatched']=[v for v in result['unpatched'] if not v.startswith('J1')]
    result['provenance'].append({'path':'pcbgolf.pretty/PJ-002AH-SMT-TR.kicad_mod','url':'https://www.sameskydevices.com/product/resource/pj-002ah-smt-tr.pdf','drawing_page':2,'drawing_date':'2024-09-12'})
    p.write_text(json.dumps(result,indent=2))
    print('RemovedBH1-BH4; correctedJ1footprint; canonicalizedJ3B-rowduplicatepads')

if __name__=='__main__':main()
