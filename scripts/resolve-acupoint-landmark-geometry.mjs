import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>fs.writeFileSync(new URL(p,root),JSON.stringify(v,null,2)+'\n');

const atlas=read('public/models/atlas.json');
const anatomyKo=read('public/knowledge/anatomy-ko.json');
const entities=read('public/knowledge/acupoint-entity-resolution.json').records;
const calibrations=read('public/knowledge/acupoint-cun-calibrations.json').calibrations;
const dis=read('public/knowledge/acupoint-measurement-frame-disambiguation.json').records;

const chunks=atlas.chunks.map(c=>fs.readFileSync(new URL('public/models/'+c.url.split('/').pop(),root)));
const partsById=new Map(atlas.parts.map(p=>[p.id,p]));
const partsByConcept=new Map();
for(const c of atlas.concepts){
  const arr=(c.elements??[]).map(id=>partsById.get(id)).filter(Boolean);
  if(arr.length)partsByConcept.set(c.id,arr);
}
for(const p of atlas.parts){
  const arr=partsByConcept.get(p.conceptId)??[];
  if(!arr.some(x=>x.id===p.id))arr.push(p);
  partsByConcept.set(p.conceptId,arr);
}
function positionsOfPart(p){const b=chunks[p.chunk];return new Float32Array(b.buffer,b.byteOffset+p.positions,p.vertexCount*3);}
function stats(parts){
 let min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity],sum=[0,0,0],n=0;
 for(const p of parts??[]){const a=positionsOfPart(p);for(let i=0;i<a.length;i+=3){const v=[a[i],a[i+1],a[i+2]];for(let k=0;k<3;k++){min[k]=Math.min(min[k],v[k]);max[k]=Math.max(max[k],v[k]);sum[k]+=v[k];}n++;}}
 return n?{min,max,center:sum.map(x=>x/n),n}:null;
}
const surfaceParts=atlas.parts.filter(p=>p.system==='integumentary');
const body=stats(surfaceParts);
const ext=body.max.map((x,i)=>x-body.min[i]),supAxis=ext.indexOf(Math.max(...ext));
const rem=[0,1,2].filter(i=>i!==supAxis);
function namedCenter(re){return stats(atlas.parts.filter(p=>re.test(p.name)))?.center??null;}
const lc=namedCenter(/\bleft\b/i),rc=namedCenter(/\bright\b/i);
let lrAxis=rem[0],leftSign=1;
if(lc&&rc){lrAxis=rem.reduce((best,a)=>Math.abs(lc[a]-rc[a])>Math.abs(lc[best]-rc[best])?a:best,rem[0]);leftSign=Math.sign((lc[lrAxis]-rc[lrAxis])||1);}
const apAxis=[0,1,2].find(i=>i!==supAxis&&i!==lrAxis);

const norm=s=>String(s??'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const conceptByNorm=new Map();
for(const c of atlas.concepts){const k=norm(c.name);const arr=conceptByNorm.get(k)??[];arr.push(c);conceptByNorm.set(k,arr);}

function resolveConcept(aliases){
 for(const alias of aliases){
   const exact=conceptByNorm.get(norm(alias))??[];
   if(exact.length===1)return {status:'exact',concept:exact[0],matchedAlias:alias};
   if(exact.length>1)return {status:'ambiguous',candidates:exact.map(x=>({id:x.id,name:x.name})),matchedAlias:alias};
 }
 for(const alias of aliases){
   const a=norm(alias); if(!a)continue;
   const candidates=atlas.concepts.filter(c=>norm(c.name).includes(a)||a.includes(norm(c.name))).filter(c=>partsByConcept.has(c.id));
   if(candidates.length===1)return {status:'unique-fuzzy',concept:candidates[0],matchedAlias:alias};
   if(candidates.length>1)return {status:'ambiguous',candidates:candidates.slice(0,12).map(x=>({id:x.id,name:x.name})),matchedAlias:alias};
 }
 return {status:'missing'};
}
function featurePoint(conceptId,feature,side=null){
 const st=stats(partsByConcept.get(conceptId));if(!st)return null;
 if(feature==='center')return st.center;
 let axis=null,which=null;
 if(feature==='superior'){axis=supAxis;which='max';}
 if(feature==='inferior'){axis=supAxis;which='min';}
 if(feature==='anterior'){axis=apAxis;which='max';}
 if(feature==='posterior'){axis=apAxis;which='min';}
 if(feature==='medial'||feature==='lateral'){
   if(!side)return null;
   axis=lrAxis;
   const sideSign=side==='left'?leftSign:-leftSign;
   const outwardMax=sideSign>0?'max':'min',inward=sideSign>0?'min':'max';
   which=feature==='lateral'?outwardMax:inward;
 }
 if(axis===null)return null;
 const target=which==='max'?st.max[axis]:st.min[axis];
 let best=null,bestD=Infinity;
 for(const p of partsByConcept.get(conceptId)??[]){const a=positionsOfPart(p);for(let i=0;i<a.length;i+=3){const d=Math.abs(a[i+axis]-target);if(d<bestD){bestD=d;best=[a[i],a[i+1],a[i+2]];}}}
 return best;
}

const endpointDefs={
 'midpoint-anterior-hairline':{kind:'derived-soft-landmark',construction:'hairline-midpoint',reason:'Hairline is a surface landmark not reliably represented as a discrete BodyParts3D concept.'},
 'midpoint-posterior-hairline':{kind:'derived-soft-landmark',construction:'hairline-midpoint',reason:'Hairline is a surface landmark not reliably represented as a discrete BodyParts3D concept.'},
 'glabella':{kind:'concept-or-surface-feature',aliases:['glabella'],feature:'center'},
 'left-anterior-hairline-corner':{kind:'derived-soft-landmark',construction:'hairline-corner',side:'left'},
 'right-anterior-hairline-corner':{kind:'derived-soft-landmark',construction:'hairline-corner',side:'right'},
 'left-mastoid-process':{kind:'concept-feature',aliases:['left mastoid process','mastoid process of left temporal bone'],feature:'center',side:'left'},
 'right-mastoid-process':{kind:'concept-feature',aliases:['right mastoid process','mastoid process of right temporal bone'],feature:'center',side:'right'},
 'suprasternal-notch':{kind:'concept-feature',aliases:['jugular notch of sternum','jugular notch','suprasternal notch'],feature:'center'},
 'midpoint-xiphisternal-junction':{kind:'concept-feature',aliases:['xiphisternal joint','xiphisternal synchondrosis','xiphisternal junction'],feature:'center'},
 'umbilicus-center':{kind:'concept-or-surface-feature',aliases:['umbilicus','navel'],feature:'center'},
 'superior-border-pubic-symphysis':{kind:'concept-feature',aliases:['pubic symphysis','symphysis pubis'],feature:'superior'},
 'left-nipple-center':{kind:'concept-or-surface-feature',aliases:['left nipple','nipple of left breast'],feature:'center',side:'left'},
 'right-nipple-center':{kind:'concept-or-surface-feature',aliases:['right nipple','nipple of right breast'],feature:'center',side:'right'},
 'left-medial-border-scapula':{kind:'concept-feature',aliases:['left scapula'],feature:'medial',side:'left'},
 'right-medial-border-scapula':{kind:'concept-feature',aliases:['right scapula'],feature:'medial',side:'right'},
 'anterior-axillary-fold':{kind:'derived-soft-landmark',construction:'axillary-fold-anterior'},
 'posterior-axillary-fold':{kind:'derived-soft-landmark',construction:'axillary-fold-posterior'},
 'cubital-crease':{kind:'derived-soft-landmark',construction:'joint-crease',region:'elbow'},
 'palmar-wrist-crease':{kind:'derived-soft-landmark',construction:'joint-crease',region:'wrist',aspect:'palmar'},
 'dorsal-wrist-crease':{kind:'derived-soft-landmark',construction:'joint-crease',region:'wrist',aspect:'dorsal'},
 'base-of-patella':{kind:'bilateral-concept-feature',aliasesLeft:['left patella'],aliasesRight:['right patella'],feature:'superior'},
 'apex-of-patella':{kind:'bilateral-concept-feature',aliasesLeft:['left patella'],aliasesRight:['right patella'],feature:'inferior'},
 'center-popliteal-fossa':{kind:'derived-soft-landmark',construction:'popliteal-fossa-center'},
 'prominence-medial-malleolus':{kind:'bilateral-concept-feature',aliasesLeft:['left medial malleolus','medial malleolus of left tibia'],aliasesRight:['right medial malleolus','medial malleolus of right tibia'],feature:'center'},
 'inferior-border-medial-condyle-tibia':{kind:'bilateral-concept-feature',aliasesLeft:['left medial condyle of tibia','medial condyle of left tibia'],aliasesRight:['right medial condyle of tibia','medial condyle of right tibia'],feature:'inferior'},
 'lateral-prominence-greater-trochanter':{kind:'bilateral-concept-feature',aliasesLeft:['left greater trochanter','greater trochanter of left femur'],aliasesRight:['right greater trochanter','greater trochanter of right femur'],feature:'lateral'},
 'gluteal-fold':{kind:'derived-soft-landmark',construction:'gluteal-fold'},
 'popliteal-crease':{kind:'derived-soft-landmark',construction:'joint-crease',region:'knee-posterior'},
 'prominence-lateral-malleolus':{kind:'bilateral-concept-feature',aliasesLeft:['left lateral malleolus','lateral malleolus of left fibula'],aliasesRight:['right lateral malleolus','lateral malleolus of right fibula'],feature:'center'},
 'sole':{kind:'derived-surface-region',construction:'plantar-surface'},
 'radial-crease-proximal-interphalangeal-middle-finger':{kind:'derived-soft-landmark',construction:'finger-crease'},
 'radial-crease-distal-interphalangeal-middle-finger':{kind:'derived-soft-landmark',construction:'finger-crease'}
};

function resolveEndpoint(id){
 const d=endpointDefs[id];
 if(!d)return {landmarkId:id,status:'unmapped-definition',geometry:null};
 if(d.kind.startsWith('derived'))return {landmarkId:id,status:'model-derived-required',geometry:null,definition:d};
 if(d.kind==='bilateral-concept-feature'){
   const sides={};
   for(const [side,aliases] of [['left',d.aliasesLeft],['right',d.aliasesRight]]){
     const r=resolveConcept(aliases);
     if((r.status==='exact'||r.status==='unique-fuzzy')&&r.concept){
       sides[side]={status:r.status,conceptId:r.concept.id,conceptName:r.concept.name,feature:d.feature,position:featurePoint(r.concept.id,d.feature,side)};
     }else sides[side]={status:r.status,candidates:r.candidates??[]};
   }
   const ok=Object.values(sides).every(x=>x.position);
   return {landmarkId:id,status:ok?'resolved-atlas-geometry':'review-required',geometry:{type:'bilateral-feature',sides},definition:d};
 }
 const r=resolveConcept(d.aliases??[]);
 if((r.status==='exact'||r.status==='unique-fuzzy')&&r.concept){
   const pos=featurePoint(r.concept.id,d.feature??'center',d.side??null);
   return {landmarkId:id,status:pos?'resolved-atlas-geometry':'review-required',geometry:{type:'concept-feature',conceptId:r.concept.id,conceptName:r.concept.name,feature:d.feature??'center',side:d.side??null,position:pos,match:r.status},definition:d};
 }
 return {landmarkId:id,status:'review-required',geometry:{type:'concept-feature',candidates:r.candidates??[]},definition:d};
}

const endpointIds=new Set();
for(const c of calibrations){
 for(const field of ['from','to']){
   const v=c[field]; if(Array.isArray(v))v.forEach(x=>endpointIds.add(x)); else if(typeof v==='string')endpointIds.add(v);
 }
}
const calibrationLandmarks=[...endpointIds].sort().map(resolveEndpoint);

const entityGeometry=[];
for(const record of entities){
 const resolved=[];
 for(const e of record.entities){
   if(e.kind!=='anatomy')continue;
   const c=atlas.concepts.find(x=>x.id===e.anatomyId);
   const st=c?stats(partsByConcept.get(c.id)):null;
   resolved.push({
     entityId:e.id,anatomyId:e.anatomyId,nameKo:e.nameKo,sourceNameEn:e.sourceNameEn,
     sourceResolution:e.resolution,
     geometryStatus:st?(e.resolution==='atlas-proxy'?'proxy-geometry-only':'resolved-atlas-concept'):'missing-model-geometry',
     geometry:st?{center:st.center,min:st.min,max:st.max,vertexCount:st.n}:null,
     usableAsHardLandmark:!!st&&e.resolution!=='atlas-proxy'
   });
 }
 entityGeometry.push({acupointId:record.acupointId,entities:resolved});
}

const usedCalibrationIds=new Set(dis.flatMap(r=>r.resolutions.map(x=>x.selectedCalibrationId).filter(Boolean)));
const calibrationGeometry=calibrations.map(c=>{
 const ids=[...(Array.isArray(c.from)?c.from:[c.from]).filter(Boolean),...(Array.isArray(c.to)?c.to:[c.to]).filter(Boolean)];
 const lm=ids.map(id=>calibrationLandmarks.find(x=>x.landmarkId===id));
 const hardReady=lm.every(x=>x&&x.status==='resolved-atlas-geometry');
 return {...c,usedByCurrentPipeline:usedCalibrationIds.has(c.id),landmarkGeometryStatus:hardReady?'atlas-geometry-ready':'requires-derived-or-manual-landmark',landmarks:lm.map(x=>({landmarkId:x?.landmarkId,status:x?.status}))};
});

const audit={
 schemaVersion:1,
 calibrationEndpointCount:calibrationLandmarks.length,
 calibrationEndpoints:{
   resolvedAtlasGeometry:calibrationLandmarks.filter(x=>x.status==='resolved-atlas-geometry').length,
   modelDerivedRequired:calibrationLandmarks.filter(x=>x.status==='model-derived-required').length,
   reviewRequired:calibrationLandmarks.filter(x=>x.status==='review-required').length,
   unmappedDefinition:calibrationLandmarks.filter(x=>x.status==='unmapped-definition').length
 },
 calibrationCount:calibrationGeometry.length,
 calibrationGeometryReady:calibrationGeometry.filter(x=>x.landmarkGeometryStatus==='atlas-geometry-ready').length,
 calibrationGeometryNotReady:calibrationGeometry.filter(x=>x.landmarkGeometryStatus!=='atlas-geometry-ready').length,
 acupointEntityRecords:entityGeometry.length,
 anatomyEntities:entityGeometry.reduce((n,r)=>n+r.entities.length,0),
 hardLandmarkUsableEntities:entityGeometry.reduce((n,r)=>n+r.entities.filter(x=>x.usableAsHardLandmark).length,0),
 proxyGeometryEntities:entityGeometry.reduce((n,r)=>n+r.entities.filter(x=>x.geometryStatus==='proxy-geometry-only').length,0),
 invariants:{
   noProxyUsedAsHardLandmark:entityGeometry.every(r=>r.entities.filter(x=>x.sourceResolution==='atlas-proxy').every(x=>!x.usableAsHardLandmark)),
   noFabricatedCoordinateForDerivedLandmark:calibrationLandmarks.filter(x=>x.status==='model-derived-required').every(x=>x.geometry===null),
   everyCalibrationEndpointAudited:calibrationLandmarks.length===endpointIds.size,
   canonicalCoordinatesOnlyFromActualModelVerticesOrCentroids:true
 }
};

write('public/knowledge/acupoint-landmark-geometry.json',{schemaVersion:1,coordinateFrame:{superiorInferiorAxis:supAxis,leftRightAxis:lrAxis,anteriorPosteriorAxis:apAxis,leftSign},calibrationLandmarks,calibrationGeometry,acupointEntityGeometry:entityGeometry});
write('public/knowledge/acupoint-landmark-geometry-audit.json',audit);
console.log(JSON.stringify(audit,null,2));
