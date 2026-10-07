import re

def norm_pdf(s):
    s=str(s).lower().replace('–','-').replace('—','-').replace('‐','-').replace('−','-')
    s=re.sub(r'-\s+','-',s)
    s=re.sub(r'\s+',' ',s).strip()
    return s

# source-only dehyphenated string with mapping to original positions
def semantic_text_with_map(src):
    out=[]; mp=[]; i=0; prev_space=False
    while i<len(src):
        ch=src[i]
        # remove hyphenation inserted inside alphabetic words
        if ch in '-‐‑‒–—−' and i>0 and i+1<len(src) and src[i-1].isalpha() and src[i+1].isalpha():
            i+=1; continue
        if ch.isspace():
            if not prev_space:
                out.append(' '); mp.append(i); prev_space=True
            i+=1; continue
        prev_space=False
        out.append(ch.lower()); mp.append(i); i+=1
    return ''.join(out),mp

def orig_span(mp,a,b,src):
    if a>=len(mp): return (len(src),len(src))
    st=mp[a]
    en=(mp[b-1]+1) if b>0 and b-1<len(mp) else st
    return st,en

def span_obj(src, mp, a,b, role=None):
    st,en=orig_span(mp,a,b,src)
    return {'source_raw':src[st:en],'char_start':st,'char_end':en,'role':role}

# ---------- independent WHO-source expected representation ----------
DIRS=r'(?:superior|inferior|medial|lateral|anterior|posterior|proximal|distal|radial|ulnar|posterosuperior|posteroinferior|anterosuperior|anteroinferior|medioinferior|proximal lateral|proximal medial|anterior and distal|posterior and superior|posterior and proximal|distal and lateral)'
FRACTION=r'(?:one|two|three)\s+(?:thirds?|fourths?)'

def clause_boundary(t,start):
    xs=[x for x in [t.find(',',start),t.find(';',start),t.find('.',start)] if x!=-1]
    return min(xs) if xs else len(t)

def source_expected_v2(s):
    src=s['text_canonical']; t,mp=semantic_text_with_map(src)
    out={'required_landmark_mentions':[],'relations':[],'conditional_branches':[],'geometry_constructs':[],'proportional_measurements':[],'composites':[]}
    # conditions: source-only, no graph input
    cond_specs=[
      ('sex_specific',r'\bin males?\b|\bin females?\b'),
      ('anatomical_variant',r'\bif\b[^,.]{0,120}'),
      ('body_position',r'\bwhen\b[^,.]{0,120}|\bwith\b[^,.]{0,120}\b(?:flexed|extended|abducted|adducted|opened|closed|supinated|pronated|folded)\b'),
      ('alternative',r'\balternative location\b|\bor on the continuation\b|\bmay be in [^,.]+ or [^,.]+'),
      ('palpation_dependent',r'\b(?:palpat\w*|prominent|more distinct|appears?|felt when|easier to locate|easier to find)\b[^.]*')]
    for kind,pat in cond_specs:
        for m in re.finditer(pat,t,re.I): out['conditional_branches'].append({'condition_type':kind,**span_obj(src,mp,m.start(),m.end())})
    # constructed lines: line connecting A with/and B; curved line from A to B; connecting line between A and B
    line_patterns=[
      # WHO LU3 wording: "line connecting the level with anterior axillary fold to LU5"; the endpoints are the fold-level and LU5.
      ('constructed_line',re.compile(r'\bline connecting the level with\s+(.+?)\s+to\s+(.+?)(?=,|\.|;)',re.I)),
      ('constructed_line',re.compile(r'\bline connecting\s+(.+?)\s+with\s+(.+?)(?=,|\.|;|\bin males\b|\bin females\b|\band the horizontal line\b|\bat the|\b\d+(?:\.\d+)?\s+[bf]cun\b)',re.I)),
      ('constructed_line',re.compile(r'\bline connecting\s+(.+?)\s+and\s+(.+?)(?=,|\.|;|\bin males\b|\bin females\b|\band the horizontal line\b|\bat the|\b\d+(?:\.\d+)?\s+[bf]cun\b)',re.I)),
      ('curved_line',re.compile(r'\bcurved line from\s+(.+?)\s+to\s+(.+?)(?=,|\.|;)',re.I)),
      ('constructed_line',re.compile(r'\bconnecting line between\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)',re.I)),
      ('constructed_line',re.compile(r'\bline from\s+(.+?)\s+to\s+(.+?)(?=,|\.|;)',re.I)),
    ]
    for gtype,pat in line_patterns:
        for m in pat.finditer(t):
            matched=t[m.start():m.end()]
            # Do not let generic line patterns split source-internal conjunctions or sex-specific branches.
            if matched.startswith('line connecting') and 'line connecting the level with' in t and matched != 'line connecting the level with anterior axillary fold to lu5':
                continue
            if matched.startswith('line connecting') and 'line connecting the heel with the web margin between the bases of the second and third toes' in t and 'web margin' not in matched:
                continue
            if matched.startswith('line connecting') and ' in males and ' in t and ' in females' in t:
                continue
            e1=span_obj(src,mp,m.start(1),m.end(1),'line_endpoint'); e2=span_obj(src,mp,m.start(2),m.end(2),'line_endpoint')
            full=span_obj(src,mp,m.start(),m.end(),'line_construct')
            out['geometry_constructs'].append({'geometry_type':gtype,'source_span':full,'required_endpoint_count':2,'endpoints':[e1,e2]})
            out['required_landmark_mentions'] += [e1,e2]
            out['relations'].append({'expected_relation_type':'on-line','cue_span':full,'arguments':[e1,e2]})
    # intersection of X and Y => true two-geometry/landmark junction
    for m in re.finditer(r'\bintersection of\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)',t,re.I):
        a=span_obj(src,mp,m.start(1),m.end(1),'intersection_operand'); b=span_obj(src,mp,m.start(2),m.end(2),'intersection_operand'); cue=span_obj(src,mp,m.start(),m.end(),'intersection')
        out['required_landmark_mentions'] += [a,b]
        out['geometry_constructs'].append({'geometry_type':'intersection','source_span':cue,'required_endpoint_count':2,'endpoints':[a,b]})
        out['relations'].append({'expected_relation_type':'at-junction','cue_span':cue,'arguments':[a,b],'source_semantics':'intersection'})
    # midpoint / midway when directly locating the subject, not merely midpoint used inside another landmark phrase
    for pat in [r'\b(?:is located |is |at |located at )?(?:the )?midpoint of the line connecting\b',r'\b(?:is located |is |at |located at )?(?:the )?midpoint of the curved line from\b',r'\b(?:is located |is |at |located )?midway between\b',r'\b(?:is located |is |at |located at )?(?:the )?midpoint between\b']:
        for m in re.finditer(pat,t,re.I):
            cue=span_obj(src,mp,m.start(),m.end(),'midpoint')
            out['relations'].append({'expected_relation_type':'midpoint-between','cue_span':cue,'arguments':[]})
    # Explicit midpoint/midway endpoints from source only. These are required landmarks even when no line mention node exists.
    midpoint_pair_patterns=[
      re.compile(r'\bmidway between\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)',re.I),
      re.compile(r'\bmidpoint between\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)',re.I),
      re.compile(r'\bmidpoint of the connecting line between\s+(.+?)\s+and\s+(.+?)(?=,|\.|;)',re.I),
    ]
    for pat in midpoint_pair_patterns:
        for m in pat.finditer(t):
            a=span_obj(src,mp,m.start(1),m.end(1),'midpoint_endpoint'); b=span_obj(src,mp,m.start(2),m.end(2),'midpoint_endpoint')
            out['required_landmark_mentions'] += [a,b]

    # between explicit relation
    for m in re.finditer(r'\bbetween\b',t,re.I):
        # skip if part of connecting line between: already handled
        if t[max(0,m.start()-25):m.start()].endswith('connecting line '): continue
        end=clause_boundary(t,m.end())
        cue=span_obj(src,mp,m.start(),end,'between_clause')
        out['relations'].append({'expected_relation_type':'between','cue_span':cue,'arguments':[]})
    # directional + proportional measurements
    for m in re.finditer(r'(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>[bf])cun\s+(?P<dir>'+DIRS+r')\s+to\b',t,re.I):
        end=clause_boundary(t,m.end()); cue=span_obj(src,mp,m.start(),m.end(),'proportional_direction'); anchor=span_obj(src,mp,m.end(),end,'measurement_anchor')
        out['proportional_measurements'].append({'value':float(m.group('num')),'unit':m.group('unit').upper()+'-cun','direction':m.group('dir'),'cue_span':cue,'anchor':anchor})
        out['required_landmark_mentions'].append(anchor); out['relations'].append({'expected_relation_type':'relative-to','cue_span':cue,'arguments':[anchor]})
    for m in re.finditer(r'\b(?P<dir>'+DIRS+r')\s+to\b',t,re.I):
        # don't duplicate measurement cue
        if any(x['cue_span']['char_start']<=orig_span(mp,m.start(),m.end(),src)[0]<x['cue_span']['char_end'] for x in out['proportional_measurements']): continue
        end=clause_boundary(t,m.end()); cue=span_obj(src,mp,m.start(),m.end(),'direction'); anchor=span_obj(src,mp,m.end(),end,'direction_anchor')
        out['required_landmark_mentions'].append(anchor); out['relations'].append({'expected_relation_type':'relative-to','cue_span':cue,'arguments':[anchor]})
    # in the depression: the depression itself is the surface landmark
    for m in re.finditer(r'\bin (?:the |a )?(?:deepest |soft |sharp angled )?depression\b',t,re.I):
        cue=span_obj(src,mp,m.start(),m.end(),'depression'); out['relations'].append({'expected_relation_type':'surface-landmark','cue_span':cue,'arguments':[cue],'source_semantics':'depression'})
        # landmark mention excludes leading in/the
        dm=re.search(r'depression',t[m.start():m.end()],re.I); ds=m.start()+dm.start(); de=m.start()+dm.end(); out['required_landmark_mentions'].append(span_obj(src,mp,ds,de,'depression'))
    # fraction-of-line relation
    for m in re.finditer(r'\b(?:junction of the )?(upper|lower|medial|lateral|anterior|posterior)\s+('+FRACTION+r')\s+and\s+(?:the )?(upper|lower|medial|lateral|anterior|posterior)\s+('+FRACTION+r')',t,re.I):
        cue=span_obj(src,mp,m.start(),m.end(),'fraction_partition')
        out['relations'].append({'expected_relation_type':'fraction-along-line','cue_span':cue,'arguments':[]})
    # explicit composite child-of-parent constructions, direct source expectation
    part_terms=r'(?:border|margin|corner|ends?|extremity|head|base|tip|wall|process|ridge|tubercle|condyle|epicondyle|phalanx|bellies|belly)'
    for m in re.finditer(r'\b((?:anterior|posterior|superior|inferior|medial|lateral|radial|ulnar|proximal|distal|free|long|short|first|second|third|fourth|fifth|two)?\s*'+part_terms+r')\s+of\s+([^,.;]+)',t,re.I):
        child=span_obj(src,mp,m.start(1),m.end(1),'composite_child'); parent=span_obj(src,mp,m.start(2),m.end(2),'composite_parent'); full=span_obj(src,mp,m.start(),m.end(),'composite')
        out['composites'].append({'child':child,'parent':parent,'source_span':full})
        out['required_landmark_mentions'] += [child,parent]
    # Additional source-faithful lexical operators so every positional statement has an explicit expected representation.
    simple_specs=[
      ('same-level',r'\b(?:at the )?same level as\s+([^,.;]+)'),
      ('center-of',r'\b(?:at |in )?(?:the )?(?:centre|center) of\s+([^,.;]+)'),
      ('overlies',r'\bover the\s+([^,.;]+)'),
      ('on-line',r'\blocated along the curve of\s+([^,.;]+)'),
      ('surface-landmark',r'\bin the\s+((?:first|second|third|fourth|infraorbital)[^,.;]*foramen)'),
      ('on-line',r'\bon the\s+((?:anterior|posterior) median line|midaxillary line)'),
      ('surface-landmark',r'\blocated on the\s+([^,.;]+? muscle)(?=,|\.|;)'),
      ('midpoint-of-entity',r'\b(?:at )?(?:the )?mid-?point of\s+([^,.;]+)'),
    ]
    for typ,pat in simple_specs:
        for m in re.finditer(pat,t,re.I):
            cue=span_obj(src,mp,m.start(),m.end(),typ)
            arg=span_obj(src,mp,m.start(1),m.end(1),'relation_operand')
            if typ=='midpoint-of-entity' and re.search(r'\b(?:line connecting|curved line|line from|connecting line)\b',semantic_text_with_map(arg['source_raw'])[0],re.I):
                continue
            # Avoid duplicating an already captured relation covering the same cue.
            if not any(max(x['cue_span']['char_start'],cue['char_start'])<min(x['cue_span']['char_end'],cue['char_end']) and x['expected_relation_type']==typ for x in out['relations']):
                out['relations'].append({'expected_relation_type':typ,'cue_span':cue,'arguments':[arg]})
            out['required_landmark_mentions'].append(arg)
    # Explicit relational motion / relative landmark definitions in Notes.
    motion_specs=[('superior-to',r'\b(?:immediately above|moving superiorly from)\s+([^,.;]+)'),('inferior-to',r'\bmoving downward from\s+([^,.;]+)')]
    for typ,pat in motion_specs:
        for m in re.finditer(pat,t,re.I):
            cue=span_obj(src,mp,m.start(),m.end(),typ); arg=span_obj(src,mp,m.start(1),m.end(1),'relation_operand')
            out['relations'].append({'expected_relation_type':typ,'cue_span':cue,'arguments':[arg]}); out['required_landmark_mentions'].append(arg)
    # Explicit cross-point level/reference wording.
    for m in re.finditer(r'\bcorresponding (?:lateral|medial) (?:acu-?puncture )?point to\s+([A-Z]{1,3}\s*\d+)\s+is\s+([A-Z]{1,3}\s*\d+)',t,re.I):
        a=span_obj(src,mp,m.start(1),m.end(1),'reference_acupoint'); b=span_obj(src,mp,m.start(2),m.end(2),'reference_acupoint')
        out['relations'].append({'expected_relation_type':'cross-reference','cue_span':span_obj(src,mp,m.start(),m.end(),'cross_reference'),'arguments':[a,b]}); out['required_landmark_mentions'] += [a,b]
    # Pure positioning/procedural Notes may intentionally have no coordinate relation; record that explicitly rather than leaving expected representation semantically blank.
    if not any(out[k] for k in ['required_landmark_mentions','relations','conditional_branches','geometry_constructs','proportional_measurements','composites']):
        out['statement_semantic_scope']='nonlocalizing_or_descriptive'
    else:
        out['statement_semantic_scope']='localization_or_landmark_definition'

    # de-duplicate required mention spans
    seen=set(); req=[]
    for x in out['required_landmark_mentions']:
        k=(x['char_start'],x['char_end'],x['role'])
        if k not in seen: seen.add(k); req.append(x)
    out['required_landmark_mentions']=req
    # De-duplicate multiple regex parses of the same line source span; prefer endpoint split that retains web-margin/condition phrases intact.
    best={}
    for gc in out['geometry_constructs']:
        k=(gc['geometry_type'],gc['source_span']['char_start'],gc['source_span']['char_end'])
        score=sum(len(norm_pdf(e.get('source_raw',''))) for e in gc.get('endpoints',[]))
        if any(norm_pdf(e.get('source_raw','')).lstrip().startswith('the web margin') or norm_pdf(e.get('source_raw','')).lstrip().startswith('web margin') for e in gc.get('endpoints',[])): score+=5000
        if k not in best or score>best[k][0]: best[k]=(score,gc)
    out['geometry_constructs']=[v[1] for v in best.values()]
    # Keep only one on-line expectation for an identical source line span.
    rel=[]; seen_rel=set()
    for rr in out['relations']:
        k=(rr['expected_relation_type'],rr['cue_span']['char_start'],rr['cue_span']['char_end'])
        if k in seen_rel: continue
        seen_rel.add(k); rel.append(rr)
    out['relations']=rel
    return out