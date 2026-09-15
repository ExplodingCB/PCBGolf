"""Read ST's official CubeMX pin data and propose an isolated package remap.

This produces evidence only. It does not change the PCB or schematic and does
not claim firmware compatibility of a changed pin allocation.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/stm32-pin-data'
OUT.mkdir(exist_ok=True)
BASE = 'https://raw.githubusercontent.com/STMicroelectronics/STM32_open_pin_data/master/mcu/'
NAMES = ['STM32H725VGTx.xml', 'STM32H725VGHx.xml', 'STM32H725ZGTx.xml']


def fetch(name):
    path = OUT / name
    if not path.exists():
        response = requests.get(BASE + name, timeout=30)
        response.raise_for_status()
        path.write_bytes(response.content)
    root = ET.parse(path).getroot()
    pins = {}
    for pin in root.iter():
        if pin.tag.split('}')[-1] != 'Pin':
            continue
        name = re.split(r'[( /]', pin.attrib['Name'])[0]
        pins[name] = dict(name=pin.attrib['Name'], position=pin.attrib['Position'],
                          type=pin.attrib.get('Type'),
                          signals=[s.attrib.get('Name') for s in pin if s.tag.split('}')[-1] == 'Signal'])
    return path.stem, dict(metadata=root.attrib, pins=pins, source=BASE + path.name)


def propose_bga100(data):
    source = json.loads((ROOT / 'reports/mcu-bga-remap.json').read_text())['pin_remap']
    symbols = json.loads((ROOT / 'reports/mcu-100pin-candidates.json').read_text())
    target = symbols['STM32H725VGHx']['pins']
    functions = data['STM32H725VGHx']['pins']
    norm = lambda name: re.split(r'[( /]', name)[0]
    moves = {'PF7':'PA2', 'PF8':'PA3', 'PF9':'PA7', 'PF10':'PC5', 'PF11':'PB0',
             'PG9':'PD13', 'PG10':'PD12', 'PD12':'PE6', 'PD13':'PE7', 'PE15':'PE5'}
    required = {'PF7':'ADC1_INP14', 'PF8':'ADC1_INP15', 'PF9':'ADC1_INP7',
                'PF10':'ADC1_INP8', 'PF11':'ADC1_INP9', 'PG9':'FDCAN3_TX',
                'PG10':'FDCAN3_RX', 'PD12':'GPIO', 'PD13':'GPIO', 'PE15':'GPIO'}
    net_by_function, remaps = {}, []
    for row in source:
        if not row['connected']:
            continue
        original = norm(row['function'])
        function = moves.get(original, original)
        if original == 'VDD50USB':
            continue # Not bonded on this package; VDD33USB remains externally supplied.
        if function in net_by_function and net_by_function[function] != row['net']:
            raise ValueError(f'Conflicting source nets for {function}')
        net_by_function[function] = row['net']
        if original in moves:
            if required[original] not in functions[function]['signals']:
                raise ValueError(f'Official ST data does not support {required[original]} on {function}')
            remaps.append(dict(original_function=original, target_function=function,
                               target_ball=functions[function]['position'], net=row['net'],
                               required_target_signal=required[original],
                               verified_in_official_ST_pin_data=True))
    missing = sorted(set(net_by_function) - {norm(f) for f in target.values()})
    if missing:
        raise ValueError(f'Missing target functions: {missing}')
    assignments = [dict(ball=ball, function=norm(function), net=net_by_function.get(norm(function)),
                        connected=norm(function) in net_by_function) for ball,function in target.items()]
    report = dict(status='pin-allocation feasibility demonstrated; not a finished electrical design',
                  target_mpn='STM32H725VGH6', package='TFBGA100 8x8mm 0.8mm pitch',
                  firmware_pin_changes=remaps, ball_assignments=assignments,
                  counts=dict(balls=len(assignments), connected_balls=sum(a['connected'] for a in assignments),
                              unconnected_balls=sum(not a['connected'] for a in assignments),
                              changed_GPIO_functions=len(remaps)),
                  preserved=['All original connected signal nets have an assigned target ball.',
                             'USB PA11/PA12, SDMMC, I2C hub and CAN0/CAN1/CAN3 pin identities retained.',
                             'PC2_C/PC3_C dedicated ADC3 analog pins retained.',
                             'Three FDCAN controllers with two alternate FDCAN2 transceiver paths retained.'],
                  remaining_validation=['Schematic/package pin-number remap and multi-sheet parity.',
                                        'Package-specific direct-SMPS, VCAP/VDDLDO and USB supply scheme.',
                                        'Eight sense ADC channels: four move from ADC3 to ADC1; timing/DMA configuration must change.',
                                        'New firmware pin/channel definitions and build verification; this is not binary compatible.',
                                        'Actual 0.8mm BGA escape, ground reference, DRC and assembly process.',
                                        'Official model and maximum package envelope.'],
                  sources=[data['STM32H725VGHx']['source'], data['STM32H725ZGTx']['source'],
                           'https://www.st.com/resource/en/datasheet/stm32h725vg.pdf',
                           'https://www.st.com/en/microcontrollers-microprocessors/stm32h725vg.html'])
    (ROOT / 'reports/mcu-bga100-feasibility.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    data = dict(ThreadPoolExecutor(3).map(fetch, NAMES))
    report = ROOT / 'reports/mcu-100pin-functions.json'
    report.write_text(json.dumps(data, indent=2) + '\n')
    proposal = propose_bga100(data)
    print('BGA100 feasible allocation', proposal['counts'])
    for name, item in data.items():
        print(name, item['metadata'])
        print('FDCAN3', {n:p for n,p in item['pins'].items() if any('FDCAN3' in s for s in p['signals'])})
        print('ADC inputs', {n:[s for s in p['signals'] if s.startswith('ADC')] for n,p in item['pins'].items() if any(s.startswith('ADC') for s in p['signals'])})
