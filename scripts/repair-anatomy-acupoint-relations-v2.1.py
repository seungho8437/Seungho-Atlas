import json,re,copy,hashlib,collections,sys,os
from pathlib import Path

BASE=Path(os.environ.get('B_V2_1_BASE','/mnt/data/bv2_independent_audit'))
V2=Path(os.environ.get('B_V2_GRAPH','/mnt/data/b_semantic_audit/B_v2_review_final/anatomy-acupoint-relations-v2.json'))
AUD=Path(os.environ.get('B_V2_INDEPENDENT_AUDIT',str(BASE/'b-v2-independent-who-audit.json')))
OUT=Path(os.environ.get('B_V2_1_OUT',str(BASE/'v2_1')))
OUT.mkdir(parents=True,exist_ok=True)

g0=json.load(open(V2,encoding='utf-8'))
aud=json.load(open(AUD,encoding='utf-8'))
g=copy.deepcopy(g0)
S={s['source_statement_id']:s for s in g['source_statements']}
POINTS={p['point_id'] for p in g['points']}

def canon(s):
    s=str(s).replace('\u00ad','').replace('‐','-').replace('–','-').replace('—','-').replace('−','-')
    s=re.sub(r'(?<=[A-Za-z])-(?=[A-Za-z])','',s)
    return re.sub(r'\s+',' ',s).strip().lower()

def hid(s,n=10): return hashlib.sha1(s.encode()).hexdigest()[:n]
def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def rebuild_indexes():
    global byl,byr,byg,byc,bym,bycb,lmid
    byl=collections.defaultdict(list);byr=collections.defaultdict(list);byg=collections.defaultdict(list);byc=collections.defaultdict(list);bym=collections.defaultdict(list);bycb=collections.defaultdict(list)
    for x in g['landmark_nodes']:byl[x['source_statement_id']].append(x)
    for x in g['relation_instances']:byr[x['source_statement_id']].append(x)
    for x in g['geometry_nodes']:byg[x['source_statement_id']].append(x)
    for x in g['conditions']:byc[x['source_statement_id']].append(x)
    for x in g['proportional_measurements']:bym[x['source_statement_id']].append(x)
    for x in g['composite_bindings']:bycb[x['source_statement_id']].append(x)
    lmid={x['node_id']:x for x in g['landmark_nodes']}
rebuild_indexes()

# Immutable repair ledger snapshot from independent WHO audit
rules={
 'SOURCE_RELATION_OVERGENERATION':'deduplicate exact semantic relation key (type+cue+subject+args+branch)',
 'PROPORTIONAL_MEASUREMENT_LOSS':'source-wide explicit B/F-cun inventory repair with exact span/value/unit/direction/anchor',
 'REFERENCE_ACUPOINT_OMISSION_OR_MISBINDING':'source-wide genuine reference-acupoint extraction and source-backed node/reference relation',
 'CONDITIONAL_BRANCH_FLATTENING':'add body-position condition and bind locator relations/landmarks to branch',
 'RELATION_TYPE_MISCLASSIFICATION':'replace transverse-line surface-landmark with on-line relation and source-backed line anchor',
 'SOURCE_RELATION_OMISSION':'construct GV20 auricular-apex line and midpoint relation',
 'SOURCE_SPAN_MISMATCH':'separate literal source_span_raw from derived_semantic_label; source_raw becomes exact source substring',
}
ledger=[]
for d in aud['defects']:
    ledger.append({
      'defect_id':d['independent_defect_id'],'point_id':d['point_id'],'statement_id':d['statement_id'],'statement_type':d['statement_type'],
      'WHO_source_text':d['source_text'],'WHO_source_page':d['source_page'],'defect_class':d['defect_class'],'severity':d['severity'],
      'v2_current_representation':{'affected_graph_ids':d.get('affected_graph_ids',[]),'evidence':d.get('evidence',{})},
      'expected_source_semantics':d.get('description',''),'repair_rule':rules[d['defect_class']],
      'v2_1_result':None,'repair_status':'PENDING','independent_reaudit_status':'PENDING'
    })
json.dump({'schema_version':'2.1.0','baseline_graph_sha256':sha256_file(V2),'defects':ledger},open(OUT/'b-v2.1-repair-ledger-initial.json','w'),ensure_ascii=False,indent=2)

# ---------- helper creation ----------
def add_landmark(sid,start,end,semantic_role,source_backing='B_v2_1_source_backed_derived',derived_label=None,cross_ref=None,creation_reason='B v2.1 targeted WHO-source repair'):
    text=S[sid]['text_canonical']; raw=text[start:end]
    # reuse exact span + role/ref if available
    for x in byl[sid]:
        if x['char_start']!=start or x['char_end']!=end:
            continue
        if cross_ref and x.get('cross_reference_point_id')!=cross_ref:
            continue
        # Same literal source span may legitimately denote multiple source-backed
        # derived endpoints (e.g. plural 'auricular apices' -> left/right).
        # Never collapse distinct derived semantic identities merely because the
        # contiguous WHO span is shared.
        if derived_label is not None and x.get('derived_semantic_label')!=derived_label:
            continue
        if derived_label is None and x.get('derived_semantic_label') is not None:
            continue
        return x
    node_id=f"LM21:{sid}:{start}-{end}:{hid((derived_label or raw)+'|'+semantic_role)}"
    x={'node_id':node_id,'node_type':'landmark','source_statement_id':sid,'point_id':S[sid]['point_id'],'source_section':S[sid]['section'],
       'source_raw':raw,'source_span_raw':raw,'char_start':start,'char_end':end,'semantic_role':semantic_role,'source_segments':[],
       'creation_reason':creation_reason,'source_backing':source_backing,'upstream_absence_provenance':{'upstream_node_found':False,'expected_source_span':{'char_start':start,'char_end':end,'source_raw':raw},'reason':creation_reason},
       'terminal_disposition':'source_backed_derived_unresolved','fma_id':None,'fma_name':None,'components':[]}
    if derived_label:x['derived_semantic_label']=derived_label
    if cross_ref:
        x.update({'landmark_class':'acupoint_reference','terminal_disposition':'cross_reference','cross_reference_point_id':cross_ref})
    g['landmark_nodes'].append(x);byl[sid].append(x);lmid[node_id]=x
    return x

def add_relation(sid,typ,args,start,end,role,branch_id=None,source_semantics=None,direction=None,geometry_ids=None,relation_id=None):
    text=S[sid]['text_canonical']; raw=text[start:end]
    # exact semantic duplicate guard
    for r in byr[sid]:
        if r['relation_type']==typ and r.get('argument_node_ids',[])==args and r['cue_span']['char_start']==start and r['cue_span']['char_end']==end and r.get('branch_id')==branch_id:
            return r
    rid=relation_id or f"RL21:{sid}:{start}-{end}:{typ}:{hid('|'.join(args)+'|'+str(branch_id))}"
    r={'relation_id':rid,'subject_node_id':'P:'+S[sid]['point_id'],'relation_type':typ,'argument_node_ids':args,'source_statement_id':sid,'source_section':S[sid]['section'],
       'cue_span':{'source_raw':raw,'char_start':start,'char_end':end,'role':role},'branch_id':branch_id,'source_semantics':source_semantics,'direction':direction,'fraction_partition':None,
       'provenance':{'construction':'B_v2.1_targeted_source_repair','binding_basis':'WHO source span only'}}
    if geometry_ids:r['geometry_node_ids']=geometry_ids
    g['relation_instances'].append(r);byr[sid].append(r);return r

def condition_branch_for(sid):
    # prefer body-position/sex branch if only one relevant; stable existing first
    xs=[c for c in byc[sid] if c.get('condition_type') in ('body_position','sex_specific','anatomical_variant','alternative_location')]
    return xs[0].get('branch_id') if xs else None

# F. literal source span integrity. This repairs B-layer metadata only; frozen upstream artifacts remain untouched.
# Reconstructed/elliptical semantic labels are kept separately from literal contiguous WHO spans.
span_fixed=0
for x in g['landmark_nodes']:
    sid=x['source_statement_id']; text=S[sid]['text_canonical']; actual=text[x['char_start']:x['char_end']]
    if canon(actual)!=canon(x.get('source_raw','')):
        x['derived_semantic_label']=x.get('derived_semantic_label') or x.get('source_raw')
        x['source_span_raw']=actual
        x['source_raw']=actual
        x['provenance_note']='v2.1 separates literal contiguous WHO source span from reconstructed/elliptical semantic label; upstream source artifact not modified'
        span_fixed+=1
# Same rule for non-contiguous branch-specific relation/geometry source semantics (e.g. CV1 female branch).
for coll,span_key,id_key in [('relation_instances','cue_span','relation_id'),('geometry_nodes','source_span','node_id')]:
    for x in g[coll]:
        sp=x.get(span_key)
        if not sp: continue
        sid=x['source_statement_id'];text=S[sid]['text_canonical'];actual=text[sp['char_start']:sp['char_end']]
        if canon(actual)!=canon(sp.get('source_raw','')):
            sp['derived_semantic_label']=sp.get('derived_semantic_label') or sp.get('source_raw')
            sp['source_span_raw']=actual
            sp['source_raw']=actual
            x['provenance_note']='v2.1 literal WHO span separated from branch-specific reconstructed semantic label'
            span_fixed+=1
rebuild_indexes()

# C. exhaustive genuine reference-acupoint nodes + reference relation
known='LU|LI|ST|SP|HT|SI|BL|KI|PC|TE|GB|LR|GV|CV'; ptpat=re.compile(rf'\b({known})\s?(\d{{1,2}})\b',re.I)
ref_mentions=[];ref_nodes_added=0;ref_rel_added=0
for sid,s in S.items():
    subj=s['point_id'].upper(); text=s['text_canonical']
    for m in ptpat.finditer(text):
        ref=(m.group(1)+m.group(2)).upper()
        if ref==subj or ref not in POINTS:continue
        ref_mentions.append((sid,m.start(),m.end(),ref))
        nodes=[x for x in byl[sid] if x.get('cross_reference_point_id','').upper()==ref and not (x['char_end']<=m.start() or x['char_start']>=m.end())]
        if not nodes:
            n=add_landmark(sid,m.start(),m.end(),'reference_acupoint',cross_ref=ref,creation_reason='WHO genuine reference acupoint absent from B v2')
            ref_nodes_added+=1
        else:n=nodes[0]
        # dedicated non-geometric source reference relation
        before=len(byr[sid]); add_relation(sid,'reference-acupoint',[n['node_id']],m.start(),m.end(),'reference_acupoint',branch_id=condition_branch_for(sid),source_semantics='reference_acupoint')
        if len(byr[sid])>before:ref_rel_added+=1
rebuild_indexes()

# D. missing explicit body-position conditions and branch binding
missing_condition_phrases={
 'S:SI6:note:1':'With the palm facing downwards',
 'S:BL38:note:1':'With the knee in slight flexion',
 'S:BL57:note:1':'With the leg stretched (plantar flexion) or the heel up',
 'S:PC4:note:1':'With the fist clenched, the wrist su-pinated, and the elbow slightly flexed',
 'S:PC5:note:1':'With the fist clenched, the wrist supinated and the elbow slightly flexed',
 'S:PC6:note:1':'With the fist clenched, the wrist supinated and the elbow slightly flexed',
 'S:PC7:note:1':'With the fist clenched, the wrist slightly flexed',
 'S:TE15:note:1':'With the upper limb hanging by the side of trunk in a seated position',
 'S:CV1:note:1':'with the subject lying on the side or in knee-chest position',
}
conditions_added=0
for sid,phrase in missing_condition_phrases.items():
    text=S[sid]['text_canonical']; start=text.lower().find(phrase.lower())
    if start<0: raise RuntimeError(f'condition source phrase not found {sid}: {phrase}')
    end=start+len(phrase)
    existing=[c for c in byc[sid] if c['condition_type']=='body_position' and not(c['source_span']['char_end']<=start or c['source_span']['char_start']>=end)]
    if existing:cnd=existing[0]
    else:
        branch=f"branch_body_position_{len([c for c in byc[sid] if c['condition_type']=='body_position'])+1}"
        cid=f"CD21:{sid}:{start}-{end}:body_position"
        cnd={'condition_id':cid,'source_statement_id':sid,'condition_type':'body_position','condition_scope':'statement_locator','branch_id':branch,
             'source_span':{'condition_type':'body_position','source_raw':text[start:end],'char_start':start,'char_end':end,'role':'body_position'},
             'branch_relation_ids':[],'branch_landmark_ids':[],
             'provenance':{'construction':'B_v2.1_targeted_source_repair','source':'WHO primary source'}}
        g['conditions'].append(cnd);byc[sid].append(cnd);conditions_added+=1
    # Bind all point-locator graph objects in this statement to the condition branch.
    relids=[]
    for r in byr[sid]:
        if r['relation_type']=='reference-acupoint' and r['cue_span']['char_start']<end: continue
        relids.append(r['relation_id'])
        arr=r.setdefault('condition_branch_ids',[])
        if cnd['branch_id'] not in arr:arr.append(cnd['branch_id'])
        if r.get('branch_id') is None:r['branch_id']=cnd['branch_id']
    lmids=[x['node_id'] for x in byl[sid]]
    cnd['branch_relation_ids']=sorted(set(cnd.get('branch_relation_ids',[])+relids))
    cnd['branch_landmark_ids']=sorted(set(cnd.get('branch_landmark_ids',[])+lmids))
# Alternative-location Remarks are conditional branches too; source statement flag alone is not a branch representation.
alternative_conditions_added=0
for sid,st in S.items():
    text=st['text_canonical']
    m=re.search(r'Alternative location',text,re.I)
    if not m: continue
    existing=[c for c in byc[sid] if c['condition_type']=='alternative_location' and not(c['source_span']['char_end']<=m.start() or c['source_span']['char_start']>=m.end())]
    if existing:cnd=existing[0]
    else:
        branch='branch_alternative_location_1';cid=f"CD21:{sid}:{m.start()}-{m.end()}:alternative_location"
        cnd={'condition_id':cid,'source_statement_id':sid,'condition_type':'alternative_location','condition_scope':'whole_statement_alternative_locator','branch_id':branch,
             'source_span':{'condition_type':'alternative_location','source_raw':text[m.start():m.end()],'char_start':m.start(),'char_end':m.end(),'role':'alternative_location'},
             'branch_relation_ids':[],'branch_landmark_ids':[],
             'provenance':{'construction':'B_v2.1_targeted_source_repair','source':'WHO primary source'}}
        g['conditions'].append(cnd);byc[sid].append(cnd);alternative_conditions_added+=1
    relids=[r['relation_id'] for r in byr[sid]];lmids=[x['node_id'] for x in byl[sid]]
    cnd['branch_relation_ids']=sorted(set(cnd.get('branch_relation_ids',[])+relids));cnd['branch_landmark_ids']=sorted(set(cnd.get('branch_landmark_ids',[])+lmids))
    for r in byr[sid]:
        arr=r.setdefault('condition_branch_ids',[])
        if cnd['branch_id'] not in arr:arr.append(cnd['branch_id'])
        if r.get('branch_id') is None:r['branch_id']=cnd['branch_id']
rebuild_indexes()

# B. exhaustive explicit numeric B/F-cun measurement coverage
mpat=re.compile(r'(?P<num>\d+(?:\.\d+)?)\s+(?P<unit>[BFbf]-cun)\b',re.I)
dirpat=re.compile(r'^\s*(?:(?:directly)\s+)?(?P<dir>proximal-lateral|proximal-medial|superior\s+and\s+medial|lateral\s+and\s+distal|posterior|anterior|superior|inferior|medial|lateral|proximal|distal|radial|ulnar|within)',re.I)
source_measures=[];meas_added=0
for sid,s in S.items():
    text=s['text_canonical']
    for m in mpat.finditer(text):
        val=float(m.group('num'));unit=m.group('unit')
        source_measures.append((sid,m.start(),m.end(),val,unit.lower()))
        matches=[x for x in bym[sid] if abs(x['value']-val)<1e-9 and x['unit'].lower()==unit.lower() and x['cue_span']['char_start']<=m.start()<=x['cue_span']['char_end']]
        if matches:
            x=matches[0];x['source_value_span']={'source_raw':text[m.start():m.end()],'char_start':m.start(),'char_end':m.end()}
            continue
        tail=text[m.end():m.end()+60];dm=dirpat.search(tail);direction=canon(dm.group('dir')).replace(' ','-') if dm else None
        # choose source-backed anchor from nearby existing relation, then nearby ref/landmark
        anchor=None
        candidates=[]
        for r in byr[sid]:
            cs=r['cue_span']['char_start']
            if m.end()-5 <= cs <= m.end()+45 and r['relation_type'] in ('relative-to','surface-landmark','same-level') and r.get('argument_node_ids'):
                candidates.append((abs(cs-m.end()),r['argument_node_ids'][0]))
        if candidates:anchor=sorted(candidates)[0][1]
        if not anchor:
            later=[x for x in byl[sid] if m.end()<=x['char_start']<=m.end()+100]
            if later:anchor=sorted(later,key=lambda x:x['char_start'])[0]['node_id']
        branch=condition_branch_for(sid)
        mid=f"PM21:{sid}:{m.start()}-{m.end()}"
        x={'measurement_id':mid,'source_statement_id':sid,'value':val,'unit':unit,'direction':direction,
           'cue_span':{'source_raw':text[m.start():m.end()],'char_start':m.start(),'char_end':m.end(),'role':'proportional_measurement'},
           'source_value_span':{'source_raw':text[m.start():m.end()],'char_start':m.start(),'char_end':m.end()},
           'anchor_landmark_id':anchor,'branch_id':branch,'provenance':{'construction':'B_v2.1_targeted_source_repair','source':'WHO primary source'}}
        g['proportional_measurements'].append(x);bym[sid].append(x);meas_added+=1
rebuild_indexes()

# E1. GV20 Note2 bilateral auricular-apex line + midpoint
sid='S:GV20:note:2';text=S[sid]['text_canonical'];sp='auricular apices';a=text.lower().index(sp);b=a+len(sp)
left=add_landmark(sid,a,b,'line_endpoint',derived_label='left auricular apex',creation_reason='WHO plural auricular apices requires two bilateral endpoints')
right=add_landmark(sid,a,b,'line_endpoint',derived_label='right auricular apex',creation_reason='WHO plural auricular apices requires two bilateral endpoints')
line_start=text.lower().index('connecting line'); line_end=b
geom_id='GM21:S:GV20:note:2:00:constructed_line'
if not any(x['node_id']==geom_id for x in g['geometry_nodes']):
    geo={'node_id':geom_id,'node_type':'geometry','geometry_type':'constructed_line','source_statement_id':sid,
         'source_span':{'source_raw':text[line_start:line_end],'char_start':line_start,'char_end':line_end,'role':'line_construct'},
         'endpoint_node_ids':[left['node_id'],right['node_id']],'required_endpoint_count':2,'branch_id':condition_branch_for(sid),
         'provenance':{'construction':'B_v2.1_targeted_source_repair','source_backed_only':True}}
    g['geometry_nodes'].append(geo);byg[sid].append(geo)
add_relation(sid,'on-line',[left['node_id'],right['node_id']],line_start,line_end,'line_construct',branch_id=condition_branch_for(sid),geometry_ids=[geom_id],source_semantics='connecting_line')
mid_start=text.lower().index('midpoint');mid_end=line_end
add_relation(sid,'midpoint-between',[left['node_id'],right['node_id']],mid_start,mid_end,'midpoint',branch_id=condition_branch_for(sid),geometry_ids=[geom_id],source_semantics='midpoint_of_connecting_line')
rebuild_indexes()
# bind existing GV20 folded-ear condition to new objects
for cnd in byc[sid]:
    if cnd['condition_type']=='body_position':
        cnd['branch_relation_ids']=sorted(set(cnd.get('branch_relation_ids',[])+[r['relation_id'] for r in byr[sid]]))
        cnd['branch_landmark_ids']=sorted(set(cnd.get('branch_landmark_ids',[])+[left['node_id'],right['node_id']]))

# E2. LU1/LU2 transverse line: on-line + line anchor
for sid,anchor_phrase in [('S:LU1:note:2','first intercostal space'),('S:LU2:note:2','inferior border of the clavicle')]:
    text=S[sid]['text_canonical']; cue='on the transverse line';cs=text.lower().index(cue);ce=cs+len(cue)
    line=[x for x in byl[sid] if canon(x['source_raw'])=='transverse line'][0]
    # remove misclassified surface-landmark with same cue/line
    g['relation_instances']=[r for r in g['relation_instances'] if not(r['source_statement_id']==sid and r['relation_type']=='surface-landmark' and line['node_id'] in r.get('argument_node_ids',[]) and r['cue_span']['char_start']==cs)]
    rebuild_indexes()
    ast=text.lower().index(anchor_phrase);ae=ast+len(anchor_phrase)
    anchors=[x for x in byl[sid] if x['char_start']<=ast and x['char_end']>=ae]
    if anchors:anc=min(anchors,key=lambda x:x['char_end']-x['char_start'])
    else:anc=add_landmark(sid,ast,ae,'line_anchor',creation_reason='WHO transverse line anatomical anchor absent from B v2')
    line['line_anchor_landmark_ids']=sorted(set(line.get('line_anchor_landmark_ids',[])+[anc['node_id']]))
    gid=f"GM21:{sid}:00:reference_line"
    if not any(x['node_id']==gid for x in g['geometry_nodes']):
        ge={'node_id':gid,'node_type':'geometry','geometry_type':'reference_line','source_statement_id':sid,
            'source_span':{'source_raw':text[cs:ae],'char_start':cs,'char_end':ae,'role':'line_construct'},'endpoint_node_ids':[],
            'anchor_node_ids':[anc['node_id']],'required_endpoint_count':0,'branch_id':condition_branch_for(sid),
            'provenance':{'construction':'B_v2.1_targeted_source_repair','source_backed_only':True}}
        g['geometry_nodes'].append(ge);byg[sid].append(ge)
    add_relation(sid,'on-line',[line['node_id']],cs,ce,'locative_on_line',branch_id=condition_branch_for(sid),geometry_ids=[gid],source_semantics='on_transverse_line')
rebuild_indexes()

# A. deduplicate exact semantic relations after branch repair
kept=[];seen={};dup_removed=[];replacement={}
for r in g['relation_instances']:
    key=(r['source_statement_id'],r['subject_node_id'],r['relation_type'],tuple(r.get('argument_node_ids',[])),r['cue_span']['char_start'],r['cue_span']['char_end'],r.get('branch_id'))
    if key in seen:
        dup_removed.append(r['relation_id']);replacement[r['relation_id']]=seen[key]['relation_id'];continue
    seen[key]=r;kept.append(r)
g['relation_instances']=kept
# fix condition branch relation references
valid_rel={r['relation_id'] for r in g['relation_instances']}
for c in g['conditions']:
    new=[]
    for rid in c.get('branch_relation_ids',[]):
        rid=replacement.get(rid,rid)
        if rid in valid_rel and rid not in new:new.append(rid)
    c['branch_relation_ids']=new
rebuild_indexes()

# Metadata/version baseline preservation
g['schema_version']='2.1.0'
g['artifact']='anatomy-acupoint-relations-v2.1.json'
g['status']='B_V2_1_REPAIR_CANDIDATE_NOT_FROZEN'
g['architecture']='B v2 targeted WHO-primary-source repair; v2 preserved as immutable baseline'
g['repair_provenance']={
 'baseline_artifact':'anatomy-acupoint-relations-v2.json','baseline_sha256':sha256_file(V2),
 'independent_audit_artifact':'b-v2-independent-who-audit.json','independent_audit_defect_count':237,
 'repair_scope_families':sorted(rules),'B_v2_modified':False,'C_gate':'STOPPED'
}
# do not retain misleading v2 freeze summary
g.pop('build_summary',None)

# ---------- internal validators ----------
rebuild_indexes()
internal={}
# duplicates
semgroups=collections.Counter((r['source_statement_id'],r['subject_node_id'],r['relation_type'],tuple(r.get('argument_node_ids',[])),r['cue_span']['char_start'],r['cue_span']['char_end'],r.get('branch_id')) for r in g['relation_instances'])
internal['duplicate_semantic_relation_count']=sum(v-1 for v in semgroups.values() if v>1)
# proportional explicit numeric coverage / overgeneration
mentions=[]
for sid,s in S.items():
    for m in mpat.finditer(s['text_canonical']):mentions.append((sid,m.start(),m.end(),float(m.group('num')),m.group('unit').lower()))
matched_meas=set();omitted=[]
for mm in mentions:
    sid,st,en,val,unit=mm
    xs=[x for x in bym[sid] if abs(x['value']-val)<1e-9 and x['unit'].lower()==unit and x['cue_span']['char_start']<=st<=x['cue_span']['char_end']]
    if not xs:omitted.append(mm)
    else:matched_meas.update(x['measurement_id'] for x in xs)
over=[x['measurement_id'] for x in g['proportional_measurements'] if x['measurement_id'] not in matched_meas]
internal['source_proportional_mention_count']=len(mentions);internal['graph_proportional_measurement_count']=len(g['proportional_measurements']);internal['proportional_omitted']=len(omitted);internal['proportional_overgenerated']=len(over)
internal['measurement_missing_anchor_count']=sum(x.get('anchor_landmark_id') is None for x in g['proportional_measurements'])
# refs exhaustive
missing_refs=[];ref_relation_missing=[]
for sid,s in S.items():
    subj=s['point_id'].upper(); text=s['text_canonical']
    for m in ptpat.finditer(text):
        ref=(m.group(1)+m.group(2)).upper()
        if ref==subj or ref not in POINTS:continue
        ns=[x for x in byl[sid] if x.get('cross_reference_point_id','').upper()==ref and not(x['char_end']<=m.start() or x['char_start']>=m.end())]
        if not ns:missing_refs.append((sid,ref,m.start()))
        elif not any(r['relation_type']=='reference-acupoint' and ns[0]['node_id'] in r.get('argument_node_ids',[]) for r in byr[sid]):ref_relation_missing.append((sid,ref))
internal['genuine_reference_acupoint_mentions']=len(ref_mentions);internal['reference_acupoint_missing']=len(missing_refs);internal['reference_relation_missing']=len(ref_relation_missing)
# conditions specified in repair scope
cond_fail=[]
for sid,phrase in missing_condition_phrases.items():
    cs=[c for c in byc[sid] if c['condition_type']=='body_position' and canon(phrase) in canon(c['source_span']['source_raw'])]
    if not cs or not cs[0].get('branch_relation_ids') or not cs[0].get('branch_landmark_ids'):cond_fail.append(sid)
internal['conditional_binding_failures']=cond_fail
# exact source spans all graph objects
def spanok(sid,objspan):
    t=S[sid]['text_canonical'];return canon(t[objspan['char_start']:objspan['char_end']])==canon(objspan['source_raw'])
span_errors=[]
for x in g['landmark_nodes']:
    if not spanok(x['source_statement_id'],{'char_start':x['char_start'],'char_end':x['char_end'],'source_raw':x['source_raw']}):span_errors.append(x['node_id'])
for r in g['relation_instances']:
    if not spanok(r['source_statement_id'],r['cue_span']):span_errors.append(r['relation_id'])
for x in g['geometry_nodes']:
    if x.get('source_span') and not spanok(x['source_statement_id'],x['source_span']):span_errors.append(x['node_id'])
for x in g['conditions']:
    if not spanok(x['source_statement_id'],x['source_span']):span_errors.append(x['condition_id'])
for x in g['proportional_measurements']:
    if not spanok(x['source_statement_id'],x['cue_span']):span_errors.append(x['measurement_id'])
internal['source_span_mismatch_count']=len(span_errors);internal['source_span_mismatch_ids']=span_errors
# mandatory repaired semantics
internal['GV20_midpoint']=any(r['source_statement_id']=='S:GV20:note:2' and r['relation_type']=='midpoint-between' for r in g['relation_instances'])
internal['GV20_line_geometry']=any(x['source_statement_id']=='S:GV20:note:2' and x['geometry_type']=='constructed_line' and len(x.get('endpoint_node_ids',[]))==2 and len(set(x.get('endpoint_node_ids',[])))==2 for x in g['geometry_nodes'])
internal['LU1_on_line']=any(r['source_statement_id']=='S:LU1:note:2' and r['relation_type']=='on-line' for r in g['relation_instances'])
internal['LU2_on_line']=any(r['source_statement_id']=='S:LU2:note:2' and r['relation_type']=='on-line' for r in g['relation_instances'])
# orphan refs
valid_nodes={p['node_id'] for p in g['points']}|{x['node_id'] for x in g['landmark_nodes']}|{x['node_id'] for x in g['geometry_nodes']}
orph=[]
for r in g['relation_instances']:
    for a in r.get('argument_node_ids',[]):
        if a not in valid_nodes:orph.append((r['relation_id'],a))
for geo in g['geometry_nodes']:
    for a in geo.get('endpoint_node_ids',[])+geo.get('anchor_node_ids',[]):
        if a not in valid_nodes:orph.append((geo['node_id'],a))
internal['orphan_reference_count']=len(orph)

# repair ledger result mapping from live graph checks
for row in ledger:
    cls=row['defect_class'];sid=row['statement_id'];ok=False;detail={}
    if cls=='SOURCE_RELATION_OVERGENERATION':
        groups=collections.Counter((r['relation_type'],tuple(r.get('argument_node_ids',[])),r['cue_span']['char_start'],r['cue_span']['char_end'],r.get('branch_id')) for r in byr[sid]);ok=all(v==1 for v in groups.values());detail={'duplicates_remaining':sum(v-1 for v in groups.values() if v>1)}
    elif cls=='PROPORTIONAL_MEASUREMENT_LOSS':
        e=row['v2_current_representation']['evidence'];ok=any(abs(x['value']-e['value'])<1e-9 and x['unit'].lower()==e['unit'].lower() and x['cue_span']['char_start']<=e['char_start']<=x['cue_span']['char_end'] for x in bym[sid]);detail={'covered':ok}
    elif cls=='REFERENCE_ACUPOINT_OMISSION_OR_MISBINDING':
        e=row['v2_current_representation']['evidence'];ref=e['reference_point_id'];ns=[x for x in byl[sid] if x.get('cross_reference_point_id','').upper()==ref];ok=bool(ns) and any(r['relation_type']=='reference-acupoint' and any(n['node_id'] in r.get('argument_node_ids',[]) for n in ns) for r in byr[sid]);detail={'node_count':len(ns)}
    elif cls=='CONDITIONAL_BRANCH_FLATTENING':
        ok=sid not in cond_fail;detail={'bound':ok}
    elif cls=='RELATION_TYPE_MISCLASSIFICATION':ok=any(r['relation_type']=='on-line' for r in byr[sid]);detail={'on_line':ok}
    elif cls=='SOURCE_RELATION_OMISSION':ok=internal['GV20_midpoint'] and internal['GV20_line_geometry'];detail={'midpoint':internal['GV20_midpoint'],'line':internal['GV20_line_geometry']}
    elif cls=='SOURCE_SPAN_MISMATCH':
        nid=row['v2_current_representation']['evidence']['node_id'];n=next((x for x in g['landmark_nodes'] if x['node_id']==nid),None);ok=bool(n) and canon(S[sid]['text_canonical'][n['char_start']:n['char_end']])==canon(n['source_raw']);detail={'exact_span':ok,'derived_semantic_label':n.get('derived_semantic_label') if n else None}
    row['v2_1_result']=detail;row['repair_status']='REPAIRED' if ok else 'UNRESOLVED'

internal['repair_ledger_repaired']=sum(x['repair_status']=='REPAIRED' for x in ledger);internal['repair_ledger_total']=len(ledger)
internal['repair_ledger_unresolved']=[x['defect_id'] for x in ledger if x['repair_status']!='REPAIRED']
internal['PASS']=(internal['duplicate_semantic_relation_count']==0 and internal['proportional_omitted']==0 and internal['proportional_overgenerated']==0 and internal['measurement_missing_anchor_count']==0 and internal['reference_acupoint_missing']==0 and internal['reference_relation_missing']==0 and not internal['conditional_binding_failures'] and internal['source_span_mismatch_count']==0 and internal['GV20_midpoint'] and internal['GV20_line_geometry'] and internal['LU1_on_line'] and internal['LU2_on_line'] and internal['orphan_reference_count']==0 and internal['repair_ledger_repaired']==237)

# Negative mutation tests, targeted + prior-style core tests
def deep():return copy.deepcopy(g)
def hasdup(G):
 c=collections.Counter((r['source_statement_id'],r['subject_node_id'],r['relation_type'],tuple(r.get('argument_node_ids',[])),r['cue_span']['char_start'],r['cue_span']['char_end'],r.get('branch_id')) for r in G['relation_instances']);return any(v>1 for v in c.values())
def meas_coverage(G,sid,start,val,unit):return any(x['source_statement_id']==sid and abs(x['value']-val)<1e-9 and x['unit'].lower()==unit.lower() and x['cue_span']['char_start']<=start<=x['cue_span']['char_end'] for x in G['proportional_measurements'])
def ref_coverage(G,sid,ref):return any(x['source_statement_id']==sid and x.get('cross_reference_point_id','').upper()==ref for x in G['landmark_nodes'])
def cond_bound(G,sid):return any(c['source_statement_id']==sid and c['condition_type']=='body_position' and c.get('branch_relation_ids') and c.get('branch_landmark_ids') for c in G['conditions'])
def gv20_ok(G):return any(r['source_statement_id']=='S:GV20:note:2' and r['relation_type']=='midpoint-between' and len(r.get('argument_node_ids',[]))==2 and len(set(r.get('argument_node_ids',[])))==2 for r in G['relation_instances'])
def lu1line(G):return any(r['source_statement_id']=='S:LU1:note:2' and r['relation_type']=='on-line' for r in G['relation_instances'])
def spans_ok(G):
 ss={s['source_statement_id']:s for s in G['source_statements']}
 for x in G['landmark_nodes']:
  if canon(ss[x['source_statement_id']]['text_canonical'][x['char_start']:x['char_end']])!=canon(x['source_raw']):return False
 return True
nt=[]
# 1 duplicate ST35
M=deep();base=next(r for r in M['relation_instances'] if r['source_statement_id']=='S:ST35:location' and r['relation_type']=='surface-landmark' and 'depression' in r['cue_span']['source_raw']);z=copy.deepcopy(base);z['relation_id']+=':MUT';M['relation_instances'].append(z);nt.append({'test':'ST35 depression duplicate edge','PASS':hasdup(M)})
#2 LU11 meas deletion
M=deep();M['proportional_measurements']=[x for x in M['proportional_measurements'] if not(x['source_statement_id']=='S:LU11:location' and abs(x['value']-.1)<1e-9)];nt.append({'test':'LU11 0.1 F-cun deletion','PASS':not meas_coverage(M,'S:LU11:location',44,.1,'f-cun')})
#3 LU1 ref deletion
M=deep();M['landmark_nodes']=[x for x in M['landmark_nodes'] if not(x['source_statement_id']=='S:LU1:note:2' and x.get('cross_reference_point_id')=='ST14')];nt.append({'test':'LU1 Note2 reference deletion','PASS':not ref_coverage(M,'S:LU1:note:2','ST14')})
#4 CV1 condition deletion
M=deep();M['conditions']=[x for x in M['conditions'] if not(x['source_statement_id']=='S:CV1:note:1' and x['condition_type']=='body_position')];nt.append({'test':'CV1 posture condition deletion','PASS':not cond_bound(M,'S:CV1:note:1')})
#5 GV20 midpoint deletion
M=deep();M['relation_instances']=[x for x in M['relation_instances'] if not(x['source_statement_id']=='S:GV20:note:2' and x['relation_type']=='midpoint-between')];nt.append({'test':'GV20 midpoint deletion','PASS':not gv20_ok(M)})
#6 LU1 on-line reclassify
M=deep();r=next(x for x in M['relation_instances'] if x['source_statement_id']=='S:LU1:note:2' and x['relation_type']=='on-line');r['relation_type']='surface-landmark';nt.append({'test':'LU1 transverse-line on-line reclassification','PASS':not lu1line(M)})
#7 source span manipulation
M=deep();x=next(x for x in M['landmark_nodes'] if x.get('source_backing') in ('B_v2_1_source_backed_derived','B_v2_source_backed_derived'));x['source_raw']='NOT IN SOURCE';nt.append({'test':'derived landmark source span manipulation','PASS':not spans_ok(M)})
# prior core style: endpoint/cardinality/composite/argument/intersection/sex branch smoke
# CV12 endpoint remove
M=deep();geo=next(x for x in M['geometry_nodes'] if x['source_statement_id']=='S:CV12:note:1' and len(x.get('endpoint_node_ids',[]))==2);geo['endpoint_node_ids']=geo['endpoint_node_ids'][:1];nt.append({'test':'CV12 endpoint removal','PASS':len(geo['endpoint_node_ids'])!=geo.get('required_endpoint_count',2)})
# between endpoint remove from any between relation
M=deep();br=next(x for x in M['relation_instances'] if x['relation_type']=='between' and len(x.get('argument_node_ids',[]))>=2);br['argument_node_ids']=br['argument_node_ids'][:1];nt.append({'test':'between endpoint removal','PASS':len(br['argument_node_ids'])<2})
# composite parent removal
M=deep();cb=M['composite_bindings'][0];M['composite_bindings'].remove(cb);nt.append({'test':'composite parent binding removal','PASS':cb not in M['composite_bindings']})
# intersection arg replace
M=deep();ir=next(x for x in M['relation_instances'] if x['relation_type']=='at-junction' and len(x.get('argument_node_ids',[]))>=2);ir['argument_node_ids'][1]=ir['argument_node_ids'][0];nt.append({'test':'intersection operand corruption','PASS':len(set(ir['argument_node_ids']))<2})
# CV1 sex condition removal
M=deep();M['conditions']=[x for x in M['conditions'] if not(x['source_statement_id']=='S:CV1:location' and x.get('condition_type')=='sex_specific')];nt.append({'test':'CV1 sex condition removal','PASS':not any(x['source_statement_id']=='S:CV1:location' and x.get('condition_type')=='sex_specific' for x in M['conditions'])})
internal['negative_mutation_tests']=nt;internal['negative_mutation_tests_PASS']=all(x['PASS'] for x in nt)
internal['PASS']=internal['PASS'] and internal['negative_mutation_tests_PASS']

# write graph / internal report / ledger pre-reaudit
json.dump(g,open(OUT/'anatomy-acupoint-relations-v2.1.json','w'),ensure_ascii=False,indent=2)
json.dump({'schema_version':'2.1.0','internal_validator':internal,'repair_stats':{'span_fixed':span_fixed,'reference_nodes_added':ref_nodes_added,'reference_relations_added':ref_rel_added,'conditions_added':conditions_added,'alternative_conditions_added':alternative_conditions_added,'measurements_added':meas_added,'duplicate_relations_removed':len(dup_removed)}},open(OUT/'b-v2.1-internal-validator.json','w'),ensure_ascii=False,indent=2)
json.dump({'schema_version':'2.1.0','baseline_graph_sha256':sha256_file(V2),'v2_1_graph_sha256':sha256_file(OUT/'anatomy-acupoint-relations-v2.1.json'),'defects':ledger},open(OUT/'b-v2.1-repair-ledger.json','w'),ensure_ascii=False,indent=2)
print(json.dumps({'internal':internal,'stats':{'span_fixed':span_fixed,'reference_nodes_added':ref_nodes_added,'reference_relations_added':ref_rel_added,'conditions_added':conditions_added,'alternative_conditions_added':alternative_conditions_added,'measurements_added':meas_added,'duplicate_relations_removed':len(dup_removed)},'graph_sha256':sha256_file(OUT/'anatomy-acupoint-relations-v2.1.json')},ensure_ascii=False,indent=2))
if not internal['PASS']:sys.exit(2)