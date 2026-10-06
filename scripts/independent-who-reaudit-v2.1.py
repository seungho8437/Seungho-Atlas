import json,re,collections,hashlib,csv,sys,os
from pathlib import Path
from pypdf import PdfReader

PDF=Path(os.environ.get('B_V2_1_WHO_PDF','/mnt/data/bv2_independent_audit/9789290613831-eng.pdf'))
GRAPH=Path(os.environ.get('B_V2_1_GRAPH','/mnt/data/bv2_independent_audit/v2_1/anatomy-acupoint-relations-v2.1.json'))
OUT=Path(os.environ.get('B_V2_1_REAUDIT_OUT','/mnt/data/bv2_independent_audit/v2_1/independent_reaudit_final'));OUT.mkdir(parents=True,exist_ok=True)
G=json.load(open(GRAPH,encoding='utf-8'))
S={s['source_statement_id']:s for s in G['source_statements']}; POINTS={p['point_id'] for p in G['points']}
byl=collections.defaultdict(list);byr=collections.defaultdict(list);byg=collections.defaultdict(list);byc=collections.defaultdict(list);bym=collections.defaultdict(list);bycb=collections.defaultdict(list)
for x in G['landmark_nodes']:byl[x['source_statement_id']].append(x)
for x in G['relation_instances']:byr[x['source_statement_id']].append(x)
for x in G['geometry_nodes']:byg[x['source_statement_id']].append(x)
for x in G['conditions']:byc[x['source_statement_id']].append(x)
for x in G['proportional_measurements']:bym[x['source_statement_id']].append(x)
for x in G['composite_bindings']:bycb[x['source_statement_id']].append(x)
LM={x['node_id']:x for x in G['landmark_nodes']}

def canon(s):
 s=str(s).replace('\u00ad','').replace('‐','-').replace('–','-').replace('—','-').replace('−','-');s=re.sub(r'(?<=[A-Za-z])-(?=[A-Za-z])','',s);return re.sub(r'\s+',' ',s).strip().lower()
def norm_pdf(s):
 s=str(s).replace('\u00ad','').replace('‐','-').replace('–','-').replace('—','-').replace('−','-');s=re.sub(r'(?<=[A-Za-z])-\s*(?=[A-Za-z])','',s);s=s.lower();s=re.sub(r'[^a-z0-9]+',' ',s);return re.sub(r'\s+',' ',s).strip()
def semantic_label(x):return canon(x.get('derived_semantic_label') or x.get('source_raw',''))
def span_exact(sid,sp):
 t=S[sid]['text_canonical'];return 0<=sp['char_start']<=sp['char_end']<=len(t) and canon(t[sp['char_start']:sp['char_end']])==canon(sp.get('source_raw',''))
def overlaps(a0,a1,b0,b1):return not(a1<=b0 or b1<=a0)
def arg_nodes(r):return [LM[a] for a in r.get('argument_node_ids',[]) if a in LM]
def arg_labels(r):return [semantic_label(x) for x in arg_nodes(r)]
def near_rel(sid,typ,start,end=None,tol=12):
 end=end if end is not None else start
 return [r for r in byr[sid] if r['relation_type']==typ and (overlaps(r['cue_span']['char_start'],r['cue_span']['char_end'],start,end) or abs(r['cue_span']['char_start']-start)<=tol)]

def defect(sid,cls,sev,desc,evidence=None,ids=None):
 s=S[sid]; defects.append({'statement_id':sid,'point_id':s['point_id'],'statement_type':s['section'],'source_page':s.get('source',{}).get('pdf_page') or s.get('audit_source_page'),'source_text':s['text_canonical'],'defect_class':cls,'severity':sev,'description':desc,'evidence':evidence or {},'affected_graph_ids':ids or []})

def add_family(sid,fam):family_hits[fam].add(sid)

def source_context_supports_label(sid,node):
 label=canon(node.get('derived_semantic_label') or '')
 if not label:return True
 text=canon(S[sid]['text_canonical'])
 # controlled bilateral elaboration from an explicitly plural paired source term
 controlled={'left','right'}
 toks=[t for t in re.findall(r'[a-z0-9]+',label) if t not in controlled and t not in {'the','of','a','an'}]
 # singular/plural and dehyphenated loose token support in full statement
 for tok in toks:
  variants={tok}
  if tok.endswith('s') and len(tok)>3:variants.add(tok[:-1])
  if tok=='apex':variants.add('apices')
  if tok=='basis':variants.add('bases')
  if not any(v in text for v in variants):return False
 return True

defects=[];family_hits=collections.defaultdict(set)

# 1. WHO PDF direct source verification for all 583
reader=PdfReader(str(PDF));pages=[p.extract_text() or '' for p in reader.pages]
for sid,s in S.items():
 txt=norm_pdf(s['text_canonical']);pp=s.get('source',{}).get('pdf_page') or s.get('audit_source_page');ok=False
 idxs=[pp-1] if pp and 1<=pp<=len(pages) else range(len(pages))
 for i in idxs:
  if txt in norm_pdf(pages[i]):ok=True;break
 if not ok and pp:
  for i in range(max(0,pp-3),min(len(pages),pp+2)):
   if txt in norm_pdf(pages[i]):ok=True;break
 if not ok:defect(sid,'PRIMARY_SOURCE_TEXT_MISMATCH','CRITICAL','Canonical statement is not directly recoverable from cited WHO primary-source page.')

# 2. source-span integrity for every graph semantic object
for sid in S:
 for x in byl[sid]:
  sp={'char_start':x['char_start'],'char_end':x['char_end'],'source_raw':x['source_raw']}
  if not span_exact(sid,sp):defect(sid,'SOURCE_SPAN_MISMATCH','MINOR','landmark source span/raw mismatch',{'node_id':x['node_id'],'actual':S[sid]['text_canonical'][x['char_start']:x['char_end']],'stored':x['source_raw']},[x['node_id']])
 for r in byr[sid]:
  if not span_exact(sid,r['cue_span']):defect(sid,'SOURCE_SPAN_MISMATCH','MINOR','relation cue span/raw mismatch',{'relation_id':r['relation_id']},[r['relation_id']])
 for x in byg[sid]:
  if x.get('source_span') and not span_exact(sid,x['source_span']):defect(sid,'SOURCE_SPAN_MISMATCH','MINOR','geometry source span/raw mismatch',{'geometry_id':x['node_id']},[x['node_id']])
 for x in byc[sid]:
  if not span_exact(sid,x['source_span']):defect(sid,'SOURCE_SPAN_MISMATCH','MINOR','condition source span/raw mismatch',{'condition_id':x['condition_id']},[x['condition_id']])
 for x in bym[sid]:
  if not span_exact(sid,x['cue_span']):defect(sid,'SOURCE_SPAN_MISMATCH','MINOR','measurement cue span/raw mismatch',{'measurement_id':x['measurement_id']},[x['measurement_id']])
  if x.get('source_value_span') and not span_exact(sid,x['source_value_span']):defect(sid,'SOURCE_SPAN_MISMATCH','MINOR','measurement value source span/raw mismatch',{'measurement_id':x['measurement_id']},[x['measurement_id']])
 for x in bycb[sid]:
  if not span_exact(sid,x['source_span']):defect(sid,'SOURCE_SPAN_MISMATCH','MINOR','composite-binding source span/raw mismatch',{'binding_id':x['binding_id']},[x['binding_id']])

# 3. derived landmark false-positive control
for x in G['landmark_nodes']:
 if 'derived' not in str(x.get('source_backing','')).lower():continue
 sid=x['source_statement_id']; add_family(sid,'derived_landmark')
 if not x.get('creation_reason') or not x.get('upstream_absence_provenance'):
  defect(sid,'DERIVED_LANDMARK_PROVENANCE_GAP','MAJOR','source-backed derived landmark lacks creation/upstream-absence provenance',{'node_id':x['node_id']},[x['node_id']])
 if not source_context_supports_label(sid,x):
  defect(sid,'DERIVED_LANDMARK_SEMANTIC_FABRICATION','MAJOR','derived semantic label introduces anatomy not supported by WHO statement text',{'node_id':x['node_id'],'derived_semantic_label':x.get('derived_semantic_label'),'source_raw':x.get('source_raw')},[x['node_id']])

# 4. exact semantic duplicate relation overgeneration
for sid in S:
 groups=collections.defaultdict(list)
 for r in byr[sid]:
  k=(r['subject_node_id'],r['relation_type'],tuple(r.get('argument_node_ids',[])),r['cue_span']['char_start'],r['cue_span']['char_end'],r.get('branch_id'))
  groups[k].append(r)
 for xs in groups.values():
  if len(xs)>1:defect(sid,'SOURCE_RELATION_OVERGENERATION','MAJOR','duplicate semantic relation instances for one WHO cue',{'count':len(xs),'cue':xs[0]['cue_span']},[x['relation_id'] for x in xs])

# 5. depression family: exactly one point→depression relation per explicit cue
for sid,s in S.items():
 t=s['text_canonical']
 for m in re.finditer(r'\b(?:in|at)\s+the\s+de-?pression\b',t,re.I):
  add_family(sid,'depression');dw=re.search(r'de-?pression',m.group(0),re.I);ds=m.start()+dw.start();de=m.start()+dw.end()
  nodes=[x for x in byl[sid] if overlaps(x['char_start'],x['char_end'],ds,de)]
  rels=[r for r in byr[sid] if r['relation_type']=='surface-landmark' and r['cue_span']['char_start']==m.start() and r['cue_span']['char_end']==m.end() and any(a['node_id'] in r.get('argument_node_ids',[]) for a in nodes)]
  # de-hyphenated source may shift the exact cue to an equivalent stored span by one char; allow exact semantic depression tag as fallback
  if not rels:rels=[r for r in byr[sid] if r['relation_type']=='surface-landmark' and r.get('source_semantics')=='depression' and overlaps(r['cue_span']['char_start'],r['cue_span']['char_end'],m.start(),m.end()) and any(a['node_id'] in r.get('argument_node_ids',[]) for a in nodes)]
  if len(rels)!=1:defect(sid,'DEPRESSION_RELATION_INTEGRITY','MAJOR','explicit depression must have exactly one dedicated point→depression surface relation',{'source_span':[m.start(),m.end()],'matching_relation_count':len(rels)},[r['relation_id'] for r in rels])

# 6. all explicit numeric B/F-cun mentions: exact one-to-one inventory
mpat=re.compile(r'(?P<num>\d+(?:\.\d+)?)\s+(?P<unit>[BFbf]-cun)\b',re.I);source_measure_keys=[];matched_ids=set()
for sid,s in S.items():
 for m in mpat.finditer(s['text_canonical']):
  add_family(sid,'proportional_measurement');val=float(m.group('num'));unit=m.group('unit').lower();source_measure_keys.append((sid,m.start(),m.end(),val,unit))
  xs=[x for x in bym[sid] if abs(x['value']-val)<1e-9 and x['unit'].lower()==unit and x['cue_span']['char_start']<=m.start()<=x['cue_span']['char_end']]
  if len(xs)!=1:defect(sid,'PROPORTIONAL_MEASUREMENT_INTEGRITY','CRITICAL','explicit B/F-cun mention does not map to exactly one graph measurement',{'source_raw':m.group(0),'span':[m.start(),m.end()],'matches':len(xs)},[x['measurement_id'] for x in xs])
  else:
   matched_ids.add(xs[0]['measurement_id'])
   if xs[0].get('anchor_landmark_id') is None:defect(sid,'PROPORTIONAL_MEASUREMENT_INTEGRITY','MAJOR','proportional measurement lacks source-backed anchor',{'measurement_id':xs[0]['measurement_id']},[xs[0]['measurement_id']])
for x in G['proportional_measurements']:
 if x['measurement_id'] not in matched_ids:defect(x['source_statement_id'],'PROPORTIONAL_MEASUREMENT_OVERGENERATION','MAJOR','graph proportional measurement has no unique explicit WHO numeric B/F-cun mention',{'measurement_id':x['measurement_id']},[x['measurement_id']])

# 7. genuine reference acupoints: source-backed node + dedicated nongeometric reference relation
known='LU|LI|ST|SP|HT|SI|BL|KI|PC|TE|GB|LR|GV|CV';ptpat=re.compile(rf'\b({known})\s?(\d{{1,2}})\b',re.I)
source_refs=[]
for sid,s in S.items():
 subj=s['point_id'].upper();t=s['text_canonical']
 for m in ptpat.finditer(t):
  ref=(m.group(1)+m.group(2)).upper()
  if ref==subj or ref not in POINTS:continue
  add_family(sid,'reference_acupoint');source_refs.append((sid,m.start(),m.end(),ref))
  ns=[x for x in byl[sid] if x.get('cross_reference_point_id','').upper()==ref and overlaps(x['char_start'],x['char_end'],m.start(),m.end())]
  if len(ns)<1:defect(sid,'REFERENCE_ACUPOINT_OMISSION_OR_MISBINDING','MAJOR',f'reference acupoint {ref} lacks source-backed landmark node',{'span':[m.start(),m.end()]})
  else:
   rr=[r for r in byr[sid] if r['relation_type']=='reference-acupoint' and any(n['node_id'] in r.get('argument_node_ids',[]) for n in ns)]
   if len(rr)!=1:defect(sid,'REFERENCE_ACUPOINT_OMISSION_OR_MISBINDING','MAJOR',f'reference acupoint {ref} lacks exactly one reference relation',{'span':[m.start(),m.end()],'relation_count':len(rr)},[r['relation_id'] for r in rr])
# no source-free reference relation
ref_keys={(sid,ref) for sid,_,_,ref in source_refs}
for r in G['relation_instances']:
 if r['relation_type']!='reference-acupoint':continue
 ns=arg_nodes(r);ref=ns[0].get('cross_reference_point_id') if ns else None
 if not ref or (r['source_statement_id'],ref.upper()) not in ref_keys:defect(r['source_statement_id'],'SOURCE_RELATION_OVERGENERATION','MAJOR','reference-acupoint relation has no corresponding genuine WHO reference mention',{'relation_id':r['relation_id']},[r['relation_id']])

# 8. conditional semantics: source-first conservative high-confidence cues
cond_expect=[]
# exact repaired posture phrases plus generic strong condition families
explicit_body={
 'S:SI6:note:1':'With the palm facing downwards','S:BL38:note:1':'With the knee in slight flexion','S:BL57:note:1':'With the leg stretched (plantar flexion) or the heel up',
 'S:PC4:note:1':'With the fist clenched, the wrist su-pinated, and the elbow slightly flexed','S:PC5:note:1':'With the fist clenched, the wrist supinated and the elbow slightly flexed',
 'S:PC6:note:1':'With the fist clenched, the wrist supinated and the elbow slightly flexed','S:PC7:note:1':'With the fist clenched, the wrist slightly flexed',
 'S:TE15:note:1':'With the upper limb hanging by the side of trunk in a seated position','S:CV1:note:1':'with the subject lying on the side or in knee-chest position'}
for sid,phrase in explicit_body.items():
 t=S[sid]['text_canonical'];st=t.lower().find(phrase.lower());cond_expect.append((sid,'body_position',st,st+len(phrase)))
# sex / anatomical-variant / alternative cues from source
for sid,s in S.items():
 t=s['text_canonical']
 for m in re.finditer(r'\b(?:in\s+)?(?:males|male|females|female)\b',t,re.I):cond_expect.append((sid,'sex_specific',m.start(),m.end()))
 for m in re.finditer(r'\bif\s+[^.;,]{0,80}\b(?:is|are)\s+not\s+present\b|\bin\s+the\s+absence\s+of\b',t,re.I):cond_expect.append((sid,'anatomical_variant',m.start(),m.end()))
 for m in re.finditer(r'\balternative\s+location\b',t,re.I):cond_expect.append((sid,'alternative_location',m.start(),m.end()))
# validate expectations; branch binding required when statement has locator graph objects
for sid,typ,st,en in cond_expect:
 add_family(sid,'conditional');xs=[c for c in byc[sid] if c['condition_type']==typ and overlaps(c['source_span']['char_start'],c['source_span']['char_end'],st,en)]
 if not xs:defect(sid,'CONDITIONAL_BRANCH_FLATTENING','MAJOR',f'WHO {typ} condition is absent from graph',{'span':[st,en]})
 else:
  c=xs[0]
  if (byr[sid] or byl[sid]) and typ in ('body_position','sex_specific','anatomical_variant') and (not c.get('branch_relation_ids') or not c.get('branch_landmark_ids')):
   defect(sid,'CONDITIONAL_BRANCH_FLATTENING','MAJOR',f'{typ} condition exists but locator relations/landmarks are not bound to its branch',{'condition_id':c['condition_id']},[c['condition_id']])

# 9. directional and same-level source relations
patdir=re.compile(r'\b(?:directly\s+)?(?:superior|inferior|medial|lateral|proximal|distal|anterior|posterior|radial|ulnar)(?:ly)?\s+to\b',re.I)
for sid,s in S.items():
 for m in patdir.finditer(s['text_canonical']):
  add_family(sid,'directional');rels=near_rel(sid,'relative-to',m.start(),m.end(),12)
  if not rels:defect(sid,'SOURCE_RELATION_OMISSION','MAJOR','directional WHO cue lacks relative-to relation',{'cue':m.group(0),'span':[m.start(),m.end()]})
 for m in re.finditer(r'(?:at\s+)?the\s+same\s+level\s+as\b',s['text_canonical'],re.I):
  add_family(sid,'same_level');rels=near_rel(sid,'same-level',m.start(),m.end(),15)
  if not rels:defect(sid,'SOURCE_RELATION_OMISSION','MAJOR','same-level WHO cue lacks same-level relation',{'span':[m.start(),m.end()]})

# 10. between: explicit A-and-B syntax requires two distinct source-backed operands; set-valued 'two X' forms may use one set node
for sid,s in S.items():
 t=s['text_canonical']
 for m in re.finditer(r'\bbetween\b',t,re.I):
  add_family(sid,'between')
  # GV20 connecting-line 'between auricular apices' belongs to line geometry, not between point relation
  prefix=t[max(0,m.start()-30):m.start()].lower()
  if 'connecting line' in prefix:continue
  rels=near_rel(sid,'between',m.start(),m.start()+7,10)
  if not rels:defect(sid,'SOURCE_RELATION_OMISSION','MAJOR','between WHO cue lacks between relation',{'span':[m.start(),m.end()]});continue
  # Explicit 'and' in same between clause (to punctuation) => >=2 distinct arguments; otherwise set landmark acceptable.
  clause=t[m.end():];stop=re.search(r'[,;.]',clause);clause=clause[:stop.start()] if stop else clause
  explicit_and=bool(re.search(r'\band\b',clause,re.I))
  if explicit_and and max(len(set(r.get('argument_node_ids',[]))) for r in rels)<2:defect(sid,'ENDPOINT_CARDINALITY_MISMATCH','CRITICAL','explicit between A and B does not preserve two distinct arguments',{'clause':clause},[r['relation_id'] for r in rels])

# 11. line construction: any source-backed constructed/curved connecting line must have two distinct endpoints; transverse/longitudinal line may be anchored reference line
linecue=re.compile(r'\b(?:(?:curved\s+)?line\s+(?:con-?necting|connecting|from)|connecting\s+line(?:\s+between)?)\b',re.I)
for sid,s in S.items():
 t=s['text_canonical']
 for m in linecue.finditer(t):
  add_family(sid,'line_construction');cands=[x for x in byg[sid] if x.get('geometry_type') in ('constructed_line','curved_line') and (overlaps(x['source_span']['char_start'],x['source_span']['char_end'],m.start(),m.end()) or abs(x['source_span']['char_start']-m.start())<=12)]
  if not cands:defect(sid,'GEOMETRY_SEMANTICS_MISMATCH','CRITICAL','WHO connecting/from line lacks constructed-line geometry',{'span':[m.start(),m.end()]})
  elif not any(len(x.get('endpoint_node_ids',[]))==2 and len(set(x.get('endpoint_node_ids',[])))==2 and x.get('required_endpoint_count')==2 for x in cands):defect(sid,'ENDPOINT_CARDINALITY_MISMATCH','CRITICAL','WHO connecting/from line does not have exactly two distinct geometry endpoints',{'geometries':[x['node_id'] for x in cands]},[x['node_id'] for x in cands])
# LU1/LU2/general point located on a named line
locline=re.compile(r'\b(?:is|are)\s+located\s+(?:on|along)\s+(?:the\s+)?(?:curved\s+|transverse\s+|longitudinal\s+|vertical\s+|horizontal\s+)?line\b|\blocated\s+(?:on|along)\s+(?:the\s+)?(?:curved\s+|transverse\s+|longitudinal\s+|vertical\s+|horizontal\s+)?line\b',re.I)
for sid,s in S.items():
 for m in locline.finditer(s['text_canonical']):
  add_family(sid,'on_line');
  if not near_rel(sid,'on-line',m.start(),m.end(),30):defect(sid,'RELATION_TYPE_MISCLASSIFICATION','MAJOR','WHO point-on-line locator lacks on-line relation',{'span':[m.start(),m.end()]})

# 12. midpoint/midway semantics
for sid,s in S.items():
 for m in re.finditer(r'\b(?:midpoint|midway)\b',s['text_canonical'],re.I):
  add_family(sid,'midpoint');rels=[r for r in byr[sid] if r['relation_type'] in ('midpoint-between','midpoint-of-entity') and abs(r['cue_span']['char_start']-m.start())<=50]
  if not rels:defect(sid,'SOURCE_RELATION_OMISSION','CRITICAL','midpoint/midway WHO cue lacks midpoint relation',{'span':[m.start(),m.end()]})

# 13. intersection/junction: distinguish geometric intersection from fractional junction along a line
for sid,s in S.items():
 t=s['text_canonical']
 for m in re.finditer(r'\b(intersection|junction)\s+of\b',t,re.I):
  add_family(sid,'intersection_junction');window=t[m.start():m.start()+120].lower();fraction=(m.group(1).lower()=='junction' and bool(re.search(r'\b(?:one|two|three)\s+(?:third|thirds|fourth|fourths|quarter|quarters)\b|\b(?:upper|lower|medial|lateral|anterior|posterior)\s+(?:one|two|three)\s+(?:third|thirds|fourth|fourths|quarter|quarters)\b',window)))
  typ='fraction-along-line' if fraction else 'at-junction';rels=[r for r in byr[sid] if r['relation_type']==typ and abs(r['cue_span']['char_start']-m.start())<=20]
  if not rels:defect(sid,'RELATION_TYPE_MISCLASSIFICATION','MAJOR',f'WHO {m.group(1)} cue lacks {typ} relation',{'span':[m.start(),m.end()]})
  elif not fraction and max(len(set(r.get('argument_node_ids',[]))) for r in rels)<2:defect(sid,'ENDPOINT_CARDINALITY_MISMATCH','CRITICAL','intersection/junction lacks two distinct operands',{'span':[m.start(),m.end()]},[r['relation_id'] for r in rels])

# 14. at-border semantics: source-faithful combination surface border locator + between operands is accepted
for sid,s in S.items():
 for m in re.finditer(r'\bat\s+the\s+border\s+between\b',s['text_canonical'],re.I):
  add_family(sid,'at_border');surf=[r for r in byr[sid] if r['relation_type']=='surface-landmark' and 'at the border' in canon(r['cue_span']['source_raw'])];bet=[r for r in byr[sid] if r['relation_type']=='between' and r['cue_span']['char_start']>=m.start()]
  if not surf or not bet:defect(sid,'SOURCE_RELATION_OMISSION','MAJOR','WHO at-the-border-between semantics are not jointly represented by border locator and between operands',{'span':[m.start(),m.end()]})

# 15. composite parent-child coverage for conservative high-confidence source patterns
# A composite is source-faithful when parent semantics are preserved either by an explicit binding OR by a full source-backed
# relation/endpoint landmark whose semantic label carries the shared parent. This deliberately handles coordinated ellipsis
# such as "anterior and posterior borders of X" without pretending each derived endpoint has a literal contiguous phrase.
childwords='border|borders|head|heads|process|processes|base|bases|extremity|extremities|commissure|commissures|centre|center'
def composite_semantics_supported(sid,m):
    a,b=m.start(),m.end(); phrase=canon(m.group(0))
    # explicit binding overlapping phrase
    if any(overlaps(cb['source_span']['char_start'],cb['source_span']['char_end'],a,b) for cb in bycb[sid]):return True
    # source-backed relation operands / geometry endpoints preserve the full or reconstructed child-parent semantics
    used=set()
    for r in byr[sid]:used.update(r.get('argument_node_ids',[]))
    for ge in byg[sid]:used.update(ge.get('endpoint_node_ids',[]));used.update(ge.get('anchor_node_ids',[]))
    cands=[LM[n] for n in used if n in LM and overlaps(LM[n]['char_start'],LM[n]['char_end'],a,b)]
    # Full phrase/set landmark is acceptable
    if any(canon(x['source_raw']) in phrase or phrase in canon(x['source_raw']) for x in cands):return True
    # Derived semantic labels with child-of-parent structure are acceptable in coordinated/shared-head expressions
    semantic=[semantic_label(x) for x in cands]
    if any((' of ' in z and any(w in z for w in ('border','head','process','base','extremity','commissure','centre','center'))) for z in semantic):return True
    # At least two coordinated endpoints sourced from this phrase also preserve shared-head semantics through the relation cue.
    if len({x['node_id'] for x in cands})>=2 and (' and ' in phrase):return True
    return False
for sid,s in S.items():
 t=s['text_canonical']
 # Only clear child-of-parent forms in location-bearing clauses; descriptive plural anatomy not used by any relation is not promoted.
 for m in re.finditer(rf'\b(?:(?:superior|inferior|medial|lateral|anterior|posterior|proximal|distal|radial|ulnar|free|sternal|clavicular)\s+(?:and\s+(?:superior|inferior|medial|lateral|anterior|posterior|proximal|distal|radial|ulnar|free|sternal|clavicular)\s+)?)?(?:{childwords})\s+of\s+(?:the\s+)?[^,.;]+',t,re.I):
  # ignore purely explanatory phrase if no graph relation/geometry touches it
  touched=any(any(a in LM and overlaps(LM[a]['char_start'],LM[a]['char_end'],m.start(),m.end()) for a in r.get('argument_node_ids',[])) for r in byr[sid]) or any(any(a in LM and overlaps(LM[a]['char_start'],LM[a]['char_end'],m.start(),m.end()) for a in ge.get('endpoint_node_ids',[])+ge.get('anchor_node_ids',[])) for ge in byg[sid])
  if not touched:continue
  add_family(sid,'composite_parent')
  if not composite_semantics_supported(sid,m):defect(sid,'COMPOSITE_PARENT_BINDING_ERROR','MAJOR','WHO composite child-parent semantics are not preserved by binding or source-backed operand semantics',{'source_raw':m.group(0),'span':[m.start(),m.end()]})

# 16. every graph relation must have lexical/source semantic support for its type (anti-overgeneration)
def relation_supported(r):
 raw=canon(r['cue_span']['source_raw']);typ=r['relation_type']
 if typ=='relative-to':return bool(re.search(r'proximallateral|proximalmedial|anteroinferior|posteroinferior|posterosuperior|medioinferior|anterosuperior',raw.replace('-','')) or re.search(r'\b(superior|inferior|medial|lateral|proximal|distal|anterior|posterior|radial|ulnar|deep|superficial|posterosuperior|posteroinferior|medioinferior|anteroinferior|anterosuperior)\b',raw.replace('-','')))
 if typ=='surface-landmark':return bool(re.search(r'\b(on|in|at|within|where)\b',raw) or 'depression' in raw or 'sulcus' in raw or 'rests' in raw)
 if typ=='between':return 'between' in raw
 if typ=='same-level':return 'level' in raw
 if typ=='on-line':return 'line' in raw or 'curve' in raw
 if typ in ('midpoint-between','midpoint-of-entity'):return 'midpoint' in raw or 'midway' in raw
 if typ=='at-junction':return any(k in raw for k in ('intersection','junction','connecting point','angle formed','joint of'))
 if typ=='fraction-along-line':return 'junction' in raw or 'third' in raw or 'fourth' in raw
 if typ=='reference-acupoint':return bool(re.fullmatch(r'(?i)(?:LU|LI|ST|SP|HT|SI|BL|KI|PC|TE|GB|LR|GV|CV)\s?\d{1,2}',r['cue_span']['source_raw'].strip()))
 return True
for r in G['relation_instances']:
 if not relation_supported(r):defect(r['source_statement_id'],'SOURCE_RELATION_OVERGENERATION','MAJOR','graph relation type lacks lexical/source support in its own WHO cue span',{'relation_id':r['relation_id'],'type':r['relation_type'],'cue':r['cue_span']['source_raw']},[r['relation_id']])

# 17. geometry cardinality self-consistency
for x in G['geometry_nodes']:
 req=x.get('required_endpoint_count')
 if req is not None and len(x.get('endpoint_node_ids',[]))!=req:defect(x['source_statement_id'],'ENDPOINT_CARDINALITY_MISMATCH','CRITICAL','geometry endpoint count disagrees with required_endpoint_count',{'geometry_id':x['node_id'],'required':req,'observed':len(x.get('endpoint_node_ids',[]))},[x['node_id']])

# deterministic de-dup defects
uniq=[];seen=set()
for d in defects:
 k=(d['statement_id'],d['defect_class'],d['description'],json.dumps(d.get('evidence',{}),sort_keys=True,default=str))
 if k not in seen:seen.add(k);uniq.append(d)
defects=sorted(uniq,key=lambda d:({'CRITICAL':0,'MAJOR':1,'MINOR':2}[d['severity']],d['statement_id'],d['defect_class'],json.dumps(d['evidence'],sort_keys=True,default=str)))
for i,d in enumerate(defects,1):d['reaudit_defect_id']=f'REAUDIT-{i:04d}'
sev=collections.Counter(d['severity'] for d in defects);cls=collections.Counter(d['defect_class'] for d in defects)
mandatory_points=['CV1','CV12','ST35','GB26','ST29','GV20','LU11','LI1','ST8','BL1','LU1','LU2','PC4','BL38','BL57']
mandatory={p:{'PASS':not any(d['point_id']==p and d['severity'] in ('CRITICAL','MAJOR') for d in defects),'defects':[d['reaudit_defect_id'] for d in defects if d['point_id']==p]} for p in mandatory_points}
derived=[x for x in G['landmark_nodes'] if 'derived' in str(x.get('source_backing','')).lower()]
derived_def=[d for d in defects if d['defect_class'].startswith('DERIVED_LANDMARK') or (d['defect_class']=='SOURCE_SPAN_MISMATCH' and any(i in {x['node_id'] for x in derived} for i in d.get('affected_graph_ids',[])))]
family_result={k:{'statements_scanned':len(v),'PASS':not any(d['statement_id'] in v and d['severity'] in ('CRITICAL','MAJOR') for d in defects)} for k,v in sorted(family_hits.items())}
summary={'independently_audited_statements':len(S),'primary_source_direct_matches':len(S)-sum(d['defect_class']=='PRIMARY_SOURCE_TEXT_MISMATCH' for d in defects),'new_defects_total':len(defects),'severity_counts':dict(sev),'defect_class_counts':dict(cls),'affected_points':sorted(set(d['point_id'] for d in defects)),'affected_points_count':len(set(d['point_id'] for d in defects)),'mandatory_regression':mandatory,'derived_landmark_audit':{'total':len(derived),'defects':len(derived_def),'semantic_fabrication':sum(d['defect_class']=='DERIVED_LANDMARK_SEMANTIC_FABRICATION' for d in derived_def),'provenance_gaps':sum(d['defect_class']=='DERIVED_LANDMARK_PROVENANCE_GAP' for d in derived_def)},'relation_family_results':family_result,'final_judgment':'B_V2_1_FREEZE_APPROVED' if not any(d['severity'] in ('CRITICAL','MAJOR') for d in defects) and sum(d['severity']=='MINOR' for d in defects)==0 and all(x['PASS'] for x in mandatory.values()) else 'B_V2_1_FREEZE_REJECTED'}
json.dump({'schema_version':'2.1-independent-reaudit','independence_contract':{'semantic_source_of_truth':['9789290613831-eng.pdf','anatomy-acupoint-relations-v2.1.json'],'uses_B_v2_1_validator_expected_values':False,'uses_prior_audit_expected_representation':False},'summary':summary,'defects':defects},open(OUT/'b-v2.1-independent-who-reaudit.json','w'),ensure_ascii=False,indent=2)
with open(OUT/'b-v2.1-independent-who-defects.csv','w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=['reaudit_defect_id','point_id','statement_type','statement_id','source_page','defect_class','severity','description','source_text','evidence','affected_graph_ids']);w.writeheader()
 for d in defects:
  z=d.copy();z['evidence']=json.dumps(z['evidence'],ensure_ascii=False);z['affected_graph_ids']=json.dumps(z['affected_graph_ids'],ensure_ascii=False);w.writerow({k:z.get(k) for k in w.fieldnames})
report=['# B v2.1 independent WHO-primary-source re-audit','',f"Final judgment: **{summary['final_judgment']}**",'',f"- Independently audited statements: {len(S)}/583",f"- Direct WHO primary-source statement matches: {summary['primary_source_direct_matches']}/583",f"- New defects: {len(defects)}",f"- Severity: {dict(sev)}",'', '## Permanent 15-point regression']+[f"- {p}: {'PASS' if x['PASS'] else 'FAIL'}" for p,x in mandatory.items()]+['','## Relation-family source-only checks']+[f"- {k}: {'PASS' if v['PASS'] else 'FAIL'} ({v['statements_scanned']} statements)" for k,v in family_result.items()]+['','## Derived landmarks',f"- audited: {len(derived)}",f"- defects: {len(derived_def)}",f"- semantic fabrication: {summary['derived_landmark_audit']['semantic_fabrication']}",f"- provenance gaps: {summary['derived_landmark_audit']['provenance_gaps']}"]
(OUT/'b-v2.1-independent-who-reaudit-report.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))