#!/usr/bin/env python3
"""Build Vertical Slice v1 human-review package.

Important: the review UI has NO anatomical mask logic.  It renders geometry
precomputed by slice_surface_registry.py, which is the same executor imported by
the pilot solver.  Review-mask / solver-mask identity is hash-checked separately.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from spatial_core import AtlasStore
from slice_surface_registry import REGISTRY, execute_all

B_SHA="8126e20938a478a2d214f4a8487cabeebc8f3115f7a81ad30e46b594958fb2c1"
COHORT=("HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26","ST2","ST10","LI18","LI17","BL17","BL23","BL25","BL40","TE20","ST4","TE6","ST9")
FORCED={"HT7":"known prior C failure: wrist/cardinality","LI4":"user-requested known-error/anchor test","ST1":"user-requested face/soft-tissue test","GB14":"user-requested B-cun/head test","GB23":"known prior C failure: intercostal/midaxillary","LU6":"known prior C failure: forearm line/B-cun","LI7":"known prior C failure: forearm line/cardinality","GB26":"known prior C failure: lateral abdomen/rib/level"}

WHO_PDF_PAGE={
 "S:GB14:location":187,"S:GB23:location":192,
 "S:LU6:location":37,"S:LU6:note:1":37,
 "S:LI7:location":46,"S:BL17:location":117,
 "S:BL23:location":120,"S:BL25:location":121,
 "S:ST4:location":56,"S:TE6:location":169,"S:TE6:note:1":169,
}

def sha256(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def serialize_geom(g):
 return {
  "registry_id":g.registry_id,"status":g.status,
  "surface_vertex_indices":g.surface_vertex_indices,
  "solver_vertex_hash":g.vertex_hash(),
  "geometry_hash":g.geometry_hash(),
  "curves":[[[float(x) for x in p] for p in c] for c in g.curves],
  "markers":g.markers,
  "deep_points":[[float(x) for x in p] for p in g.deep_points],
  "hidden_surface_vertex_indices":g.hidden_surface_vertex_indices,
  "view":g.view,"notes":g.notes
 }

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json")
 ap.add_argument("--model-dir",default="public/models")
 ap.add_argument("--substrate",default=".tmp/c-v3-slice/spatial-substrate.json")
 ap.add_argument("--out-dir",default=".tmp/c-v3-slice/review")
 args=ap.parse_args()
 gp=Path(args.graph)
 if sha256(gp)!=B_SHA:raise SystemExit("B v2.1 SHA mismatch")
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
   reason=f"pilot fill: resolved_fma {resolved}/{total}; low/overlapping surface-registry burden and family coverage"
  cohort.append({"point_id":p,"selection_reason":reason,"terminal_dispositions":disp,
   "relation_types":sorted({r["relation_type"] for r in x["relations"]}),
   "measurement_count":len(x["measurements"]),"condition_count":len(x["conditions"]),
   "source_statements":[{"id":s["source_statement_id"],"section":s.get("section"),"page":s.get("page") or s.get("source_page") or s.get("pdf_page"),"text":s.get("text_canonical")} for s in x["statements"]]})
 (out/"cohort.json").write_text(json.dumps({"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-cohort","status":"FROZEN_FOR_PILOT","points":cohort},ensure_ascii=False,indent=2)+"\n")

 registry={"schema_version":"2.0.0","artifact":"c-v3-vertical-slice-v1-surface-registry","status":"DRAFT_AWAITING_HUMAN_REVIEW",
   "geometry_executor":"scripts/cv3/slice_surface_registry.py","entries":REGISTRY,
   "rule":"Only ACCEPTED entries may execute; review UI may not define substitute masks."}
 (out/"surface-registry-draft.json").write_text(json.dumps(registry,ensure_ascii=False,indent=2)+"\n")

 calibration=[]
 for p in COHORT:
  for m in bypoint[p]["measurements"]:
   s=sid[m["source_statement_id"]]
   calibration.append({"calibration_id":m["measurement_id"],"point_id":p,"unit_raw":m.get("unit"),"value":m.get("value"),"direction":m.get("direction"),
    "anchor_landmark_id":m.get("anchor_landmark_id"),"branch_id":m.get("branch_id"),
    "who_citation":{"document":"WHO Standard Acupuncture Point Locations in the Western Pacific Region","edition":"Updated and Reprinted 2009 (project primary PDF)",
     "pdf_page":WHO_PDF_PAGE.get(s["source_statement_id"]),"page_basis":"1-indexed project primary PDF page; directly verified",
     "source_statement_id":s["source_statement_id"],"section":s.get("section"),"source_text":s.get("text_canonical"),
     "measurement_span":m.get("source_value_span") or m.get("cue_span")},
    "calibration_status":"DRAFT_AWAITING_HUMAN_FREEZE" if WHO_PDF_PAGE.get(s["source_statement_id"]) else "BLOCKED_MISSING_WHO_PAGE"})
 (out/"calibration-draft.json").write_text(json.dumps({"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-calibration",
  "status":"DRAFT_AWAITING_HUMAN_REVIEW","rows":calibration,
  "normalization_rule":"F-cun/f-cun normalize to F-cun for execution while preserving source spelling in trace."},ensure_ascii=False,indent=2)+"\n")

 sub=json.loads(Path(args.substrate).read_text());store=AtlasStore(Path(args.model_dir));skin_id=sub["surface_contract"]["skin_part_id"]
 verts=[list(v) for v in store.vertices(skin_id)];inds=list(store.indices(skin_id))
 results=execute_all(store,sub)
 payload={e["id"]:serialize_geom(results[e["id"]]) for e in REGISTRY}
 (out/"registry-geometry-payload.json").write_text(json.dumps({"schema_version":"1.0.0","executor":"slice_surface_registry.py","entries":payload},ensure_ascii=False,indent=2)+"\n")

 gf=sub["global_frame"];origin=gf["origin"];basis={"left":gf["axes"]["left"],"superior":gf["axes"]["superior"],"anterior":gf["axes"]["anterior"]}
 specs={e["id"]:e for e in REGISTRY}
 html=f'''<!doctype html><meta charset="utf-8"><title>C v3 Vertical Slice Registry Review v2</title>
<style>
body{{font-family:system-ui;margin:18px;background:#f4f5f7;color:#111}}
section{{background:#fff;border:1px solid #c7cbd1;margin:18px 0;padding:14px;border-radius:8px}}
.card{{padding:12px;margin:14px 0;border:1px solid #ccd3db;border-radius:7px;background:#eef6ff}}
.card.unresolved{{background:#fff3cd}} canvas{{width:100%;max-width:840px;height:660px;border:1px solid #aaa;background:#fff}}
.meta{{line-height:1.5}} .hash{{font:12px ui-monospace,monospace;word-break:break-all}}
.checks{{padding:8px;background:#fff;border:1px solid #ddd;margin-top:8px}}
</style>
<h1>C v3 · Vertical Slice v1 · Surface Registry Review v2</h1>
<p><b>Critical contract:</b> this HTML contains no anatomical mask rules. Every red region/curve and deep-space path is precomputed by <code>slice_surface_registry.py</code>, the same geometry executor reserved for the pilot solver. The displayed vertex-set SHA-256 is independently checked in CI.</p>
<div id="app"></div>
<script>
const verts={json.dumps(verts,separators=(',',':'))}, inds={json.dumps(inds,separators=(',',':'))};
const origin={json.dumps(origin)}, basis={json.dumps(basis,separators=(',',':'))};
const specs={json.dumps(specs,ensure_ascii=False,separators=(',',':'))}, payload={json.dumps(payload,ensure_ascii=False,separators=(',',':'))};
function dot(a,b){{return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]}}
function sub(a,b){{return [a[0]-b[0],a[1]-b[1],a[2]-b[2]]}}
function cross(a,b){{return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]}}
function norm(a){{return Math.hypot(a[0],a[1],a[2])}} function unit(a){{let n=norm(a)||1;return a.map(x=>x/n)}}
function patient(p){{let r=sub(p,origin);return [dot(r,basis.left),dot(r,basis.superior),dot(r,basis.anterior)]}}
const pv=verts.map(patient);
const cams={{
 front:{{sx:[-1,0,0],sy:[0,1,0],d:[0,0,1]}},
 back:{{sx:[1,0,0],sy:[0,1,0],d:[0,0,-1]}},
 left_hidden_arms:{{sx:[0,0,-1],sy:[0,1,0],d:[1,0,0]}},
 back_bones:{{sx:[1,0,0],sy:[0,1,0],d:[0,0,-1]}}
}};
function project(q,c){{return [dot(q,c.sx),dot(q,c.sy),dot(q,c.d)]}}
function draw(canvas,entry){{
 const ctx=canvas.getContext('2d'),W=canvas.width,H=canvas.height,cam=cams[entry.view]||cams.front;
 const pr=pv.map(q=>project(q,cam));let xmin=1e9,xmax=-1e9,ymin=1e9,ymax=-1e9,zmin=1e9,zmax=-1e9;
 for(const q of pr){{xmin=Math.min(xmin,q[0]);xmax=Math.max(xmax,q[0]);ymin=Math.min(ymin,q[1]);ymax=Math.max(ymax,q[1]);zmin=Math.min(zmin,q[2]);zmax=Math.max(zmax,q[2])}}
 const sc=Math.min((W-50)/(xmax-xmin),(H-50)/(ymax-ymin)),X=x=>W/2+(x-(xmin+xmax)/2)*sc,Y=y=>H/2-(y-(ymin+ymax)/2)*sc;
 const selected=new Set(entry.surface_vertex_indices),hidden=new Set(entry.hidden_surface_vertex_indices);
 const zb=new Float64Array(W*H);zb.fill(-Infinity);const shade=new Uint8Array(W*H);shade.fill(230);const red=new Uint8Array(W*H);
 function edge(ax,ay,bx,by,px,py){{return (px-ax)*(by-ay)-(py-ay)*(bx-ax)}}
 for(let k=0;k<inds.length;k+=3){{let ia=inds[k],ib=inds[k+1],ic=inds[k+2];if(hidden.has(ia)&&hidden.has(ib)&&hidden.has(ic))continue;
  let a=pr[ia],b=pr[ib],c=pr[ic],ax=X(a[0]),ay=Y(a[1]),bx=X(b[0]),by=Y(b[1]),cx=X(c[0]),cy=Y(c[1]),A=edge(ax,ay,bx,by,cx,cy);if(Math.abs(A)<1e-10)continue;
  let n=unit(cross(sub(pv[ib],pv[ia]),sub(pv[ic],pv[ia]))),isRed=(selected.has(ia)&&selected.has(ib)&&selected.has(ic));
  for(let y=Math.max(0,Math.floor(Math.min(ay,by,cy)));y<=Math.min(H-1,Math.ceil(Math.max(ay,by,cy)));y++)for(let x=Math.max(0,Math.floor(Math.min(ax,bx,cx)));x<=Math.min(W-1,Math.ceil(Math.max(ax,bx,cx)));x++){{let sx=x+.5,sy=y+.5,w0=edge(bx,by,cx,cy,sx,sy)/A,w1=edge(cx,cy,ax,ay,sx,sy)/A,w2=edge(ax,ay,bx,by,sx,sy)/A;if(w0<0||w1<0||w2<0)continue;let z=w0*a[2]+w1*b[2]+w2*c[2],ii=y*W+x;if(z<=zb[ii])continue;zb[ii]=z;shade[ii]=Math.round(145+80*Math.abs(dot(n,cam.d)));red[ii]=isRed?1:0;}}
 }}
 let im=ctx.createImageData(W,H);for(let i=0;i<W*H;i++){{let o=i*4;if(zb[i]===-Infinity){{im.data[o]=im.data[o+1]=im.data[o+2]=255;im.data[o+3]=255;continue}}if(red[i]){{im.data[o]=215;im.data[o+1]=58;im.data[o+2]=45}}else{{im.data[o]=im.data[o+1]=im.data[o+2]=shade[i]}}im.data[o+3]=255}}ctx.putImageData(im,0,0);
 function P(w){{let q=project(patient(w),cam);return [X(q[0]),Y(q[1])]}}
 // Explicit selected vertices: guarantees the reviewed vertex set is visually represented even at region boundaries.
 ctx.fillStyle='rgba(215,58,45,.65)';for(const i of entry.surface_vertex_indices){{let q=pr[i],x=X(q[0]),y=Y(q[1]);ctx.fillRect(x-0.7,y-0.7,1.4,1.4)}}
 // Lines/creases/median lines are thin curves, not filled bands.
 ctx.strokeStyle='#d7191c';ctx.lineWidth=2.0;for(const curve of entry.curves){{if(curve.length<2)continue;ctx.beginPath();let p=P(curve[0]);ctx.moveTo(...p);for(let i=1;i<curve.length;i++){{p=P(curve[i]);ctx.lineTo(...p)}}ctx.stroke()}}
 // Deep space (radius-ulna) is shown as a distinct 3D path.
 if(entry.deep_points.length>1){{ctx.strokeStyle='#8e44ad';ctx.lineWidth=4;ctx.beginPath();let p=P(entry.deep_points[0]);ctx.moveTo(...p);for(let i=1;i<entry.deep_points.length;i++){{p=P(entry.deep_points[i]);ctx.lineTo(...p)}}ctx.stroke()}}
 // Bone reference anchors.
 ctx.font='12px system-ui';for(const m of entry.markers){{if(!m.point)continue;let p=P(m.point);ctx.fillStyle='#0068b5';ctx.beginPath();ctx.arc(p[0],p[1],5,0,Math.PI*2);ctx.fill();ctx.fillStyle='#003b66';ctx.fillText(m.label,p[0]+7,p[1]-5)}}
 ctx.fillStyle='#111';ctx.font='bold 14px system-ui';ctx.fillText(entry.view.toUpperCase(),12,20);
}}
const grouped={{}};for(const [id,s] of Object.entries(specs))(grouped[s.group]??=[]).push(id);const app=document.getElementById('app');
for(const [group,ids] of Object.entries(grouped)){{let sec=document.createElement('section');sec.innerHTML='<h2>'+group+'</h2>';for(const id of ids){{let s=specs[id],e=payload[id],card=document.createElement('div');card.className='card '+(s.status.includes('UNRESOLVED')?'unresolved':'');card.innerHTML='<h3>'+id+'</h3><div class="meta"><b>WHO expression:</b> '+s.terms.join(' / ')+'<br><b>Definition:</b> '+s.definition+'<br><b>Required by:</b> '+s.required_by.join(', ')+'<br><b>Execution status:</b> '+e.status+'<br><b>Review view:</b> '+e.view+'<br><b>Selected skin vertices:</b> '+e.surface_vertex_indices.length+'<br><b>Solver vertex hash:</b> <span class="hash">'+e.solver_vertex_hash+'</span></div><div class="checks">☐ anatomical scope 맞다 / 틀리다 &nbsp; ☐ side·aspect 맞다 / 틀리다 &nbsp; ☐ proximal-distal 또는 superior-inferior extent 맞다 / 틀리다<br>☐ line·crease·boundary placement 맞다 / 틀리다 &nbsp; ☐ bone anchors 맞다 / 틀리다 &nbsp; ☐ ACCEPT &nbsp; ☐ REJECT &nbsp; ☐ KEEP UNRESOLVED</div>';if(e.status!=='UNRESOLVED'||e.curves.length||e.markers.length||e.deep_points.length){{let cv=document.createElement('canvas');cv.width=840;cv.height=660;card.appendChild(cv);setTimeout(()=>draw(cv,e),0)}}sec.appendChild(card)}}app.appendChild(sec)}}
</script>'''
 (out/"surface-registry-review.html").write_text(html,encoding="utf-8")
 print(json.dumps({"cohort":list(COHORT),"registry_entries":len(REGISTRY),"calibration_rows":len(calibration),"resolved_registry":sum(1 for x in results.values() if x.status=="RESOLVED"),"unresolved_registry":sum(1 for x in results.values() if x.status=="UNRESOLVED"),"out_dir":str(out)}))

if __name__=="__main__":main()
