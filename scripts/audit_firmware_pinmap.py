"""Check firmware GPIO/ADC selections against schematic allocation and ST pin data."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
header=ROOT/'firmware/pcbgolf/pcbgolf_bga100.h'
allocation=ROOT/'reports/mcu-bga100-feasibility.json'
official=ROOT/'reports/mcu-100pin-functions.json'
text=header.read_text();pins=json.loads(allocation.read_text())['ball_assignments']
by_function={p['function']:p for p in pins};st=json.loads(official.read_text())['STM32H725VGHx']['pins']
arrays=dict(re.findall(r'gpio_t (\w+)\[\] = \{(.*?)\};',text,re.S));checks=[]
for array,suffix in {'power_pins':'PWR_EN','sbu1_ignition_pins':'SBU1_IGN','sbu1_relay_pins':'SBU1_RELAY',
                     'sbu2_ignition_pins':'SBU2_IGN','sbu2_relay_pins':'SBU2_RELAY','can_enable_pins':None}.items():
    rows=re.findall(r'GPIO([A-Z]),\s*(\d+)',arrays[array]);assert len(rows)==4,array
    for i,(bank,pin) in enumerate(rows):
        gpio='P'+bank+pin;expected=f'CH{i+1}_{suffix}' if suffix else f'CAN{i}_EN'
        actual=by_function[gpio];assert actual['net']==expected,(array,i,actual,expected)
        checks.append({'kind':'GPIO','array':array,'channel':i+1,**actual})
adc_expected={
    'imon_channels':['CH1_IMON','CH2_IMON','CH3_IMON','CH4_IMON'],
    'sbu1_channels':['Net-(U3-PC2_C)','Net-(U3-PF9)','Net-(U3-PC0)','Net-(U3-PF10)'],
    'sbu2_channels':['Net-(U3-PC3_C)','Net-(U3-PF7)','Net-(U3-PC1)','Net-(U3-PF8)'],
}
for array,expected in adc_expected.items():
    body=re.search(r'const adc_signal_t '+array+r'\[\] = \{(.*?)\};',text,re.S).group(1)
    channels=re.findall(r'PCBGOLF_ADC\((ADC\d),\s*(\d+)\)',body);assert len(channels)==4
    for i,((adc,channel),net) in enumerate(zip(channels,expected)):
        row=next(p for p in pins if p['net']==net);signal=adc+'_INP'+channel
        official_pin=next(v for v in st.values() if v['position']==row['ball'])
        assert signal in official_pin['signals'],(array,i,signal,official_pin)
        checks.append({'kind':'ADC','array':array,'channel':i+1,'signal':signal,**row})
for gpio,net,signal in [('PB8','CAN0_RX','FDCAN1_RX'),('PB9','CAN0_TX','FDCAN1_TX'),
                       ('PB5','CAN1_RX','FDCAN2_RX'),('PB6','CAN1_TX','FDCAN2_TX'),
                       ('PD12','CAN2_RX','FDCAN3_RX'),('PD13','CAN2_TX','FDCAN3_TX'),
                       ('PB12','CAN3_RX','FDCAN2_RX'),('PB13','CAN3_TX','FDCAN2_TX')]:
    row=by_function[gpio];assert row['net']==net
    official_pin=next(v for v in st.values() if v['position']==row['ball'])
    assert signal in official_pin['signals']
    checks.append({'kind':'CAN alternate function','signal':signal,**row})
assert by_function['PE5']['net']=='BTN'
result={'status':'GPIO and ADC allocation checks passed; hardware not tested','checks':checks,
        'sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (header,allocation,official)},
        'limitations':['Checks the allocation documented by schematic parity and official ST pin data.',
                       'Does not validate firmware timing, all peripherals, power-up behavior or electrical operation.']}
(ROOT/'firmware/pcbgolf/pinmap.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'checked_gpio_adc_can_assignments':len(checks),'status':result['status']}))
