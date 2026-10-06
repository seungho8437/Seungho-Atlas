#!/usr/bin/env python3
"""Build vertical-slice v1 human-review package.

Creates:
- frozen cohort proposal with selection evidence
- slice-only surface-expression geometry registry DRAFT
- slice-only B/F-cun calibration DRAFT with WHO source locators
- z-buffer review HTML grouped by anatomical region

No registry/calibration entry is executable until human approval.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re
from pathlib import Path
from spatial_core import AtlasStore

B_SHA="8126e20938a478a2d214f4a8487cabeebc8f3115f7a81ad30e46b594958fb2c1"
COHORT=("HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26","ST2","ST10","LI18","LI17","BL17","BL23","BL25","BL40","TE20","ST4","TE6","ST9")
FORCED={"HT7":"known prior C failure: wrist/cardinality","LI4":"user-requested known-error/anchor test","ST1":"user-requested face/soft-tissue test","GB14":"user-requested B-cun/head test","GB23":"known prior C failure: intercostal/midaxillary","LU6":"known prior C failure: forearm line/B-cun","LI7":"known prior C failure: forearm line/cardinality","GB26":"known prior C failure: lateral abdomen/rib/level"}

REGISTRY=[
 {"id":"SR:dorsum_hand","group":"upper_limb","terms":["dorsum of the hand"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"skin over the hand segment whose outward normal has positive component along the frozen hand dorsal axis; restricted distal to the wrist joint and to the hand skeletal envelope","render":"hand_dorsal","required_by":["LI4"]},
 {"id":"SR:anteromedial_wrist","group":"upper_limb","terms":["anteromedial aspect of the wrist"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"wrist-local skin band centered on the wrist joint; intersection of palmar/anterior-facing half with the medial half of the side-specific wrist frame","render":"wrist_anteromedial","required_by":["HT7"]},
 {"id":"SR:palmar_wrist_crease","group":"upper_limb","terms":["palmar wrist crease"],"kind":"surface_line","status":"DRAFT_HUMAN_REVIEW",
  "definition":"skin intersection of a plane perpendicular to the forearm proximal-distal axis through the wrist center, restricted to the palmar/anterior half of the wrist surface","render":"palmar_wrist_crease","required_by":["HT7","LU6"]},
 {"id":"SR:dorsal_wrist_crease","group":"upper_limb","terms":["dorsal wrist crease"],"kind":"surface_line","status":"DRAFT_HUMAN_REVIEW",
  "definition":"skin intersection of a plane perpendicular to the forearm proximal-distal axis through the wrist center, restricted to the dorsal/posterior half of the wrist surface","render":"dorsal_wrist_crease","required_by":["LI7","TE6"]},
 {"id":"SR:anterolateral_forearm","group":"upper_limb","terms":["anterolateral aspect of the forearm"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"forearm-segment skin whose normal is anterior-facing and whose local outward coordinate lies on the lateral half; excludes wrist/elbow joint bands","render":"forearm_anterolateral","required_by":["LU6"]},
 {"id":"SR:posterolateral_forearm","group":"upper_limb","terms":["posterolateral aspect of the forearm"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"forearm-segment skin whose normal is posterior-facing and whose local outward coordinate lies on the lateral half; excludes wrist/elbow joint bands","render":"forearm_posterolateral","required_by":["LI7"]},
 {"id":"SR:posterior_forearm","group":"upper_limb","terms":["posterior aspect of the forearm"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"forearm-segment skin with posterior-facing surface normal in the frozen forearm frame","render":"forearm_posterior","required_by":["TE6"]},
 {"id":"SR:face_region","group":"head_face","terms":["on the face"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"anterior head skin below the supraorbital/head transition and above the mandibular inferior extent; serves only as a scope mask, not as a landmark","render":"face","required_by":["ST1","ST2","ST4"]},
 {"id":"SR:head_region","group":"head_face","terms":["on the head"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"cranial skin superior to the neck transition; serves only as a scope mask","render":"head","required_by":["GB14","TE20"]},
 {"id":"SR:nasolabial_sulcus","group":"head_face","terms":["nasolabial sulcus"],"kind":"surface_line","status":"PROPOSED_UNRESOLVED",
  "definition":"BodyParts3D skin has no explicit nasolabial crease annotation; no silent curvature-derived proxy is accepted in v1 slice","render":"none","required_by":["ST4"]},
 {"id":"SR:lateral_thorax","group":"trunk","terms":["lateral thoracic region"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"lateral-facing trunk skin in the thoracic vertical interval, excluding upper-limb skin","render":"lateral_thorax","required_by":["GB23"]},
 {"id":"SR:midaxillary_line","group":"trunk","terms":["midaxillary line"],"kind":"surface_line","status":"PROPOSED_UNRESOLVED",
  "definition":"requires an axillary-apex anchor and lateral thorax geodesic/plane construction; no global-x extreme substitute is permitted","render":"none","required_by":["GB23"]},
 {"id":"SR:fourth_intercostal_space","group":"trunk","terms":["fourth intercostal space"],"kind":"surface_band","status":"DRAFT_HUMAN_REVIEW",
  "definition":"surface band obtained by projecting the anatomical gap between the fourth and fifth ribs to the lateral thoracic skin along the validated thoracic aspect direction","render":"intercostal4","required_by":["GB23"]},
 {"id":"SR:lateral_abdomen","group":"trunk","terms":["lateral abdomen"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"lateral-facing abdominal skin below the costal thorax and above the pelvic/inguinal transition","render":"lateral_abdomen","required_by":["GB26"]},
 {"id":"SR:anterior_neck","group":"neck","terms":["anterior region of the neck","anterior aspect of the neck"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"neck skin anterior to the cervical axial frame, bounded superiorly by the mandibular region and inferiorly by the clavicular/sternal transition","render":"anterior_neck","required_by":["ST10","LI18","LI17","ST9"]},
 {"id":"SR:posterior_median_line","group":"back","terms":["posterior median line"],"kind":"surface_line","status":"DRAFT_HUMAN_REVIEW",
  "definition":"posterior skin curve constrained to the patient midsagittal plane and posterior-facing surface, following connected skin components of the trunk","render":"posterior_median","required_by":["BL17","BL23","BL25"]},
 {"id":"SR:upper_back","group":"back","terms":["upper back region"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"posterior-facing trunk skin over the thoracic axial interval","render":"upper_back","required_by":["BL17"]},
 {"id":"SR:lumbar_region","group":"back","terms":["lumbar region"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"posterior-facing trunk skin over the lumbar vertebral interval","render":"lumbar","required_by":["BL23","BL25"]},
 {"id":"SR:posterior_knee","group":"lower_limb","terms":["posterior aspect of the knee"],"kind":"surface_region","status":"DRAFT_HUMAN_REVIEW",
  "definition":"knee-local skin band centered on the knee joint with posterior-facing surface normal","render":"posterior_knee","required_by":["BL40"]},
 {"id":"SR:popliteal_crease","group":"lower_limb","terms":["popliteal crease"],"kind":"surface_line","status":"DRAFT_HUMAN_REVIEW",
  "definition":"posterior-half skin intersection of the transverse plane through the knee joint center, perpendicular to the adjacent limb long axis","render":"popliteal_crease","required_by":["BL40"]},
 {"id":"SR:radius_ulna_interosseous_space","group":"upper_limb","terms":["interosseous space between the radius and the ulna"],"kind":"deep_space","status":"DRAFT_HUMAN_REVIEW",
  "definition":"3D gap locus between radius and ulna meshes within the forearm frame; midpoint is defined from paired nearest bone surfaces at the queried longitudinal station","render":"forearm_interosseous","required_by":["TE6"]}
]

def sha256(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json");ap.add_argument("--model-dir",default="public/models");ap.add_argument("--substrate",default=".tmp/c-v3-slice/spatial-substrate.json");ap.add_argument("--out-dir",default=".tmp/c-v3-slice/review");args=ap.parse_args()
 gp=Path(args.graph)
 if sha256(gp)!=B_SHA: raise SystemExit("B v2.1 SHA mismatch")
 g=json.loads(gp.read_text());out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
 sid={s["source_statement_id"]:s for s in g["source_statements"]}
 bypoint={p:{"landmarks":[],"relations":[],"measurements":[],"conditions":[],"statements":[]} for p in COHORT}
 for s in g["source_statements"]:
  if s["point_id"] in bypoint:bypoint[s["point_id"]]["statements"].append(s)
 for x in g["landmark_nodes"]:
  if x["point_id"] in bypoint:bypoint[x["point_id"]]["landmarks"].append(x)
 for r in g["relation_instances"]:
  p=r["subject_node_id"].split(":",1)[1]
  if p in bypoint:bypoint[p]["relations"].append(r)
 for m in g.get("proportional_measurements",[]):
  p=sid[m["source_statement_id"]]["point_id"]
  if p in bypoint:bypoint[p]["measurements"].append(m)
 for c in g.get("conditions",[]):
  p=sid[c["source_statement_id"]]["point_id"]
  if p in bypoint:bypoint[p]["conditions"].append(c)

 cohort=[]
 for p in COHORT:
  x=bypoint[p];disp={}
  for n in x["landmarks"]:disp[n.get("terminal_disposition","<none>")]=disp.get(n.get("terminal_disposition","<none>"),0)+1
  reason=FORCED.get(p)
  if reason is None:
   resolved=disp.get("resolved_fma",0);total=max(1,len(x["landmarks"]))
   reason=f"pilot fill: resolved_fma {resolved}/{total}; selected for low/overlapping surface-registry burden and family coverage"
  cohort.append({"point_id":p,"selection_reason":reason,"terminal_dispositions":disp,
    "relation_types":sorted({r["relation_type"] for r in x["relations"]}),
    "measurement_count":len(x["measurements"]),"condition_count":len(x["conditions"]),
    "source_statements":[{"id":s["source_statement_id"],"section":s.get("section"),"page":s.get("page") or s.get("source_page") or s.get("pdf_page"),"text":s.get("text_canonical")} for s in x["statements"]]})
 json.dump({"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-cohort","status":"FROZEN_FOR_PILOT","points":cohort},open(out/"cohort.json","w"),ensure_ascii=False,indent=2)

 registry={"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-surface-registry","status":"DRAFT_AWAITING_HUMAN_REVIEW","entries":REGISTRY,
  "rule":"Only ACCEPTED entries may execute. PROPOSED_UNRESOLVED stays UNRESOLVED. Rejected entries are not substituted."}
 json.dump(registry,open(out/"surface-registry-draft.json","w"),ensure_ascii=False,indent=2)

 calibration=[]
 for p in COHORT:
  for m in bypoint[p]["measurements"]:
   s=sid[m["source_statement_id"]]
   calibration.append({"calibration_id":m["measurement_id"],"point_id":p,"unit_raw":m.get("unit"),"value":m.get("value"),"direction":m.get("direction"),
    "anchor_landmark_id":m.get("anchor_landmark_id"),"branch_id":m.get("branch_id"),
    "who_citation":{"document":"WHO Standard Acupuncture Point Locations in the Western Pacific Region","edition":"Updated and Reprinted 2009 (project primary PDF)","page":s.get("page") or s.get("source_page") or s.get("pdf_page"),"source_statement_id":s["source_statement_id"],"section":s.get("section"),"source_text":s.get("text_canonical"),"measurement_span":m.get("source_value_span") or m.get("cue_span")},
    "calibration_status":"DRAFT_AWAITING_HUMAN_FREEZE"})
 json.dump({"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-calibration","status":"DRAFT_AWAITING_HUMAN_REVIEW","rows":calibration,
   "normalization_rule":"F-cun/f-cun normalize to F-cun for execution while preserving source spelling in trace."},open(out/"calibration-draft.json","w"),ensure_ascii=False,indent=2)

 # Visual review: z-buffer surface plus rule overlays. Exact solver geometry is NOT produced here.
 sub=json.loads(Path(args.substrate).read_text());store=AtlasStore(Path(args.model_dir));pid=sub["surface_contract"]["skin_part_id"]
 verts=[list(v) for v in store.vertices(pid)];inds=list(store.indices(pid));gf=sub["global_frame"]
 review_specs={e["id"]:e for e in REGISTRY}
 html=f'''<!doctype html><meta charset="utf-8"><title>C v3 vertical slice registry review</title>
<style>body{{font-family:system-ui;margin:18px;background:#f5f6f7;color:#111}}section{{background:#fff;border:1px solid #ccc;margin:16px 0;padding:14px}}canvas{{width:100%;max-width:760px;height:620px;border:1px solid #bbb}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px;vertical-align:top}}.unresolved{{background:#fff3cd}}.draft{{background:#eef6ff}}code{{white-space:pre-wrap}}</style>
<h1>C v3 · Vertical Slice v1 · Surface Registry Human Review</h1>
<p>These are DRAFT definitions only. No highlighted geometry is solver-approved until the reviewer accepts it. Yellow entries intentionally propose UNRESOLVED rather than a silent proxy.</p>
<div id="app"></div>
<script>
const verts={json.dumps(verts,separators=(',',':'))}, inds={json.dumps(inds,separators=(',',':'))};
const origin={json.dumps(gf["origin"])}, basis={{left:{json.dumps(gf["axes"]["left"])},superior:{json.dumps(gf["axes"]["superior"])},anterior:{json.dumps(gf["axes"]["anterior"])}}};
const entries={json.dumps(REGISTRY,ensure_ascii=False,separators=(',',':'))};
const sub={json.dumps({"frames":sub["frames"],"joints":sub["joints"]},separators=(',',':'))};
function dot(a,b){{return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]}} function sub3(a,b){{return [a[0]-b[0],a[1]-b[1],a[2]-b[2]]}}
function cross(a,b){{return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]}} function norm(a){{return Math.hypot(...a)}} function unit(a){{let n=norm(a)||1;return a.map(x=>x/n)}}
function patient(p){{let r=sub3(p,origin);return [dot(r,basis.left),dot(r,basis.superior),dot(r,basis.anterior)]}} const pv=verts.map(patient);
function Pworld(p){{return patient(p)}} function near(a,b,r){{return norm(sub3(a,b))<=r}}
function mask(id,q,n){{
 const y=q[1],x=q[0],z=q[2];
 if(id==='SR:face_region') return y>0.55&&y<0.75&&z>0.02;
 if(id==='SR:head_region') return y>0.62;
 if(id==='SR:lateral_thorax') return y>0.32&&y<0.58&&Math.abs(x)>0.09;
 if(id==='SR:lateral_abdomen') return y>0.05&&y<0.34&&Math.abs(x)>0.08;
 if(id==='SR:anterior_neck') return y>0.48&&y<0.66&&z>0.015;
 if(id==='SR:upper_back') return y>0.30&&y<0.58&&z<0;
 if(id==='SR:lumbar_region') return y>0.10&&y<0.34&&z<0;
 if(id==='SR:posterior_median_line') return Math.abs(x)<0.006&&z<0&&y>0.05&&y<0.62;
 let side=x>=0?'left':'right',J=sub.joints[side]||sub.joints.left;
 if(id==='SR:posterior_knee'||id==='SR:popliteal_crease'){{let k=Pworld(J.knee.center);return near(q,k,id.endsWith('crease')?0.035:0.075)&&z<k[2];}}
 if(id.includes('wrist_crease')||id==='SR:anteromedial_wrist'){{let w=Pworld(J.wrist.center); if(!near(q,w,0.075))return false; if(id==='SR:anteromedial_wrist')return z>w[2]&&Math.abs(x)<Math.abs(w[0])+0.04; return id.includes('palmar')?z>w[2]:z<w[2];}}
 if(id.includes('forearm')){{let e=Pworld(J.elbow.center),w=Pworld(J.wrist.center);let miny=Math.min(e[1],w[1])+0.03,maxy=Math.max(e[1],w[1])-0.03;if(y<miny||y>maxy)return false; if(id==='SR:forearm_anterolateral')return z>0&&Math.abs(x)>0.10;if(id==='SR:forearm_posterolateral')return z<0&&Math.abs(x)>0.10;return z<0;}}
 if(id==='SR:dorsum_hand'){{let w=Pworld(J.wrist.center);return y<w[1]+0.03&&y>w[1]-0.16&&z<w[2];}}
 return false;
}}
function render(canvas,id){{
 const c=canvas,ctx=c.getContext('2d'),W=c.width,H=c.height,cam={{sx:[-1,0,0],sy:[0,1,0],d:[0,0,1]}};
 const pr=pv.map(q=>[dot(q,cam.sx),dot(q,cam.sy),dot(q,cam.d)]);let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9,zmin=1e9,zmax=-1e9;
 for(const q of pr){{xmin=Math.min(xmin,q[0]);xmax=Math.max(xmax,q[0]);ymin=Math.min(ymin,q[1]);ymax=Math.max(ymax,q[1]);zmin=Math.min(zmin,q[2]);zmax=Math.max(zmax,q[2])}}
 let sc=Math.min((W-50)/(xmax-xmin),(H-50)/(ymax-ymin)),X=x=>W/2+(x-(xmin+xmax)/2)*sc,Y=y=>H/2-(y-(ymin+ymax)/2)*sc;
 let zb=new Float64Array(W*H);zb.fill(-Infinity),col=new Uint8Array(W*H);col.fill(235),hi=new Uint8Array(W*H);
 function edge(ax,ay,bx,by,px,py){{return (px-ax)*(by-ay)-(py-ay)*(bx-ax)}}
 for(let k=0;k<inds.length;k+=3){{let ia=inds[k],ib=inds[k+1],ic=inds[k+2],a=pr[ia],b=pr[ib],d=pr[ic],ax=X(a[0]),ay=Y(a[1]),bx=X(b[0]),by=Y(b[1]),cx=X(d[0]),cy=Y(d[1]),A=edge(ax,ay,bx,by,cx,cy);if(Math.abs(A)<1e-9)continue;
  let n=unit(cross(sub3(pv[ib],pv[ia]),sub3(pv[ic],pv[ia]))),cent=[(pv[ia][0]+pv[ib][0]+pv[ic][0])/3,(pv[ia][1]+pv[ib][1]+pv[ic][1])/3,(pv[ia][2]+pv[ib][2]+pv[ic][2])/3],mh=mask(id,cent,n);
  for(let py=Math.max(0,Math.floor(Math.min(ay,by,cy)));py<=Math.min(H-1,Math.ceil(Math.max(ay,by,cy)));py++)for(let px=Math.max(0,Math.floor(Math.min(ax,bx,cx)));px<=Math.min(W-1,Math.ceil(Math.max(ax,bx,cx)));px++){{let sx=px+.5,sy=py+.5,w0=edge(bx,by,cx,cy,sx,sy)/A,w1=edge(cx,cy,ax,ay,sx,sy)/A,w2=edge(ax,ay,bx,by,sx,sy)/A;if(w0<0||w1<0||w2<0)continue;let z=w0*a[2]+w1*b[2]+w2*d[2],ii=py*W+px;if(z<=zb[ii])continue;zb[ii]=z;col[ii]=Math.round(150+75*Math.abs(dot(n,cam.d)));hi[ii]=mh?1:0;}}
 }}
 let im=ctx.createImageData(W,H);for(let i=0;i<W*H;i++){{let o=i*4;if(zb[i]===-Infinity){{im.data[o]=im.data[o+1]=im.data[o+2]=255;im.data[o+3]=255;continue}}if(hi[i]){{im.data[o]=210;im.data[o+1]=70;im.data[o+2]=55}}else{{im.data[o]=im.data[o+1]=im.data[o+2]=col[i]}}im.data[o+3]=255}}ctx.putImageData(im,0,0);
}}
const groups={{}};for(const e of entries)(groups[e.group]??=[]).push(e);const app=document.getElementById('app');
for(const [g,es] of Object.entries(groups)){{let sec=document.createElement('section');sec.innerHTML='<h2>'+g+'</h2>';for(const e of es){{let box=document.createElement('div');box.className=e.status.includes('UNRESOLVED')?'unresolved':'draft';box.style.padding='10px';box.style.margin='10px 0';box.innerHTML='<h3>'+e.id+'</h3><p><b>WHO term:</b> '+e.terms.join(' / ')+'</p><p><b>Definition:</b> '+e.definition+'</p><p><b>Required by:</b> '+e.required_by.join(', ')+'</p><p><b>Status:</b> '+e.status+'</p><p>☐ anatomical scope correct ☐ side/aspect correct ☐ extent correct ☐ line/crease placement correct ☐ ambiguity acceptable ☐ ACCEPT ☐ REJECT ☐ KEEP UNRESOLVED</p>';if(e.render!=='none'){{let cv=document.createElement('canvas');cv.width=700;cv.height=620;box.appendChild(cv);setTimeout(()=>render(cv,e.id),0)}}sec.appendChild(box)}}app.appendChild(sec)}}
</script>'''
 (out/"surface-registry-review.html").write_text(html,encoding="utf-8")
 print(json.dumps({"cohort":list(COHORT),"registry_entries":len(REGISTRY),"calibration_rows":len(calibration),"out_dir":str(out)}))

if __name__=="__main__":main()
