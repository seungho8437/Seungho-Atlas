#!/usr/bin/env python3
"""Independent Stage 3 guard validator for C v3 Vertical Slice v1.

This is not Stage 4. It protects Stage 3 pilot output by independently checking
input identity, coordinate trace completeness, skin-triangle reconstruction,
cardinality, projection consistency, Stage-2 eligibility, suppressed-provenance
isolation and mutation rejection. It does not import the Stage 3 solver or the
surface-registry executor.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,math
from pathlib import Path
from spatial_core import AtlasStore,barycentric_reconstruct,ray_triangle,ray_hits_part,dot,normalize,vsub,distance

COHORT=("HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26","ST2","ST10",
        "LI18","LI17","BL17","BL23","BL25","BL40","TE20","ST4","TE6","ST9")
SKIN_PART="FJ2810"

def sha256_file(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def primary_statement(p):return next((x for x in p["statements"] if x.get("section")=="location"),None)

def dedupe_geometric_hits(hits,tol_t=1.5e-3,tol_point=1.5e-3):
 groups=[]
 for h in hits:
  for g in groups:
   if abs(h.t-g[0].t)<=tol_t and distance(h.point,g[0].point)<=tol_point:
    g.append(h);break
  else:groups.append([h])
 return [min(g,key=lambda x:(x.t,x.triangle_index)) for g in groups]

def suppressed_metrics(stage2):
 suppressed=set()
 for p in stage2["points"]:
  for nid,r in p["landmarks"].items():
   if r.get("semantic_suppressed") is True:suppressed.add(nid)
 exe=0;resolved_path=0;influence=0
 for p in stage2["points"]:
  for r in p["relations"].values():
   ids=(r.get("constraint") or {}).get("executable_argument_node_ids") or r.get("executable_argument_node_ids") or []
   hit=[x for x in ids if x in suppressed]
   exe+=len(hit)
   if r.get("status")=="RESOLVED" and hit:resolved_path+=1
  # Point aggregation is statement/relation/measurement based. A suppressed node
  # can influence it only if it enters an executable relation dependency.
  if any(
    any(x in suppressed for x in ((r.get("constraint") or {}).get("executable_argument_node_ids") or r.get("executable_argument_node_ids") or []))
    for r in p["relations"].values()
  ):influence+=1
 return {
  "suppressed_executable_operand_count":exe,
  "suppressed_status_aggregation_influence_count":influence,
  "suppressed_only_resolved_path_count":resolved_path
 }

def validate(output,stage2,sub,store,lock):
 errors=[];checks=0
 def ck(ok,code,detail=None):
  nonlocal checks;checks+=1
  if not ok:errors.append({"code":code,"detail":detail})
 p2={x["point_id"]:x for x in stage2["points"]};p3={x["point_id"]:x for x in output["points"]}
 ck(tuple(p3)==COHORT,"COVERAGE_OR_ORDER_MISMATCH",list(p3))
 ck(output.get("deployable") is False,"DEPLOYABLE_MUST_BE_FALSE")
 ck(output.get("production_write") is False,"PRODUCTION_WRITE_MUST_BE_FALSE")
 ck(output.get("legacy_coordinate_input") is False,"LEGACY_INPUT_MUST_BE_FALSE")
 ck(output.get("input_identity",{}).get("stage2_sha256")==lock["stage2"]["repaired_execution_sha256"],"STAGE2_LOCK_IDENTITY_MISMATCH")
 ck(output.get("input_identity",{}).get("calibration_sha256")==lock["registry_calibration"]["calibration_sha256"],"CALIBRATION_LOCK_IDENTITY_MISMATCH")
 metrics=suppressed_metrics(stage2)
 for k,v in metrics.items():ck(v==0,k.upper(),v)

 gf=sub["global_frame"];ant=normalize(tuple(gf["axes"]["anterior"]));left=normalize(tuple(gf["axes"]["left"]));origin=tuple(gf["origin"])
 vv=store.vertices(SKIN_PART);ii=store.indices(SKIN_PART)
 generated=0
 for pid in COHORT:
  a=p2[pid];b=p3[pid];loc=primary_statement(a)
  ck(b["stage2_primary_status"]==a["primary_location_status"],"STAGE2_STATUS_COPY_MISMATCH",pid)
  if a["primary_location_status"]!="RESOLVED":
   ck(not b["coordinates"],"COORDINATE_FROM_STAGE2_UNRESOLVED",pid)
   ck(b["stage3_status"]=="BLOCKED_BY_STAGE2","STAGE2_UNRESOLVED_NOT_BLOCKED",pid)
  if b["coordinates"]:
   generated+=1
   ck(a["primary_location_status"]=="RESOLVED","GENERATED_WITHOUT_STAGE2_RESOLVED",pid)
   mids=(loc or {}).get("measurement_ids",[])
   ck(not mids or bool(b.get("trace",{}).get("physical_metric_evidence")),"GENERATED_QUANTITATIVE_POINT_WITHOUT_INDEPENDENT_METRIC_EVIDENCE",{"point":pid,"measurements":mids})
   rels=[a["relations"][rid] for rid in (loc or {}).get("relation_ids",[])]
   qual=[r for r in rels if (r.get("constraint") or {}).get("op")=="directional_relation" and not (r.get("semantic_fields") or {}).get("bound_measurement_ids")]
   ck(not qual or bool(b.get("trace",{}).get("physical_displacement_rule_evidence")),"GENERATED_QUALITATIVE_DIRECTION_WITHOUT_DISPLACEMENT_EVIDENCE",pid)
   # Current safe generated family must be source-supported surface-line midpoint.
   ck(b.get("trace",{}).get("synthesis_family")=="surface_line_arc_midpoint_then_aspect_ray","UNRECOGNIZED_STAGE3_GENERATED_FAMILY",pid)
   midpoint=[r for r in rels if (r.get("constraint") or {}).get("op")=="entity_midpoint"]
   surface=[r for r in rels if (r.get("constraint") or {}).get("op")=="surface_membership"]
   ck(len(midpoint)==1 and bool(surface),"GENERATED_FAMILY_SOURCE_STRUCTURE_MISMATCH",pid)
   sides=[c["side"] for c in b["coordinates"]]
   ck(sorted(sides)==["left","right"],"BILATERAL_CARDINALITY_OR_SIDE_MISMATCH",{"point":pid,"sides":sides})
   ck(len(set(sides))==len(sides),"DUPLICATE_SIDE",pid)
   for c in b["coordinates"]:
    req=("coordinate_world_m","skin_part_id","triangle_index","barycentric","candidate_world_m","projection","source_geometry")
    ck(all(k in c for k in req),"COORDINATE_TRACE_INCOMPLETE",{"point":pid,"side":c.get("side")})
    ck(c.get("skin_part_id")==SKIN_PART,"WRONG_SKIN_PART",pid)
    ti=c["triangle_index"];ck(isinstance(ti,int) and 0<=3*ti+2<len(ii),"TRIANGLE_INDEX_INVALID",{"point":pid,"ti":ti})
    if not (isinstance(ti,int) and 0<=3*ti+2<len(ii)):continue
    ids=ii[3*ti:3*ti+3];tri=(vv[ids[0]],vv[ids[1]],vv[ids[2]])
    w=c["barycentric"];ck(len(w)==3 and abs(sum(w)-1.0)<=1e-7 and min(w)>=-1e-8 and max(w)<=1+1e-8,"BARYCENTRIC_INVALID",{"point":pid,"side":c["side"],"w":w})
    q=barycentric_reconstruct(*tri,w)
    xyz=tuple(c["coordinate_world_m"])
    ck(distance(q,xyz)<=1e-7,"COORDINATE_NOT_TRIANGLE_RECONSTRUCTION",{"point":pid,"side":c["side"],"residual":distance(q,xyz)})
    proj=c["projection"]
    ck(proj.get("method")=="aspect_directed_ray_cast","PROJECTION_NOT_ASPECT_RAY",pid)
    d=normalize(tuple(proj["direction_world"]))
    ck(dot(d,tuple(-x for x in ant))>=0.999,"POSTERIOR_DIRECTION_MISMATCH",{"point":pid,"side":c["side"],"dot":dot(d,tuple(-x for x in ant))})
    t=float(proj["t_m"]);budget=float(proj["budget_m"])
    ck(t>0 and t<=budget,"PROJECTION_OVER_DECLARED_BUDGET",{"point":pid,"side":c["side"],"t":t,"budget":budget})
    ck(t<=0.05,"PROJECTION_EXCEEDS_INDEPENDENT_LOCALITY_BOUND",{"point":pid,"side":c["side"],"t":t})
    rr=ray_triangle(tuple(proj["origin_world_m"]),d,*tri)
    ck(rr is not None,"DECLARED_RAY_DOES_NOT_HIT_DECLARED_TRIANGLE",{"point":pid,"side":c["side"]})
    all_hits=[h for h in ray_hits_part(store,SKIN_PART,tuple(proj["origin_world_m"]),d) if h.t>1e-7 and h.t<=budget]
    unique_hits=dedupe_geometric_hits(all_hits)
    ck(len(unique_hits)==1,"DISTINCT_RAY_SURFACE_HIT_CARDINALITY_NOT_ONE",{"point":pid,"side":c["side"],"raw":len(all_hits),"distinct":len(unique_hits)})
    if rr is not None:
     rt,rw=rr
     ck(abs(rt-t)<=1e-7,"RAY_T_MISMATCH",{"point":pid,"side":c["side"],"declared":t,"recomputed":rt})
     ck(max(abs(rw[i]-w[i]) for i in range(3))<=1e-6,"RAY_BARYCENTRIC_MISMATCH",{"point":pid,"side":c["side"]})
    # side is independently checked from global left axis.
    px=dot(vsub(xyz,origin),left)
    ck((c["side"]=="left" and px>0) or (c["side"]=="right" and px<0),"SIDE_GEOMETRY_MISMATCH",{"point":pid,"side":c["side"],"left_coord":px})
    ck(c["source_geometry"].get("registry_geometry_hash")==c["source_geometry"].get("stage2_registry_geometry_hash"),"REGISTRY_HASH_IDENTITY_MISMATCH",pid)
   tr=b.get("trace",{})
   ck(bool(tr.get("trace_hash")),"TRACE_HASH_MISSING",pid)
   ck(tr.get("hard_constraints_all_stage2_resolved") is True,"HARD_CONSTRAINT_FLAG_MISSING",pid)
  else:
   ck(b["stage3_status"] in ("UNRESOLVED","BLOCKED_BY_STAGE2"),"EMPTY_COORDINATE_WITH_INVALID_STATUS",pid)

 ck(output.get("summary",{}).get("generated_points")==generated,"SUMMARY_GENERATED_POINT_COUNT_MISMATCH")
 ck(output.get("summary",{}).get("generated_coordinates")==sum(len(x["coordinates"]) for x in p3.values()),"SUMMARY_COORDINATE_COUNT_MISMATCH")
 return checks,errors,metrics

def negative_tests(output,stage2,sub,store,lock):
 tests={}
 def rejected(o,s=stage2):
  _,e,_=validate(o,s,sub,store,lock);return bool(e)
 # 1. coordinate tamper
 m=copy.deepcopy(output)
 target=next((p for p in m["points"] if p["coordinates"]),None)
 if target:
  target["coordinates"][0]["coordinate_world_m"][0]+=0.01
  tests["forged_coordinate_rejected"]=rejected(m)
  m=copy.deepcopy(output);t=next(p for p in m["points"] if p["coordinates"]);t["coordinates"].append(copy.deepcopy(t["coordinates"][0]))
  tests["duplicate_side_rejected"]=rejected(m)
  m=copy.deepcopy(output);t=next(p for p in m["points"] if p["coordinates"]);t["coordinates"][0]["projection"]["t_m"]=t["coordinates"][0]["projection"]["budget_m"]+0.01
  tests["over_budget_projection_rejected"]=rejected(m)
  m=copy.deepcopy(output);t=next(p for p in m["points"] if p["coordinates"]);t["trace"].pop("trace_hash",None)
  tests["missing_trace_rejected"]=rejected(m)
 else:
  tests.update({"forged_coordinate_rejected":"SKIPPED_NO_GENERATED_COORDINATE",
                "duplicate_side_rejected":"SKIPPED_NO_GENERATED_COORDINATE",
                "over_budget_projection_rejected":"SKIPPED_NO_GENERATED_COORDINATE",
                "missing_trace_rejected":"SKIPPED_NO_GENERATED_COORDINATE"})
 # 2. coordinate injected into a Stage2-unresolved point
 m=copy.deepcopy(output);dst=next((p for p in m["points"] if p["stage2_primary_status"]!="RESOLVED"),None)
 if dst:
  vv=store.vertices(SKIN_PART);ii=store.indices(SKIN_PART);ids=ii[:3]
  xyz=[sum(vv[i][k] for i in ids)/3 for k in range(3)]
  dst["coordinates"]=[{"side":"left","coordinate_world_m":xyz,"skin_part_id":SKIN_PART,"triangle_index":0,
    "barycentric":[1/3,1/3,1/3],"candidate_world_m":xyz,
    "projection":{"method":"aspect_directed_ray_cast","origin_world_m":xyz,"direction_world":[0,0,-1],"t_m":0.001,"budget_m":0.01},
    "source_geometry":{"registry_geometry_hash":"FORGED","stage2_registry_geometry_hash":"FORGED"}}]
  dst["stage3_status"]="GENERATED";dst["trace"]={"synthesis_family":"surface_line_arc_midpoint_then_aspect_ray","trace_hash":"FORGED","hard_constraints_all_stage2_resolved":True}
  tests["stage2_unresolved_coordinate_injection_rejected"]=rejected(m)
 else:tests["stage2_unresolved_coordinate_injection_rejected"]="SKIPPED_NO_STAGE2_UNRESOLVED_POINT"
 # 3. suppressed Stage2 operand injection
 s=copy.deepcopy(stage2);done=False
 for p in s["points"]:
  suppressed=[nid for nid,r in p["landmarks"].items() if r.get("semantic_suppressed") is True]
  if not suppressed:continue
  rel=next(iter(p["relations"].values()),None)
  if rel is None:continue
  con=rel.setdefault("constraint",{});con.setdefault("executable_argument_node_ids",[]).append(suppressed[0]);rel["status"]="RESOLVED";done=True;break
 tests["suppressed_operand_injection_rejected"]=done and rejected(copy.deepcopy(output),s)
 return tests

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--output",required=True);ap.add_argument("--stage2",required=True);ap.add_argument("--substrate",required=True)
 ap.add_argument("--input-lock",default="artifacts/c-v3/vertical-slice-v1/stage3-input-lock.json")
 ap.add_argument("--model-dir",default="public/models");ap.add_argument("--out",required=True)
 args=ap.parse_args()
 output=json.loads(Path(args.output).read_text());stage2=json.loads(Path(args.stage2).read_text());sub=json.loads(Path(args.substrate).read_text());lock=json.loads(Path(args.input_lock).read_text())
 store=AtlasStore(Path(args.model_dir))
 checks,errors,metrics=validate(output,stage2,sub,store,lock)
 neg=negative_tests(output,stage2,sub,store,lock)
 for k,v in neg.items():
  checks+=1
  if v is False:errors.append({"code":"NEGATIVE_TEST_NOT_REJECTED","detail":k})
 status="PASS" if not errors else "FAIL"
 report={"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-stage3-validation","status":status,
  "stage4":False,"checks":checks,"errors":len(errors),"error_details":errors,"negative_tests":neg,
  "suppressed_provenance_watchpoint_metrics":metrics,
  "coordinate_generation_count":output.get("summary",{}).get("generated_coordinates",0),
  "legacy_c_coordinate_reference_count":0,
  "result_disposition":"AUTOMATED_VALIDATED_HUMAN_AUDIT_PENDING" if status=="PASS" else "REJECTED",
  "note":"This protects Stage 3 pilot output only; it is not Stage 4 global validation."}
 Path(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"status":status,"checks":checks,"errors":len(errors),"negative_tests":neg,"watchpoint":metrics}))
 raise SystemExit(0 if status=="PASS" else 1)
if __name__=="__main__":main()
