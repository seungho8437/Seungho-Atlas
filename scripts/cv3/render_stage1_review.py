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
   "right":{"screen_x":[0,0,1],"screen_y":[0,1,0],"depth":[-1,0,0],"label":"RIGHT"},
   "front_oblique":{"screen_x":[-0.7071067811865476,0,0.7071067811865476],"screen_y":[0,1,0],"depth":[0.7071067811865476,0,0.7071067811865476],"label":"FRONT-OBLIQUE"},
   "back_oblique":{"screen_x":[0.7071067811865476,0,-0.7071067811865476],"screen_y":[0,1,0],"depth":[-0.7071067811865476,0,-0.7071067811865476],"label":"BACK-OBLIQUE"}
 }
 contract={"schema_version":"1.0.0","artifact":"stage1-review-camera-contract",
   "coordinate_basis":{"left":left,"superior":superior,"anterior":anterior,"origin":origin},
   "cameras":cameras,
   "rendering":{"normal_shading":True,"depth_cue":True,"hidden_surface":"software_z_buffer","wireframe_overlay":False,"oblique_views":True,"acupoints_rendered":False},
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
<p class="note">No acupoints are rendered. The skin uses a per-pixel software z-buffer, so hidden anterior surfaces cannot bleed through the BACK view and hidden posterior surfaces cannot bleed through the FRONT view. Normal/depth shading and oblique views are included for occiput, back, buttocks, heel and foot-orientation review.</p>
<div class="grid">
<canvas id="front" width="700" height="620"></canvas><canvas id="back" width="700" height="620"></canvas>
<canvas id="left" width="700" height="620"></canvas><canvas id="right" width="700" height="620"></canvas>
<canvas id="front_oblique" width="700" height="620"></canvas><canvas id="back_oblique" width="700" height="620"></canvas>
</div>
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
function cross(a,b){{return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]}}
function norm(a){{return Math.hypot(a[0],a[1],a[2])}}
function unit(a){{const n=norm(a)||1;return [a[0]/n,a[1]/n,a[2]/n]}}
function patient(p){{const r=sub(p,origin);return [dot(r,basis.left),dot(r,basis.superior),dot(r,basis.anterior)]}}
const pv=verts.map(patient);
function proj(q,cam){{return [dot(q,cam.screen_x),dot(q,cam.screen_y),dot(q,cam.depth)]}}
function draw(id){{
 const c=document.getElementById(id),ctx=c.getContext('2d'),cam=cameras[id];
 ctx.clearRect(0,0,c.width,c.height);
 const projected=pv.map(q=>proj(q,cam));
 let xmin=Infinity,xmax=-Infinity,ymin=Infinity,ymax=-Infinity,zmin=Infinity,zmax=-Infinity;
 for(const q of projected){{xmin=Math.min(xmin,q[0]);xmax=Math.max(xmax,q[0]);ymin=Math.min(ymin,q[1]);ymax=Math.max(ymax,q[1]);zmin=Math.min(zmin,q[2]);zmax=Math.max(zmax,q[2])}}
 const padx=34,pady=36,sx=(c.width-2*padx)/(xmax-xmin),sy=(c.height-2*pady)/(ymax-ymin),scale=Math.min(sx,sy);
 const X=x=>c.width/2+(x-(xmin+xmax)/2)*scale, Y=y=>c.height/2-(y-(ymin+ymax)/2)*scale;
 const W=c.width,H=c.height;
 const zbuf=new Float64Array(W*H);zbuf.fill(-Infinity);
 const shadebuf=new Uint8Array(W*H);shadebuf.fill(255);
 const light=unit([0.35,0.55,0.76]);
 function edge(ax,ay,bx,by,px,py){{return (px-ax)*(by-ay)-(py-ay)*(bx-ax)}}
 for(let k=0;k<inds.length;k+=3){{
   const ia=inds[k],ib=inds[k+1],ic=inds[k+2];
   const pa=projected[ia],pb=projected[ib],pc=projected[ic];
   const ax=X(pa[0]),ay=Y(pa[1]),bx=X(pb[0]),by=Y(pb[1]),cx=X(pc[0]),cy=Y(pc[1]);
   const area=edge(ax,ay,bx,by,cx,cy);
   if(Math.abs(area)<1e-9)continue;
   const minx=Math.max(0,Math.floor(Math.min(ax,bx,cx))),maxx=Math.min(W-1,Math.ceil(Math.max(ax,bx,cx)));
   const miny=Math.max(0,Math.floor(Math.min(ay,by,cy))),maxy=Math.min(H-1,Math.ceil(Math.max(ay,by,cy)));
   const va=pv[ia],vb=pv[ib],vc=pv[ic],n=unit(cross(sub(vb,va),sub(vc,va)));
   const facing=Math.abs(dot(n,cam.depth)),lam=Math.abs(dot(n,light));
   for(let py=miny;py<=maxy;py++){{for(let px=minx;px<=maxx;px++){{
     const sx=px+0.5,sy=py+0.5;
     const w0=edge(bx,by,cx,cy,sx,sy)/area,w1=edge(cx,cy,ax,ay,sx,sy)/area,w2=edge(ax,ay,bx,by,sx,sy)/area;
     if(w0<-1e-8||w1<-1e-8||w2<-1e-8)continue;
     const z=w0*pa[2]+w1*pb[2]+w2*pc[2],idx=py*W+px;
     if(z<=zbuf[idx])continue;
     zbuf[idx]=z;
     const depth=(z-zmin)/(zmax-zmin||1);
     shadebuf[idx]=Math.round(Math.max(72,Math.min(235,88+92*facing+34*lam+20*depth)));
   }}}}
 }}
 const img=ctx.createImageData(W,H);
 for(let i=0;i<W*H;i++){{
   const o=i*4;
   if(zbuf[i]===-Infinity){{img.data[o]=255;img.data[o+1]=255;img.data[o+2]=255;img.data[o+3]=255;continue}}
   const s=shadebuf[i];img.data[o]=s;img.data[o+1]=s;img.data[o+2]=s;img.data[o+3]=255;
 }}
 // Depth-gradient contour enhancement only on visible pixels.
 for(let y=1;y<H-1;y++){{for(let x=1;x<W-1;x++){{
   const i=y*W+x;if(zbuf[i]===-Infinity)continue;
   const zl=zbuf[i-1],zr=zbuf[i+1],zu=zbuf[i-W],zd=zbuf[i+W];
   if(zl===-Infinity||zr===-Infinity||zu===-Infinity||zd===-Infinity)continue;
   const g=Math.max(Math.abs(zr-zl),Math.abs(zd-zu));
   if(g>0.003){{const o=i*4;img.data[o]=Math.max(30,img.data[o]-42);img.data[o+1]=Math.max(30,img.data[o+1]-42);img.data[o+2]=Math.max(30,img.data[o+2]-42)}}
 }}}}
 ctx.putImageData(img,0,0);
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
for(const m of ['front','back','left','right','front_oblique','back_oblique'])draw(m);
</script>'''
 p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(html,encoding="utf-8")
 print(json.dumps({"out":str(p),"contract":str(cp),"vertices":len(verts),"triangles":len(inds)//3,"views":len(cameras),"frame_lines":len(lines),"joints":len(joints)}))
if __name__=="__main__":main()
