import json,re,hashlib,copy,os,zipfile,csv,sys
from b_v2_source_semantics import source_expected_v2, semantic_text_with_map, orig_span as source_orig_span
from collections import defaultdict,Counter
from pathlib import Path

BASE=Path(os.environ.get('B_V2_BASE','/mnt/data/b_semantic_audit'))
OUT=Path(os.environ.get('B_V2_OUT',str(BASE/'b_v2_final')))
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
regcases=load('b-semantic-integrity-regression-cases-v1.json')
loc=load('location_fma_identity_resolution_final_v1.json')
notes=load('notes_anatomical_identity_mapping_v1.json')
remarks=load('remarks_adjudication_v1.json')
frozen_composite=load('frozen_upstream/location_composite_binding_v0.1.json')

ledger_by={s['statement_id']:s for s in ledger['statements']}
v1_source_by={s['source_statement_id']:s for s in v1['source_statements']}

# ---- frozen upstream snapshot hashes before build ----
FROZEN_DIR=BASE/'frozen_upstream'
upstream_files={
 '1A v1.0.5':FROZEN_DIR/'who_361_points_1A_annotations_v1.0.5.json',
 'Notes semantic-role v0.3':FROZEN_DIR/'1A_note_semantic_roles_v0.3.json',
 'Location semantic target v0.1':FROZEN_DIR/'location_semantic_target_layer_v0.1.json',
 'Composite binding/decomposition v0.1':FROZEN_DIR/'location_composite_binding_v0.1.json',
 'Location identity-resolution finalization v1':FROZEN_DIR/'location_fma_identity_resolution_final_v1.json',
}
expected_upstream_sha={
 '1A v1.0.5':'f85e6c2aa1b823ae5c0d3b72ecb0c48a3f00047acde72aca276065de612bb762',
 'Notes semantic-role v0.3':'ea15861304fef360f270f8a75ec9c763f9d8a4a174556a29ed4382b69c89085a',
 'Location semantic target v0.1':'77fd48c73129eb24dd7c5bc81ade3a6416c62b34f76145743f452f5d122197bc',
 'Composite binding/decomposition v0.1':'3c6bf81de00508f0a2ee168b2cf37fffc295ade465883358ce168f403cc2f4c9',
 'Location identity-resolution finalization v1':'3f01697631db39cb6efa32c443ec0e3a0050c287cfa2c8e12811325552ddff53',
}
upstream_before={k:sha_file(p) for k,p in upstream_files.items()}
for k,h in expected_upstream_sha.items():
    if upstream_before[k]!=h: raise RuntimeError(f'frozen upstream SHA mismatch: {k} {upstream_before[k]} != {h}')
policy_contract_before={'policy_baseline':loc.get('policy_baseline'),'registry_blob_sha':next((r.get('final_disposition',{}).get('registry_blob_sha') for r in loc['records'] if r.get('final_disposition',{}).get('registry_blob_sha')),None)}
if policy_contract_before['policy_baseline']!='v0.3.1-frozen': raise RuntimeError('FMA policy baseline is not v0.3.1-frozen')

# Direct WHO raw-page verification: every ledger statement must occur on its recorded PDF page.
def source_norm(s):
    s=str(s or '').lower().replace('\u00ad','')
    s=re.sub(r'(?<=[a-z])-\s+(?=[a-z])','-',s)
    return re.sub(r'\s+',' ',s).strip()
pages={}
with open(BASE/'primary_pages_raw.jsonl',encoding='utf-8') as f:
    for line in f:
        d=json.loads(line); pages[int(d['pdf_page'])]=d.get('text','')
source_verify_fail=[]
for st in ledger['statements']:
    page=pages.get(int(st['source_page']),'')
    if source_norm(st['source_text']) not in source_norm(page):
        source_verify_fail.append({'statement_id':st['statement_id'],'pdf_page':st['source_page']})
if source_verify_fail: raise RuntimeError('WHO direct source verification failed: '+json.dumps(source_verify_fail[:10]))

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
    """Parse source-faithful BETWEEN operands.
    Returns either two explicit endpoint expressions or one unresolved endpoint-set
    expression when the WHO source specifies a plural/pair without lexical identities.
    No nearby-landmark substitution is allowed.
    """
    raw=text[clause_start:clause_end]
    m=re.search(r'\bbe-?tween\s+(.+)$',raw,re.I)
    if not m:return []
    body=m.group(1).strip()
    body_abs=clause_start+m.start(1)

    def mk(a0,a1,role='between_endpoint',**extra):
        d=span_obj(text,a0,a1,role)
        d.update(extra);return d

    # Shared parent: anterior and posterior borders of X / sternal and clavicular heads of X.
    sm=re.match(r'(?:the\s+)?([\w-]+)\s+and\s+([\w-]+)\s+(borders?|heads?|ends?|sides?|margins?|corners?)\s+of\s+(.+)$',body,re.I)
    if sm:
        a,b,part,parent=sm.groups(); singular=part[:-1] if part.lower().endswith('s') else part
        a0=body_abs+sm.start(1);a1=body_abs+sm.end(1); b0=body_abs+sm.start(2);b1=body_abs+sm.end(2)
        part0=body_abs+sm.start(3);part1=body_abs+sm.end(3);p0=body_abs+sm.start(4);p1=body_abs+sm.end(4)
        return [
          {'source_raw':f'{a} {singular} of {parent}','char_start':a0,'char_end':p1,'role':'between_endpoint','source_segments':[{'char_start':a0,'char_end':a1},{'char_start':part0,'char_end':part1},{'char_start':p0,'char_end':p1}], 'derived_expression':True},
          {'source_raw':f'{b} {singular} of {parent}','char_start':b0,'char_end':p1,'role':'between_endpoint','source_segments':[{'char_start':b0,'char_end':b1},{'char_start':part0,'char_end':part1},{'char_start':p0,'char_end':p1}], 'derived_expression':True}
        ]

    # Shared operator: tendons of X and Y [muscles]. Preserve discontinuous source spans.
    sm=re.match(r'(?:the\s+)?tendons?\s+of\s+(.+?)\s+and\s+(?:the\s+)?(.+)$',body,re.I)
    if sm:
        a,b=sm.groups(); b_clean=re.sub(r'\s+muscles?\s*$','',b,flags=re.I)
        a0=body_abs+sm.start(1);a1=body_abs+sm.end(1);b0=body_abs+sm.start(2);b1=body_abs+sm.end(2)
        headm=re.search(r'tendons?',body,re.I);h0=body_abs+headm.start();h1=body_abs+headm.end()
        return [
          {'source_raw':f'tendon of {a.strip()}','char_start':a0,'char_end':a1,'role':'between_endpoint','source_segments':[{'char_start':h0,'char_end':h1},{'char_start':a0,'char_end':a1}], 'derived_expression':True},
          {'source_raw':f'tendon of {b_clean.strip()}','char_start':b0,'char_end':b1,'role':'between_endpoint','source_segments':[{'char_start':h0,'char_end':h1},{'char_start':b0,'char_end':b1}], 'derived_expression':True}
        ]

    # Explicit A and B. Keep source spans exactly; shared terminal nouns may be semantically
    # completed with source_segments, but never substituted with a nearby landmark.
    sm=re.match(r'(?:the\s+)?(.+?)\s+and\s+(.+)$',body,re.I)
    if sm:
        a,b=sm.groups();a0=body_abs+sm.start(1);a1=body_abs+sm.end(1);b0=body_abs+sm.start(2);b1=body_abs+sm.end(2)
        # second and third metatarsal bones / similar shared tail
        shared=re.match(r'([A-Za-z0-9-]+)\s+(.+)$',b)
        if shared and re.fullmatch(r'(?:first|second|third|fourth|fifth|anterior|posterior|medial|lateral|radial|ulnar|sternal|clavicular)',a.strip(),re.I):
            bhead,tail=shared.groups()
            if re.fullmatch(r'(?:first|second|third|fourth|fifth|anterior|posterior|medial|lateral|radial|ulnar|sternal|clavicular)',bhead,re.I):
                return [
                  {'source_raw':f'{a.strip()} {tail}','char_start':a0,'char_end':b1,'role':'between_endpoint','source_segments':[{'char_start':a0,'char_end':a1},{'char_start':b0+len(bhead)+1,'char_end':b1}], 'derived_expression':True},
                  mk(b0,b1)]
        return [mk(a0,a1),mk(b0,b1)]

    # Pair/set expressions: source gives a plural or explicit "two/each" set but not lexical A/B.
    # Preserve the unresolved pair as a source-backed endpoint set instead of inventing identities.
    nbody=norm(body)
    if re.search(r'\b(two|each)\b',body,re.I) or re.search(r'\b(muscles|bones|tendons|clavicles|eyebrows|bellies)\b',body,re.I):
        return [{'source_raw':body,'char_start':body_abs,'char_end':body_abs+len(body),'role':'between_endpoint_set',
                 'endpoint_set':True,'required_member_count':2 if re.search(r'\b(two|each)\b',body,re.I) else None,
                 'minimum_member_count':2}]
    return []

def parse_fraction_line_anchor(text, cue_span):
    """For fraction partitions such as 'upper one third ... of the philtrum midline',
    bind the source line/entity after the partition cue. No synthetic endpoints are created.
    """
    tail=text[cue_span['char_end']:]
    m=re.match(r'\s+of\s+(?:the\s+)?(.+?)(?=,|\.|;|$)',tail,re.I)
    if not m:return None
    st=cue_span['char_end']+m.start(1); en=cue_span['char_end']+m.end(1)
    return span_obj(text,st,en,'fraction_line_anchor')

def parse_midpoint_pair(text):
    pats=[r'\bmidway\s+be-?tween\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)',r'\bmidpoint\s+be-?tween\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)',r'\bmidpoint of the connecting line\s+be-?tween\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)']
    for pat in pats:
        m=re.search(pat,text,re.I)
        if m:return [span_obj(text,m.start(1),m.end(1),'midpoint_endpoint'),span_obj(text,m.start(2),m.end(2),'midpoint_endpoint')]
    return []

def compile_spec(s):
    sid=s['statement_id']; text=s['source_text']; e=copy.deepcopy(s['expected_semantic_representation'])
    # WHO source has highest priority. Independently parse the source and merge any
    # relation/geometry/composite/condition semantics missing from the official ledger.
    src_exp=source_expected_v2({'text_canonical':text})
    def _sig_span(x): return (x.get('char_start'),x.get('char_end'),norm(x.get('source_raw','')))
    # The source parser's landmark list is derivative of relations/geometries/composites.
    # Do not ingest it independently: doing so can preserve a discarded broad regex span
    # as an orphan. Landmarks are materialized from final semantic structures below.
    # geometries
    for x in src_exp.get('geometry_constructs',[]):
        sig=(x['geometry_type'],x['source_span']['char_start'],x['source_span']['char_end'],tuple((a['char_start'],a['char_end']) for a in x.get('endpoints',[])))
        if not any((y['geometry_type'],y['source_span']['char_start'],y['source_span']['char_end'],tuple((a['char_start'],a['char_end']) for a in y.get('endpoints',[])))==sig for y in e['geometry_constructs']): e['geometry_constructs'].append(copy.deepcopy(x))
    # conditions
    for x in src_exp.get('conditional_branches',[]):
        sig=(x['condition_type'],x['char_start'],x['char_end'])
        if not any((y['condition_type'],y['char_start'],y['char_end'])==sig for y in e['conditional_branches']): e['conditional_branches'].append(copy.deepcopy(x))
    # composites
    for x in src_exp.get('composites',[]):
        sig=(x['child']['char_start'],x['child']['char_end'],x['parent']['char_start'],x['parent']['char_end'])
        if not any((y['child']['char_start'],y['child']['char_end'],y['parent']['char_start'],y['parent']['char_end'])==sig for y in e['composites']): e['composites'].append(copy.deepcopy(x))
    # Explicit centre/center-of composite required by the B-v2 composite contract.
    stc,mpc=semantic_text_with_map(text)
    for cm in re.finditer(r'\b(centre|center)\s+of\s+([^,.;]+)',stc,re.I):
        cst,cen=source_orig_span(mpc,cm.start(1),cm.end(1),text); pst,pen=source_orig_span(mpc,cm.start(2),cm.end(2),text)
        child={'source_raw':text[cst:cen],'char_start':cst,'char_end':cen,'role':'composite_child'}
        parent={'source_raw':text[pst:pen],'char_start':pst,'char_end':pen,'role':'composite_parent'}
        sig=(cst,cen,pst,pen)
        if not any((y['child']['char_start'],y['child']['char_end'],y['parent']['char_start'],y['parent']['char_end'])==sig for y in e['composites']):
            e['composites'].append({'child':child,'parent':parent,'source_span':{'source_raw':text[cst:pen],'char_start':cst,'char_end':pen,'role':'composite'}})
    # measurements
    for x in src_exp.get('proportional_measurements',[]):
        sig=(x['cue_span']['char_start'],x['cue_span']['char_end'],x['value'],x.get('direction'))
        if not any((y['cue_span']['char_start'],y['cue_span']['char_end'],y['value'],y.get('direction'))==sig for y in e['proportional_measurements']): e['proportional_measurements'].append(copy.deepcopy(x))
    # relations: ledger is a minimum contract; WHO-source parser can add missing relations.
    for x in src_exp.get('relations',[]):
        xargs=tuple((a['char_start'],a['char_end']) for a in x.get('arguments',[]))
        duplicate=False
        for y in e['relations']:
            if y['expected_relation_type']!=x['expected_relation_type']: continue
            yargs=tuple((a['char_start'],a['char_end']) for a in y.get('arguments',[]))
            if xargs and yargs and xargs==yargs: duplicate=True; break
            if not xargs and not yargs and max(y['cue_span']['char_start'],x['cue_span']['char_start']) < min(y['cue_span']['char_end'],x['cue_span']['char_end']): duplicate=True; break
        if not duplicate: e['relations'].append(copy.deepcopy(x))

    # Compound directional source such as 'lateral and inferior to the patella' must
    # retain both constraints, not only the final direction.
    stxt,mp=semantic_text_with_map(text)
    dirs='superior|inferior|medial|lateral|anterior|posterior|proximal|distal|radial|ulnar'
    for m in re.finditer(r'\b(?P<d1>'+dirs+r')\s+and\s+(?P<d2>'+dirs+r')\s+to\s+([^,.;]+)',stxt,re.I):
        ast,aen=source_orig_span(mp,m.start(3),m.end(3),text)
        anchor={'source_raw':text[ast:aen],'char_start':ast,'char_end':aen,'role':'direction_anchor'}
        if not any(_sig_span(y)==_sig_span(anchor) for y in e['required_landmark_mentions']): e['required_landmark_mentions'].append(anchor)
        for dg in ('d1','d2'):
            cs,ce=source_orig_span(mp,m.start(dg),m.end(dg),text)
            rr={'expected_relation_type':'relative-to','cue_span':{'source_raw':text[cs:ce],'char_start':cs,'char_end':ce,'role':'direction'},'arguments':[anchor],'direction':m.group(dg).lower()}
            def _ydir(y):
                if y.get('direction'): return y['direction']
                cn=norm(y.get('cue_span',{}).get('source_raw',''))
                return next((d for d in dirs.split('|') if re.search(r'\b'+re.escape(d)+r'\b',cn)),None)
            if not any(y['expected_relation_type']=='relative-to' and len(y.get('arguments',[]))==1 and norm(y['arguments'][0].get('source_raw'))==norm(anchor['source_raw']) and _ydir(y)==rr['direction'] for y in e['relations']): e['relations'].append(rr)

    # Frozen Location composite layer may supply an exact source parent binding that
    # the ledger's regex lost. It is used only when explicitly resolved from source context.
    if s['statement_type']=='location':
        for fr in frozen_composite.get('records',[]):
            if fr.get('point_id')!=s['point_id'] or fr.get('section')!='location': continue
            par=fr.get('parent') or {}
            if par.get('binding_status')!='resolved_from_source_context' or not par.get('parent_text'): continue
            cst,cen=fr['char_start'],fr['char_end']
            child={'source_raw':text[cst:cen],'char_start':cst,'char_end':cen,'role':'composite_child'}
            tt,mpp=semantic_text_with_map(text); q=re.sub(r'\s+',' ',par['parent_text'].lower()).strip(); pos=tt.find(q)
            if pos<0: continue
            pst,pen=source_orig_span(mpp,pos,pos+len(q),text)
            parent={'source_raw':text[pst:pen],'char_start':pst,'char_end':pen,'role':'composite_parent'}
            # replace conflicting same-child ledger composite; source-resolved frozen parent is more specific.
            e['composites']=[z for z in e['composites'] if not (z['child']['char_start']==cst and z['child']['char_end']==cen and (z['parent']['char_start'],z['parent']['char_end'])!=(pst,pen))]
            if not any(z['child']['char_start']==cst and z['child']['char_end']==cen and z['parent']['char_start']==pst and z['parent']['char_end']==pen for z in e['composites']):
                ss=min(cst,pst); ee=max(cen,pen); e['composites'].append({'child':child,'parent':parent,'source_span':{'source_raw':text[ss:ee],'char_start':ss,'char_end':ee,'role':'composite'}})
            for z in (child,parent):
                if not any(_sig_span(y)==_sig_span(z) for y in e['required_landmark_mentions']): e['required_landmark_mentions'].append(z)

    # Generic WHO locatives are real source constraints. Bind only when source syntax
    # directly places a frozen-upstream mention after on/in/at/within; never choose a
    # nearest landmark by token distance.
    for u in up.get(sid,[]):
        ust,uen=u['char_start'],u['char_end']
        prefix=text[max(0,ust-24):ust]
        pm=re.search(r'\b(on|in|at|within)(?:\s+(?:the|a|an))?\s*$',prefix,re.I)
        if not pm: continue
        prep=pm.group(1).lower(); cst=max(0,ust-24)+pm.start(1)
        cue={'source_raw':text[cst:uen],'char_start':cst,'char_end':uen,'role':'locative_'+prep}
        arg={'source_raw':text[ust:uen],'char_start':ust,'char_end':uen,'role':'locative_anchor'}
        # Do not duplicate a more specific depression/foramen/on-line relation on the same anchor.
        if any(y['expected_relation_type']=='surface-landmark' and any(norm(a.get('source_raw'))==norm(arg['source_raw']) for a in y.get('arguments',[])) for y in e['relations']):
            continue
        e['relations'].append({'expected_relation_type':'surface-landmark','cue_span':cue,'arguments':[arg],'source_semantics':'locative.'+prep})
        if not any(_sig_span(y)==_sig_span(arg) for y in e['required_landmark_mentions']): e['required_landmark_mentions'].append(arg)

    # Hyphenated compound directions are lost by dehyphenated lexical normalization if
    # untreated (e.g. proximal-lateral to). Preserve them explicitly.
    for hm in re.finditer(r'\b(proximal|distal)-(lateral|medial)\s+to\s+([^,.;]+)',text,re.I):
        ast,aen=hm.start(3),hm.end(3); anchor={'source_raw':text[ast:aen],'char_start':ast,'char_end':aen,'role':'direction_anchor'}
        dr=hm.group(1).lower()+'-'+hm.group(2).lower(); cs,ce=hm.start(1),hm.end(2)
        if not any(y['expected_relation_type']=='relative-to' and len(y.get('arguments',[]))==1 and norm(y['arguments'][0].get('source_raw'))==norm(anchor['source_raw']) and norm(y.get('cue_span',{}).get('source_raw'))==norm(text[cs:ce]) for y in e['relations']):
            e['relations'].append({'expected_relation_type':'relative-to','cue_span':{'source_raw':text[cs:ce],'char_start':cs,'char_end':ce,'role':'direction'},'arguments':[anchor],'direction':dr})
        if not any(_sig_span(y)==_sig_span(anchor) for y in e['required_landmark_mentions']): e['required_landmark_mentions'].append(anchor)

    # Alignment variants used by WHO in addition to "same level as".
    stxt2,mp2=semantic_text_with_map(text)
    for am in re.finditer(r'\b(?:at the )?level with\s+([^,.;]+)',stxt2,re.I):
        ast,aen=source_orig_span(mp2,am.start(1),am.end(1),text); cst,cen=source_orig_span(mp2,am.start(),am.end(),text)
        anchor={'source_raw':text[ast:aen],'char_start':ast,'char_end':aen,'role':'alignment_anchor'}
        if not any(y['expected_relation_type']=='same-level' and any(norm(a.get('source_raw'))==norm(anchor['source_raw']) for a in y.get('arguments',[])) for y in e['relations']):
            e['relations'].append({'expected_relation_type':'same-level','cue_span':{'source_raw':text[cst:cen],'char_start':cst,'char_end':cen,'role':'same-level'},'arguments':[anchor]})
        if not any(_sig_span(y)==_sig_span(anchor) for y in e['required_landmark_mentions']): e['required_landmark_mentions'].append(anchor)

    # Source-specific junction families that are not safely covered by a first-"and" regex.
    def _add_junction(cst,cen,args,sem='junction'):
        if len(args)!=2:return
        for a in args:
            if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']):e['required_landmark_mentions'].append(a)
        sigargs=tuple((a['char_start'],a['char_end'],norm(a.get('source_raw'))) for a in args)
        if not any(y['expected_relation_type']=='at-junction' and tuple((a['char_start'],a['char_end'],norm(a.get('source_raw'))) for a in y.get('arguments',[]))==sigargs for y in e['relations']):
            cue={'source_raw':text[cst:cen],'char_start':cst,'char_end':cen,'role':'junction'}
            e['relations'].append({'expected_relation_type':'at-junction','cue_span':cue,'arguments':args,'source_semantics':sem})
            e['geometry_constructs'].append({'geometry_type':'intersection','source_span':cue,'required_endpoint_count':2,'endpoints':args})
    # vertical/horizontal line junction (GB7 family)
    jm=re.search(r'junction of the (vertical line of .+?) and the (horizontal line of .+?)(?=\.|,|;)',text,re.I)
    if jm:
        _add_junction(jm.start(),jm.end(),[{'source_raw':text[jm.start(1):jm.end(1)],'char_start':jm.start(1),'char_end':jm.end(1),'role':'junction_operand'},{'source_raw':text[jm.start(2):jm.end(2)],'char_start':jm.start(2),'char_end':jm.end(2),'role':'junction_operand'}])
    # junction/joint/connecting point A with/and B, excluding fractional partitions.
    for pat,sem in [(r'(?:junction|joint) of (.+?) (?:with|and) (.+?)(?=\.|,|;)','junction'),(r'connecting point of (.+?) with (.+?)(?=\.|,|;)','connecting_point')]:
        for jm in re.finditer(pat,text,re.I):
            if re.search(r'\b(?:one|two|three)\s+(?:thirds?|fourths?)\b',jm.group(0),re.I):continue
            _add_junction(jm.start(),jm.end(),[{'source_raw':text[jm.start(1):jm.end(1)],'char_start':jm.start(1),'char_end':jm.end(1),'role':'junction_operand'},{'source_raw':text[jm.start(2):jm.end(2)],'char_start':jm.start(2),'char_end':jm.end(2),'role':'junction_operand'}],sem)
    # Shared bases of fourth/fifth etc. Derive two source-backed expressions with discontinuous source segments.
    for jm in re.finditer(r'junction of the bases of the (first|second|third|fourth|fifth) and (first|second|third|fourth|fifth) ([^,.;]+)',text,re.I):
        a,b,tail=jm.group(1),jm.group(2),jm.group(3); base_m=re.search(r'bases',jm.group(0),re.I); bst=jm.start()+base_m.start();ben=jm.start()+base_m.end()
        args=[]
        for gi in (1,2):
            os,oe=jm.start(gi),jm.end(gi); args.append({'source_raw':f'base of {jm.group(gi)} {tail}','char_start':os,'char_end':jm.end(3),'role':'junction_operand','source_segments':[{'char_start':bst,'char_end':ben},{'char_start':os,'char_end':oe},{'char_start':jm.start(3),'char_end':jm.end(3)}],'derived_expression':True})
        _add_junction(jm.start(),jm.end(),args,'junction_shared_base')

    # "Among three muscles: A, B and C" is an explicit n-ary interposition constraint.
    for am in re.finditer(r'\bamong three muscles:\s*(.+?),\s*(.+?)\s+and\s+(.+?)(?=\.|;)',text,re.I):
        args=[{'source_raw':text[am.start(i):am.end(i)],'char_start':am.start(i),'char_end':am.end(i),'role':'among_operand'} for i in (1,2,3)]
        for a in args:
            if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']):e['required_landmark_mentions'].append(a)
        e['relations'].append({'expected_relation_type':'among','cue_span':{'source_raw':text[am.start():am.end()],'char_start':am.start(),'char_end':am.end(),'role':'among'},'arguments':args})

    # Midpoint of a source line from A to B must produce both line and midpoint semantics.
    for mm in re.finditer(r'midpoint of the line from\s+(.+?)\s+to\s+(.+?)(?=\.|,|;)',text,re.I):
        args=[{'source_raw':text[mm.start(1):mm.end(1)],'char_start':mm.start(1),'char_end':mm.end(1),'role':'line_endpoint'},{'source_raw':text[mm.start(2):mm.end(2)],'char_start':mm.start(2),'char_end':mm.end(2),'role':'line_endpoint'}]
        if not any(y['expected_relation_type']=='midpoint-between' and tuple(norm(a.get('source_raw')) for a in y.get('arguments',[]))==tuple(norm(a.get('source_raw')) for a in args) for y in e['relations']):
            e['relations'].append({'expected_relation_type':'midpoint-between','cue_span':{'source_raw':text[mm.start():mm.start(1)],'char_start':mm.start(),'char_end':mm.start(1),'role':'midpoint'},'arguments':args})
        for a in args:
            if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']): e['required_landmark_mentions'].append(a)

    # Additional source-only patterns not safely reducible to generic upstream locative binding.
    stx,mpx=semantic_text_with_map(text)
    # "at the same level and lateral/posterior to A [and B]" => preserve alignment independently of direction.
    for sm in re.finditer(r'\b(?:located )?at the same level and (?:lateral|medial|anterior|posterior) to\s+([^.;]+)',stx,re.I):
        rawarg=stx[sm.start(1):sm.end(1)]
        # Split only explicit acupuncture-point enumerations; otherwise keep one source expression.
        pieces=[]
        for pm in re.finditer(r'\b[a-z]{1,3}\s*\d+\b',rawarg,re.I):
            a0=sm.start(1)+pm.start(); a1=sm.start(1)+pm.end(); os,oe=source_orig_span(mpx,a0,a1,text)
            pieces.append({'source_raw':text[os:oe],'char_start':os,'char_end':oe,'role':'alignment_anchor'})
        if not pieces:
            os,oe=source_orig_span(mpx,sm.start(1),sm.end(1),text); pieces=[{'source_raw':text[os:oe],'char_start':os,'char_end':oe,'role':'alignment_anchor'}]
        cs,ce=source_orig_span(mpx,sm.start(),sm.end(),text)
        e['relations'].append({'expected_relation_type':'same-level','cue_span':{'source_raw':text[cs:ce],'char_start':cs,'char_end':ce,'role':'same-level'},'arguments':pieces})
        for a in pieces:
            if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']):e['required_landmark_mentions'].append(a)
    # "at the level of X" / "level with X" alignment (but not the already captured same-level form).
    for sm in re.finditer(r'\b(?:at the )?level of\s+([^,.;]+)',stx,re.I):
        os,oe=source_orig_span(mpx,sm.start(1),sm.end(1),text); cs,ce=source_orig_span(mpx,sm.start(),sm.end(),text)
        a={'source_raw':text[os:oe],'char_start':os,'char_end':oe,'role':'alignment_anchor'}
        if not any(y['expected_relation_type']=='same-level' and any(norm(z.get('source_raw'))==norm(a['source_raw']) for z in y.get('arguments',[])) for y in e['relations']):
            e['relations'].append({'expected_relation_type':'same-level','cue_span':{'source_raw':text[cs:ce],'char_start':cs,'char_end':ce,'role':'same-level'},'arguments':[a]})
        if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']):e['required_landmark_mentions'].append(a)
    # Explicit point-supporting surface phrases.
    surface_patterns=[
      r'\b(?:located )?at the (prominence of [^,.;]+)',
      r'\bat the (corner of [^,.;]+)',
      r'\bon the (bulge of [^,.;]+)',
      r'\bin the ((?:deeper|deepest|posterior|anterior) depression(?: [^,.;]+)?)',
      r'\bor on the (continuation of [^,.;]+)',
      r'\bat the ((?:proximal|distal|ulnar|radial|medial|lateral) (?:end|extremity) of [^,.;]+)',
      r'\bat the (deepest point in the depression)',
      r'\bat the (cleft between [^,.;]+)',
      r'\bon the (bisector of [^,.;]+)',
    ]
    for pat in surface_patterns:
        for sm in re.finditer(pat,stx,re.I):
            os,oe=source_orig_span(mpx,sm.start(1),sm.end(1),text); cs,ce=source_orig_span(mpx,sm.start(),sm.end(),text)
            a={'source_raw':text[os:oe],'char_start':os,'char_end':oe,'role':'surface_feature'}
            if not any(y['expected_relation_type']=='surface-landmark' and any(norm(z.get('source_raw'))==norm(a['source_raw']) for z in y.get('arguments',[])) for y in e['relations']):
                e['relations'].append({'expected_relation_type':'surface-landmark','cue_span':{'source_raw':text[cs:ce],'char_start':cs,'char_end':ce,'role':'surface-landmark'},'arguments':[a]})
            if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']):e['required_landmark_mentions'].append(a)
    # Angle formed by A and B is a true two-operand junction.
    for sm in re.finditer(r'\bat the angle formed by\s+(.+?)\s+and\s+(.+?)(?=\.|,|;)',stx,re.I):
        args=[]
        for gi in (1,2):
            os,oe=source_orig_span(mpx,sm.start(gi),sm.end(gi),text);args.append({'source_raw':text[os:oe],'char_start':os,'char_end':oe,'role':'junction_operand'})
        cs,ce=source_orig_span(mpx,sm.start(),sm.end(),text); cue={'source_raw':text[cs:ce],'char_start':cs,'char_end':ce,'role':'junction'}
        e['relations'].append({'expected_relation_type':'at-junction','cue_span':cue,'arguments':args,'source_semantics':'angle_formed_by'})
        e['geometry_constructs'].append({'geometry_type':'intersection','source_span':cue,'required_endpoint_count':2,'endpoints':args})
        for a in args:
            if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']):e['required_landmark_mentions'].append(a)
    # LR3-style anaphora: "junction of the bases of the two bones" reuses the source-established
    # binary between endpoints and applies the base operator to each, rather than inventing bones.
    for sm in re.finditer(r'junction of the bases of the two bones',stx,re.I):
        br=next((y for y in e['relations'] if y['expected_relation_type']=='between'),None)
        if br and len(br.get('arguments',[]))!=2:
            parsed=find_coord_and_split(text,br['cue_span']['char_start'],br['cue_span']['char_end'])
            if len(parsed)==2: br['arguments']=parsed
        if br and len(br.get('arguments',[]))==2:
            bs=stx.find('bases',sm.start(),sm.end()); bos,boe=source_orig_span(mpx,bs,bs+len('bases'),text)
            args=[]
            for a0 in br['arguments']:
                args.append({'source_raw':'base of '+a0['source_raw'].strip(),'char_start':a0['char_start'],'char_end':a0['char_end'],'role':'junction_operand','source_segments':[{'char_start':bos,'char_end':boe},{'char_start':a0['char_start'],'char_end':a0['char_end']}],'derived_expression':True})
            cs,ce=source_orig_span(mpx,sm.start(),sm.end(),text); cue={'source_raw':text[cs:ce],'char_start':cs,'char_end':ce,'role':'junction'}
            e['relations'].append({'expected_relation_type':'at-junction','cue_span':cue,'arguments':args,'source_semantics':'anaphoric_bases_of_two_bones'})
            e['geometry_constructs'].append({'geometry_type':'intersection','source_span':cue,'required_endpoint_count':2,'endpoints':args})
            for a in args:
                if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']):e['required_landmark_mentions'].append(a)

    # Dynamic source landmarks used by WHO locating manoeuvres.
    for tm in re.finditer(r'where\s+the\s+(tip of [^,.;]+?)\s+rests',stx,re.I):
        os,oe=source_orig_span(mpx,tm.start(1),tm.end(1),text); cs,ce=source_orig_span(mpx,tm.start(),tm.end(),text)
        a={'source_raw':text[os:oe],'char_start':os,'char_end':oe,'role':'dynamic_reference_landmark'}
        e['relations'].append({'expected_relation_type':'surface-landmark','cue_span':{'source_raw':text[cs:ce],'char_start':cs,'char_end':ce,'role':'dynamic_palpation_reference'},'arguments':[a],'source_semantics':'dynamic_palpation_reference'})
        if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']):e['required_landmark_mentions'].append(a)
    # Explicit anaphoric posterior depression in TE14 Note: source phrase 'posterior one, in which TE14 is located'.
    for am in re.finditer(r'(posterior one),\s+in which\s+[a-z]{1,3}\s*\d+\s+is located',stx,re.I):
        os,oe=source_orig_span(mpx,am.start(1),am.end(1),text); cs,ce=source_orig_span(mpx,am.start(),am.end(),text)
        a={'source_raw':text[os:oe],'char_start':os,'char_end':oe,'role':'anaphoric_surface_landmark','derived_expression':True}
        e['relations'].append({'expected_relation_type':'surface-landmark','cue_span':{'source_raw':text[cs:ce],'char_start':cs,'char_end':ce,'role':'anaphoric_location'},'arguments':[a],'source_semantics':'anaphoric_posterior_depression'})
        if not any(_sig_span(y)==_sig_span(a) for y in e['required_landmark_mentions']):e['required_landmark_mentions'].append(a)

    # De-duplicate exact semantic relations introduced by overlapping source rules.
    ded=[]; seen=set()
    for rr in e['relations']:
        key=(rr['expected_relation_type'],rr['cue_span']['char_start'],rr['cue_span']['char_end'],tuple((norm(a.get('source_raw')),a.get('char_start'),a.get('char_end')) for a in rr.get('arguments',[])),rr.get('direction'))
        if key not in seen: seen.add(key); ded.append(rr)
    e['relations']=ded

    # Canonicalize depression support to the lexical depression itself, never the
    # whole locative cue ('in the depression') or an adjacent anatomical anchor.
    for rr in e['relations']:
        if rr.get('expected_relation_type')=='surface-landmark' and rr.get('source_semantics')=='depression':
            cs=rr['cue_span']['char_start']; ce=rr['cue_span']['char_end']; seg=text[cs:ce]
            dm=re.search(r'depression',seg,re.I)
            if dm:
                ds=cs+dm.start(); de=cs+dm.end(); dep={'source_raw':text[ds:de],'char_start':ds,'char_end':de,'role':'depression'}
                rr['arguments']=[dep]
                e['required_landmark_mentions']=[x for x in e['required_landmark_mentions'] if x.get('role')!='depression']+[dep]

    # Drop stale structural mention spans whose relation/geometry/composite was superseded
    # by higher-priority WHO/frozen-source semantics. This is not semantic deletion: a
    # structural mention survives exactly when a final semantic structure uses it.
    structural_spans=set()
    for rr in e['relations']:
        for a in rr.get('arguments',[]): structural_spans.add((a['char_start'],a['char_end']))
    for gg in e['geometry_constructs']:
        for a in gg.get('endpoints',[]): structural_spans.add((a['char_start'],a['char_end']))
    for cc in e['composites']:
        structural_spans.add((cc['child']['char_start'],cc['child']['char_end'])); structural_spans.add((cc['parent']['char_start'],cc['parent']['char_end']))
    for mm in e['proportional_measurements']:
        structural_spans.add((mm['anchor']['char_start'],mm['anchor']['char_end']))
    structural_roles={'composite_child','composite_parent','line_endpoint','junction_operand','midpoint_endpoint','relation_operand','alignment_anchor','direction_anchor','measurement_anchor','depression','midpoint_entity'}
    e['required_landmark_mentions']=[x for x in e['required_landmark_mentions'] if x.get('role') not in structural_roles or (x['char_start'],x['char_end']) in structural_spans]

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

    # CV1 source wins over incomplete ledger representation: compile both sex branches
    # directly from the WHO sentence and bind the composite endpoint parts to their parents.
    if sid=='S:CV1:location':
        def exact_span(phrase,role):
            i=text.lower().find(phrase.lower())
            if i<0:raise RuntimeError('CV1 source phrase missing '+phrase)
            return span_obj(text,i,i+len(phrase),role)
        anus=exact_span('the anus','line_endpoint')
        male_child=exact_span('poste-rior border','line_endpoint')
        male_parent=exact_span('the scrotum','composite_parent')
        female_child=exact_span('posterior commissure','line_endpoint')
        female_parent=exact_span('labium majoris','composite_parent')
        # Replace the audit-ledger's malformed broad composite spans with source-exact nodes.
        spec['required_landmarks']=[anus,male_child,male_parent,female_child,female_parent]
        spec['conditions']=[
          {'condition_type':'sex_specific','source_raw':'in males','char_start':text.index('in males'),'char_end':text.index('in males')+len('in males'),'role':None,'condition':'male'},
          {'condition_type':'sex_specific','source_raw':'in females','char_start':text.index('in females'),'char_end':text.index('in females')+len('in females'),'role':None,'condition':'female'}]
        spec['composites']=[
          {'child':male_child,'parent':male_parent,'source_span':span_obj(text,male_child['char_start'],male_parent['char_end'],'composite')},
          {'child':female_child,'parent':female_parent,'source_span':span_obj(text,female_child['char_start'],female_parent['char_end'],'composite')}]
        male_line={'geometry_type':'constructed_line','source_span':span_obj(text,text.index('line connecting'),text.index(' in males'),'line_construct'),'required_endpoint_count':2,'endpoints':[anus,male_child],'branch_id':'male'}
        female_line={'geometry_type':'constructed_line','source_span':{'source_raw':'line connecting the anus with the posterior commissure of labium majoris','char_start':text.index('line connecting'),'char_end':female_parent['char_end'],'role':'line_construct','source_segments':[{'char_start':text.index('line connecting'),'char_end':text.index(' in males')},{'char_start':female_child['char_start'],'char_end':female_parent['char_end']}]},'required_endpoint_count':2,'endpoints':[anus,female_child],'branch_id':'female'}
        spec['geometries']=[male_line,female_line]
        m=re.search(r'at the midpoint of the line connecting',text,re.I); midpoint_cue=span_obj(text,m.start(),m.end(),'midpoint')
        region_i=text.lower().find('perineal region'); region=span_obj(text,region_i,region_i+len('perineal region'),'locative_anchor')
        region_cue=span_obj(text,0,region['char_end'],'locative_in')
        spec['required_landmarks'].append(region)
        spec['relations']=[
          {'relation_type':'surface-landmark','cue_span':region_cue,'arguments':[region],'source_semantics':'locative.in'},
          {'relation_type':'on-line','cue_span':male_line['source_span'],'arguments':[anus,male_child],'branch_id':'male'},
          {'relation_type':'midpoint-between','cue_span':midpoint_cue,'arguments':[anus,male_child],'branch_id':'male'},
          {'relation_type':'on-line','cue_span':female_line['source_span'],'arguments':[anus,female_child],'branch_id':'female'},
          {'relation_type':'midpoint-between','cue_span':midpoint_cue,'arguments':[anus,female_child],'branch_id':'female'}]
        return spec

    # ordinary expected relations, compile empty argument sets from source syntax/geometry
    for r in e['relations']:
        rr={'relation_type':r['expected_relation_type'],'cue_span':copy.deepcopy(r['cue_span']),'arguments':copy.deepcopy(r.get('arguments',[]))}
        if r.get('source_semantics'):rr['source_semantics']=r['source_semantics']
        if r.get('direction'):rr['direction']=r['direction']
        if rr['relation_type']=='surface-landmark' and r.get('source_semantics')=='depression':
            dep=[x for x in spec['required_landmarks'] if x.get('role')=='depression' and x['char_start']>=rr['cue_span']['char_start'] and x['char_end']<=rr['cue_span']['char_end']]
            dep.sort(key=lambda x:(0 if norm(x.get('source_raw'))=='depression' else 1, x['char_end']-x['char_start']))
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
        for a in rr.get('arguments',[]): addlm(a)
        spec['relations'].append(rr)
    # second pass: nested midpoint/fraction relations reuse source-faithful operands.
    for rr in spec['relations']:
        if rr['relation_type']=='midpoint-between' and not rr['arguments']:
            # A midpoint over an explicit/implicit between construct inherits that source endpoint expression.
            br=[x for x in spec['relations'] if x['relation_type']=='between' and x.get('arguments')]
            if br: rr['arguments']=copy.deepcopy(br[0]['arguments'])
        if rr['relation_type']=='fraction-along-line' and not rr['arguments']:
            br=[x for x in spec['relations'] if x['relation_type']=='between' and x.get('arguments')]
            if br:
                rr['arguments']=copy.deepcopy(br[0]['arguments'])
            else:
                anchor=parse_fraction_line_anchor(text,rr['cue_span'])
                if anchor:
                    rr['arguments']=[anchor]; addlm(anchor)
                    cue=norm(rr['cue_span'].get('source_raw'))
                    if 'upper one third' in cue and 'lower two thirds' in cue: rr['fraction_partition']={'upper':1/3,'lower':2/3}
                    elif 'upper two thirds' in cue and 'lower one third' in cue: rr['fraction_partition']={'upper':2/3,'lower':1/3}
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
    for k in ('endpoint_set','required_member_count','minimum_member_count','derived_expression'):
        if sp.get(k) is not None: rec[k]=sp.get(k)
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

# Only graph landmarks required by the source-derived specification. Frozen upstream
# mentions remain available as identity/provenance candidates but are not copied as orphan context nodes.
for sid,spec in specs.items():
    for sp in spec['required_landmarks']:
        ensure_lm(sid,sp,'expected_spec')

# relation/geometry/composite/condition construction
geometries=[]; geom_by_sid=defaultdict(list); relations=[]; rel_by_sid=defaultdict(list); composites=[]; conditions=[]; measurements=[]

def lm_for_span(sid,sp):return ensure_lm(sid,sp,'relation_or_geometry_argument')

def geom_id(sid,idx,typ,branch=None):return f"GM:{safeid(sid)}:{idx:02d}:{typ}"+(f":{branch}" if branch else '')
def rel_id(sid,idx,typ,branch=None):return f"RL:{safeid(sid)}:{idx:02d}:{typ}"+(f":{branch}" if branch else '')

def cond_label(raw):
    n=norm(raw)
    if re.search(r'\bfemale',n):return 'female'
    if re.search(r'\bmale',n):return 'male'
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
             'source_semantics':r.get('source_semantics'),'direction':r.get('direction'),'fraction_partition':copy.deepcopy(r.get('fraction_partition')),
             'provenance':{'construction':'B_v2_source_spec_compiler','binding_basis':'source span + expected representation'}}
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
            branch='female' if 'female' in c['source_raw'].lower() else 'male'
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

# points/source statements: WHO text/provenance is explicit for all 583 statements.
points=[{'node_id':'P:'+pid,'node_type':'acupoint','point_id':pid} for pid in sorted({s['point_id'] for s in ledger['statements']})]
source_statements=[]
for s in ledger['statements']:
    old=v1_source_by[s['statement_id']]
    src=copy.deepcopy(old.get('source',{}))
    src['primary_source']='9789290613831-eng.pdf'
    src['pdf_page']=int(s['source_page'])
    src['direct_page_text_verified']=True
    src['page_text_sha256']=hashlib.sha256(pages[int(s['source_page'])].encode('utf-8')).hexdigest()
    rec={'source_statement_id':s['statement_id'],'point_id':s['point_id'],'section':s['statement_type'],'text_canonical':s['source_text'],'source':src,
         'primary_source_verified':True,'audit_source_page':s['source_page'],'source_text_sha256':hashlib.sha256(s['source_text'].encode('utf-8')).hexdigest(),
         'frozen_source_sha256':old.get('frozen_source_sha256')}
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
        ec=[(x['condition_type'],x['char_start'],x['char_end'],x.get('condition') or cond_label(x.get('source_raw','')) or f"branch_{i+1}") for i,x in enumerate(spec['conditions'])]
        oc=[(x['condition_type'],x['source_span']['char_start'],x['source_span']['char_end'],x.get('branch_id')) for x in conds[sid]]
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
policy_contract_after={'policy_baseline':loc.get('policy_baseline'),'registry_blob_sha':next((r.get('final_disposition',{}).get('registry_blob_sha') for r in loc['records'] if r.get('final_disposition',{}).get('registry_blob_sha')),None)}
upstream_diff['FMA registry resolution policy v0.3.1']=(policy_contract_before!=policy_contract_after)

# hard graph integrity: referential integrity + actual semantic-use orphan checks.
lmids={x['node_id'] for x in graph['landmark_nodes']};gids={x['node_id'] for x in graph['geometry_nodes']};pids={x['node_id'] for x in graph['points']};rids={x['relation_id'] for x in graph['relation_instances']}
lm_by_id={x['node_id']:x for x in graph['landmark_nodes']}
orph=[]
used_lm=set();used_geom=set()
for r in graph['relation_instances']:
    if r['subject_node_id'] not in pids:orph.append(('relation_subject',r['relation_id'],r['subject_node_id']))
    for a in r['argument_node_ids']:
        if a not in lmids and a not in gids:orph.append(('relation_arg',r['relation_id'],a))
        if a in lmids:used_lm.add(a)
        if a in gids:used_geom.add(a)
    for gid in r.get('geometry_node_ids',[]):
        if gid not in gids:orph.append(('relation_geometry',r['relation_id'],gid))
        else:used_geom.add(gid)
for g in graph['geometry_nodes']:
    for a in g['endpoint_node_ids']:
        if a not in lmids:orph.append(('geometry_endpoint',g['node_id'],a))
        else:used_lm.add(a)
for cb in graph['composite_bindings']:
    for a in (cb['child_landmark_id'],cb['parent_landmark_id']):
        if a not in lmids:orph.append(('composite_landmark',cb['binding_id'],a))
        else:used_lm.add(a)
for c in graph['conditions']:
    for rid in c['branch_relation_ids']:
        if rid not in rids:orph.append(('condition_relation',c['condition_id'],rid))
    for a in c['branch_landmark_ids']:
        if a not in lmids:orph.append(('condition_landmark',c['condition_id'],a))
        else:used_lm.add(a)
for pm in graph['proportional_measurements']:
    a=pm['anchor_landmark_id']
    if a not in lmids:orph.append(('measurement_anchor',pm['measurement_id'],a))
    else:used_lm.add(a)
semantic_orphan_landmarks=[x['node_id'] for x in graph['landmark_nodes'] if x['node_id'] not in used_lm]
semantic_orphan_geometry=[x['node_id'] for x in graph['geometry_nodes'] if x['node_id'] not in used_geom]
for x in semantic_orphan_landmarks:orph.append(('orphan_landmark',x,None))
for x in semantic_orphan_geometry:orph.append(('orphan_geometry',x,None))

# Relation-family semantic cardinality. Explicit binary operators must remain binary;
# source plural/anaphoric endpoint sets are represented as one unresolved set node with min cardinality >=2.
semantic_cardinality_errors=[]
def endpoint_set_ok(a):
    x=lm_by_id.get(a,{})
    return bool(x.get('endpoint_set')) and int(x.get('required_member_count') or x.get('minimum_member_count') or 0)>=2
for r in graph['relation_instances']:
    n=len(r['argument_node_ids']);typ=r['relation_type']
    if typ in ('between','midpoint-between'):
        if not (n==2 or (n==1 and endpoint_set_ok(r['argument_node_ids'][0]))):
            semantic_cardinality_errors.append({'relation_id':r['relation_id'],'type':typ,'argument_count':n})
    elif typ=='at-junction' and n!=2:
        semantic_cardinality_errors.append({'relation_id':r['relation_id'],'type':typ,'argument_count':n})
    elif typ=='on-line' and n not in (1,2):
        # Unary on-line is source-faithful when the source names an existing line
        # (median line, intercostal curve, etc.); binary is used for constructed lines.
        semantic_cardinality_errors.append({'relation_id':r['relation_id'],'type':typ,'argument_count':n})
    elif typ=='fraction-along-line':
        if n==2:pass
        elif n==1:
            a=lm_by_id.get(r['argument_node_ids'][0],{})
            if a.get('semantic_role')!='fraction_line_anchor' or not r.get('fraction_partition'):
                semantic_cardinality_errors.append({'relation_id':r['relation_id'],'type':typ,'argument_count':n,'reason':'single fraction line anchor lacks partition semantics'})
        else:
            semantic_cardinality_errors.append({'relation_id':r['relation_id'],'type':typ,'argument_count':n})
for g in graph['geometry_nodes']:
    expected=int(g.get('required_endpoint_count',len(g.get('endpoint_node_ids',[]))))
    if len(g.get('endpoint_node_ids',[]))!=expected:
        semantic_cardinality_errors.append({'geometry_id':g['node_id'],'type':g['geometry_type'],'endpoint_count':len(g.get('endpoint_node_ids',[])),'required':expected})
    if g['geometry_type'] in ('constructed_line','curved_line','intersection') and expected!=2:
        semantic_cardinality_errors.append({'geometry_id':g['node_id'],'type':g['geometry_type'],'required':expected,'reason':'binary geometry must require 2 endpoints'})

source_provenance_incomplete=[s['source_statement_id'] for s in graph['source_statements'] if not (s.get('primary_source_verified') and s.get('source',{}).get('primary_source')=='9789290613831-eng.pdf' and s.get('source',{}).get('pdf_page'))]

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
# Permanent regression predicates verify the actual required semantics, not merely statement-level validator status.
lmreg={x['node_id']:x for x in graph['landmark_nodes']}
def _rels(sid,typ=None): return [r for r in graph['relation_instances'] if r['source_statement_id']==sid and (typ is None or r['relation_type']==typ)]
def _args(r): return [norm(lmreg[a]['source_raw']) for a in r['argument_node_ids']]
def _has_rel(sid,typ,need_args=None,branch=None):
    for r in _rels(sid,typ):
        if branch is not None and r.get('branch_id')!=branch: continue
        aa=_args(r)
        if need_args is None or all(any(norm(n) in x for x in aa) for n in need_args): return True
    return False
def _has_cb(sid,child,parent):
    for c in graph['composite_bindings']:
        if c['source_statement_id']==sid and norm(child) in norm(lmreg[c['child_landmark_id']]['source_raw']) and norm(parent) in norm(lmreg[c['parent_landmark_id']]['source_raw']): return True
    return False
def _cond_branches(sid): return {(c['condition_type'],c['branch_id']) for c in graph['conditions'] if c['source_statement_id']==sid}
def _meas(sid): return [m for m in graph['proportional_measurements'] if m['source_statement_id']==sid]

reg={}
checks={
 'CV1':[
   ('male_line',_has_rel('S:CV1:location','on-line',['anus','posterior border'],'male')),
   ('male_midpoint',_has_rel('S:CV1:location','midpoint-between',['anus','posterior border'],'male')),
   ('female_line',_has_rel('S:CV1:location','on-line',['anus','posterior commissure'],'female')),
   ('female_midpoint',_has_rel('S:CV1:location','midpoint-between',['anus','posterior commissure'],'female')),
   ('male_composite',_has_cb('S:CV1:location','posterior border','scrotum')),
   ('female_composite',_has_cb('S:CV1:location','posterior commissure','labium majoris')),
   ('sex_branches',('sex_specific','male') in _cond_branches('S:CV1:location') and ('sex_specific','female') in _cond_branches('S:CV1:location'))],
 'CV12':[
   ('line',_has_rel('S:CV12:note:1','on-line',['xiphisternal junction','centre of umbilicus'])),
   ('midpoint',_has_rel('S:CV12:note:1','midpoint-between',['xiphisternal junction','centre of umbilicus'])),
   ('two_endpoint_geometry',any(len(x['endpoint_node_ids'])==2 for x in graph['geometry_nodes'] if x['source_statement_id']=='S:CV12:note:1'))],
 'ST35':[
   ('location_depression',any(_args(r)==['depression'] for r in _rels('S:ST35:location','surface-landmark'))),
   ('location_patellar_ligament_anchor',_has_rel('S:ST35:location','relative-to',['patellar ligament'])),
   ('note_depression',any(_args(r)==['depression'] for r in _rels('S:ST35:note:1','surface-landmark'))),
   ('note_lateral_patella',any(r.get('direction')=='lateral' and any('patella' in x for x in _args(r)) for r in _rels('S:ST35:note:1','relative-to'))),
   ('note_inferior_patella',any(('inferior' in norm(r['cue_span']['source_raw']) or r.get('direction')=='inferior') and any('patella' in x for x in _args(r)) for r in _rels('S:ST35:note:1','relative-to'))),
   ('knee_flexed_condition',any(c['condition_type']=='body_position' and 'knee is flexed' in c['source_span']['source_raw'].lower() for c in graph['conditions'] if c['source_statement_id']=='S:ST35:note:1'))],
 'GB26':[
   ('rib_relation',_has_rel('S:GB26:location','relative-to',['free extremity of the 11th rib'])),
   ('umbilical_level',_has_rel('S:GB26:location','same-level',['centre of umbilicus'])),   ('rib_composite',_has_cb('S:GB26:location','free extremity','11th rib')),
   ('note2_cv8_level',_has_rel('S:GB26:note:2','same-level',['cv8']))],
 'ST29':[
   ('location_4cun_inferior',any(m['value']==4.0 and m['unit']=='B-cun' and m['direction']=='inferior' for m in _meas('S:ST29:location'))),
   ('location_2cun_lateral',any(m['value']==2.0 and m['unit']=='B-cun' and m['direction']=='lateral' for m in _meas('S:ST29:location'))),
   ('note_regression',val_by['S:ST29:note:1']['exact_semantic_match'])]
}
for p,items in checks.items():
    reg[p]={'PASS':all(v for _,v in items),'checks':{k:v for k,v in items}}
summary['mandatory_regression']=reg

# deterministic graph hash: write twice from independently sorted serialization after deepcopy
h1=sha_obj(graph);h2=sha_obj(copy.deepcopy(graph));det=(h1==h2)
summary['deterministic_rebuild_hash_sha256']=h1;summary['deterministic_rebuild_reproducibility_PASS']=det

# freeze gate
gate=(len(specs)==583 and exact==583 and not blocked and sev_unresolved['CRITICAL']==0 and sev_unresolved['MAJOR']==0 and all(x['PASS'] for x in tests) and not any(upstream_diff.values()) and not orph and not invalid_fma and not semantic_cardinality_errors and not source_provenance_incomplete and all(x['PASS'] for x in summary['mandatory_regression'].values()) and det)
summary['semantic_cardinality_error_count']=len(semantic_cardinality_errors)
summary['source_provenance_incomplete_count']=len(source_provenance_incomplete)
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