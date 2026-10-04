import fs from 'node:fs';
import assert from 'node:assert/strict';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>fs.writeFileSync(new URL(p,root),JSON.stringify(v,null,2)+'\n');

const specs=read('public/knowledge/acupoint-specialized-landmark-specs.json');
const anchors=read('public/knowledge/acupoint-specialized-landmark-anchors.json');
const derived=read('public/knowledge/acupoint-derived-surface-landmarks.json');
const atlas=read('public/models/atlas.json');

const unresolved=derived.landmarks.filter(l=>l.status==='manual-or-specialized-detection-required').map(l=>l.landmarkId).sort();
const specIds=specs.landmarks.map(x=>x.landmarkId).sort();
assert.deepEqual(specIds,unresolved,'Specialized specs must cover exactly the unresolved landmark set');

const allowedMethods=new Set(anchors.recordContract.method);
const allowedStatuses=new Set(anchors.recordContract.reviewStatus);
const records=[];
const duplicateCheck=new Set();
for(const a of anchors.records){
 assert.ok(specIds.includes(a.landmarkId),a.landmarkId+': anchor is not in unresolved registry');
 assert.ok(!duplicateCheck.has(a.landmarkId),a.landmarkId+': duplicate anchor');
 duplicateCheck.add(a.landmarkId);
 assert.ok(allowedMethods.has(a.method),a.landmarkId+': invalid method');
 assert.ok(allowedStatuses.has(a.reviewStatus),a.landmarkId+': invalid reviewStatus');
 assert.ok(Array.isArray(a.position)&&a.position.length===3&&a.position.every(Number.isFinite),a.landmarkId+': invalid position');
 assert.ok(a.modelRevision&&a.modelRevision===atlas.version,a.landmarkId+': model revision mismatch');
 assert.ok(a.surfaceProjection&&Number.isInteger(a.surfaceProjection.triangleIndex),a.landmarkId+': missing surface projection');
 assert.ok(Array.isArray(a.surfaceProjection.barycentric)&&a.surfaceProjection.barycentric.length===3&&a.surfaceProjection.barycentric.every(Number.isFinite),a.landmarkId+': invalid barycentric');
 const barySum=a.surfaceProjection.barycentric.reduce((s,v)=>s+v,0);
 assert.ok(Math.abs(barySum-1)<=1e-6,a.landmarkId+': barycentric sum must equal 1');
 assert.ok(a.surfaceProjection.barycentric.every(v=>v>=-1e-7&&v<=1+1e-7),a.landmarkId+': barycentric coordinate outside triangle');
 assert.ok(Number.isFinite(a.surfaceProjection.distance),a.landmarkId+': invalid surface distance');
 const surfacePart=atlas.parts.find(p=>p.id===a.surfaceProjection.meshId);
 assert.ok(surfacePart&&surfacePart.name==='Skin'&&surfacePart.system==='integumentary',a.landmarkId+': accepted anchor must project to canonical Skin mesh');
 if(a.reviewStatus==='accepted')assert.ok(a.surfaceProjection.distance<=specs.acceptancePolicy.positionTolerance.surfaceDistanceMaxModelUnits,a.landmarkId+': accepted anchor is too far from skin');
 assert.ok(Array.isArray(a.evidence?.views)&&a.evidence.views.length>=1,a.landmarkId+': missing evidence views');
 assert.ok(a.evidence?.definitionCheck===true,a.landmarkId+': definition check not confirmed');
 assert.ok(a.provenance?.createdBy&&a.provenance?.createdAt&&a.provenance?.sourceSpecVersion,a.landmarkId+': missing provenance');
 records.push(a);
}

const bilateralPairs=[
 ['left-anterior-hairline-corner','right-anterior-hairline-corner'],
 ['left-nipple-center','right-nipple-center']
];
const pairChecks=[];
for(const [l,r] of bilateralPairs){
 const la=records.find(x=>x.landmarkId===l),ra=records.find(x=>x.landmarkId===r);
 if(!la&&!ra){pairChecks.push({left:l,right:r,status:'not-yet-anchored'});continue;}
 assert.ok(la&&ra,`${l}/${r}: bilateral pair must be anchored together`);
 pairChecks.push({left:l,right:r,status:'paired',reviewStatuses:[la.reviewStatus,ra.reviewStatus]});
}

const audit={
 schemaVersion:1,
 unresolvedLandmarkCount:unresolved.length,
 specializedSpecCount:specIds.length,
 anchorRecordCount:records.length,
 acceptedAnchorCount:records.filter(x=>x.reviewStatus==='accepted').length,
 pendingLandmarkCount:unresolved.length-records.filter(x=>x.reviewStatus==='accepted').length,
 coverage:{
   exactUnresolvedSetCovered:true,
   missingSpecializedSpecs:[],
   extraSpecializedSpecs:[]
 },
 policies:{
   noDetectorOnlyCalibration:specs.acceptancePolicy.detectorOnlyMayNotCalibrate===true,
   acceptedRequiresSurfaceProjection:true,
   acceptedRequiresModelRevision:true,
   acceptedRequiresEvidenceAndDefinitionCheck:true,
   bilateralPairCheckEnabled:true,
   symmetrySupportingOnly:specs.acceptancePolicy.positionTolerance.pairedSymmetryIsSupportingOnly===true
 },
 pairChecks,
 readiness:records.filter(x=>x.reviewStatus==='accepted').length===unresolved.length?'all-specialized-landmarks-ready':'manual-or-specialized-anchoring-pending'
};
write('public/knowledge/acupoint-specialized-landmark-anchor-audit.json',audit);
console.log(JSON.stringify(audit,null,2));
