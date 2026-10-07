#!/usr/bin/env python3
from __future__ import annotations
import math, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from spatial_core import (
    closest_point_on_triangle,barycentric_reconstruct,ray_triangle,
    vsub,distance,triangle_normal
)

def close(a,b,tol=1e-10): return distance(a,b)<=tol

# Synthetic tests are deliberately atlas-independent.
a=(0.0,0.0,0.0); b=(1.0,0.0,0.0); c=(0.0,1.0,0.0)
q,w=closest_point_on_triangle((0.25,0.25,1.0),a,b,c)
assert close(q,(0.25,0.25,0.0))
assert abs(sum(w)-1.0)<1e-12 and all(x>=-1e-12 for x in w)
assert close(barycentric_reconstruct(a,b,c,w),q)
r=ray_triangle((0.25,0.25,1.0),(0.0,0.0,-1.0),a,b,c)
assert r is not None
t,rw=r
assert abs(t-1.0)<1e-12
assert close(barycentric_reconstruct(a,b,c,rw),(0.25,0.25,0.0))
n=triangle_normal(a,b,c)
assert close(n,(0.0,0.0,1.0))
# Outside nearest-point cases.
q2,w2=closest_point_on_triangle((2.0,0.0,0.0),a,b,c)
assert close(q2,b)
q3,w3=closest_point_on_triangle((-1.0,-1.0,0.0),a,b,c)
assert close(q3,a)
print("spatial_core synthetic geometry tests: PASS")
