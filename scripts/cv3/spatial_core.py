#!/usr/bin/env python3
"""C v3 spatial substrate core.

Acupoint-independent geometry only.
No WHO point IDs, no legacy coordinates, no region fallbacks.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence
import json, math, struct, hashlib

Vec3 = tuple[float, float, float]

def vadd(a:Vec3,b:Vec3)->Vec3: return (a[0]+b[0],a[1]+b[1],a[2]+b[2])
def vsub(a:Vec3,b:Vec3)->Vec3: return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def vmul(a:Vec3,s:float)->Vec3: return (a[0]*s,a[1]*s,a[2]*s)
def dot(a:Vec3,b:Vec3)->float: return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a:Vec3,b:Vec3)->Vec3:
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm2(a:Vec3)->float: return dot(a,a)
def norm(a:Vec3)->float: return math.sqrt(norm2(a))
def normalize(a:Vec3)->Vec3:
    n=norm(a)
    if n <= 1e-15: raise ValueError("zero-length vector")
    return vmul(a,1.0/n)
def distance(a:Vec3,b:Vec3)->float: return norm(vsub(a,b))
def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20), b""): h.update(block)
    return h.hexdigest()

@dataclass(frozen=True)
class MeshPartMeta:
    id:str
    name:str
    concept_id:str
    system:str
    chunk:int
    positions:int
    vertex_count:int
    indices:int
    index_count:int
    laterality:Optional[str]
    bounds_min:Vec3
    bounds_max:Vec3

@dataclass(frozen=True)
class TriangleHit:
    part_id:str
    triangle_index:int
    point:Vec3
    barycentric:tuple[float,float,float]
    distance:float

@dataclass(frozen=True)
class RayHit:
    part_id:str
    triangle_index:int
    point:Vec3
    barycentric:tuple[float,float,float]
    t:float

@dataclass(frozen=True)
class PlaneSegment:
    part_id:str
    triangle_index:int
    a:Vec3
    b:Vec3

def infer_laterality(name:str)->Optional[str]:
    s=name.strip().lower()
    left=s.startswith("left ") or s.endswith(" left") or " left " in s
    right=s.startswith("right ") or s.endswith(" right") or " right " in s
    if left and right: return "bilateral"
    if left: return "left"
    if right: return "right"
    return None

class AtlasStore:
    def __init__(self, model_dir:Path):
        self.model_dir=Path(model_dir)
        self.atlas_path=self.model_dir/"atlas.json"
        self.atlas=json.loads(self.atlas_path.read_text(encoding="utf-8"))
        self.parts={p["id"]:p for p in self.atlas["parts"]}
        self.concepts={c["id"]:c for c in self.atlas["concepts"]}
        self.concepts_by_name={c["name"].strip().lower():c for c in self.atlas["concepts"]}
        self._chunks:dict[int,bytes]={}

    def chunk(self,index:int)->bytes:
        if index not in self._chunks:
            rec=self.atlas["chunks"][index]
            path=self.model_dir/Path(rec["url"]).name
            data=path.read_bytes()
            if len(data)!=rec["bytes"]:
                raise ValueError(f"chunk byte count mismatch: {path.name}")
            self._chunks[index]=data
        return self._chunks[index]

    def vertices(self,part_id:str)->tuple[Vec3,...]:
        p=self.parts[part_id]
        raw=self.chunk(p["chunk"])
        vals=struct.unpack_from("<"+"f"*(p["vertexCount"]*3),raw,p["positions"])
        return tuple((float(vals[i]),float(vals[i+1]),float(vals[i+2])) for i in range(0,len(vals),3))

    def indices(self,part_id:str)->tuple[int,...]:
        p=self.parts[part_id]
        raw=self.chunk(p["chunk"])
        vals=struct.unpack_from("<"+"I"*p["indexCount"],raw,p["indices"])
        return tuple(int(x) for x in vals)

    def triangles(self,part_id:str)->Iterator[tuple[int,Vec3,Vec3,Vec3]]:
        vv=self.vertices(part_id); ii=self.indices(part_id)
        for k in range(0,len(ii),3):
            yield k//3, vv[ii[k]], vv[ii[k+1]], vv[ii[k+2]]

    def concept_part_ids(self,concept_id_or_name:str)->tuple[str,...]:
        c=self.concepts.get(concept_id_or_name)
        if c is None: c=self.concepts_by_name.get(concept_id_or_name.strip().lower())
        if c is None: raise KeyError(concept_id_or_name)
        return tuple(c["elements"])

    def metadata(self,part_id:str)->MeshPartMeta:
        p=self.parts[part_id]; vv=self.vertices(part_id)
        lo=tuple(min(v[j] for v in vv) for j in range(3))
        hi=tuple(max(v[j] for v in vv) for j in range(3))
        return MeshPartMeta(
            id=p["id"], name=p["name"], concept_id=p["conceptId"], system=p["system"],
            chunk=p["chunk"], positions=p["positions"], vertex_count=p["vertexCount"],
            indices=p["indices"], index_count=p["indexCount"], laterality=infer_laterality(p["name"]),
            bounds_min=lo, bounds_max=hi
        )

def closest_point_on_triangle(p:Vec3,a:Vec3,b:Vec3,c:Vec3)->tuple[Vec3,tuple[float,float,float]]:
    # Christer Ericson, Real-Time Collision Detection.
    ab=vsub(b,a); ac=vsub(c,a); ap=vsub(p,a)
    d1=dot(ab,ap); d2=dot(ac,ap)
    if d1<=0 and d2<=0: return a,(1.0,0.0,0.0)
    bp=vsub(p,b); d3=dot(ab,bp); d4=dot(ac,bp)
    if d3>=0 and d4<=d3: return b,(0.0,1.0,0.0)
    vc=d1*d4-d3*d2
    if vc<=0 and d1>=0 and d3<=0:
        v=d1/(d1-d3); return vadd(a,vmul(ab,v)),(1-v,v,0.0)
    cp=vsub(p,c); d5=dot(ab,cp); d6=dot(ac,cp)
    if d6>=0 and d5<=d6: return c,(0.0,0.0,1.0)
    vb=d5*d2-d1*d6
    if vb<=0 and d2>=0 and d6<=0:
        w=d2/(d2-d6); return vadd(a,vmul(ac,w)),(1-w,0.0,w)
    va=d3*d6-d5*d4
    if va<=0 and (d4-d3)>=0 and (d5-d6)>=0:
        w=(d4-d3)/((d4-d3)+(d5-d6))
        bc=vsub(c,b); return vadd(b,vmul(bc,w)),(0.0,1-w,w)
    denom=1.0/(va+vb+vc)
    v=vb*denom; w=vc*denom; u=1.0-v-w
    q=vadd(vadd(vmul(a,u),vmul(b,v)),vmul(c,w))
    return q,(u,v,w)

def barycentric_reconstruct(a:Vec3,b:Vec3,c:Vec3,w:Sequence[float])->Vec3:
    return (a[0]*w[0]+b[0]*w[1]+c[0]*w[2],
            a[1]*w[0]+b[1]*w[1]+c[1]*w[2],
            a[2]*w[0]+b[2]*w[1]+c[2]*w[2])

def nearest_on_part(store:AtlasStore,part_id:str,p:Vec3)->TriangleHit:
    best=None
    for ti,a,b,c in store.triangles(part_id):
        q,w=closest_point_on_triangle(p,a,b,c); d=distance(p,q)
        if best is None or d<best.distance:
            best=TriangleHit(part_id,ti,q,w,d)
    if best is None: raise ValueError(f"part has no triangles: {part_id}")
    return best

def ray_triangle(origin:Vec3,direction:Vec3,a:Vec3,b:Vec3,c:Vec3,eps:float=1e-10):
    # Moller-Trumbore.
    e1=vsub(b,a); e2=vsub(c,a); h=cross(direction,e2); det=dot(e1,h)
    if abs(det)<eps: return None
    inv=1.0/det; s=vsub(origin,a); u=inv*dot(s,h)
    if u < -eps or u > 1.0+eps: return None
    q=cross(s,e1); v=inv*dot(direction,q)
    if v < -eps or u+v > 1.0+eps: return None
    t=inv*dot(e2,q)
    if t < -eps: return None
    return t,(1.0-u-v,u,v)

def ray_hits_part(store:AtlasStore,part_id:str,origin:Vec3,direction:Vec3)->list[RayHit]:
    d=normalize(direction); hits=[]
    for ti,a,b,c in store.triangles(part_id):
        r=ray_triangle(origin,d,a,b,c)
        if r is None: continue
        t,w=r; hits.append(RayHit(part_id,ti,vadd(origin,vmul(d,t)),w,t))
    hits.sort(key=lambda x:x.t)
    return hits

def plane_triangle_segments(store:AtlasStore,part_id:str,normal:Vec3,offset:float,eps:float=1e-10)->list[PlaneSegment]:
    n=normalize(normal); out=[]
    for ti,a,b,c in store.triangles(part_id):
        verts=(a,b,c); vals=[dot(n,x)-offset for x in verts]; pts=[]
        for i,j in ((0,1),(1,2),(2,0)):
            vi,vj=vals[i],vals[j]; pi,pj=verts[i],verts[j]
            if abs(vi)<=eps: pts.append(pi)
            if vi*vj < -eps*eps:
                t=vi/(vi-vj); pts.append(vadd(pi,vmul(vsub(pj,pi),t)))
        uniq=[]
        for p in pts:
            if not any(distance(p,q)<=1e-9 for q in uniq): uniq.append(p)
        if len(uniq)>=2: out.append(PlaneSegment(part_id,ti,uniq[0],uniq[1]))
    return out

def triangle_normal(a:Vec3,b:Vec3,c:Vec3)->Vec3:
    return normalize(cross(vsub(b,a),vsub(c,a)))
