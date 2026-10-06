#!/usr/bin/env python3
"""Independent G1-C topology audit for BodyParts3D skin.

Does not import the S1 spatial kernel.
"""
from __future__ import annotations
import argparse,json,math,struct,hashlib
from pathlib import Path

def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def sub(a,b):return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def norm2(a):return a[0]*a[0]+a[1]*a[1]+a[2]*a[2]
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for z in iter(lambda:f.read(1<<20),b""):h.update(z)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--model-dir",default="public/models")
 ap.add_argument("--skin-part",default="FJ2810")
 ap.add_argument("--report",default=".tmp/c-v3-s1/g1-c-surface-topology.json")
 args=ap.parse_args()
 md=Path(args.model_dir);atlasp=md/"atlas.json";atlas=json.loads(atlasp.read_text())
 parts={p["id"]:p for p in atlas["parts"]}
 if args.skin_part not in parts: raise SystemExit(f"skin part missing: {args.skin_part}")
 p=parts[args.skin_part];chunkrec=atlas["chunks"][p["chunk"]];raw=(md/Path(chunkrec["url"]).name).read_bytes()
 vals=struct.unpack_from("<"+"f"*(p["vertexCount"]*3),raw,p["positions"])
 vv=[(vals[i],vals[i+1],vals[i+2]) for i in range(0,len(vals),3)]
 ii=struct.unpack_from("<"+"I"*p["indexCount"],raw,p["indices"])
 errors=[]
 def err(code,detail=None):errors.append({"code":code,"detail":detail})
 if p["indexCount"]%3:err("INDEX_COUNT_NOT_MULTIPLE_OF_3",p["indexCount"])
 if any(i>=p["vertexCount"] for i in ii):err("INDEX_OUT_OF_RANGE")
 degenerate=0;edge_use={}
 for k in range(0,len(ii),3):
  i,j,l=ii[k:k+3]
  if len({i,j,l})<3:degenerate+=1;continue
  area2=norm2(cross(sub(vv[j],vv[i]),sub(vv[l],vv[i])))
  if area2<=1e-20:degenerate+=1
  for x,y in ((i,j),(j,l),(l,i)):
   e=(x,y) if x<y else (y,x);edge_use[e]=edge_use.get(e,0)+1
 boundary_edges=sum(n==1 for n in edge_use.values())
 nonmanifold_edges=sum(n>2 for n in edge_use.values())
 if degenerate:err("DEGENERATE_TRIANGLES",degenerate)
 if nonmanifold_edges:err("NONMANIFOLD_EDGES",nonmanifold_edges)
 # Connected components in vertex adjacency.
 adj=[set() for _ in range(p["vertexCount"])]
 for k in range(0,len(ii),3):
  a,b,c=ii[k:k+3];adj[a].update((b,c));adj[b].update((a,c));adj[c].update((a,b))
 seen=set();sizes=[]
 for start in range(len(adj)):
  if start in seen:continue
  stack=[start];seen.add(start);n=0
  while stack:
   x=stack.pop();n+=1
   for y in adj[x]:
    if y not in seen:seen.add(y);stack.append(y)
  sizes.append(n)
 sizes.sort(reverse=True)
 # Multiple components are reported, not automatically rejected: anatomy mesh may intentionally contain them.
 report={
  "schema_version":"1.0.0","gate":"G1-C-topology","status":"PASS" if not errors else "FAIL",
  "independence":"direct binary/topology audit; does not import spatial_core",
  "skin_part_id":args.skin_part,"atlas_sha256":sha(atlasp),
  "vertex_count":p["vertexCount"],"triangle_count":p["indexCount"]//3,
  "unique_edges":len(edge_use),"boundary_edges":boundary_edges,
  "nonmanifold_edges":nonmanifold_edges,"degenerate_triangles":degenerate,
  "connected_components":len(sizes),"component_vertex_counts":sizes,
  "errors":errors,
  "promotion_allowed":False,
  "note":"Topology PASS is necessary but not sufficient. Query round-trip, frame, transition, and human gates remain."
 }
 rp=Path(args.report);rp.parent.mkdir(parents=True,exist_ok=True);rp.write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps({"gate":report["gate"],"status":report["status"],"components":len(sizes),"errors":len(errors)}))
 raise SystemExit(0 if not errors else 1)
if __name__=="__main__":main()
