#!/usr/bin/env python3
"""Independent validator for the Stage 2 human-review projection.

It does NOT import the review builder or Stage 2 solver. It independently
reconstructs a canonical projection from the frozen Stage 2 output and B v2.1,
then verifies identity, coverage, no-new-semantics constraints, conditional
preservation, special requested audits, and mutation rejection.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, re
from pathlib import Path

COHORT=("LI4","GB23","ST10","LI18","LI17","BL17","BL23","BL25","BL40","ST4","TE6","ST9",
        "HT7","ST1","GB14","LU6","LI7","GB26","ST2","TE20")
RESOLVED=set(("LI4","GB23","ST10","LI18","LI17","BL17","BL23","BL25","BL40","ST4","TE6","ST9"))
UNRESOLVED=set(("HT7","ST1","GB14","LU6","LI7","GB26","ST2","TE20"))

def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def sha(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def fsha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def identity(rec):
 g=rec.get("geometry") or {};k=g.get("kind");o={"kind":k}
 if k=="fma_concept":o.update({"fma_id":g.get("fma_id"),"part_ids":g.get("part_ids",[])})
 elif k=="surface_registry":o.update({"registry_id":g.get("registry_id"),"geometry_hash":g.get("geometry_hash")})
 elif k=="reference_acupoint":o["reference_point_id"]=g.get("point_id")
 elif k=="entity_subfeature":o.update({"parent_landmark_id":g.get("parent_landmark_id"),"modifier":g.get("modifier")})
 if rec.get("candidates") is not None:o["candidates"]=rec.get("candidates")
 return o

def loc_statement(p):
 return next((s for s in p["statements"] if s.get("section")=="location"),None)

def edges(p,condsrc):
 e=[]
 for rid,r in p["relations"].items():
  args=(r.get("constraint") or {}).get("argument_node_ids") or r.get("argument_node_ids") or []
  for a in args:e.append({"from":a,"to":rid,"kind":"operand_to_relation"})
  sid=(r.get("constraint") or {}).get("source_statement_id")
  if sid:e.append({"from":rid,"to":sid,"kind":"relation_to_statement"})
 for mid,m in p["measurements"].items():
  c=m.get("constraint") or {};a=c.get("anchor_landmark_id");sid=c.get("source_statement_id")
  if a:e.append({"from":a,"to":mid,"kind":"anchor_to_measurement"})
  if sid:e.append({"from":mid,"to":sid,"kind":"measurement_to_statement"})
 for cid in p["conditions"]:
  sid=condsrc.get(cid,{}).get("source_statement_id")
  if sid:e.append({"from":cid,"to":sid,"kind":"condition_to_statement"})
 for s in p["statements"]:e.append({"from":s["source_statement_id"],"to":p["point_id"],"kind":"statement_to_point"})
 return e

def blocker(p,bnodes):
 loc=loc_statement(p)
 if not loc or p.get("primary_location_status")=="RESOLVED":
  return {"first_unresolved_dependency":None,"upstream_resolved_dependencies":[],"blocking_items":[],"downstream_stop_items":[]}
 up=[];blocks=[];down=[]
 for rid in loc.get("relation_ids",[]):
  r=p["relations"].get(rid)
  if not r:continue
  args=(r.get("constraint") or {}).get("argument_node_ids") or r.get("argument_node_ids") or []
  if r.get("status")=="RESOLVED":
   up.append(rid)
   for a in args:
    if p["landmarks"].get(a,{}).get("status")=="RESOLVED":up.append(a)
  else:
   got=[]
   for a in args:
    lr=p["landmarks"].get(a)
    if lr and lr.get("status")!="RESOLVED":
     b=bnodes.get(a,{})
     got.append({"node_id":a,"node_type":"landmark","status":lr.get("status"),"reason":lr.get("reason"),
                 "source_raw":b.get("source_raw"),"landmark_class":b.get("landmark_class")})
   if not got:got=[{"node_id":rid,"node_type":"relation","status":r.get("status"),"reason":r.get("reason")}]
   blocks.extend(got);down.append(rid)
 for mid in loc.get("measurement_ids",[]):
  m=p["measurements"].get(mid)
  if m and m.get("status")!="RESOLVED":
   blocks.append({"node_id":mid,"node_type":"measurement","status":m.get("status"),"reason":m.get("reason")});down.append(mid)
 return {"first_unresolved_dependency":blocks[0] if blocks else None,
         "upstream_resolved_dependencies":list(dict.fromkeys(up)),"blocking_items":blocks,"downstream_stop_items":down}

def reconstruct(p,bsource,condsrc):
 bnodes={x["node_id"]:x for x in bsource["landmark_nodes"]};loc=loc_statement(p)
 src={}
 for sid in [x["source_statement_id"] for x in p["statements"]]:
  s=next((x for x in bsource["source_statements"] if x["source_statement_id"]==sid),None)
  if s:src[sid]={"section":s.get("section"),"text":s.get("text_canonical")}
 ops=[]
 for nid,r in p["landmarks"].items():
  b=bnodes.get(nid,{})
  ops.append({"landmark_id":nid,"source_raw":b.get("source_raw"),"landmark_class":b.get("landmark_class"),
              "terminal_disposition":b.get("terminal_disposition"),"status":r.get("status"),
              "executor":r.get("executor"),"identity":identity(r),"reason":r.get("reason")})
 rel=[]
 for rid,r in p["relations"].items():
  c=r.get("constraint") or {}
  rel.append({"relation_id":rid,"status":r.get("status"),"executor":r.get("executor"),
              "operator":c.get("op"),"operand_ids":c.get("argument_node_ids") or r.get("argument_node_ids") or [],
              "source_statement_id":c.get("source_statement_id"),"branch_id":c.get("branch_id"),
              "direction":c.get("direction"),"reason":r.get("reason")})
 mea=[]
 for mid,m in p["measurements"].items():
  c=m.get("constraint") or {}
  mea.append({"measurement_id":mid,"status":m.get("status"),"executor":m.get("executor"),
    "kind":c.get("kind"),"value":c.get("value"),"unit":c.get("unit"),"source_unit":c.get("source_unit"),
    "direction":c.get("direction"),"anchor_landmark_id":c.get("anchor_landmark_id"),
    "source_statement_id":c.get("source_statement_id"),"who_pdf_page":c.get("who_pdf_page"),"reason":m.get("reason")})
 con=[]
 for cid,c in p["conditions"].items():
  bs=condsrc.get(cid,{})
  con.append({"condition_id":cid,"status":c.get("status"),"executor":c.get("executor"),
              "condition_type":c.get("condition_type"),"branch_id":c.get("branch_id"),"reason":c.get("reason"),
              "source_statement_id":bs.get("source_statement_id"),"source_span":bs.get("source_span")})
 order=list(p["landmarks"])+list(p["measurements"])+list(p["conditions"])+list(p["relations"])+[s["source_statement_id"] for s in p["statements"]]+[p["point_id"]]
 return {"point_id":p["point_id"],"final_stage2_status":p.get("primary_location_status"),
         "conditional_present":any(x["status"]=="CONDITIONAL" for x in con),
         "primary_location_source_statement_id":loc.get("source_statement_id") if loc else None,
         "source_statements":src,"operands":ops,"relations":rel,"measurements":mea,"conditions":con,
         "dependency_edges":edges(p,condsrc),"recorded_data_order":order,"explicit_runtime_order_recorded":False,
         "final_semantic_execution_result":{"primary_location_status":p.get("primary_location_status"),
           "location_statement_status":loc.get("status") if loc else None},
         "blocking":blocker(p,bnodes)}

def get_identity_ids(review_point):
 vals=set()
 for o in review_point["operands"]:
  vals.add(o["landmark_id"]);i=o["identity"]
  for k in ("fma_id","registry_id","reference_point_id","parent_landmark_id"):
   if i.get(k):vals.add(i[k])
 for r in review_point["relations"]:
  vals.add(r["relation_id"]);vals.update(r["operand_ids"])
 for m in review_point["measurements"]:
  vals.add(m["measurement_id"])
  if m.get("anchor_landmark_id"):vals.add(m["anchor_landmark_id"])
 for c in review_point["conditions"]:vals.add(c["condition_id"])
 return vals

def special_audits(stage2,graph):
 out={};pby={p["point_id"]:p for p in stage2["points"]}
 bnodes={x["node_id"]:x for x in graph["landmark_nodes"]}
 bs={x["source_statement_id"]:x for x in graph["source_statements"]}
 def loc(pid):return next(x for x in pby[pid]["statements"] if x["section"]=="location")
 def raw(pid):return [bnodes[n]["source_raw"] for n in pby[pid]["landmarks"] if n in bnodes]
 # Requested checks are observational projections of existing B/Stage2 fields.
 g=pby["GB23"];out["GB23"]={
  "lateral_thoracic_region_present":any("lateral thoracic region" in (x or "").lower() for x in raw("GB23")),
  "fourth_intercostal_space_present":any("fourth intercostal space" in (x or "").lower() for x in raw("GB23")),
  "midaxillary_line_present":any("midaxillary line" in (x or "").lower() for x in raw("GB23")),
  "one_b_cun_anterior_present":any(m.get("constraint",{}).get("value")==1.0 and m.get("constraint",{}).get("direction")=="anterior" for m in g["measurements"].values())}
 t=pby["TE6"];out["TE6"]={
  "posterior_forearm_present":any("posterior aspect" in (x or "").lower() for x in raw("TE6")),
  "interosseous_operand":next((x for x in t["landmarks"].values() if (x.get("geometry") or {}).get("registry_id")=="SR:radius_ulna_interosseous_space"),None),
  "three_b_cun_proximal_present":any(m.get("constraint",{}).get("value")==3.0 and m.get("constraint",{}).get("direction")=="proximal" for m in t["measurements"].values()),
  "deep_space_not_replaced_by_surface_membership":any(r.get("executor")=="entity_midpoint" for r in t["relations"].values())}
 s=pby["ST4"];locsid=loc("ST4")["source_statement_id"]
 out["ST4"]={
  "primary_location_resolved":s["primary_location_status"]=="RESOLVED",
  "primary_relation_statuses":[s["relations"][r]["status"] for r in loc("ST4")["relation_ids"]],
  "note_nasolabial_unresolved":[{"id":nid,"status":v["status"],"reason":v.get("reason")} for nid,v in s["landmarks"].items() if "nasolabial" in (bnodes.get(nid,{}).get("source_raw") or "").lower()],
  "note_dependencies_separate_from_primary":all((s["relations"][r].get("constraint") or {}).get("source_statement_id")==locsid for r in loc("ST4")["relation_ids"] if s["relations"][r]["status"]=="RESOLVED")}
 neck={}
 for pid in ("ST9","ST10","LI17","LI18"):
  neck[pid]=sorted((o.get("geometry") or {}).get("fma_id") or (o.get("geometry") or {}).get("registry_id") or nid for nid,o in pby[pid]["landmarks"].items() if o.get("status")=="RESOLVED")
 out["neck_point_identity_signatures"]=neck
 for pid in ("BL17","BL23","BL25"):
  q=pby[pid];out[pid]={
   "vertebral_anchor_present":any("vertebra" in (x or "").lower() for x in raw(pid)),
   "posterior_median_line_present":any("posterior median line" in (x or "").lower() for x in raw(pid)),
   "lateral_1_5_b_cun_present":any(m.get("constraint",{}).get("value")==1.5 and m.get("constraint",{}).get("direction")=="lateral" for m in q["measurements"].values())}
 for pid in ("LI4","BL40"):
  q=pby[pid];ls=loc(pid)
  out[pid]={"all_primary_relations_resolved":all(q["relations"][rid]["status"]=="RESOLVED" for rid in ls["relation_ids"]),
            "all_primary_relation_operands_resolved":all(q["landmarks"][a]["status"]=="RESOLVED" for rid in ls["relation_ids"] for a in ((q["relations"][rid].get("constraint") or {}).get("argument_node_ids") or q["relations"][rid].get("argument_node_ids") or []))}
 return out

def validate(review,stage2,graph,html_text,builder_text):
 identity_errors=[];ind_errors=[];discrepancies=[];ic=0;dc=0
 def I(ok,code,detail=None):
  nonlocal ic;ic+=1
  if not ok:identity_errors.append({"code":code,"detail":detail})
 def D(ok,code,detail=None):
  nonlocal dc;dc+=1
  if not ok:ind_errors.append({"code":code,"detail":detail})
 condsrc={x["condition_id"]:x for x in graph.get("conditions",[])}
 psrc={p["point_id"]:p for p in stage2["points"]};prev={p["point_id"]:p for p in review["points"]}
 I(set(prev)==set(COHORT),"REVIEW_20_POINT_COVERAGE",sorted(set(COHORT)-set(prev)))
 I({p for p in prev if prev[p]["final_stage2_status"]=="RESOLVED"}==RESOLVED,"RESOLVED_12_COVERAGE")
 I({p for p in prev if prev[p]["final_stage2_status"]=="UNRESOLVED"}==UNRESOLVED,"UNRESOLVED_8_COVERAGE")
 I(review.get("stage2_source_sha256")==fsha(Path(args.stage2)),"STAGE2_SOURCE_FILE_HASH_MISMATCH")
 for pid in COHORT:
  s=psrc[pid];r=prev[pid]
  I(r["source_point_record"]==s,"LOSSLESS_SOURCE_POINT_RECORD_MISMATCH",pid)
  I(r["source_point_sha256"]==sha(s),"SOURCE_POINT_HASH_MISMATCH",pid)
  sm={x["source_statement_id"] for x in graph["source_statements"] if x["point_id"]==pid}
  bp={"source_statements":[x for x in graph["source_statements"] if x["point_id"]==pid],
      "landmark_nodes":[x for x in graph["landmark_nodes"] if x["point_id"]==pid]}
  exp=reconstruct(s,bp,condsrc)
  core={k:exp[k] for k in ("point_id","final_stage2_status","conditional_present","primary_location_source_statement_id","operands","relations","measurements","conditions","dependency_edges","recorded_data_order","explicit_runtime_order_recorded","final_semantic_execution_result","blocking")}
  gotcore={k:r[k] for k in core}
  I(gotcore==core,"CANONICAL_SEMANTIC_PROJECTION_MISMATCH",pid)
  I(r["canonical_semantic_sha256"]==sha(core),"CANONICAL_SEMANTIC_HASH_MISMATCH",pid)
  # IDs and operators are exactly existing Stage2 source.
  I([x["relation_id"] for x in r["relations"]]==list(s["relations"].keys()),"RELATION_ID_SEQUENCE_MISMATCH",pid)
  I([x["operator"] for x in r["relations"]]==[(s["relations"][k].get("constraint") or {}).get("op") for k in s["relations"]],"OPERATOR_SEQUENCE_MISMATCH",pid)
  source_ids=set(s["landmarks"])|set(s["relations"])|set(s["measurements"])|set(s["conditions"])|{x["source_statement_id"] for x in s["statements"]}|{pid}
  for e in r["dependency_edges"]:
   I(e["from"] in source_ids and e["to"] in source_ids,"FORGED_DEPENDENCY_ENDPOINT",{"point":pid,"edge":e})
  if r["blocking"]["first_unresolved_dependency"]:
   I(r["blocking"]["first_unresolved_dependency"]["node_id"] in source_ids,"BLOCKER_NOT_SOURCE_GRAPH_NODE",pid)
 # renderer purity
 D("<script" not in html_text.lower(),"HTML_SCRIPT_FORBIDDEN")
 for token in ("fallback semantic","new relation","hard-coded expected operator","fma substitution","fallback landmark","inferred dependency"):
  D(token not in html_text.lower(),"HTML_SEMANTIC_LOGIC_MARKER",token)
 for token in ("REL_OP","SURFACE_RULES","atlas_lookup(","parse_acupoint_ref(","execute_vertical_slice_stage2"):
  D(token not in builder_text,"BUILDER_SECOND_EXECUTOR_MARKER",token)
 # coordinate/legacy fields
 def walk(o):
  if isinstance(o,dict):
   for k,v in o.items():
    yield k,v
    yield from walk(v)
  elif isinstance(o,list):
   for v in o:yield from walk(v)
 coord_keys={"coordinate","coordinates","xyz","world_coordinate","physical_coordinate_value"}
 coord_count=sum(1 for k,v in walk(review) if str(k).lower() in coord_keys)
 D(coord_count==0,"COORDINATE_FIELD_COUNT_NONZERO",coord_count)
 D(all(p.get("coordinate_generation_count")==0 and p.get("legacy_c_coordinate_reference_count")==0 for p in review["points"]),"COORDINATE_OR_LEGACY_INVARIANT_NONZERO")
 # Conditional identity and independent pose-preservation audit.
 for pid in COHORT:
  s=psrc[pid];r=prev[pid]
  D([(x["condition_id"],x["status"]) for x in r["conditions"]]==[(cid,c["status"]) for cid,c in s["conditions"].items()],"CONDITIONAL_STATE_LOSS",pid)
  for cid,c in s["conditions"].items():
   b=condsrc.get(cid,{})
   raw=((b.get("source_span") or {}).get("source_raw") or "").lower()
   if b.get("condition_type")=="body_position" and any(x in raw for x in ("folded","turned","against resistance","pressed against")):
    if c.get("status")!="CONDITIONAL":
     discrepancies.append({"code":"POSE_CONDITION_NOT_PRESERVED_AS_CONDITIONAL","point_id":pid,"condition_id":cid,"source_raw":raw,"stage2_status":c.get("status")})
 special=special_audits(stage2,graph)
 # Gate the specifically requested resolved composition observations without inventing replacement semantics.
 for name,val in special["GB23"].items():D(bool(val),f"GB23_{name.upper()}")
 D(special["TE6"]["posterior_forearm_present"],"TE6_POSTERIOR_FOREARM_MISSING")
 D(bool(special["TE6"]["interosseous_operand"]),"TE6_INTEROSSEOUS_OPERAND_MISSING")
 D(special["TE6"]["three_b_cun_proximal_present"],"TE6_3_BCUN_PROXIMAL_MISSING")
 D(special["TE6"]["deep_space_not_replaced_by_surface_membership"],"TE6_DEEP_SPACE_RELATION_COLLAPSED")
 D(special["ST4"]["primary_location_resolved"],"ST4_PRIMARY_NOT_RESOLVED")
 D(all(x=="RESOLVED" for x in special["ST4"]["primary_relation_statuses"]),"ST4_PRIMARY_RELATION_NOT_RESOLVED")
 D(bool(special["ST4"]["note_nasolabial_unresolved"]),"ST4_NASOLABIAL_UNRESOLVED_NOT_VISIBLE")
 D(special["ST4"]["note_dependencies_separate_from_primary"],"ST4_NOTE_PRIMARY_DEPENDENCY_MIXED")
 sigs=special["neck_point_identity_signatures"];D(len({canon(v) for v in sigs.values()})==4,"NECK_POINT_ANCHOR_SIGNATURES_NOT_DISTINCT",sigs)
 for pid in ("BL17","BL23","BL25"):
  for k,v in special[pid].items():D(bool(v),f"{pid}_{k.upper()}")
 for pid in ("LI4","BL40"):
  for k,v in special[pid].items():D(bool(v),f"{pid}_{k.upper()}")
 return ic,identity_errors,dc,ind_errors,discrepancies,special

def mutation_rejected(review,stage2,graph,html_text,builder_text,kind):
 m=copy.deepcopy(review)
 if kind=="operator":
  m["points"][0]["relations"][0]["operator"]="FORGED_OPERATOR"
 elif kind=="identity":
  changed=False
  for p in m["points"]:
   for o in p["operands"]:
    if o["identity"].get("fma_id"):
     o["identity"]["fma_id"]="FMA_FORGED";changed=True;break
    if o["identity"].get("registry_id"):
     o["identity"]["registry_id"]="SR:FORGED";changed=True;break
   if changed:break
 elif kind=="edge":
  m["points"][0]["dependency_edges"].append({"from":"LM:FORGED","to":"RL:FORGED","kind":"operand_to_relation"})
 elif kind=="status":
  m["points"][0]["final_stage2_status"]="UNRESOLVED" if m["points"][0]["final_stage2_status"]=="RESOLVED" else "RESOLVED"
 ic,ie,dc,de,disc,spec=validate(m,stage2,graph,html_text,builder_text)
 return bool(ie or de)

def main():
 global args
 ap=argparse.ArgumentParser()
 ap.add_argument("--stage2",required=True)
 ap.add_argument("--review-data",required=True)
 ap.add_argument("--review-html",required=True)
 ap.add_argument("--builder",default="scripts/cv3/build_vertical_slice_stage2_human_review.py")
 ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json")
 ap.add_argument("--out",required=True)
 args=ap.parse_args()
 stage2=json.loads(Path(args.stage2).read_text());review=json.loads(Path(args.review_data).read_text());graph=json.loads(Path(args.graph).read_text())
 html_text=Path(args.review_html).read_text();builder_text=Path(args.builder).read_text()
 ic,ie,dc,de,disc,special=validate(review,stage2,graph,html_text,builder_text)
 neg={k:mutation_rejected(review,stage2,graph,html_text,builder_text,k) for k in ("operator","identity","edge","status")}
 for k,v in neg.items():
  dc+=1
  if not v:de.append({"code":f"NEGATIVE_{k.upper()}_MUTATION_NOT_REJECTED"})
 status="PASS" if not ie and not de else "FAIL"
 review_disposition="HUMAN_REVIEW_REJECTED" if disc else "HUMAN_REVIEW_PENDING"
 out={"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-stage2-human-review-validation",
      "status":status,"review_disposition":review_disposition,
      "identity_validation":{"checks":ic,"errors":len(ie),"error_details":ie},
      "independent_validation":{"checks":dc,"errors":len(de),"error_details":de},
      "negative_tests":{"forged_operator_rejected":neg["operator"],"forged_fma_or_registry_identity_rejected":neg["identity"],
                        "forged_dependency_edge_rejected":neg["edge"],"forged_status_flip_rejected":neg["status"]},
      "coverage":{"points":len(review["points"]),"resolved":sum(p["final_stage2_status"]=="RESOLVED" for p in review["points"]),
                  "unresolved":sum(p["final_stage2_status"]=="UNRESOLVED" for p in review["points"]),
                  "conditional_points":sum(p["conditional_present"] for p in review["points"])},
      "coordinate_generation_count":0,"legacy_c_coordinate_reference_count":0,
      "semantic_discrepancies":disc,"special_requested_audits":special,
      "final_stage_state":"Stage 2 = AUTOMATED VALIDATED, HUMAN REVIEW PENDING"}
 Path(args.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"status":status,"review_disposition":review_disposition,"identity_checks":ic,"identity_errors":len(ie),
                   "independent_checks":dc,"independent_errors":len(de),"semantic_discrepancies":len(disc),"negative_tests":neg}))
 raise SystemExit(0 if status=="PASS" else 1)
if __name__=="__main__":main()
