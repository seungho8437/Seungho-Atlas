import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>fs.writeFileSync(new URL(p,root),JSON.stringify(v,null,2)+'\n');

const atlas=read('public/models/atlas.json');
const prior=read('public/knowledge/acupoint-landmark-geometry.json');
const specializedAnchors=read('public/knowledge/acupoint-specialized-landmark-anchors.json').records??[];
const acceptedSpecialized=new Map(specializedAnchors.filter(x=>x.reviewStatus==='accepted').map(x=>[x.landmarkId,x]));
const chunks=atlas.chunks.map(c=>fs.readFileSync(new URL('public/models/'+c.url.split('/').pop(),root)));

const partsByConcept=new Map();
for(const p of atlas.parts){const arr=partsByConcept.get(p.conceptId)??[];arr.push(p);partsByConcept.set(p.conceptId,arr);}
const conceptById=new Map(atlas.concepts.map(c=>[c.id,c]));
const norm=s=>String(s??'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();

function posArray(p){const b=chunks[p.chunk];return new Float32Array(b.buffer,b.byteOffset+p.positions,p.vertexCount*3);}
function vertices(parts){const out=[];for(const p of parts??[]){const a=posArray(p);for(let i=0;i<a.length;i+=3)out.push([a[i],a[i+1],a[i+2]]);}return out;}
function stats(parts){const vs=vertices(parts);if(!vs.length)return null;const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity],sum=[0,0,0];for(const v of vs){for(let k=0;k<3;k++){min[k]=Math.min(min[k],v[k]);max[k]=Math.max(max[k],v[k]);sum[k]+=v[k];}}return {min,max,center:sum.map(x=>x/vs.length),vertices:vs};}

const skinParts=atlas.parts.filter(p=>p.system==='integumentary');
const skin=stats(skinParts), ext=skin.max.map((x,i)=>x-skin.min[i]), supAxis=ext.indexOf(Math.max(...ext));
const rem=[0,1,2].filter(i=>i!==supAxis);
function conceptPartsByName(re){const ids=atlas.concepts.filter(c=>re.test(c.name)).map(c=>c.id);return ids.flatMap(id=>partsByConcept.get(id)??[]);}
function centerByName(re){return stats(conceptPartsByName(re))?.center??null;}
const lc=centerByName(/\bleft\b/i), rc=centerByName(/\bright\b/i);
let lrAxis=rem[0],leftSign=1;
if(lc&&rc){lrAxis=rem.reduce((best,a)=>Math.abs(lc[a]-rc[a])>Math.abs(lc[best]-rc[best])?a:best,rem[0]);leftSign=Math.sign((lc[lrAxis]-rc[lrAxis])||1);}
const apAxis=[0,1,2].find(i=>i!==supAxis&&i!==lrAxis);
const skinCenter=skin.center;
const anteriorSign=1; // resolved below from sternum/vertebra geometry where possible
const sternum=centerByName(/sternum/i), spine=centerByName(/vertebr/i);
let antSign=anteriorSign;
if(sternum&&spine)antSign=Math.sign((sternum[apAxis]-spine[apAxis])||1);

function candidatesByName(words,side){
 const ws=words.map(norm);
 const cs=atlas.concepts.filter(c=>{
   const n=norm(c.name);
   if(side&& !n.includes(side))return false;
   return ws.some(w=>n===w||n.includes(w)||w.includes(n));
 }).filter(c=>partsByConcept.has(c.id));
 return cs;
}
function bestSpecific(words,side){
 const cs=candidatesByName(words,side);
 if(!cs.length)return null;
 cs.sort((a,b)=>{
   const an=norm(a.name),bn=norm(b.name);
   const aside=side&&an.includes(side)?1:0,bside=side&&bn.includes(side)?1:0;
   if(aside!==bside)return bside-aside;
   return an.length-bn.length;
 });
 return cs[0];
}
function extremePoint(st,axis,mode,filters={}){
 if(!st)return null;let best=null,bestVal=mode==='max'?-Infinity:Infinity;
 for(const v of st.vertices){
   if(filters.supMin!=null&&v[supAxis]<filters.supMin)continue;
   if(filters.supMax!=null&&v[supAxis]>filters.supMax)continue;
   const val=v[axis];
   if((mode==='max'&&val>bestVal)||(mode==='min'&&val<bestVal)){bestVal=val;best=v;}
 }
 return best;
}
function sideOutMode(side){const sign=side==='left'?leftSign:-leftSign;return sign>0?'max':'min';}
function anteriorMode(){return antSign>0?'max':'min';}
function posteriorMode(){return antSign>0?'min':'max';}

function projectSkin(target,{side=null,aspect=null,levelTolerance=null,lrTolerance=null}={}){
 let best=null,bestD=Infinity;
 const tol=levelTolerance??ext[supAxis]*0.02;
 for(const v of skin.vertices){
   if(side){
     const sign=side==='left'?leftSign:-leftSign;
     if((v[lrAxis]-skinCenter[lrAxis])*sign<0)continue;
   }
   if(Math.abs(v[supAxis]-target[supAxis])>tol)continue;
   if(lrTolerance!=null&&Math.abs(v[lrAxis]-target[lrAxis])>lrTolerance)continue;
   if(aspect==='anterior'&&(v[apAxis]-skinCenter[apAxis])*antSign<0)continue;
   if(aspect==='posterior'&&(v[apAxis]-skinCenter[apAxis])*antSign>0)continue;
   if(aspect==='plantar'){
     // plantar = inferior surface of foot; aspect filter handled by distance to target level
   }
   const d=(v[0]-target[0])**2+(v[1]-target[1])**2+(v[2]-target[2])**2;
   if(d<bestD){bestD=d;best=v;}
 }
 return best;
}

function boneStats(words,side=null){const c=bestSpecific(words,side);return c?{concept:c,stats:stats(partsByConcept.get(c.id))}:null;}
function bilateralBoneFeature(words,feature){
 const sides={};
 for(const side of ['left','right']){
   const b=boneStats(words,side); if(!b){sides[side]={status:'missing'};continue;}
   const st=b.stats;let p=null;
   if(feature==='distal-inferior')p=extremePoint(st,supAxis,'min');
   if(feature==='proximal-superior')p=extremePoint(st,supAxis,'max');
   if(feature==='lateral'){
     const cutoff=st.min[supAxis]+(st.max[supAxis]-st.min[supAxis])*0.62;
     p=extremePoint(st,lrAxis,sideOutMode(side),{supMin:cutoff});
   }
   if(feature==='medial-distal'){
     const cutoff=st.min[supAxis]+(st.max[supAxis]-st.min[supAxis])*0.28;
     const mode=sideOutMode(side)==='max'?'min':'max';
     p=extremePoint(st,lrAxis,mode,{supMax:cutoff});
   }
   sides[side]={status:p?'resolved':'missing',conceptId:b.concept.id,conceptName:b.concept.name,position:p};
 }
 return sides;
}

function jointLevel(wordsA,wordsB,side){
 const a=boneStats(wordsA,side),b=boneStats(wordsB,side);if(!a||!b)return null;
 const aInf=a.stats.min[supAxis], bSup=b.stats.max[supAxis];
 const level=(aInf+bSup)/2;
 const lr=(a.stats.center[lrAxis]+b.stats.center[lrAxis])/2;
 const ap=(a.stats.center[apAxis]+b.stats.center[apAxis])/2;
 const t=[0,0,0];t[supAxis]=level;t[lrAxis]=lr;t[apAxis]=ap;return t;
}
function surfaceAtJoint(id,wordsA,wordsB,aspect){
 const sides={};
 for(const side of ['left','right']){
   const t=jointLevel(wordsA,wordsB,side);
   const p=t?projectSkin(t,{side,aspect,levelTolerance:ext[supAxis]*0.015}):null;
   sides[side]={status:p?'constructed':'review-required',position:p,method:'joint-level surface projection',aspect};
 }
 return {landmarkId:id,status:Object.values(sides).every(x=>x.position)?'constructed-surface-geometry':'review-required',geometry:{type:'bilateral-surface-landmark',sides},confidence:'moderate'};
}

const out=new Map(prior.calibrationLandmarks.map(x=>[x.landmarkId,x]));

function set(rec){out.set(rec.landmarkId,rec);}

// Resolve bony review landmarks conservatively.
for(const [id,words,feature] of [
 ['prominence-lateral-malleolus',['fibula'],'distal-inferior'],
 ['prominence-medial-malleolus',['tibia'],'medial-distal'],
 ['lateral-prominence-greater-trochanter',['femur'],'lateral'],
]){
 const sides=bilateralBoneFeature(words,feature);
 set({landmarkId:id,status:Object.values(sides).every(x=>x.position)?'constructed-atlas-geometry':'review-required',geometry:{type:'bilateral-bone-feature',sides},confidence:'moderate',construction:'model-specific bone extremum constrained to relevant segment'});
}

// Mastoid process from inferoposterior temporal bone extremum, projected to skin.
for(const side of ['left','right']){
 const b=boneStats(['temporal bone'],side);let p=null;
 if(b){
   const st=b.stats;const lower=st.min[supAxis]+(st.max[supAxis]-st.min[supAxis])*0.45;
   const candidates=st.vertices.filter(v=>v[supAxis]<=lower);
   if(candidates.length){
     candidates.sort((u,v)=>{
       const postU=(u[apAxis]*-antSign),postV=(v[apAxis]*-antSign);
       const lowU=-u[supAxis],lowV=-v[supAxis];
       return (postV+lowV)-(postU+lowU);
     });
     p=projectSkin(candidates[0],{side,aspect:'posterior',levelTolerance:ext[supAxis]*0.025});
   }
 }
 set({landmarkId:`${side}-mastoid-process`,status:p?'constructed-surface-geometry':'review-required',geometry:p?{type:'bone-guided-surface-point',position:p}:null,confidence:'moderate',construction:'inferoposterior temporal-bone guided surface projection'});
}

// Joint creases and popliteal fossa.
set(surfaceAtJoint('cubital-crease',['humerus'],['radius','ulna'],'anterior'));
set(surfaceAtJoint('palmar-wrist-crease',['radius','ulna'],['carpal'],'anterior'));
set(surfaceAtJoint('dorsal-wrist-crease',['radius','ulna'],['carpal'],'posterior'));
set(surfaceAtJoint('popliteal-crease',['femur'],['tibia'],'posterior'));
set(surfaceAtJoint('center-popliteal-fossa',['femur'],['tibia'],'posterior'));

// Sole: most inferior plantar skin point per side around foot.
{
 const sides={};
 for(const side of ['left','right']){
   const foot=boneStats(['talus','calcaneus','metatarsal'],side);
   let p=null;
   const sign=side==='left'?leftSign:-leftSign;
   const vs=skin.vertices.filter(v=>(v[lrAxis]-skinCenter[lrAxis])*sign>0 && v[supAxis] < skin.min[supAxis]+ext[supAxis]*0.14);
   if(vs.length)p=vs.reduce((a,b)=>b[supAxis]<a[supAxis]?b:a);
   sides[side]={status:p?'constructed':'review-required',position:p,method:'inferior plantar skin extremum'};
 }
 set({landmarkId:'sole',status:Object.values(sides).every(x=>x.position)?'constructed-surface-region':'review-required',geometry:{type:'bilateral-surface-region-anchor',sides},confidence:'high',construction:'inferior plantar skin extremum'});
}

// Axillary folds: proximal humerus level, anterior/posterior lateral skin projection.
for(const [id,aspect] of [['anterior-axillary-fold','anterior'],['posterior-axillary-fold','posterior']]){
 const sides={};
 for(const side of ['left','right']){
   const hum=boneStats(['humerus'],side);let p=null;
   if(hum){
     const st=hum.stats,level=st.max[supAxis]-(st.max[supAxis]-st.min[supAxis])*0.12;
     const t=[...st.center];t[supAxis]=level;
     p=projectSkin(t,{side,aspect,levelTolerance:ext[supAxis]*0.025});
   }
   sides[side]={status:p?'constructed':'review-required',position:p,method:'proximal-humerus-level surface projection',aspect};
 }
 set({landmarkId:id,status:Object.values(sides).every(x=>x.position)?'constructed-surface-geometry':'review-required',geometry:{type:'bilateral-surface-landmark',sides},confidence:'moderate',construction:'proximal-humerus level surface fold proxy'});
}

// Gluteal fold: posterior skin at proximal femur / lesser-trochanter transition.
{
 const sides={};
 for(const side of ['left','right']){
   const fem=boneStats(['femur'],side);let p=null;
   if(fem){
     const st=fem.stats,level=st.max[supAxis]-(st.max[supAxis]-st.min[supAxis])*0.18;
     const t=[...st.center];t[supAxis]=level;
     p=projectSkin(t,{side,aspect:'posterior',levelTolerance:ext[supAxis]*0.025});
   }
   sides[side]={status:p?'constructed':'review-required',position:p,method:'proximal-femur-level posterior surface projection'};
 }
 set({landmarkId:'gluteal-fold',status:Object.values(sides).every(x=>x.position)?'constructed-surface-geometry':'review-required',geometry:{type:'bilateral-surface-landmark',sides},confidence:'moderate',construction:'proximal-femur posterior surface fold proxy'});
}

// Pubic symphysis: use medial pubic-bone superior extremum when discrete symphysis is absent.
{
 const pelvis=stats(conceptPartsByName(/pubis|pubic bone|hip bone/i));let p=null;
 if(pelvis){
   const nearMid=pelvis.vertices.filter(v=>Math.abs(v[lrAxis]-skinCenter[lrAxis])<ext[lrAxis]*0.08);
   if(nearMid.length){const b=nearMid.reduce((a,b)=>b[supAxis]>a[supAxis]?b:a);p=projectSkin(b,{aspect:'anterior',levelTolerance:ext[supAxis]*0.02,lrTolerance:ext[lrAxis]*0.06});}
 }
 set({landmarkId:'superior-border-pubic-symphysis',status:p?'constructed-surface-geometry':'review-required',geometry:p?{type:'bone-guided-surface-point',position:p}:null,confidence:'moderate',construction:'superomedial pubic-bone guided anterior surface projection'});
}

// Xiphisternal junction: inferior sternum/xiphoid transition.
{
 const xip=stats(conceptPartsByName(/xiphoid/i)),ster=stats(conceptPartsByName(/sternum/i));let p=null;
 const guide=xip?.max?.[supAxis]!=null?(()=>{const t=xip.center.slice();t[supAxis]=xip.max[supAxis];return t;})():ster?(()=>{const t=ster.center.slice();t[supAxis]=ster.min[supAxis]+(ster.max[supAxis]-ster.min[supAxis])*0.18;return t;})():null;
 if(guide)p=projectSkin(guide,{aspect:'anterior',levelTolerance:ext[supAxis]*0.02,lrTolerance:ext[lrAxis]*0.04});
 set({landmarkId:'midpoint-xiphisternal-junction',status:p?'constructed-surface-geometry':'review-required',geometry:p?{type:'bone-guided-surface-point',position:p}:null,confidence:xip?'high':'moderate',construction:xip?'superior xiphoid guided anterior surface projection':'inferior sternum proxy'});
}

// Glabella: anterior surface at inferomedial frontal-bone level.
{
 const frontal=stats(conceptPartsByName(/frontal bone/i));let p=null;
 if(frontal){
   const level=frontal.min[supAxis]+(frontal.max[supAxis]-frontal.min[supAxis])*0.22;
   const near=frontal.vertices.filter(v=>Math.abs(v[supAxis]-level)<ext[supAxis]*0.012&&Math.abs(v[lrAxis]-skinCenter[lrAxis])<ext[lrAxis]*0.035);
   if(near.length){const b=near.reduce((a,b)=>((b[apAxis]-a[apAxis])*antSign>0)?b:a);p=projectSkin(b,{aspect:'anterior',levelTolerance:ext[supAxis]*0.012,lrTolerance:ext[lrAxis]*0.035});}
 }
 set({landmarkId:'glabella',status:p?'constructed-surface-geometry':'review-required',geometry:p?{type:'bone-guided-surface-point',position:p}:null,confidence:'moderate',construction:'inferomedial frontal-bone guided anterior surface projection'});
}

// Soft landmarks remain gated unless an accepted model-revision-specific surface anchor exists.
for(const id of ['midpoint-anterior-hairline','midpoint-posterior-hairline','left-anterior-hairline-corner','right-anterior-hairline-corner','left-nipple-center','right-nipple-center','umbilicus-center','radial-crease-proximal-interphalangeal-middle-finger','radial-crease-distal-interphalangeal-middle-finger']){
 const old=out.get(id),anchor=acceptedSpecialized.get(id);
 if(anchor)set({...old,status:'accepted-specialized-anchor',geometry:{type:'accepted-surface-anchor',position:anchor.position,surfaceProjection:anchor.surfaceProjection,method:anchor.method,side:anchor.side??null,detectorId:anchor.detectorId??null,detectorConfidence:anchor.detectorConfidence??null},confidence:anchor.detectorConfidence==='high'?'high':'reviewed',constructionNote:'Accepted by interactive landmark QC on the exact BodyParts3D model revision.'});
 else set({...old,status:'manual-or-specialized-detection-required',geometry:null,confidence:'unresolved',constructionNote:'No accepted model-specific surface anchor is available; anthropometric fallback is prohibited.'});
}

const landmarks=[...out.values()].sort((a,b)=>a.landmarkId.localeCompare(b.landmarkId));
const statuses={};for(const l of landmarks)statuses[l.status]=(statuses[l.status]??0)+1;
const audit={
 schemaVersion:1,
 landmarkCount:landmarks.length,
 statusCounts:statuses,
 resolvedOrConstructed:landmarks.filter(l=>['resolved-atlas-geometry','constructed-atlas-geometry','constructed-surface-geometry','constructed-surface-region','accepted-specialized-anchor'].includes(l.status)).length,
 unresolved:landmarks.filter(l=>['review-required','manual-or-specialized-detection-required'].includes(l.status)).length,
 invariants:{
   noAnthropometricGuessForHairlineNippleUmbilicus:true,
   allConstructedCoordinatesFinite:landmarks.filter(l=>String(l.status).startsWith('constructed')).every(l=>JSON.stringify(l.geometry).match(/null/)===null),
   derivedSoftLandmarksLabeledByConfidence:landmarks.filter(l=>String(l.status).startsWith('constructed')).every(l=>['high','moderate'].includes(l.confidence)),
   unresolvedLandmarksHaveNoFabricatedGeometry:landmarks.filter(l=>l.status==='manual-or-specialized-detection-required').every(l=>l.geometry===null),
   acceptedSpecializedAnchorsPreserveSurfaceProjection:landmarks.filter(l=>l.status==='accepted-specialized-anchor').every(l=>l.geometry?.type==='accepted-surface-anchor'&&l.geometry?.surfaceProjection?.meshId)
 }
};
write('public/knowledge/acupoint-derived-surface-landmarks.json',{schemaVersion:1,coordinateFrame:{superiorInferiorAxis:supAxis,leftRightAxis:lrAxis,anteriorPosteriorAxis:apAxis,leftSign,anteriorSign:antSign},landmarks});
write('public/knowledge/acupoint-derived-surface-landmarks-audit.json',audit);
console.log(JSON.stringify(audit,null,2));
