#!/usr/bin/env python3
"""Vertical-slice surface-expression geometry.

Single source of truth for the pilot review and pilot solver.  This module uses
only the Stage 1 spatial substrate/queries and BodyParts3D geometry.  The review
UI is not allowed to define its own masks.

All surface regions/lines are returned as explicit skin vertex-index sets plus
optional curves / deep-geometry overlays.  Hashes are deterministic and are
used to prove review-mask == solver-mask identity.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib,json,math,re
from pathlib import Path
from typing import Iterable
from spatial_core import AtlasStore, dot, vsub, vadd, vmul, norm, normalize, distance

Vec3=tuple[float,float,float]

REGISTRY=[
 {"id":"SR:dorsum_hand","group":"upper_limb","terms":["dorsum of the hand"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"skin over the hand skeletal envelope, distal to the wrist, on the dorsal half of the frozen hand frame","required_by":["LI4"]},
 {"id":"SR:anteromedial_wrist","group":"upper_limb","terms":["anteromedial aspect of the wrist"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"wrist-local skin band centered on the wrist, restricted to palmar/anterior and medial halves of the side-specific wrist frame","required_by":["HT7"]},
 {"id":"SR:palmar_wrist_crease","group":"upper_limb","terms":["palmar wrist crease"],"kind":"surface_line","status":"DRAFT_HUMAN_REVIEW",
  "definition":"thin skin curve at the wrist transverse plane, restricted to the palmar half of the wrist capsule","required_by":["HT7","LU6"]},
 {"id":"SR:dorsal_wrist_crease","group":"upper_limb","terms":["dorsal wrist crease"],"kind":"surface_line","status":"DRAFT_HUMAN_REVIEW",
  "definition":"thin skin curve at the wrist transverse plane, restricted to the dorsal half of the wrist capsule","required_by":["LI7","TE6"]},
 {"id":"SR:anterolateral_forearm","group":"upper_limb","terms":["anterolateral aspect of the forearm"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"forearm-capsule skin between elbow and wrist joint bands, restricted to anterior and lateral halves in the side-specific forearm frame","required_by":["LU6"]},
 {"id":"SR:posterolateral_forearm","group":"upper_limb","terms":["posterolateral aspect of the forearm"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"forearm-capsule skin between elbow and wrist joint bands, restricted to posterior and lateral halves in the side-specific forearm frame","required_by":["LI7"]},
 {"id":"SR:posterior_forearm","group":"upper_limb","terms":["posterior aspect of the forearm"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"forearm-capsule skin between elbow and wrist joint bands, restricted to the posterior half of the side-specific forearm frame","required_by":["TE6"]},
 {"id":"SR:face_region","group":"head_face","terms":["on the face"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"anterior facial skin from the mandibular inferior border up to the frontal/supraorbital forehead boundary; excludes neck and cranial vault","required_by":["ST1","ST2","ST4"]},
 {"id":"SR:head_region","group":"head_face","terms":["on the head"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"cranial-vault skin superior to the forehead/face transition and superior to the mandibular-neck transition","required_by":["GB14","TE20"]},
 {"id":"SR:nasolabial_sulcus","group":"head_face","terms":["nasolabial sulcus"],"kind":"surface_line","status":"PROPOSED_UNRESOLVED",
  "definition":"BodyParts3D skin has no explicit nasolabial crease annotation; no curvature proxy is accepted","required_by":["ST4"]},
 {"id":"SR:lateral_thorax","group":"trunk","terms":["lateral thoracic region"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"lateral-facing thoracic trunk skin between shoulder and upper-abdominal transition, with all upper-limb skin capsules explicitly excluded","required_by":["GB23"]},
 {"id":"SR:midaxillary_line","group":"trunk","terms":["midaxillary line"],"kind":"surface_line","status":"DRAFT_HUMAN_REVIEW",
  "definition":"thin vertical lateral-thorax skin curve near the coronal plane through the trunk origin, with upper-limb skin excluded","required_by":["GB23"]},
 {"id":"SR:fourth_intercostal_space","group":"trunk","terms":["fourth intercostal space"],"kind":"surface_band","status":"DRAFT_HUMAN_REVIEW",
  "definition":"lateral thoracic skin band lying between the actual lateral 4th- and 5th-rib shapes on each side; upper-limb skin excluded","required_by":["GB23"]},
 {"id":"SR:lateral_abdomen","group":"trunk","terms":["lateral abdomen"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"lateral-facing abdominal trunk skin between costal and pelvic transitions, with upper-limb skin capsules explicitly excluded","required_by":["GB26"]},
 {"id":"SR:anterior_neck","group":"neck","terms":["anterior region of the neck","anterior aspect of the neck"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"anterior neck skin bounded superiorly by the mandibular inferior border and inferiorly by the clavicle/sternal transition","required_by":["ST10","LI18","LI17","ST9"]},
 {"id":"SR:posterior_median_line","group":"back","terms":["posterior median line"],"kind":"surface_line","status":"DRAFT_HUMAN_REVIEW",
  "definition":"thin connected posterior trunk skin curve within the midsagittal plane; upper-limb skin excluded","required_by":["BL17","BL23","BL25"]},
 {"id":"SR:upper_back","group":"back","terms":["upper back region"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"posterior thoracic trunk skin, excluding upper-limb skin capsules","required_by":["BL17"]},
 {"id":"SR:lumbar_region","group":"back","terms":["lumbar region"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"posterior lumbar trunk skin over the lumbar axial interval, excluding upper-limb skin capsules","required_by":["BL23","BL25"]},
 {"id":"SR:posterior_knee","group":"lower_limb","terms":["posterior aspect of the knee"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"skin inside the knee-local capsule and on the posterior half of the knee frame","required_by":["BL40"]},
 {"id":"SR:popliteal_crease","group":"lower_limb","terms":["popliteal crease"],"kind":"surface_line","status":"DRAFT_HUMAN_REVIEW",
  "definition":"thin posterior knee skin curve at the knee transverse plane, bounded by the knee capsule","required_by":["BL40"]},
 {"id":"SR:radius_ulna_interosseous_space","group":"upper_limb","terms":["interosseous space between the radius and the ulna"],"kind":"deep_space","status":"DRAFT_HUMAN_REVIEW",
  "definition":"3D midpoint locus of paired nearest radius/ulna bone surfaces at successive forearm longitudinal stations","required_by":["TE6"]}
]
REGISTRY_BY_ID={x["id"]:x for x in REGISTRY}

@dataclass
class GeometryResult:
 registry_id:str
 status:str
 surface_vertex_indices:list[int]
 curves:list[list[Vec3]]
 markers:list[dict]
 deep_paths:list[dict]
 hidden_surface_vertex_indices:list[int]
 view:str
 notes:list[str]
 def vertex_hash(self)->str:
  raw=",".join(map(str,sorted(set(self.surface_vertex_indices)))).encode()
  return hashlib.sha256(raw).hexdigest()
 def geometry_hash(self)->str:
  payload={"vertices":sorted(set(self.surface_vertex_indices)),
           "curves":[[[round(v,9) for v in p] for p in c] for c in self.curves],
           "markers":self.markers,
           "deep_paths":[{"side":p["side"],"points":[[round(v,9) for v in q] for q in p["points"]],"source_part_ids":p.get("source_part_ids",[])} for p in self.deep_paths]}
  return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()

class GeometryContext:
 def __init__(self,store:AtlasStore,substrate:dict,skin_part_id="FJ2810"):
  self.store=store;self.sub=substrate;self.skin_part_id=skin_part_id
  self.skin=list(store.vertices(skin_part_id));self.frames=substrate["frames"];self.joints=substrate["joints"]
  gf=substrate["global_frame"];self.origin=tuple(gf["origin"]);self.left=tuple(gf["axes"]["left"]);self.sup=tuple(gf["axes"]["superior"]);self.ant=tuple(gf["axes"]["anterior"])
  self.pskin=[self.patient(p) for p in self.skin]
  self._part_cache={}
  self.upper_limb_skin=set()
  for side in ("left","right"):
   for seg in ("upper_arm","forearm","hand"):
    self.upper_limb_skin.update(self.segment_skin(side,seg,margin=0.025))
  self.mandible_ids=self.find_parts(("mandible",),system="skeletal")
  self.frontal_ids=self.find_parts(("frontal",),system="skeletal")
  self.clavicle_ids=self.find_parts(("clavicle",),system="skeletal")
  self.sternum_ids=self.find_parts(("sternum",),system="skeletal")
  if not self.mandible_ids: raise RuntimeError("mandible mesh not found")
  self.mandible_y_min=min(self.patient(v)[1] for pid in self.mandible_ids for v in store.vertices(pid))
  # forehead boundary: superior orbital/forehead transition approximated from the inferior frontal-bone quartile.
  # It is explicit, reviewable and shared by review + solver; it is not a hidden HTML heuristic.
  fyp=[self.patient(v)[1] for pid in self.frontal_ids for v in store.vertices(pid)]
  if not fyp: raise RuntimeError("frontal bone mesh not found")
  fyp.sort();self.forehead_boundary_y=fyp[max(0,int(len(fyp)*0.25)-1)]
  cy=[self.patient(v)[1] for pid in self.clavicle_ids for v in store.vertices(pid)]
  self.neck_lower_y=max(cy) if cy else self.patient(tuple(self.frames["trunk"]["origin"]))[1]
  self.trunk_origin=self.patient(tuple(self.frames["trunk"]["origin"]))
  self.shoulder_y=sum(self.patient(tuple(self.joints[s]["shoulder"]["center"]))[1] for s in ("left","right"))/2
  self.hip_y=sum(self.patient(tuple(self.joints[s]["hip"]["center"]))[1] for s in ("left","right"))/2

 def patient(self,p:Vec3)->Vec3:
  r=vsub(p,self.origin);return (dot(r,self.left),dot(r,self.sup),dot(r,self.ant))

 def world(self,q:Vec3)->Vec3:
  return vadd(self.origin,vadd(vmul(self.left,q[0]),vadd(vmul(self.sup,q[1]),vmul(self.ant,q[2]))))

 def find_parts(self,tokens:tuple[str,...],side:str|None=None,system:str|None=None)->list[str]:
  key=(tokens,side,system)
  if key in self._part_cache:return self._part_cache[key]
  out=[]
  for p in self.store.atlas["parts"]:
   n=p["name"].lower()
   if system and p.get("system")!=system:continue
   if side and side not in n:continue
   if all(t.lower() in n for t in tokens):out.append(p["id"])
  self._part_cache[key]=out;return out

 def part_points_patient(self,ids:Iterable[str])->list[Vec3]:
  return [self.patient(v) for pid in ids for v in self.store.vertices(pid)]

 def axis_metrics(self,q:Vec3,a:Vec3,b:Vec3):
  ab=vsub(b,a);L=norm(ab);u=normalize(ab);t=dot(vsub(q,a),u);proj=vadd(a,vmul(u,t));r=distance(q,proj)
  return t,L,r,proj,u

 def segment_endpoints(self,side:str,seg:str)->tuple[Vec3,Vec3]:
  if seg=="upper_arm":
   return self.patient(tuple(self.joints[side]["shoulder"]["center"])),self.patient(tuple(self.joints[side]["elbow"]["center"]))
  if seg=="forearm":
   return self.patient(tuple(self.joints[side]["elbow"]["center"])),self.patient(tuple(self.joints[side]["wrist"]["center"]))
  if seg=="hand":
   a=self.patient(tuple(self.joints[side]["wrist"]["center"]));fr=self.frames[f"{side}_hand"];b=self.patient(tuple(fr["distal"]));return a,b
  if seg=="thigh":
   return self.patient(tuple(self.joints[side]["hip"]["center"])),self.patient(tuple(self.joints[side]["knee"]["center"]))
  if seg=="lower_leg":
   return self.patient(tuple(self.joints[side]["knee"]["center"])),self.patient(tuple(self.joints[side]["ankle"]["center"]))
  raise KeyError(seg)

 def segment_bone_radius(self,side:str,seg:str)->float:
  fr=self.frames[f"{side}_{seg}"];a,b=self.segment_endpoints(side,seg);mx=0.0
  for pid in fr["defining_part_ids"]:
   for w in self.store.vertices(pid):
    q=self.patient(w);t,L,r,_,_=self.axis_metrics(q,a,b)
    if -0.02<=t<=L+0.02:mx=max(mx,r)
  return mx

 def segment_skin(self,side:str,seg:str,margin=.02,end_margin=.02)->set[int]:
  a,b=self.segment_endpoints(side,seg);rad=self.segment_bone_radius(side,seg)+margin;out=set()
  for i,q in enumerate(self.pskin):
   t,L,r,_,_=self.axis_metrics(q,a,b)
   if -end_margin<=t<=L+end_margin and r<=rad:out.add(i)
  return out

 def local_components(self,side:str,seg:str,q:Vec3):
  fr=self.frames[f"{side}_{seg}"];a,b=self.segment_endpoints(side,seg);t,L,r,proj,u=self.axis_metrics(q,a,b)
  outward=tuple(fr["axes"]["outward"])
  # frame axes are world vectors; convert to patient coordinates.
  op=(dot(outward,self.left),dot(outward,self.sup),dot(outward,self.ant))
  surfkey="palmar" if "palmar" in fr["axes"] else ("dorsal" if "dorsal" in fr["axes"] else "anterior")
  sa=tuple(fr["axes"].get(surfkey,fr["axes"].get("anterior",(0,0,1))))
  sp=(dot(sa,self.left),dot(sa,self.sup),dot(sa,self.ant))
  rel=vsub(q,proj)
  return t,L,dot(rel,normalize(op)),dot(rel,normalize(sp)),r

 def nearest_indices(self,points:list[Vec3],indices:set[int],limit=1)->list[int]:
  out=[]
  for p in points:
   q=self.patient(p);best=sorted(indices,key=lambda i:distance(self.pskin[i],q))[:limit];out.extend(best)
  return out

def _view(regid:str)->str:
 if regid in {"SR:dorsum_hand","SR:dorsal_wrist_crease","SR:posterolateral_forearm","SR:posterior_forearm","SR:posterior_median_line","SR:upper_back","SR:lumbar_region","SR:posterior_knee","SR:popliteal_crease"}:return "back"
 if regid in {"SR:lateral_thorax","SR:midaxillary_line","SR:fourth_intercostal_space","SR:lateral_abdomen"}:return "left_hidden_arms"
 if regid=="SR:radius_ulna_interosseous_space":return "back_bones"
 return "front"

def _side_from_q(q:Vec3)->str:return "left" if q[0]>=0 else "right"

def _line_order(ctx:GeometryContext,idxs:Iterable[int],axis:int=0)->list[Vec3]:
 vals=sorted((ctx.pskin[i] for i in set(idxs)),key=lambda q:(q[axis],q[(axis+1)%3],q[(axis+2)%3]))
 return [ctx.world(q) for q in vals]

def _rib_parts(ctx:GeometryContext,n:int,side:str)->list[str]:
 word={4:"fourth",5:"fifth"}[n]
 patterns=(f"rib {n}",f"{n}th rib",f"{n}rd rib",f"{n}nd rib",f"{n}st rib",f"{word} rib",f"rib, {word}",f"rib {word}")
 found=[]
 for p in ctx.store.atlas["parts"]:
  nm=p["name"].lower()
  if p.get("system")!="skeletal" or side not in nm:continue
  if any(k in nm for k in patterns):found.append(p["id"])
 if found:return found
 # permissive fallback for names like "Left 4th rib"
 ords={4:"4th",5:"5th"}
 return [p["id"] for p in ctx.store.atlas["parts"] if p.get("system")=="skeletal" and side in p["name"].lower() and "rib" in p["name"].lower() and ords[n] in p["name"].lower()]

def _bone_centroid(ctx,ids):
 pts=[v for pid in ids for v in ctx.store.vertices(pid)]
 if not pts:return None
 return tuple(sum(p[k] for p in pts)/len(pts) for k in range(3))

def _wrist_markers(ctx:GeometryContext):
 out=[]
 for side in ("left","right"):
  pis=ctx.find_parts(("pisiform",),side=side,system="skeletal")
  sty=ctx.find_parts(("styloid","ulna"),side=side,system="skeletal")
  if pis:
   out.append({"label":f"{side} pisiform","point":_bone_centroid(ctx,pis),"source_part_ids":pis})
  if sty:
   out.append({"label":f"{side} ulnar styloid","point":_bone_centroid(ctx,sty),"source_part_ids":sty})
  else:
   # Explicit fallback marker: distal ulna cap, labeled as such rather than pretending it is a styloid mesh.
   ul=ctx.find_parts(("ulna",),side=side,system="skeletal")
   if ul:
    w=ctx.patient(tuple(ctx.joints[side]["wrist"]["center"]));pts=[(ctx.patient(v),v) for pid in ul for v in ctx.store.vertices(pid)]
    pts.sort(key=lambda x:distance(x[0],w))
    cap=[v for _,v in pts[:max(8,len(pts)//50)]]
    out.append({"label":f"{side} distal ulna cap (styloid-bearing end; no separate styloid mesh)","point":_bone_centroid_raw(cap),"source_part_ids":ul})
 return out

def _bone_centroid_raw(pts):
 return tuple(sum(p[k] for p in pts)/len(pts) for k in range(3))

def execute(ctx:GeometryContext,regid:str)->GeometryResult:
 spec=REGISTRY_BY_ID[regid]
 if spec["status"]=="PROPOSED_UNRESOLVED":
  return GeometryResult(regid,"UNRESOLVED",[],[],[],[],[],_view(regid),["No approved BodyParts3D geometric definition; deliberately unresolved."])
 selected=set();curves=[];markers=[];deep_paths=[];notes=[];hidden=set()
 # Surface orientation below is derived from local/global frame coordinates, not HTML.
 if regid=="SR:dorsum_hand":
  for side in ("left","right"):
   eligible=ctx.segment_skin(side,"hand",margin=.018,end_margin=.005)
   for i in eligible:
    t,L,outw,surf,r=ctx.local_components(side,"hand",ctx.pskin[i])
    if 0<=t<=L+0.005 and surf>0:selected.add(i)
 elif regid=="SR:anteromedial_wrist":
  for side in ("left","right"):
   fore=ctx.segment_skin(side,"forearm",margin=.025,end_margin=.025);w=ctx.patient(tuple(ctx.joints[side]["wrist"]["center"]))
   for i in fore:
    t,L,outw,surf,r=ctx.local_components(side,"forearm",ctx.pskin[i])
    if abs(t-L)<=0.035 and surf>0 and outw<0:selected.add(i)
 elif regid in ("SR:palmar_wrist_crease","SR:dorsal_wrist_crease"):
  pal=regid.startswith("SR:palmar")
  for side in ("left","right"):
   fore=ctx.segment_skin(side,"forearm",margin=.025,end_margin=.015);line=[]
   for i in fore:
    t,L,outw,surf,r=ctx.local_components(side,"forearm",ctx.pskin[i])
    if abs(t-L)<=0.004 and ((surf>0) if pal else (surf<0)):
     selected.add(i);line.append(i)
   curves.append(_line_order(ctx,line,axis=0))
  markers=_wrist_markers(ctx)
 elif regid in ("SR:anterolateral_forearm","SR:posterolateral_forearm","SR:posterior_forearm"):
  for side in ("left","right"):
   eligible=ctx.segment_skin(side,"forearm",margin=.025,end_margin=.0)
   for i in eligible:
    t,L,outw,surf,r=ctx.local_components(side,"forearm",ctx.pskin[i])
    if not (0.06*L<=t<=0.94*L):continue
    if regid=="SR:anterolateral_forearm" and surf>0 and outw>0:selected.add(i)
    elif regid=="SR:posterolateral_forearm" and surf<0 and outw>0:selected.add(i)
    elif regid=="SR:posterior_forearm" and surf<0:selected.add(i)
 elif regid in ("SR:face_region","SR:head_region","SR:anterior_neck"):
  for i,q in enumerate(ctx.pskin):
   x,y,z=q
   if i in ctx.upper_limb_skin:continue
   if regid=="SR:face_region" and ctx.mandible_y_min<=y<=ctx.forehead_boundary_y and z>=ctx.trunk_origin[2]:selected.add(i)
   elif regid=="SR:head_region" and y>=ctx.forehead_boundary_y:selected.add(i)
   elif regid=="SR:anterior_neck" and ctx.neck_lower_y<=y<=ctx.mandible_y_min and z>=ctx.trunk_origin[2]:selected.add(i)
  if regid=="SR:anterior_neck":
   markers=[
    {"label":"mandible inferior boundary","point":ctx.world((0,ctx.mandible_y_min,ctx.trunk_origin[2])),"source_part_ids":ctx.mandible_ids},
    {"label":"clavicular/sternal lower boundary","point":ctx.world((0,ctx.neck_lower_y,ctx.trunk_origin[2])),"source_part_ids":ctx.clavicle_ids+ctx.sternum_ids}
   ]
  else:
   markers=[
    {"label":"mandible inferior boundary","point":ctx.world((0,ctx.mandible_y_min,ctx.trunk_origin[2])),"source_part_ids":ctx.mandible_ids},
    {"label":"forehead boundary (inferior frontal-bone quartile plane)","point":ctx.world((0,ctx.forehead_boundary_y,ctx.trunk_origin[2])),"source_part_ids":ctx.frontal_ids}
   ]
 elif regid in ("SR:lateral_thorax","SR:midaxillary_line","SR:lateral_abdomen","SR:upper_back","SR:lumbar_region","SR:posterior_median_line","SR:fourth_intercostal_space"):
  hidden=set(ctx.upper_limb_skin)
  thor_lo=ctx.hip_y+0.43*(ctx.shoulder_y-ctx.hip_y); abd_hi=thor_lo
  trunk_candidates=[i for i,q in enumerate(ctx.pskin) if i not in hidden]
  if regid=="SR:lateral_thorax":
   selected={i for i in trunk_candidates if thor_lo<=ctx.pskin[i][1]<=ctx.shoulder_y and abs(ctx.pskin[i][0])>=0.075}
  elif regid=="SR:midaxillary_line":
   selected={i for i in trunk_candidates if thor_lo<=ctx.pskin[i][1]<=ctx.shoulder_y and abs(ctx.pskin[i][0])>=0.075 and abs(ctx.pskin[i][2]-ctx.trunk_origin[2])<=0.006}
   for side in (-1,1):
    ids=[i for i in selected if ctx.pskin[i][0]*side>0];curves.append(_line_order(ctx,ids,axis=1))
  elif regid=="SR:lateral_abdomen":
   selected={i for i in trunk_candidates if ctx.hip_y<=ctx.pskin[i][1]<=abd_hi and abs(ctx.pskin[i][0])>=0.07}
  elif regid=="SR:upper_back":
   selected={i for i in trunk_candidates if thor_lo<=ctx.pskin[i][1]<=ctx.shoulder_y and ctx.pskin[i][2]<ctx.trunk_origin[2]}
  elif regid=="SR:lumbar_region":
   selected={i for i in trunk_candidates if ctx.hip_y-0.015<=ctx.pskin[i][1]<=thor_lo and ctx.pskin[i][2]<ctx.trunk_origin[2]}
  elif regid=="SR:posterior_median_line":
   selected={i for i in trunk_candidates if ctx.hip_y-0.015<=ctx.pskin[i][1]<=ctx.shoulder_y and ctx.pskin[i][2]<ctx.trunk_origin[2] and abs(ctx.pskin[i][0])<=0.005}
   curves=[_line_order(ctx,selected,axis=1)]
  elif regid=="SR:fourth_intercostal_space":
   rib_overlay=[]
   for side in ("left","right"):
    r4ids=_rib_parts(ctx,4,side);r5ids=_rib_parts(ctx,5,side)
    if not r4ids or not r5ids:
     return GeometryResult(regid,"UNRESOLVED",[],[],[],[],list(hidden),_view(regid),[f"Could not resolve actual 4th/5th rib meshes for {side}."])
    p4=ctx.part_points_patient(r4ids);p5=ctx.part_points_patient(r5ids)
    sign=1 if side=="left" else -1
    p4=[p for p in p4 if p[0]*sign>0.06];p5=[p for p in p5 if p[0]*sign>0.06]
    # use actual lateral rib point clouds.  Skin is in the band whose superior coordinate
    # lies between nearest lateral rib-4 and rib-5 samples at the same posterior/anterior vicinity.
    sample4=p4[::max(1,len(p4)//500)];sample5=p5[::max(1,len(p5)//500)]
    for i in trunk_candidates:
     q=ctx.pskin[i]
     if q[0]*sign<=0.065 or not (thor_lo-0.08<=q[1]<=ctx.shoulder_y):continue
     n4=min(sample4,key=lambda p:(p[2]-q[2])**2+(p[0]-q[0])**2)
     n5=min(sample5,key=lambda p:(p[2]-q[2])**2+(p[0]-q[0])**2)
     lo,hi=sorted((n4[1],n5[1]))
     if lo<=q[1]<=hi:selected.add(i)
    # Overlay the actual rib shapes, not a centroid plane.
    curves.append([ctx.world(p) for p in sorted(sample4,key=lambda p:p[2])])
    curves.append([ctx.world(p) for p in sorted(sample5,key=lambda p:p[2])])
    markers.append({"label":f"{side} 4th rib mesh","point":ctx.world(_centroid(sample4)),"source_part_ids":r4ids})
    markers.append({"label":f"{side} 5th rib mesh","point":ctx.world(_centroid(sample5)),"source_part_ids":r5ids})
 elif regid in ("SR:posterior_knee","SR:popliteal_crease"):
  line_mode=regid.endswith("crease")
  for side in ("left","right"):
   k=ctx.patient(tuple(ctx.joints[side]["knee"]["center"]));th_a,th_b=ctx.segment_endpoints(side,"thigh");ll_a,ll_b=ctx.segment_endpoints(side,"lower_leg")
   # local long axis = average proximal->distal directions across the joint.
   u1=normalize(vsub(th_b,th_a));u2=normalize(vsub(ll_b,ll_a));u=normalize(vadd(u1,u2))
   ids=[]
   for i,q in enumerate(ctx.pskin):
    rel=vsub(q,k);ax=dot(rel,u);rad=norm(vsub(rel,vmul(u,ax)))
    if rad>0.09:continue
    posterior=q[2]<k[2]
    if not posterior:continue
    if (abs(ax)<=0.004 if line_mode else abs(ax)<=0.055):
     selected.add(i);ids.append(i)
   if line_mode:curves.append(_line_order(ctx,ids,axis=0))
 elif regid=="SR:radius_ulna_interosseous_space":
  for side in ("left","right"):
   rid=ctx.find_parts(("radius",),side=side,system="skeletal");uid=ctx.find_parts(("ulna",),side=side,system="skeletal")
   if not rid or not uid:
    return GeometryResult(regid,"UNRESOLVED",[],[],[],[],[],_view(regid),[f"radius/ulna meshes missing for {side}"])
   rp=ctx.part_points_patient(rid);up=ctx.part_points_patient(uid);a,b=ctx.segment_endpoints(side,"forearm");u=normalize(vsub(b,a));L=distance(a,b)
   path=[]
   for frac in [0.10+i*0.05 for i in range(17)]:
    t=frac*L;rw=[p for p in rp if abs(dot(vsub(p,a),u)-t)<0.006];uw=[p for p in up if abs(dot(vsub(p,a),u)-t)<0.006]
    if not rw or not uw:continue
    # nearest paired bone surfaces in the station slice
    best=None
    for pr in rw[::max(1,len(rw)//35)]:
     pu=min(uw,key=lambda x:distance(pr,x));d=distance(pr,pu)
     if best is None or d<best[0]:best=(d,pr,pu)
    if best:path.append(ctx.world(vmul(vadd(best[1],best[2]),0.5)))
   deep_paths.append({"side":side,"points":path,"source_part_ids":rid+uid})
   markers.append({"label":f"{side} radius","point":_bone_centroid(ctx,rid),"source_part_ids":rid})
   markers.append({"label":f"{side} ulna","point":_bone_centroid(ctx,uid),"source_part_ids":uid})
 else:
  return GeometryResult(regid,"INVALID",[],[],[],[],[],_view(regid),["unimplemented registry id"])
 if not selected and not deep_paths and spec["kind"]!="deep_space":
  notes.append("definition executed but produced an empty geometry set")
  status="UNRESOLVED"
 else:status="RESOLVED"
 return GeometryResult(regid,status,sorted(selected),curves,markers,deep_paths,sorted(hidden),_view(regid),notes)

def _centroid(pts):
 return tuple(sum(p[k] for p in pts)/len(pts) for k in range(3))

def execute_all(store:AtlasStore,substrate:dict)->dict[str,GeometryResult]:
 ctx=GeometryContext(store,substrate)
 return {e["id"]:execute(ctx,e["id"]) for e in REGISTRY}
