#!/usr/bin/env python3
from math import radians
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE={
'battery':((1500,1100,120),(0,0,220),(0,0,0)),'underbody_bracket':((500,800,20),(0,0,145),(0,0,0)),
'left_rail':((1700,90,160),(0,650,300),(0,0,0)),'right_rail':((1700,90,160),(0,-650,300),(0,0,0)),
'motor':((520,480,420),(650,0,520),(0,0,0.8)),'motor_bracket':((260,70,240),(650,295,520),(0,0,0)),
'controller':((360,260,150),(300,-360,610),(0,1.0,0)),'controller_bracket':((300,40,180),(300,-515,610),(0,0,0)),
'exhaust':((600,180,180),(720,480,450),(0,0,0)),'front_crossmember':((130,1150,120),(1020,0,330),(0,0,0)),
'ground_ref':((2800,1700,10),(0,0,0),(0,0,0)),'rear_module':((460,420,300),(-800,0,420),(0,0.6,0))}

def variant(v):
 d={k:[list(a),list(b),list(c)] for k,(a,b,c) in BASE.items()}
 if v=='V2':
  d['battery'][1]=[0,0,205];d['controller'][1]=[300,-375,610];d['motor'][1]=[680,0,520];d['motor'][2]=[0,0,2.2];d['rear_module'][2]=[0,0.1,0]
 return d

def loc(center,rot):
 from OCP.TopLoc import TopLoc_Location
 from OCP.gp import gp_Quaternion,gp_Trsf,gp_Vec,gp_EulerSequence
 q=gp_Quaternion();q.SetEulerAngles(gp_EulerSequence.gp_Extrinsic_XYZ,*[radians(x) for x in rot]);t=gp_Trsf();t.SetRotation(q);t.SetTranslationPart(gp_Vec(*center));return TopLoc_Location(t)

def write(v,path):
 from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
 from OCP.Interface import Interface_Static
 from OCP.STEPCAFControl import STEPCAFControl_Writer
 from OCP.STEPControl import STEPControl_AsIs
 from OCP.TCollection import TCollection_ExtendedString
 from OCP.TDataStd import TDataStd_Name
 from OCP.TDocStd import TDocStd_Document
 from OCP.XCAFApp import XCAFApp_Application
 from OCP.XCAFDoc import XCAFDoc_DocumentTool
 from OCP.gp import gp_Pnt
 app=XCAFApp_Application.GetApplication_s();fmt=TCollection_ExtendedString('XmlXCAF');doc=TDocStd_Document(fmt);app.NewDocument(fmt,doc);tool=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main());tool.SetAutoNaming_s(False)
 root=tool.NewShape();TDataStd_Name.Set_s(root,TCollection_ExtendedString('Vehicle'))
 for name,(size,center,rot) in variant(v).items():
  sx,sy,sz=size;shape=BRepPrimAPI_MakeBox(gp_Pnt(-sx/2,-sy/2,-sz/2),sx,sy,sz).Shape();part=tool.AddShape(shape,False);TDataStd_Name.Set_s(part,TCollection_ExtendedString(name+'_part'));comp=tool.AddComponent(root,part,loc(center,rot));TDataStd_Name.Set_s(comp,TCollection_ExtendedString(name))
 Interface_Static.SetCVal_s('write.step.schema','AP242DIS');Interface_Static.SetCVal_s('write.step.unit','MM');w=STEPCAFControl_Writer();w.SetNameMode(True);w.Transfer(doc,STEPControl_AsIs);path.parent.mkdir(parents=True,exist_ok=True);w.Write(str(path));return path

if __name__=='__main__':
 for v,f in [('V1','vehicle_v1.step'),('V2','vehicle_v2.step')]: print(write(v,ROOT/'data/step'/f))
