#!/usr/bin/env python3
"""Build a lossless human-review layer from an EXISTING frozen Stage 2 output.

This script is a renderer/projection only:
- it never imports or runs the Stage 2 solver/executor;
- it never creates new semantic relations, landmark identities, FMA substitutions,
  registry substitutions, or fallback dependencies;
- every displayed semantic item is copied from the frozen Stage 2 output and the
  frozen B v2.1 source text keyed by existing source_statement_id.

Dependency edges are a mechanical projection of existing argument_node_ids,
measurement anchor_landmark_id, condition source_statement_id, and statement
membership. No semantic edge is inferred beyond those explicit fields.
"""
from __future__ import annotations
import argparse, hashlib, html, json, os
from pathlib import Path

COHORT=("LI4","GB23","ST10","LI18","LI17","BL17","BL23","BL25","BL40","ST4","TE6","ST9",
        "HT7","ST1","GB14","LU6","LI7","GB26","ST2","TE20")

def canon(obj):
 return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def sha(obj):
 return hashlib.sha256(canon(obj).encode()).hexdigest()

def file_sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()

def identity_from_landmark(rec):
 g=rec.get("geometry") or {}
 kind=g.get("kind")
 out={"kind":kind}
 if kind=="fma_concept":
  out.update({"fma_id":g.get("fma_id"),"part_ids":g.get("part_ids",[])})
 elif kind=="surface_registry":
  out.update({"registry_id":g.get("registry_id"),"geometry_hash":g.get("geometry_hash")})
 elif kind=="reference_acupoint":
  out.update({"reference_point_id":g.get("point_id")})
 elif kind=="entity_subfeature":
  out.update({"parent_landmark_id":g.get("parent_landmark_id"),"modifier":g.get("modifier")})
 if rec.get("candidates") is not None:
  out["candidates"]=rec.get("candidates")
 return out

def explicit_edges(point):
 edges=[]
 for rid,r in point["relations"].items():
  args=(r.get("constraint") or {}).get("argument_node_ids") or r.get("argument_node_ids") or []
  for a in args: edges.append({"from":a,"to":rid,"kind":"operand_to_relation"})
  sid=(r.get("constraint") or {}).get("source_statement_id")
  if sid: edges.append({"from":rid,"to":sid,"kind":"relation_to_statement"})
 for mid,m in point["measurements"].items():
  c=m.get("constraint") or {}
  a=c.get("anchor_landmark_id")
  if a: edges.append({"from":a,"to":mid,"kind":"anchor_to_measurement"})
  sid=c.get("source_statement_id")
  if sid: edges.append({"from":mid,"to":sid,"kind":"measurement_to_statement"})
 for cid,c in point["conditions"].items():
  # Stage 2 condition output does not repeat source_statement_id; statement membership
  # is copied from the frozen B condition record later, not guessed here.
  pass
 for s in point["statements"]:
  edges.append({"from":s["source_statement_id"],"to":point["point_id"],"kind":"statement_to_point"})
 return edges

def primary_location_statement(point):
 for s in point["statements"]:
  if s.get("section")=="location": return s
 return None

def derive_blocking(point,b_by_id):
 loc=primary_location_statement(point)
 if not loc or point.get("primary_location_status")=="RESOLVED":
  return {"first_unresolved_dependency":None,"upstream_resolved_dependencies":[],"blocking_items":[],"downstream_stop_items":[]}
 upstream=[];blocks=[];down=[]
 for rid in loc.get("relation_ids",[]):
  r=point["relations"].get(rid)
  if not r: continue
  args=(r.get("constraint") or {}).get("argument_node_ids") or r.get("argument_node_ids") or []
  if r.get("status")=="RESOLVED":
   upstream.append(rid)
   for a in args:
    if point["landmarks"].get(a,{}).get("status")=="RESOLVED": upstream.append(a)
  else:
   local=[]
   for a in args:
    lr=point["landmarks"].get(a)
    if lr and lr.get("status")!="RESOLVED":
     bn=b_by_id.get(a,{})
     local.append({"node_id":a,"node_type":"landmark","status":lr.get("status"),
                   "reason":lr.get("reason"),"source_raw":bn.get("source_raw"),
                   "landmark_class":bn.get("landmark_class")})
   if not local:
    local=[{"node_id":rid,"node_type":"relation","status":r.get("status"),"reason":r.get("reason")}]
   blocks.extend(local);down.append(rid)
 for mid in loc.get("measurement_ids",[]):
  m=point["measurements"].get(mid)
  if m and m.get("status")!="RESOLVED":
   blocks.append({"node_id":mid,"node_type":"measurement","status":m.get("status"),"reason":m.get("reason")});down.append(mid)
 return {"first_unresolved_dependency":blocks[0] if blocks else None,
         "upstream_resolved_dependencies":list(dict.fromkeys(upstream)),
         "blocking_items":blocks,"downstream_stop_items":down}

def make_projection(point,b_source,condition_source):
 b_by_id={x["node_id"]:x for x in b_source["landmark_nodes"]}
 loc=primary_location_statement(point)
 source_statement_ids=[x["source_statement_id"] for x in point["statements"]]
 source_text={}
 for sid in source_statement_ids:
  s=next((x for x in b_source["source_statements"] if x["source_statement_id"]==sid),None)
  if s: source_text[sid]={"section":s.get("section"),"text":s.get("text_canonical")}
 operands=[]
 for nid,rec in point["landmarks"].items():
  b=b_by_id.get(nid,{})
  operands.append({"landmark_id":nid,"source_raw":b.get("source_raw"),"landmark_class":b.get("landmark_class"),
                   "terminal_disposition":b.get("terminal_disposition"),"status":rec.get("status"),
                   "executor":rec.get("executor"),"identity":identity_from_landmark(rec),"reason":rec.get("reason")})
 relations=[]
 for rid,r in point["relations"].items():
  c=r.get("constraint") or {}
  relations.append({"relation_id":rid,"status":r.get("status"),"executor":r.get("executor"),
                    "operator":c.get("op"),"operand_ids":c.get("argument_node_ids") or r.get("argument_node_ids") or [],
                    "source_statement_id":c.get("source_statement_id"),"branch_id":c.get("branch_id"),
                    "direction":c.get("direction"),"reason":r.get("reason")})
 measurements=[]
 for mid,m in point["measurements"].items():
  c=m.get("constraint") or {}
  measurements.append({"measurement_id":mid,"status":m.get("status"),"executor":m.get("executor"),
    "kind":c.get("kind"),"value":c.get("value"),"unit":c.get("unit"),"source_unit":c.get("source_unit"),
    "direction":c.get("direction"),"anchor_landmark_id":c.get("anchor_landmark_id"),
    "source_statement_id":c.get("source_statement_id"),"who_pdf_page":c.get("who_pdf_page"),"reason":m.get("reason")})
 conditions=[]
 for cid,c in point["conditions"].items():
  bs=condition_source.get(cid,{})
  conditions.append({"condition_id":cid,"status":c.get("status"),"executor":c.get("executor"),
    "condition_type":c.get("condition_type"),"branch_id":c.get("branch_id"),"reason":c.get("reason"),
    "source_statement_id":bs.get("source_statement_id"),"source_span":bs.get("source_span")})
 edges=explicit_edges(point)
 for co in conditions:
  if co.get("source_statement_id"):
   edges.append({"from":co["condition_id"],"to":co["source_statement_id"],"kind":"condition_to_statement"})
 edges=sorted(edges,key=lambda e:(e["kind"],e["from"],e["to"]))
 block=derive_blocking(point,b_by_id)
 # Preserve source record order; this is not claimed to be timestamped runtime order.
 order=(list(point["landmarks"].keys())+list(point["measurements"].keys())+
        list(point["conditions"].keys())+list(point["relations"].keys())+
        [x["source_statement_id"] for x in point["statements"]]+[point["point_id"]])
 proj={"point_id":point["point_id"],"final_stage2_status":point.get("primary_location_status"),
       "conditional_present":any(x["status"]=="CONDITIONAL" for x in conditions),
       "primary_location_source_statement_id":loc.get("source_statement_id") if loc else None,
       "source_statements":source_text,"operands":operands,"relations":relations,
       "measurements":measurements,"conditions":conditions,"dependency_edges":edges,
       "recorded_data_order":order,"explicit_runtime_order_recorded":False,
       "final_semantic_execution_result":{"primary_location_status":point.get("primary_location_status"),
         "location_statement_status":loc.get("status") if loc else None},
       "blocking":block,"coordinate_generation_count":0,"legacy_c_coordinate_reference_count":0}
 return proj

def svg_graph(proj):
 nodes=[]
 for o in proj["operands"]: nodes.append((o["landmark_id"],"operand",o["status"]))
 for r in proj["relations"]: nodes.append((r["relation_id"],"relation",r["status"]))
 for m in proj["measurements"]: nodes.append((m["measurement_id"],"measurement",m["status"]))
 for c in proj["conditions"]: nodes.append((c["condition_id"],"condition",c["status"]))
 for sid in proj["source_statements"]: nodes.append((sid,"statement",""))
 nodes.append((proj["point_id"],"point",proj["final_stage2_status"]))
 # Compact deterministic rows by type; edges are explicit-source projections only.
 col={"operand":20,"relation":430,"measurement":430,"condition":430,"statement":800,"point":1080}
 ycount={}
 pos={}
 elems=[]
 for nid,typ,status in nodes:
  y=ycount.get(typ,0)*48+25;ycount[typ]=ycount.get(typ,0)+1
  x=col[typ];pos[nid]=(x,y)
  label=nid if len(nid)<=48 else nid[:45]+"..."
  fill="#dff0d8" if status=="RESOLVED" else ("#fff3cd" if status in ("UNRESOLVED","MULTIPLE","CONDITIONAL") else "#eef2f7")
  elems.append(f'<rect x="{x}" y="{y}" width="340" height="30" rx="5" fill="{fill}" stroke="#64748b"/><text x="{x+6}" y="{y+20}" font-size="10">{html.escape(label)}</text>')
 h=max([p[1] for p in pos.values()] or [100])+70
 lines=[]
 for e in proj["dependency_edges"]:
  if e["from"] in pos and e["to"] in pos:
   x1,y1=pos[e["from"]];x2,y2=pos[e["to"]]
   lines.append(f'<line x1="{x1+340}" y1="{y1+15}" x2="{x2}" y2="{y2+15}" stroke="#94a3b8" stroke-width="1"/>')
 return f'<svg viewBox="0 0 1440 {h}" width="100%" height="{min(h,820)}" xmlns="http://www.w3.org/2000/svg">'+"".join(lines+elems)+"</svg>"

def render_html(data,out):
 css="""body{font-family:system-ui,sans-serif;margin:24px;background:#f6f7f9;color:#111} .point{background:white;border:1px solid #ccd2da;border-radius:10px;padding:18px;margin:22px 0}.ok{color:#166534}.bad{color:#991b1b}.cond{color:#92400e}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #d6d9de;padding:5px;vertical-align:top}.mono{font-family:ui-monospace,monospace;font-size:11px;word-break:break-all}.src{white-space:pre-wrap;background:#f8fafc;padding:8px}.checks{border:1px solid #999;padding:10px;margin-top:12px;line-height:1.9}.small{font-size:12px;color:#475569}details{margin:8px 0}"""
 parts=[f'<!doctype html><meta charset="utf-8"><title>Stage 2 Human Semantic Review</title><style>{css}</style>',
 '<h1>C v3 Vertical Slice v1 - Stage 2 Human Semantic Review</h1>',
 '<p><b>Renderer-only contract:</b> this document is generated from the frozen Stage 2 output. It contains no JavaScript and no semantic executor.</p>',
 f'<p class="small">Frozen source SHA-256: <span class="mono">{data["stage2_source_sha256"]}</span> · coordinates generated: 0 · legacy C coordinate references: 0</p>']
 for p in data["points"]:
  st=p["final_stage2_status"];cls="ok" if st=="RESOLVED" else "bad"
  parts.append(f'<section class="point" id="{p["point_id"]}"><h2>{p["point_id"]} - <span class="{cls}">{st}</span></h2>')
  if p["conditional_present"]:parts.append('<p class="cond"><b>CONDITIONAL state present in Stage 2 output.</b></p>')
  sid=p["primary_location_source_statement_id"];src=p["source_statements"].get(sid,{})
  parts.append(f'<h3>WHO primary Location</h3><div class="src"><b>{html.escape(str(sid))}</b><br>{html.escape(str(src.get("text")))}</div>')
  parts.append('<h3>Semantic decomposition / operand identity</h3><table><tr><th>landmark ID</th><th>source</th><th>class</th><th>status</th><th>executor</th><th>identity actually used</th><th>reason</th></tr>')
  for o in p["operands"]:
   parts.append("<tr>"+ "".join(f"<td class='mono'>{html.escape(str(v))}</td>" for v in [o["landmark_id"],o.get("source_raw"),o.get("landmark_class"),o.get("status"),o.get("executor"),canon(o.get("identity")),o.get("reason")]) +"</tr>")
  parts.append('</table><h3>Relation / operator chain</h3><table><tr><th>relation ID</th><th>status</th><th>operator</th><th>operands</th><th>direction</th><th>source statement</th><th>reason</th></tr>')
  for r in p["relations"]:
   vals=[r["relation_id"],r["status"],r.get("operator") or r.get("executor"),", ".join(r["operand_ids"]),r.get("direction"),r.get("source_statement_id"),r.get("reason")]
   parts.append("<tr>"+ "".join(f"<td class='mono'>{html.escape(str(v))}</td>" for v in vals) +"</tr>")
  parts.append('</table>')
  if p["measurements"]:
   parts.append('<h3>Measurements / calibration use</h3><table><tr><th>ID</th><th>status</th><th>value</th><th>unit</th><th>direction</th><th>anchor</th><th>WHO PDF page</th></tr>')
   for m in p["measurements"]:
    vals=[m["measurement_id"],m["status"],m["value"],m["unit"],m["direction"],m["anchor_landmark_id"],m["who_pdf_page"]]
    parts.append("<tr>"+ "".join(f"<td class='mono'>{html.escape(str(v))}</td>" for v in vals) +"</tr>")
   parts.append('</table>')
  if p["conditions"]:
   parts.append('<h3>Conditional statements preserved from source/output</h3><table><tr><th>ID</th><th>source statement</th><th>source condition text</th><th>type</th><th>Stage 2 status</th><th>reason</th></tr>')
   for c in p["conditions"]:
    vals=[c["condition_id"],c["source_statement_id"],(c.get("source_span") or {}).get("source_raw"),c["condition_type"],c["status"],c["reason"]]
    parts.append("<tr>"+ "".join(f"<td class='mono'>{html.escape(str(v))}</td>" for v in vals) +"</tr>")
   parts.append('</table>')
  parts.append('<h3>Dependency graph</h3>'+svg_graph(p))
  parts.append('<h3>Execution order evidence</h3><p class="small">Stage 2 output does not record timestamped per-operation runtime order. The following is the exact serialized Stage 2 data order and is shown without semantic reordering.</p><div class="mono">'+html.escape(" -> ".join(p["recorded_data_order"]))+'</div>')
  parts.append('<h3>Final semantic execution result</h3><pre class="mono">'+html.escape(json.dumps(p["final_semantic_execution_result"],ensure_ascii=False,indent=2))+'</pre>')
  if st!="RESOLVED":
   parts.append('<h3>Blocking dependency</h3><pre class="mono">'+html.escape(json.dumps(p["blocking"],ensure_ascii=False,indent=2))+'</pre>')
  parts.append('<p><b>Coordinates generated:</b> 0<br><b>Legacy C coordinate referenced:</b> 0</p>')
  parts.append('<details><summary>Canonical identity hashes</summary><div class="mono">source point: '+p["source_point_sha256"]+'<br>canonical semantic: '+p["canonical_semantic_sha256"]+'</div></details>')
  parts.append('<div class="checks">[ ] semantic decomposition correct<br>[ ] operator semantics correct<br>[ ] operand identity correct<br>[ ] dependency structure correct<br>[ ] unresolved/conditional handling correct<br>[ ] ACCEPT<br>[ ] REJECT</div></section>')
 out.write_text("".join(parts),encoding="utf-8")

def render_pdf(data,out):
 from reportlab.lib.pagesizes import A4
 from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
 from reportlab.lib.units import mm
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,KeepTogether
 from reportlab.pdfbase import pdfmetrics
 from reportlab.pdfbase.ttfonts import TTFont
 font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
 if os.path.exists(font):pdfmetrics.registerFont(TTFont("DV",font));base="DV"
 else:base="Helvetica"
 styles=getSampleStyleSheet()
 body=ParagraphStyle("BodyX",parent=styles["BodyText"],fontName=base,fontSize=8.2,leading=10.6,spaceAfter=2)
 h1=ParagraphStyle("H1X",parent=styles["Heading1"],fontName=base,fontSize=15,leading=18,spaceAfter=6)
 h2=ParagraphStyle("H2X",parent=styles["Heading2"],fontName=base,fontSize=11.5,leading=14,spaceBefore=5,spaceAfter=3)
 h3=ParagraphStyle("H3X",parent=styles["Heading3"],fontName=base,fontSize=9.4,leading=11.5,spaceBefore=3,spaceAfter=2)
 mono=ParagraphStyle("MonoX",parent=body,fontName=base,fontSize=6.8,leading=8.5,wordWrap="CJK")
 doc=SimpleDocTemplate(str(out),pagesize=A4,leftMargin=12*mm,rightMargin=12*mm,topMargin=12*mm,bottomMargin=12*mm)
 story=[Paragraph("C v3 Vertical Slice v1 - Stage 2 Human Semantic Review",h1),
        Paragraph("Renderer-only artifact from the frozen existing Stage 2 output. No Stage 2 execution is performed by this document builder.",body),
        Paragraph(f"Frozen Stage 2 source SHA-256: {data['stage2_source_sha256']}",mono),Spacer(1,5)]
 for p in data["points"]:
  story+=[PageBreak(),Paragraph(f"{p['point_id']} - {p['final_stage2_status']}",h1)]
  if p["conditional_present"]:story.append(Paragraph("CONDITIONAL state present in Stage 2 output.",h2))
  sid=p["primary_location_source_statement_id"];src=p["source_statements"].get(sid,{})
  story+=[Paragraph("WHO primary Location",h2),Paragraph(f"<b>{html.escape(str(sid))}</b>: {html.escape(str(src.get('text')))}",body),Spacer(1,3)]
  story.append(Paragraph("Semantic decomposition / operands",h2))
  for o in p["operands"]:
   lines=[
    f"<b>{html.escape(str(o['landmark_id']))}</b>",
    f"source: {html.escape(str(o.get('source_raw')))}",
    f"class: {html.escape(str(o.get('landmark_class')))} | status: {html.escape(str(o.get('status')))} | executor: {html.escape(str(o.get('executor')))}",
    f"identity: {html.escape(canon(o.get('identity')))}",
    f"reason: {html.escape(str(o.get('reason')))}"
   ]
   story.append(KeepTogether([Paragraph("<br/>".join(lines),mono),Spacer(1,3)]))
  story.append(Paragraph("Relation / operator chain",h2))
  for r in p["relations"]:
   lines=[
    f"<b>{html.escape(str(r['relation_id']))}</b>",
    f"status: {html.escape(str(r.get('status')))} | operator: {html.escape(str(r.get('operator') or r.get('executor')))}",
    f"operand IDs: {html.escape(', '.join(r['operand_ids']))}",
    f"direction: {html.escape(str(r.get('direction')))} | source statement: {html.escape(str(r.get('source_statement_id')))}",
    f"reason: {html.escape(str(r.get('reason')))}"
   ]
   story.append(KeepTogether([Paragraph("<br/>".join(lines),mono),Spacer(1,3)]))
  if p["measurements"]:
   story+=[Paragraph("Measurements / calibration use",h2)]
   for m in p["measurements"]:story.append(Paragraph(html.escape(canon(m)),mono))
  if p["conditions"]:
   story+=[Paragraph("Conditions",h2)]
   for co in p["conditions"]:story.append(Paragraph(html.escape(canon(co)),mono))
  story+=[Paragraph("Dependency edges (projection of existing explicit IDs)",h2)]
  for e in p["dependency_edges"]:
   story.append(Paragraph(html.escape(f"{e['from']} -> {e['to']} [{e['kind']}]"),mono))
  story+=[Paragraph("Recorded data order",h2),
          Paragraph("Stage 2 output does not record timestamped per-operation runtime order. The following preserves exact serialized Stage 2 data order.",body),
          Paragraph(html.escape(" -> ".join(p["recorded_data_order"])),mono),
          Paragraph("Final semantic execution result",h2),
          Paragraph(html.escape(canon(p["final_semantic_execution_result"])),mono)]
  if p["final_stage2_status"]!="RESOLVED":
   story+=[Paragraph("Blocking dependency",h2),Paragraph(html.escape(canon(p["blocking"])),mono)]
  story+=[Spacer(1,4),Paragraph("Coordinates generated: 0 | Legacy C coordinate referenced: 0",body),
          Spacer(1,6),Paragraph("[ ] semantic decomposition correct<br/>[ ] operator semantics correct<br/>[ ] operand identity correct<br/>[ ] dependency structure correct<br/>[ ] unresolved/conditional handling correct<br/>[ ] ACCEPT<br/>[ ] REJECT",body)]
 doc.build(story)

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--stage2",required=True)
 ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json")
 ap.add_argument("--summary",default="artifacts/c-v3/vertical-slice-v1/stage2-summary.json")
 ap.add_argument("--out-dir",default="artifacts/c-v3/vertical-slice-v1")
 args=ap.parse_args()
 stage2_path=Path(args.stage2);source=json.loads(stage2_path.read_text())
 graph=json.loads(Path(args.graph).read_text());summary=json.loads(Path(args.summary).read_text())
 bypid={x["point_id"]:x for x in source["points"]}
 if set(COHORT)!=set(bypid):raise SystemExit("Stage 2 source cohort mismatch")
 condsrc={x["condition_id"]:x for x in graph.get("conditions",[])}
 # source records grouped only to enrich display with frozen B raw/source text
 b_by_point={}
 for pid in COHORT:
  ss=[x for x in graph["source_statements"] if x["point_id"]==pid]
  sm={x["source_statement_id"] for x in ss}
  b_by_point[pid]={"source_statements":ss,
   "landmark_nodes":[x for x in graph["landmark_nodes"] if x["point_id"]==pid],
   "relation_instances":[x for x in graph["relation_instances"] if x["subject_node_id"]==f"P:{pid}"],
   "proportional_measurements":[x for x in graph.get("proportional_measurements",[]) if x["source_statement_id"] in sm],
   "conditions":[x for x in graph.get("conditions",[]) if x["source_statement_id"] in sm]}
 data={"schema_version":"1.0.0","artifact":"c-v3-vertical-slice-v1-stage2-human-review-data",
       "status":"HUMAN_REVIEW_PENDING","stage2_source_sha256":file_sha(stage2_path),
       "stage2_source_scope":source.get("scope"),"points":[]}
 for pid in COHORT:
  point=bypid[pid];proj=make_projection(point,b_by_point[pid],condsrc)
  proj["source_point_sha256"]=sha(point)
  semantic_core={k:proj[k] for k in ("point_id","final_stage2_status","conditional_present","primary_location_source_statement_id",
    "operands","relations","measurements","conditions","dependency_edges","recorded_data_order",
    "explicit_runtime_order_recorded","final_semantic_execution_result","blocking")}
  proj["canonical_semantic_sha256"]=sha(semantic_core)
  proj["source_point_record"]=point
  data["points"].append(proj)
 out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
 (out/"stage2-human-review-data.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
 render_html(data,out/"stage2-human-review.html")
 render_pdf(data,out/"stage2-human-review.pdf")
 print(json.dumps({"points":len(data["points"]),"resolved":sum(p["final_stage2_status"]=="RESOLVED" for p in data["points"]),
  "unresolved":sum(p["final_stage2_status"]=="UNRESOLVED" for p in data["points"]),
  "conditional_points":sum(p["conditional_present"] for p in data["points"]),"coordinates":0,"legacy_refs":0}))
if __name__=="__main__":main()
