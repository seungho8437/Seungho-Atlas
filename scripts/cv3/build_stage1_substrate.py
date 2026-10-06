#!/usr/bin/env python3
"""Build C v3 Stage 1 spatial substrate frames.

This stage is acupoint-independent. It derives global/local anatomical frames
from BodyParts3D skeletal geometry and records every defining structure.
Output is GENERATED_NOT_VALIDATED until the independent Stage 1 validators pass.
"""
from __future__ import annotations
import argparse, json, math, re
from pathlib import Path
from spatial_core import AtlasStore, nearest_on_part, normalize, dot, vsub, vadd, vmul, distance, sha256_file

def avg(ps):
    if not ps: raise ValueError("cannot average empty point set")
    return tuple(sum(p[i] for p in ps)/len(ps) for i in range(3))

def centroid(ps): return avg(ps)

def project_off(v, axes):
    out=v
    for a in axes: out=vsub(out,vmul(a,dot(out,a)))
    return out

def covariance_axis(points, initial=(0.0,1.0,0.0)):
    c=centroid(points)
    xx=xy=xz=yy=yz=zz=0.0
    for p in points:
        x,y,z=vsub(p,c)
        xx+=x*x;xy+=x*y;xz+=x*z;yy+=y*y;yz+=y*z;zz+=z*z
    n=max(len(points)-1,1)
    M=((xx/n,xy/n,xz/n),(xy/n,yy/n,yz/n),(xz/n,yz/n,zz/n))
    v=normalize(initial)
    for _ in range(64):
        w=(M[0][0]*v[0]+M[0][1]*v[1]+M[0][2]*v[2],
           M[1][0]*v[0]+M[1][1]*v[1]+M[1][2]*v[2],
           M[2][0]*v[0]+M[2][1]*v[1]+M[2][2]*v[2])
        if sum(x*x for x in w)<1e-24: break
        nv=normalize(w)
        if distance(nv,v)<1e-12 or distance(nv,vmul(v,-1))<1e-12:
            v=nv;break
        v=nv
    lam=dot(v,(M[0][0]*v[0]+M[0][1]*v[1]+M[0][2]*v[2],
               M[1][0]*v[0]+M[1][1]*v[1]+M[1][2]*v[2],
               M[2][0]*v[0]+M[2][1]*v[1]+M[2][2]*v[2]))
    trace=M[0][0]+M[1][1]+M[2][2]
    return v,c,(lam/trace if trace>0 else 0.0)

def cap_centroid(points, axis, high, fraction=.08):
    vals=[dot(p,axis) for p in points]; lo=min(vals); hi=max(vals)
    cutoff=hi-(hi-lo)*fraction if high else lo+(hi-lo)*fraction
    selected=[p for p,t in zip(points,vals) if (t>=cutoff if high else t<=cutoff)]
    return centroid(selected)

def part_by_exact_name(store,name):
    q=name.strip().lower()
    ms=[p for p in store.atlas["parts"] if p["name"].strip().lower()==q]
    if len(ms)!=1: raise RuntimeError(f"expected one part named {name!r}, found {len(ms)}")
    return ms[0]["id"]

def points_for_names(store,names):
    ids=[part_by_exact_name(store,n) for n in names]
    pts=[]
    for pid in ids: pts.extend(store.vertices(pid))
    return ids,pts

def points_matching(store,predicate):
    ids=[];pts=[]
    for p in store.atlas["parts"]:
        if predicate(p):
            ids.append(p["id"]);pts.extend(store.vertices(p["id"]))
    return ids,pts

def skeletal_exact(store,side,bone):
    return points_for_names(store,[f"{side} {bone}"])

def nearest_point_on_parts(store,part_ids,p):
    hits=[nearest_on_part(store,pid,p) for pid in part_ids]
    return min(hits,key=lambda h:h.distance)

def make_orthogonal_axes(longitudinal, global_left, global_anterior, side):
    long=normalize(longitudinal)
    side_sign=1.0 if side=="left" else -1.0
    outward_seed=vmul(global_left,side_sign)
    outward=normalize(project_off(outward_seed,[long]))
    anterior=normalize(project_off(global_anterior,[long,outward]))
    return long,outward,anterior

def segment_frame(store,side,label,names,trunk_origin,global_left,global_anterior):
    ids,pts=points_for_names(store,names)
    pca,center,ratio=covariance_axis(pts)
    lo=cap_centroid(pts,pca,False); hi=cap_centroid(pts,pca,True)
    # Proximal endpoint is the cap closer to the central trunk/pelvis reference.
    if distance(lo,trunk_origin)<=distance(hi,trunk_origin):
        prox,dist=lo,hi
    else:
        prox,dist=hi,lo
    long,outward,anterior=make_orthogonal_axes(vsub(dist,prox),global_left,global_anterior,side)
    return {
        "name":f"{side}_{label}","side":side,"kind":"limb_segment",
        "origin":list(prox),"proximal":list(prox),"distal":list(dist),
        "axes":{"proximal_to_distal":list(long),"outward":list(outward),"anterior":list(anterior)},
        "defining_part_ids":ids,
        "method":"PCA long axis; endpoint caps are 8% projection quantiles; proximal cap chosen by distance to central trunk reference",
        "metrics":{"pca_primary_variance_fraction":ratio,"segment_length_m":distance(prox,dist)}
    }, pts

def points_for_hand(store,side):
    tokens=("capitate","hamate","lunate","pisiform","scaphoid","trapezium","trapezoid","triquetral","metacarpal bone")
    return points_matching(store,lambda p:p.get("system")=="skeletal" and p["name"].lower().startswith(side+" ") and any(t in p["name"].lower() for t in tokens))

def points_for_foot(store,side):
    tokens=("talus","calcaneus","metatarsal bone")
    return points_matching(store,lambda p:p.get("system")=="skeletal" and p["name"].lower().startswith(side+" ") and any(t in p["name"].lower() for t in tokens))

def appendage_frame(side,label,ids,pts,proximal_reference,global_left,global_anterior):
    center=centroid(pts)
    longitudinal=vsub(center,proximal_reference)
    long,outward,anterior=make_orthogonal_axes(longitudinal,global_left,global_anterior,side)
    projections=[dot(vsub(p,proximal_reference),long) for p in pts]
    distal=max(projections)
    return {
        "name":f"{side}_{label}","side":side,"kind":"appendage",
        "origin":list(proximal_reference),
        "proximal":list(proximal_reference),
        "distal":list(vadd(proximal_reference,vmul(long,distal))),
        "axes":{"proximal_to_distal":list(long),"outward":list(outward),"anterior":list(anterior)},
        "defining_part_ids":ids,
        "method":"proximal joint reference to skeletal appendage centroid; distal extent from maximum projection",
        "metrics":{"segment_length_m":distal}
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--model-dir",default="public/models")
    ap.add_argument("--out",default=".tmp/c-v3-stage1/spatial-substrate.json")
    args=ap.parse_args()
    md=Path(args.model_dir);store=AtlasStore(md)

    # Independent bilateral references for left-right direction.
    lh_id,lh=skeletal_exact(store,"left","humerus"); rh_id,rh=skeletal_exact(store,"right","humerus")
    lf_id,lf=skeletal_exact(store,"left","femur"); rf_id,rf=skeletal_exact(store,"right","femur")
    lc_id,lc=skeletal_exact(store,"left","clavicle"); rc_id,rc=skeletal_exact(store,"right","clavicle")
    lhip_id,lhip=points_for_names(store,["Left hip bone"]); rhip_id,rhip=points_for_names(store,["Right hip bone"])
    sac_id,sac=points_for_names(store,["Sacrum"])
    stern_id,stern=points_for_names(store,["Body of sternum"])
    vert_ids,verts=points_matching(store,lambda p:p.get("system")=="skeletal" and re.search(r"\bvertebra$",p["name"].lower()) is not None)
    if not vert_ids: raise RuntimeError("no skeletal vertebral bodies found")

    left_ref=vsub(avg([centroid(lh),centroid(lf),centroid(lc),centroid(lhip)]),
                  avg([centroid(rh),centroid(rf),centroid(rc),centroid(rhip)]))
    left=normalize(left_ref)

    lower_ref=centroid(sac)
    upper_ref=avg([centroid(lc),centroid(rc)])
    superior_seed=project_off(vsub(upper_ref,lower_ref),[left])
    superior=normalize(superior_seed)

    posterior_ref=centroid(verts); anterior_ref=centroid(stern)
    anterior_seed=project_off(vsub(anterior_ref,posterior_ref),[left,superior])
    anterior=normalize(anterior_seed)

    # Re-orthogonalize while preserving all three independently derived signs.
    # left = superior x anterior in this patient coordinate convention.
    from spatial_core import cross
    left2=normalize(cross(superior,anterior))
    if dot(left2,left_ref)<0: left2=vmul(left2,-1)
    anterior2=normalize(cross(left2,superior))
    if dot(anterior2,vsub(anterior_ref,posterior_ref))<0:
        anterior2=vmul(anterior2,-1)
        left2=vmul(left2,-1)
    left=left2; anterior=anterior2

    trunk_origin=centroid(sac)
    global_frame={
        "name":"global_patient","kind":"global","origin":list(trunk_origin),
        "axes":{"left":list(left),"superior":list(superior),"anterior":list(anterior)},
        "references":{
            "left_right":{"left_part_ids":lh_id+lf_id+lc_id+lhip_id,"right_part_ids":rh_id+rf_id+rc_id+rhip_id},
            "superior_inferior":{"upper_part_ids":lc_id+rc_id,"lower_part_ids":sac_id},
            "anterior_posterior":{"anterior_part_ids":stern_id,"posterior_part_ids":vert_ids}
        },
        "method":"three independent skeletal reference vectors followed by sign-preserving Gram-Schmidt orthogonalization",
        "metrics":{
            "left_reference_alignment":dot(left,normalize(left_ref)),
            "superior_reference_alignment":dot(superior,normalize(superior_seed)),
            "anterior_reference_alignment":dot(anterior,normalize(anterior_seed)),
            "orthogonality_max_abs_dot":max(abs(dot(left,superior)),abs(dot(left,anterior)),abs(dot(superior,anterior)))
        }
    }

    segment_defs={
        "left_upper_arm":["Left humerus"],"right_upper_arm":["Right humerus"],
        "left_forearm":["Left radius","Left ulna"],"right_forearm":["Right radius","Right ulna"],
        "left_thigh":["Left femur"],"right_thigh":["Right femur"],
        "left_lower_leg":["Left tibia","Left fibula"],"right_lower_leg":["Right tibia","Right fibula"],
    }
    frames={};clouds={}
    for key,names in segment_defs.items():
        side="left" if key.startswith("left_") else "right"
        label=key[len(side)+1:]
        fr,pts=segment_frame(store,side,label,names,trunk_origin,left,anterior)
        frames[key]=fr;clouds[key]=pts

    # Joint centers use two adjacent anatomical structures where possible.
    joints={}
    for side in ("left","right"):
        ua=frames[f"{side}_upper_arm"]; fa=frames[f"{side}_forearm"]
        th=frames[f"{side}_thigh"]; ll=frames[f"{side}_lower_leg"]

        scap_ids,_=points_for_names(store,[f"{side.capitalize()} scapula"])
        hip_ids,_=points_for_names(store,[f"{side.capitalize()} hip bone"])
        carpal_ids,carpal_pts=points_for_hand(store,side)
        foot_ids,foot_pts=points_for_foot(store,side)
        talus_id,_=points_for_names(store,[f"{side.capitalize()} talus"])

        shoulder_h=tuple(ua["proximal"]); shoulder_s=nearest_point_on_parts(store,scap_ids,shoulder_h).point
        shoulder=avg([shoulder_h,shoulder_s])
        elbow=avg([tuple(ua["distal"]),tuple(fa["proximal"])])
        wrist_fore=tuple(fa["distal"]); wrist_hand=nearest_point_on_parts(store,carpal_ids,wrist_fore).point
        wrist=avg([wrist_fore,wrist_hand])

        hip_f=tuple(th["proximal"]); hip_p=nearest_point_on_parts(store,hip_ids,hip_f).point
        hip=avg([hip_f,hip_p])
        knee=avg([tuple(th["distal"]),tuple(ll["proximal"])])
        ankle_leg=tuple(ll["distal"]); ankle_t=nearest_point_on_parts(store,talus_id,ankle_leg).point
        ankle=avg([ankle_leg,ankle_t])

        joints[side]={
            "shoulder":{"center":list(shoulder),"defining_part_ids":ua["defining_part_ids"]+scap_ids},
            "elbow":{"center":list(elbow),"defining_part_ids":ua["defining_part_ids"]+fa["defining_part_ids"]},
            "wrist":{"center":list(wrist),"defining_part_ids":fa["defining_part_ids"]+carpal_ids},
            "hip":{"center":list(hip),"defining_part_ids":th["defining_part_ids"]+hip_ids},
            "knee":{"center":list(knee),"defining_part_ids":th["defining_part_ids"]+ll["defining_part_ids"]},
            "ankle":{"center":list(ankle),"defining_part_ids":ll["defining_part_ids"]+talus_id},
        }

        frames[f"{side}_hand"]=appendage_frame(side,"hand",carpal_ids,carpal_pts,wrist,left,anterior)
        frames[f"{side}_foot"]=appendage_frame(side,"foot",foot_ids,foot_pts,ankle,left,anterior)

    mand_id,mand=points_for_names(store,["Mandible"])
    frames["trunk"]={
        "name":"trunk","kind":"axial","origin":list(avg([centroid(stern),centroid(verts)])),
        "axes":{"left":list(left),"superior":list(superior),"anterior":list(anterior)},
        "defining_part_ids":stern_id+vert_ids+sac_id+lhip_id+rhip_id,
        "method":"inherits validated global orientation; origin is midpoint of sternum and vertebral centroids"
    }
    frames["head_neck"]={
        "name":"head_neck","kind":"axial","origin":list(centroid(mand)),
        "axes":{"left":list(left),"superior":list(superior),"anterior":list(anterior)},
        "defining_part_ids":mand_id+vert_ids,
        "method":"inherits validated global orientation; origin is mandible centroid"
    }

    out={
        "schema_version":"1.0.0","artifact":"c-v3-stage1-spatial-substrate",
        "status":"GENERATED_NOT_VALIDATED",
        "scope":"acupoint-independent spatial substrate only",
        "source":{"atlas_path":str(md/"atlas.json"),"atlas_sha256":sha256_file(md/"atlas.json"),"atlas_version":store.atlas.get("version")},
        "prohibitions":{"legacy_coordinate_input":False,"exclusive_skin_region_partition":False,"acupoint_specific_logic":False},
        "global_frame":global_frame,"frames":frames,"joints":joints,
        "surface_contract":{
            "skin_part_id":"FJ2810",
            "representation":"component-aware indexed triangle surface",
            "manifold_assumption":False,
            "queries":["nearest_triangle_point","ray_surface_intersection","plane_surface_intersection","triangle_normal","component_membership","mesh-edge geodesic"]
        }
    }
    p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"artifact":str(p),"status":out["status"],"frames":len(frames),"joint_sides":len(joints)}))

if __name__=="__main__":
    main()
