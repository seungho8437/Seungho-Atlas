#!/usr/bin/env python3
"""C v3 Stage 2 ontology census and execution-contract manifest.

Reads the frozen B v2.1 graph and produces a complete semantic inventory.
No coordinates are generated. No legacy C artifact is read.
"""
from __future__ import annotations
import argparse,collections,hashlib,json
from pathlib import Path

EXPECTED_B_SHA256="8126e20938a478a2d214f4a8487cabeebc8f3115f7a81ad30e46b594958fb2c1"
EXPECTED_SOURCE_STATEMENTS=583

HARD_UNRESOLVED={"source_backed_derived_unresolved","ambiguous_generic","parent_unresolved","blocked_by_context"}

def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json")
 ap.add_argument("--out",default=".tmp/c-v3-stage2/semantic-census.json")
 args=ap.parse_args()
 p=Path(args.graph);sha=sha256_file(p)
 if sha!=EXPECTED_B_SHA256: raise SystemExit(f"B v2.1 SHA mismatch: {sha}")
 g=json.loads(p.read_text(encoding="utf-8"))
 if len(g.get("source_statements",[]))!=EXPECTED_SOURCE_STATEMENTS:
  raise SystemExit("B v2.1 source statement count mismatch")

 rel=collections.Counter(x["relation_type"] for x in g["relation_instances"])
 lmcls=collections.Counter(x.get("landmark_class") or "<none>" for x in g["landmark_nodes"])
 disp=collections.Counter(x.get("terminal_disposition") or "<none>" for x in g["landmark_nodes"])
 geom=collections.Counter(x.get("geometry_type") or "<none>" for x in g["geometry_nodes"])
 cond=collections.Counter(x.get("condition_type") or "<none>" for x in g.get("conditions",[]))
 units=collections.Counter(x.get("unit") or "<none>" for x in g.get("proportional_measurements",[]))

 node_by_id={x["node_id"]:x for x in g["landmark_nodes"]}
 pair=collections.Counter()
 hard_rel=[]; special_rel=[]
 for r in g["relation_instances"]:
  rel_args=[node_by_id[a] for a in r.get("argument_node_ids",[]) if a in node_by_id]
  classes=sorted({x.get("landmark_class") or "<none>" for x in rel_args}) or ["<none>"]
  for cls in classes: pair[(r["relation_type"],cls)]+=1
  dispositions={x.get("terminal_disposition") for x in rel_args}
  if dispositions & HARD_UNRESOLVED: hard_rel.append(r["relation_id"])
  if dispositions & {"registry_limited","specialized_anchor"}: special_rel.append(r["relation_id"])

 out={
  "schema_version":"1.0.0","artifact":"c-v3-stage2-semantic-census",
  "status":"CENSUS_COMPLETE_EXECUTION_NOT_VALIDATED",
  "input":{"path":str(p),"sha256":sha,"source_statements":len(g["source_statements"])},
  "counts":{
   "points":len(g["points"]),"landmark_nodes":len(g["landmark_nodes"]),
   "geometry_nodes":len(g["geometry_nodes"]),"relation_instances":len(g["relation_instances"]),
   "conditions":len(g.get("conditions",[])),"proportional_measurements":len(g.get("proportional_measurements",[])),
   "composite_bindings":len(g.get("composite_bindings",[]))
  },
  "relation_types":dict(sorted(rel.items())),
  "landmark_classes":dict(sorted(lmcls.items())),
  "terminal_dispositions":dict(sorted(disp.items())),
  "geometry_types":dict(sorted(geom.items())),
  "condition_types":dict(sorted(cond.items())),
  "measurement_units":dict(sorted(units.items())),
  "relation_x_landmark_class":[{"relation_type":a,"landmark_class":b,"count":n} for (a,b),n in sorted(pair.items(),key=lambda z:(-z[1],z[0]))],
  "risk_inventory":{
    "hard_unresolved_dispositions":sorted(HARD_UNRESOLVED),
    "relation_instances_touching_hard_unresolved":len(set(hard_rel)),
    "relation_instances_touching_registry_limited_or_specialized_anchor":len(set(special_rel))
  },
  "invariants":{
    "legacy_coordinate_input":False,
    "acupoint_specific_patch_input":False,
    "full_graph_census":True
  }
 }
 q=Path(args.out);q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"status":out["status"],**out["counts"],"relation_types":len(rel),"landmark_classes":len(lmcls)}))

if __name__=="__main__":main()
