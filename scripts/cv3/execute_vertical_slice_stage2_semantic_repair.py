#!/usr/bin/env python3
"""Stage 2 semantic-repair executor for Vertical Slice v1.

Repairs the human-audit defect families without generating coordinates:
- parent-only composite/subfeature collapse
- child-subfeature dependency omission
- distinct-subfeature identity collapse
- incompatible condition promotion

The approved surface registry/calibration remain unchanged.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,re,subprocess
from pathlib import Path
from spatial_core import AtlasStore
from slice_surface_registry import execute_all

B_SHA="8126e20938a478a2d214f4a8487cabeebc8f3115f7a81ad30e46b594958fb2c1"
COHORT=("HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26","ST2","ST10","LI18","LI17","BL17","BL23","BL25","BL40","TE20","ST4","TE6","ST9")
EXPECTED_GEOMETRY_BLOB="efb078aaecc08af1a4491cb40e9c84fd4e4443fa"
EXPECTED_REVIEW_BUILDER_BLOB="1c3a05ceb4b6f84ee670b6d6cf2c50c6f8349b5a"
STOP={"the","of","and","a","an","to","in","on","at","with","bone","muscle","border","aspect","region","space","line","centre","center","midpoint"}
SUBFEATURES=("superior border","inferior border","anterior border","posterior border","free end","midpoint","centre","center","margin","edge","angle","apex","border","end")
SYMBOLIC_CONSTRUCTIBLE={"midpoint":"entity_midpoint","centre":"entity_center","center":"entity_center"}
REL_OP={"surface-landmark":"surface_membership","relative-to":"directional_relation","reference-acupoint":"reference_dependency",
 "same-level":"same_level_plane","between":"between_constraint","midpoint-of-entity":"entity_midpoint","on-line":"line_membership",
 "center-of":"entity_center","midpoint-between":"midpoint_between","overlies":"overlies_projection"}

def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"))
def objhash(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def sha256(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()
def git_blob(p):return subprocess.check_output(["git","hash-object",p],text=True).strip()
def norm(s):return re.sub(r"[^a-z0-9]+"," ",(s or "").lower().replace("proxi-mal","proximal").replace("pos-terior","posterior")).strip()
def subfeature_type(raw):
 n=norm(raw)
 return next((x for x in SUBFEATURES if x in n),None)

def span_info(node_id):
 m=re.search(r":(\d+)-(\d+)(?::[^:]+)?$",node_id or "")
 return (node_id[:m.start()],int(m.group(1)),int(m.group(2))) if m else None

def contained_bound_children(arg_id,bindings):
 a=span_info(arg_id)
 if not a:return []
 out=[]
 for b in bindings:
  cs=span_info(b["child_landmark_id"]);ps=span_info(b["parent_landmark_id"])
  if not cs or not ps or cs[0]!=a[0] or ps[0]!=a[0]:continue
  if a[1]<=cs[1] and cs[2]<=a[2] and a[1]<=ps[1] and ps[2]<=a[2]:
   out.append(b["child_landmark_id"])
 return out
def content_tokens(s):return [x for x in norm(s).split() if len(x)>2 and x not in STOP]
def parse_ref(raw):
 m=re.search(r"\b(?:LU|LI|ST|SP|HT|SI|BL|KI|PC|TE|GB|LR|CV|GV)\s*\d+\b",(raw or "").upper())
 return re.sub(r"\s+","",m.group(0)) if m else None
def relation_direction(r):
 cue=norm((r.get("cue_span") or {}).get("source_raw"))
 return next((x for x in ("radial","ulnar","anterior","posterior","superior","inferior","medial","lateral","proximal","distal") if x in cue),None)
def status_rank(s):return {"INVALID":5,"UNRESOLVED":4,"MULTIPLE":3,"CONDITIONAL":2,"RESOLVED":1}.get(s,9)

def atlas_lookup(store,raw):
 toks=content_tokens(raw)
 if not toks:return {"status":"UNRESOLVED","reason":"no discriminating atlas-name tokens"}
 exact=[];partial=[]
 for p in store.atlas["parts"]:
  n=norm(p["name"])
  if all(t in n.split() for t in toks):exact.append((p["id"],p["name"]))
  elif all(t in n for t in toks):partial.append((p["id"],p["name"]))
 cand=exact or partial
 if len(cand)==1:return {"status":"RESOLVED","geometry":{"kind":"atlas_part","part_id":cand[0][0],"name":cand[0][1]}}
 if len(cand)>1:return {"status":"MULTIPLE","reason":"multiple atlas-name candidates","candidates":[{"part_id":a,"name":b} for a,b in cand[:30]]}
 cc=[]
 for x in store.atlas["concepts"]:
  n=norm(x["name"])
  if all(t in n for t in toks):cc.append(x)
 if len(cc)==1 and cc[0].get("elements"):
  return {"status":"RESOLVED","geometry":{"kind":"atlas_concept","concept_id":cc[0]["id"],"name":cc[0]["name"],"part_ids":cc[0]["elements"]}}
 if len(cc)>1:return {"status":"MULTIPLE","reason":"multiple atlas-concept candidates","candidates":[{"concept_id":x["id"],"name":x["name"]} for x in cc[:30]]}
 return {"status":"UNRESOLVED","reason":"no unique atlas name match"}

def surface_registry_id(node,stmt_text):
 raw=norm(node.get("source_raw"));full=norm(stmt_text)
 direct=(("palmar wrist crease","SR:palmar_wrist_crease"),("dorsal wrist crease","SR:dorsal_wrist_crease"),
 ("dorsum of the hand","SR:dorsum_hand"),("popliteal crease","SR:popliteal_crease"),("posterior median line","SR:posterior_median_line"),
 ("midaxillary line","SR:midaxillary_line"),("fourth intercostal space","SR:fourth_intercostal_space"),
 ("lateral thoracic region","SR:lateral_thorax"),("lateral abdomen","SR:lateral_abdomen"),("upper back region","SR:upper_back"),
 ("lumbar region","SR:lumbar_region"),("nasolabial sulcus","SR:nasolabial_sulcus"),
 ("interosseous space between the radius and the ulna","SR:radius_ulna_interosseous_space"))
 for phrase,rid in direct:
  if phrase in raw:return rid
 if raw=="face":return "SR:face_region"
 if raw=="head":return "SR:head_region"
 if "anteromedial aspect" in raw and "wrist" in full:return "SR:anteromedial_wrist"
 if "anterolateral aspect" in raw and "forearm" in full:return "SR:anterolateral_forearm"
 if "posterolateral aspect" in raw and "forearm" in full:return "SR:posterolateral_forearm"
 if "posterior aspect" in raw and "forearm" in full:return "SR:posterior_forearm"
 if "posterior aspect" in raw and "knee" in full:return "SR:posterior_knee"
 if ("anterior region" in raw or "anterior aspect" in raw) and "neck" in full:return "SR:anterior_neck"
 return None

def geometry_identity(rec):
 g=rec.get("geometry") or {}
 if g.get("geometry_hash"):return "hash:"+g["geometry_hash"]
 if g.get("constructed_id"):return "constructed:"+g["constructed_id"]
 if g.get("fma_id"):return "fma:"+g["fma_id"]+":"+",".join(sorted(g.get("part_ids",[])))
 if g.get("concept_id"):return "concept:"+g["concept_id"]+":"+",".join(sorted(g.get("part_ids",[])))
 if g.get("part_id"):return "part:"+g["part_id"]
 if g.get("registry_id"):return "registry:"+g["registry_id"]+":"+str(g.get("geometry_hash"))
 if g.get("point_id"):return "point:"+g["point_id"]
 return None

def relation_semantic_fields(r,op,semantic,bound_measurements,statement_measurements):
 fields={"op":op,"relation_type":r["relation_type"],"source_statement_id":r["source_statement_id"],
         "branch_id":r.get("branch_id"),"semantic_argument_node_ids":semantic,
         "bound_measurement_ids":[m["measurement_id"] for m in bound_measurements],
         "quantitative_constraints":[m["constraint"] for m in bound_measurements],
         "statement_measurement_ids":[m["measurement_id"] for m in statement_measurements]}
 if r["relation_type"]=="relative-to":
  fields["direction"]=relation_direction(r)
 return fields

def relation_measurements(r,pms,mout):
 same=[{"measurement_id":m["measurement_id"],"constraint":(mout.get(m["measurement_id"]) or {}).get("constraint")} for m in pms if m["source_statement_id"]==r["source_statement_id"] and (mout.get(m["measurement_id"]) or {}).get("constraint")]
 if r["relation_type"]!="relative-to":return [],same
 d=relation_direction(r)
 bound=[x for x in same if (x["constraint"] or {}).get("direction")==d]
 return bound,same

def attach_semantic_hash(rec):
 fields=rec.get("semantic_fields") or {}
 rec["semantic_fields_hash"]=objhash(fields)
 return rec

DERIVED_RELATION_TYPES={"midpoint-of-entity":"midpoint","center-of":"center","midpoint-between":"midpoint"}

def derived_candidate_nodes(r,lms,bnodes):
 token=DERIVED_RELATION_TYPES.get(r["relation_type"])
 if not token:return []
 args=list(r.get("argument_node_ids",[]));aspans=[span_info(a) for a in args]
 out=[]
 for n in lms:
  raw=norm(n.get("source_raw"));sp=span_info(n["node_id"])
  if not sp or token not in raw:continue
  # Candidate must belong to same source statement and textually contain at least one producer operand span.
  if n.get("source_statement_id")!=r.get("source_statement_id"):continue
  if any(a and a[0]==sp[0] and sp[1]<=a[1] and a[2]<=sp[2] for a in aspans):
   out.append(n["node_id"])
 return sorted(out,key=lambda x:((span_info(x)[2]-span_info(x)[1]) if span_info(x) else 10**9,x))

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json")
 ap.add_argument("--model-dir",default="public/models")
 ap.add_argument("--substrate",default=".tmp/c-v3-repair/spatial-substrate.json")
 ap.add_argument("--calibration",default=".tmp/c-v3-repair/review/calibration-draft.json")
 ap.add_argument("--approval",default="artifacts/c-v3/vertical-slice-v1/registry-calibration-approval.json")
 ap.add_argument("--out",default=".tmp/c-v3-repair/stage2-repaired-execution.json")
 args=ap.parse_args()
 if sha256(Path(args.graph))!=B_SHA:raise SystemExit("B v2.1 SHA mismatch")
 if git_blob("scripts/cv3/slice_surface_registry.py")!=EXPECTED_GEOMETRY_BLOB:raise SystemExit("approved surface executor changed")
 if git_blob("scripts/cv3/build_vertical_slice_review.py")!=EXPECTED_REVIEW_BUILDER_BLOB:raise SystemExit("approved calibration builder changed")
 approval=json.loads(Path(args.approval).read_text())
 if approval.get("status")!="APPROVED":raise SystemExit("registry/calibration approval missing")
 calibration=json.loads(Path(args.calibration).read_text());cal={x["calibration_id"]:x for x in calibration["rows"]}
 g=json.loads(Path(args.graph).read_text());store=AtlasStore(Path(args.model_dir));sub=json.loads(Path(args.substrate).read_text())
 surf=execute_all(store,sub);stmt={x["source_statement_id"]:x for x in g["source_statements"]}
 concepts={x["id"]:x for x in store.atlas["concepts"]};all_points={x["point_id"] for x in g["points"]}
 bindings=g.get("composite_bindings",[]);binding_by_child={x["child_landmark_id"]:x for x in bindings}
 children_by_parent=collections.defaultdict(list)
 for b in bindings:children_by_parent[b["parent_landmark_id"]].append(b["child_landmark_id"])
 bnodes={x["node_id"]:x for x in g["landmark_nodes"]}
 out={"schema_version":"2.0.0","artifact":"c-v3-vertical-slice-v1-stage2-semantic-repair","status":"GENERATED_NOT_VALIDATED",
  "scope":{"cohort":list(COHORT),"physical_coordinates_generated":False,"legacy_coordinate_input":False},
  "repair_contract":{"parent_only_composite_resolution_forbidden":True,"child_dependency_binding_required":True,
   "distinct_subfeatures_require_distinct_executable_identity":True,"incompatible_body_position_must_be_conditional":True,
   "quantitative_relation_semantics_loss_forbidden":True,"derived_operator_output_binding_required":True},
  "points":[]}
 for pid in COHORT:
  ss=[x for x in g["source_statements"] if x["point_id"]==pid];sm={x["source_statement_id"] for x in ss}
  lms=[x for x in g["landmark_nodes"] if x["point_id"]==pid];rels=[x for x in g["relation_instances"] if x["subject_node_id"]==f"P:{pid}"]
  pms=[x for x in g.get("proportional_measurements",[]) if x["source_statement_id"] in sm]
  conds=[x for x in g.get("conditions",[]) if x["source_statement_id"] in sm]
  lout={}
  for n in lms:
   nid=n["node_id"];disp=n.get("terminal_disposition")
   if disp=="resolved_fma":
    co=concepts.get(n.get("fma_id"))
    if co and co.get("elements"):lout[nid]={"status":"RESOLVED","executor":"fma_mesh","geometry":{"kind":"fma_concept","fma_id":n["fma_id"],"concept_name":co["name"],"part_ids":co["elements"]}}
    else:lout[nid]={"status":"UNRESOLVED","executor":"fma_mesh","geometry":None,"reason":"FMA concept has no atlas mesh elements"}
   elif disp=="cross_reference":
    rid=n.get("cross_reference_point_id") or parse_ref(n.get("source_raw",""))
    lout[nid]={"status":"RESOLVED" if rid in all_points else "INVALID","executor":"reference_acupoint",
      "geometry":{"kind":"reference_acupoint","point_id":rid} if rid in all_points else None,
      "reason":None if rid in all_points else "reference point absent from B graph"}
   else:
    sr=surface_registry_id(n,stmt[n["source_statement_id"]]["text_canonical"])
    if sr:
     rr=surf[sr];lout[nid]={"status":rr.status,"executor":"approved_surface_registry",
      "geometry":{"kind":"surface_registry","registry_id":sr,"geometry_hash":rr.geometry_hash()} if rr.status=="RESOLVED" else None,
      "reason":rr.notes[0] if rr.notes else (None if rr.status=="RESOLVED" else "approved registry unresolved")}
    elif disp in ("registry_limited","specialized_anchor"):
     z=atlas_lookup(store,n.get("source_raw",""));lout[nid]={"executor":"atlas_name_resolution",**z}
    elif disp in ("source_backed_derived_unresolved","ambiguous_generic","parent_unresolved","blocked_by_context"):
     z=atlas_lookup(store,n.get("source_raw",""))
     lout[nid]={"executor":"atlas_name_resolution",**z} if z["status"]=="RESOLVED" else {"status":"UNRESOLVED","executor":"explicit_unresolved_taxonomy","geometry":None,"reason":disp}
    else:
     z=atlas_lookup(store,n.get("source_raw",""))
     lout[nid]={"executor":"atlas_name_resolution",**z} if z["status"]!="UNRESOLVED" else {"status":"UNRESOLVED","executor":"no_family_executor","geometry":None,"reason":f"unsupported or unresolved landmark: {disp}/{n.get('landmark_class')}"}
  # Bound child subfeatures override any coarse lookup.
  for n in lms:
   nid=n["node_id"]
   if nid not in binding_by_child:continue
   b=binding_by_child[nid];parent_id=b["parent_landmark_id"];sf=subfeature_type(n.get("source_raw"));par=lout.get(parent_id)
   if not sf:
    lout[nid]={"status":"UNRESOLVED","executor":"composite_subfeature_binding","geometry":None,"reason":"child subfeature type not recognized","provenance":{"binding_id":b["binding_id"],"parent_landmark_id":parent_id}}
   elif not par or par.get("status")!="RESOLVED":
    lout[nid]={"status":"UNRESOLVED","executor":"composite_subfeature_binding","geometry":None,"reason":"parent entity is not uniquely resolved","provenance":{"binding_id":b["binding_id"],"parent_landmark_id":parent_id,"subfeature_type":sf}}
   elif sf in SYMBOLIC_CONSTRUCTIBLE:
    rule=SYMBOLIC_CONSTRUCTIBLE[sf];spec={"rule":rule,"parent_identity":geometry_identity(par),"subfeature_type":sf,"parent_landmark_id":parent_id}
    gh=objhash(spec);cid=f"SUBFEATURE:{sf}:{parent_id}:{gh[:16]}"
    lout[nid]={"status":"RESOLVED","executor":"constructed_subfeature","geometry":{"kind":"constructed_subfeature","subfeature_type":sf,
      "parent_landmark_id":parent_id,"construction_rule":rule,"constructed_id":cid,"geometry_hash":gh},
      "provenance":{"binding_id":b["binding_id"],"parent_landmark_id":parent_id}}
   else:
    lout[nid]={"status":"UNRESOLVED","executor":"composite_subfeature_binding","geometry":None,
      "reason":f"no approved executable construction rule for subfeature '{sf}'",
      "provenance":{"binding_id":b["binding_id"],"parent_landmark_id":parent_id,"subfeature_type":sf}}
  # Any semantic operand containing subfeature language may not survive as a
  # parent whole-entity geometry.  Bindings are detected by source-span containment,
  # because B may bind the child to the entity fragment while a relation references
  # a larger composite phrase spanning both fragments.
  for n in lms:
   nid=n["node_id"];sf=subfeature_type(n.get("source_raw"))
   if not sf or nid in binding_by_child:continue
   relevant=[k for k in contained_bound_children(nid,bindings) if subfeature_type(bnodes.get(k,{}).get("source_raw"))]
   if len(relevant)==1 and lout.get(relevant[0],{}).get("status")=="RESOLVED":
    child=relevant[0];cg=lout[child]["geometry"]
    lout[nid]={"status":"RESOLVED","executor":"bound_composite_subfeature","geometry":{"kind":"bound_subfeature",
      "semantic_parent_landmark_id":nid,"executable_child_landmark_id":child,"constructed_id":cg.get("constructed_id"),"geometry_hash":cg.get("geometry_hash"),
      "subfeature_type":cg.get("subfeature_type")},"provenance":{"child_landmark_ids":relevant}}
   else:
    lout[nid]={"status":"UNRESOLVED","executor":"bound_composite_subfeature","geometry":None,
      "reason":"composite contains subfeature semantics but no unique executable child subfeature geometry",
      "provenance":{"child_landmark_ids":relevant,"subfeature_type":sf}}
  mout={}
  for m in pms:
   row=cal.get(m["measurement_id"])
   if not row or not row.get("who_citation",{}).get("pdf_page"):mout[m["measurement_id"]]={"status":"UNRESOLVED","executor":"approved_calibration","reason":"approved WHO-cited calibration unavailable"}
   else:mout[m["measurement_id"]]={"status":"RESOLVED","executor":"approved_calibration","constraint":{"kind":"proportional_offset","value":m.get("value"),
    "unit":"F-cun" if str(m.get("unit")).lower()=="f-cun" else m.get("unit"),"source_unit":m.get("unit"),"direction":m.get("direction"),
    "anchor_landmark_id":m.get("anchor_landmark_id"),"who_pdf_page":row["who_citation"]["pdf_page"],"source_statement_id":m["source_statement_id"]}}
  cout={}
  for c in conds:
   raw=norm((c.get("source_span") or {}).get("source_raw"))
   pose_incompatible=(c["condition_type"]=="body_position" and any(x in raw for x in ("auricle folded","folded forward","folded forwards","head is turned","head turned","against resistance","pressed against")))
   if pose_incompatible:st="CONDITIONAL";reason="condition requires pose incompatible with default BodyParts3D pose"
   elif c["condition_type"] in ("alternative","palpation_dependent"):st="CONDITIONAL";reason="condition preserved as non-executed conditional branch"
   else:st="RESOLVED";reason=None
   cout[c["condition_id"]]={"status":st,"executor":"condition_contract","condition_type":c["condition_type"],"branch_id":c.get("branch_id"),
    "source_statement_id":c["source_statement_id"],"source_span":c.get("source_span"),
    "default_pose_compatible":False if pose_incompatible else None,"reason":reason}
  # Pre-execute named derived-geometry producers so their outputs can become
  # executable operands of downstream relations in the same semantic statement.
  rout={};derived_outputs={}
  for r in rels:
   if r["relation_type"] not in DERIVED_RELATION_TYPES:continue
   rid=r["relation_id"];op=REL_OP.get(r["relation_type"]);semantic=list(r.get("argument_node_ids",[]))
   bound_ms,stmt_ms=relation_measurements(r,pms,mout);semantic_fields=relation_semantic_fields(r,op,semantic,bound_ms,stmt_ms)
   args=[lout.get(x,{"status":"INVALID"}) for x in semantic]
   if not op or any(x.get("status")!="RESOLVED" for x in args):
    rout[rid]=attach_semantic_hash({"status":"UNRESOLVED","executor":op or "relation_dispatch","reason":"derived geometry producer operand not executable",
      "semantic_fields":semantic_fields,"semantic_argument_node_ids":semantic,"executable_argument_node_ids":semantic,
      "operand_binding_trace":[{"semantic_operand_id":x,"executable_operand_id":x,"binding":"identity"} for x in semantic]})
    continue
   spec={"producer_relation_id":rid,"operator":op,"relation_type":r["relation_type"],
         "source_statement_id":r["source_statement_id"],"argument_node_ids":semantic,
         "argument_identities":[geometry_identity(lout[x]) for x in semantic]}
   gh=objhash(spec);dgid=f"DERIVED:{rid}:{gh[:16]}"
   derived_outputs[dgid]={"derived_geometry_id":dgid,"producer_relation_id":rid,"operator":op,"geometry_hash":gh,
     "source_statement_id":r["source_statement_id"],"semantic_argument_node_ids":semantic}
   candidates=derived_candidate_nodes(r,lms,bnodes)
   for nid in candidates:
    lout[nid]={"status":"RESOLVED","executor":"derived_relation_output","geometry":{"kind":"derived_relation_output",
      "producer_relation_id":rid,"derived_geometry_id":dgid,"constructed_id":dgid,"geometry_hash":gh,
      "construction_rule":op},"provenance":{"producer_relation_id":rid,"producer_argument_node_ids":semantic}}
   con=dict(semantic_fields);con.update({"argument_node_ids":semantic,"executable_argument_node_ids":semantic,
     "operand_binding_trace":[{"semantic_operand_id":x,"executable_operand_id":x,"binding":"identity"} for x in semantic],
     "result_geometry_id":dgid,"result_geometry_hash":gh})
   rout[rid]=attach_semantic_hash({"status":"RESOLVED","executor":op,"constraint":con,"semantic_fields":semantic_fields,
     "semantic_argument_node_ids":semantic,"executable_argument_node_ids":semantic,
     "operand_binding_trace":con["operand_binding_trace"],"result_geometry_id":dgid,"result_geometry_hash":gh})
  for r in rels:
   rid=r["relation_id"]
   if rid in rout:continue
   op=REL_OP.get(r["relation_type"]);semantic=list(r.get("argument_node_ids",[]))
   bound_ms,stmt_ms=relation_measurements(r,pms,mout)
   semantic_fields=relation_semantic_fields(r,op,semantic,bound_ms,stmt_ms)
   if not op:
    rout[rid]=attach_semantic_hash({"status":"INVALID","executor":"relation_dispatch","reason":"relation family has no slice executor",
      "semantic_fields":semantic_fields,"semantic_argument_node_ids":semantic,"executable_argument_node_ids":[],"operand_binding_trace":[]});continue
   # Non-operand semantics are captured before any executable-operand repair.
   # They remain present even when execution becomes UNRESOLVED.
   if r["relation_type"]=="relative-to" and not semantic_fields.get("direction"):
    rout[rid]=attach_semantic_hash({"status":"UNRESOLVED","executor":op,"reason":"direction cue not normalized",
      "semantic_fields":semantic_fields,"semantic_argument_node_ids":semantic,"executable_argument_node_ids":[],"operand_binding_trace":[]});continue
   executable=[];binding_trace=[];ambiguous=False
   for a in semantic:
    kids=[k for k in contained_bound_children(a,bindings) if subfeature_type(bnodes.get(k,{}).get("source_raw"))]
    asf=subfeature_type(bnodes.get(a,{}).get("source_raw"))
    if kids:
     if len(kids)==1:
      executable.append(kids[0]);binding_trace.append({"semantic_operand_id":a,"executable_operand_id":kids[0],"binding":"child_subfeature"})
     else:
      ambiguous=True;binding_trace.append({"semantic_operand_id":a,"executable_operand_ids":kids,"binding":"ambiguous_multi_subfeature"})
    elif asf:
     ambiguous=True;binding_trace.append({"semantic_operand_id":a,"executable_operand_ids":[],"binding":"missing_executable_subfeature"})
    else:
     executable.append(a);binding_trace.append({"semantic_operand_id":a,"executable_operand_id":a,"binding":"identity"})
   if ambiguous:
    rout[rid]=attach_semantic_hash({"status":"UNRESOLVED","executor":op,"reason":"semantic composite has multiple child subfeatures and no unique executable operand",
      "semantic_fields":semantic_fields,"semantic_argument_node_ids":semantic,"executable_argument_node_ids":executable,"operand_binding_trace":binding_trace});continue
   argrecs=[lout.get(x,{"status":"INVALID"}) for x in executable]
   worst=sorted((x["status"] for x in argrecs),key=status_rank,reverse=True)[0] if argrecs else "RESOLVED"
   if worst in ("INVALID","UNRESOLVED","MULTIPLE"):
    rout[rid]=attach_semantic_hash({"status":worst,"executor":op,"reason":"executable operand not uniquely executable",
      "semantic_fields":semantic_fields,"semantic_argument_node_ids":semantic,"executable_argument_node_ids":executable,"operand_binding_trace":binding_trace});continue
   if len(executable)>1:
    fps=[geometry_identity(lout[x]) for x in executable]
    sft=[subfeature_type(bnodes.get(x,{}).get("source_raw")) for x in executable]
    collision=False
    for i in range(len(executable)):
     for j in range(i+1,len(executable)):
      if sft[i] and sft[j] and sft[i]!=sft[j] and fps[i] and fps[i]==fps[j]:
       collision=True;break
     if collision:break
    if collision:
     rout[rid]=attach_semantic_hash({"status":"UNRESOLVED","executor":op,"reason":"DISTINCT_SEMANTIC_SUBFEATURES_REQUIRE_DISTINCT_EXECUTABLE_IDENTITY",
      "semantic_fields":semantic_fields,"semantic_argument_node_ids":semantic,"executable_argument_node_ids":executable,"operand_binding_trace":binding_trace});continue
   con=dict(semantic_fields)
   con.update({"argument_node_ids":semantic,"executable_argument_node_ids":executable,"operand_binding_trace":binding_trace})
   rout[rid]=attach_semantic_hash({"status":"RESOLVED","executor":op,"constraint":con,"semantic_fields":semantic_fields,
     "semantic_argument_node_ids":semantic,"executable_argument_node_ids":executable,"operand_binding_trace":binding_trace})
  statements=[]
  for s in ss:
   sid=s["source_statement_id"];rr=[r["relation_id"] for r in rels if r["source_statement_id"]==sid];mm=[m["measurement_id"] for m in pms if m["source_statement_id"]==sid];cc=[c["condition_id"] for c in conds if c["source_statement_id"]==sid]
   statuses=[rout[x]["status"] for x in rr]+[mout[x]["status"] for x in mm]
   base="RESOLVED" if not statuses else sorted(statuses,key=status_rank,reverse=True)[0]
   statements.append({"source_statement_id":sid,"section":s["section"],"status":base,"relation_ids":rr,"measurement_ids":mm,"condition_ids":cc})
  loc=next((x for x in statements if x["section"]=="location"),None)
  out["points"].append({"point_id":pid,"primary_location_status":loc["status"] if loc else "UNRESOLVED","landmarks":lout,"relations":rout,
    "measurements":mout,"derived_geometries":derived_outputs,"conditions":cout,"statements":statements})
 q=Path(args.out);q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"points":20,"primary":dict(collections.Counter(x["primary_location_status"] for x in out["points"])),
  "conditions":dict(collections.Counter(v["status"] for x in out["points"] for v in x["conditions"].values()))}))
if __name__=="__main__":main()
