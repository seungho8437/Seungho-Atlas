#!/usr/bin/env python3
from __future__ import annotations
import json, math, hashlib, struct
from pathlib import Path
from statistics import median

ROOT=Path(__file__).resolve().parents[1]
ATLAS=ROOT/"public/models/atlas.json"
B=ROOT/"public/knowledge/anatomy-acupoint-relations-v2.1.json"
OUT=Path(__import__("os").environ.get("C_V3_S1_OUT", ROOT/".tmp/c-v3-s1"))
OUT.mkdir(parents=True,exist_ok=True)
EXPECTED_B="8126e20938a478a2d214f4a8487cabeebc8f3115f7a81ad30e46b594958fb2c1"

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(v):
    n=math.sqrt(sum(x*x for x in v))
    return [x/n for x in v] if n else [0.0,0.0,0.0]
def add(a,b): return [a[i]+b[i] for i in range(3)]
def sub(a,b): return [a[i]-b[i] for i in range(3)]
def mul(a,s): return [x*s for x in a]
def dot(a,b): return sum(a[i]*b[i] for i in range(3))
def cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def avg(ps):
    return [sum(p[i] for p in ps)/len(ps) for i in range(3)]
def dist(a,b): return math.sqrt(sum((a[i]-b[i])**2 for i in range(3)))
def seg_dist(p,a,b):
    ab=sub(b,a); d=dot(ab,ab)
    t=dot(sub(p,a),ab)/d if d else 0
    tc=max(0.0,min(1.0,t)); q=add(a,mul(ab,tc))
    return dist(p,q),t,q
def percentile(xs,q):
    if not xs:return 0.0
    ys=sorted(xs); pos=(len(ys)-1)*q; lo=int(pos); hi=min(len(ys)-1,lo+1); f=pos-lo
    return ys[lo]*(1-f)+ys[hi]*f

atlas=json.loads(ATLAS.read_text())
b=json.loads(B.read_text())
b_sha=sha(B)
if b_sha!=EXPECTED_B: raise SystemExit(f"B v2.1 SHA mismatch: {b_sha}")
if len(b.get("source_statements",[]))!=583: raise SystemExit("B v2.1 statement count != 583")
parts={p["id"]:p for p in atlas["parts"]}
concepts={c["name"].lower():c for c in atlas["concepts"]}

def resolve_concept(name):
    c=concepts.get(name.lower())
    if not c: raise KeyError(name)
    return c["elements"]

chunk_cache={}
def chunk_bytes(ci):
    if ci not in chunk_cache:
        chunk_cache[ci]=(ROOT/f"public/models/body-{ci}.bin").read_bytes()
    return chunk_cache[ci]
def part_vertices(pid):
    p=parts[pid]; raw=chunk_bytes(p["chunk"]); off=p["positions"]; n=p["vertexCount"]
    vals=struct.unpack_from("<"+("f"*(n*3)),raw,off)
    return [[vals[i],vals[i+1],vals[i+2]] for i in range(0,len(vals),3)]
def concept_vertices(name):
    out=[]
    for pid in resolve_concept(name): out.extend(part_vertices(pid))
    return out
def endpoint(ps,which,frac=.08):
    ys=[p[1] for p in ps]; lo=min(ys); hi=max(ys); span=max(hi-lo,1e-9)
    if which=="max": sel=[p for p in ps if p[1]>=hi-frac*span]
    else: sel=[p for p in ps if p[1]<=lo+frac*span]
    return avg(sel)

# Direct mesh measurements; no C v1/v2 inputs.
side_data={}
for side in ("left","right"):
    hum=concept_vertices(f"{side} humerus")
    fore=concept_vertices(f"{side} radius")+concept_vertices(f"{side} ulna")
    fem=concept_vertices(f"{side} femur")
    leg=concept_vertices(f"{side} tibia")+concept_vertices(f"{side} fibula")
    shoulder=endpoint(hum,"max")
    elbow=avg([endpoint(hum,"min"),endpoint(fore,"max")])
    wrist=endpoint(fore,"min")
    hip=endpoint(fem,"max")
    knee=avg([endpoint(fem,"min"),endpoint(leg,"max")])
    ankle=endpoint(leg,"min")
    side_data[side]=dict(shoulder=shoulder,elbow=elbow,wrist=wrist,hip=hip,knee=knee,ankle=ankle,
                         humerus_vertices=hum,forearm_vertices=fore,femur_vertices=fem,leg_vertices=leg)

shoulder_mid=avg([side_data["left"]["shoulder"],side_data["right"]["shoulder"]])
hip_mid=avg([side_data["left"]["hip"],side_data["right"]["hip"]])
superior=norm(sub(shoulder_mid,hip_mid))
left_axis=norm(sub(side_data["left"]["shoulder"],side_data["right"]["shoulder"]))
anterior=norm(cross(left_axis,superior))
if anterior[2]<0: anterior=mul(anterior,-1)
left_axis=norm(cross(superior,anterior))
origin=hip_mid

# Skeletal hand/foot envelopes from mesh registry names.
def skeletal_bbox(side,tokens):
    ids=[p["id"] for p in atlas["parts"] if p.get("system")=="skeletal" and p["name"].lower().startswith(side+" ") and any(t in p["name"].lower() for t in tokens)]
    if not ids: raise RuntimeError((side,tokens))
    vs=[]
    for pid in ids: vs.extend(part_vertices(pid))
    lo=[min(v[i] for v in vs) for i in range(3)]; hi=[max(v[i] for v in vs) for i in range(3)]
    return {"part_ids":ids,"min":lo,"max":hi,"center":avg(vs),"vertex_count":len(vs)}
for side in ("left","right"):
    side_data[side]["hand_bbox"]=skeletal_bbox(side,["carpal","metacarpal","phalanx"])
    side_data[side]["foot_bbox"]=skeletal_bbox(side,["tarsal","metatarsal","calcaneus","talus","phalanx"])

# Segment thresholds are mesh-derived: p95 bone radial distance x 2.0.
segments={}
for side in ("left","right"):
    sd=side_data[side]
    specs=[("upper_arm",sd["shoulder"],sd["elbow"],sd["humerus_vertices"]),
           ("forearm",sd["elbow"],sd["wrist"],sd["forearm_vertices"]),
           ("thigh",sd["hip"],sd["knee"],sd["femur_vertices"]),
           ("lower_leg",sd["knee"],sd["ankle"],sd["leg_vertices"])]
    for name,a0,b0,bonevs in specs:
        rs=[seg_dist(v,a0,b0)[0] for v in bonevs]
        r95=percentile(rs,.95)
        segments[f"{side}_{name}"]={"a":a0,"b":b0,"bone_radial_p95_m":r95,"skin_radius_limit_m":2.0*r95}

skin=part_vertices("FJ2810")
regions=["head","neck","trunk","left_upper_arm","right_upper_arm","left_forearm","right_forearm","left_hand","right_hand","left_thigh","right_thigh","left_lower_leg","right_lower_leg","left_foot","right_foot"]
rid={r:i for i,r in enumerate(regions)}

# Neck/head bounds derived from skull/mandible and clavicle registry.
mand=concept_vertices("mandible")
mand_min_y=min(v[1] for v in mand)
clav=concept_vertices("clavicle")
clav_max_y=max(v[1] for v in clav)
neck_lower=clav_max_y
head_lower=mand_min_y

def in_expanded_bbox(p,bb,scale=.22):
    spans=[bb["max"][i]-bb["min"][i] for i in range(3)]
    pad=[max(0.012,spans[i]*scale) for i in range(3)]
    return all(bb["min"][i]-pad[i] <= p[i] <= bb["max"][i]+pad[i] for i in range(3))

labels=[]
counts={r:0 for r in regions}
bounds={r:[[1e9,1e9,1e9],[-1e9,-1e9,-1e9]] for r in regions}
sums={r:[0.0,0.0,0.0] for r in regions}
for p in skin:
    side="left" if dot(sub(p,origin),left_axis)>=0 else "right"
    sd=side_data[side]
    # Hands/feet are explicit skeletal envelopes first.
    if in_expanded_bbox(p,sd["hand_bbox"],.30):
        reg=f"{side}_hand"
    elif in_expanded_bbox(p,sd["foot_bbox"],.28):
        reg=f"{side}_foot"
    else:
        candidates=[]
        for segname in ("upper_arm","forearm","thigh","lower_leg"):
            s=segments[f"{side}_{segname}"]
            d,t,_=seg_dist(p,s["a"],s["b"])
            if -0.08<=t<=1.08 and d<=s["skin_radius_limit_m"]:
                candidates.append((d/s["skin_radius_limit_m"],f"{side}_{segname}"))
        if candidates:
            candidates.sort()
            reg=candidates[0][1]
        elif p[1]>=head_lower:
            reg="head"
        elif p[1]>=neck_lower:
            reg="neck"
        else:
            reg="trunk"
    labels.append(rid[reg]);counts[reg]+=1
    for i in range(3):
        bounds[reg][0][i]=min(bounds[reg][0][i],p[i]);bounds[reg][1][i]=max(bounds[reg][1][i],p[i]);sums[reg][i]+=p[i]

stats={}
for r in regions:
    n=counts[r]; stats[r]={"vertex_count":n,"fraction":n/len(skin),"bounds":bounds[r] if n else None,
                           "centroid":[x/n for x in sums[r]] if n else None}

# Automatic pre-QC, not a substitute for human G1 review.
issues=[]
for r in regions:
    if counts[r]==0: issues.append({"severity":"CRITICAL","class":"EMPTY_REGION","region":r})
for side in ("left","right"):
    sign=1 if side=="left" else -1
    for seg in ("upper_arm","forearm","hand","thigh","lower_leg","foot"):
        reg=f"{side}_{seg}"; ids=[i for i,x in enumerate(labels) if x==rid[reg]]
        if ids:
            wrong=sum(1 for i in ids if sign*dot(sub(skin[i],origin),left_axis)<-0.005)
            rate=wrong/len(ids)
            if rate>.01: issues.append({"severity":"MAJOR","class":"SIDE_CROSSOVER","region":reg,"rate":rate})

body_frame={
 "schema_version":"1.0.0","artifact":"body-frame.json","stage":"C_v3_S1",
 "input_sha256":{"B_v2_1":b_sha,"atlas_json":sha(ATLAS)},
 "model":{"name":atlas["version"],"sex":atlas.get("sex"),"scope":atlas.get("scope"),"unit":"m"},
 "world_axis_confirmation":{"positive_x":"patient_left","positive_y":"superior","positive_z":"anterior"},
 "body_frame":{"origin":origin,"left":left_axis,"superior":superior,"anterior":anterior},
 "joints":{side:{k:v for k,v in side_data[side].items() if k in ("shoulder","elbow","wrist","hip","knee","ankle")} for side in ("left","right")},
 "limb_local_axes":{name:{"proximal":s["a"],"distal":s["b"],"proximal_to_distal":norm(sub(s["b"],s["a"]))} for name,s in segments.items()},
 "pose_measurement":{"description":"standing reference; arms lowered and slightly lateral; elbows near extended; knees extended",
   "shoulder_x":[side_data["right"]["shoulder"][0],side_data["left"]["shoulder"][0]],
   "wrist_x":[side_data["right"]["wrist"][0],side_data["left"]["wrist"][0]],
   "hip_x":[side_data["right"]["hip"][0],side_data["left"]["hip"][0]],
   "ankle_x":[side_data["right"]["ankle"][0],side_data["left"]["ankle"][0]]}
}
skin_regions={
 "schema_version":"1.0.0","artifact":"skin-regions.json","stage":"C_v3_S1","skin_part_id":"FJ2810",
 "input_sha256":{"B_v2_1":b_sha,"atlas_json":sha(ATLAS)},
 "vertex_count":len(skin),"region_registry":{str(i):r for r,i in rid.items()},"region_ids":labels,
 "segmentation_method":{"limbs":"nearest eligible skeletal segment axis; radius limit = 2.0 × bone radial p95; hand/foot use expanded skeletal envelope",
   "head_lower_y_m":head_lower,"neck_lower_y_m":neck_lower,"hand_bbox_pad_fraction":.30,"foot_bbox_pad_fraction":.28,
   "segment_parameters":segments},
 "statistics":stats,"automatic_pre_qc":{"issues":issues,"critical":sum(x["severity"]=="CRITICAL" for x in issues),"major":sum(x["severity"]=="MAJOR" for x in issues)}
}
inputs_lock={
 "schema_version":"1.0.0","artifact":"inputs.lock.json","gate":"G0a",
 "status":"APPROVED","B_v2_1":{"path":str(B.relative_to(ROOT)),"sha256":b_sha,"expected_sha256":EXPECTED_B,"statements":len(b["source_statements"])},
 "BodyParts3D":{"atlas_path":str(ATLAS.relative_to(ROOT)),"sha256":sha(ATLAS),"version":atlas["version"],"sex":atlas.get("sex"),"mesh_input":"public/models/body-*.bin"},
 "forbidden_inputs_used":[],"G0b":{"status":"BLOCKED","reason":"production network access unavailable in prior execution environment; does not block S1-S7"},
 "judgment":"C_V3_G0a_APPROVED"
}

for name,obj in [("inputs.lock.json",inputs_lock),("body-frame.json",body_frame),("skin-regions.json",skin_regions)]:
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")

# Self-contained canvas QC: four orthographic views, no remote dependencies.
sample_step=max(1,len(skin)//12000)
pts=[[skin[i][0],skin[i][1],skin[i][2],labels[i]] for i in range(0,len(skin),sample_step)]
palette=["#6b7280","#a78bfa","#9ca3af","#e11d48","#fb7185","#ea580c","#fdba74","#be123c","#f43f5e","#7c3aed","#a78bfa","#0f766e","#2dd4bf","#0369a1","#38bdf8"]
html=f'''<!doctype html><meta charset="utf-8"><title>C v3 G1 skin region QC</title>
<style>body{{font-family:system-ui;margin:20px;background:#f7f7f8;color:#111}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(320px,1fr));gap:14px}}canvas{{width:100%;height:620px;background:white;border:1px solid #ccc}}.legend{{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}}.chip{{font-size:12px;padding:4px 7px;border-radius:12px;background:white;border:1px solid #ddd}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}</style>
<h1>C v3 · G1 skin-region visual QC</h1><p>Human review required. S2 must not start until this segmentation is accepted.</p>
<div class="legend" id="legend"></div><div class="grid"><canvas id="front" width="700" height="620"></canvas><canvas id="back" width="700" height="620"></canvas><canvas id="left" width="700" height="620"></canvas><canvas id="right" width="700" height="620"></canvas></div>
<script>
const pts={json.dumps(pts,separators=(',',':'))};const regions={json.dumps(regions)};const colors={json.dumps(palette)};
const leg=document.getElementById('legend');regions.forEach((r,i)=>{{const s=document.createElement('span');s.className='chip';s.innerHTML='<b style="color:'+colors[i]+'">●</b> '+r;leg.appendChild(s)}});
function draw(id,mode){{const c=document.getElementById(id),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);x.fillStyle='#111';x.font='16px system-ui';x.fillText(id.toUpperCase(),14,24);
 for(const p of pts){{let a,b;if(mode==='front'){{a=p[0];b=p[1]}}else if(mode==='back'){{a=-p[0];b=p[1]}}else if(mode==='left'){{a=-p[2];b=p[1]}}else{{a=p[2];b=p[1]}}const px=350+a*800,py=600-b*335;x.fillStyle=colors[p[3]];x.fillRect(px,py,2.2,2.2)}}}}
draw('front','front');draw('back','back');draw('left','left');draw('right','right');
</script>'''
(OUT/"skin-regions-review.html").write_text(html)

summary={"gate":"G1","status":"AWAITING_HUMAN_REVIEW","vertex_count":len(skin),"region_counts":counts,
         "automatic_pre_qc":skin_regions["automatic_pre_qc"],"S2_started":False,
         "judgment":"C_V3_G1_PENDING_HUMAN_QC"}
(OUT/"g1-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
print(json.dumps(summary))
