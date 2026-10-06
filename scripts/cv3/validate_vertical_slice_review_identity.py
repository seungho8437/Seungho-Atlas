#!/usr/bin/env python3
"""Validate Vertical Slice v1 registry review/solver identity.

The review payload must be byte-for-byte equivalent at the selected skin-vertex
set level to the shared geometry executor used by the pilot solver.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from spatial_core import AtlasStore
from slice_surface_registry import REGISTRY, execute_all

def vhash(xs):
 return hashlib.sha256(",".join(map(str,sorted(set(xs)))).encode()).hexdigest()

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--model-dir",default="public/models")
 ap.add_argument("--substrate",default=".tmp/c-v3-slice/spatial-substrate.json")
 ap.add_argument("--payload",default=".tmp/c-v3-slice/review/registry-geometry-payload.json")
 ap.add_argument("--html",default=".tmp/c-v3-slice/review/surface-registry-review.html")
 ap.add_argument("--out",default=".tmp/c-v3-slice/review/review-identity-validation.json")
 args=ap.parse_args()
 sub=json.loads(Path(args.substrate).read_text());store=AtlasStore(Path(args.model_dir))
 expected=execute_all(store,sub);payload=json.loads(Path(args.payload).read_text())["entries"];html=Path(args.html).read_text()
 errors=[];checks=0
 def ck(ok,code,detail=None):
  nonlocal checks;checks+=1
  if not ok:errors.append({"code":code,"detail":detail})
 ck("function mask(" not in html,"HTML_ANATOMICAL_MASK_LOGIC_FORBIDDEN")
 ck("slice_surface_registry.py" in html,"SHARED_EXECUTOR_DISCLOSURE_MISSING")
 for spec in REGISTRY:
  rid=spec["id"];ck(rid in payload,"MISSING_REVIEW_ENTRY",rid)
  if rid not in payload:continue
  got=payload[rid];exp=expected[rid]
  eh=exp.vertex_hash();gh=vhash(got["surface_vertex_indices"])
  ck(got["solver_vertex_hash"]==eh,"SOLVER_HASH_MISMATCH",rid)
  ck(gh==eh,"SCREEN_VERTEX_SET_HASH_MISMATCH",rid)
  ck(got["status"]==exp.status,"STATUS_MISMATCH",rid)
  ck(got["geometry_hash"]==exp.geometry_hash(),"GEOMETRY_HASH_MISMATCH",rid)
  if spec["status"]!="PROPOSED_UNRESOLVED":
   ck(exp.status=="RESOLVED","DRAFT_ENTRY_EMPTY_OR_UNRESOLVED",rid)
  if spec["kind"]=="surface_line" and rid!="SR:nasolabial_sulcus":
   ck(bool(exp.curves),"LINE_HAS_NO_CURVE",rid)
  if rid in ("SR:palmar_wrist_crease","SR:dorsal_wrist_crease"):
   labs=[m["label"].lower() for m in exp.markers]
   ck(any("pisiform" in x for x in labs),"PISIFORM_MARKER_MISSING",rid)
   ck(any("ulna" in x for x in labs),"ULNAR_REFERENCE_MARKER_MISSING",rid)
  if rid in ("SR:lateral_thorax","SR:midaxillary_line","SR:fourth_intercostal_space","SR:lateral_abdomen","SR:upper_back","SR:lumbar_region","SR:posterior_median_line"):
   ck(bool(exp.hidden_surface_vertex_indices),"UPPER_LIMB_HIDE_SET_MISSING",rid)
  if rid=="SR:radius_ulna_interosseous_space":
   ck(len(exp.deep_points)>=8,"INTEROSSEOUS_3D_PATH_TOO_SHORT",len(exp.deep_points))
  if rid=="SR:fourth_intercostal_space":
   labs=[m["label"].lower() for m in exp.markers]
   ck(any("4th rib" in x for x in labs) and any("5th rib" in x for x in labs),"RIB_ANCHORS_MISSING",labs)
 status="PASS" if not errors else "FAIL"
 out={"schema_version":"1.0.0","test":"vertical-slice-review-solver-geometry-identity","status":status,"checks":checks,"errors":errors,
      "contract":"Review surface vertex sets and solver surface vertex sets must have identical SHA-256; review HTML may not define anatomical masks."}
 p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+"\n")
 print(json.dumps({"status":status,"checks":checks,"errors":len(errors),"error_details":errors}));raise SystemExit(0 if status=="PASS" else 1)
if __name__=="__main__":main()
