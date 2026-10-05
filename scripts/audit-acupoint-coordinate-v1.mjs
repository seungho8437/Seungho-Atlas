import fs from 'node:fs';
import zlib from 'node:zlib';
import crypto from 'node:crypto';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>{const u=new URL(p,root);fs.mkdirSync(new URL('./',u),{recursive:true});fs.writeFileSync(u,JSON.stringify(v,null,2)+'\n');};
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const FROZEN_SHA='6dd00d386a6262d02900ec5a30ea9b18aace899f071159e772c12679740b1d06';

const packed=Buffer.from(fs.readFileSync(new URL('scripts/data/anatomy-acupoint-relations-v1.json.gz.b64.txt',root),'utf8').trim(),'base64');
const graphBytes=zlib.gunzipSync(packed);
if(sha(graphBytes)!==FROZEN_SHA) throw new Error('frozen B SHA mismatch');
const graph=JSON.parse(graphBytes.toString('utf8'));
const coords=read('public/knowledge/acupoint-coordinates.json');
const realization=read('public/knowledge/acupoint-bodyparts3d-realization.json');
const legacySolver=read('public/knowledge/acupoint-coordinate-solver.json');
const anchors=read('public/knowledge/acupoint-specialized-landmark-anchors.json');
const derived=read('public/knowledge/acupoint-derived-surface-landmarks.json');
const visual=read('public/knowledge/acupoint-coordinate-visual-audit-v1.json');

const sourceById=new Map(graph.source_statements.map(x=>[x.source_statement_id,x]));
const relById=new Map(graph.relation_instances.map(x=>[x.relation_id,x]));
const realById=new Map(realization.landmark_realizations.map(x=>[x.node_id,x]));
const geomById=new Map(realization.geometry_realizations.map(x=>[x.node_id,x]));
const pointRows=coords.points||[];
const physicalSidesByPoint=new Map(); for(const p of pointRows){const a=physicalSidesByPoint.get(p.point_id)||new Set();a.add(p.side);physicalSidesByPoint.set(p.point_id,a);}

const wrongMap=new Map();
for(const x of visual.definiteCorrect||[]) for(const side of x.sides||[]) wrongMap.set(x.id+':'+side,{label:'visually_wrong',reason:x.reason,source:'visual.definiteCorrect'});
for(const x of visual.ambiguousUserRecheck||[]) for(const side of x.sides||[]) wrongMap.set(x.id+':'+side,{label:'visual_review_problem',reason:x.reason,source:'visual.ambiguousUserRecheck'});
for(const k of visual.modelLimitationsFromDetailedReview||[]) if(!wrongMap.has(k)) wrongMap.set(k,{label:'visual_review_problem',reason:'listed in modelLimitationsFromDetailedReview',source:'visual.modelLimitationsFromDetailedReview'});
const passSet=new Set(visual.detailedPass||[]);

function originAudit(p){
 const legacy=!!p.legacy_candidate;
 return {point_id:p.point_id,side:p.side,v1_coordinate_status:p.coordinate_status,audit_status:p.coordinate_status==='solved'?'provisional_projected_candidate':p.coordinate_status,coordinate_origin:legacy?'legacy_bodyparts3d_candidate_reused':'none',legacy_candidate_id_source:legacy?'public/knowledge/acupoint-coordinates.json:'+p.point_id+':'+p.side:null,native_relation_executed:false,native_relation_types_executed:[],surface_projection_reused_from_legacy:legacy&&p.legacy_candidate?.surface_mesh_id==='FJ2810',anchor_dependencies:(p.mesh_object_provenance||[]).filter(x=>['specialized_anchor_resolved','constructed_geometry','reference_acupoint'].includes(x.realization_status)).map(x=>({node_id:x.node_id,status:x.realization_status,selection:x.selection})),measurement_dependencies:p.measurement_inputs||[],evidence:{solver_method:p.solver_method||null,raw_equals_legacy_raw:legacy&&JSON.stringify(p.coordinate_raw)===JSON.stringify(p.legacy_candidate?.coordinate_raw),projected_equals_legacy_projected:legacy&&JSON.stringify(p.coordinate_projected)===JSON.stringify(p.legacy_candidate?.coordinate_projected)}};
}
const provenance=pointRows.filter(p=>p.coordinate_status==='solved').map(originAudit);
const originCounts=provenance.reduce((o,x)=>(o[x.coordinate_origin]=(o[x.coordinate_origin]||0)+1,o),{});

function posOfAnchor(id,side){
 const a=(anchors.records||[]).find(x=>x.landmarkId===id&&x.reviewStatus==='accepted');
 if(a?.position) return {position:a.position,source:'specialized-anchor-registry',record:a};
 const d=(derived.landmarks||[]).find(x=>x.landmarkId===id); if(!d)return null;
 const g=d.geometry||{};
 if(g.sides?.[side]?.position)return {position:g.sides[side].position,source:'derived-surface-landmarks',record:d};
 if(Array.isArray(g.position))return {position:g.position,source:'derived-surface-landmarks',record:d};
 return null;
}
const usedEndpointIds=new Set();
for(const s of legacySolver.records||[])for(const f of s.measurementFrames||[])for(const ss of f.sideScales||[]){const c=ss.chosen;if(c?.from)usedEndpointIds.add(c.from);if(c?.to)usedEndpointIds.add(c.to);}
for(const id of ['umbilicus-center','left-nipple-center','right-nipple-center','midpoint-anterior-hairline','midpoint-posterior-hairline','left-anterior-hairline-corner','right-anterior-hairline-corner','suprasternal-notch','midpoint-xiphisternal-junction'])usedEndpointIds.add(id);

const anchorAudit=[];
for(const id of [...usedEndpointIds].sort()){
 const side=id.startsWith('left-')?'left':id.startsWith('right-')?'right':'midline';
 const r=posOfAnchor(id,side),pos=r?.position||null,issues=[];
 if(!pos){const d=(derived.landmarks||[]).find(x=>x.landmarkId===id);if(d?.geometry?.sides)issues.push('bilateral_anchor_requires_physical_side_context');else issues.push('coordinate_missing');}
 if(pos&&side==='left'&&pos[0]<=0)issues.push('laterality_sign_mismatch');
 if(pos&&side==='right'&&pos[0]>=0)issues.push('laterality_sign_mismatch');
 if(pos&&side==='midline'&&/umbilicus|hairline|suprasternal|xiphisternal/.test(id)&&Math.abs(pos[0])>.03)issues.push('unexpected_midline_offset');
 let derivation=null,prov=null,surface=null;
 if(r?.source==='specialized-anchor-registry'){derivation=r.record.method;prov=r.record.provenance;surface=r.record.surfaceProjection;}
 else if(r){derivation=r.record.construction||r.record.geometry?.method||r.record.status;prov={definition:r.record.definition,confidence:r.record.confidence};surface=r.record.geometry?.surfaceProjection||null;}
 anchorAudit.push({anchor_id:id,side,coordinate:pos,derivation_method:derivation,source_provenance:prov,bodyparts3d_surface_structure_relation:surface,expected_anatomical_region:'review-from-anchor-identity',issues});
}
const anchorMap=new Map(anchorAudit.map(x=>[x.anchor_id,x]));
const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
const axisDist=(a,b,i)=>Math.abs(a[i]-b[i]);
const sanity=[];
function sanityPair(id,a,b,metric,expectedCun){const A=anchorMap.get(a)?.coordinate,B=anchorMap.get(b)?.coordinate;if(!A||!B)return;const d=metric==='lr-axis'?axisDist(A,B,0):metric==='si-axis'?axisDist(A,B,1):dist(A,B);sanity.push({id,from:a,to:b,metric,distance:d,expected_cun:expectedCun||null,model_unit_per_cun:expectedCun?d/expectedCun:null});}
sanityPair('nipple-span','left-nipple-center','right-nipple-center','lr-axis',8);
sanityPair('suprasternal-xiphisternal','suprasternal-notch','midpoint-xiphisternal-junction','si-axis',9);
sanityPair('anterior-posterior-hairline','midpoint-anterior-hairline','midpoint-posterior-hairline','euclidean',12);
sanityPair('anterior-hairline-corners','left-anterior-hairline-corner','right-anterior-hairline-corner','lr-axis',9);
sanityPair('suprasternal-umbilicus','suprasternal-notch','umbilicus-center','si-axis',null);

const calibrationMap=new Map();
for(const s of legacySolver.records||[])for(const f of s.measurementFrames||[])for(const ss of f.sideScales||[]){
 if(!physicalSidesByPoint.get(s.acupointId)?.has(ss.side))continue;
 const c=ss.chosen;if(!c||!f.selectedCalibrationId)continue;const key=f.selectedCalibrationId+':'+ss.side;
 if(!calibrationMap.has(key))calibrationMap.set(key,{calibration_id:f.selectedCalibrationId,side:ss.side,unit:f.unit,region:f.bodyRegion||f.calibration?.region||null,axis:f.axis||f.calibration?.axis||null,expected_cun:f.calibration?.cun||null,from:c.from,to:c.to,metric_policy:c.metricPolicy,reported_interval_length:c.intervalLength,reported_model_unit_per_cun:c.cunLength,used_by:[]});
 calibrationMap.get(key).used_by.push({point_id:s.acupointId,frame_id:f.id,value:f.value,direction:f.direction});
}
const calibrations=[...calibrationMap.values()];
for(const c of calibrations){
 const A=posOfAnchor(c.from,c.side)?.position,B=posOfAnchor(c.to,c.side)?.position;c.endpoint_coordinates={from:A||null,to:B||null};
 let measured=null;if(A&&B)measured=/left-right-axis/.test(c.metric_policy||'')?axisDist(A,B,0):/superior-axis/.test(c.metric_policy||'')?axisDist(A,B,1):dist(A,B);
 c.recomputed_model_distance=measured;c.recomputed_model_unit_per_cun=measured&&c.expected_cun?measured/c.expected_cun:null;c.distance_discrepancy=measured!=null&&c.reported_interval_length!=null?Math.abs(measured-c.reported_interval_length):null;c.issues=[];
 if(!A||!B)c.issues.push('endpoint_coordinate_missing');
 if(c.expected_cun&&c.recomputed_model_unit_per_cun!=null&&c.recomputed_model_unit_per_cun<0.01)c.issues.push('extremely_small_model_unit_per_cun');
 if(c.distance_discrepancy!=null&&c.distance_discrepancy>0.005)c.issues.push('stored_interval_does_not_match_current_endpoint_geometry');
}
const byRegion=new Map();for(const c of calibrations)if(c.recomputed_model_unit_per_cun&&c.region){const a=byRegion.get(c.region)||[];a.push(c);byRegion.set(c.region,a);}
for(const [region,xs] of byRegion){const vals=xs.map(x=>x.recomputed_model_unit_per_cun).sort((a,b)=>a-b),med=vals[Math.floor(vals.length/2)];for(const c of xs){c.region_median_model_unit_per_cun=med;c.ratio_to_region_median=c.recomputed_model_unit_per_cun/med;if(c.ratio_to_region_median<0.4||c.ratio_to_region_median>2.5)c.issues.push('neighboring_calibration_ratio_outlier');}}
for(const c of calibrations.filter(x=>x.calibration_id==='CHEST_SUPRASTERNAL_TO_XIPHISTERNAL'))c.issues.push('BLOCKER_suprasternal_endpoint_is_sternum_center_not_jugular_notch_feature');


const bStructural=[];
for(const g of graph.geometry_nodes||[]){
 const deps=g.endpoint_node_ids||[], raw=String(g.source_raw||'').toLowerCase();
 const intrinsicallyTwoEnded=g.geometry_type==='constructed_line'||(g.geometry_type==='reference_line'&&/line connecting|connecting line|line between/.test(raw));
 if(intrinsicallyTwoEnded&&deps.length!==2)bStructural.push({kind:'GEOMETRY_LINE_CARDINALITY',node_id:g.node_id,point_id:String(g.source_statement_id||'').split(':')[1]||null,geometry_type:g.geometry_type,endpoint_count:deps.length,endpoint_node_ids:deps,source_raw:g.source_raw});
 if(String(g.geometry_type||'').includes('midpoint')&&deps.length!==2)bStructural.push({kind:'GEOMETRY_MIDPOINT_CARDINALITY',node_id:g.node_id,point_id:String(g.source_statement_id||'').split(':')[1]||null,geometry_type:g.geometry_type,endpoint_count:deps.length,endpoint_node_ids:deps,source_raw:g.source_raw});
}
for(const r of graph.relation_instances||[]){
 const args=r.argument_node_ids||[], n=args.length;
 if(r.relation_type==='between'&&n<2)bStructural.push({kind:'RELATION_ARGUMENT_CARDINALITY',relation_id:r.relation_id,point_id:String(r.subject_node_id||'').replace(/^P:/,''),relation_type:r.relation_type,argument_count:n,argument_node_ids:args,source_raw:r.source_raw});
 if(r.relation_type==='midpoint-between'&&n===1&&!String(args[0]).startsWith('G:'))bStructural.push({kind:'RELATION_ARGUMENT_CARDINALITY',relation_id:r.relation_id,point_id:String(r.subject_node_id||'').replace(/^P:/,''),relation_type:r.relation_type,argument_count:n,argument_node_ids:args,source_raw:r.source_raw});
 if(r.relation_type==='fraction-along-line'&&n===0)bStructural.push({kind:'RELATION_ARGUMENT_CARDINALITY',relation_id:r.relation_id,point_id:String(r.subject_node_id||'').replace(/^P:/,''),relation_type:r.relation_type,argument_count:n,argument_node_ids:args,source_raw:r.source_raw});
}
const bAffected=[...new Set(bStructural.map(x=>x.point_id).filter(Boolean))];

const sampleSpec=[
 ['CV24','midline','head/face','wrong'],['ST7','left','head/face','control'],['TE17','left','neck','review'],['TE16','left','neck','control'],
 ['GB26','left','thorax/abdomen','wrong'],['ST29','right','thorax/abdomen','wrong'],['GB23','left','thorax/abdomen','control'],
 ['BL54','left','back','review'],['SI14','left','back','control'],['LI10','left','upper limb','review'],['HT4','left','upper limb','control'],
 ['PC7','left','hand','review'],['PC8','left','hand','control'],['ST35','left','lower limb','wrong'],['ST31','left','lower limb','control'],
 ['BL65','left','foot','review'],['LR2','left','foot','control'],['CV1','midline','midline','wrong'],['CV12','midline','midline','control'],['GV14','midline','midline','control'],
 ['GB26','right','bilateral','wrong'],['LU5','right','bilateral','review'],['ST31','right','bilateral','control']
];
function tracePoint(id,side,region,kind){
 const p=pointRows.find(x=>x.point_id===id&&x.side===side);const rels=(p?.relation_instance_ids||[]).map(rid=>relById.get(rid)).filter(Boolean);const sources=[...new Set(p?.source_statement_ids||[])].map(sid=>sourceById.get(sid)).filter(Boolean);const lands=(p?.landmark_node_ids||[]).map(nid=>realById.get(nid)).filter(Boolean);const geoms=[...new Set(rels.flatMap(r=>r.argument_node_ids||[]))].map(nid=>geomById.get(nid)).filter(Boolean);
 const vis=wrongMap.get(id+':'+side)||(passSet.has(id+':'+side)?{label:'visual_pass_control',reason:'detailedPass',source:'visual.detailedPass'}:{label:kind==='control'?'sweep_pass_control':'not_explicitly_labeled',reason:null,source:'sample-design'});
 const calIssues=(p?.measurement_inputs||[]).flatMap(m=>calibrations.filter(c=>c.calibration_id===m.selected_calibration_id&&c.side===side).flatMap(c=>c.issues.map(issue=>({calibration_id:c.calibration_id,issue}))));
 const classes=[];if(calIssues.length)classes.push('MEASUREMENT_CALIBRATION_ERROR');if(p?.legacy_candidate)classes.push('LEGACY_COORDINATE_CANDIDATE_ERROR');classes.push('RELATION_SOLVER_NOT_EXECUTED');if((p?.legacy_candidate?.projection_distance||0)>.1)classes.push('SURFACE_PROJECTION_ERROR');
 const first=calIssues.length?'MEASUREMENT_CALIBRATION_ERROR':'RELATION_SOLVER_NOT_EXECUTED';
 return {point_id:id,side,region,sample_kind:kind,visual_evidence:vis,final_projected_coordinate:p?.coordinate_projected||null,raw_coordinate:p?.coordinate_raw||null,coordinate_candidate_source:p?.legacy_candidate||null,measurement_calibration:p?.measurement_inputs||[],geometry_operation:rels.map(r=>({relation_id:r.relation_id,relation_type:r.relation_type,argument_node_ids:r.argument_node_ids,source_raw:r.source_raw})),bp3d_realization:lands.map(x=>({node_id:x.node_id,status:x.realization_status,fma_identity:x.fma_identity,object_candidates:(x.object_candidates||[]).map(o=>({object_id:o.object_id,name:o.name,laterality:o.laterality,geometry_available:o.geometry_available})),geometry_source:x.geometry_source,unresolved_reason:x.unresolved_reason})),nested_geometry:geoms,B_relation_arguments:rels.map(r=>({relation_id:r.relation_id,relation_type:r.relation_type,argument_node_ids:r.argument_node_ids})),WHO_source_statements:sources,classifications:[...new Set(classes)],first_failing_layer:first,B_layer_assessment:'NO_AUTOMATIC_B_ERROR_ESTABLISHED; source/relation trace retained for manual adjudication',evidence_notes:['v1 builder copied legacy raw/projected coordinates after dependency/laterality gates; relation operations were not forward-executed.'].concat(calIssues.map(x=>x.calibration_id+': '+x.issue)).concat((p?.legacy_candidate?.projection_distance||0)>.1?['legacy projection distance '+p.legacy_candidate.projection_distance+' > 0.1']:[])};
}
const traces=sampleSpec.map(x=>tracePoint(...x));
const summaryByFirst=traces.reduce((o,x)=>(o[x.first_failing_layer]=(o[x.first_failing_layer]||0)+1,o),{});
const classificationCounts=traces.flatMap(x=>x.classifications).reduce((o,k)=>(o[k]=(o[k]||0)+1,o),{});
const report={schema_version:'1.0.1',artifact:'acupoint-coordinate-v1-error-attribution-audit.json',generated_at:new Date().toISOString(),baseline:{version:'acupoint-coordinate-v1',frozen:false,preserved:true,frozen_B_sha256:FROZEN_SHA,frozen_B_modified:false},status_semantics:{dependency_ready:'dependencies available only',relation_executed:'native relation geometry operation actually forward-executed',relation_satisfied:'numeric residual within tolerance',surface_projected:'raw candidate projected to Skin',visual_QC_passed:'explicit visual review passed',final_validated:'all upstream stages + numeric residual + visual QC passed'},v1_status_correction:{previous_solved_records:pointRows.filter(x=>x.coordinate_status==='solved').length,reinterpreted_as:'provisional_projected_candidate',destructive_rewrite_of_v1:false},provenance_census:{solved_physical_records:provenance.length,origin_counts:originCounts,native_relation_executed:provenance.filter(x=>x.native_relation_executed).length,legacy_candidate_reused:provenance.filter(x=>x.coordinate_origin==='legacy_bodyparts3d_candidate_reused').length,specialized_anchor_dependency_records:provenance.filter(x=>x.anchor_dependencies.some(a=>a.status==='specialized_anchor_resolved')).length,surface_projection_reused_from_legacy:provenance.filter(x=>x.surface_projection_reused_from_legacy).length},audit_sample:{audited_physical_records:traces.length,normal_controls:traces.filter(x=>x.sample_kind==='control').length,visually_wrong_records:traces.filter(x=>x.visual_evidence.label==='visually_wrong').length,visual_review_problem_records:traces.filter(x=>x.visual_evidence.label==='visual_review_problem').length,first_failing_layer_counts:summaryByFirst,classification_counts:classificationCounts,B_layer_error_suspected_records:traces.filter(x=>bAffected.includes(x.point_id)).length,realization_error_records:traces.filter(x=>x.classifications.includes('BP3D_REALIZATION_ERROR')).length,anchor_or_calibration_error_records:traces.filter(x=>x.classifications.includes('MEASUREMENT_CALIBRATION_ERROR')||x.classifications.includes('SPECIALIZED_ANCHOR_ERROR')).length,legacy_candidate_error_records:traces.filter(x=>x.classifications.includes('LEGACY_COORDINATE_CANDIDATE_ERROR')).length,surface_projection_error_records:traces.filter(x=>x.classifications.includes('SURFACE_PROJECTION_ERROR')).length,unknown_records:traces.filter(x=>x.classifications.includes('UNKNOWN')).length},specialized_reference_anchor_audit:{record_count:anchorAudit.length,anchors:anchorAudit,pairwise_sanity:sanity},proportional_calibration_audit:{unique_calibration_side_records:calibrations.length,blocker_records:calibrations.filter(x=>x.issues.some(i=>i.startsWith('BLOCKER_'))).length,issue_records:calibrations.filter(x=>x.issues.length).length,calibrations},representative_full_traces:traces,frozen_B_structural_coordinate_audit:{issue_count:bStructural.length,affected_point_count:bAffected.length,affected_points:bAffected,issues:bStructural},B_reopen_assessment:{recommendation:bStructural.length?'PROPOSE_MINIMAL_B_REOPEN_FOR_STRUCTURAL_CARDINALITY_REVIEW':'DO_NOT_REOPEN_B_YET',reason:bStructural.length?'Repeated source-geometry/relation cardinality defects exist in frozen B. Do not edit yet; adjudicate affected records against WHO source and reopen only the minimal affected subset if confirmed.':'No repeated frozen-B structural coordinate-use defect detected; current dominant failures remain C-layer.'}};
write('public/knowledge/acupoint-coordinate-v1-error-attribution-audit.json',report);
write('public/knowledge/acupoint-coordinate-v1-provenance-census.json',{schema_version:'1.0.0',generated_at:report.generated_at,status:'provisional_baseline_only',records:provenance});
write('public/knowledge/acupoint-specialized-anchor-audit-v1.json',{schema_version:'1.0.0',generated_at:report.generated_at,...report.specialized_reference_anchor_audit});
write('public/knowledge/acupoint-calibration-audit-v1.json',{schema_version:'1.0.0',generated_at:report.generated_at,...report.proportional_calibration_audit});
console.log(JSON.stringify({v1_status_correction:report.v1_status_correction,provenance_census:report.provenance_census,audit_sample:report.audit_sample,anchor_count:anchorAudit.length,calibration_records:calibrations.length,calibration_issue_records:report.proportional_calibration_audit.issue_records,calibration_blockers:report.proportional_calibration_audit.blocker_records,B_reopen:report.B_reopen_assessment},null,2));
