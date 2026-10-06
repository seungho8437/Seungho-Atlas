#!/usr/bin/env python3
"""Independent validator for Vertical Slice v1 Stage 2 semantic execution.

Deliberately does not import:
- execute_vertical_slice_stage2.py
- slice_surface_registry.py
- stage2_semantic.py
- solver calibration/constants

It independently rereads B v2.1 + BodyParts3D and validates coverage,
FMA realizability, relation-family contracts, condition handling, and the
absence of physical-coordinate/legacy leakage.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,re
from pathlib import Path
from collections import Counter

B_SHA="8126e20938a478a2d214f4a8487cabeebc8f3115f7a81ad30e46b594958fb2c1"
COHORT=("HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26","ST2","ST10","LI18","LI17","BL17","BL23","BL25","BL40","TE20","ST4","TE6","ST9")
REL_OP={
 "surface-landmark":"surface_membership",
 "relative-to":"directional_relation",
 "reference-acupoint":"reference_dependency",
 "same-level":"same_level_plane",
 "between":"between_constraint",
 "midpoint-of-entity":"entity_midpoint",
 "on-line":"line_membership",
 "center-of":"entity_center",
 "midpoint-between":"midpoint_between",
 "overlies":"overlies_projection",
}
APPROVED_REGISTRY_IDS={
 "SR:dorsum_hand","SR:anteromedial_wrist","SR:palmar_wrist_crease","SR:dorsal_wrist_crease",
 "SR:anterolateral_forearm","SR:posterolateral_forearm","SR:posterior_forearm","SR:face_region",
 "SR:head_region","SR:nasolabial_sulcus","SR:lateral_thorax","SR:midaxillary_line",
 "SR:fourth_intercostal_space","SR:lateral_abdomen","SR:anterior_neck","SR:posterior_median_line",
 "SR:upper_back","SR:lumbar_region","SR:posterior_knee","SR:popliteal_crease",
 "SR:radius_ulna_interosseous_space"
}
INTENTIONAL_UNRESOLVED={"SR:nasolabial_sulcus"}

def sha256(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def norm(s):return re.sub(r"[^a-z0-9]+"," ",(s or "").lower()).strip()

def validate(out,g,atlas,approval):
 errors=[];checks=0
 def ck(ok,code,detail=None):
  nonlocal checks;checks+=1
  if not ok:errors.append({"code":code,"detail":detail})
 ck(out.get("status")=="GENERATED_NOT_VALIDATED","PREMATURE_OR_BAD_STATUS",out.get("status"))
 ck(out.get("scope",{}).get("physical_coordinates_generated") is False,"PHYSICAL_COORDINATE_STAGE2_FORBIDDEN")
 ck(out.get("scope",{}).get("legacy_coordinate_input") is False,"LEGACY_COORDINATE_INPUT_FORBIDDEN")
 ck(approval.get("status")=="APPROVED","HUMAN_APPROVAL_MISSING")
 points=out.get("points",[])
 ck([x.get("point_id") for x in points]==list(COHORT),"COHORT_ORDER_OR_MEMBERSHIP_MISMATCH")
 pout={x["point_id"]:x for x in points}
 concepts={x["id"]:x for x in atlas["concepts"]}
 allpts={x["point_id"] for x in g["points"]}
 bnodes={x["node_id"]:x for x in g["landmark_nodes"]}
 for pid in COHORT:
  p=pout.get(pid)
  if not p:continue
  sm={x["source_statement_id"] for x in g["source_statements"] if x["point_id"]==pid}
  lms=[x for x in g["landmark_nodes"] if x["point_id"]==pid]
  rels=[x for x in g["relation_instances"] if x["subject_node_id"]==f"P:{pid}"]
  pms=[x for x in g.get("proportional_measurements",[]) if x["source_statement_id"] in sm]
  conds=[x for x in g.get("conditions",[]) if x["source_statement_id"] in sm]
  ck(set(p["landmarks"])=={x["node_id"] for x in lms},"LANDMARK_COVERAGE_MISMATCH",pid)
  ck(set(p["relations"])=={x["relation_id"] for x in rels},"RELATION_COVERAGE_MISMATCH",pid)
  ck(set(p["measurements"])=={x["measurement_id"] for x in pms},"MEASUREMENT_COVERAGE_MISMATCH",pid)
  ck(set(p["conditions"])=={x["condition_id"] for x in conds},"CONDITION_COVERAGE_MISMATCH",pid)
  for n in lms:
   got=p["landmarks"][n["node_id"]]
   if n.get("terminal_disposition")=="resolved_fma":
    c=concepts.get(n.get("fma_id"))
    ck(c is not None and bool(c.get("elements")),"B_RESOLVED_FMA_NOT_MESH_REALIZABLE",n["node_id"])
    if c and c.get("elements"):
     ck(got["status"]=="RESOLVED","RESOLVED_FMA_NOT_RESOLVED",n["node_id"])
     geom=got.get("geometry") or {}
     ck(geom.get("fma_id")==n.get("fma_id"),"FMA_ID_MISMATCH",n["node_id"])
     ck(set(geom.get("part_ids",[]))==set(c.get("elements",[])),"FMA_PART_SET_MISMATCH",n["node_id"])
   if n.get("terminal_disposition")=="cross_reference":
    rid=n.get("cross_reference_point_id")
    ck(rid in allpts,"B_REFERENCE_TARGET_MISSING",n["node_id"])
    ck(got["status"]=="RESOLVED","REFERENCE_DEPENDENCY_NOT_RESOLVED",n["node_id"])
    ck((got.get("geometry") or {}).get("point_id")==rid,"REFERENCE_TARGET_MISMATCH",n["node_id"])
   if got.get("executor")=="approved_surface_registry":
    geom=got.get("geometry") or {}
    rid=geom.get("registry_id")
    # Unresolved registry entries may have no geometry payload; infer only from reason.
    if got["status"]=="RESOLVED":
     ck(rid in APPROVED_REGISTRY_IDS,"UNAPPROVED_SURFACE_REGISTRY_ID",{"node":n["node_id"],"rid":rid})
     ck(rid not in INTENTIONAL_UNRESOLVED,"INTENTIONAL_UNRESOLVED_WAS_RESOLVED",rid)
     ck(bool(geom.get("geometry_hash")),"SURFACE_GEOMETRY_HASH_MISSING",n["node_id"])
  for r in rels:
   got=p["relations"][r["relation_id"]];expected=REL_OP.get(r["relation_type"])
   ck(expected is not None,"VALIDATOR_UNKNOWN_RELATION_TYPE",r["relation_type"])
   ck(got.get("executor")==expected,"RELATION_EXECUTOR_MISMATCH",{"id":r["relation_id"],"got":got.get("executor"),"expected":expected})
   args=[p["landmarks"].get(x) for x in r.get("argument_node_ids",[])]
   if got["status"]=="RESOLVED":
    ck(all(x and x.get("status")=="RESOLVED" for x in args),"RELATION_RESOLVED_WITH_NONRESOLVED_ARGUMENT",r["relation_id"])
    con=got.get("constraint") or {}
    ck(con.get("op")==expected,"RELATION_OP_MISMATCH",r["relation_id"])
    ck(con.get("source_statement_id")==r["source_statement_id"],"RELATION_SOURCE_MISMATCH",r["relation_id"])
    if r["relation_type"]=="relative-to":
     ck(con.get("direction") in {"radial","ulnar","anterior","posterior","superior","inferior","medial","lateral","proximal","distal"},"RELATIVE_DIRECTION_INVALID",r["relation_id"])
  for m in pms:
   got=p["measurements"][m["measurement_id"]]
   ck(got["status"]=="RESOLVED","APPROVED_MEASUREMENT_NOT_RESOLVED",m["measurement_id"])
   con=got.get("constraint") or {}
   ck(con.get("kind")=="proportional_offset","MEASUREMENT_KIND_MISMATCH",m["measurement_id"])
   ck(con.get("value")==m.get("value"),"MEASUREMENT_VALUE_MISMATCH",m["measurement_id"])
   expected_unit="F-cun" if str(m.get("unit")).lower()=="f-cun" else m.get("unit")
   ck(con.get("unit")==expected_unit,"MEASUREMENT_UNIT_MISMATCH",m["measurement_id"])
   ck(con.get("direction")==m.get("direction"),"MEASUREMENT_DIRECTION_MISMATCH",m["measurement_id"])
   ck(isinstance(con.get("who_pdf_page"),int) and con["who_pdf_page"]>0,"WHO_CITATION_PAGE_MISSING",m["measurement_id"])
  for c in conds:
   got=p["conditions"][c["condition_id"]];raw=norm((c.get("source_span") or {}).get("source_raw"))
   if c["condition_type"]=="body_position" and any(k in raw for k in ("head is turned","against resistance","auricle is folded","folded forward")):
    ck(got["status"]=="CONDITIONAL","POSE_INCOMPATIBLE_BRANCH_NOT_CONDITIONAL",c["condition_id"])
   if c["condition_type"] in ("alternative","palpation_dependent"):
    ck(got["status"]=="CONDITIONAL","ALTERNATIVE_OR_PALPATION_BRANCH_NOT_CONDITIONAL",c["condition_id"])
 # Stage 2 must not contain a physical coordinate product or legacy input references.
 raw=json.dumps(out).lower()
 for forbidden in ("acupoint-coordinates.json","legacy candidate","legacy_coordinate","physical_coordinate"):
  ck(forbidden not in raw,"FORBIDDEN_STAGE2_OR_LEGACY_TOKEN",forbidden)
 return checks,errors

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("execution")
 ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json")
 ap.add_argument("--model-dir",default="public/models")
 ap.add_argument("--approval",default="artifacts/c-v3/vertical-slice-v1/registry-calibration-approval.json")
 ap.add_argument("--report",default=".tmp/c-v3-slice/stage2-validation.json")
 args=ap.parse_args()
 if sha256(Path(args.graph))!=B_SHA:raise SystemExit("B v2.1 SHA mismatch")
 out=json.loads(Path(args.execution).read_text());g=json.loads(Path(args.graph).read_text());atlas=json.loads((Path(args.model_dir)/"atlas.json").read_text());approval=json.loads(Path(args.approval).read_text())
 checks,errors=validate(out,g,atlas,approval)
 # Negative test 1: forged relation op must be rejected.
 mutated=copy.deepcopy(out);done=False
 for p in mutated["points"]:
  for rid,x in p["relations"].items():
   if x.get("status")=="RESOLVED":
    x["executor"]="forged_operator";done=True;break
  if done:break
 ck2,err2=validate(mutated,g,atlas,approval)
 neg1=bool(err2)
 # Negative test 2: FMA identity corruption must be rejected.
 mutated2=copy.deepcopy(out);done=False
 for p in mutated2["points"]:
  for nid,x in p["landmarks"].items():
   if x.get("executor")=="fma_mesh" and x.get("status")=="RESOLVED":
    x["geometry"]["fma_id"]="FMA_FORGED";done=True;break
  if done:break
 ck3,err3=validate(mutated2,g,atlas,approval);neg2=bool(err3)
 errors2=list(errors)
 if not neg1:errors2.append({"code":"NEGATIVE_FORGED_RELATION_NOT_REJECTED"})
 if not neg2:errors2.append({"code":"NEGATIVE_FORGED_FMA_NOT_REJECTED"})
 status="PASS" if not errors2 else "FAIL"
 rep={"schema_version":"1.0.0","stage":"Vertical Slice Stage 2","status":status,"checks":checks+2,
      "errors":errors2,"negative_tests":{"forged_relation_operator_rejected":neg1,"forged_fma_identity_rejected":neg2},
      "independence":"validator imports neither solver, registry executor, nor calibration table"}
 q=Path(args.report);q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(rep,indent=2)+"\n")
 print(json.dumps({"status":status,"checks":checks+2,"errors":len(errors2),"negative_tests":rep["negative_tests"]}));raise SystemExit(0 if status=="PASS" else 1)
if __name__=="__main__":main()
