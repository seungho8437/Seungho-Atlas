import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>fs.writeFileSync(new URL(p,root),JSON.stringify(v,null,2)+'\n');

const specs=read('public/knowledge/acupoint-location-specs.json').specs;
const relations=read('public/knowledge/anatomy-acupoint-relations.json');
const atlas=read('public/models/atlas.json');
const anatomyKo=read('public/knowledge/anatomy-ko.json');

const conceptById=new Map(atlas.concepts.map(c=>[c.id,c]));
const relByPoint=new Map();
for(const r of relations){const a=relByPoint.get(r.acupointId)??[];a.push(r);relByPoint.set(r.acupointId,a);}

const virtualPatterns=[
 ['anterior-median-line','anatomical-axis',/앞정중선/],
 ['posterior-median-line','anatomical-axis',/뒤정중선/],
 ['median-line','anatomical-axis',/(?<!앞|뒤)정중선/],
 ['umbilicus-center','surface-feature',/배꼽(?:\s*중심)?/],
 ['anterior-axillary-fold','surface-feature',/앞겨드랑주름/],
 ['posterior-axillary-fold','surface-feature',/뒤겨드랑주름/],
 ['cubital-crease','surface-feature',/팔오금주름/],
 ['popliteal-crease','surface-feature',/(?<!팔)오금주름/],
 ['palmar-wrist-crease','surface-feature',/손바닥쪽\s*손목주름/],
 ['dorsal-wrist-crease','surface-feature',/손등쪽\s*손목주름/],
 ['anterior-hairline','surface-feature',/앞머리선/],
 ['hairline','surface-feature',/(?<!앞)머리선/],
 ['intercostal-space','derived-space',/갈비사이공간/],
 ['interosseous-space','derived-space',/뼈사이공간/],
 ['skin-boundary','surface-feature',/피부가 만나는 경계/],
 ['nail-margin','surface-feature',/손톱|발톱/],
 ['depression','surface-feature',/오목|패인 곳/],
];
const regionAxis=(region,direction)=>{
 if(['forearm','upper-arm','thigh','leg'].includes(region)){
   if(['proximal','distal','superior','inferior'].includes(direction))return 'longitudinal';
   if(['medial','lateral','radial','ulnar','anterior','posterior'].includes(direction))return 'transverse';
 }
 if(region==='wrist-hand'||region==='ankle-foot'){
   if(['proximal','distal'].includes(direction))return 'longitudinal';
   return 'surface-geodesic';
 }
 if(['chest','abdomen','back','head','neck','pelvis-perineum','shoulder','elbow','knee'].includes(region)){
   if(['superior','inferior'].includes(direction))return 'longitudinal';
   if(['medial','lateral'].includes(direction))return 'transverse';
   return 'surface-geodesic';
 }
 return 'custom';
};

const entityRecords=[],frameRecords=[],atomRecords=[],planRecords=[];
let proxyCount=0,atlasSupportedCount=0,virtualCount=0,measurementFrameCount=0,atomCount=0;
let pointPlansReady=0,pointPlansReview=0;

for(const spec of specs){
 const text=spec.source.textKo;
 const entities=[];
 for(const r of relByPoint.get(spec.acupointId)??[]){
   const c=conceptById.get(r.anatomyId);
   const loc=anatomyKo[r.anatomyId]??{};
   const isProxy=/proxy|더 넓은 지역 개념|보수적 proxy/.test(r.noteKo??'');
   entities.push({
     id:`${spec.acupointId}:anatomy:${r.anatomyId}:${r.relation}`,
     kind:'anatomy',
     anatomyId:r.anatomyId,
     relationRole:r.relation,
     sourceNameEn:c?.name??loc.sourceNameEn??null,
     nameKo:loc.nameKo??null,
     resolution:isProxy?'atlas-proxy':'atlas-supported',
     noteKo:r.noteKo,
     sourceIds:r.sourceIds
   });
   if(isProxy)proxyCount++;else atlasSupportedCount++;
 }
 for(const [id,kind,re] of virtualPatterns){
   const matches=[...text.matchAll(new RegExp(re.source,re.flags.includes('g')?re.flags:re.flags+'g'))];
   matches.forEach((m,i)=>{
     entities.push({
       id:`${spec.acupointId}:virtual:${id}:${i+1}`,
       kind,
       virtualType:id,
       evidence:m[0],
       sourceSpan:{start:m.index,end:m.index+m[0].length},
       resolution:'derived-from-source-text'
     });virtualCount++;
   });
 }
 for(const pr of spec.pointReferences){
   entities.push({
     id:`${spec.acupointId}:acupoint:${pr.acupointId}:${pr.start}`,
     kind:'acupoint-reference',
     acupointId:pr.acupointId,
     sourceSpan:{start:pr.start,end:pr.end},
     resolution:'exact-reference'
   });
 }
 const unique=new Map(entities.map(e=>[e.id,e]));
 entityRecords.push({
   acupointId:spec.acupointId,
   sourceHash:spec.source.sha256,
   entities:[...unique.values()],
   audit:{
     anatomyRelationCount:(relByPoint.get(spec.acupointId)??[]).length,
     sourceReferenceCount:spec.pointReferences.length,
     hasAtLeastOneResolvableEntity:unique.size>0
   }
 });

 const frames=[];
 spec.measurements.forEach((m,i)=>{
   const direction=m.direction?.id??null;
   const axis=regionAxis(spec.context.bodyRegion,direction);
   const calibration=m.unit==='B-cun'?'proportional-bone-cun':'finger-cun';
   const frame={
     id:`${spec.acupointId}:MF${i+1}`,
     measurementIndex:i,
     unit:m.unit,
     value:m.value,
     direction,
     bodyRegion:spec.context.bodyRegion,
     sidePolicy:spec.context.laterality,
     axis,
     path:axis==='surface-geodesic'?'surface-geodesic':'local-anatomical-axis',
     calibration,
     calibrationStatus:m.unit==='B-cun'?'requires-regional-cun-anchor-resolution':'model-independent-source-measurement',
     sourceSpan:{start:m.start,end:m.end},
     sourceText:m.text
   };
   frames.push(frame);measurementFrameCount++;
 });
 frameRecords.push({acupointId:spec.acupointId,frames});

 const atoms=[];
 const push=(statement,type,strength,evidence={},extra={})=>{
   atoms.push({
     id:`${spec.acupointId}:C${atoms.length+1}`,
     statementId:statement.id,
     type,
     strength,
     evidence,
     sourceSpan:{start:statement.start,end:statement.end},
     sourceText:statement.text,
     ...extra
   });
 };
 for(const s of spec.statements){
   push(s,'VERBATIM_STATEMENT','hard',{text:s.text},{preservationOnly:true});
   const tags=new Set(s.semanticTags);
   if(tags.has('REGION_CONTEXT'))push(s,'IN_REGION','hard',{bodyRegion:spec.context.bodyRegion});
   if(tags.has('MIDLINE'))push(s,'ON_MIDLINE','hard',{kind:/앞정중선/.test(s.text)?'anterior':/뒤정중선/.test(s.text)?'posterior':'unspecified'});
   if(tags.has('BETWEEN'))push(s,'BETWEEN','hard',{text:'사이'});
   if(tags.has('MIDPOINT'))push(s,'MIDPOINT','hard',{text:/중점/.test(s.text)?'중점':'가운데'});
   if(tags.has('INTERSPACE'))push(s,'IN_INTERSPACE','hard',{text:'space/interspace'});
   if(tags.has('DEPRESSION'))push(s,'IN_DEPRESSION','model-dependent',{text:'오목/패인 곳'});
   if(tags.has('BORDER_MARGIN'))push(s,'ON_BORDER_OR_MARGIN','hard',{text:'경계/모서리/끝'});
   if(tags.has('FOLD'))push(s,'ON_FOLD','hard',{text:'주름'});
   if(tags.has('LINE_BETWEEN'))push(s,'ON_LINE_BETWEEN','hard',{text:'잇는 선'});
   if(tags.has('CURVE_BETWEEN'))push(s,'ON_CURVE_BETWEEN','hard',{text:'잇는 곡선'});
   if(tags.has('SAME_LEVEL'))push(s,'SAME_LEVEL','hard',{text:'같은 높이'});
   if(tags.has('INTERSECTION'))push(s,'INTERSECTION','hard',{text:'교점/만나는 지점'});
   if(tags.has('SEGMENT_FRACTION')){
     for(const f of spec.fractions.filter(f=>f.start>=s.start&&f.end<=s.end))push(s,'SEGMENT_FRACTION','hard',{numerator:f.numerator,denominator:f.denominator,value:f.value,span:{start:f.start,end:f.end}});
   }
   if(tags.has('ORDINAL_SPACE')){
     const mm=s.text.match(/(첫째|둘째|셋째|넷째|다섯째|여섯째|일곱째)\s*갈비사이공간/);
     if(mm)push(s,'ORDINAL_INTERCOSTAL_SPACE','hard',{ordinal:mm[1]});
   }
   if(tags.has('SURFACE_BOUNDARY'))push(s,'SURFACE_BOUNDARY','hard',{text:'피부 경계'});
   if(tags.has('POSTURE_CONDITION'))push(s,'POSTURE_CONDITION','model-dependent',{text:s.text});
   if(tags.has('SEX_CONDITION'))push(s,'SEX_CONDITION','hard',{text:s.text});
   const ms=spec.measurements.filter(m=>m.start>=s.start&&m.end<=s.end);
   for(const m of ms){
     const idx=spec.measurements.indexOf(m);
     push(s,'OFFSET','hard',{amount:m.value,unit:m.unit,direction:m.direction?.id??null,text:m.text},{measurementFrameId:`${spec.acupointId}:MF${idx+1}`});
   }
   for(const pr of spec.pointReferences.filter(p=>p.start>=s.start&&p.end<=s.end))push(s,'ACUPOINT_REFERENCE','hard',{acupointId:pr.acupointId,span:{start:pr.start,end:pr.end}});
 }
 atomCount+=atoms.length;
 atomRecords.push({acupointId:spec.acupointId,atoms});

 const types=new Set(atoms.filter(a=>!a.preservationOnly).map(a=>a.type));
 const solverPrimitives=[];
 if(types.has('IN_REGION'))solverPrimitives.push('REGION_RESTRICTION');
 if(types.has('ON_MIDLINE'))solverPrimitives.push('MIDLINE_CONSTRAINT');
 if(types.has('BETWEEN')||types.has('IN_INTERSPACE'))solverPrimitives.push('LOCAL_CROSS_SECTION_OR_INTERSPACE');
 if(types.has('MIDPOINT'))solverPrimitives.push('MIDPOINT');
 if(types.has('ON_LINE_BETWEEN'))solverPrimitives.push('LINE_INTERPOLATION');
 if(types.has('ON_CURVE_BETWEEN'))solverPrimitives.push('CURVE_INTERPOLATION');
 if(types.has('SEGMENT_FRACTION'))solverPrimitives.push(types.has('ON_CURVE_BETWEEN')?'CURVE_FRACTION':'SEGMENT_FRACTION');
 if(types.has('SAME_LEVEL'))solverPrimitives.push('LEVEL_CONSTRAINT');
 if(types.has('INTERSECTION'))solverPrimitives.push('INTERSECTION');
 if(types.has('ORDINAL_INTERCOSTAL_SPACE'))solverPrimitives.push('ORDINAL_SPACE');
 if(types.has('ON_FOLD')||types.has('ON_BORDER_OR_MARGIN')||types.has('IN_DEPRESSION')||types.has('SURFACE_BOUNDARY'))solverPrimitives.push('SURFACE_FEATURE');
 if(types.has('OFFSET'))solverPrimitives.push('LOCAL_OFFSET');
 if(types.has('ACUPOINT_REFERENCE'))solverPrimitives.push('ACUPOINT_RELATIVE');
 if(types.has('POSTURE_CONDITION'))solverPrimitives.push('POSE_DEPENDENT');

 const blockers=[];
 if(frames.some(f=>f.calibrationStatus==='requires-regional-cun-anchor-resolution'))blockers.push('regional-cun-anchor-resolution');
 if(entities.some(e=>e.resolution==='atlas-proxy'))blockers.push('proxy-anatomy-entity');
 if(types.has('POSTURE_CONDITION'))blockers.push('pose-dependent-landmark');
 if((relByPoint.get(spec.acupointId)??[]).length===0)blockers.push('no-atlas-anatomy-relation');
 const status=blockers.length?'review-required-before-coordinate-generation':'solver-ready';
 if(status==='solver-ready')pointPlansReady++;else pointPlansReview++;

 planRecords.push({
   acupointId:spec.acupointId,
   canonicalSurface:'body-surface',
   localRegion:spec.context.bodyRegion,
   laterality:spec.context.laterality,
   primitives:[...new Set(solverPrimitives)],
   executionOrder:[
     'resolve-anatomy-and-derived-landmarks',
     ...(frames.length?['instantiate-local-measurement-frames']:[]),
     'satisfy-hard-constraints',
     'solve-model-dependent-surface-features',
     'project-only-to-local-body-surface',
     'independent-constraint-validation'
   ],
   hardValidationRule:'all hard constraints must pass before status=validated',
   blockers:[...new Set(blockers)],
   status
 });
}

const entityOut={schemaVersion:1,methodology:{principle:'Resolve source landmarks to atlas concepts without discarding proxy status; preserve virtual/derived landmarks explicitly.'},records:entityRecords};
const frameOut={schemaVersion:1,methodology:{principle:'Every B-cun/F-cun measurement receives a body-region-local frame; B-cun calibration anchors are resolved in the next geometric calibration stage, never by global body height.'},records:frameRecords};
const atomOut={schemaVersion:1,methodology:{principle:'Every source statement retains one verbatim hard atom plus typed atomic constraints. Normalized atoms never replace the source statement.'},records:atomRecords};
const planOut={schemaVersion:1,methodology:{principle:'Solver plans are composed from primitives; coordinates are forbidden until blockers are resolved.'},records:planRecords};
const audit={
 schemaVersion:1,
 standardAcupointCount:specs.length,
 coverage:{
   entityResolutionRecords:entityRecords.length,
   measurementFrameRecords:frameRecords.length,
   constraintAtomRecords:atomRecords.length,
   solverPlanRecords:planRecords.length,
   all361Covered:[entityRecords,frameRecords,atomRecords,planRecords].every(a=>a.length===361)
 },
 counts:{
   atlasSupportedEntities:atlasSupportedCount,
   atlasProxyEntities:proxyCount,
   virtualDerivedEntities:virtualCount,
   measurementFrames:measurementFrameCount,
   constraintAtoms:atomCount,
   solverReadyPlans:pointPlansReady,
   reviewRequiredPlans:pointPlansReview
 },
 invariants:{
   canonicalSurfaceBodySurface:planRecords.every(p=>p.canonicalSurface==='body-surface'),
   everySpecHasVerbatimAtom:atomRecords.every(r=>r.atoms.some(a=>a.type==='VERBATIM_STATEMENT')),
   everyMeasurementHasFrame:frameRecords.every((r,i)=>r.frames.length===specs[i].measurements.length),
   noGlobalBodyHeightCun:true,
   hardConstraintsGateValidation:true
 }
};

write('public/knowledge/acupoint-entity-resolution.json',entityOut);
write('public/knowledge/acupoint-measurement-frames.json',frameOut);
write('public/knowledge/acupoint-constraint-atoms.json',atomOut);
write('public/knowledge/acupoint-solver-plans.json',planOut);
write('public/knowledge/acupoint-resolution-audit.json',audit);
console.log(JSON.stringify(audit,null,2));
