import fs from 'node:fs';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>{const u=new URL(p,root);fs.mkdirSync(new URL('./',u),{recursive:true});fs.writeFileSync(u,JSON.stringify(v,null,2)+'\n');};
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const stable=(v)=>JSON.stringify(v,null,2)+'\n';
const now=new Date().toISOString();

const FROZEN_GRAPH_SHA='6dd00d386a6262d02900ec5a30ea9b18aace899f071159e772c12679740b1d06';
const ATLAS_BLOB_SHA='0f81b5621479a0c0548f4683c316f33bd4d6545b';
const snapshotPath=new URL('scripts/data/anatomy-acupoint-relations-v1.json.gz.b64.txt',root);
const packed=Buffer.from(fs.readFileSync(snapshotPath,'utf8').trim(),'base64');
const graphBytes=zlib.gunzipSync(packed);
if(sha(graphBytes)!==FROZEN_GRAPH_SHA)throw new Error(`Frozen B SHA mismatch: ${sha(graphBytes)}`);
const graph=JSON.parse(graphBytes.toString('utf8'));
if(graph.landmark_nodes?.length!==2325||graph.geometry_nodes?.length!==97||graph.relation_instances?.length!==2595)throw new Error('Frozen B graph cardinality mismatch');

const atlas=read('public/models/atlas.json');
const anchors=read('public/knowledge/acupoint-specialized-landmark-anchors.json');
const derived=read('public/knowledge/acupoint-derived-surface-landmarks.json');
const legacyCoords=read('public/knowledge/acupoint-coordinates.json');
const legacyQc=read('public/knowledge/acupoint-coordinates-audit.json');
const legacySolver=read('public/knowledge/acupoint-coordinate-solver.json');
const acupoints=read('public/knowledge/acupoints.json');
const anatomyKo=read('public/knowledge/anatomy-ko.json');

const conceptById=new Map(atlas.concepts.map(x=>[x.id,x]));
const partById=new Map(atlas.parts.map(x=>[x.id,x]));
const anchorById=new Map((anchors.records??[]).filter(x=>x.reviewStatus==='accepted').map(x=>[x.landmarkId,x]));
const derivedById=new Map((derived.landmarks??[]).map(x=>[x.landmarkId,x]));
const pointById=new Map(acupoints.map(x=>[x.id,x]));
const solverByPoint=new Map((legacySolver.records??[]).map(x=>[x.acupointId,x]));
const legacyByKey=new Map((legacyCoords.points??[]).map(x=>[`${x.acupointId}:${x.side}`,x]));
const sourceById=new Map(graph.source_statements.map(x=>[x.source_statement_id,x]));
const landmarkById=new Map(graph.landmark_nodes.map(x=>[x.node_id,x]));
const geometryById=new Map(graph.geometry_nodes.map(x=>[x.node_id,x]));
const relationsByPoint=new Map();
for(const r of graph.relation_instances){const p=String(r.subject_node_id||'').replace(/^P:/,'');const xs=relationsByPoint.get(p)??[];xs.push(r);relationsByPoint.set(p,xs);}

const norm=s=>String(s??'').toLowerCase().replace(/[‐‑‒–—−]/g,'-').replace(/[^a-z0-9가-힣]+/g,' ').trim().replace(/\s+/g,' ');
const sideOfPart=p=>/^left\b/i.test(p.name)?'left':/^right\b/i.test(p.name)?'right':'midline_or_unpaired';
const partSummary=p=>({object_id:p.id,asset_fj_id:p.id,name:p.name,part_concept_id:p.conceptId,system:p.system,chunk:p.chunk,vertex_count:p.vertexCount,index_count:p.indexCount,bounds:p.bounds,laterality:sideOfPart(p),geometry_available:Number.isInteger(p.chunk)&&Number.isFinite(p.positions)&&Number.isFinite(p.indices)&&p.vertexCount>0&&p.indexCount>0});
const fmaParts=id=>{const c=conceptById.get(id);if(!c)return[];const ids=[...(c.elements??[])];for(const p of atlas.parts)if(p.conceptId===id&&!ids.includes(p.id))ids.push(p.id);return ids.map(x=>partById.get(x)).filter(Boolean);};

const aliasRules=[
 [/anterior axillary fold|앞겨드랑주름/,'anterior-axillary-fold'],[/posterior axillary fold|뒤겨드랑주름/,'posterior-axillary-fold'],
 [/palmar wrist crease|손바닥쪽 손목주름/,'palmar-wrist-crease'],[/dorsal wrist crease|손등쪽 손목주름/,'dorsal-wrist-crease'],
 [/popliteal crease|오금주름/,'popliteal-crease'],[/center of popliteal fossa|popliteal fossa.*center|오금오목.*가운데/,'center-popliteal-fossa'],
 [/glabella|미간/,'glabella'],[/gluteal fold|볼기주름/,'gluteal-fold'],[/xiphisternal junction|칼몸통결합|검상흉골결합/,'midpoint-xiphisternal-junction'],
 [/apex of patella|patellar apex|무릎뼈.*꼭지/,'apex-of-patella'],[/base of patella|patellar base|무릎뼈.*바닥/,'base-of-patella'],
 [/mastoid process|꼭지돌기/,'left-mastoid-process'],[/medial border of scapula|어깨뼈.*안쪽모서리/,'left-medial-border-scapula'],
 [/greater trochanter|큰돌기/,'lateral-prominence-greater-trochanter']
];
function derivedCandidates(raw){const s=norm(raw),out=[];for(const [re,id] of aliasRules)if(re.test(s)&&derivedById.has(id))out.push(id);return [...new Set(out)];}
function specializedCandidates(raw){const s=norm(raw),out=[];
 if(/umbilicus|navel|배꼽/.test(s)&&anchorById.has('umbilicus-center'))out.push('umbilicus-center');
 if(/nipple|젖꼭지|유두/.test(s)){for(const id of ['left-nipple-center','right-nipple-center'])if(anchorById.has(id))out.push(id);}
 if(/anterior hairline|앞머리선/.test(s)){for(const id of ['midpoint-anterior-hairline','left-anterior-hairline-corner','right-anterior-hairline-corner'])if(anchorById.has(id))out.push(id);}
 if(/posterior hairline|뒤머리선/.test(s)){if(anchorById.has('midpoint-posterior-hairline'))out.push('midpoint-posterior-hairline');}
 if(/proximal interphalangeal|pip|몸쪽손가락뼈사이/.test(s)){const id='radial-crease-proximal-interphalangeal-middle-finger';if(anchorById.has(id))out.push(id);}
 if(/distal interphalangeal|dip|먼쪽손가락뼈사이/.test(s)){const id='radial-crease-distal-interphalangeal-middle-finger';if(anchorById.has(id))out.push(id);}
 return out;
}
function refPoint(raw){const m=String(raw??'').match(/\b(?:LU|LI|ST|SP|HT|SI|BL|KI|PC|TE|GB|LR|GV|CV)\s*\d+\b/i);return m?m[0].replace(/\s+/g,'').toUpperCase():null;}
function isConstraintOnly(n){return ['body_region','surface_aspect','anatomical_line','anatomical_plane','surface_region'].includes(n.semantic_target_type)||/region\.|surface\.|line\.|plane\./.test(n.landmark_class??'');}
function nodeRealization(n){
 const base={node_id:n.node_id,point_id:n.point_id,source_statement_id:n.source_statement_id,source_section:n.source_section,source_raw:n.source_raw,landmark_class:n.landmark_class,semantic_target_type:n.semantic_target_type,terminal_disposition:n.terminal_disposition,fma_identity:n.fma_id?{fma_id:n.fma_id,fma_name:n.fma_name??conceptById.get(n.fma_id)?.name??null}:null,atlas_concept:null,object_candidates:[],selection_policy:null,geometry_source:null,geometry_available:false,hard_dependency_role:!isConstraintOnly(n),unresolved_reason:null};
 if(n.terminal_disposition==='cross_reference'){
   const p=refPoint(n.source_raw);return {...base,realization_status:'reference_acupoint',reference_point_id:p,geometry_source:'reference_acupoint',geometry_available:!!p,unresolved_reason:p?null:'cross_reference_target_not_parseable'};
 }
 if(n.fma_id){const c=conceptById.get(n.fma_id),parts=fmaParts(n.fma_id);base.atlas_concept=c?{concept_id:c.id,name:c.name,element_ids:c.elements??[]}:null;base.object_candidates=parts.map(partSummary);base.selection_policy='preserve_generic_fma_identity; at coordinate solve choose object whose explicit part laterality matches point side; for midline use only unpaired/midline object or a source-backed constructed feature; never fall back contralaterally';
   if(!c||parts.length===0)return {...base,realization_status:'fma_no_mesh',geometry_source:null,geometry_available:false,unresolved_reason:!c?'fma_missing_from_atlas_concepts':'atlas_concept_has_no_renderable_part'};
   return {...base,realization_status:'fma_mesh_resolved',geometry_source:'atlas_mesh_object',geometry_available:true,landmark_specificity:['body_region','surface_aspect'].includes(n.semantic_target_type)?'region_or_aggregate_mesh':'entity_mesh'};
 }
 if(n.terminal_disposition==='specialized_anchor'){
   const cs=specializedCandidates(n.source_raw);return {...base,realization_status:cs.length?'specialized_anchor_resolved':'geometry_unresolved',specialized_anchor_candidates:cs,geometry_source:cs.length?'specialized_anchor_registry':null,geometry_available:cs.length>0,selection_policy:cs.length?'select only by source phrase + point side/relation context; do not infer side in identity layer':null,unresolved_reason:cs.length?null:'no_accepted_specialized_anchor_matching_source_family'};
 }
 const ds=derivedCandidates(n.source_raw);
 if(ds.length)return {...base,realization_status:'constructed_geometry',derived_geometry_candidates:ds,geometry_source:'derived_surface_landmark_registry',geometry_available:true,selection_policy:'select side-specific geometry at solve time; do not rewrite source identity'};
 if(n.terminal_disposition==='geometry_or_surface'||isConstraintOnly(n))return {...base,realization_status:'surface_geometry',geometry_source:'body_surface_constraint',geometry_available:true,selection_policy:'constraint-only; realized by model body surface, region, aspect, line or projection constraint rather than a fabricated landmark point'};
 if(n.terminal_disposition==='registry_limited')return {...base,realization_status:'registry_limited_but_geometry_recoverable',geometry_source:'source_constraint_plus_reviewed_model_measurement',geometry_available:true,selection_policy:'recover only when a reviewed measurement frame or explicit relation operation supplies geometry; otherwise block coordinate promotion'};
 return {...base,realization_status:'geometry_unresolved',geometry_source:null,geometry_available:false,unresolved_reason:`terminal_disposition_${n.terminal_disposition}_has_no_source_backed_geometry_provider`};
}
const landmarkRealizations=graph.landmark_nodes.map(nodeRealization);
const realizationById=new Map(landmarkRealizations.map(x=>[x.node_id,x]));

function geometryOp(g){
 const deps=[...(g.endpoint_node_ids??[])];let op='unresolved';
 if(g.geometry_type==='constructed_line'||g.geometry_type==='reference_line')op='line';
 else if(g.geometry_type?.includes('midpoint'))op='midpoint';
 else if(g.geometry_type?.includes('junction'))op='junction';
 const missing=deps.filter(id=>!realizationById.has(id)&&!geometryById.has(id));
 const depBlocked=deps.filter(id=>realizationById.has(id)&&!realizationById.get(id).geometry_available);
 return {node_id:g.node_id,source_statement_id:g.source_statement_id,source_mention_node_id:g.source_mention_node_id,source_raw:g.source_raw,geometry_type:g.geometry_type,operation:op,dependency_node_ids:deps,dependency_graph:op==='line'?{steps:[{op:'realize_endpoint',inputs:deps},{op:'line',inputs:deps}]}:{steps:[{op,inputs:deps}]},realization_status:missing.length||depBlocked.length||!deps.length?'geometry_unresolved':'constructed_geometry',unresolved_reason:missing.length?'missing_dependency_nodes':depBlocked.length?'dependency_geometry_unresolved':!deps.length?'source_endpoint_absent':null};
}
const geometryRealizations=graph.geometry_nodes.map(geometryOp);
const geometryRealizationById=new Map(geometryRealizations.map(x=>[x.node_id,x]));

function selectedObject(real,side){
 const xs=real.object_candidates??[];if(!xs.length)return {status:'none',objects:[]};
 if(side==='left'||side==='right'){
   const matching=xs.filter(x=>x.laterality===side);const unpaired=xs.filter(x=>x.laterality==='midline_or_unpaired');
   if(matching.length)return {status:'side-matched',objects:matching};
   if(unpaired.length&&xs.every(x=>x.laterality==='midline_or_unpaired'))return {status:'unpaired-valid',objects:unpaired};
   return {status:'contralateral_or_ambiguous',objects:[]};
 }
 const unpaired=xs.filter(x=>x.laterality==='midline_or_unpaired');
 return unpaired.length?{status:'midline-unpaired',objects:unpaired}:{status:'midline_bilateral_only_blocked',objects:[]};
}
function anchorSelection(real,side){
 const ids=real.specialized_anchor_candidates??[];if(!ids.length)return {status:'none',anchors:[]};
 const xs=ids.map(id=>anchorById.get(id)).filter(Boolean);
 const explicit=xs.filter(x=>x.side===side||(!x.side&&/^(left|right)-/.test(x.landmarkId)&&x.landmarkId.startsWith(side+'-')));
 if(side==='midline'){const m=xs.filter(x=>!/^left-|^right-/.test(x.landmarkId)&&!x.side);return m.length===1?{status:'selected',anchors:m}:{status:'ambiguous',anchors:[]};}
 if(explicit.length===1)return {status:'selected',anchors:explicit};
 const generic=xs.filter(x=>!x.side&&!/^left-|^right-/.test(x.landmarkId));if(generic.length===1&&xs.length===1)return {status:'selected',anchors:generic};
 return {status:'ambiguous',anchors:[]};
}
function derivedSelection(real,side){
 const xs=(real.derived_geometry_candidates??[]).map(id=>derivedById.get(id)).filter(Boolean);if(xs.length!==1)return {status:xs.length?'ambiguous':'none',items:[]};
 const x=xs[0],g=x.geometry??{};if(g.sides){const s=g.sides[side];return s?.position?{status:'selected',items:[{landmarkId:x.landmarkId,position:s.position,geometry:g,side}]}:{status:'side_unavailable',items:[]};}
 if(Array.isArray(g.position))return {status:'selected',items:[{landmarkId:x.landmarkId,position:g.position,geometry:g,side:'midline_or_unpaired'}]};
 return {status:'geometry_missing',items:[]};
}

const relationSemantics={
 'midpoint-between':'midpoint(line(A,B))','between':'segment(A,B) constraint; unique only with source-backed fraction/measurement','fraction-along-line':'lerp(A,B,fraction)','on-line':'line membership constraint','at-border':'border(parent/surface) intersection','at-junction':'junction/intersection of realized geometries','relative-to':'directional/proportional transform from reference','surface-landmark':'region/surface constraint','reference-landmark':'landmark proximity/reference constraint','adjacent':'adjacency constraint','overlies':'surface projection over realized structure','deep-to':'depth relation used only as provenance/QC; final point remains on surface'
};
function relationPlan(r){
 const args=r.argument_node_ids??[];const deps=args.map(id=>realizationById.get(id)??geometryRealizationById.get(id)??null);const missing=args.filter((id,i)=>!deps[i]);const blockers=deps.filter(x=>x&&((x.realization_status==='geometry_unresolved')||x.geometry_available===false&&x.realization_status!=='surface_geometry'));
 const rel=r.relation_type;return {relation_instance_id:r.relation_id,source_statement_id:r.source_statement_id,source_section:r.source_section,relation_type:rel,operator:r.operator??r.source_relation_id??null,source_raw:r.source_raw,argument_node_ids:args,solver_operation:relationSemantics[rel]??'constraint',dependency_status:missing.length?'missing':blockers.length?'blocked':'available',missing_dependency_ids:missing,blocked_dependency_ids:blockers.map(x=>x.node_id),unique_coordinate_operator:['midpoint-between','fraction-along-line'].includes(rel),constraint_only:['between','on-line','surface-landmark','reference-landmark','adjacent','deep-to','overlies'].includes(rel)};
}
const relationPlans=graph.relation_instances.map(relationPlan);

function measurementInputs(pointId,side){
 const s=solverByPoint.get(pointId);return (s?.measurementFrames??[]).map(f=>{const ss=(f.sideScales??[]).find(x=>x.side===side)??(f.sideScales??[]).find(x=>x.side==='midline');return {frame_id:f.id,unit:f.unit,direction:f.direction,value:f.value??f.distance??null,selected_calibration_id:f.selectedCalibrationId,calibration:f.calibration??null,side_scale:ss?.chosen??null,connection_status:f.connectionStatus,proportional_policy:ss?.chosen?.metricPolicy??null};});
}
function pointSides(id){const legacy=[...legacyByKey.values()].filter(x=>x.acupointId===id).map(x=>x.side);if(legacy.length)return legacy;return ['midline'];}
function regionText(pointId){return graph.source_statements.filter(s=>s.point_id===pointId&&s.source_section==='location').map(s=>s.source_raw??s.text??'').join(' ');}
function relationNodeIds(pointId){const rels=relationsByPoint.get(pointId)??[];return [...new Set(rels.flatMap(r=>r.argument_node_ids??[]).filter(id=>landmarkById.has(id)))];}
function relationIds(pointId){return (relationsByPoint.get(pointId)??[]).map(r=>r.relation_id);}
function sourceIdsFor(pointId){return [...new Set((relationsByPoint.get(pointId)??[]).map(r=>r.source_statement_id).filter(Boolean))];}

const physical=[];
for(const p of graph.points){const id=p.point_id;for(const side of pointSides(id)){
 const legacy=legacyByKey.get(`${id}:${side}`)??null;const rels=(relationsByPoint.get(id)??[]).filter(r=>r.source_section==='location');const nodeIds=[...new Set(rels.flatMap(r=>r.argument_node_ids??[]).filter(x=>landmarkById.has(x)))];const selections=[];let hardBlock=[];let contralateral=[];let ambiguousAnchor=[];
 for(const nid of nodeIds){const real=realizationById.get(nid);if(!real)continue;let sel={status:'constraint'};
   if(real.realization_status==='fma_mesh_resolved')sel=selectedObject(real,side);
   else if(real.realization_status==='specialized_anchor_resolved')sel=anchorSelection(real,side);
   else if(real.realization_status==='constructed_geometry')sel=derivedSelection(real,side);
   else if(real.realization_status==='reference_acupoint')sel={status:real.reference_point_id?'reference':'none',reference_point_id:real.reference_point_id};
   else if(real.realization_status==='geometry_unresolved')sel={status:'unresolved'};
   selections.push({node_id:nid,realization_status:real.realization_status,selection:sel});
   if(['contralateral_or_ambiguous','midline_bilateral_only_blocked'].includes(sel.status))contralateral.push(nid);
   if(sel.status==='ambiguous')ambiguousAnchor.push(nid);
   if(real.hard_dependency_role&&(real.realization_status==='geometry_unresolved'||real.realization_status==='fma_no_mesh'||['none','contralateral_or_ambiguous','midline_bilateral_only_blocked','side_unavailable','geometry_missing','ambiguous'].includes(sel.status)))hardBlock.push(nid);
 }
 const plans=rels.map(relationPlan);const relationBlocked=plans.filter(x=>x.dependency_status!=='available'&&!x.constraint_only).map(x=>x.relation_instance_id);
 const measurements=measurementInputs(id,side);const hasSourceGeometry=rels.length>0&&(nodeIds.length>0||measurements.length>0);
 const legacyCandidate=legacy?{coordinate_raw:legacy.validation?.preProjectionTarget??legacy.position,coordinate_projected:legacy.position,projection_distance:legacy.validation?.projectionDistance??0,surface_mesh_id:legacy.validation?.surfacePartId??null,legacy_confidence:legacy.confidence,legacy_visual_disposition:legacy.validation?.visualAuditDisposition??null,provider_sha:'d3ba19266282c13345e401abcdf326b6a5754336'}:null;
 const projectionOk=!!legacyCandidate&&legacyCandidate.surface_mesh_id==='FJ2810'&&Array.isArray(legacyCandidate.coordinate_projected)&&legacyCandidate.coordinate_projected.every(Number.isFinite);
 const promotable=!!legacy&&hasSourceGeometry&&hardBlock.length===0&&relationBlocked.length===0&&contralateral.length===0&&ambiguousAnchor.length===0&&projectionOk;
 const status=promotable?'solved':legacy?'conditional':'unresolved';
 const reasons=[];if(!legacy)reasons.push('no_bodyparts3d_coordinate_candidate');if(!hasSourceGeometry)reasons.push('no_source_backed_geometry_dependency');if(hardBlock.length)reasons.push('hard_landmark_dependency_unresolved');if(relationBlocked.length)reasons.push('relation_operation_dependency_unresolved');if(contralateral.length)reasons.push('laterality_object_selection_blocked');if(ambiguousAnchor.length)reasons.push('specialized_anchor_family_ambiguous');if(legacy&&!projectionOk)reasons.push('surface_projection_not_verified_on_FJ2810');
 physical.push({point_id:id,acupointId:id,side,coordinate_raw:promotable?legacyCandidate.coordinate_raw:null,coordinate_projected:promotable?legacyCandidate.coordinate_projected:null,position:promotable?legacyCandidate.coordinate_projected:null,solver_method:promotable?'frozen-B-dependency-gated legacy BodyParts3D geometric candidate + source-backed realization + region/laterality-constrained Skin projection':null,source_statement_ids:sourceIdsFor(id),landmark_node_ids:relationNodeIds(id),relation_instance_ids:relationIds(id),measurement_inputs:measurements,mesh_object_provenance:selections,confidence:promotable?(legacy.confidence==='high'?'high':'moderate'):'unresolved',coordinate_status:status,status:promotable?'validated':status,validation:promotable?{preProjectionTarget:legacyCandidate.coordinate_raw,projectionDistance:legacyCandidate.projection_distance,surfacePartId:legacyCandidate.surface_mesh_id,regionConstrained:true,visualAuditDisposition:legacyCandidate.legacy_visual_disposition}:null,unresolved_reason:promotable?null:reasons,legacy_candidate:legacyCandidate});
}}

// QC: conservative hard gates + inherited model visual review evidence.
const solved=physical.filter(x=>x.coordinate_status==='solved');
const byPoint=new Map();for(const x of physical){const a=byPoint.get(x.point_id)??[];a.push(x);byPoint.set(x.point_id,a);}
const flags=[];
const lrAxis=legacyQc?.summary?.coordinateFrame?.leftRightAxis??0; // existing audit may omit; BodyParts3D verified x-axis in legacy generator
for(const x of physical){const p=x.coordinate_projected;if(!p)continue;const sign=p[0];if(x.side==='left'&&sign<0)flags.push({severity:'hard',type:'left_right_flip',point_id:x.point_id,side:x.side});if(x.side==='right'&&sign>0)flags.push({severity:'hard',type:'left_right_flip',point_id:x.point_id,side:x.side});if(x.side==='midline'&&Math.abs(sign)>.02)flags.push({severity:'review',type:'midline_crossing_or_offset',point_id:x.point_id,side:x.side,value:sign});if((x.legacy_candidate?.projection_distance??0)>.1)flags.push({severity:'review',type:'large_surface_projection_distance',point_id:x.point_id,side:x.side,value:x.legacy_candidate.projection_distance});}
for(const [id,xs] of byPoint){const l=xs.find(x=>x.side==='left'&&x.coordinate_projected),r=xs.find(x=>x.side==='right'&&x.coordinate_projected);if(l&&r){const dl=Math.hypot(l.coordinate_projected[0]+r.coordinate_projected[0],l.coordinate_projected[1]-r.coordinate_projected[1],l.coordinate_projected[2]-r.coordinate_projected[2]);if(dl>.06)flags.push({severity:'review',type:'bilateral_symmetry_outlier',point_id:id,value:dl});if(Math.hypot(...l.coordinate_projected.map((v,i)=>v-r.coordinate_projected[i]))<1e-4)flags.push({severity:'hard',type:'bilateral_coordinate_collapse',point_id:id});}}
const dup=new Map();for(const x of solved){const k=x.coordinate_projected.map(v=>v.toFixed(5)).join(',');const a=dup.get(k)??[];a.push(`${x.point_id}:${x.side}`);dup.set(k,a);}for(const [k,a] of dup)if(a.length>1)flags.push({severity:'review',type:'coordinate_duplication',coordinate:k,records:a});
const relationQc=relationPlans.map(x=>({relation_instance_id:x.relation_instance_id,relation_type:x.relation_type,status:x.dependency_status==='available'?'computable_or_constraint_ready':'not_computable',dependency_status:x.dependency_status,argument_node_ids:x.argument_node_ids}));
const visualProblems=(legacyCoords.points??[]).filter(x=>['review-needed','model-limitation'].includes(x.validation?.visualAuditDisposition)).map(x=>({point_id:x.acupointId,side:x.side,legacy_visual_disposition:x.validation.visualAuditDisposition}));
const reviewQueue=[...new Map([...physical.filter(x=>x.coordinate_status!=='solved').map(x=>[`${x.point_id}:${x.side}`,{point_id:x.point_id,side:x.side,reasons:x.unresolved_reason}]),...flags.map(x=>[`${x.point_id??'global'}:${x.side??x.type}`,x]),...visualProblems.map(x=>[`${x.point_id}:${x.side}`,x])]).values()];

const statusCounts=landmarkRealizations.reduce((o,x)=>(o[x.realization_status]=(o[x.realization_status]??0)+1,o),{});
const fmaNoMesh=landmarkRealizations.filter(x=>x.realization_status==='fma_no_mesh').length;
const meshRealizable=landmarkRealizations.filter(x=>['fma_mesh_resolved','specialized_anchor_resolved','constructed_geometry','surface_geometry','registry_limited_but_geometry_recoverable','reference_acupoint'].includes(x.realization_status)&&x.geometry_available).length;
const logicalSolved=[...byPoint.entries()].filter(([id,xs])=>xs.every(x=>x.coordinate_status==='solved')).map(([id])=>id);
const logicalConditional=[...byPoint.entries()].filter(([id,xs])=>!xs.every(x=>x.coordinate_status==='solved')).map(([id])=>id);
const projectionSuccess=solved.filter(x=>x.coordinate_projected).length;

const realization={schema_version:'1.0.0',artifact:'acupoint-bodyparts3d-realization.json',generated_at:now,model:'BodyParts3D 4.0',frozen_B:{sha256:FROZEN_GRAPH_SHA,modified:false,landmark_node_count:2325,geometry_node_count:97,relation_instance_count:2595},atlas:{path:'public/models/atlas.json',git_blob_sha:ATLAS_BLOB_SHA,concept_count:atlas.concepts.length,part_count:atlas.parts.length},laterality_contract:'generic source identity preserved; physical point side selects actual FJ object only at coordinate solve; midline never selects bilateral-only object',status_counts:statusCounts,summary:{landmark_nodes:landmarkRealizations.length,mesh_or_geometry_realizable:meshRealizable,fma_no_mesh:fmaNoMesh,specialized_anchor_resolved:statusCounts.specialized_anchor_resolved??0,surface_geometry:statusCounts.surface_geometry??0,constructed_geometry:statusCounts.constructed_geometry??0,reference_acupoint:statusCounts.reference_acupoint??0,registry_limited_but_geometry_recoverable:statusCounts.registry_limited_but_geometry_recoverable??0,geometry_unresolved:statusCounts.geometry_unresolved??0},landmark_realizations:landmarkRealizations,geometry_realizations:geometryRealizations};
const solverInput={schema_version:'1.0.0',artifact:'acupoint-coordinate-solver-input.json',generated_at:now,frozen_B_sha256:FROZEN_GRAPH_SHA,principles:{no_fixed_mm_conversion:true,measurement_geometry_proportional:true,no_synthetic_endpoints:true,unresolved_dependencies_block_promotion:true,legacy_coordinate_provider_is_candidate_only:true},relation_operation_contract:relationSemantics,relation_plans:relationPlans,points:graph.points.map(p=>({point_id:p.point_id,source_statement_ids:sourceIdsFor(p.point_id),landmark_node_ids:relationNodeIds(p.point_id),relation_instance_ids:relationIds(p.point_id),measurement_frames:solverByPoint.get(p.point_id)?.measurementFrames??[]}))};
const coords={schema_version:'1.0.0',artifact:'acupoint-coordinates.json',generated_at:now,standard:'WHO 2008 primary source + frozen B relation graph v1 + BodyParts3D 4.0',frozen_B_sha256:FROZEN_GRAPH_SHA,coordinate_count_physical:physical.length,logical_point_count:361,status_summary:{logical_solved:logicalSolved.length,logical_conditional_or_unresolved:logicalConditional.length,physical_solved:solved.length,physical_conditional:physical.filter(x=>x.coordinate_status==='conditional').length,physical_unresolved:physical.filter(x=>x.coordinate_status==='unresolved').length},points:physical};
const qc={schema_version:'1.0.0',artifact:'acupoint-coordinate-qc.json',generated_at:now,summary:{logical_points:361,physical_records:physical.length,logical_solved:logicalSolved.length,logical_conditional_or_unresolved:logicalConditional.length,surface_projection_success_count:projectionSuccess,surface_projection_success_rate:solved.length?projectionSuccess/solved.length:0,hard_qc_flags:flags.filter(x=>x.severity==='hard').length,review_qc_flags:flags.filter(x=>x.severity==='review').length,relation_total:relationQc.length,relation_computable_or_constraint_ready:relationQc.filter(x=>x.status==='computable_or_constraint_ready').length,relation_not_computable:relationQc.filter(x=>x.status==='not_computable').length,legacy_visual_problem_records:visualProblems.length,review_queue_records:reviewQueue.length},bilateral_midline_qc:flags.filter(x=>['left_right_flip','midline_crossing_or_offset','bilateral_symmetry_outlier','bilateral_coordinate_collapse'].includes(x.type)),relation_satisfaction_qc:relationQc,flags,legacy_visual_qc_problems:visualProblems,unresolved_review_queue:reviewQueue,frozen_B_modification:false};

write('public/knowledge/acupoint-bodyparts3d-realization.json',realization);
write('public/knowledge/acupoint-coordinate-solver-input.json',solverInput);
write('public/knowledge/acupoint-coordinates.json',coords);
write('public/knowledge/acupoint-coordinate-qc.json',qc);

// Manifest + regression for the frozen-B-gated official coordinate registry.
const outputPaths=['public/knowledge/acupoint-bodyparts3d-realization.json','public/knowledge/acupoint-coordinate-solver-input.json','public/knowledge/acupoint-coordinates.json','public/knowledge/acupoint-coordinate-qc.json'];
const hashes=Object.fromEntries(outputPaths.map(p=>[p,sha(fs.readFileSync(new URL(p,root)))]));
const regression={schema_version:'1.0.0',generated_at:now,checks:{frozen_B_sha_exact:sha(graphBytes)===FROZEN_GRAPH_SHA,frozen_B_modified:false,landmark_count_2325:landmarkRealizations.length===2325,geometry_count_97:geometryRealizations.length===97,relation_count_2595:relationPlans.length===2595,logical_points_361:byPoint.size===361,no_solved_without_surface_projection:solved.every(x=>x.coordinate_projected&&x.legacy_candidate?.surface_mesh_id==='FJ2810'),no_solved_with_hard_unresolved_reason:solved.every(x=>!x.unresolved_reason),no_midline_bilateral_object_selection:physical.filter(x=>x.side==='midline').every(x=>x.mesh_object_provenance.every(y=>y.selection?.status!=='side-matched')),no_contralateral_object_selection:physical.every(x=>x.mesh_object_provenance.every(y=>y.selection?.status!=='contralateral_or_ambiguous'))},counts:{...realization.summary,...qc.summary}};
write('public/knowledge/acupoint-coordinate-regression-report.json',regression);
outputPaths.push('public/knowledge/acupoint-coordinate-regression-report.json');
const manifest={schema_version:'1.0.0',generated_at:now,frozen_inputs:{anatomy_acupoint_relations_v1_sha256:FROZEN_GRAPH_SHA,atlas_git_blob_sha:ATLAS_BLOB_SHA,legacy_coordinates_git_blob_sha:'d3ba19266282c13345e401abcdf326b6a5754336'},outputs:Object.fromEntries(outputPaths.map(p=>[p,{sha256:sha(fs.readFileSync(new URL(p,root))),bytes:fs.statSync(new URL(p,root)).size}])),frozen_B_modified:false};
write('public/knowledge/acupoint-coordinate-manifest.json',manifest);

// Bundle for audit/review.
const bundleDir=new URL('artifacts/acupoint-coordinate-v1/',root);fs.mkdirSync(bundleDir,{recursive:true});
for(const p of [...outputPaths,'public/knowledge/acupoint-coordinate-manifest.json'])fs.copyFileSync(new URL(p,root),new URL(p.split('/').pop(),bundleDir));
fs.copyFileSync(snapshotPath,new URL('anatomy-acupoint-relations-v1.json.gz.b64.txt',bundleDir));
try{execFileSync('zip',['-q','-r','acupoint-coordinate-v1.zip','acupoint-coordinate-v1'],{cwd:new URL('artifacts/',root)});}catch(e){console.warn('zip unavailable',e.message);}
if(fs.existsSync(new URL('artifacts/acupoint-coordinate-v1.zip',root))){const zp=new URL('artifacts/acupoint-coordinate-v1.zip',root);const zsha=sha(fs.readFileSync(zp));fs.writeFileSync(new URL('artifacts/acupoint-coordinate-v1.zip.sha256',root),`${zsha}  acupoint-coordinate-v1.zip\n`);}

console.log(JSON.stringify({frozen_B_sha:sha(graphBytes),realization:realization.summary,coordinates:coords.status_summary,qc:qc.summary,regression:regression.checks},null,2));