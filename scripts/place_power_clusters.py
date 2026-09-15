"""Place eFuses beneath their connectors in an isolated power candidate."""
import argparse
import json
from pathlib import Path
import shutil
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'candidates/power-base'
SOURCE = ROOT / 'candidates/compact-v6-usb'
PROJECT_SOURCE = ROOT / 'candidates/compact-v6-preconnect'
OUT.mkdir(parents=True, exist_ok=True)
for pattern in ['*.kicad_pcb', '*.kicad_pro', '*.kicad_dru', '*.kicad_sch', '*.kicad_sym', '*lib-table']:
    for path in PROJECT_SOURCE.glob(pattern): shutil.copy2(path, OUT/path.name)
shutil.copy2(SOURCE/'pcbgolf.kicad_pcb', OUT/'pcbgolf.kicad_pcb')
for folder in ['pcbgolf.pretty', 'pcbgolf.3dshapes']:
    shutil.copytree(PROJECT_SOURCE/folder, OUT/folder, dirs_exist_ok=True)
board = pcb.LoadBoard(str(OUT/'pcbgolf.kicad_pcb'))
refs = {f.GetReference(): f for f in board.GetFootprints()}
retired = []
for t in list(board.GetTracks()): board.Remove(t); retired.append(t)
for index in range(4):
    ic = refs['U'+str(index+13)]
    connector = refs['J'+str(index+5)]
    if not ic.IsFlipped(): ic.Flip(ic.GetPosition(), pcb.FLIP_DIRECTION_TOP_BOTTOM)
    ic.SetOrientationDegrees(270)
    ic.SetPosition(connector.GetPosition()+pcb.VECTOR2I(pcb.FromMM(3.0),0))
board.BuildConnectivity()
for zone in board.Zones(): zone.UnFill()
pcb.SaveBoard(str(OUT/'pcbgolf.kicad_pcb'), board)
print('Prepared',OUT,'with four bottom eFuses directly beneath output connectors')
