"""Measure source STEP assets with OpenCascade (dimensions in mm)."""
import json
from pathlib import Path
from OCP.STEPControl import STEPControl_Reader
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.IFSelect import IFSelect_RetDone

root = Path(__file__).resolve().parents[1]
rows = {}
for path in (root/'pcbgolf.3dshapes').rglob('*.step'):
    reader=STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(path)
    reader.TransferRoots()
    box=Bnd_Box(); BRepBndLib.AddOptimal_s(reader.OneShape(),box,False,False)
    lo, hi = box.CornerMin(), box.CornerMax()
    bounds=(lo.X(),lo.Y(),lo.Z(),hi.X(),hi.Y(),hi.Z())
    rows[str(path.relative_to(root)).replace('\\','/')]=dict(bounds=list(bounds),size=[bounds[i+3]-bounds[i] for i in range(3)])
(root/'reports/model-bounds.json').write_text(json.dumps(rows,indent=2))
for path, row in rows.items():
    print(Path(path).name, [round(v,3) for v in row['size']], [round(v,3) for v in row['bounds']])
