#!/usr/bin/env python3
"""Build C v3 Stage 1 spatial substrate frames.

Acupoint-independent only. No WHO point IDs, no legacy coordinates and no
exclusive skin-region partition. Every frame records its defining anatomy.
"""
from __future__ import annotations
import argparse,json,math,re
from pathlib import Path
from spatial_core import AtlasStore,nearest_on_part,normalize,dot,vsub,vadd,vmul,distance,sha256_file,cross

def avg(ps):
    if not ps: raise ValueError("cannot average empty points")
    return tuple(sum(p[i] for p in ps)/len(ps) for i in range(3))
def centroid(ps):return avg(ps)
def project_off(v,axes):
    out=v
    for a in axes:out=vsub(out,vmul(a,dot(out,a)))
    return out

def covariance_axis(points,initial=(0.0,1.0,0.0)):
    c=centroid(points);xx=xy=xz=yy=yz=zz=0.0
    for p in points:
        x,y,z=vsub(p,c);xx+=x*x;xy+=x*y;xz+=x*z;yy+=y*y;yz+=y*z;zz+=z*z
    n=max(len(points)-1,1)
    M=((xx/n,xy/n,xz/n),(xy/n,yy/n,yz/n),(xz/n,yz/n,zz/n))
    v=normalize(initial)
    for _ in range(80):
        w=(M[0][0]*v[0]+M[0][1]*v[1]+M[0][2]*v[2],
           M[1][0]*v[0]+M[1][1]*v[1]+M[1][2]*v[2],
           M[2][0]*v[0]+M[2][1]*v[1]+M[2][2]*v[2])
        if dot(w,w)<1e-24:break
        nv=normalize(w)
        if min(distance(nv,v),distance(nv,vmul(v,-1)))<1e-13:v=nv;break
        v=nv
    mv=(M[0][0]*v[0]+M[0][1]*v[1]+M[0][2]*v[2],
        M[1][0]*v[0]+M[1][1]*v[1]+M[1][2]*v[2],
        M[2][0]*v[0]+M[2][1]*v[1]+M[2][2]*v[2])
    lam=dot(v,mv);trace=M[0][0]+M[1][1]+M[2][2]
    return v,c,lam/trace if trace>0 else 0.0

def cap_centroid(points,axis,high,fraction=.08):
    vals=[dot(p,axis) for p in points];lo=min(vals);hi=max(vals)
    cutoff=hi-(hi-lo)*fraction if high else lo+(hi-lo)*fraction
    sel=[p for p,t in zip(points,vals) if t>=cutoff] if high else [p for p,t in zip(points,vals) if t<=cutoff]
    return centroid(sel)

def part_by_exact_name(store,name):
    q=name.lower();m=[p["id"] for p in store.atlas["parts"] if p["name"].strip().lower()==q]
    if len(m)!=1:raise RuntimeError(f"expected exactly one part {name!r}; got {len(m)}")
    return m[0]
def points_for_names(store,names):
    ids=[part_by_exact_name(store,n) for n in names];pts=[]
    for pid in ids:pts.extend(store.vertices(pid))
    return ids,pts
def points_matching(store,predicate):
    ids=[];pts=[]
    for p in store.atlas["parts"]:
        if predicate(p):ids.append(p["id"]);pts.extend(store.vertices(p["id"]))
    return ids,pts
def nearest_point_on_parts(store,ids,p):
    return min((nearest_on_part(store,i,p) for i in ids),key=lambda h:h.distance)

def orthogonal_local(longitudinal,side,global_left,surface_seed):
    long=normalize(longitudinal);sgn=1.0 if side=="left" else -1.0
    outward=normalize(project_off(vmul(global_left,sgn),[long]))
    surface=normalize(project_off(surface_seed,[long,outward]))
    return long,outward,surface

def segment_frame(store,side,label,names,proximal_anchor,distal_anchor,global_left,global_anterior):
    ids,pts=points_for_names(store,names);pca,_,ratio=covariance_axis(pts)
    lo=cap_centroid(pts,pca,False);hi=cap_centroid(pts,pca,True)
    # Resolve PCA sign by the full anatomical chain, never by world Y or distance
    # to a generic trunk origin.
    score_a=distance(lo,proximal_anchor)+distance(hi,distal_anchor)
    score_b=distance(hi,proximal_anchor)+distance(lo,distal_anchor)
    prox,dist=(lo,hi) if score_a<=score_b else (hi,lo)
    long,outward,anterior=orthogonal_local(vsub(dist,prox),side,global_left,global_anterior)
    return {"name":f"{side}_{label}","side":side,"kind":"limb_segment","origin":list(prox),
      "proximal":list(prox),"distal":list(dist),
      "axes":{"proximal_to_distal":list(long),"outward":list(outward),"anterior":list(anterior)},
      "defining_part_ids":ids,
      "method":"PCA long axis; 8% endpoint caps; sign chosen by proximal+distal anatomical chain anchors",
      "anchor_provenance":{"proximal_anchor":list(proximal_anchor),"distal_anchor":list(distal_anchor)},
      "metrics":{"pca_primary_variance_fraction":ratio,"segment_length_m":distance(prox,dist)}},pts

def points_for_hand(store,side):
    tokens=("capitate","hamate","lunate","pisiform","scaphoid","trapezium","trapezoid","triquetral","metacarpal bone")
    return points_matching(store,lambda p:p.get("system")=="skeletal" and p["name"].lower().startswith(side+" ") and any(t in p["name"].lower() for t in tokens))
def points_for_foot(store,side):
    tokens=("talus","calcaneus","metatarsal bone")
    return points_matching(store,lambda p:p.get("system")=="skeletal" and p["name"].lower().startswith(side+" ") and any(t in p["name"].lower() for t in tokens))

def appendage_frame(side,label,ids,pts,proximal_reference,global_left,global_anterior,global_superior):
    center=centroid(pts);long_seed=vsub(center,proximal_reference)
    surface_name="palmar" if label=="hand" else "dorsal"
    surface_seed=global_anterior if label=="hand" else global_superior
    long,outward,surface=orthogonal_local(long_seed,side,global_left,surface_seed)
    proj=[dot(vsub(p,proximal_reference),long) for p in pts];distal=max(proj)
    return {"name":f"{side}_{label}","side":side,"kind":"appendage","origin":list(proximal_reference),
      "proximal":list(proximal_reference),"distal":list(vadd(proximal_reference,vmul(long,distal))),
      "axes":{"proximal_to_distal":list(long),"outward":list(outward),surface_name:list(surface)},
      "defining_part_ids":ids,
      "method":f"proximal joint to skeletal {label} centroid; {surface_name} seed from global {'anterior' if label=='hand' else 'superior'}",
      "metrics":{"segment_length_m":distal}}

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--model-dir",default="public/models");ap.add_argument("--out",default=".tmp/c-v3-stage1/spatial-substrate.json");args=ap.parse_args()
    md=Path(args.model_dir);store=AtlasStore(md)

    # Reference clouds.
    def one(n):return points_for_names(store,[n])
    lh_id,lh=one("Left humerus");rh_id,rh=one("Right humerus")
    lf_id,lf=one("Left femur");rf_id,rf=one("Right femur")
    lc_id,lc=one("Left clavicle");rc_id,rc=one("Right clavicle")
    lhip_id,lhip=one("Left hip bone");rhip_id,rhip=one("Right hip bone")
    sac_id,sac=one("Sacrum");stern_id,stern=one("Body of sternum")
    vert_ids,verts=points_matching(store,lambda p:p.get("system")=="skeletal" and re.search(r"\bvertebra$",p["name"].lower()) is not None)
    if not vert_ids:raise RuntimeError("no vertebral reference meshes")

    # Superior comes from the vertebral column PCA, with sign independently fixed
    # by sacrum -> clavicles. This avoids using a tilted single endpoint vector as
    # the axis itself.
    spine_axis,_,spine_ratio=covariance_axis(verts)
    superior_sign_ref=vsub(avg([centroid(lc),centroid(rc)]),centroid(sac))
    superior=spine_axis if dot(spine_axis,superior_sign_ref)>0 else vmul(spine_axis,-1)

    left_ref=vsub(avg([centroid(lh),centroid(lf),centroid(lc),centroid(lhip)]),avg([centroid(rh),centroid(rf),centroid(rc),centroid(rhip)]))
    left=normalize(project_off(left_ref,[superior]))
    ant_ref=vsub(centroid(stern),centroid(verts))
    anterior=normalize(project_off(ant_ref,[superior,left]))
    # Final orthogonalization, preserving independent reference signs.
    left2=normalize(cross(superior,anterior))
    if dot(left2,left_ref)<0:left2=vmul(left2,-1)
    anterior2=normalize(cross(left2,superior))
    if dot(anterior2,ant_ref)<0:
        anterior2=vmul(anterior2,-1);left2=vmul(left2,-1)
    left,anterior=left2,anterior2
    origin=centroid(sac)

    global_frame={"name":"global_patient","kind":"global","origin":list(origin),
      "axes":{"left":list(left),"superior":list(superior),"anterior":list(anterior)},
      "references":{"left_right":{"left_part_ids":lh_id+lf_id+lc_id+lhip_id,"right_part_ids":rh_id+rf_id+rc_id+rhip_id},
        "superior_inferior":{"spine_part_ids":vert_ids,"sign_upper_part_ids":lc_id+rc_id,"sign_lower_part_ids":sac_id},
        "anterior_posterior":{"anterior_part_ids":stern_id,"posterior_part_ids":vert_ids}},
      "method":"vertebral-column PCA for superior; bilateral skeleton for left; sternum-versus-spine for anterior; sign-preserving orthogonalization",
      "metrics":{"vertebral_pca_primary_variance_fraction":spine_ratio,"left_reference_alignment":dot(left,normalize(project_off(left_ref,[superior]))),
        "superior_sign_alignment":dot(superior,normalize(superior_sign_ref)),"anterior_reference_alignment":dot(anterior,normalize(project_off(ant_ref,[superior,left]))),
        "orthogonality_max_abs_dot":max(abs(dot(left,superior)),abs(dot(left,anterior)),abs(dot(superior,anterior)))}}

    # Chain anchors are independent neighboring skeletal groups.
    refs={}
    for side in ("left","right"):
        cap=side.capitalize()
        _,scap=one(f"{cap} scapula");_,hum=one(f"{cap} humerus");_,rad=one(f"{cap} radius");_,uln=one(f"{cap} ulna")
        _,hip=one(f"{cap} hip bone");_,fem=one(f"{cap} femur");_,tib=one(f"{cap} tibia");_,fib=one(f"{cap} fibula")
        hand_ids,hand_pts=points_for_hand(store,side);foot_ids,foot_pts=points_for_foot(store,side)
        refs[side]={"shoulder":centroid(scap),"humerus":centroid(hum),"forearm":centroid(rad+uln),"hand":centroid(hand_pts),
                    "hip":centroid(hip),"femur":centroid(fem),"leg":centroid(tib+fib),"foot":centroid(foot_pts),
                    "hand_ids":hand_ids,"hand_pts":hand_pts,"foot_ids":foot_ids,"foot_pts":foot_pts}

    frames={}
    for side in ("left","right"):
        cap=side.capitalize();r=refs[side]
        frames[f"{side}_upper_arm"],_=segment_frame(store,side,"upper_arm",[f"{cap} humerus"],r["shoulder"],r["forearm"],left,anterior)
        frames[f"{side}_forearm"],_=segment_frame(store,side,"forearm",[f"{cap} radius",f"{cap} ulna"],r["humerus"],r["hand"],left,anterior)
        frames[f"{side}_thigh"],_=segment_frame(store,side,"thigh",[f"{cap} femur"],r["hip"],r["leg"],left,anterior)
        frames[f"{side}_lower_leg"],_=segment_frame(store,side,"lower_leg",[f"{cap} tibia",f"{cap} fibula"],r["femur"],r["foot"],left,anterior)

    joints={}
    for side in ("left","right"):
        cap=side.capitalize();ua=frames[f"{side}_upper_arm"];fa=frames[f"{side}_forearm"];th=frames[f"{side}_thigh"];ll=frames[f"{side}_lower_leg"]
        scap_ids,_=one(f"{cap} scapula");hip_ids,_=one(f"{cap} hip bone");talus_ids,_=one(f"{cap} talus")
        hand_ids=refs[side]["hand_ids"];hand_pts=refs[side]["hand_pts"];foot_ids=refs[side]["foot_ids"];foot_pts=refs[side]["foot_pts"]
        sh_h=tuple(ua["proximal"]);sh_s=nearest_point_on_parts(store,scap_ids,sh_h).point;shoulder=avg([sh_h,sh_s])
        elbow=avg([tuple(ua["distal"]),tuple(fa["proximal"])])
        wf=tuple(fa["distal"]);wh=nearest_point_on_parts(store,hand_ids,wf).point;wrist=avg([wf,wh])
        hf=tuple(th["proximal"]);hp=nearest_point_on_parts(store,hip_ids,hf).point;hip=avg([hf,hp])
        knee=avg([tuple(th["distal"]),tuple(ll["proximal"])])
        al=tuple(ll["distal"]);at=nearest_point_on_parts(store,talus_ids,al).point;ankle=avg([al,at])
        joints[side]={"shoulder":{"center":list(shoulder),"defining_part_ids":ua["defining_part_ids"]+scap_ids},
          "elbow":{"center":list(elbow),"defining_part_ids":ua["defining_part_ids"]+fa["defining_part_ids"]},
          "wrist":{"center":list(wrist),"defining_part_ids":fa["defining_part_ids"]+hand_ids},
          "hip":{"center":list(hip),"defining_part_ids":th["defining_part_ids"]+hip_ids},
          "knee":{"center":list(knee),"defining_part_ids":th["defining_part_ids"]+ll["defining_part_ids"]},
          "ankle":{"center":list(ankle),"defining_part_ids":ll["defining_part_ids"]+talus_ids}}
        frames[f"{side}_hand"]=appendage_frame(side,"hand",hand_ids,hand_pts,wrist,left,anterior,superior)
        frames[f"{side}_foot"]=appendage_frame(side,"foot",foot_ids,foot_pts,ankle,left,anterior,superior)

    mand_id,mand=one("Mandible")
    frames["trunk"]={"name":"trunk","kind":"axial","origin":list(avg([centroid(stern),centroid(verts)])),
      "axes":{"left":list(left),"superior":list(superior),"anterior":list(anterior)},"defining_part_ids":stern_id+vert_ids+sac_id+lhip_id+rhip_id,
      "method":"inherits independently validated global orientation"}
    frames["head_neck"]={"name":"head_neck","kind":"axial","origin":list(centroid(mand)),
      "axes":{"left":list(left),"superior":list(superior),"anterior":list(anterior)},"defining_part_ids":mand_id+vert_ids,
      "method":"inherits independently validated global orientation"}

    out={"schema_version":"1.0.0","artifact":"c-v3-stage1-spatial-substrate","status":"GENERATED_NOT_VALIDATED","scope":"acupoint-independent spatial substrate only",
      "source":{"atlas_path":str(md/"atlas.json"),"atlas_sha256":sha256_file(md/"atlas.json"),"atlas_version":store.atlas.get("version")},
      "prohibitions":{"legacy_coordinate_input":False,"exclusive_skin_region_partition":False,"acupoint_specific_logic":False},
      "global_frame":global_frame,"frames":frames,"joints":joints,
      "surface_contract":{"skin_part_id":"FJ2810","representation":"component-aware indexed triangle surface","manifold_assumption":False,
        "queries":["nearest_triangle_point","ray_surface_intersection","plane_surface_intersection","triangle_normal","component_membership","mesh-edge geodesic"]}}
    p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"artifact":str(p),"status":out["status"],"frames":len(frames),"joint_sides":len(joints)}))
if __name__=="__main__":main()
