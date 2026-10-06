#!/usr/bin/env python3
"""Render non-deployed Stage 1 frame/surface QC artifact.

Uses the validated patient frame, not raw XYZ labels. Orthographic views are
true opposite camera projections with depth-aware triangle rendering.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
from spatial_core import AtlasStore

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--model-dir",default="public/models")
 ap.add_argument("--substrate",default=".tmp/c-v3-stage1/spatial-substrate.json")
 ap.add_argument("--out",default=".tmp/c-v3-stage1/stage1-review.html")
 ap.add_argument("--contract-out",default=".tmp/c-v3-stage1/stage1-review-contract.json")
 args=ap.parse_args()
 s=json.loads(Path(args.substrate).read_text())
 store=AtlasStore(Path(args.model_dir))
 pid=s["surface_contract"]["skin_part_id"]
 verts=[list(v) for v in store.vertices(pid)]
 inds=list(store.indices(pid))
 gf=s["global_frame"]; origin=gf["origin"]
 left=gf["axes"]["left"]; superior=gf["axes"]["superior"]; anterior=gf["axes"]["anterior"]

 cameras={
   "front":{"screen_x":[-1,0,0],"screen_y":[0,1,0],"depth":[0,0,1],"label":"FRONT"},
   "back":{"screen_x":[1,0,0],"screen_y":[0,1,0],"depth":[0,0,-1],"label":"BACK"},
   "left":{"screen_x":[0,0,-1],"screen_y":[0,1,0],"depth":[1,0,0],"label":"LEFT"},
   "right":{"screen_x":[0,0,1],"screen_y":[0,1,0],"depth":[-1,0,0],"label":"RIGHT"}
 }
 contract={"schema_version":"1.0.0","artifact":"stage1-review-camera-contract",
   "coordinate_basis":{"left":left,"superior":superior,"anterior":anterior,"origin":origin},
   "cameras":cameras,
   "invariants":{"front_back_depth_opposite":True,"left_right_depth_opposite":True,
     "front_back_screen_x_mirrored":True,"left_right_screen_x_mirrored":True,
     "depth_aware_surface_rendering":True,"raw_world_xyz_projection":False}}
 cp=Path(args.contract_out);cp.parent.mkdir(parents=True,exist_ok=True);cp.write_text(json.dumps(contract,indent=2)+"\n")

 lines=[];o=origin
 for name,v in gf["axes"].items():
  lines.append({"name":"global_"+name,"a":o,"b":[o[i]+v[i]*0.22 for i in range(3)],"kind":"global"})
 for name,fr in s["frames"].items():
  if "proximal_to_distal" not in fr["axes"]:continue
  lines.append({"name":name,"a":fr["proximal"],"b":fr["distal"],"kind":"segment"})
 joints=[]
 for side,jj in s["joints"].items():
  for name,x in jj.items():joints.append({"name":side+"_"+name,"p":x["center"]})

 html=f'''<!doctype html><meta charset="utf-8"><title>C v3 Stage 1 spatial QC</title>
<style>
body{{font-family:system-ui;margin:18px;background:#f6f7f8;color:#111}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(320px,1fr));gap:12px}}
canvas{{width:100%;height:620px;background:white;border:1px solid #bbb}}
.note{{max-width:1050px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
</style>
<h1>C v3 · Stage 1 spatial substrate visual QC</h1>
<p class="note">No acupoints are rendered. Surface triangles are projected in the validated patient frame with depth-aware orthographic cameras. FRONT/BACK and LEFT/RIGHT are true opposite views. Frame lines and joint points are overlaid for QC.</p>
<div class="grid"><canvas id="front" width="700" height="620"></canvas><canvas id="back" width="700" height="620"></canvas><canvas id="left" width="700" height="620"></canvas><canvas id="right" width="700" height="620"></canvas></div>
<script>
const verts={json.dumps(verts,separators=(',',':'))};
const inds={json.dumps(inds,separators=(',',':'))};
const origin={json.dumps(origin)};
const basis={{left:{json.dumps(left)},superior:{json.dumps(superior)},anterior:{json.dumps(anterior)}}};
const cameras={json.dumps(cameras,separators=(',',':'))};
const lines={json.dumps(lines,separators=(',',':'))};
const joints={json.dumps(joints,separators=(',',':'))};
function dot(a,b){{return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]}}
function sub(a,b){{return [a[0]-b[0],a[1]-b[1],a[2]-b[2]]}}
function patient(p){{const r=sub(p,origin);return [dot(r,basis.left),dot(r,basis.superior),dot(r,basis.anterior)]}}
const pv=verts.map(patient);
function proj(q,cam){{return [dot(q,cam.screen_x),dot(q,cam.screen_y),dot(q,cam.depth)]}}
function draw(id){{
 const c=document.getElementById(id),ctx=c.getContext('2d'),cam=cameras[id];
 ctx.clearRect(0,0,c.width,c.height);
 const projected=pv.map(q=>proj(q,cam));
 let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity;
 for(const q of projected){{xmin=Math.min(xmin,q[0]);xmax=Math.max(xmax,q[0]);ymin=Math.min(ymin,q[1]);ymax=Math.max(ymax,q[1])}}
 const padx=34,pady=36,sx=(c.width-2*padx)/(xmax-xmin),sy=(c.height-2*pady)/(ymax-ymin),scale=Math.min(sx,sy);
 const X=x=>c.width/2+(x-(xmin+xmax)/2)*scale, Y=y=>c.height/2-(y-(ymin+ymax)/2)*scale;
 const tris=[];
 for(let k=0;k<inds.length;k+=3){{
   const ia=inds[k],ib=inds[k+1],ic=inds[k+2];
   tris.push([(projected[ia][2]+projected[ib][2]+projected[ic][2])/3,ia,ib,ic]);
 }}
 tris.sort((a,b)=>a[0]-b[0]);
 ctx.fillStyle='#d1d5db';
 for(const t of tris){{
   const a=projected[t[1]],b=projected[t[2]],d=projected[t[3]];
   ctx.beginPath();ctx.moveTo(X(a[0]),Y(a[1]));ctx.lineTo(X(b[0]),Y(b[1]));ctx.lineTo(X(d[0]),Y(d[1]));ctx.closePath();ctx.fill();
 }}
 ctx.lineWidth=2;
 for(const l of lines){{
   const a=proj(patient(l.a),cam),b=proj(patient(l.b),cam);
   ctx.strokeStyle=l.kind==='global'?'#111':'#4b5563';
   ctx.beginPath();ctx.moveTo(X(a[0]),Y(a[1]));ctx.lineTo(X(b[0]),Y(b[1]));ctx.stroke();
 }}
 for(const j of joints){{
   const q=proj(patient(j.p),cam);ctx.fillStyle='#111';ctx.beginPath();ctx.arc(X(q[0]),Y(q[1]),3,0,Math.PI*2);ctx.fill();
 }}
 ctx.fillStyle='#111';ctx.font='16px system-ui';ctx.fillText(cam.label,12,22);
}}
for(const m of ['front','back','left','right'])draw(m);
</script>'''
 p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(html,encoding="utf-8")
 print(json.dumps({"out":str(p),"contract":str(cp),"vertices":len(verts),"triangles":len(inds)//3,"frame_lines":len(lines),"joints":len(joints)}))
if __name__=="__main__":main()
