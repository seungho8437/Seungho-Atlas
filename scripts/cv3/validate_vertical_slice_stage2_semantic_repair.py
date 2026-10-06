#!/usr/bin/env python3
"""Independent semantic-repair validator for Vertical Slice v1 Stage 2.

Does not import the repair executor. Contracts are independently encoded from
the human-audit requirements.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,re
from pathlib import Path

COHORT=("HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26","ST2","ST10","LI18","LI17","BL17","BL23","BL25","BL40","TE20","ST4","TE6","ST9")
KNOWN={"TE20","ST10","LI17","LI18","BL17","BL23","BL25","ST9"}
SUBFEATURE_SYNONYMS=(
 ("superior border","superior_border"),("inferior border","inferior_border"),
 ("anterior border","anterior_border"),("posterior border","posterior_border"),
 ("free extremity","free_end"),("free end","free_end"),
 ("midpoint","midpoint"),("centre","center"),("center","center"),
 ("margin","margin"),("edge","edge"),("angle","angle"),("apex","apex"),
 ("tip","tip"),("border","border"),("end","end"),("process","process"))

def norm(s):return re.sub(r"[^a-z0-9]+"," ",(s or "").lower()).strip()
def expected_direction(rel):
 cue=norm((rel.get("cue_span") or {}).get("source_raw"))
 return next((x for x in ("radial","ulnar","anterior","posterior","superior","inferior","medial","lateral","proximal","distal") if x in cue),None)
def expected_measurements_for_relation(rel,g):
 same=[m for m in g.get("proportional_measurements",[]) if m["source_statement_id"]==rel.get("source_statement_id")]
 if rel.get("relation_type")!="relative-to":return [],same
 d=expected_direction(rel)
 return [m for m in same if m.get("direction")==d],same
def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"))
def objhash(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def expected_subfeature_normalization(raw):
 n=norm(raw)
 for lexical,canonical in SUBFEATURE_SYNONYMS:
  if lexical in n:return {"source_lexical_form":lexical,"canonical_subfeature_type":canonical}
 return None
def sf(raw):
 x=expected_subfeature_normalization(raw);return x["canonical_subfeature_type"] if x else None
def fma_atomic_at_same_granularity(node):
 if node.get("terminal_disposition")!="resolved_fma" or not node.get("fma_name"):return False
 ex=expected_subfeature_normalization(node.get("source_raw"))
 if not ex:return True
 fname=norm(node.get("fma_name"));lex=ex["source_lexical_form"];canon=ex["canonical_subfeature_type"]
 if lex in fname:return True
 if canon=="free_end" and ("free end" in fname or "free extremity" in fname):return True
 if canon=="center" and ("center" in fname or "centre" in fname):return True
 return False
def identity(rec):
 g=rec.get("geometry") or {}
 if g.get("geometry_hash"):return "hash:"+g["geometry_hash"]
 if g.get("constructed_id"):return "constructed:"+g["constructed_id"]
 if g.get("fma_id"):return "fma:"+g["fma_id"]+":"+",".join(sorted(g.get("part_ids",[])))
 if g.get("concept_id"):return "concept:"+g["concept_id"]+":"+",".join(sorted(g.get("part_ids",[])))
 if g.get("part_id"):return "part:"+g["part_id"]
 if g.get("registry_id"):return "registry:"+g["registry_id"]+":"+str(g.get("geometry_hash"))
 if g.get("point_id"):return "point:"+g["point_id"]
 return None

def span_info(node_id):
 m=re.search(r":(\d+)-(\d+)(?::[^:]+)?$",node_id or "")
 return (node_id[:m.start()],int(m.group(1)),int(m.group(2))) if m else None

def lexicalized_atomic_container(child_id,parent_id,bnodes):
 cs=span_info(child_id);ps=span_info(parent_id)
 if not cs or not ps or cs[0]!=ps[0]:return None
 for nid,n in bnodes.items():
  if nid in (child_id,parent_id):continue
  ns=span_info(nid)
  if not ns or ns[0]!=cs[0]:continue
  if ns[1]<=cs[1] and cs[2]<=ns[2] and ns[1]<=ps[1] and ps[2]<=ns[2] and fma_atomic_at_same_granularity(n):
   return nid
 return None

def contained_children(arg_id,bindings,bnodes):
 a=span_info(arg_id)
 if not a:return []
 out=[]
 for b in bindings:
  cs=span_info(b["child_landmark_id"]);ps=span_info(b["parent_landmark_id"])
  if not cs or not ps or cs[0]!=a[0] or ps[0]!=a[0]:continue
  if a[1]<=cs[1] and cs[2]<=a[2] and a[1]<=ps[1] and ps[2]<=a[2] and sf(bnodes.get(b["child_landmark_id"],{}).get("source_raw")):
   out.append(b["child_landmark_id"])
 return out

def build_maps(g):
 bnodes={x["node_id"]:x for x in g["landmark_nodes"]};children={}
 for b in g.get("composite_bindings",[]):children.setdefault(b["parent_landmark_id"],[]).append(b["child_landmark_id"])
 cond={x["condition_id"]:x for x in g.get("conditions",[])}
 rel={x["relation_id"]:x for x in g.get("relation_instances",[])}
 return bnodes,children,cond,rel

def derived_target_candidates(src_rel,g,bnodes):
 token={"midpoint-of-entity":"midpoint","center-of":"center","midpoint-between":"midpoint"}.get(src_rel.get("relation_type"))
 if not token:return []
 def span_info_local(node_id):
  m=re.search(r":(\d+)-(\d+)(?::[^:]+)?$",node_id or "")
  return (node_id[:m.start()],int(m.group(1)),int(m.group(2))) if m else None
 args=list(src_rel.get("argument_node_ids",[]));asp=[span_info_local(a) for a in args]
 out=[]
 for n in g.get("landmark_nodes",[]):
  if n.get("source_statement_id")!=src_rel.get("source_statement_id"):continue
  if token not in norm(n.get("source_raw")):continue
  sp=span_info_local(n["node_id"])
  if not sp:continue
  if any(a and a[0]==sp[0] and sp[1]<=a[1] and a[2]<=sp[2] for a in asp):out.append(n["node_id"])
 return sorted(out)

def scan(out,g):
 bnodes,children,condsrc,relsrc=build_maps(g);bindings=g.get("composite_bindings",[]);binding_by_child={x["child_landmark_id"]:x for x in bindings};findings=[]
 pby={x["point_id"]:x for x in out["points"]}
 for pid,p in pby.items():
  suppressed=p.get("lexicalized_suppressed_children",{})
  # Lexicalized anatomical entity guard + synonym normalization.
  for b in bindings:
   child=b["child_landmark_id"];parent=b["parent_landmark_id"]
   if child not in p["landmarks"]:continue
   source=bnodes.get(child,{}).get("source_raw");expected_norm=expected_subfeature_normalization(source)
   container=lexicalized_atomic_container(child,parent,bnodes)
   rec=p["landmarks"].get(child,{})
   if expected_norm and rec.get("semantic_normalization")!=expected_norm:
    findings.append({"rule":"subfeature_synonym_normalization_gap","point_id":pid,"node_id":child,"source_raw":source,"expected":expected_norm,"actual":rec.get("semantic_normalization")})
   if container:
    if not rec.get("semantic_suppressed") or rec.get("executor")!="lexicalized_entity_guard" or child not in suppressed:
     findings.append({"rule":"lexicalized_anatomical_entity_false_subfeature_split","point_id":pid,"node_id":child,"parent_id":parent,"atomic_landmark_id":container,"record":rec})
    for rid,rr in p["relations"].items():
     exe=(rr.get("constraint") or {}).get("executable_argument_node_ids") or rr.get("executable_argument_node_ids") or []
     if child in exe:
      findings.append({"rule":"lexicalized_anatomical_entity_false_subfeature_split","point_id":pid,"node_id":child,"relation_id":rid,"detail":"suppressed lexical token used as executable operand"})
  # Rule 1 / 5: any non-child semantic node carrying subfeature language may not
  # resolve to only a coarse parent/entity geometry.
  for nid,rec in p["landmarks"].items():
   if nid in binding_by_child:continue
   psf=sf(bnodes.get(nid,{}).get("source_raw"))
   if psf and rec.get("status")=="RESOLVED" and not fma_atomic_at_same_granularity(bnodes.get(nid,{})):
    kind=(rec.get("geometry") or {}).get("kind")
    if kind not in ("bound_subfeature","constructed_subfeature","derived_relation_output"):
     findings.append({"rule":"parent_only_composite_resolution","point_id":pid,"node_id":nid,"source_raw":bnodes.get(nid,{}).get("source_raw"),"geometry_kind":kind,"identity":identity(rec)})
  # Rules 2 / 3 + trace completeness.
  for rid,r in p["relations"].items():
   semantic=(r.get("constraint") or {}).get("semantic_argument_node_ids") or (r.get("constraint") or {}).get("argument_node_ids") or r.get("semantic_argument_node_ids") or r.get("argument_node_ids") or []
   executable=(r.get("constraint") or {}).get("executable_argument_node_ids") or r.get("executable_argument_node_ids") or semantic
   src=relsrc.get(rid,{})
   sflds=r.get("semantic_fields") or {}
   exp_dir=expected_direction(src) if src.get("relation_type")=="relative-to" else None
   if sflds.get("op")!=r.get("executor"):
    findings.append({"rule":"relation_nonoperand_semantics_loss","point_id":pid,"relation_id":rid,"field":"op","expected":r.get("executor"),"actual":sflds.get("op")})
   if sflds.get("source_statement_id")!=src.get("source_statement_id"):
    findings.append({"rule":"relation_nonoperand_semantics_loss","point_id":pid,"relation_id":rid,"field":"source_statement_id","expected":src.get("source_statement_id"),"actual":sflds.get("source_statement_id")})
   if sflds.get("branch_id")!=src.get("branch_id"):
    findings.append({"rule":"relation_nonoperand_semantics_loss","point_id":pid,"relation_id":rid,"field":"branch_id","expected":src.get("branch_id"),"actual":sflds.get("branch_id")})
   if sflds.get("semantic_argument_node_ids")!=list(src.get("argument_node_ids",[])):
    findings.append({"rule":"relation_nonoperand_semantics_loss","point_id":pid,"relation_id":rid,"field":"semantic_argument_node_ids","expected":src.get("argument_node_ids",[]),"actual":sflds.get("semantic_argument_node_ids")})
   if src.get("relation_type")=="relative-to" and sflds.get("direction")!=exp_dir:
    findings.append({"rule":"direction_preservation_failure","point_id":pid,"relation_id":rid,"expected":exp_dir,"actual":sflds.get("direction")})
   exp_bound,exp_stmt=expected_measurements_for_relation(src,g)
   exp_bound_ids=[m["measurement_id"] for m in exp_bound];exp_stmt_ids=[m["measurement_id"] for m in exp_stmt]
   if sflds.get("bound_measurement_ids",[])!=exp_bound_ids:
    findings.append({"rule":"quantitative_relation_semantics_loss","point_id":pid,"relation_id":rid,"field":"bound_measurement_ids","expected":exp_bound_ids,"actual":sflds.get("bound_measurement_ids")})
   if sflds.get("statement_measurement_ids",[])!=exp_stmt_ids:
    findings.append({"rule":"quantitative_relation_semantics_loss","point_id":pid,"relation_id":rid,"field":"statement_measurement_ids","expected":exp_stmt_ids,"actual":sflds.get("statement_measurement_ids")})
   gotqc=sflds.get("quantitative_constraints",[])
   if len(gotqc)!=len(exp_bound):
    findings.append({"rule":"quantitative_relation_semantics_loss","point_id":pid,"relation_id":rid,"field":"quantitative_constraints_count","expected":len(exp_bound),"actual":len(gotqc)})
   else:
    for srcm,q in zip(exp_bound,gotqc):
     if q.get("value")!=srcm.get("value") or q.get("direction")!=srcm.get("direction") or q.get("source_statement_id")!=srcm.get("source_statement_id"):
      findings.append({"rule":"quantitative_relation_semantics_loss","point_id":pid,"relation_id":rid,"measurement_id":srcm["measurement_id"],"expected":{"value":srcm.get("value"),"direction":srcm.get("direction"),"source_statement_id":srcm.get("source_statement_id")},"actual":q})
     if not q.get("unit"):
      findings.append({"rule":"quantitative_relation_semantics_loss","point_id":pid,"relation_id":rid,"measurement_id":srcm["measurement_id"],"field":"unit","actual":q.get("unit")})
   if r.get("semantic_fields_hash")!=objhash(sflds):
    findings.append({"rule":"relation_semantic_hash_mismatch","point_id":pid,"relation_id":rid})
   if r.get("status")=="RESOLVED" and ("semantic_argument_node_ids" not in (r.get("constraint") or {}) or "executable_argument_node_ids" not in (r.get("constraint") or {})):
    findings.append({"rule":"operand_trace_incomplete","point_id":pid,"relation_id":rid})
   for a in semantic:
    kids=[k for k in contained_children(a,bindings,bnodes) if k not in suppressed]
    anode=bnodes.get(a,{})
    asf=None if fma_atomic_at_same_granularity(anode) else sf(anode.get("source_raw"))
    if r.get("status")=="RESOLVED":
     if kids and (a in executable or not any(k in executable for k in kids)):
      findings.append({"rule":"child_subfeature_unused_by_relation","point_id":pid,"relation_id":rid,"semantic_operand":a,"child_ids":kids,"executable_operands":executable})
     if asf and not kids and a in executable:
      akind=(p["landmarks"].get(a,{}).get("geometry") or {}).get("kind")
      if akind!="derived_relation_output":
       findings.append({"rule":"parent_only_composite_resolution","point_id":pid,"relation_id":rid,"node_id":a,"source_raw":bnodes.get(a,{}).get("source_raw"),"detail":"subfeature-bearing relation operand has no executable child"})
   if r.get("status")=="RESOLVED" and len(executable)>1:
    ids=[identity(p["landmarks"].get(x,{})) for x in executable]
    sfs=[sf(bnodes.get(x,{}).get("source_raw")) for x in executable]
    for i in range(len(executable)):
     for j in range(i+1,len(executable)):
      if sfs[i] and sfs[j] and sfs[i]!=sfs[j] and ids[i] and ids[i]==ids[j]:
       findings.append({"rule":"distinct_subfeature_identity_collapse","point_id":pid,"relation_id":rid,"operand_a":executable[i],"operand_b":executable[j],"identity":ids[i]})
  # Derived operator output must be consumable by downstream relations.
  derived=p.get("derived_geometries",{})
  for dgid,dg in derived.items():
   prod=dg.get("producer_relation_id")
   if prod not in p["relations"] or p["relations"][prod].get("status")!="RESOLVED":
    findings.append({"rule":"derived_geometry_output_not_bound","point_id":pid,"derived_geometry_id":dgid,"detail":"producer relation missing or not resolved"})
   refs=[nid for nid,rec in p["landmarks"].items() if (rec.get("geometry") or {}).get("derived_geometry_id")==dgid]
   src_rel=relsrc.get(prod,{})
   expected_targets=derived_target_candidates(src_rel,g,bnodes)
   if expected_targets and not refs:
    findings.append({"rule":"derived_geometry_output_not_bound","point_id":pid,"derived_geometry_id":dgid,"detail":"named derived semantic operand exists but output is not bound","expected_targets":expected_targets})
  for nid,rec in p["landmarks"].items():
   gref=rec.get("geometry") or {}
   if gref.get("kind")=="derived_relation_output":
    prod=gref.get("producer_relation_id");dgid=gref.get("derived_geometry_id")
    if not prod or dgid not in derived:
     findings.append({"rule":"derived_geometry_output_not_bound","point_id":pid,"node_id":nid,"detail":"derived landmark lacks registered producer/output"})
    # A resolved downstream relation that semantically references this node must execute against it.
    consumers=[(rid,r) for rid,r in p["relations"].items() if nid in ((r.get("semantic_fields") or {}).get("semantic_argument_node_ids") or []) and rid!=prod]
    for rid,r in consumers:
     exe=(r.get("constraint") or {}).get("executable_argument_node_ids") or r.get("executable_argument_node_ids") or []
     if r.get("status")=="RESOLVED" and nid not in exe:
      findings.append({"rule":"derived_geometry_output_not_bound","point_id":pid,"node_id":nid,"relation_id":rid,"detail":"resolved downstream relation does not consume derived output node"})
  # Child itself may not fallback to a whole parent mesh.
  for child,b in ((x["child_landmark_id"],x) for x in g.get("composite_bindings",[]) if x["child_landmark_id"] in p["landmarks"]):
   raw=bnodes.get(child,{}).get("source_raw");typ=sf(raw);rec=p["landmarks"][child]
   if child in suppressed:continue
   if typ and rec.get("status")=="RESOLVED":
    kind=(rec.get("geometry") or {}).get("kind")
    if kind not in ("constructed_subfeature","bound_subfeature","derived_relation_output"):
     findings.append({"rule":"child_subfeature_false_fallback","point_id":pid,"node_id":child,"subfeature":typ,"geometry_kind":kind,"identity":identity(rec)})
  # Rule 4: condition preservation.
  for cid,c in p["conditions"].items():
   src=condsrc.get(cid,{});raw=norm((src.get("source_span") or {}).get("source_raw"))
   incompatible=(src.get("condition_type")=="body_position" and any(x in raw for x in ("auricle folded","folded forward","folded forwards","head is turned","head turned","against resistance","pressed against")))
   if incompatible and c.get("status")=="RESOLVED":
    findings.append({"rule":"condition_preservation_failure","point_id":pid,"condition_id":cid,"source_raw":raw})
   if c.get("source_statement_id")!=src.get("source_statement_id"):
    findings.append({"rule":"condition_linkage_loss","point_id":pid,"condition_id":cid,"expected":src.get("source_statement_id"),"actual":c.get("source_statement_id")})
   if c.get("branch_id")!=src.get("branch_id"):
    findings.append({"rule":"condition_linkage_loss","point_id":pid,"condition_id":cid,"field":"branch_id","expected":src.get("branch_id"),"actual":c.get("branch_id")})
 return findings

def validate(out,before,g):
 errors=[];checks=0
 def ck(ok,code,detail=None):
  nonlocal checks;checks+=1
  if not ok:errors.append({"code":code,"detail":detail})
 pids=[x["point_id"] for x in out["points"]]
 ck(set(pids)==set(COHORT) and len(pids)==20,"REGRESSION_COVERAGE_20",pids)
 ck(KNOWN.issubset(set(pids)),"KNOWN_AFFECTED_COVERAGE_8")
 ck(out.get("scope",{}).get("physical_coordinates_generated") is False,"COORDINATE_GENERATION_NONZERO")
 ck(out.get("scope",{}).get("legacy_coordinate_input") is False,"LEGACY_INPUT_NONZERO")
 findings=scan(out,g)
 grouped={}
 for f in findings:grouped.setdefault(f["rule"],[]).append(f)
 for rule in ("parent_only_composite_resolution","child_subfeature_unused_by_relation","distinct_subfeature_identity_collapse","condition_preservation_failure","condition_linkage_loss","child_subfeature_false_fallback","operand_trace_incomplete","relation_nonoperand_semantics_loss","direction_preservation_failure","relation_semantic_hash_mismatch","quantitative_relation_semantics_loss","derived_geometry_output_not_bound","lexicalized_anatomical_entity_false_subfeature_split","subfeature_synonym_normalization_gap"):
  ck(len(grouped.get(rule,[]))==0,rule.upper(),grouped.get(rule,[]))
 # Trace completeness for every relation.
 for p in out["points"]:
  for rid,r in p["relations"].items():
   con=r.get("constraint") or {}
   if r.get("status")=="RESOLVED":
    ck("semantic_argument_node_ids" in con and "executable_argument_node_ids" in con and "operand_binding_trace" in con,"SEMANTIC_EXECUTABLE_TRACE_INCOMPLETE",{"point":p["point_id"],"relation":rid})
    for x in con.get("executable_argument_node_ids",[]):
     ck(x in p["landmarks"],"EXECUTABLE_OPERAND_NOT_LANDMARK_NODE",{"point":p["point_id"],"relation":rid,"operand":x})
     ck(p["landmarks"][x].get("status")=="RESOLVED","RESOLVED_RELATION_USES_NONRESOLVED_OPERAND",{"point":p["point_id"],"relation":rid,"operand":x})
 # Lossless measurement/value/unit/source semantics.
 pmap={x["point_id"]:x for x in out["points"]}
 for p in out["points"]:
  for mid,m in p["measurements"].items():
   con=m.get("constraint") or {}
   ck(con.get("value") is not None,"MEASUREMENT_VALUE_LOST",{"point":p["point_id"],"measurement":mid})
   ck(con.get("unit") is not None,"MEASUREMENT_UNIT_LOST",{"point":p["point_id"],"measurement":mid})
   ck(con.get("source_statement_id") is not None,"MEASUREMENT_SOURCE_LINK_LOST",{"point":p["point_id"],"measurement":mid})
 # Before/after regression inventory.
 pre=scan(before,g);new_pre=[f for f in pre if f["point_id"] not in KNOWN]
 return checks,errors,findings,pre,new_pre

def mutate_child_to_parent(out,g):
 m=copy.deepcopy(out);bnodes,children,_,relsrc=build_maps(g)
 for p in m["points"]:
  for rid,r in p["relations"].items():
   con=r.setdefault("constraint",{})
   semantic=con.get("semantic_argument_node_ids") or r.get("semantic_argument_node_ids") or r.get("argument_node_ids") or []
   for par in semantic:
    kids=contained_children(par,g.get("composite_bindings",[]),bnodes)
    if kids:
     # Forge exactly the forbidden parent-only execution.
     prec=p["landmarks"][par];prec["status"]="RESOLVED";prec["executor"]="fma_mesh";prec["geometry"]={"kind":"fma_concept","fma_id":"FMA_FORGED_PARENT","part_ids":["FORGED"]}
     con.update({"semantic_argument_node_ids":semantic,"executable_argument_node_ids":[par if x in kids else x for x in (con.get("executable_argument_node_ids") or semantic)],
       "operand_binding_trace":[{"semantic_operand_id":par,"executable_operand_id":par,"binding":"identity"}],"op":con.get("op") or r.get("executor")})
     r["status"]="RESOLVED";return m
 raise RuntimeError("no composite parent relation for negative test")

def mutate_distinct_same_hash(out,g):
 m=copy.deepcopy(out);bnodes,children,_,relsrc=build_maps(g);p=next(x for x in m["points"] if x["point_id"]=="LI18")
 candidates=[nid for nid in p["landmarks"] if sf(bnodes.get(nid,{}).get("source_raw")) in ("anterior border","posterior border")]
 if len(candidates)<2:
  candidates=[nid for nid in p["landmarks"] if sf(bnodes.get(nid,{}).get("source_raw"))]
 if len(candidates)<2:raise RuntimeError("LI18 distinct subfeatures unavailable")
 a,b=candidates[:2]
 fake={"kind":"constructed_subfeature","constructed_id":"SUBFEATURE:FORGED","geometry_hash":"FORGED_SAME_HASH"}
 for x in (a,b):p["landmarks"][x]={"status":"RESOLVED","executor":"constructed_subfeature","geometry":copy.deepcopy(fake)}
 # Make one multi-operand relation resolve against them.
 rid,nextrel=next(iter(p["relations"].items()));nextrel["status"]="RESOLVED";nextrel["constraint"]={"op":nextrel.get("executor"),"semantic_argument_node_ids":[a,b],"executable_argument_node_ids":[a,b],"argument_node_ids":[a,b],"operand_binding_trace":[],"source_statement_id":"FORGED"}
 return m

def mutate_same_level_parent(out,g):
 m=copy.deepcopy(out);bnodes,children,_,relsrc=build_maps(g)
 binding_by_child={x["child_landmark_id"]:x for x in g.get("composite_bindings",[])}
 # Prefer BL17, then any same-level relation carrying a bound child operand.
 points=sorted(m["points"],key=lambda x:(x["point_id"]!="BL17",x["point_id"]))
 for p in points:
  for rid,r in p["relations"].items():
   con=r.setdefault("constraint",{});op=con.get("op") or r.get("executor")
   if op!="same_level_plane":continue
   semantic=con.get("semantic_argument_node_ids") or r.get("semantic_argument_node_ids") or r.get("argument_node_ids") or []
   executable=con.get("executable_argument_node_ids") or semantic
   for sem in semantic:
    kids=contained_children(sem,g.get("composite_bindings",[]),bnodes)
    if kids:
     child=kids[0]
     p["landmarks"][sem]={"status":"RESOLVED","executor":"fma_mesh","geometry":{"kind":"fma_concept","fma_id":"FMA_FORGED_PARENT","part_ids":["FORGED"]}}
     con.update({"op":"same_level_plane","semantic_argument_node_ids":semantic,
       "executable_argument_node_ids":[sem if x==child else x for x in executable],
       "operand_binding_trace":[{"semantic_operand_id":sem,"executable_operand_id":sem,"binding":"FORGED_PARENT_REPLACEMENT"}]})
     r["status"]="RESOLVED";return m
 raise RuntimeError("no same-level bound child available")

def mutate_te20_condition(out):
 m=copy.deepcopy(out);p=next(x for x in m["points"] if x["point_id"]=="TE20")
 for c in p["conditions"].values():
  if c.get("status")=="CONDITIONAL":c["status"]="RESOLVED";return m
 raise RuntimeError("TE20 conditional unavailable")

def mutate_unknown_subfeature_fallback(out,g):
 m=copy.deepcopy(out);bnodes,children,_,relsrc=build_maps(g)
 for p in m["points"]:
  for child,rec in p["landmarks"].items():
   if sf(bnodes.get(child,{}).get("source_raw")) and rec.get("status")=="UNRESOLVED":
    # Forge whole-entity fallback, exactly the forbidden failure mode.
    rec.clear();rec.update({"status":"RESOLVED","executor":"fma_mesh","geometry":{"kind":"fma_concept","fma_id":"FMA_FORGED_PARENT","part_ids":["FORGED"]}})
    return m
 raise RuntimeError("no unresolved subfeature available")

def mutate_lexicalized_process_unsuppressed(out,g):
 m=copy.deepcopy(out)
 for p in m["points"]:
  for nid,meta in p.get("lexicalized_suppressed_children",{}).items():
   src=next((x for x in g["landmark_nodes"] if x["node_id"]==nid),{})
   if "process" in norm(src.get("source_raw")):
    rec=p["landmarks"][nid];rec["semantic_suppressed"]=False;rec["executor"]="composite_subfeature_binding";rec["reason"]="FORGED_GENERIC_PROCESS_SPLIT"
    return m
 raise RuntimeError("no suppressed process lexical token found")

def mutate_atomic_fma_internal_child_executable(out,g):
 m=copy.deepcopy(out)
 for p in m["points"]:
  for nid,meta in p.get("lexicalized_suppressed_children",{}).items():
   rec=p["landmarks"][nid];rec.update({"status":"RESOLVED","executor":"constructed_subfeature","semantic_suppressed":False,
    "geometry":{"kind":"constructed_subfeature","constructed_id":"FORGED_INTERNAL_CHILD","geometry_hash":"FORGED_INTERNAL_CHILD_HASH"}})
   # Force any relation in the same point to consume the false child.
   for rid,r in p["relations"].items():
    con=r.get("constraint")
    if isinstance(con,dict):
     con.setdefault("executable_argument_node_ids",[]).append(nid);return m
   return m
 raise RuntimeError("no suppressed atomic-FMA internal child found")

def mutate_free_extremity_normalization_removed(out,g):
 m=copy.deepcopy(out)
 for p in m["points"]:
  for nid,rec in p["landmarks"].items():
   src=next((x for x in g["landmark_nodes"] if x["node_id"]==nid),{})
   if "free extremity" in norm(src.get("source_raw")):
    rec["semantic_normalization"]=None;rec["reason"]="child subfeature type not recognized";return m
 raise RuntimeError("no free extremity node found")

def mutate_synonym_to_unknown(out,g):
 m=copy.deepcopy(out)
 for p in m["points"]:
  for nid,rec in p["landmarks"].items():
   normrec=rec.get("semantic_normalization")
   if normrec and normrec.get("source_lexical_form") in ("free extremity","centre"):
    rec["semantic_normalization"]={"source_lexical_form":normrec["source_lexical_form"],"canonical_subfeature_type":"UNKNOWN_SUBFEATURE"}
    return m
 raise RuntimeError("no normalized synonym node found")

def mutate_measurement_value_to_none(out,g):
 m=copy.deepcopy(out)
 for p in m["points"]:
  for rid,r in p["relations"].items():
   sflds=r.get("semantic_fields") or {}
   qs=sflds.get("quantitative_constraints") or []
   if qs:
    qs[0]["value"]=None;r["semantic_fields_hash"]=objhash(sflds);return m
 raise RuntimeError("no quantitative relation for negative test")

def mutate_measurement_unit_to_none(out,g):
 m=copy.deepcopy(out)
 for p in m["points"]:
  for rid,r in p["relations"].items():
   sflds=r.get("semantic_fields") or {}
   qs=sflds.get("quantitative_constraints") or []
   if qs:
    qs[0]["unit"]=None;r["semantic_fields_hash"]=objhash(sflds);return m
 raise RuntimeError("no quantitative relation for negative test")

def mutate_remove_derived_binding(out,g):
 m=copy.deepcopy(out)
 for p in m["points"]:
  for nid,rec in p["landmarks"].items():
   gg=rec.get("geometry") or {}
   if gg.get("kind")=="derived_relation_output":
    rec["status"]="UNRESOLVED";rec["geometry"]=None;rec["reason"]="FORGED_DERIVED_OUTPUT_REMOVAL";return m
 raise RuntimeError("no derived output landmark for negative test")

def mutate_direction_to_none(out,g,direction):
 m=copy.deepcopy(out);rels={x["relation_id"]:x for x in g.get("relation_instances",[])}
 for p in m["points"]:
  for rid,r in p["relations"].items():
   src=rels.get(rid,{})
   if src.get("relation_type")=="relative-to" and expected_direction(src)==direction:
    sflds=r.setdefault("semantic_fields",{});sflds["direction"]=None
    r["semantic_fields_hash"]=objhash(sflds)
    if "constraint" in r and isinstance(r["constraint"],dict):r["constraint"]["direction"]=None
    return m
 raise RuntimeError(f"no {direction} relation for negative test")

def rejected(mut,before,g):
 _,errs,find,_,_=validate(mut,before,g)
 return bool(errs or find)

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--before",required=True);ap.add_argument("--after",required=True);ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json");ap.add_argument("--out",required=True);args=ap.parse_args()
 before=json.loads(Path(args.before).read_text());after=json.loads(Path(args.after).read_text());g=json.loads(Path(args.graph).read_text())
 checks,errors,remaining,pre,new_pre=validate(after,before,g)
 muts={
  "child_removed_parent_whole_mesh":mutate_child_to_parent(after,g),
  "distinct_borders_same_geometry_hash":mutate_distinct_same_hash(after,g),
  "same_level_child_replaced_by_parent":mutate_same_level_parent(after,g),
  "te20_conditional_to_resolved":mutate_te20_condition(after),
  "unknown_subfeature_whole_entity_fallback":mutate_unknown_subfeature_fallback(after,g),
  "direction_anterior_to_none":mutate_direction_to_none(after,g,"anterior"),
  "direction_posterior_to_none":mutate_direction_to_none(after,g,"posterior"),
  "direction_radial_to_none":mutate_direction_to_none(after,g,"radial"),
  "direction_lateral_to_none":mutate_direction_to_none(after,g,"lateral"),
  "quantitative_value_to_none":mutate_measurement_value_to_none(after,g),
  "quantitative_unit_to_none":mutate_measurement_unit_to_none(after,g),
  "derived_output_binding_removed":mutate_remove_derived_binding(after,g),
  "lexicalized_process_generic_split":mutate_lexicalized_process_unsuppressed(after,g),
  "atomic_fma_internal_child_executable":mutate_atomic_fma_internal_child_executable(after,g),
  "free_extremity_normalization_removed":mutate_free_extremity_normalization_removed(after,g),
  "synonym_left_unknown":mutate_synonym_to_unknown(after,g)
 }
 neg={k:rejected(v,before,g) for k,v in muts.items()}
 for k,v in neg.items():
  checks+=1
  if not v:errors.append({"code":"NEGATIVE_TEST_NOT_REJECTED","detail":k})
 status="PASS" if not errors else "FAIL"
 def count(rule,arr):return sum(x["rule"]==rule for x in arr)
 report={"schema_version":"1.0.0","artifact":"c-v3-stage2-semantic-repair-validation","status":status,
  "checks":checks,"errors":len(errors),"error_details":errors,
  "coverage":{"known_affected":8,"regression_points":20},
  "remaining_defects":remaining,
  "pre_repair_scan":{"total":len(pre),"new_regression_defects_outside_known8":len(new_pre),"new_regression_findings":new_pre},
  "post_repair_counts":{
   "parent_only_collapse":count("parent_only_composite_resolution",remaining),
   "unused_child_subfeature":count("child_subfeature_unused_by_relation",remaining),
   "distinct_subfeature_identity_collapse":count("distinct_subfeature_identity_collapse",remaining),
   "condition_preservation_failure":count("condition_preservation_failure",remaining),
   "direction_preservation_failure":count("direction_preservation_failure",remaining),
   "relation_nonoperand_semantics_loss":count("relation_nonoperand_semantics_loss",remaining),
   "condition_linkage_loss":count("condition_linkage_loss",remaining),
   "quantitative_relation_semantics_loss":count("quantitative_relation_semantics_loss",remaining),
   "derived_geometry_output_not_bound":count("derived_geometry_output_not_bound",remaining),
   "lexicalized_anatomical_entity_false_subfeature_split":count("lexicalized_anatomical_entity_false_subfeature_split",remaining),
   "subfeature_synonym_normalization_gap":count("subfeature_synonym_normalization_gap",remaining),
   "false_fallback":count("child_subfeature_false_fallback",remaining)},
  "negative_tests":neg,"coordinate_generation_count":0,"legacy_c_coordinate_reference_count":0,
  "final_state":{"stage2_automated_structural_validation":"PASS","stage2_semantic_repair_validation":status,"stage2_human_semantic_audit":"PENDING","stage3":"NOT_STARTED"}}
 Path(args.out).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"status":status,"checks":checks,"errors":len(errors),"new_regression_defects":len(new_pre),"post_counts":report["post_repair_counts"],"negative_tests":neg}))
 raise SystemExit(0 if status=="PASS" else 1)
if __name__=="__main__":main()
