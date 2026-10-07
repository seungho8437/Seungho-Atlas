#!/usr/bin/env python3
"""Build Stage 3 human-audit artifacts for the Vertical Slice v1 pilot.

Renderer only: consumes the frozen Stage 3 result/validation and source graph.
It does not synthesize or alter coordinates.
"""
from __future__ import annotations
import argparse,hashlib,html,json,math,os
from pathlib import Path
from spatial_core import AtlasStore,vsub,dot

ORDER=("LI4","GB23","BL40","TE6","HT7","ST1","GB14","LU6","LI7","GB26","ST2","ST10","LI18","LI17","BL17","BL23","BL25","TE20","ST4","ST9")

def sha256_file(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def patient(p,sub):
 gf=sub["global_frame"];o=tuple(gf["origin"]);r=vsub(tuple(p),o)
 return (dot(r,tuple(gf["axes"]["left"])),dot(r,tuple(gf["axes"]["superior"])),dot(r,tuple(gf["axes"]["anterior"])))

def render_back(store,sub,coords,path,crop=None,w=760,h=1100):
 from PIL import Image,ImageDraw
 pts=[patient(p,sub) for p in store.vertices("FJ2810")]
 if crop:
  xmin,xmax,ymin,ymax=crop
 else:
  xs=[p[0] for p in pts];ys=[p[1] for p in pts];xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys)
 padx=(xmax-xmin)*.04 or .01;pady=(ymax-ymin)*.04 or .01;xmin-=padx;xmax+=padx;ymin-=pady;ymax+=pady
 img=Image.new("RGB",(w,h),"white");pix=img.load();zbuf=[[float("inf")]*w for _ in range(h)]
 for x,y,z in pts:
  if not (xmin<=x<=xmax and ymin<=y<=ymax):continue
  px=int((x-xmin)/(xmax-xmin)*(w-1));py=int((ymax-y)/(ymax-ymin)*(h-1))
  # back view: most posterior = smallest patient-anterior coordinate
  if z<zbuf[py][px]:
   zbuf[py][px]=z
   pix[px,py]=(185,185,185)
 dr=ImageDraw.Draw(img)
 for c in coords:
  x,y,z=patient(c["coordinate_world_m"],sub)
  if not (xmin<=x<=xmax and ymin<=y<=ymax):continue
  px=int((x-xmin)/(xmax-xmin)*(w-1));py=int((ymax-y)/(ymax-ymin)*(h-1))
  r=8;dr.ellipse((px-r,py-r,px+r,py+r),fill=(210,35,35),outline=(80,0,0),width=2)
  dr.text((px+10,py-7),c["side"],fill=(0,0,0))
 img.save(path)

def source_map(graph,pid):
 rows=[]
 for s in graph["source_statements"]:
  if s.get("point_id")==pid and s.get("section") in ("location","note","remarks"):
   rows.append({"source_statement_id":s["source_statement_id"],"section":s.get("section"),"text":s.get("text_canonical"),"page":s.get("page") or s.get("source_page")})
 return rows

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--stage3",required=True);ap.add_argument("--validation",required=True);ap.add_argument("--stage2",required=True)
 ap.add_argument("--substrate",required=True);ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json")
 ap.add_argument("--model-dir",default="public/models");ap.add_argument("--out-dir",required=True)
 args=ap.parse_args()
 s3=json.loads(Path(args.stage3).read_text());val=json.loads(Path(args.validation).read_text());s2=json.loads(Path(args.stage2).read_text())
 sub=json.loads(Path(args.substrate).read_text());graph=json.loads(Path(args.graph).read_text());store=AtlasStore(Path(args.model_dir))
 p3={x["point_id"]:x for x in s3["points"]};p2={x["point_id"]:x for x in s2["points"]}
 out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True);imgdir=out/"stage3-review-images";imgdir.mkdir(exist_ok=True)
 allcoords=[c for p in s3["points"] for c in p["coordinates"]]
 render_back(store,sub,allcoords,imgdir/"full-back.png")
 visuals={}
 for pid in ORDER:
  if not p3[pid]["coordinates"]:continue
  pcs=[patient(c["coordinate_world_m"],sub) for c in p3[pid]["coordinates"]]
  xmin=min(x for x,y,z in pcs)-.16;xmax=max(x for x,y,z in pcs)+.16;ymin=min(y for x,y,z in pcs)-.15;ymax=max(y for x,y,z in pcs)+.15
  fn=f"{pid}-back-close.png";render_back(store,sub,p3[pid]["coordinates"],imgdir/fn,crop=(xmin,xmax,ymin,ymax),w=900,h=650);visuals[pid]=fn
 data={"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-stage3-human-review-data",
  "human_audit_status":"PENDING","stage3_sha256":sha256_file(Path(args.stage3)),"validation_sha256":sha256_file(Path(args.validation)),
  "validation_status":val["status"],"validation_checks":val["checks"],"validation_errors":val["errors"],
  "suppressed_provenance_watchpoint_metrics":val.get("suppressed_provenance_watchpoint_metrics",{}),
  "summary":s3["summary"],"points":[]}
 for pid in ORDER:
  a=p3[pid];b=p2[pid]
  data["points"].append({"point_id":pid,"who_source":source_map(graph,pid),"stage2_primary_status":b["primary_location_status"],
   "stage3_status":a["stage3_status"],"blocking_reason":a["blocking_reason"],"coordinates":a["coordinates"],"trace":a["trace"],
   "visual":visuals.get(pid)})
 (out/"stage3-human-review-data.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")

 css="body{font-family:system-ui;margin:22px;background:#f5f6f8}.card{background:#fff;border:1px solid #ccd;padding:16px;margin:18px 0;border-radius:8px}.mono{font:11px ui-monospace,monospace;word-break:break-all;white-space:pre-wrap}.src{background:#f8fafc;padding:8px;margin:5px 0}.ok{background:#dcfce7}.warn{background:#fef3c7}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #ccd;padding:5px;vertical-align:top}img{max-width:100%;border:1px solid #aaa}.check{line-height:1.7;border:1px solid #999;padding:10px}"
 H=['<!doctype html><meta charset="utf-8"><title>C v3 Stage 3 Human Audit</title><style>'+css+'</style>',
    '<h1>C v3 Vertical Slice v1 - Stage 3 Human Audit</h1>',
    f'<p><b>Automated validation:</b> {val["status"]} ({val["checks"]} checks / {val["errors"]} errors). <b>Human audit: PENDING.</b> Stage 4 has not started.</p>',
    '<p>Coordinates in this artifact are pilot candidates only, non-deployable, and protected from production coordinate writes.</p>',
    '<h2>Outcome summary</h2><pre class="mono">'+html.escape(json.dumps(s3["summary"],indent=2))+'</pre>',
    '<h2>Suppressed-provenance watchpoint</h2><pre class="mono">'+html.escape(json.dumps(val.get("suppressed_provenance_watchpoint_metrics",{}),indent=2))+'</pre>',
    '<h2>Full back overview</h2><img src="stage3-review-images/full-back.png">']
 for p in data["points"]:
  cls="ok" if p["stage3_status"]=="GENERATED" else "warn"
  H.append(f'<section class="card {cls}"><h2>{p["point_id"]}: {p["stage3_status"]}</h2><p>Stage 2 primary: <b>{p["stage2_primary_status"]}</b><br>Blocker: {html.escape(str(p["blocking_reason"]))}</p>')
  H.append("<h3>WHO source</h3>")
  for s in p["who_source"]:H.append(f'<div class="src"><b>{html.escape(str(s["section"]))} / {html.escape(str(s["source_statement_id"]))} / page {html.escape(str(s["page"]))}</b><br>{html.escape(str(s["text"]))}</div>')
  H.append('<h3>Stage 3 trace</h3><pre class="mono">'+html.escape(json.dumps(p["trace"],ensure_ascii=False,indent=2))+'</pre>')
  if p["coordinates"]:
   H.append('<h3>Generated pilot coordinates</h3><table><tr><th>side</th><th>world coordinate</th><th>triangle</th><th>barycentric</th><th>projection t/budget</th><th>registry hash</th></tr>')
   for c in p["coordinates"]:
    H.append("<tr>"+''.join(f"<td class='mono'>{html.escape(str(v))}</td>" for v in [c["side"],c["coordinate_world_m"],c["triangle_index"],c["barycentric"],f'{c["projection"]["t_m"]} / {c["projection"]["budget_m"]}',c["source_geometry"]["registry_geometry_hash"]])+"</tr>")
   H.append('</table>')
   if p["visual"]:H.append(f'<h3>Local back-view visual QC</h3><img src="stage3-review-images/{p["visual"]}">')
  H.append('<div class="check">[ ] WHO location semantics are compatible with the Stage 3 synthesis family<br>[ ] all hard primary constraints were executable<br>[ ] cardinality/laterality are correct<br>[ ] candidate geometry is anatomically plausible<br>[ ] aspect-directed ray projection is correct<br>[ ] coordinate lies on the declared skin triangle<br>[ ] projection budget is acceptable<br>[ ] unresolved points were not force-solved<br>[ ] ACCEPT<br>[ ] REJECT</div></section>')
 (out/"stage3-human-review.html").write_text("".join(H),encoding="utf-8")

 from reportlab.lib.pagesizes import A4
 from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
 from reportlab.lib.units import mm
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Image
 from reportlab.pdfbase import pdfmetrics
 from reportlab.pdfbase.ttfonts import TTFont
 font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf";base="Helvetica"
 if os.path.exists(font):pdfmetrics.registerFont(TTFont("DV",font));base="DV"
 styles=getSampleStyleSheet();h1=ParagraphStyle("h1x",parent=styles["Heading1"],fontName=base,fontSize=14,leading=17)
 h2=ParagraphStyle("h2x",parent=styles["Heading2"],fontName=base,fontSize=10.5,leading=13,spaceBefore=5)
 body=ParagraphStyle("bx",parent=styles["BodyText"],fontName=base,fontSize=7.8,leading=10)
 mono=ParagraphStyle("mx",parent=body,fontName=base,fontSize=6.4,leading=8.1,wordWrap="CJK")
 doc=SimpleDocTemplate(str(out/"stage3-human-review.pdf"),pagesize=A4,leftMargin=11*mm,rightMargin=11*mm,topMargin=11*mm,bottomMargin=11*mm)
 story=[Paragraph("C v3 Vertical Slice v1 - Stage 3 Human Audit",h1),
        Paragraph(f"Automated validation: {val['status']} ({val['checks']} checks / {val['errors']} errors). Human audit: PENDING. Stage 4 not started.",body),
        Paragraph("Pilot coordinates are non-deployable and are not the production 361-point coordinate dataset.",body),
        Paragraph("Outcome summary",h2),Paragraph(html.escape(json.dumps(s3["summary"],ensure_ascii=False)),mono),
        Paragraph("Suppressed-provenance watchpoint",h2),Paragraph(html.escape(json.dumps(val.get("suppressed_provenance_watchpoint_metrics",{}),ensure_ascii=False)),mono)]
 full=imgdir/"full-back.png"
 if full.exists():story+=[Spacer(1,5),Image(str(full),width=170*mm,height=170*mm*1100/760)]
 for p in data["points"]:
  story+=[PageBreak(),Paragraph(f"{p['point_id']}: {p['stage3_status']}",h1),
         Paragraph(f"Stage 2 primary: {p['stage2_primary_status']} | blocker: {html.escape(str(p['blocking_reason']))}",body),
         Paragraph("WHO source",h2)]
  for s in p["who_source"]:story.append(Paragraph(html.escape(f"{s['section']} | {s['source_statement_id']} | page {s['page']} | {s['text']}"),body))
  story+=[Paragraph("Stage 3 trace",h2),Paragraph(html.escape(json.dumps(p["trace"],ensure_ascii=False,sort_keys=True)),mono)]
  if p["coordinates"]:
   story.append(Paragraph("Generated pilot coordinates",h2))
   for c in p["coordinates"]:story.append(Paragraph(html.escape(json.dumps(c,ensure_ascii=False,sort_keys=True)),mono))
   if p["visual"]:
    q=imgdir/p["visual"]
    if q.exists():story+=[Spacer(1,5),Image(str(q),width=175*mm,height=175*mm*650/900)]
  story.append(Paragraph("[ ] WHO semantics compatible with synthesis family<br/>[ ] hard constraints executable<br/>[ ] cardinality/laterality correct<br/>[ ] anatomy plausible<br/>[ ] aspect-directed ray projection correct<br/>[ ] skin triangle reconstruction correct<br/>[ ] projection budget acceptable<br/>[ ] unresolved cases not force-solved<br/>[ ] ACCEPT<br/>[ ] REJECT",body))
 doc.build(story)
 print(json.dumps({"points":len(data["points"]),"generated_coordinates":s3["summary"]["generated_coordinates"],"human_audit":"PENDING"}))
if __name__=="__main__":main()
