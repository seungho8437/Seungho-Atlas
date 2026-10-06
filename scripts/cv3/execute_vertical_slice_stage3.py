#!/usr/bin/env python3
"""C v3 Vertical Slice v1 - Stage 3 pilot coordinate synthesis.

Consumes the frozen, human-approved Stage 2 repaired output. It never reparses
WHO text and never reads legacy C coordinates.

Stage 3 is deliberately conservative:
- only Stage-2 RESOLVED primary locations are eligible;
- a physical coordinate is emitted only for a synthesis family whose metric
  construction is fully determined by approved Stage 1/2 geometry;
- B/F-cun relations without an approved physical scale route remain unresolved;
- qualitative directional relations without a frozen displacement rule remain
  unresolved;
- final skin placement uses an aspect-directed ray cast, not nearest-on-skin.
"""
from __future__ import annotations
import argparse,hashlib,json,math
from pathlib import Path
from spatial_core import AtlasStore,ray_hits_part,vadd,vmul,vsub,dot,distance,normalize
from slice_surface_registry import execute_all,REGISTRY_BY_ID

COHORT=("HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26","ST2","ST10",
        "LI18","LI17","BL17","BL23","BL25","BL40","TE20","ST4","TE6","ST9")
SKIN_PART="FJ2810"
DIRECT_SURFACE_PROJECTION_BUDGET_M=0.03
DIRECT_SURFACE_INWARD_OFFSET_M=0.012

def sha256_file(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"))
def objhash(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def vec(a):return tuple(float(x) for x in a)

def patient_coords(p,sub):
 gf=sub["global_frame"];o=vec(gf["origin"]);left=vec(gf["axes"]["left"]);sup=vec(gf["axes"]["superior"]);ant=vec(gf["axes"]["anterior"])
 r=vsub(vec(p),o)
 return (dot(r,left),dot(r,sup),dot(r,ant))

def arc_midpoint(curve):
 if len(curve)<2:return None
 seg=[distance(vec(curve[i]),vec(curve[i+1])) for i in range(len(curve)-1)]
 total=sum(seg)
 if total<=1e-12:return vec(curve[len(curve)//2])
 target=total/2;acc=0.0
 for i,d in enumerate(seg):
  if acc+d>=target:
   t=(target-acc)/d if d>1e-15 else 0.0
   a=vec(curve[i]);b=vec(curve[i+1])
   return vadd(a,vmul(vsub(b,a),t))
  acc+=d
 return vec(curve[-1])

def side_of_curve(curve,sub):
 xs=[patient_coords(p,sub)[0] for p in curve]
 m=sum(xs)/len(xs)
 return "left" if m>0 else "right"

def dedupe_geometric_ray_hits(hits,tol_t=1e-6,tol_point=1e-6):
 groups=[]
 for h in hits:
  placed=False
  for g in groups:
   if abs(h.t-g[0].t)<=tol_t and distance(h.point,g[0].point)<=tol_point:
    g.append(h);placed=True;break
  if not placed:groups.append([h])
 return [min(g,key=lambda x:(x.t,x.triangle_index)) for g in groups]

def physical_calibration_ready(row):
 # A Stage-3 metric scale must be explicit, not inferred from joint distance.
 keys=("physical_scale_m_per_cun","physical_interval_m","nominal_interval_m","metric_length_m")
 return any(isinstance(row.get(k),(int,float)) and row.get(k)>0 for k in keys)

def primary_statement(point):
 return next((x for x in point["statements"] if x.get("section")=="location"),None)

def registry_operand(point,relation):
 ids=(relation.get("constraint") or {}).get("executable_argument_node_ids") or relation.get("executable_argument_node_ids") or []
 for nid in ids:
  rec=point["landmarks"].get(nid,{})
  g=rec.get("geometry") or {}
  if g.get("kind")=="surface_registry":return nid,g.get("registry_id"),g.get("geometry_hash")
 return None,None,None

def resolved_primary_relations(point):
 loc=primary_statement(point)
 return [(rid,point["relations"][rid]) for rid in (loc or {}).get("relation_ids",[])]

def synthesize_surface_line_midpoint(point,surface,sub,store):
 rels=resolved_primary_relations(point)
 midpoint=[(rid,r) for rid,r in rels if (r.get("constraint") or {}).get("op")=="entity_midpoint"]
 membership=[(rid,r) for rid,r in rels if (r.get("constraint") or {}).get("op")=="surface_membership"]
 if len(midpoint)!=1 or not membership:return None,"NOT_SURFACE_LINE_MIDPOINT_FAMILY"
 mrid,mr=midpoint[0];nid,regid,stage2_hash=registry_operand(point,mr)
 if not regid:return None,"MIDPOINT_OPERAND_IS_NOT_APPROVED_SURFACE_REGISTRY"
 spec=REGISTRY_BY_ID.get(regid)
 if not spec or spec.get("kind")!="surface_line":return None,"MIDPOINT_OPERAND_IS_NOT_SURFACE_LINE"
 geom=surface.get(regid)
 if not geom or geom.status!="RESOLVED":return None,"SURFACE_LINE_GEOMETRY_UNRESOLVED"
 if geom.geometry_hash()!=stage2_hash:return None,"STAGE2_REGISTRY_GEOMETRY_HASH_MISMATCH"
 curves=[c for c in geom.curves if len(c)>=2]
 if not curves:return None,"SURFACE_LINE_HAS_NO_EXECUTABLE_CURVE"

 # Only a relation family yielding an unambiguous one-curve-per-side result can synthesize bilateral coordinates.
 side_curves={}
 for c in curves:
  side=side_of_curve(c,sub)
  if side in side_curves:return None,"MULTIPLE_CURVES_ON_SAME_SIDE"
  side_curves[side]=c
 if set(side_curves)!={"left","right"}:return None,"BILATERAL_CURVE_CARDINALITY_NOT_2"

 ant=normalize(vec(sub["global_frame"]["axes"]["anterior"]))
 posterior=vmul(ant,-1.0)
 coords=[]
 for side in ("left","right"):
  candidate=arc_midpoint(side_curves[side])
  if candidate is None:return None,f"{side.upper()}_CURVE_MIDPOINT_UNRESOLVED"
  origin=vadd(candidate,vmul(ant,DIRECT_SURFACE_INWARD_OFFSET_M))
  raw_hits=[h for h in ray_hits_part(store,SKIN_PART,origin,posterior) if h.t>1e-7 and h.t<=DIRECT_SURFACE_PROJECTION_BUDGET_M]
  hits=dedupe_geometric_ray_hits(raw_hits)
  # Triangulation can produce duplicate hits at a shared edge/vertex; those are one
  # geometric surface hit. Distinct depth/position clusters remain ambiguous.
  if len(hits)!=1:return None,f"{side.upper()}_ASPECT_RAY_GEOMETRIC_HIT_CARDINALITY_{len(hits)}"
  h=hits[0]
  coords.append({
   "side":side,
   "coordinate_world_m":[float(x) for x in h.point],
   "skin_part_id":SKIN_PART,
   "triangle_index":h.triangle_index,
   "barycentric":[float(x) for x in h.barycentric],
   "candidate_world_m":[float(x) for x in candidate],
   "candidate_to_hit_m":distance(candidate,h.point),
   "projection":{
    "method":"aspect_directed_ray_cast",
    "aspect":"posterior",
    "origin_world_m":[float(x) for x in origin],
    "direction_world":[float(x) for x in posterior],
    "t_m":float(h.t),
    "budget_m":DIRECT_SURFACE_PROJECTION_BUDGET_M,
    "inward_offset_m":DIRECT_SURFACE_INWARD_OFFSET_M,
    "raw_triangle_hit_count_within_budget":len(raw_hits),
    "distinct_geometric_hit_count_within_budget":len(hits)
   },
   "source_geometry":{
    "registry_id":regid,
    "registry_geometry_hash":geom.geometry_hash(),
    "stage2_registry_geometry_hash":stage2_hash,
    "derived_relation_id":mrid,
    "derived_geometry_id":(mr.get("constraint") or {}).get("result_geometry_id"),
    "derived_geometry_hash":(mr.get("constraint") or {}).get("result_geometry_hash")
   }
  })
 return coords,None

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--stage2",required=True)
 ap.add_argument("--calibration",required=True)
 ap.add_argument("--substrate",required=True)
 ap.add_argument("--input-lock",default="artifacts/c-v3/vertical-slice-v1/stage3-input-lock.json")
 ap.add_argument("--model-dir",default="public/models")
 ap.add_argument("--out",required=True)
 args=ap.parse_args()
 lock=json.loads(Path(args.input_lock).read_text())
 if lock["status"]!="FROZEN_FOR_STAGE3":raise SystemExit("Stage3 input lock not frozen")
 if sha256_file(Path(args.stage2))!=lock["stage2"]["repaired_execution_sha256"]:raise SystemExit("approved Stage2 execution SHA mismatch")
 if sha256_file(Path(args.calibration))!=lock["registry_calibration"]["calibration_sha256"]:raise SystemExit("approved calibration SHA mismatch")
 stage2=json.loads(Path(args.stage2).read_text());caldoc=json.loads(Path(args.calibration).read_text());cal={x["calibration_id"]:x for x in caldoc["rows"]}
 sub=json.loads(Path(args.substrate).read_text());store=AtlasStore(Path(args.model_dir));surface=execute_all(store,sub)
 if [x["point_id"] for x in stage2["points"]]!=list(COHORT):raise SystemExit("Stage2 cohort/order mismatch")

 out={"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-stage3-synthesis",
  "status":"GENERATED_NOT_VALIDATED","deployable":False,"scope":"Vertical Slice v1",
  "input_identity":{"stage2_sha256":sha256_file(Path(args.stage2)),"calibration_sha256":sha256_file(Path(args.calibration)),
                    "input_lock_sha256":sha256_file(Path(args.input_lock))},
  "production_write":False,"legacy_coordinate_input":False,
  "projection_contract":{"direct_surface_family":{"method":"aspect_directed_ray_cast",
    "budget_m":DIRECT_SURFACE_PROJECTION_BUDGET_M,"inward_offset_m":DIRECT_SURFACE_INWARD_OFFSET_M}},
  "points":[]}
 for p in stage2["points"]:
  pid=p["point_id"];loc=primary_statement(p);entry={"point_id":pid,"stage2_primary_status":p["primary_location_status"],
    "stage3_status":None,"coordinates":[],"trace":{},"blocking_reason":None}
  if p["primary_location_status"]!="RESOLVED":
   entry["stage3_status"]="BLOCKED_BY_STAGE2"
   entry["blocking_reason"]="Stage2 primary location is not RESOLVED"
   entry["trace"]={"location_statement_id":loc.get("source_statement_id") if loc else None}
   out["points"].append(entry);continue

  mids=(loc or {}).get("measurement_ids",[])
  if mids:
   not_ready=[mid for mid in mids if mid not in cal or not physical_calibration_ready(cal[mid])]
   if not_ready:
    entry["stage3_status"]="UNRESOLVED"
    entry["blocking_reason"]="APPROVED_CALIBRATION_HAS_NO_EXPLICIT_PHYSICAL_CUN_SCALE"
    entry["trace"]={"location_statement_id":loc["source_statement_id"],"measurement_ids":mids,
      "non_metric_calibration_ids":not_ready,
      "rule":"Stage3 does not infer metres-per-cun from atlas joint distances."}
    out["points"].append(entry);continue

  rels=resolved_primary_relations(p)
  qualitative_direction=[rid for rid,r in rels if (r.get("constraint") or {}).get("op")=="directional_relation" and not (r.get("semantic_fields") or {}).get("bound_measurement_ids")]
  midpoint_surface=any((r.get("constraint") or {}).get("op")=="entity_midpoint" for _,r in rels)
  if midpoint_surface:
   coords,reason=synthesize_surface_line_midpoint(p,surface,sub,store)
   if coords:
    entry["stage3_status"]="GENERATED"
    entry["coordinates"]=coords
    entry["trace"]={"location_statement_id":loc["source_statement_id"],
      "primary_relation_ids":loc["relation_ids"],"primary_measurement_ids":loc["measurement_ids"],
      "synthesis_family":"surface_line_arc_midpoint_then_aspect_ray",
      "hard_constraints_all_stage2_resolved":True,
      "cardinality":{"expected":["left","right"],"actual":[x["side"] for x in coords]},
      "trace_hash":None}
    entry["trace"]["trace_hash"]=objhash({k:v for k,v in entry["trace"].items() if k!="trace_hash"}|{"coordinates":coords})
    out["points"].append(entry);continue
   if reason not in ("MIDPOINT_OPERAND_IS_NOT_APPROVED_SURFACE_REGISTRY","MIDPOINT_OPERAND_IS_NOT_SURFACE_LINE","NOT_SURFACE_LINE_MIDPOINT_FAMILY"):
    entry["stage3_status"]="UNRESOLVED";entry["blocking_reason"]=reason
    entry["trace"]={"location_statement_id":loc["source_statement_id"],"primary_relation_ids":loc["relation_ids"]}
    out["points"].append(entry);continue

  if qualitative_direction:
   entry["stage3_status"]="UNRESOLVED"
   entry["blocking_reason"]="QUALITATIVE_DIRECTION_HAS_NO_FROZEN_PHYSICAL_DISPLACEMENT_RULE"
   entry["trace"]={"location_statement_id":loc["source_statement_id"],"directional_relation_ids":qualitative_direction,
     "rule":"Stage3 refuses nearest/distance heuristics for unquantified directional language."}
   out["points"].append(entry);continue

  entry["stage3_status"]="UNRESOLVED";entry["blocking_reason"]="NO_FROZEN_STAGE3_SYNTHESIS_FAMILY"
  entry["trace"]={"location_statement_id":loc["source_statement_id"],"primary_relation_ids":loc["relation_ids"]}
  out["points"].append(entry)

 out["summary"]={
  "logical_points":len(out["points"]),
  "generated_points":sum(x["stage3_status"]=="GENERATED" for x in out["points"]),
  "generated_coordinates":sum(len(x["coordinates"]) for x in out["points"]),
  "unresolved_stage3":sum(x["stage3_status"]=="UNRESOLVED" for x in out["points"]),
  "blocked_by_stage2":sum(x["stage3_status"]=="BLOCKED_BY_STAGE2" for x in out["points"]),
  "legacy_coordinate_inputs":0
 }
 Path(args.out).parent.mkdir(parents=True,exist_ok=True)
 Path(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(out["summary"],sort_keys=True))
if __name__=="__main__":main()
