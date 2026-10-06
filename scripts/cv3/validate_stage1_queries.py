#!/usr/bin/env python3
"""Atlas-backed Stage 1 spatial-query validation.

Exercises the implementation on deterministic BodyParts3D skin triangles.
This is an implementation test; independent binary/topology validation is
performed separately by validate_g1_surface_topology.py.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
from spatial_core import AtlasStore,nearest_on_part,ray_hits_part,plane_triangle_segments,triangle_normal,barycentric_reconstruct,surface_components,mesh_edge_geodesic_distance,distance,dot,vadd,vmul

def avg3(a,b,c):return ((a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3,(a[2]+b[2]+c[2])/3)

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--model-dir",default="public/models");ap.add_argument("--substrate",default=".tmp/c-v3-stage1/spatial-substrate.json");ap.add_argument("--report",default=".tmp/c-v3-stage1/stage1-query-validation.json");args=ap.parse_args()
 store=AtlasStore(Path(args.model_dir));sub=json.loads(Path(args.substrate).read_text());pid=sub["surface_contract"]["skin_part_id"]
 tris=list(store.triangles(pid));errors=[];samples=[]
 # Deterministic spread across source triangle order.
 stride=max(1,len(tris)//48)
 selected=[tris[i] for i in range(0,len(tris),stride)][:48]
 for ti,a,b,c in selected:
  center=avg3(a,b,c)
  try:n=triangle_normal(a,b,c)
  except ValueError:
   errors.append({"code":"ZERO_NORMAL","triangle":ti});continue
  eps=5e-5
  probe=vadd(center,vmul(n,eps))
  near=nearest_on_part(store,pid,probe)
  rec=barycentric_reconstruct(a,b,c,(1/3,1/3,1/3))
  if distance(rec,center)>1e-12:errors.append({"code":"BARYCENTER_RECONSTRUCTION","triangle":ti})
  if near.distance>eps*1.05:errors.append({"code":"NEAREST_DISTANCE_TOO_LARGE","triangle":ti,"distance":near.distance})
  rays=ray_hits_part(store,pid,probe,vmul(n,-1))
  if not rays or rays[0].t>eps*1.10:
   errors.append({"code":"RAY_ROUNDTRIP_FAIL","triangle":ti,"first_t":rays[0].t if rays else None})
  samples.append({"triangle":ti,"nearest_triangle":near.triangle_index,"nearest_distance_m":near.distance,"ray_first_t_m":rays[0].t if rays else None})

 # Plane intersection residuals in validated global frame.
 gf=sub["global_frame"];origin=tuple(gf["origin"]);planes=[]
 for name,normal in gf["axes"].items():
  n=tuple(normal);offset=dot(n,origin);segs=plane_triangle_segments(store,pid,n,offset)
  if not segs:errors.append({"code":"EMPTY_PLANE_INTERSECTION","plane":name});continue
  maxres=max(max(abs(dot(n,s.a)-offset),abs(dot(n,s.b)-offset)) for s in segs)
  if maxres>1e-8:errors.append({"code":"PLANE_RESIDUAL","plane":name,"residual":maxres})
  planes.append({"plane":name,"segments":len(segs),"max_residual":maxres})

 labels,components=surface_components(store,pid)
 if len(labels)!=store.parts[pid]["vertexCount"]:errors.append({"code":"COMPONENT_LABEL_COUNT"})
 if sum(len(c) for c in components)!=len(labels):errors.append({"code":"COMPONENT_COVERAGE"})
 # Geodesic invariant on an actual mesh edge.
 ii=store.indices(pid);src,tgt=ii[0],ii[1]
 geo=mesh_edge_geodesic_distance(store,pid,src,tgt,components[labels[src]])
 if geo.status!="RESOLVED":errors.append({"code":"GEODESIC_ADJACENT_EDGE_UNRESOLVED"})
 else:
  eu=distance(store.vertices(pid)[src],store.vertices(pid)[tgt]);gd=geo.candidates[0]
  if gd+1e-10<eu:errors.append({"code":"GEODESIC_LT_EUCLIDEAN","geodesic":gd,"euclidean":eu})
  if gd>eu*1.000001:errors.append({"code":"ADJACENT_EDGE_GEODESIC_NOT_EDGE","geodesic":gd,"edge":eu})

 status="PASS" if not errors else "FAIL"
 out={"schema_version":"1.0.0","stage":"Stage1","test":"atlas-backed-spatial-query-validation","status":status,"skin_part_id":pid,"sample_count":len(samples),"samples":samples,"plane_tests":planes,"component_count":len(components),"component_sizes":sorted([len(c) for c in components],reverse=True),"errors":errors,"promotion_allowed":False}
 p=Path(args.report);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,indent=2)+"\n");print(json.dumps({"status":status,"samples":len(samples),"planes":len(planes),"components":len(components),"errors":len(errors)}));raise SystemExit(0 if status=="PASS" else 1)
if __name__=="__main__":main()
