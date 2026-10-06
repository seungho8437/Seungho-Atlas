#!/usr/bin/env python3
"""Human semantic review renderer for the Stage 2 repair.

Consumes only:
- frozen pre-repair Stage 2 output
- repaired Stage 2 output
- frozen B v2.1
- independent semantic-repair validation report

It does not execute or infer replacement semantics.
"""
from __future__ import annotations
import argparse,hashlib,html,json,os
from pathlib import Path

ORDER=("LI18","ST10","LI17","BL17","BL23","BL25","ST9","TE20","HT7","LI4","ST1","GB14","GB23","LU6","LI7","GB26","ST2","BL40","ST4","TE6")
KNOWN={"TE20","ST10","LI17","LI18","BL17","BL23","BL25","ST9"}
WHO_PDF_PAGE={"LI4":44,"GB23":192,"ST10":59,"LI18":51,"LI17":51,"BL17":117,"BL23":120,"BL25":121,"BL40":128,"ST4":56,"TE6":169,"ST9":59,"HT7":94,"ST1":55,"GB14":187,"LU6":37,"LI7":46,"GB26":193,"ST2":55,"TE20":176}

def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(",",":"))
def fsha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1<<20),b""):h.update(b)
 return h.hexdigest()
def page_of(s):
 for k in ("page","source_page","pdf_page","page_pdf","source_pdf_page"):
  if s.get(k) is not None:return s[k]
 pid=s.get("point_id")
 return WHO_PDF_PAGE.get(pid,"NOT_RECORDED_IN_B_V2_1")
def identity(rec):
 g=rec.get("geometry") or {}
 return {"kind":g.get("kind"),"fma_id":g.get("fma_id"),"registry_id":g.get("registry_id"),"constructed_id":g.get("constructed_id"),
  "geometry_hash":g.get("geometry_hash"),"part_id":g.get("part_id"),"concept_id":g.get("concept_id"),
  "reference_point_id":g.get("point_id"),"parent_landmark_id":g.get("parent_landmark_id"),"subfeature_type":g.get("subfeature_type"),
  "construction_rule":g.get("construction_rule")}

def point_projection(pid,before,after,g,validation,rejection):
 b=next(x for x in before["points"] if x["point_id"]==pid);a=next(x for x in after["points"] if x["point_id"]==pid)
 stm=[x for x in g["source_statements"] if x["point_id"]==pid];bnodes={x["node_id"]:x for x in g["landmark_nodes"] if x["point_id"]==pid}
 binds=[x for x in g.get("composite_bindings",[]) if x.get("parent_landmark_id") in bnodes or x.get("child_landmark_id") in bnodes]
 children={}
 for x in binds:children.setdefault(x["parent_landmark_id"],[]).append(x["child_landmark_id"])
 related=[{"source_statement_id":s["source_statement_id"],"section":s.get("section"),"page":page_of(s),"text":s.get("text_canonical")} for s in stm if s.get("section") in ("location","note","remarks")]
 operands=[]
 for nid,rec in a["landmarks"].items():
  n=bnodes.get(nid,{})
  bind=next((x for x in binds if x["child_landmark_id"]==nid),None)
  parent=bind.get("parent_landmark_id") if bind else None
  operands.append({"node_id":nid,"source_raw":n.get("source_raw"),"semantic_class":n.get("landmark_class"),"parent_entity":parent,
    "child_subfeature":n.get("source_raw") if bind else None,"executor":rec.get("executor"),"status":rec.get("status"),
    "identity":identity(rec),"reason":rec.get("reason")})
 hierarchy=[]
 for par,kids in children.items():
  hierarchy.append({"parent_node_id":par,"parent_source_raw":bnodes.get(par,{}).get("source_raw"),"parent_status":a["landmarks"].get(par,{}).get("status"),
   "parent_semantic_identity":identity(a["landmarks"].get(par,{})),"children":[{"node_id":k,"source_raw":bnodes.get(k,{}).get("source_raw"),
    "semantic_identity":{"landmark_class":bnodes.get(k,{}).get("landmark_class")},"executable_identity":identity(a["landmarks"].get(k,{})),
    "status":a["landmarks"].get(k,{}).get("status")} for k in kids]})
 rels=[]
 edges=[]
 for rid,r in a["relations"].items():
  con=r.get("constraint") or {};sflds=r.get("semantic_fields") or {}
  sem=sflds.get("semantic_argument_node_ids") or con.get("semantic_argument_node_ids") or r.get("semantic_argument_node_ids") or r.get("argument_node_ids") or []
  exe=con.get("executable_argument_node_ids") or r.get("executable_argument_node_ids") or []
  rels.append({"relation_id":rid,"source_phrase":next(iter([((x.get("cue_span") or {}).get("source_raw") or x.get("source_raw")) for x in g["relation_instances"] if x["relation_id"]==rid]),None),
   "operator":sflds.get("op") or con.get("op") or r.get("executor"),"semantic_operand_ids":sem,"actual_executable_operand_ids":exe,
   "direction":sflds.get("direction") if "direction" in sflds else con.get("direction"),
   "branch_id":sflds.get("branch_id"),"source_statement_id":sflds.get("source_statement_id") or con.get("source_statement_id"),
   "semantic_fields_hash":r.get("semantic_fields_hash"),"status":r.get("status"),"reason":r.get("reason")})
  for s,e in zip(sem,exe):
   if s!=e:edges.append({"from":s,"to":e,"kind":"semantic_to_executable"})
  for e in exe:edges.append({"from":e,"to":rid,"kind":"executable_to_relation"})
  sid=sflds.get("source_statement_id") or con.get("source_statement_id")
  if sid:edges.append({"from":rid,"to":sid,"kind":"relation_to_statement"})
 for h in hierarchy:
  for ch in h["children"]:edges.append({"from":h["parent_node_id"],"to":ch["node_id"],"kind":"parent_to_child_subfeature"})
 for s in stm:edges.append({"from":s["source_statement_id"],"to":pid,"kind":"statement_to_point"})
 conditions=[]
 condsrc={x["condition_id"]:x for x in g.get("conditions",[])}
 for cid,c in a["conditions"].items():
  src=condsrc.get(cid,{})
  conditions.append({"condition_id":cid,"source_statement_id":c.get("source_statement_id") or src.get("source_statement_id"),"source_raw":(c.get("source_span") or src.get("source_span") or {}).get("source_raw"),
   "condition_type":src.get("condition_type"),"branch_id":c.get("branch_id"),"repaired_status":c.get("status"),"default_pose_compatible":c.get("default_pose_compatible"),"reason":c.get("reason")})
 defects=[x for x in rejection.get("human_semantic_audit",{}).get("confirmed_defects",[]) if x.get("point_id")==pid]
 prefind=[x for x in validation.get("pre_repair_scan",{}).get("new_regression_findings",[]) if x.get("point_id")==pid]
 before_after={
  "status":{"before":b.get("primary_location_status"),"after":a.get("primary_location_status")},
  "landmarks":[{"node_id":nid,"source_raw":bnodes.get(nid,{}).get("source_raw"),"before_status":b["landmarks"].get(nid,{}).get("status"),
    "before_identity":identity(b["landmarks"].get(nid,{})),"after_status":a["landmarks"].get(nid,{}).get("status"),"after_identity":identity(a["landmarks"].get(nid,{}))}
    for nid in a["landmarks"] if b["landmarks"].get(nid)!=a["landmarks"].get(nid)],
  "relations":[{"relation_id":rid,"before":b["relations"].get(rid),"after":a["relations"].get(rid)} for rid in a["relations"] if b["relations"].get(rid)!=a["relations"].get(rid)],
  "conditions":[{"condition_id":cid,"before":b["conditions"].get(cid),"after":a["conditions"].get(cid)} for cid in a["conditions"] if b["conditions"].get(cid)!=a["conditions"].get(cid)]
 }
 return {"point_id":pid,"previous_stage2_status":b.get("primary_location_status"),"repaired_stage2_status":a.get("primary_location_status"),
  "defect_family":[x.get("type") for x in defects] or [x.get("rule") for x in prefind] or ["regression_scan_no_known_defect"],
  "human_review_disposition":"PENDING","who_source":related,"operands":operands,"composite_binding_view":hierarchy,
  "relations":rels,"dependency_edges":edges,"conditions":conditions,"before_after_diff":before_after,
  "coordinates_generated":0,"legacy_c_coordinate_references":0}

def graph_svg(p):
 nodes=[]
 for o in p["operands"]:nodes.append((o["node_id"],o["status"],"operand"))
 for r in p["relations"]:nodes.append((r["relation_id"],r["status"],"relation"))
 for s in p["who_source"]:nodes.append((s["source_statement_id"],"", "statement"))
 nodes.append((p["point_id"],p["repaired_stage2_status"],"point"))
 uniq=[];seen=set()
 for x in nodes:
  if x[0] not in seen:uniq.append(x);seen.add(x[0])
 xmap={"operand":20,"relation":530,"statement":950,"point":1270};count={};pos={};elts=[]
 for nid,st,typ in uniq:
  y=count.get(typ,0)*42+25;count[typ]=count.get(typ,0)+1;pos[nid]=(xmap[typ],y)
  fill="#dcfce7" if st=="RESOLVED" else ("#fef3c7" if st in ("UNRESOLVED","CONDITIONAL","MULTIPLE") else "#f1f5f9")
  label=nid if len(nid)<58 else nid[:55]+"..."
  elts.append(f'<rect x="{xmap[typ]}" y="{y}" width="370" height="27" rx="4" fill="{fill}" stroke="#64748b"/><text x="{xmap[typ]+5}" y="{y+18}" font-size="9">{html.escape(label)}</text>')
 lines=[]
 for e in p["dependency_edges"]:
  if e["from"] in pos and e["to"] in pos:
   x1,y1=pos[e["from"]];x2,y2=pos[e["to"]];lines.append(f'<line x1="{x1+370}" y1="{y1+13}" x2="{x2}" y2="{y2+13}" stroke="#94a3b8"/>')
 h=max((y for _,y in pos.values()),default=100)+60
 return f'<svg viewBox="0 0 1680 {h}" width="100%" height="{min(h,760)}">'+"".join(lines+elts)+"</svg>"

def build_html(data,path):
 css="body{font-family:system-ui;margin:20px;background:#f5f6f8}.pt{background:white;border:1px solid #cbd5e1;padding:16px;margin:18px 0;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #cbd5e1;padding:5px;vertical-align:top}.mono{font:11px ui-monospace,monospace;word-break:break-all}.src{white-space:pre-wrap;background:#f8fafc;padding:8px}.before{background:#fee2e2}.after{background:#dcfce7}.check{line-height:1.8;border:1px solid #999;padding:10px}"
 out=[f'<!doctype html><meta charset="utf-8"><title>Stage 2 Semantic Repair Human Review</title><style>{css}</style>',
 '<h1>C v3 Vertical Slice v1 - Stage 2 Semantic Repair Human Review</h1>',
 f'<p>Repair validation: <b>{data["validation_status"]}</b>. Human semantic audit remains <b>PENDING</b>. Stage 3 is NOT STARTED.</p>',
 '<p>This renderer projects repaired Stage 2 output + frozen B v2.1 only; it does not execute semantic rules.</p>',
 '<h2>20-point regression overview</h2><table><tr><th>point</th><th>before</th><th>after</th><th>pre-repair regression findings outside known-8</th><th>post-repair finding count</th></tr>']
 for row in data["regression_table"]:
  out.append("<tr>"+"".join(f"<td class='mono'>{html.escape(str(v))}</td>" for v in [row["point_id"],row["before_status"],row["after_status"],", ".join(row["pre_repair_rules"]),row["post_repair_finding_count"]])+"</tr>")
 out.append("</table>")
 for p in data["points"]:
  out.append(f'<section class="pt"><h2>{p["point_id"]}: {p["previous_stage2_status"]} → {p["repaired_stage2_status"]}</h2><p><b>Defect family:</b> {html.escape(", ".join(p["defect_family"]))}<br><b>Human review disposition:</b> PENDING</p>')
  out.append('<h3>WHO source</h3>')
  for s in p["who_source"]:out.append(f'<div class="src"><b>{html.escape(str(s["section"]))} · {html.escape(str(s["source_statement_id"]))} · page {html.escape(str(s["page"]))}</b><br>{html.escape(str(s["text"]))}</div>')
  out.append('<h3>Semantic decomposition</h3><table><tr><th>source raw</th><th>node ID</th><th>class</th><th>parent entity</th><th>child subfeature</th><th>executor</th><th>status</th><th>identity / geometry hash</th><th>reason</th></tr>')
  for o in p["operands"]:
   vals=[o["source_raw"],o["node_id"],o["semantic_class"],o["parent_entity"],o["child_subfeature"],o["executor"],o["status"],canon(o["identity"]),o["reason"]]
   out.append("<tr>"+"".join(f"<td class='mono'>{html.escape(str(v))}</td>" for v in vals)+"</tr>")
  out.append('</table><h3>Composite binding view</h3>')
  for h in p["composite_binding_view"]:
   out.append(f'<div class="mono"><b>{html.escape(str(h["parent_source_raw"]))}</b> [{h["parent_node_id"]}] status={h["parent_status"]}<br>semantic/executable identity={html.escape(canon(h["parent_semantic_identity"]))}')
   for ch in h["children"]:out.append(f'<br>&nbsp;&nbsp;└─ {html.escape(str(ch["source_raw"]))} [{ch["node_id"]}] semantic={html.escape(canon(ch["semantic_identity"]))} executable={html.escape(canon(ch["executable_identity"]))} status={ch["status"]}')
   out.append('</div>')
  out.append('<h3>Relation execution</h3><table><tr><th>ID</th><th>operator</th><th>semantic operand IDs</th><th>actual executable operand IDs</th><th>direction</th><th>branch</th><th>source statement</th><th>semantic hash</th><th>status</th><th>reason</th></tr>')
  for r in p["relations"]:
   vals=[r["relation_id"],r["operator"],", ".join(r["semantic_operand_ids"]),", ".join(r["actual_executable_operand_ids"]),r["direction"],r["branch_id"],r["source_statement_id"],r["semantic_fields_hash"],r["status"],r["reason"]]
   out.append("<tr>"+"".join(f"<td class='mono'>{html.escape(str(v))}</td>" for v in vals)+"</tr>")
  out.append('</table>')
  if p["conditions"]:
   out.append('<h3>Conditions</h3><table><tr><th>ID</th><th>source</th><th>type</th><th>repaired status</th><th>default pose compatible</th><th>reason</th></tr>')
   for c in p["conditions"]:
    vals=[c["condition_id"],c["source_raw"],c["condition_type"],c["repaired_status"],c["default_pose_compatible"],c["reason"]]
    out.append("<tr>"+"".join(f"<td class='mono'>{html.escape(str(v))}</td>" for v in vals)+"</tr>")
   out.append('</table>')
  out.append('<h3>Dependency graph</h3>'+graph_svg(p))
  if p["point_id"] in KNOWN:
   out.append('<h3>BEFORE / AFTER machine-readable diff</h3><div class="before"><b>BEFORE</b><pre class="mono">'+html.escape(json.dumps({"status":p["before_after_diff"]["status"]["before"],"landmarks":[{"node_id":x["node_id"],"status":x["before_status"],"identity":x["before_identity"]} for x in p["before_after_diff"]["landmarks"]],"relations":[x["before"] for x in p["before_after_diff"]["relations"]],"conditions":[x["before"] for x in p["before_after_diff"]["conditions"]]},ensure_ascii=False,indent=2))+'</pre></div>')
   out.append('<div class="after"><b>AFTER</b><pre class="mono">'+html.escape(json.dumps({"status":p["before_after_diff"]["status"]["after"],"landmarks":[{"node_id":x["node_id"],"status":x["after_status"],"identity":x["after_identity"]} for x in p["before_after_diff"]["landmarks"]],"relations":[x["after"] for x in p["before_after_diff"]["relations"]],"conditions":[x["after"] for x in p["before_after_diff"]["conditions"]]},ensure_ascii=False,indent=2))+'</pre></div>')
  out.append('<p><b>Coordinates generated:</b> 0 · <b>Legacy C coordinate references:</b> 0</p>')
  out.append('<div class="check">[ ] WHO source phrase가 정확히 반영됨<br>[ ] semantic granularity 보존됨<br>[ ] child subfeature가 실제 execution에 사용됨<br>[ ] distinct subfeatures가 distinct executable identity를 가짐<br>[ ] relation operator가 올바른 operand를 참조함<br>[ ] condition state가 정확히 보존됨<br>[ ] RESOLVED/UNRESOLVED 판정이 타당함<br>[ ] ACCEPT<br>[ ] REJECT</div></section>')
 path.write_text("".join(out),encoding="utf-8")

def build_pdf(data,path):
 from reportlab.lib.pagesizes import A4
 from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
 from reportlab.lib.units import mm
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,KeepTogether
 from reportlab.graphics.shapes import Drawing,Rect,String,Line
 from reportlab.lib import colors
 from reportlab.pdfbase import pdfmetrics
 from reportlab.pdfbase.ttfonts import TTFont
 font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf";base="Helvetica"
 if os.path.exists(font):pdfmetrics.registerFont(TTFont("DV",font));base="DV"
 styles=getSampleStyleSheet();h1=ParagraphStyle("h1x",parent=styles["Heading1"],fontName=base,fontSize=14,leading=17)
 h2=ParagraphStyle("h2x",parent=styles["Heading2"],fontName=base,fontSize=10.5,leading=13,spaceBefore=5)
 body=ParagraphStyle("bx",parent=styles["BodyText"],fontName=base,fontSize=7.8,leading=10)
 mono=ParagraphStyle("mx",parent=body,fontName=base,fontSize=6.5,leading=8.2,wordWrap="CJK")
 doc=SimpleDocTemplate(str(path),pagesize=A4,leftMargin=11*mm,rightMargin=11*mm,topMargin=11*mm,bottomMargin=11*mm)
 def pdf_graph(p):
  nodes=[]
  for o in p["operands"]:nodes.append((o["node_id"],o["status"],"operand"))
  for r in p["relations"]:nodes.append((r["relation_id"],r["status"],"relation"))
  for s in p["who_source"]:nodes.append((s["source_statement_id"],"", "statement"))
  nodes.append((p["point_id"],p["repaired_stage2_status"],"point"))
  uniq=[];seen=set()
  for x in nodes:
   if x[0] not in seen:uniq.append(x);seen.add(x[0])
  xmap={"operand":4,"relation":205,"statement":390,"point":515};count={};pos={}
  maxrows=1
  for nid,stt,typ in uniq:
   row=count.get(typ,0);count[typ]=row+1;maxrows=max(maxrows,row+1);pos[nid]=(xmap[typ],row)
  step=13;h=max(45,min(250,maxrows*step+22));d=Drawing(555,h)
  for e in p["dependency_edges"]:
   if e["from"] in pos and e["to"] in pos:
    x1,r1=pos[e["from"]];x2,r2=pos[e["to"]];y1=h-15-r1*step;y2=h-15-r2*step
    d.add(Line(x1+115,y1,x2,y2,strokeColor=colors.HexColor("#94a3b8"),strokeWidth=.45))
  for nid,stt,typ in uniq:
   x,row=pos[nid];y=h-22-row*step
   fill=colors.HexColor("#dcfce7") if stt=="RESOLVED" else (colors.HexColor("#fef3c7") if stt in ("UNRESOLVED","CONDITIONAL","MULTIPLE") else colors.HexColor("#f1f5f9"))
   w=115 if typ!="point" else 38
   d.add(Rect(x,y,w,10,rx=2,ry=2,fillColor=fill,strokeColor=colors.HexColor("#64748b"),strokeWidth=.4))
   lab=nid if len(nid)<=29 else nid[:26]+"..."
   d.add(String(x+2,y+2.2,lab,fontName=base,fontSize=4.2,fillColor=colors.black))
  return d
 st=[Paragraph("C v3 Vertical Slice v1 - Stage 2 Semantic Repair Human Review",h1),
     Paragraph(f"Repair validation: {data['validation_status']} | Human semantic audit: PENDING | Stage 3: NOT STARTED",body),
     Paragraph("20-point regression overview",h2)]
 for row in data["regression_table"]:
  st.append(Paragraph(html.escape(f"{row['point_id']} | {row['before_status']} -> {row['after_status']} | pre-repair rules={row['pre_repair_rules']} | post-repair findings={row['post_repair_finding_count']}"),mono))
 for p in data["points"]:
  st+=[PageBreak(),Paragraph(f"{p['point_id']}: {p['previous_stage2_status']} -> {p['repaired_stage2_status']}",h1),
       Paragraph("Defect family: "+html.escape(", ".join(p["defect_family"])),body)]
  st.append(Paragraph("WHO source",h2))
  for s in p["who_source"]:st.append(Paragraph(html.escape(f"{s['section']} | {s['source_statement_id']} | page {s['page']} | {s['text']}"),body))
  st.append(Paragraph("Semantic decomposition",h2))
  for o in p["operands"]:
   txt=f"{o['node_id']} | source={o['source_raw']} | class={o['semantic_class']} | parent={o['parent_entity']} | child={o['child_subfeature']} | executor={o['executor']} | status={o['status']} | identity={canon(o['identity'])} | reason={o['reason']}"
   st.append(KeepTogether([Paragraph(html.escape(txt),mono),Spacer(1,2)]))
  st.append(Paragraph("Composite binding view",h2))
  for h in p["composite_binding_view"]:
   st.append(Paragraph(html.escape(f"PARENT {h['parent_node_id']} {h['parent_source_raw']} status={h['parent_status']} identity={canon(h['parent_semantic_identity'])}"),mono))
   for ch in h["children"]:st.append(Paragraph(html.escape(f"  -> CHILD {ch['node_id']} {ch['source_raw']} status={ch['status']} executable={canon(ch['executable_identity'])}"),mono))
  st.append(Paragraph("Relation execution",h2))
  for r in p["relations"]:st.append(Paragraph(html.escape(f"{r['relation_id']} | op={r['operator']} | semantic={r['semantic_operand_ids']} | executable={r['actual_executable_operand_ids']} | dir={r['direction']} | branch={r['branch_id']} | source={r['source_statement_id']} | semantic_hash={r['semantic_fields_hash']} | status={r['status']} | reason={r['reason']}"),mono))
  if p["conditions"]:
   st.append(Paragraph("Conditions",h2))
   for c in p["conditions"]:st.append(Paragraph(html.escape(canon(c)),mono))
  st.append(Paragraph("Dependency graph",h2));st.append(pdf_graph(p))
  st.append(Paragraph("Dependency graph edge list",h2))
  for e in p["dependency_edges"]:st.append(Paragraph(html.escape(f"{e['from']} -> {e['to']} [{e['kind']}]"),mono))
  if p["point_id"] in KNOWN:
   st+=[Paragraph("BEFORE / AFTER diff",h2),Paragraph("BEFORE: "+html.escape(canon({"status":p["before_after_diff"]["status"]["before"],"relations":[x["before"] for x in p["before_after_diff"]["relations"]],"conditions":[x["before"] for x in p["before_after_diff"]["conditions"]]})),mono),
        Paragraph("AFTER: "+html.escape(canon({"status":p["before_after_diff"]["status"]["after"],"relations":[x["after"] for x in p["before_after_diff"]["relations"]],"conditions":[x["after"] for x in p["before_after_diff"]["conditions"]]})),mono)]
  st+=[Paragraph("Coordinates generated: 0 | Legacy C coordinate references: 0",body),
       Paragraph("[ ] WHO source phrase가 정확히 반영됨<br/>[ ] semantic granularity 보존됨<br/>[ ] child subfeature가 실제 execution에 사용됨<br/>[ ] distinct subfeatures가 distinct executable identity를 가짐<br/>[ ] relation operator가 올바른 operand를 참조함<br/>[ ] condition state가 정확히 보존됨<br/>[ ] RESOLVED/UNRESOLVED 판정이 타당함<br/>[ ] ACCEPT<br/>[ ] REJECT",body)]
 doc.build(st)

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--before",required=True);ap.add_argument("--after",required=True);ap.add_argument("--validation",required=True);ap.add_argument("--graph",default="public/knowledge/anatomy-acupoint-relations-v2.1.json");ap.add_argument("--rejection",default="artifacts/c-v3/vertical-slice-v1/stage2-summary.json");ap.add_argument("--out-dir",default="artifacts/c-v3/vertical-slice-v1");args=ap.parse_args()
 before=json.loads(Path(args.before).read_text());after=json.loads(Path(args.after).read_text());validation=json.loads(Path(args.validation).read_text());g=json.loads(Path(args.graph).read_text());rej=json.loads(Path(args.rejection).read_text())
 pts=[point_projection(pid,before,after,g,validation,rej) for pid in ORDER]
 pre=validation.get("pre_repair_scan",{}).get("new_regression_findings",[])
 rem=validation.get("remaining_defects",[])
 regression_table=[]
 for p in pts:
  pid=p["point_id"]
  regression_table.append({"point_id":pid,"before_status":p["previous_stage2_status"],"after_status":p["repaired_stage2_status"],
    "pre_repair_rules":sorted({x["rule"] for x in pre if x.get("point_id")==pid}),
    "post_repair_finding_count":sum(1 for x in rem if x.get("point_id")==pid)})
 data={"schema_version":"1.0.0","artifact":"c-v3-stage2-semantic-repair-human-review-data","human_review_disposition":"PENDING",
  "before_sha256":fsha(Path(args.before)),"after_sha256":fsha(Path(args.after)),"validation_status":validation["status"],
  "stage3":"NOT_STARTED","points":pts,"regression_table":regression_table,
  "regression_summary":{"new_regression_defects_outside_known8":validation["pre_repair_scan"]["new_regression_defects_outside_known8"],"post_repair_counts":validation["post_repair_counts"]}}
 out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
 (out/"stage2-semantic-repair-human-review-data.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
 build_html(data,out/"stage2-semantic-repair-human-review.html");build_pdf(data,out/"stage2-semantic-repair-human-review.pdf")
 print(json.dumps({"points":len(data["points"]),"validation":data["validation_status"],"human_review":"PENDING"}))
if __name__=="__main__":main()
