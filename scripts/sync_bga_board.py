"""Sync isolated bga-base PCB via KiCad; run using bundled KiCad Python."""
from pathlib import Path
import hashlib
import json
import pcbnew as pcb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'candidates/bga-base'
NAME = 'STM32H725AGI6_UFBGA169'
root_hash = hashlib.sha256((ROOT / 'pcbgolf.kicad_pcb').read_bytes()).hexdigest()
print('Loading isolated board', flush=True)
board = pcb.LoadBoard(str(OUT / 'pcbgolf.kicad_pcb'))
print('Loaded board', flush=True)
old = next(fp for fp in board.GetFootprints() if fp.GetReference() == 'U3')
old_position, old_angle, old_flipped = old.GetPosition(), old.GetOrientationDegrees(), old.IsFlipped()
loader = pcb.PCB_IO_KICAD_SEXPR()
new = loader.FootprintLoad(str(OUT / 'pcbgolf.pretty'), NAME, False)
print('Loaded footprint', flush=True)
new.SetReference('U3')
new.SetValue('STM32H725AGI6')
print('Set reference/value', flush=True)
new.SetFPIDAsString('pcbgolf:' + NAME)
new.SetPath(old.GetPath())
new.SetUuid(old.m_Uuid)
new.SetAttributes(old.GetAttributes())
print('Set identity', old_position.x, old_position.y, old_angle, old_flipped, flush=True)
board.Remove(old)
board.Add(new)
new.SetPosition(old_position)
print('Set position', flush=True)
if old_flipped: new.Flip(old_position, pcb.FLIP_DIRECTION_TOP_BOTTOM)
print('Set side', flush=True)
new.SetOrientationDegrees(old_angle)
print('Updated footprint attributes', flush=True)
mapping = json.loads((OUT / 'mcu-bga-remap.json').read_text())
nets = {row['ball']: row['net'] for row in mapping['ball_assignments']}
assert len(nets) == 169
for pad in new.Pads():
    netname = nets[pad.GetNumber()]
    if netname:
        net = board.FindNet(netname)
        if not net: raise ValueError('Missing existing circuit net ' + netname)
        pad.SetNet(net)
new.Reference().SetVisible(False)
new.Value().SetVisible(False)
print('Assigned all pad nets', flush=True)
board.GetDesignSettings().SetBoardThickness(pcb.FromMM(1.6))
board.BuildConnectivity()
for zone in board.Zones(): zone.UnFill()
print('Saving board', flush=True)
pcb.SaveBoard(str(OUT / 'pcbgolf.kicad_pcb'), board)
assert hashlib.sha256((ROOT / 'pcbgolf.kicad_pcb').read_bytes()).hexdigest() == root_hash
assert len(board.GetFootprints()) == 239
statuspath = OUT / 'bga-status.json'
status = json.loads(statuspath.read_text())
status.update(status='BGA footprint and all 169 balls synchronized; parity pending',
              root_board_sha256_unchanged=root_hash,
              board_sha256=hashlib.sha256((OUT/'pcbgolf.kicad_pcb').read_bytes()).hexdigest(),
              root_board_unmodified=True,
              u3_placement={'x_mm':pcb.ToMM(old_position.x),'y_mm':pcb.ToMM(old_position.y),
                            'angle_degrees':old_angle,'bottom':old_flipped},
              tracks=len(board.GetTracks()), zones=len(board.Zones()))
statuspath.write_text(json.dumps(status,indent=2))
print(json.dumps({k:status[k] for k in ('status','u3_placement','tracks','zones','root_board_unmodified')}))
