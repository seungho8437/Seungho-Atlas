#!/usr/bin/env python3
"""Discover a ~20-point vertical-slice cohort from frozen B v2.1.

Selection favors points whose landmark dependencies are already resolved_fma and
whose surface-expression burden is low. A small forced regression set is always
included to prevent an easy-only pilot.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,re
from pathlib import Path

EXPECTED_B_SHA256="8126e20938a478a2d214f4a8487cabeebc8f3115f7a81ad30e46b594958fb2c1"
FORCED=("HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26")
SURFACE_CLASSES={
 "surface.aspect","crease.skin_crease","line.anatomical_line","line.reference_line",
 "boundary.border","space.anatomical_space","fossa_or_depression","orifice_or_cavity"
}
HARD={"source_backed_derived_unresolved","ambiguous_generic","parent_unresolved","blocked_by_context"}

def sha256(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def meridian(pid):
 return re.match(r"^[A-Z]+",pid).group(0)

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json");ap.add_argument("--out",default=".tmp/c-v3-slice/cohort-discovery.json");args=ap.parse_args()
 p=Path(args.graph)
 if sha256(p)!=EXPECTED_B_SHA256: raise SystemExit("B v2.1 SHA mismatch")
 g=json.loads(p.read_text())
 statements=collections.defaultdict(list)
 for s in g["source_statements"]:statements[s["point_id"]].append(s)
 lms=collections.defaultdict(list)
 for x in g["landmark_nodes"]:lms[x["point_id"]].append(x)
 rels=collections.defaultdict(list)
 for r in g["relation_instances"]:
  pid=r["subject_node_id"].split(":",1)[1]
  rels[pid].append(r)
 meas=collections.defaultdict(list)
 sid2pid={s["source_statement_id"]:s["point_id"] for s in g["source_statements"]}
 for m in g.get("proportional_measurements",[]):meas[sid2pid[m["source_statement_id"]]].append(m)
 cond=collections.defaultdict(list)
 for c in g.get("conditions",[]):cond[sid2pid[c["source_statement_id"]]].append(c)

 rows=[]
 for pnt in g["points"]:
  pid=pnt["point_id"]; xs=lms[pid]
  disp=collections.Counter(x.get("terminal_disposition","<none>") for x in xs)
  cls=collections.Counter(x.get("landmark_class","<none>") for x in xs)
  resolved=disp["resolved_fma"]; hard=sum(disp[x] for x in HARD); surface=sum(cls[x] for x in SURFACE_CLASSES)
  specialized=disp["specialized_anchor"]+disp["registry_limited"]
  total=max(len(xs),1)
  # higher is easier; hard unresolved heavily penalized.
  score=4*resolved - 5*hard - 2*surface - specialized - 2*len(meas[pid]) - 3*len(cond[pid])
  rows.append({
   "point_id":pid,"meridian":meridian(pid),"score":score,
   "landmarks":len(xs),"resolved_fma":resolved,"resolved_fma_ratio":resolved/total,
   "hard_unresolved":hard,"surface_expression_count":surface,"specialized_or_registry_limited":specialized,
   "measurement_count":len(meas[pid]),"condition_count":len(cond[pid]),
   "landmark_classes":dict(sorted(cls.items())),"terminal_dispositions":dict(sorted(disp.items())),
   "relation_types":dict(sorted(collections.Counter(r["relation_type"] for r in rels[pid]).items())),
   "source_statements":[{"id":s["source_statement_id"],"section":s["section"],"text":s["text_canonical"]} for s in statements[pid]]
  })
 byid={r["point_id"]:r for r in rows}
 selected=[];reasons={}
 for pid in FORCED:
  if pid in byid:
   selected.append(pid);reasons[pid]="forced regression/known-error representative"
 # Fill with easy points while spreading meridians and anatomy.
 used_mer=collections.Counter(byid[p]["meridian"] for p in selected)
 candidates=sorted((r for r in rows if r["point_id"] not in selected),key=lambda r:(r["hard_unresolved"]>0,-r["resolved_fma_ratio"],r["surface_expression_count"],-r["score"],r["point_id"]))
 for r in candidates:
  if len(selected)>=20:break
  # Prefer no hard blockers and low surface burden; encourage meridian spread.
  if r["hard_unresolved"]>0:continue
  if r["surface_expression_count"]>2:continue
  if r["resolved_fma_ratio"]<0.45:continue
  if used_mer[r["meridian"]]>=2:continue
  selected.append(r["point_id"]);used_mer[r["meridian"]]+=1
  reasons[r["point_id"]]=f"high resolved_fma ratio ({r['resolved_fma_ratio']:.2f}), low surface burden ({r['surface_expression_count']}), no hard unresolved"
 # Relax only if needed.
 for r in candidates:
  if len(selected)>=20:break
  if r["point_id"] in selected or r["hard_unresolved"]>0:continue
  selected.append(r["point_id"]);reasons[r["point_id"]]="fallback easy-case fill after primary criteria"
 out={"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-cohort-discovery","status":"DISCOVERY_ONLY_NOT_FROZEN",
      "forced_points":list(FORCED),"selected":[{**byid[p],"selection_reason":reasons[p]} for p in selected],
      "selection_contract":{"target_count":20,"prefer_resolved_fma":True,"prefer_low_surface_expression":True,"hard_unresolved_preferred_zero":True,"forced_regression_cases":list(FORCED)},
      "all_candidates":rows}
 q=Path(args.out);q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"selected":selected,"forced":list(FORCED),"count":len(selected)}))

if __name__=="__main__":main()
