"""Merge checked critical copper between identical placements, without moving parts.

Run using native KiCad Python. The output is a new project copy. A geometry or
net mismatch stops the merge; native DRC and return/current checks follow it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import pcbnew as pcb


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def footprint_signature(fp):
    return (fp.GetFPIDAsString(),fp.GetValue(),fp.GetPosition().x,fp.GetPosition().y,
            round(fp.GetOrientationDegrees(),6),fp.GetLayer(),
            sorted((p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y) for p in fp.Pads()))


def track_key(t):
    if isinstance(t,pcb.PCB_VIA):
        p=t.GetPosition()
        return ('via',t.GetNetname(),p.x,p.y,t.GetWidth(pcb.F_Cu),t.GetDrillValue(),tuple(t.GetLayerSet().CuStack()))
    a,b=t.GetStart(),t.GetEnd();ends=sorted([(a.x,a.y),(b.x,b.y)])
    middle=(t.GetMid().x,t.GetMid().y) if isinstance(t,pcb.PCB_ARC) else None
    return ('arc' if middle else 'track',t.GetNetname(),t.GetLayer(),t.GetWidth(),tuple(ends),middle)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',type=Path,required=True);parser.add_argument('--addon',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--nets',default=r'^(USB_D_[NP]|CH[1-4]_D_[NP]|STM_D_[NP]|GND)$')
    parser.add_argument('--overwrite-output',action='store_true');args=parser.parse_args()
    if args.out.resolve() in [args.base.resolve(),args.addon.resolve()]:raise ValueError('Use a new output board')
    if args.out.exists() and not args.overwrite_output:raise ValueError('Output exists; choose a new output or explicitly overwrite output')
    before={str(p):digest(p) for p in (args.base,args.addon)}
    base=pcb.LoadBoard(str(args.base.resolve()));addon=pcb.LoadBoard(str(args.addon.resolve()))
    if base.GetCopperLayerCount()!=addon.GetCopperLayerCount():raise ValueError('Layer count differs')
    a={f.GetReference():footprint_signature(f) for f in base.GetFootprints()}
    b={f.GetReference():footprint_signature(f) for f in addon.GetFootprints()}
    mismatch=[r for r in a.keys()|b.keys() if a.get(r)!=b.get(r)]
    if mismatch:raise ValueError('Footprint placement or net differences: '+', '.join(sorted(mismatch)))
    pattern=re.compile(args.nets);keys={track_key(t) for t in base.GetTracks()};uids={t.m_Uuid.AsString() for t in base.GetTracks()}
    added=[];skipped=0
    for source in addon.GetTracks():
        if not pattern.fullmatch(source.GetNetname()):continue
        key=track_key(source)
        if key in keys:skipped+=1;continue
        if source.m_Uuid.AsString() in uids:raise ValueError('Same track UUID has different geometry')
        if isinstance(source,pcb.PCB_VIA):
            target=pcb.PCB_VIA(base);target.SetPosition(source.GetPosition())
            target.SetWidth(source.GetWidth(pcb.F_Cu));target.SetDrill(source.GetDrillValue())
            target.SetViaType(source.GetViaType());target.SetLayerPair(source.TopLayer(),source.BottomLayer())
            target.SetIsFree(True)
        elif isinstance(source,pcb.PCB_ARC):
            target=pcb.PCB_ARC(base);target.SetStart(source.GetStart());target.SetMid(source.GetMid());target.SetEnd(source.GetEnd())
            target.SetWidth(source.GetWidth());target.SetLayer(source.GetLayer())
        else:
            target=pcb.PCB_TRACK(base);target.SetStart(source.GetStart());target.SetEnd(source.GetEnd())
            target.SetWidth(source.GetWidth());target.SetLayer(source.GetLayer())
        target.SetNet(base.FindNet(source.GetNetname()));target.SetLocked(True);target.SetUuid(source.m_Uuid)
        base.Add(target);keys.add(key);uids.add(target.m_Uuid.AsString());added.append(target.m_Uuid.AsString())
    zone_ids={z.m_Uuid.AsString() for z in base.Zones()};zone_added=[]
    for source in addon.Zones():
        if not pattern.fullmatch(source.GetNetname()) or source.m_Uuid.AsString() in zone_ids:continue
        target=pcb.ZONE(source);target.SetParent(base);target.SetNet(base.FindNet(source.GetNetname()))
        base.Add(target);zone_ids.add(target.m_Uuid.AsString());zone_added.append(target.m_Uuid.AsString())
    outdir=args.out.parent;outdir.mkdir(parents=True,exist_ok=True)
    for path in args.base.parent.iterdir():
        if path.is_file() and (path.suffix in ('.kicad_sch','.kicad_sym') or path.name in ('fp-lib-table','sym-lib-table')):
            shutil.copy2(path,outdir/path.name)
        elif path.is_dir() and path.suffix in ('.pretty','.3dshapes'):
            shutil.copytree(path,outdir/path.name,dirs_exist_ok=True)
    for suffix in ('.kicad_pro','.kicad_dru'):
        source=args.base.with_suffix(suffix)
        if source.exists():shutil.copy2(source,args.out.with_suffix(suffix))
    base.BuildConnectivity();pcb.ZONE_FILLER(base).Fill(base.Zones());pcb.SaveBoard(str(args.out.resolve()),base)
    if any(digest(Path(p))!=d for p,d in before.items()):raise RuntimeError('An input changed during integration')
    report=dict(inputs=before,output=str(args.out),output_sha256=digest(args.out),added_copper_items=added,added_zones=zone_added,
                skipped_identical_copper=skipped,matching_footprints=len(a),validated=False,
                required_checks=['Native DRC and merged schematic parity','USB filled reference coverage','Actual power connectivity and copper neck widths'])
    args.out.with_suffix('.merge.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(added_copper=len(added),added_zones=len(zone_added),skipped=skipped,output=str(args.out))))


if __name__=='__main__':main()
