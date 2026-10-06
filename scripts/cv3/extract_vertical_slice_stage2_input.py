#!/usr/bin/env python3
"""Extract exact B v2.1 semantic records for the approved Vertical Slice v1 cohort."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

B_SHA="8126e20938a478a2d214f4a8487cabeebc8f3115f7a81ad30e46b594958fb2c1"
COHORT=("HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26","ST2","ST10","LI18","LI17","BL17","BL23","BL25","BL40","TE20","ST4","TE6","ST9")

def sha256(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json");ap.add_argument("--out",default=".tmp/c-v3-slice/stage2-semantic-input.json");args=ap.parse_args()
 p=Path(args.graph)
 if sha256(p)!=B_SHA:raise SystemExit("B v2.1 SHA mismatch")
 g=json.loads(p.read_text())
 ss={x["source_statement_id"]:x for x in g["source_statements"]}
 out={"schema_version":"1.0.0","artifact":"vertical-slice-v1-stage2-semantic-input","b_sha256":B_SHA,"points":[]}
 for pid in COHORT:
  stm=[x for x in g["source_statements"] if x["point_id"]==pid]
  lm=[x for x in g["landmark_nodes"] if x["point_id"]==pid]
  gids={x["geometry_node_id"] for x in g["geometry_nodes"] if x.get("point_id")==pid}
  ge=[x for x in g["geometry_nodes"] if x.get("point_id")==pid]
  re=[x for x in g["relation_instances"] if x["subject_node_id"].split(":",1)[1]==pid]
  sm={x["source_statement_id"] for x in stm}
  pm=[x for x in g.get("proportional_measurements",[]) if x["source_statement_id"] in sm]
  co=[x for x in g.get("conditions",[]) if x["source_statement_id"] in sm]
  cb=[x for x in g.get("composite_bindings",[]) if x.get("point_id")==pid or x.get("source_statement_id") in sm]
  out["points"].append({"point_id":pid,"source_statements":stm,"landmark_nodes":lm,"geometry_nodes":ge,"relation_instances":re,"proportional_measurements":pm,"conditions":co,"composite_bindings":cb})
 q=Path(args.out);q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"points":len(out["points"]),"landmarks":sum(len(x["landmark_nodes"]) for x in out["points"]),"relations":sum(len(x["relation_instances"]) for x in out["points"]),"measurements":sum(len(x["proportional_measurements"]) for x in out["points"]),"conditions":sum(len(x["conditions"]) for x in out["points"])}))
if __name__=="__main__":main()
