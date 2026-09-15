from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.XCAFDoc import XCAFDoc_DocumentTool,XCAFDoc_ShapeTool
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.collections import Sequence_TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from pathlib import Path
import json,sys
p=Path(sys.argv[1]);doc=TDocStd_Document(TCollection_ExtendedString('pcbgolf'));reader=STEPCAFControl_Reader();reader.ReadFile(str(p));reader.Transfer(doc);st=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
seq=Sequence_TDF_Label();st.GetFreeShapes(seq)
print('ROOTS',seq.Length())
def name(label):
 attr=TDataStd_Name()
 return attr.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(),attr) else ''
def bounds(shape):
 b=Bnd_Box();BRepBndLib.AddOptimal_s(shape,b,False,False);lo,hi=b.CornerMin(),b.CornerMax();return [lo.X(),lo.Y(),lo.Z(),hi.X(),hi.Y(),hi.Z()]
for i in range(1,seq.Length()+1):
 label=seq.Value(i);print('root',name(label),bounds(st.GetShape_s(label)))
 kids=Sequence_TDF_Label();st.GetComponents_s(label,kids)
 print('children',kids.Length())
 result=[]
 for k in range(1,kids.Length()+1):
  child=kids.Value(k);a={'name':name(child),'bounds':bounds(st.GetShape_s(child))};result.append(a)
  if k<15:print(a)
 out=p.parent/'step-component-bounds.json';out.write_text(json.dumps(result,indent=2));print(out)
