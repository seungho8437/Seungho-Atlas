#!/usr/bin/env python3
"""Profile candidate reference structures for C v3 Stage 1 frame design."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from spatial_core import AtlasStore

KEYWORDS=("humerus","radius","ulna","femur","tibia","fibula","sternum","vertebr","sacrum","pelvis","hip bone","clavicle","scapula","mandible","skull","carpal","metacarpal","tarsal","metatarsal","talus","calcaneus")

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--model-dir",default="public/models");ap.add_argument("--out",default=".tmp/c-v3-stage1/reference-structure-profile.json");args=ap.parse_args()
 s=AtlasStore(Path(args.model_dir));rows=[]
 for c in s.atlas["concepts"]:
  name=c["name"].strip().lower()
  if not any(k in name for k in KEYWORDS):continue
  pts=[]
  for pid in c["elements"]:pts.extend(s.vertices(pid))
  if not pts:continue
  lo=[min(p[i] for p in pts) for i in range(3)];hi=[max(p[i] for p in pts) for i in range(3)];cent=[sum(p[i] for p in pts)/len(pts) for i in range(3)]
  rows.append({"id":c["id"],"name":c["name"],"elements":c["elements"],"vertex_count":len(pts),"bounds":{"min":lo,"max":hi},"centroid":cent})
 out={"schema_version":"1.0.0","artifact":"stage1-reference-structure-profile","status":"DESIGN_PROFILE_ONLY","concepts":rows}
 p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+"\n")
 print(json.dumps({"matching_concepts":len(rows),"out":str(p)}))
if __name__=="__main__":main()
