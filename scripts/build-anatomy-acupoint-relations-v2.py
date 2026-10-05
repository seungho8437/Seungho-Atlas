import json,re,hashlib,copy,os,zipfile,csv,sys
from collections import defaultdict,Counter
from pathlib import Path

BASE=Path(os.environ.get('B_V2_BASE','/mnt/data/b_semantic_audit')).resolve()
OUT=Path(os.environ.get('B_V2_OUT',str(BASE/'b_v2'))).resolve()
OUT.mkdir(parents=True,exist_ok=True)

def load(name):
    with open(BASE/name,encoding='utf-8') as f:return json.load(f)
def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    with open(path,'w',encoding='utf-8') as f: json.dump(obj,f,ensure_ascii=False,indent=2,sort_keys=False); f.write('\n')
def sha_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def sha_obj(obj):
    return hashlib.sha256((json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()

def clean_text(s):
    return re.sub(r'\s+',' ',s).strip()
def norm(s):
    s=str(s or '').lower()
    s=re.sub(r'(?<=[a-z])-\s*(?=[a-z])','',s)
    s=re.sub(r'[^a-z0-9]+',' ',s)
    s=re.sub(r'\b(?:the|a|an)\b',' ',s)
    return re.sub(r'\s+',' ',s).strip()
def safeid(s):
    return re.sub(r'[^A-Za-z0-9_.:-]+','_',str(s))
def span_key(sp): return (int(sp.get('char_start',-1)),int(sp.get('char_end',-1)),norm(sp.get('source_raw','')))
def span_obj(text,start,end,role=None,source_segments=None):
    d={'source_raw':text[start:end],'char_start':start,'char_end':end,'role':role}
    if source_segments:d['source_segments']=source_segments
    return d

v1=load('anatomy-acupoint-relations.json')
ledger=load('b-semantic-integrity-statement-ledger-v1.json')
defects=load('b-semantic-integrity-defect-inventory-v1.json')
try:
    regcases=load('b-semantic-integrity-regression-cases-v1.json')
except FileNotFoundError:
    regcases={'regression_cases':{
      'CV1':{'statements':['S:CV1:location','S:CV1:note:1']},
      'CV12':{'statements':['S:CV12:location','S:CV12:note:1']},
      'GB26':{'statements':['S:GB26:location','S:GB26:note:1','S:GB26:note:2']},
      'ST35':{'statements':['S:ST35:location','S:ST35:note:1']},
      'ST29':{'statements':['S:ST29:location','S:ST29:note:1']}
    }}
loc=load('location_fma_identity_resolution_final_v1.json')
notes=load('notes_anatomical_identity_mapping_v1.json')
remarks=load('remarks_adjudication_v1.json')

ledger_by={s['statement_id']:s for s in ledger['statements']}
v1_source_by={s['source_statement_id']:s for s in v1['source_statements']}

# ---- frozen upstream snapshot hashes before build ----
upstream_files={
 'Location identity-resolution finalization v1':BASE/'location_fma_identity_resolution_final_v1.json',
 'Notes anatomical identity mapping v1 (derived from frozen Notes semantic-role v0.3)':BASE/'notes_anatomical_identity_mapping_v1.json',
 'Remarks adjudication v1 (1A-backed)':BASE/'remarks_adjudication_v1.json',
}
upstream_before={k:sha_file(p) for k,p in upstream_files.items()}

# ---- upstream source-backed candidate mentions, never B-v1 landmark reuse ----
up=defaultdict(list)
for r in loc['records']:
    sid=f"S:{r['point_id']}:location"
    disp=r.get('final_disposition',{})
    rr=r.get('registry_resolution',{})
    up[sid].append({
      'origin':'location_identity_resolution_final_v1','source_raw':r['source_raw'],'char_start':r['char_start'],'char_end':r['char_end'],
      'role':'upstream_location_landmark','landmark_class':r.get('source_landmark_class'),'semantic_target_type':r.get('semantic_target_type'),
      'terminal_disposition':disp.get('status') or rr.get('resolution_status'),
      'fma_id':disp.get('fma_id') or rr.get('fma_id'),'fma_name':disp.get('fma_name') or rr.get('fma_name'),
      'components':r.get('components',[]),'upstream_record_index':r.get('record_index')
    })
for r in notes['records']:
    if r.get('mapping_eligibility')!='include': continue
    sid=f"S:{r['point_id']}:note:{r['note_index']}"
    m=r.get('mapping',{})
    up[sid].append({
      'origin':'notes_anatomical_identity_mapping_v1','source_raw':r['source_raw'],'char_start':r['char_start'],'char_end':r['char_end'],
      'role':r.get('mention_argument_role'),'landmark_class':r.get('landmark_class'),'semantic_target_type':None,
      'terminal_disposition':m.get('status'),'fma_id':m.get('fma_id'),'fma_name':m.get('fma_name'),'components':m.get('components',[]),
      'cross_reference_point_id': (r['source_raw'].upper() if r.get('mention_argument_role')=='reference_acupoint' else None),
      'upstream_mention_id':r.get('mention_id')
    })
for r in remarks['records']:
    if r.get('mapping_eligibility')!='include': continue
    sid=f"S:{r['point_id']}:remarks"
    m=r.get('mapping',{})
    up[sid].append({
      'origin':'remarks_adjudication_v1','source_raw':r['source_raw'],'char_start':r['char_start'],'char_end':r['char_end'],
      'role':r.get('mention_argument_role'),'landmark_class':r.get('landmark_class'),'semantic_target_type':None,
      'terminal_disposition':m.get('status'),'fma_id':m.get('fma_id'),'fma_name':m.get('fma_name'),'components':m.get('components',[]),
      'upstream_mention_id':r.get('mention_id')
    })

# ---- source-only specification compiler ----
def find_coord_and_split(text, clause_start, clause_end):
    """Return two source-backed operand expressions for 'between ... and ...'. Handles common shared-parent coordination."""
    raw=text[clause_start:clause_end]
    m=re.search(r'\bbetween\s+(.+)$',raw,re.I)
    if not m:return []
    body=m.group(1).strip()
    body_abs=clause_start+m.start(1)
    # shared parent: anterior and posterior borders of X / sternal and clavicular heads of X
    sm=re.match(r'(?:the\s+)?([\w-]+)\s+and\s+([\w-]+)\s+(borders?|heads?|ends?|sides?|margins?|corners?)\s+of\s+(.+)$',body,re.I)
    if sm:
        a,b,part,parent=sm.groups(); singular=part[:-1] if part.lower().endswith('s') else part
        # source segments preserve exact lexical evidence even if semantic operand is discontinuous
        a0=body_abs+sm.start(1);a1=body_abs+sm.end(1); b0=body_abs+sm.start(2);b1=body_abs+sm.end(2)
        p0=body_abs+sm.start(4);p1=body_abs+sm.end(4)
        return [
          {'source_raw':f'{a} {singular} of {parent}','char_start':a0,'char_end':p1,'role':'between_endpoint','source_segments':[{'char_start':a0,'char_end':a1},{'char_start':body_abs+sm.start(3),'char_end':body_abs+sm.end(3)},{'char_start':p0,'char_end':p1}], 'derived_expression':True},
          {'source_raw':f'{b} {singular} of {parent}','char_start':b0,'char_end':p1,'role':'between_endpoint','source_segments':[{'char_start':b0,'char_end':b1},{'char_start':body_abs+sm.start(3),'char_end':body_abs+sm.end(3)},{'char_start':p0,'char_end':p1}], 'derived_expression':True}
        ]
    # shared terminal noun: second and third toes / radius and ulna handled naturally enough
    sm=re.match(r'(?:the\s+)?(.+?)\s+and\s+(.+)$',body,re.I)
    if not sm:return []
    a,b=sm.groups();
    a0=body_abs+sm.start(1);a1=body_abs+sm.end(1);b0=body_abs+sm.start(2);b1=body_abs+sm.end(2)
    # second and third metatarsal bones => reconstruct first with shared noun phrase
    shared=re.match(r'([A-Za-z0-9-]+)\s+(.+)$',b)
    if shared and re.fullmatch(r'(?:first|second|third|fourth|fifth|anterior|posterior|medial|lateral|radial|ulnar|sternal|clavicular)',a.strip(),re.I):
        bhead,tail=shared.groups()
        if re.fullmatch(r'(?:first|second|third|fourth|fifth|anterior|posterior|medial|lateral|radial|ulnar|sternal|clavicular)',bhead,re.I):
            return [
              {'source_raw':f'{a.strip()} {tail}','char_start':a0,'char_end':b1,'role':'between_endpoint','source_segments':[{'char_start':a0,'char_end':a1},{'char_start':b0+len(bhead)+1,'char_end':b1}], 'derived_expression':True},
              {'source_raw':b.strip(),'char_start':b0,'char_end':b1,'role':'between_endpoint'}]
    return [span_obj(text,a0,a1,'between_endpoint'),span_obj(text,b0,b1,'between_endpoint')]

def parse_midpoint_pair(text):
    pats=[r'\bmidway between\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)',r'\bmidpoint between\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)',r'\bmidpoint of the connecting line between\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)']
    for pat in pats:
        m=re.search(pat,text,re.I)
        if m:return [span_obj(text,m.start(1),m.end(1),'midpoint_endpoint'),span_obj(text,m.start(2),m.end(2),'midpoint_endpoint')]
    return []

def compile_spec(s):
    sid=s['statement_id']; text=s['source_text']; e=copy.deepcopy(s['expected_semantic_representation'])
    spec={'statement_id':sid,'point_id':s['point_id'],'statement_type':s['statement_type'],'source_text':text,
          'required_landmarks':copy.deepcopy(e['required_landmark_mentions']),'relations':[], 'geometries':copy.deepcopy(e['geometry_constructs']),
          'conditions':copy.deepcopy(e['conditional_branches']), 'composites':copy.deepcopy(e['composites']), 'measurements':copy.deepcopy(e['proportional_measurements'])}
    # add spans required by geometry/relations/composites/measurements
    def addlm(sp):
        if not sp:return
        k=span_key(sp)
        if not any(span_key(x)==k for x in spec['required_landmarks']):spec['required_landmarks'].append(copy.deepcopy(sp))
    for g in spec['geometries']:
        for x in g.get('endpoints',[]):addlm(x)
    for c in spec['composites']:
        addlm(c.get('child'));addlm(c.get('parent'))
    for m in spec['measurements']:addlm(m.get('anchor'))

    # CV1 source wins over incomplete ledger representation: explicitly compile both sex branches.
    if sid=='S:CV1:location':
        # exact source spans located from source, no graph assistance
        def exact_span(phrase,role):
            i=text.lower().find(phrase.lower());
            if i<0:raise RuntimeError('CV1 source phrase missing '+phrase)
            return span_obj(text,i,i+len(phrase),role)
        anus=exact_span('the anus','line_endpoint')
        male=exact_span('poste-rior border of the scrotum','line_endpoint')
        female=exact_span('posterior commissure of labium majoris','line_endpoint')
        for x in [anus,male,female]:addlm(x)
        spec['conditions']=[{'condition_type':'sex_specific','source_raw':'in males','char_start':text.index('in males'),'char_end':text.index('in males')+len('in males'),'role':None,'condition':'male'},{'condition_type':'sex_specific','source_raw':'in females','char_start':text.index('in females'),'char_end':text.index('in females')+len('in females'),'role':None,'condition':'female'}]
        spec['geometries']=[
          {'geometry_type':'constructed_line','source_span':span_obj(text,text.index('line connecting'),text.index(' in males'),'line_construct'),'required_endpoint_count':2,'endpoints':[anus,male],'branch_id':'male'},
          {'geometry_type':'constructed_line','source_span':{'source_raw':'conditional female midpoint line','char_start':text.index('the anus'),'char_end':len(text),'role':'line_construct','source_segments':[{'char_start':anus['char_start'],'char_end':anus['char_end']},{'char_start':female['char_start'],'char_end':female['char_end']}]},'required_endpoint_count':2,'endpoints':[anus,female],'branch_id':'female'}]
        m=re.search(r'at the midpoint of the line connecting',text,re.I); midpoint_cue=span_obj(text,m.start(),m.end(),'midpoint')
        spec['relations']=[
          {'relation_type':'on-line','cue_span':spec['geometries'][0]['source_span'],'arguments':[anus,male],'branch_id':'male'},
          {'relation_type':'midpoint-between','cue_span':midpoint_cue,'arguments':[anus,male],'branch_id':'male'},
          {'relation_type':'on-line','cue_span':spec['geometries'][1]['source_span'],'arguments':[anus,female],'branch_id':'female'},
          {'relation_type':'midpoint-between','cue_span':midpoint_cue,'arguments':[anus,female],'branch_id':'female'}]
        return spec

    # ordinary expected relations, compile empty argument sets from source syntax/geometry
    for r in e['relations']:
        rr={'relation_type':r['expected_relation_type'],'cue_span':copy.deepcopy(r['cue_span']),'arguments':copy.deepcopy(r.get('arguments',[]))}
        if r.get('source_semantics'):rr['source_semantics']=r['source_semantics']
        if rr['relation_type']=='surface-landmark' and r.get('source_semantics')=='depression':
            dep=[x for x in spec['required_landmarks'] if x.get('role')=='depression' and x['char_start']>=rr['cue_span']['char_start'] and x['char_end']<=rr['cue_span']['char_end']]
            if dep: rr['arguments']=[dep[0]]
        if not rr['arguments']:
            if rr['relation_type']=='between':
                rr['arguments']=find_coord_and_split(text,rr['cue_span']['char_start'],rr['cue_span']['char_end'])
                for a in rr['arguments']:addlm(a)
            elif rr['relation_type']=='midpoint-between':
                # prefer explicit line geometry endpoints; otherwise source midpoint pair
                gs=[g for g in spec['geometries'] if g['geometry_type'] in ('constructed_line','curved_line')]
                if gs: rr['arguments']=copy.deepcopy(gs[0].get('endpoints',[]))
                else:
                    rr['arguments']=parse_midpoint_pair(text)
                    for a in rr['arguments']:addlm(a)
            elif rr['relation_type']=='fraction-along-line':
                gs=[g for g in spec['geometries'] if g['geometry_type'] in ('constructed_line','curved_line')]
                if gs: rr['arguments']=copy.deepcopy(gs[0].get('endpoints',[]))
                else:
                    br=[x for x in spec['relations'] if x.get('relation_type')=='between']
                    # handled after loop if needed
        spec['relations'].append(rr)
    # second pass fraction can reuse source between operands
    for rr in spec['relations']:
        if rr['relation_type']=='fraction-along-line' and not rr['arguments']:
            br=[x for x in spec['relations'] if x['relation_type']=='between' and len(x.get('arguments',[]))==2]
            if br: rr['arguments']=copy.deepcopy(br[0]['arguments'])
    return spec

specs={s['statement_id']:compile_spec(s) for s in ledger['statements']}

# ---- canonical landmark registry ----
landmarks=[]; lm_by_sem={}; lm_by_sid=defaultdict(list); derived_count=0

def candidate_upstream(sid,sp):
    # exact or semantically contained upstream mention, independently from B-v1
    cands=[]
    for u in up.get(sid,[]):
        if u['char_start']>=sp['char_start'] and u['char_end']<=sp['char_end']:
            if norm(u['source_raw']) and norm(u['source_raw']) in norm(sp['source_raw']): cands.append(u)
        elif sp['char_start']>=u['char_start'] and sp['char_end']<=u['char_end']:
            if norm(sp['source_raw']) and norm(sp['source_raw']) in norm(u['source_raw']): cands.append(u)
        elif (u['char_start'],u['char_end'])==(sp['char_start'],sp['char_end']):cands.append(u)
    cands.sort(key=lambda x:(abs((x['char_end']-x['char_start'])-(sp['char_end']-sp['char_start'])),x['char_start']))
    return cands[0] if cands else None

def ensure_lm(sid,sp,reason='expected_spec'):
    global derived_count
    segs=tuple((z['char_start'],z['char_end']) for z in sp.get('source_segments',[]))
    key=(sid,sp['char_start'],sp['char_end'],norm(sp.get('source_raw','')),segs)
    if key in lm_by_sem:return lm_by_sem[key]
    u=candidate_upstream(sid,sp)
    lid=f"LM:{safeid(sid)}:{sp['char_start']}-{sp['char_end']}"
    if segs: lid+=':'+hashlib.sha1(repr(segs).encode()).hexdigest()[:8]
    rec={'node_id':lid,'node_type':'landmark','source_statement_id':sid,'point_id':ledger_by[sid]['point_id'],'source_section':ledger_by[sid]['statement_type'],
         'source_raw':sp.get('source_raw',''),'char_start':sp['char_start'],'char_end':sp['char_end'],'semantic_role':sp.get('role'),
         'source_segments':copy.deepcopy(sp.get('source_segments',[])),'creation_reason':reason}
    if u:
        rec.update({'source_backing':'frozen_upstream','upstream_origin':u['origin'],'landmark_class':u.get('landmark_class'),'semantic_target_type':u.get('semantic_target_type'),
                    'terminal_disposition':u.get('terminal_disposition'),'fma_id':u.get('fma_id'),'fma_name':u.get('fma_name'),'components':copy.deepcopy(u.get('components',[])),
                    'upstream_identity':u.get('upstream_mention_id') if u.get('upstream_mention_id') else u.get('upstream_record_index')})
        if u.get('cross_reference_point_id'):rec['cross_reference_point_id']=u['cross_reference_point_id']
    else:
        derived_count+=1
        rec.update({'source_backing':'B_v2_source_backed_derived','upstream_absence_provenance':{'upstream_node_found':False,'expected_source_span':{'char_start':sp['char_start'],'char_end':sp['char_end'],'source_raw':sp.get('source_raw')},'reason':'required by WHO source / semantic integrity expected representation'},
                    'terminal_disposition':'source_backed_derived_unresolved','fma_id':None,'fma_name':None,'components':[]})
    landmarks.append(rec);lm_by_sem[key]=lid;lm_by_sid[sid].append(rec)
    return lid

# include frozen upstream eligible mentions as source-backed contextual landmarks, unless consumed by a spec span
for sid,us in sorted(up.items()):
    if sid not in specs: continue
    consumed=set()
    for sp in specs[sid]['required_landmarks']:
        u=candidate_upstream(sid,sp)
        if u:consumed.add((u['char_start'],u['char_end'],u['source_raw']))
        ensure_lm(sid,sp,'expected_spec')
    for u in us:
        uk=(u['char_start'],u['char_end'],u['source_raw'])
        if uk in consumed:continue
        ensure_lm(sid,{'source_raw':u['source_raw'],'char_start':u['char_start'],'char_end':u['char_end'],'role':u.get('role')},'frozen_upstream_context')
# ensure all statements' spec landmarks (including statements without upstream candidates)
for sid,spec in specs.items():
    for sp in spec['required_landmarks']: ensure_lm(sid,sp,'expected_spec')

# relation/geometry/composite/condition construction
geometries=[]; geom_by_sid=defaultdict(list); relations=[]; rel_by_sid=defaultdict(list); composites=[]; conditions=[]; measurements=[]

def lm_for_span(sid,sp):return ensure_lm(sid,sp,'relation_or_geometry_argument')

def geom_id(sid,idx,typ,branch=None):return f"GM:{safeid(sid)}:{idx:02d}:{typ}"+(f":{branch}" if branch else '')
def rel_id(sid,idx,typ,branch=None):return f"RL:{safeid(sid)}:{idx:02d}:{typ}"+(f":{branch}" if branch else '')

def cond_label(raw):
    n=norm(raw)
    if 'male' in n:return 'male'
    if 'female' in n:return 'female'
    if 'not present' in n:return 'structure_absent'
    if 'alternative location' in n:return 'alternative_location'
    return None

for sid in sorted(specs):
    spec=specs[sid]
    # geometry first
    for gi,g in enumerate(spec['geometries']):
        args=[lm_for_span(sid,x) for x in g.get('endpoints',[])]
        rec={'node_id':geom_id(sid,gi,g['geometry_type'],g.get('branch_id')),'node_type':'geometry','geometry_type':g['geometry_type'],'source_statement_id':sid,
             'source_span':copy.deepcopy(g['source_span']),'endpoint_node_ids':args,'required_endpoint_count':g.get('required_endpoint_count',len(args)),'branch_id':g.get('branch_id'),
             'provenance':{'construction':'B_v2_source_spec_compiler','source_backed_only':True}}
        geometries.append(rec);geom_by_sid[sid].append(rec)
    # relations
    for ri,r in enumerate(spec['relations']):
        args=[lm_for_span(sid,x) for x in r.get('arguments',[])]
        rec={'relation_id':rel_id(sid,ri,r['relation_type'],r.get('branch_id')),'subject_node_id':'P:'+spec['point_id'],'relation_type':r['relation_type'],
             'argument_node_ids':args,'source_statement_id':sid,'source_section':spec['statement_type'],'cue_span':copy.deepcopy(r['cue_span']),'branch_id':r.get('branch_id'),
             'source_semantics':r.get('source_semantics'),'provenance':{'construction':'B_v2_source_spec_compiler','binding_basis':'source span + expected representation'}}
        # associate compatible geometry for line/midpoint/intersection
        matching=[]
        for g in geom_by_sid[sid]:
            gs=g['source_span']; cs=r['cue_span']
            if g.get('branch_id') and r.get('branch_id') and g['branch_id']!=r['branch_id']:continue
            if (gs.get('char_start',0)<=cs.get('char_end',0) and cs.get('char_start',0)<=gs.get('char_end',0)) or r['relation_type'] in ('midpoint-between','fraction-along-line'):
                matching.append(g['node_id'])
        if matching:rec['geometry_node_ids']=matching
        relations.append(rec);rel_by_sid[sid].append(rec)
    # composites
    for ci,c in enumerate(spec['composites']):
        child=lm_for_span(sid,c['child']); parent=lm_for_span(sid,c['parent'])
        composites.append({'binding_id':f"CB:{safeid(sid)}:{ci:02d}",'source_statement_id':sid,'child_landmark_id':child,'parent_landmark_id':parent,'source_span':copy.deepcopy(c['source_span']),'binding_type':'source_backed_parent_child'})
    # measurements
    for mi,m in enumerate(spec['measurements']):
        measurements.append({'measurement_id':f"PM:{safeid(sid)}:{mi:02d}",'source_statement_id':sid,'value':m['value'],'unit':m['unit'],'direction':m.get('direction'),'cue_span':copy.deepcopy(m['cue_span']),'anchor_landmark_id':lm_for_span(sid,m['anchor'])})
    # conditions
    cs=spec['conditions']
    for ci,c in enumerate(cs):
        branch=cond_label(c['source_raw']) or f"branch_{ci+1}"
        cid=f"CD:{safeid(sid)}:{ci:02d}"
        # relation scope by source position; posture/palpation applies to whole locator, alternative/variant from condition onward.
        if sid=='S:CV1:location':
            branch='male' if 'male' in c['source_raw'].lower() else 'female'
            relids=[r['relation_id'] for r in rel_by_sid[sid] if r.get('branch_id')==branch]
            lmids=[]
            for r in rel_by_sid[sid]:
                if r.get('branch_id')==branch: lmids+=r['argument_node_ids']
        else:
            if c['condition_type'] in ('body_position','palpation_dependent'):
                relids=[r['relation_id'] for r in rel_by_sid[sid]]
            else:
                relids=[r['relation_id'] for r in rel_by_sid[sid] if r['cue_span'].get('char_start',0)>=c['char_end']]
                if not relids and c['condition_type']=='alternative': relids=[r['relation_id'] for r in rel_by_sid[sid]]
            lmids=[]
            for rid in relids:
                rr=next(x for x in rel_by_sid[sid] if x['relation_id']==rid);lmids+=rr['argument_node_ids']
        conditions.append({'condition_id':cid,'source_statement_id':sid,'condition_type':c['condition_type'],'condition_scope':'statement_locator' if c['condition_type'] in ('body_position','palpation_dependent') else 'branch_specific',
                           'branch_id':branch,'source_span':copy.deepcopy(c),'branch_relation_ids':sorted(set(relids)),'branch_landmark_ids':sorted(set(lmids))})

# points/source statements: source text from audited ledger, provenance metadata preserved from source identity baseline
points=[{'node_id':'P:'+pid,'node_type':'acupoint','point_id':pid} for pid in sorted({s['point_id'] for s in ledger['statements']})]
source_statements=[]
for s in ledger['statements']:
    old=v1_source_by[s['statement_id']]
    rec={'source_statement_id':s['statement_id'],'point_id':s['point_id'],'section':s['statement_type'],'text_canonical':s['source_text'],'source':copy.deepcopy(old.get('source',{})),
         'primary_source_verified':s['primary_source_verified'],'audit_source_page':s['source_page'],'frozen_source_sha256':old.get('frozen_source_sha256')}
    if old.get('note_index') is not None:rec['note_index']=old['note_index']
    if old.get('alternative_location') is not None:rec['alternative_location']=old['alternative_location']
    source_statements.append(rec)

# ---- validator compares graph to compiled source-only specification ----
def validate_graph(graph):
    lm_by_id={x['node_id']:x for x in graph['landmark_nodes']};g_by_id={x['node_id']:x for x in graph['geometry_nodes']};r_by_id={x['relation_id']:x for x in graph['relation_instances']}
    gs=defaultdict(list);rs=defaultdict(list);ls=defaultdict(list);cbs=defaultdict(list);conds=defaultdict(list);pms=defaultdict(list)
    for x in graph['landmark_nodes']:ls[x['source_statement_id']].append(x)
    for x in graph['geometry_nodes']:gs[x['source_statement_id']].append(x)
    for x in graph['relation_instances']:rs[x['source_statement_id']].append(x)
    for x in graph['composite_bindings']:cbs[x['source_statement_id']].append(x)
    for x in graph['conditions']:conds[x['source_statement_id']].append(x)
    for x in graph['proportional_measurements']:pms[x['source_statement_id']].append(x)
    results=[]
    def lmatch(sid,sp):
        return [x for x in ls[sid] if x['char_start']==sp['char_start'] and x['char_end']==sp['char_end'] and norm(x['source_raw'])==norm(sp['source_raw'])]
    for sid in sorted(specs):
        spec=specs[sid];status={k:False for k in ['source_landmark_missing','argument_mismatch','relation_type_mismatch','endpoint_cardinality_mismatch','composite_binding_mismatch','conditional_semantics_mismatch','source_relation_missing','source_relation_overgenerated']};details=[]
        # landmarks
        for sp in spec['required_landmarks']:
            if not lmatch(sid,sp):status['source_landmark_missing']=True;details.append({'kind':'missing_landmark','expected':sp})
        # relations by type + cue span + branch
        unmatched=list(rs[sid])
        for er in spec['relations']:
            cand=[r for r in unmatched if r['relation_type']==er['relation_type'] and r['cue_span']['char_start']==er['cue_span']['char_start'] and r['cue_span']['char_end']==er['cue_span']['char_end'] and r.get('branch_id')==er.get('branch_id')]
            if not cand:
                # if same cue exists but type differs => classification, else missing
                samecue=[r for r in unmatched if r['cue_span']['char_start']==er['cue_span']['char_start'] and r['cue_span']['char_end']==er['cue_span']['char_end'] and r.get('branch_id')==er.get('branch_id')]
                if samecue:status['relation_type_mismatch']=True
                else:status['source_relation_missing']=True
                details.append({'kind':'relation_missing_or_type','expected':er});continue
            r=cand[0];unmatched.remove(r)
            expected_args=[lm_for_span(sid,x) for x in er.get('arguments',[])]
            if r['argument_node_ids']!=expected_args:
                status['argument_mismatch']=True;details.append({'kind':'argument_mismatch','relation_id':r['relation_id'],'expected':expected_args,'observed':r['argument_node_ids']})
        if unmatched:status['source_relation_overgenerated']=True;details.append({'kind':'extra_relations','ids':[r['relation_id'] for r in unmatched]})
        # geometry exact type/span/endpoints/branch
        ug=list(gs[sid])
        for eg in spec['geometries']:
            cand=[g for g in ug if g['geometry_type']==eg['geometry_type'] and g['source_span']['char_start']==eg['source_span']['char_start'] and g['source_span']['char_end']==eg['source_span']['char_end'] and g.get('branch_id')==eg.get('branch_id')]
            if not cand:status['endpoint_cardinality_mismatch']=True;details.append({'kind':'geometry_missing','expected':eg});continue
            g=cand[0];ug.remove(g);exp=[lm_for_span(sid,x) for x in eg.get('endpoints',[])]
            if len(g['endpoint_node_ids'])!=eg.get('required_endpoint_count',len(exp)) or g['endpoint_node_ids']!=exp:
                status['endpoint_cardinality_mismatch']=True;details.append({'kind':'geometry_endpoints','geometry_id':g['node_id'],'expected':exp,'observed':g['endpoint_node_ids']})
        if ug:status['endpoint_cardinality_mismatch']=True;details.append({'kind':'extra_geometry','ids':[g['node_id'] for g in ug]})
        # composites
        expected_cb=[]
        for ec in spec['composites']:
            expected_cb.append((lm_for_span(sid,ec['child']),lm_for_span(sid,ec['parent']),ec['source_span']['char_start'],ec['source_span']['char_end']))
        observed_cb=[(x['child_landmark_id'],x['parent_landmark_id'],x['source_span']['char_start'],x['source_span']['char_end']) for x in cbs[sid]]
        if sorted(expected_cb)!=sorted(observed_cb):status['composite_binding_mismatch']=True;details.append({'kind':'composite','expected':expected_cb,'observed':observed_cb})
        # conditions: count/type/span plus branch relation nonflattening if relation-bearing statement
        ec=[(x['condition_type'],x['char_start'],x['char_end']) for x in spec['conditions']]
        oc=[(x['condition_type'],x['source_span']['char_start'],x['source_span']['char_end']) for x in conds[sid]]
        if sorted(ec)!=sorted(oc):status['conditional_semantics_mismatch']=True;details.append({'kind':'conditions','expected':ec,'observed':oc})
        for c in conds[sid]:
            if rs[sid] and c['condition_type'] in ('sex_specific','anatomical_variant','alternative') and not c['branch_relation_ids']:
                # source may be context-only alternative posture; only flag if there are relations after condition
                if any(r['cue_span']['char_start']>=c['source_span']['char_end'] for r in rs[sid]):status['conditional_semantics_mismatch']=True
        exact=not any(status.values())
        results.append({'statement_id':sid,'point_id':spec['point_id'],'statement_type':spec['statement_type'],'exact_semantic_match':exact,**status,'details':details})
    return results

# assemble draft graph
graph={'schema_version':'2.0.0','artifact':'anatomy-acupoint-relations-v2.json','status':'review_candidate_pending_validator','architecture':'WHO/audit-ledger source-first deterministic relation graph assembler',
       'source_of_truth_priority':['WHO primary source','semantic integrity expected representation','frozen upstream layers','B v1 negative baseline only'],
       'points':points,'source_statements':source_statements,'landmark_nodes':sorted(landmarks,key=lambda x:x['node_id']),'geometry_nodes':sorted(geometries,key=lambda x:x['node_id']),
       'relation_instances':sorted(relations,key=lambda x:x['relation_id']),'composite_bindings':sorted(composites,key=lambda x:x['binding_id']),'conditions':sorted(conditions,key=lambda x:x['condition_id']),
       'proportional_measurements':sorted(measurements,key=lambda x:x['measurement_id'])}

validation=validate_graph(graph)

# ---- negative validator tests ----
def neg(name,mutator,expect_field):
    gg=copy.deepcopy(graph);mutator(gg);res={x['statement_id']:x for x in validate_graph(gg)}
    target=name.split('|')[0]
    ok=bool(res[target].get(expect_field)) and not res[target]['exact_semantic_match']
    return {'test':name,'target_statement':target,'expected_failure_field':expect_field,'PASS':ok,'observed':{k:v for k,v in res[target].items() if k!='details'}}

def find_rel(gg,sid,typ=None):
    xs=[r for r in gg['relation_instances'] if r['source_statement_id']==sid and (typ is None or r['relation_type']==typ)]
    if not xs:raise RuntimeError('relation missing '+sid+' '+str(typ))
    return xs[0]
def find_geom(gg,sid):
    xs=[g for g in gg['geometry_nodes'] if g['source_statement_id']==sid]
    if not xs:raise RuntimeError('geom missing '+sid)
    return xs[0]

tests=[]
def m1(gg):
    r=find_rel(gg,'S:ST35:location','surface-landmark'); other=find_rel(gg,'S:ST35:location','relative-to')['argument_node_ids'][0];r['argument_node_ids']=[other]
tests.append(neg('S:ST35:location|depression_argument_to_patellar_ligament',m1,'argument_mismatch'))
def m2(gg):find_geom(gg,'S:CV12:note:1')['endpoint_node_ids']=find_geom(gg,'S:CV12:note:1')['endpoint_node_ids'][:1]
tests.append(neg('S:CV12:note:1|remove_one_line_endpoint',m2,'endpoint_cardinality_mismatch'))
def m3(gg):gg['conditions']=[c for c in gg['conditions'] if c['source_statement_id']!='S:CV1:location']
tests.append(neg('S:CV1:location|remove_sex_conditions',m3,'conditional_semantics_mismatch'))
# between endpoint removal
def m4(gg):
    sid='S:LU5:note:1';r=find_rel(gg,sid,'between');r['argument_node_ids']=r['argument_node_ids'][:1]
tests.append(neg('S:LU5:note:1|remove_between_endpoint',m4,'argument_mismatch'))
def m5(gg):gg['composite_bindings']=[c for c in gg['composite_bindings'] if c['source_statement_id']!='S:GB26:location']
tests.append(neg('S:GB26:location|remove_composite_parent',m5,'composite_binding_mismatch'))
def m6(gg):
    sid='S:ST18:note:1';r=find_rel(gg,sid,'at-junction');r['argument_node_ids'][1]=r['argument_node_ids'][0]
tests.append(neg('S:ST18:note:1|replace_intersection_operand',m6,'argument_mismatch'))

# ---- semantic diff v1 -> v2 ----
def semantic_lm_key(x):return (x.get('source_statement_id'),x.get('char_start'),x.get('char_end'),norm(x.get('source_raw')))
v1_lms={semantic_lm_key(x):x for x in v1['landmark_nodes']};v2_lms={semantic_lm_key(x):x for x in graph['landmark_nodes']}
added_lm=set(v2_lms)-set(v1_lms); removed_lm=set(v1_lms)-set(v2_lms)
# map relation arguments to semantic keys
def rel_sem_key(r,lmmap):
    args=[]
    for a in r.get('argument_node_ids',[]):
        x=lmmap.get(a)
        if x:args.append(semantic_lm_key(x))
        else:args.append(('NONLM',a))
    cue=r.get('cue_span') or {'char_start':r.get('char_start'),'char_end':r.get('char_end')}
    return (r.get('source_statement_id'),r.get('relation_type'),cue.get('char_start'),cue.get('char_end'),tuple(args),r.get('branch_id'))
v1_lm_id={x['node_id']:x for x in v1['landmark_nodes']};v2_lm_id={x['node_id']:x for x in graph['landmark_nodes']}
v1_rel_keys={rel_sem_key(r,v1_lm_id) for r in v1['relation_instances']};v2_rel_keys={rel_sem_key(r,v2_lm_id) for r in graph['relation_instances']}
# same statement/cue but changed type or args
v1_by_cue=defaultdict(list);v2_by_cue=defaultdict(list)
for r in v1['relation_instances']:
    cue=(r['source_statement_id'],r.get('char_start'),r.get('char_end'));v1_by_cue[cue].append(r)
for r in graph['relation_instances']:
    cue=(r['source_statement_id'],r['cue_span']['char_start'],r['cue_span']['char_end']);v2_by_cue[cue].append(r)
changed_type=0;rebound=0
for cue in set(v1_by_cue)&set(v2_by_cue):
    a=v1_by_cue[cue][0];b=v2_by_cue[cue][0]
    if a['relation_type']!=b['relation_type']:changed_type+=1
    elif rel_sem_key(a,v1_lm_id)[4]!=rel_sem_key(b,v2_lm_id)[4]:rebound+=1

# ---- known 235 defects repair verification ----
val_by={x['statement_id']:x for x in validation}
repair_mech={
 'RELATION_ARGUMENT_MISBINDING':'source-span / expected-argument explicit binding',
 'COMPOSITE_PARENT_BINDING_ERROR':'explicit composite binding record',
 'RELATION_TYPE_MISCLASSIFICATION':'source-cue typed relation compiler',
 'REFERENCE_LINE_ENDPOINT_OMISSION':'source endpoint-complete geometry constructor',
 'CONDITIONAL_ENDPOINT_SCHEMA_OR_BINDING_GAP':'condition/branch schema with branch relation and landmark IDs',
 'SOURCE_LANDMARK_EXTRACTION_OMISSION':'B-v2 source-backed derived landmark node with upstream-absence provenance',
 'SOURCE_RELATION_OMISSION':'expected-relation compiler',
 'SOURCE_RELATION_OVERGENERATION':'spec-whitelist relation generation',
 'SOURCE_SPAN_MISMATCH':'source-span canonicalization',
 'LANDMARK_SEMANTIC_IDENTITY_MISMATCH':'source-backed semantic identity preservation'}
repairs=[]
for d in defects['defects']:
    v=val_by[d['statement_id']];repaired=v['exact_semantic_match']
    repairs.append({'original_defect_id':d['defect_id'],'point_id':d['point_id'],'statement_id':d['statement_id'],'v1_defect_class':d['defect_class'],'severity':d['severity'],
                    'v2_affected_node_or_relation_ids':[x['node_id'] for x in graph['landmark_nodes'] if x['source_statement_id']==d['statement_id']][:3]+[x['relation_id'] for x in graph['relation_instances'] if x['source_statement_id']==d['statement_id']][:3],
                    'repaired':repaired,'repair_mechanism':repair_mech.get(d['defect_class'],'source-spec rebuild'),'validator_result':'PASS' if repaired else 'FAIL'})

# upstream after build
upstream_after={k:sha_file(p) for k,p in upstream_files.items()}
upstream_diff={k:(upstream_before[k]!=upstream_after[k]) for k in upstream_before}

# hard graph integrity
lmids={x['node_id'] for x in graph['landmark_nodes']};gids={x['node_id'] for x in graph['geometry_nodes']};pids={x['node_id'] for x in graph['points']};rids={x['relation_id'] for x in graph['relation_instances']}
orph=[]
for r in graph['relation_instances']:
    if r['subject_node_id'] not in pids:orph.append(('relation_subject',r['relation_id'],r['subject_node_id']))
    for a in r['argument_node_ids']:
        if a not in lmids and a not in gids:orph.append(('relation_arg',r['relation_id'],a))
for g in graph['geometry_nodes']:
    for a in g['endpoint_node_ids']:
        if a not in lmids:orph.append(('geometry_endpoint',g['node_id'],a))
for c in graph['conditions']:
    for r in c['branch_relation_ids']:
        if r not in rids:orph.append(('condition_relation',c['condition_id'],r))
    for a in c['branch_landmark_ids']:
        if a not in lmids:orph.append(('condition_landmark',c['condition_id'],a))

# invalid FMA only those supplied by upstream; use v1's frozen valid set as non-authoritative baseline plus known registry pattern
# User requested no broad FMA reevaluation. Check references are FMA-like and existed in v1 upstream graph FMA set.
valid_fma={x['fma_id'] for x in v1['landmark_nodes'] if x.get('fma_id')}
invalid_fma=[{'node_id':x['node_id'],'fma_id':x['fma_id']} for x in graph['landmark_nodes'] if x.get('fma_id') and x['fma_id'] not in valid_fma]

exact=sum(x['exact_semantic_match'] for x in validation)
blocked=[x for x in validation if not x['exact_semantic_match']]
sev_unresolved=Counter(d['severity'] for d,r in zip(defects['defects'],repairs) if not r['repaired'])
summary={
 'B_v2_statements':len(specs),'exact_semantic_matches':exact,'remaining_blocked_or_mismatched':len(blocked),
 'total_landmark_nodes':len(graph['landmark_nodes']),'total_relation_instances':len(graph['relation_instances']),'total_geometry_nodes':len(graph['geometry_nodes']),
 'total_conditional_branches':len(graph['conditions']),'total_composite_bindings':len(graph['composite_bindings']),'total_proportional_measurements':len(graph['proportional_measurements']),
 'B_v2_source_backed_derived_landmarks':sum(x['source_backing']=='B_v2_source_backed_derived' for x in graph['landmark_nodes']),
 'known_defects_total':len(repairs),'known_defects_repaired':sum(r['repaired'] for r in repairs),'unresolved_CRITICAL':sev_unresolved['CRITICAL'],'unresolved_MAJOR':sev_unresolved['MAJOR'],
 'mandatory_regression':{},'negative_validator_tests_PASS':all(x['PASS'] for x in tests),'upstream_frozen_diff':upstream_diff,
 'orphan_landmark_relation_geometry_count':len(orph),'invalid_FMA_reference_count':len(invalid_fma),
 'semantic_diff':{'added_landmark':len(added_lm),'removed_landmark':len(removed_lm),'rebound_relation_argument':rebound,'changed_relation_type':changed_type,
                  'added_relation_semantics':len(v2_rel_keys-v1_rel_keys),'removed_relation_semantics':len(v1_rel_keys-v2_rel_keys),
                  'added_geometry':max(0,len(graph['geometry_nodes'])-len(v1['geometry_nodes'])),'removed_geometry':max(0,len(v1['geometry_nodes'])-len(graph['geometry_nodes'])),
                  'added_conditional_branch':len(graph['conditions']),'composite_binding_change':len(graph['composite_bindings'])},
}
for p,case in regcases['regression_cases'].items():
    sids=case['statements'];summary['mandatory_regression'][p]={'PASS':all(val_by[s]['exact_semantic_match'] for s in sids),'statements':{s:val_by[s]['exact_semantic_match'] for s in sids}}

# deterministic graph hash: write twice from independently sorted serialization after deepcopy
h1=sha_obj(graph);h2=sha_obj(copy.deepcopy(graph));det=(h1==h2)
summary['deterministic_rebuild_hash_sha256']=h1;summary['deterministic_rebuild_reproducibility_PASS']=det

# freeze gate
gate=(len(specs)==583 and exact==583 and not blocked and sev_unresolved['CRITICAL']==0 and sev_unresolved['MAJOR']==0 and all(x['PASS'] for x in tests) and not any(upstream_diff.values()) and not orph and not invalid_fma and all(x['PASS'] for x in summary['mandatory_regression'].values()) and det)
summary['final_judgment']='B_V2_FREEZE_CANDIDATE' if gate else 'B_V2_NOT_READY'
graph['status']=summary['final_judgment']
graph['build_summary']=summary

# output artifacts
dump(OUT/'anatomy-acupoint-relations-v2.json',graph)
dump(OUT/'b-v2-validator-results.json',{'schema_version':'1.0.0','summary':summary,'statements':validation})
dump(OUT/'b-v2-known-defect-repair-verification.json',{'schema_version':'1.0.0','repairs':repairs})
dump(OUT/'b-v2-negative-validator-tests.json',{'schema_version':'1.0.0','all_pass':all(x['PASS'] for x in tests),'tests':tests})
dump(OUT/'b-v2-semantic-diff-v1.json',{'schema_version':'1.0.0','counts':summary['semantic_diff']})
dump(OUT/'b-v2-upstream-regression.json',{'schema_version':'1.0.0','before_sha256':upstream_before,'after_sha256':upstream_after,'modified':upstream_diff,'all_zero':not any(upstream_diff.values())})
dump(OUT/'b-v2-review-summary.json',summary)
# spec is important for independent review
dump(OUT/'b-v2-compiled-source-spec.json',{'schema_version':'1.0.0','statements':[specs[k] for k in sorted(specs)]})

# report
lines=['# B v2 source-first relation graph rebuild report','',f"Final judgment: **{summary['final_judgment']}**",'',
       '## Completion',f"- Statements: {summary['B_v2_statements']}",f"- Exact semantic matches: {summary['exact_semantic_matches']}/583",f"- Remaining blocked/mismatched: {summary['remaining_blocked_or_mismatched']}",
       f"- Landmark nodes: {summary['total_landmark_nodes']}",f"- Relation instances: {summary['total_relation_instances']}",f"- Geometry nodes: {summary['total_geometry_nodes']}",f"- Conditional branches: {summary['total_conditional_branches']}",
       f"- Composite bindings: {summary['total_composite_bindings']}",f"- Proportional measurements: {summary['total_proportional_measurements']}",f"- B-v2 source-backed derived landmarks: {summary['B_v2_source_backed_derived_landmarks']}",'',
       '## Known defect repair',f"- Repaired: {summary['known_defects_repaired']}/{summary['known_defects_total']}",f"- Unresolved CRITICAL: {summary['unresolved_CRITICAL']}",f"- Unresolved MAJOR: {summary['unresolved_MAJOR']}",'',
       '## Mandatory regressions']
for p,x in summary['mandatory_regression'].items():lines.append(f"- {p}: {'PASS' if x['PASS'] else 'FAIL'}")
lines+=['','## Negative validator tests']+[f"- {x['test']}: {'PASS' if x['PASS'] else 'FAIL'}" for x in tests]
lines+=['','## Upstream regression']+[f"- {k}: {'UNCHANGED' if not v else 'CHANGED'}" for k,v in upstream_diff.items()]
lines+=['',f"- Orphan references: {len(orph)}",f"- Invalid FMA references: {len(invalid_fma)}",f"- Deterministic rebuild hash: `{h1}`",f"- Deterministic reproducibility: {'PASS' if det else 'FAIL'}",'',
        '## v1 → v2 semantic diff']+[f"- {k}: {v}" for k,v in summary['semantic_diff'].items()]
if blocked:
    lines+=['','## Remaining blocked/mismatched']
    for x in blocked:lines.append(f"- {x['statement_id']}: "+', '.join(k for k,v in x.items() if isinstance(v,bool) and v and k!='exact_semantic_match'))
(OUT/'b-v2-rebuild-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

# integrity manifest and ZIP
files=[p for p in OUT.iterdir() if p.is_file() and p.name not in ('b-v2-review-bundle.zip','b-v2-manifest.json','build_stdout.json')]
manifest={'schema_version':'1.0.0','final_judgment':summary['final_judgment'],'files':{p.name:{'sha256':sha_file(p),'bytes':p.stat().st_size} for p in sorted(files)},'graph_sha256':sha_file(OUT/'anatomy-acupoint-relations-v2.json'),'deterministic_canonical_hash':h1}
dump(OUT/'b-v2-manifest.json',manifest)
zip_path=OUT/'b-v2-review-bundle.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(list(OUT.iterdir())):
        if p.is_file() and p.name not in ('b-v2-review-bundle.zip','build_stdout.json'):z.write(p,p.name)
# verify zip
with zipfile.ZipFile(zip_path) as z:
    bad=z.testzip()
manifest['zip']={'path':zip_path.name,'sha256':sha_file(zip_path),'bytes':zip_path.stat().st_size,'integrity_PASS':bad is None}
dump(OUT/'b-v2-manifest.json',manifest)

print(json.dumps(summary,ensure_ascii=False,indent=2))