"""Replace only generic MCU USB access in an isolated copy with paired-via sites.

Run with bundled KiCad Python. The P via-in-pad requires filled/copper-capped
POFV. This prepares physical access for the USB router, not complete USB traces.
"""
import collections
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pcbnew as pcb

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'candidates/bga100-power-escape'
OUT=ROOT/'candidates/bga100-power-escape-usb-reserved'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def vec(x,y):return pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))


def main():
    source_hash=sha(SOURCE/'pcbgolf.kicad_pcb')
    shutil.copytree(SOURCE,OUT,dirs_exist_ok=True)
    boardpath=OUT/'pcbgolf.kicad_pcb';board=pcb.LoadBoard(str(boardpath))
    u3=next(f for f in board.GetFootprints() if f.GetReference()=='U3')
    targets={'D9':('STM_D_P',(13.3,21.1)),'D10':('STM_D_N',(14.1,21.1))}
    for number,(net,pos) in targets.items():
        pad=next(p for p in u3.Pads() if p.GetNumber()==number)
        assert pad.GetNetname()==net and pad.GetPosition()==vec(*pos)
    generic=json.loads((SOURCE/'escape-report.json').read_text())
    expected={r['uuid'] for r in generic['tracks']+generic['vias'] if r['net'] in ('STM_D_P','STM_D_N')}
    removed=[];removed_native=[]
    for item in list(board.GetTracks()):
        if item.GetNetname() in ('STM_D_P','STM_D_N'):
            assert item.m_Uuid.AsString() in expected, 'Refuse to remove non-generic USB routing'
            removed.append(dict(uuid=item.m_Uuid.AsString(),net=item.GetNetname(),
                                kind='via' if isinstance(item,pcb.PCB_VIA) else 'track'))
            # Keep detached wrappers alive: KiCad10's Remove ownership handoff
            # can invalidate SWIG type registration when wrappers are collected.
            removed_native.append(item);board.RemoveNative(item)
    assert {r['uuid'] for r in removed}==expected
    added=[]
    for net,pos,in_pad in [('STM_D_P',(13.3,21.1),True),('STM_D_N',(13.7,20.7),False)]:
        v=pcb.PCB_VIA(board);v.SetPosition(vec(*pos));v.SetWidth(pcb.FromMM(.40));v.SetDrill(pcb.FromMM(.20))
        v.SetViaType(pcb.VIATYPE_THROUGH);v.SetLayerPair(pcb.F_Cu,pcb.B_Cu);v.SetNet(board.FindNet(net));board.Add(v)
        added.append(dict(uuid=v.m_Uuid.AsString(),net=net,kind='via',at_mm=pos,
                          copper_mm=.40,drill_mm=.20,via_in_pad=in_pad,
                          filled_and_copper_capped_required=in_pad))
    t=pcb.PCB_TRACK(board);t.SetStart(vec(14.1,21.1));t.SetEnd(vec(13.7,20.7));t.SetWidth(pcb.FromMM(.11))
    t.SetLayer(pcb.B_Cu);t.SetNet(board.FindNet('STM_D_N'));board.Add(t)
    added.append(dict(uuid=t.m_Uuid.AsString(),net='STM_D_N',kind='track',layer='B.Cu',
                      start_mm=[14.1,21.1],end_mm=[13.7,20.7],width_mm=.11))
    board.BuildConnectivity();pcb.ZONE_FILLER(board).Fill(board.Zones());pcb.SaveBoard(str(boardpath),board)
    assert sha(SOURCE/'pcbgolf.kicad_pcb')==source_hash
    drcpath=OUT/'usb-reservation-drc.json'
    subprocess.run([str(ROOT/'tools/kicad/bin/kicad-cli.exe'),'pcb','drc','--format','json','--severity-all',
                    '--all-track-errors','--refill-zones','--output',str(drcpath),str(boardpath)],check=True)
    drc=json.loads(drcpath.read_text())
    physical_types={'hole_to_hole','holes_co_located','clearance','hole_clearance','shorting_items',
                    'annular_width','drill_out_of_range','track_width','copper_edge_clearance',
                    'courtyards_overlap','solder_mask_bridge','connection_width','starved_thermal'}
    physical=[r for r in drc['violations'] if r['severity']=='error' or r['type'] in physical_types]
    assert not physical, physical
    paritypath=OUT/'connectivity.json'
    subprocess.run([str(ROOT/'tools/venv/Scripts/python.exe'),str(ROOT/'scripts/validate_connectivity.py'),
                    '--board',str(boardpath),'--project',str(OUT/'pcbgolf.kicad_pro'),
                    '--netlist-dir',str(OUT/'netlists'),'--output',str(paritypath)],cwd=ROOT,check=True)
    report=dict(status='USB access reserved; full USB routing remains',source_board_sha256=source_hash,
                source_unchanged=True,board_sha256=sha(boardpath),removed_generic_items=removed,
                added_items=added,nonrouting_physical_violations=0,
                total_vias=sum(isinstance(t,pcb.PCB_VIA) for t in board.GetTracks()),
                total_track_segments=sum(not isinstance(t,pcb.PCB_VIA) for t in board.GetTracks()),
                parity='passed',submission_ready=False,
                fabrication_requirement='STM_D_P via at U3.D9 must be epoxy-filled and copper-capped (POFV), then planarized/solderable; ordinary tenting is insufficient.',
                matching_note='P/N sites agree with USB routing agent; equal electrical path and impedance must be verified after full differential routing.')
    (OUT/'usb-reservation.json').write_text(json.dumps(report,indent=2)+'\n')
    # Avoid presenting the source escape report's stale item counts as current.
    (OUT/'escape-report.json').write_text(json.dumps(dict(status='Superseded by USB reservation',
        source_report=str(SOURCE/'escape-report.json'),current_report=str(OUT/'usb-reservation.json')),
        indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
