#!/usr/bin/env python3
"""Independent C v3 Stage 1 frame validator.

Does not import build_stage1_substrate.py or spatial_core.py.
Recomputes reference directions directly from BodyParts3D binaries.
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
  o=[]
  for x in ids:o.extend(self.vertices(x))
  return o
 def centroid(self,ids):return avg(self.points(ids))

def main():
 ap=argparse.ArgumentParser();ap.add_argument("substrate");ap.add_argument("--model-dir",default="public/models");ap.add_argument("--report",default=".tmp/c-v3-stage1/stage1-frame-validation.json");args=ap.parse_args()
 s=json.loads(Path(args.substrate).read_text());a=RawAtlas(args.model_dir);errors=[];warnings=[];checks=0
 def ck(cond,code,detail=None):
  nonlocal checks;checks+=1
  if not cond:errors.append({"code":code,"detail":detail})

 ck(s.get("status")=="GENERATED_NOT_VALIDATED","PREMATURE_STATUS",s.get("status"))
 ck(s["source"]["atlas_sha256"]==sha(Path(args.model_dir)/"atlas.json"),"ATLAS_SHA_MISMATCH")
 ck(s["prohibitions"]=={"legacy_coordinate_input":False,"exclusive_skin_region_partition":False,"acupoint_specific_logic":False},"PROHIBITION_CONTRACT_MISMATCH",s.get("prohibitions"))

 gf=s["global_frame"];axes=gf["axes"];left=tuple(axes["left"]);sup=tuple(axes["superior"]);ant=tuple(axes["anterior"])
 for n,v in (("left",left),("superior",sup),("anterior",ant)):ck(abs(norm(v)-1)<1e-8,"GLOBAL_AXIS_NOT_UNIT",{"axis":n,"norm":norm(v)})
 for n,x,y in (("left-superior",left,sup),("left-anterior",left,ant),("superior-anterior",sup,ant)):ck(abs(dot(x,y))<1e-8,"GLOBAL_AXES_NOT_ORTHOGONAL",{"pair":n,"dot":dot(x,y)})

 # Independent skeletal sign references.
 lh=a.centroid(a.ids_exact("Left humerus"));rh=a.centroid(a.ids_exact("Right humerus"))
 lf=a.centroid(a.ids_exact("Left femur"));rf=a.centroid(a.ids_exact("Right femur"))
 lc=a.centroid(a.ids_exact("Left clavicle"));rc=a.centroid(a.ids_exact("Right clavicle"))
 lhip=a.centroid(a.ids_exact("Left hip bone"));rhip=a.centroid(a.ids_exact("Right hip bone"))
 lr=sub(avg([lh,lf,lc,lhip]),avg([rh,rf,rc,rhip]))
 ck(dot(left,normalize(lr))>0.95,"LEFT_AXIS_WRONG_SIGN_OR_ALIGNMENT",dot(left,normalize(lr)))
 sac=a.centroid(a.ids_exact("Sacrum"));clav=avg([lc,rc]);si=sub(clav,sac)
 ck(dot(sup,normalize(si))>0.90,"SUPERIOR_AXIS_WRONG_SIGN_OR_ALIGNMENT",dot(sup,normalize(si)))
 stern=a.centroid(a.ids_exact("Body of sternum"))
 vids=[p["id"] for p in a.atlas["parts"] if p.get("system")=="skeletal" and re.search(r"\bvertebra$",p["name"].lower())]
 spine=a.centroid(vids);pa=sub(stern,spine)
 ck(dot(ant,normalize(pa))>0.80,"ANTERIOR_AXIS_WRONG_SIGN_OR_ALIGNMENT",dot(ant,normalize(pa)))

 expected={"left_upper_arm","right_upper_arm","left_forearm","right_forearm","left_thigh","right_thigh","left_lower_leg","right_lower_leg","left_hand","right_hand","left_foot","right_foot","trunk","head_neck"}
 ck(set(s["frames"])==expected,"FRAME_SET_MISMATCH",sorted(set(s["frames"])^expected))
 for name,fr in s["frames"].items():
  ax=fr["axes"]
  if "proximal_to_distal" in ax:
   long=tuple(ax["proximal_to_distal"]);out=tuple(ax["outward"]);aa=tuple(ax["anterior"])
   ck(abs(norm(long)-1)<1e-8,"LOCAL_LONG_NOT_UNIT",name);ck(abs(norm(out)-1)<1e-8,"LOCAL_OUT_NOT_UNIT",name);ck(abs(norm(aa)-1)<1e-8,"LOCAL_ANT_NOT_UNIT",name)
   ck(max(abs(dot(long,out)),abs(dot(long,aa)),abs(dot(out,aa)))<1e-7,"LOCAL_AXES_NOT_ORTHOGONAL",name)
   side=fr["side"];sgn=1 if side=="left" else -1
   ck(sgn*dot(out,left)>0.55,"LOCAL_OUTWARD_WRONG_SIDE",{"frame":name,"dot_left":dot(out,left)})
   ck(dot(aa,ant)>0.50,"LOCAL_ANTERIOR_INCONSISTENT",{"frame":name,"dot":dot(aa,ant)})
   prox=tuple(fr["proximal"]);distal=tuple(fr["distal"])
   ck(dot(sub(distal,prox),long)>0,"LOCAL_LONG_WRONG_DIRECTION",name)
   ck(fr["metrics"]["segment_length_m"]>0.03,"SEGMENT_TOO_SHORT",{"frame":name,"length":fr["metrics"]["segment_length_m"]})

 # Adjacent joint ordering and continuity.
 for side in ("left","right"):
  j={k:tuple(v["center"]) for k,v in s["joints"][side].items()}
  ua=tuple(s["frames"][f"{side}_upper_arm"]["axes"]["proximal_to_distal"])
  fa=tuple(s["frames"][f"{side}_forearm"]["axes"]["proximal_to_distal"])
  th=tuple(s["frames"][f"{side}_thigh"]["axes"]["proximal_to_distal"])
  ll=tuple(s["frames"][f"{side}_lower_leg"]["axes"]["proximal_to_distal"])
  ck(dot(sub(j["elbow"],j["shoulder"]),ua)>0,"SHOULDER_ELBOW_ORDER_FAIL",side)
  ck(dot(sub(j["wrist"],j["elbow"]),fa)>0,"ELBOW_WRIST_ORDER_FAIL",side)
  ck(dot(sub(j["knee"],j["hip"]),th)>0,"HIP_KNEE_ORDER_FAIL",side)
  ck(dot(sub(j["ankle"],j["knee"]),ll)>0,"KNEE_ANKLE_ORDER_FAIL",side)
  # Junctions must remain near the paired skeletal extents; normalized by adjacent segment length.
  ua_len=s["frames"][f"{side}_upper_arm"]["metrics"]["segment_length_m"]; fa_len=s["frames"][f"{side}_forearm"]["metrics"]["segment_length_m"]
  th_len=s["frames"][f"{side}_thigh"]["metrics"]["segment_length_m"];ll_len=s["frames"][f"{side}_lower_leg"]["metrics"]["segment_length_m"]
  ck(dist(j["elbow"],tuple(s["frames"][f"{side}_upper_arm"]["distal"]))<0.15*ua_len,"ELBOW_TOO_FAR_FROM_UPPER_ARM",side)
  ck(dist(j["elbow"],tuple(s["frames"][f"{side}_forearm"]["proximal"]))<0.15*fa_len,"ELBOW_TOO_FAR_FROM_FOREARM",side)
  ck(dist(j["knee"],tuple(s["frames"][f"{side}_thigh"]["distal"]))<0.15*th_len,"KNEE_TOO_FAR_FROM_THIGH",side)
  ck(dist(j["knee"],tuple(s["frames"][f"{side}_lower_leg"]["proximal"]))<0.15*ll_len,"KNEE_TOO_FAR_FROM_LOWER_LEG",side)

 # Bilateral length symmetry: broad threshold catches frame inversion/cross-body failures without assuming perfect anatomical symmetry.
 for seg in ("upper_arm","forearm","thigh","lower_leg","hand","foot"):
  l=s["frames"][f"left_{seg}"]["metrics"]["segment_length_m"];r=s["frames"][f"right_{seg}"]["metrics"]["segment_length_m"];ratio=l/r if r else 999
  ck(0.75<ratio<1.33,"BILATERAL_LENGTH_ASYMMETRY",{"segment":seg,"left":l,"right":r,"ratio":ratio})

 status="PASS" if not errors else "FAIL"
 report={"schema_version":"1.0.0","stage":"Stage1","test":"independent-frame-validation","status":status,"checks":checks,"errors":errors,"warnings":warnings,"promotion_allowed":False,
 "note":"PASS covers spatial frames only; registry, topology, query round-trip and human visual review are separate Stage 1 responsibilities."}
 p=Path(args.report);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2)+"\n");print(json.dumps({"status":status,"checks":checks,"errors":len(errors)}));raise SystemExit(0 if status=="PASS" else 1)
if __name__=="__main__":main()
