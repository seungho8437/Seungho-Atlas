#!/usr/bin/env python3
"""Independent Stage 1 visual-view contract validator."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
def dot(a,b):return sum(a[i]*b[i] for i in range(3))
def norm(a):return math.sqrt(dot(a,a))
def neg(a):return [-x for x in a]
def close(a,b,t=1e-12):return max(abs(a[i]-b[i]) for i in range(3))<=t
def main():
 ap=argparse.ArgumentParser();ap.add_argument("contract");ap.add_argument("--report",default=".tmp/c-v3-stage1/review-view-validation.json");args=ap.parse_args()
 c=json.loads(Path(args.contract).read_text());cams=c["cameras"];errors=[];checks=0
 def ck(ok,code,detail=None):
  nonlocal checks;checks+=1
  if not ok:errors.append({"code":code,"detail":detail})
 for name,cam in cams.items():
  for k in ("screen_x","screen_y","depth"):ck(abs(norm(cam[k])-1)<1e-12,"CAMERA_VECTOR_NOT_UNIT",{"view":name,"axis":k})
  ck(abs(dot(cam["screen_x"],cam["screen_y"]))<1e-12,"CAMERA_SCREEN_AXES_NOT_ORTHOGONAL",name)
  ck(abs(dot(cam["screen_x"],cam["depth"]))<1e-12,"CAMERA_X_DEPTH_NOT_ORTHOGONAL",name)
  ck(abs(dot(cam["screen_y"],cam["depth"]))<1e-12,"CAMERA_Y_DEPTH_NOT_ORTHOGONAL",name)
 ck(close(cams["back"]["depth"],neg(cams["front"]["depth"])),"FRONT_BACK_DEPTH_NOT_OPPOSITE")
 ck(close(cams["right"]["depth"],neg(cams["left"]["depth"])),"LEFT_RIGHT_DEPTH_NOT_OPPOSITE")
 ck(close(cams["back"]["screen_x"],neg(cams["front"]["screen_x"])),"FRONT_BACK_SCREEN_X_NOT_MIRRORED")
 ck(close(cams["right"]["screen_x"],neg(cams["left"]["screen_x"])),"LEFT_RIGHT_SCREEN_X_NOT_MIRRORED")
 ck(c["invariants"].get("depth_aware_surface_rendering") is True,"DEPTH_RENDERING_NOT_DECLARED")
 ck(c["invariants"].get("raw_world_xyz_projection") is False,"RAW_WORLD_PROJECTION_FORBIDDEN")
 render=c.get("rendering",{})
 ck(render.get("normal_shading") is True,"NORMAL_SHADING_NOT_DECLARED")
 ck(render.get("depth_cue") is True,"DEPTH_CUE_NOT_DECLARED")
 ck(render.get("wireframe_overlay") is True,"WIREFRAME_NOT_DECLARED")
 ck(render.get("oblique_views") is True,"OBLIQUE_VIEWS_NOT_DECLARED")
 ck(render.get("acupoints_rendered") is False,"ACUPOINTS_MUST_NOT_BE_RENDERED")
 ck("front_oblique" in cams and "back_oblique" in cams,"OBLIQUE_CAMERAS_MISSING")
 status="PASS" if not errors else "FAIL"
 out={"schema_version":"1.0.0","stage":"Stage1","test":"visual-view-contract","status":status,"checks":checks,"errors":errors,
 "note":"Camera/view semantics only; human visual QC remains mandatory."}
 p=Path(args.report);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+"\n")
 print(json.dumps({"status":status,"checks":checks,"errors":len(errors)}));raise SystemExit(0 if status=="PASS" else 1)
if __name__=="__main__":main()
