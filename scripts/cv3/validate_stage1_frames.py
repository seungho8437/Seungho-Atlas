#!/usr/bin/env python3
"""Independent C v3 Stage 1 frame validator.

No imports from Stage 1 builder/core. Recomputes orientation evidence directly
from BodyParts3D binaries and checks frame/joint invariants.
"""
from __future__ import annotations
import argparse,json,math,re,struct,hashlib
from pathlib import Path

def add(a,b):return (a[0]+b[0],a[1]+b[1],a[2]+b[2])
def sub(a,b):return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def mul(a,s):return (a[0]*s,a[1]*s,a[2]*s)
def dot(a,b):return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def norm(a):return math.sqrt(dot(a,a))
def normalize(a):
 n=norm(a)
 if n<=1e-15:raise ValueError("zero vector")
 return mul(a,1/n)
def avg(ps):return tuple(sum(p[i] for p in ps)/len(ps) for i in range(3))
def dist(a,b):return norm(sub(a,b))
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for z in iter(lambda:f.read(1<<20),b""):h.update(z)
 return h.hexdigest()

class RawAtlas:
 def __init__(self,root):
  self.root=Path(root);self.atlas=json.loads((self.root/"atlas.json").read_text());self.parts={p["id"]:p for p in self.atlas["parts"]};self.chunks={}
 def chunk(self,i):
  if i not in self.chunks:
   rec=self.atlas["chunks"][i];self.chunks[i]=(self.root/Path(rec["url"]).name).read_bytes()
  return self.chunks[i]
 def vertices(self,pid):
  p=self.parts[pid];raw=self.chunk(p["chunk"]);v=struct.unpack_from("<"+"f"*(p["vertexCount"]*3),raw,p["positions"])
  return [(v[i],v[i+1],v[i+2]) for i in range(0,len(v),3)]
 def ids_exact(self,name):
  m=[p["id"] for p in self.atlas["parts"] if p["name"].strip().lower()==name.strip().lower()]
  if len(m)!=1:raise RuntimeError((name,len(m)))
  return m
 def points(self,ids):
  out=[]
  for x in ids:out.extend(self.vertices(x))
  return out
 def centroid(self,ids):return avg(self.points(ids))

def main():
 ap=argparse.ArgumentParser();ap.add_argument("substrate");ap.add_argument("--model-dir",default="public/models");ap.add_argument("--report",default=".tmp/c-v3-stage1/frame-validation.json");args=ap.parse_args()
 s=json.loads(Path(args.substrate).read_text());a=RawAtlas(args.model_dir);errors=[];warnings=[];checks=0
 def ck(cond,code,detail=None):
  nonlocal checks;checks+=1
  if not cond:errors.append({"code":code,"detail":detail})
 ck(s.get("status")=="GENERATED_NOT_VALIDATED","PREMATURE_STATUS",s.get("status"))
 ck(s["source"]["atlas_sha256"]==sha(Path(args.model_dir)/"atlas.json"),"ATLAS_SHA_MISMATCH")
 ck(s["prohibitions"]=={"legacy_coordinate_input":False,"exclusive_skin_region_partition":False,"acupoint_specific_logic":False},"PROHIBITION_CONTRACT_MISMATCH",s.get("prohibitions"))

 gf=s["global_frame"];left=tuple(gf["axes"]["left"]);sup=tuple(gf["axes"]["superior"]);ant=tuple(gf["axes"]["anterior"])
 for n,v in (("left",left),("superior",sup),("anterior",ant)):ck(abs(norm(v)-1)<1e-8,"GLOBAL_AXIS_NOT_UNIT",{"axis":n,"norm":norm(v)})
 for n,x,y in (("left-superior",left,sup),("left-anterior",left,ant),("superior-anterior",sup,ant)):ck(abs(dot(x,y))<1e-8,"GLOBAL_AXES_NOT_ORTHOGONAL",{"pair":n,"dot":dot(x,y)})

 # Independent sign/alignment evidence.
 lh=a.centroid(a.ids_exact("Left humerus"));rh=a.centroid(a.ids_exact("Right humerus"))
 lf=a.centroid(a.ids_exact("Left femur"));rf=a.centroid(a.ids_exact("Right femur"))
 lc=a.centroid(a.ids_exact("Left clavicle"));rc=a.centroid(a.ids_exact("Right clavicle"))
 lhip=a.centroid(a.ids_exact("Left hip bone"));rhip=a.centroid(a.ids_exact("Right hip bone"))
 lr=sub(avg([lh,lf,lc,lhip]),avg([rh,rf,rc,rhip]))
 ck(dot(left,normalize(lr))>0.95,"LEFT_AXIS_WRONG",dot(left,normalize(lr)))
 c7=a.centroid(a.ids_exact("Seventh cervical vertebra"));l5=a.centroid(a.ids_exact("Fifth lumbar vertebra"))
 spine_sign=sub(c7,l5)
 ck(dot(sup,normalize(spine_sign))>0.95,"SUPERIOR_AXIS_WRONG",dot(sup,normalize(spine_sign)))
 stern=a.centroid(a.ids_exact("Body of sternum"))
 vids=[p["id"] for p in a.atlas["parts"] if p.get("system")=="skeletal" and re.search(r"\bvertebra$",p["name"].lower())]
 spine=a.centroid(vids);pa=sub(stern,spine)
 ck(dot(ant,normalize(pa))>0.80,"ANTERIOR_AXIS_WRONG",dot(ant,normalize(pa)))

 expected={"left_upper_arm","right_upper_arm","left_forearm","right_forearm","left_thigh","right_thigh","left_lower_leg","right_lower_leg","left_hand","right_hand","left_foot","right_foot","trunk","head_neck"}
 ck(set(s["frames"])==expected,"FRAME_SET_MISMATCH",sorted(set(s["frames"])^expected))
 for name,fr in s["frames"].items():
  ax=fr["axes"]
  if "proximal_to_distal" not in ax:continue
  long=tuple(ax["proximal_to_distal"]);out=tuple(ax["outward"]);surface_key="anterior" if "anterior" in ax else ("palmar" if "palmar" in ax else "dorsal");surf=tuple(ax[surface_key])
  ck(abs(norm(long)-1)<1e-8,"LOCAL_LONG_NOT_UNIT",name);ck(abs(norm(out)-1)<1e-8,"LOCAL_OUT_NOT_UNIT",name);ck(abs(norm(surf)-1)<1e-8,"LOCAL_SURFACE_NOT_UNIT",name)
  ck(max(abs(dot(long,out)),abs(dot(long,surf)),abs(dot(out,surf)))<1e-7,"LOCAL_AXES_NOT_ORTHOGONAL",name)
  side=fr["side"];sgn=1 if side=="left" else -1
  ck(sgn*dot(out,left)>0.55,"LOCAL_OUTWARD_WRONG_SIDE",{"frame":name,"dot_left":dot(out,left)})
  if surface_key in ("anterior","palmar"):ck(dot(surf,ant)>0.35,"LOCAL_ANTERIOR_OR_PALMAR_INCONSISTENT",{"frame":name,"dot":dot(surf,ant)})
  else:ck(dot(surf,sup)>0.35,"LOCAL_DORSAL_INCONSISTENT",{"frame":name,"dot":dot(surf,sup)})
  prox=tuple(fr["proximal"]);distal=tuple(fr["distal"])
  ck(dot(sub(distal,prox),long)>0,"LOCAL_LONG_WRONG_DIRECTION",name)
  ck(fr["metrics"]["segment_length_m"]>0.03,"SEGMENT_TOO_SHORT",{"frame":name,"length":fr["metrics"]["segment_length_m"]})

 # Chain order is the critical independent guard against the prior arm reversal.
 for side in ("left","right"):
  j={k:tuple(v["center"]) for k,v in s["joints"][side].items()}
  for a0,b0,frame,code in [
   ("shoulder","elbow",f"{side}_upper_arm","SHOULDER_ELBOW_ORDER_FAIL"),
   ("elbow","wrist",f"{side}_forearm","ELBOW_WRIST_ORDER_FAIL"),
   ("hip","knee",f"{side}_thigh","HIP_KNEE_ORDER_FAIL"),
   ("knee","ankle",f"{side}_lower_leg","KNEE_ANKLE_ORDER_FAIL")]:
   long=tuple(s["frames"][frame]["axes"]["proximal_to_distal"]);ck(dot(sub(j[b0],j[a0]),long)>0,code,side)
  # Joint centers must be close to both adjacent endpoint caps relative to segment length.
  for joint,fa,ea,fb,eb,codea,codeb in [
   ("elbow",f"{side}_upper_arm","distal",f"{side}_forearm","proximal","ELBOW_TOO_FAR_UPPER_ARM","ELBOW_TOO_FAR_FOREARM"),
   ("knee",f"{side}_thigh","distal",f"{side}_lower_leg","proximal","KNEE_TOO_FAR_THIGH","KNEE_TOO_FAR_LEG")]:
   p=j[joint];la=s["frames"][fa]["metrics"]["segment_length_m"];lb=s["frames"][fb]["metrics"]["segment_length_m"]
   ck(dist(p,tuple(s["frames"][fa][ea]))<0.12*la,codea,side)
   ck(dist(p,tuple(s["frames"][fb][eb]))<0.12*lb,codeb,side)

 for seg in ("upper_arm","forearm","thigh","lower_leg","hand","foot"):
  l=s["frames"][f"left_{seg}"]["metrics"]["segment_length_m"];r=s["frames"][f"right_{seg}"]["metrics"]["segment_length_m"];ratio=l/r if r else 999
  ck(0.75<ratio<1.33,"BILATERAL_LENGTH_ASYMMETRY",{"segment":seg,"ratio":ratio,"left":l,"right":r})

 status="PASS" if not errors else "FAIL"
 report={"schema_version":"1.0.0","stage":"Stage1","test":"independent-frame-validation","status":status,"checks":checks,"errors":errors,"warnings":warnings,"promotion_allowed":False,
  "note":"PASS validates spatial frame geometry only. It does not validate WHO semantics or any acupoint."}
 p=Path(args.report);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2)+"\n");print(json.dumps({"status":status,"checks":checks,"errors":len(errors)}));raise SystemExit(0 if status=="PASS" else 1)
if __name__=="__main__":main()
