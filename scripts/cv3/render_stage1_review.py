#!/usr/bin/env python3
"""Render non-deployed Stage 1 frame/surface QC artifact."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from spatial_core import AtlasStore

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--model-dir",default="public/models");ap.add_argument("--substrate",default=".tmp/c-v3-stage1/spatial-substrate.json");ap.add_argument("--out",default=".tmp/c-v3-stage1/stage1-review.html");args=ap.parse_args()
 s=json.loads(Path(args.substrate).read_text());store=AtlasStore(Path(args.model_dir));skin=store.vertices(s["surface_contract"]["skin_part_id"]);step=max(1,len(skin)//12000)
 pts=[list(skin[i]) for i in range(0,len(skin),step)]
 lines=[]
 gf=s["global_frame"];o=gf["origin"]
 for name,v in gf["axes"].items():
  lines.append({"name":"global_"+name,"a":o,"b":[o[i]+v[i]*0.22 for i in range(3)],"kind":"global"})
 for name,fr in s["frames"].items():
  if "proximal_to_distal" not in fr["axes"]:continue
  a=fr["proximal"];b=fr["distal"];lines.append({"name":name,"a":a,"b":b,"kind":"segment"})
 joints=[]
 for side,jj in s["joints"].items():
  for name,x in jj.items():joints.append({"name":side+"_"+name,"p":x["center"]})
 html=f'''<!doctype html><meta charset="utf-8"><title>C v3 Stage 1 spatial QC</title>
<style>body{{font-family:system-ui;margin:18px;background:#f6f7f8;color:#111}}.grid{{display:grid;grid-template-columns:repeat(2,minmax(320px,1fr));gap:12px}}canvas{{width:100%;height:620px;background:white;border:1px solid #bbb}}code{{background:#eee;padding:2px 4px}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}</style>
<h1>C v3 · Stage 1 spatial substrate visual QC</h1>
<p>No acupoints are rendered. Inspect only global/local anatomical frames, joint ordering and gross spatial orientation. This file is a workflow artifact and is not deployed.</p>
<div class="grid"><canvas id="front" width="700" height="620"></canvas><canvas id="back" width="700" height="620"></canvas><canvas id="left" width="700" height="620"></canvas><canvas id="right" width="700" height="620"></canvas></div>
<script>
const pts={json.dumps(pts,separators=(',',':'))};
const lines={json.dumps(lines,separators=(',',':'))};
const joints={json.dumps(joints,separators=(',',':'))};
function xy(p,mode){{let a,b;if(mode==='front'){{a=p[0];b=p[1]}}else if(mode==='back'){{a=-p[0];b=p[1]}}else if(mode==='left'){{a=-p[2];b=p[1]}}else{{a=p[2];b=p[1]}}return [350+a*800,600-b*335]}}
function draw(id,mode){{const c=document.getElementById(id),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);x.fillStyle='#555';for(const p of pts){{const q=xy(p,mode);x.fillRect(q[0],q[1],1.4,1.4)}}x.lineWidth=2;for(const l of lines){{const a=xy(l.a,mode),b=xy(l.b,mode);x.strokeStyle=l.kind==='global'?'#111':'#555';x.beginPath();x.moveTo(...a);x.lineTo(...b);x.stroke()}}for(const j of joints){{const q=xy(j.p,mode);x.fillStyle='#111';x.beginPath();x.arc(q[0],q[1],3,0,Math.PI*2);x.fill()}}x.fillStyle='#111';x.font='16px system-ui';x.fillText(id.toUpperCase(),12,22)}}
for(const m of ['front','back','left','right'])draw(m,m);
</script>'''
 p=Path(args.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(html,encoding="utf-8");print(json.dumps({"out":str(p),"skin_samples":len(pts),"frame_lines":len(lines),"joints":len(joints)}))
if __name__=="__main__":main()
