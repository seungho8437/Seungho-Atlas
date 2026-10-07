import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>fs.writeFileSync(new URL(p,root),JSON.stringify(v,null,2)+'\n');

const frames=read('public/knowledge/acupoint-measurement-frames.json').records;
const calibrations=read('public/knowledge/acupoint-cun-calibrations.json').calibrations;

const byRegionAxis=(region,axis,unit)=>calibrations.filter(c=>c.unit===unit&&(
 c.unit==='F-cun' || (c.region===region&&c.axis===axis)
));

const records=[];let exact=0,ambiguous=0,unresolved=0,fCun=0;
for(const record of frames){
 const bindings=[];
 for(const frame of record.frames){
   if(frame.unit==='F-cun'){
     const candidates=calibrations.filter(c=>c.unit==='F-cun').map(c=>c.id);
     bindings.push({frameId:frame.id,unit:frame.unit,status:'method-bound',candidateCalibrationIds:candidates,selectionRule:'F-cun is patient/model finger based; choose the WHO finger method represented by the source context before geometry.',sourceSpan:frame.sourceSpan});
     fCun++;continue;
   }
   let candidates=byRegionAxis(frame.bodyRegion,frame.axis,frame.unit);
   // region bridges allowed by WHO proportional intervals
   if(!candidates.length&&frame.bodyRegion==='chest'&&frame.axis==='surface-geodesic')candidates=calibrations.filter(c=>c.id==='CHEST_NIPPLE_TO_NIPPLE'||c.id==='CHEST_SUPRASTERNAL_TO_XIPHISTERNAL');
   if(!candidates.length&&frame.bodyRegion==='pelvis-perineum'&&frame.axis==='transverse')candidates=calibrations.filter(c=>c.id==='CHEST_NIPPLE_TO_NIPPLE').map(c=>({...c,proxyOnly:true}));
   if(!candidates.length&&frame.bodyRegion==='abdomen'&&frame.axis==='transverse')candidates=calibrations.filter(c=>c.id==='CHEST_NIPPLE_TO_NIPPLE').map(c=>({...c,proxyOnly:true}));
   if(!candidates.length&&frame.bodyRegion==='neck')candidates=calibrations.filter(c=>c.region==='head'&&c.axis===frame.axis);
   if(!candidates.length&&frame.bodyRegion==='shoulder')candidates=calibrations.filter(c=>c.id==='UPPER_ARM_AXILLARY_TO_CUBITAL');
   if(!candidates.length&&frame.bodyRegion==='elbow')candidates=calibrations.filter(c=>c.id==='UPPER_ARM_AXILLARY_TO_CUBITAL'||c.id==='FOREARM_CUBITAL_TO_WRIST');
   if(!candidates.length&&frame.bodyRegion==='knee')candidates=calibrations.filter(c=>c.region==='leg'||c.region==='thigh'||c.region==='knee');

   const ids=candidates.map(c=>c.id);
   let status;
   if(ids.length===1&&!candidates[0].proxyOnly){status='candidate-bound';exact++;}
   else if(ids.length>0){status='ambiguous-candidate-set';ambiguous++;}
   else {status='unresolved-no-who-interval';unresolved++;}
   bindings.push({
     frameId:frame.id,unit:frame.unit,status,candidateCalibrationIds:ids,
     selectionRule:status==='candidate-bound'?'Single WHO interval matches the local region and axis; anchor entities still require geometric resolution.':status==='ambiguous-candidate-set'?'Multiple or proxy WHO intervals are possible; source landmarks/aspect must disambiguate before coordinate generation.':'No direct WHO proportional interval was assigned; do not fall back to global body height.',
     sourceSpan:frame.sourceSpan
   });
 }
 records.push({acupointId:record.acupointId,bindings});
}
const out={schemaVersion:1,methodology:{principle:'Bind each measurement frame to WHO proportional-bone or finger-cun calibrations without inventing a global cun. Ambiguity is preserved as an explicit blocker.'},records};
const audit={schemaVersion:1,measurementFrameCount:frames.reduce((n,r)=>n+r.frames.length,0),bindingCount:records.reduce((n,r)=>n+r.bindings.length,0),counts:{candidateBound:exact,ambiguousCandidateSet:ambiguous,unresolvedNoWhoInterval:unresolved,fCunMethodBound:fCun},invariants:{allFramesBoundToRecord:true,noGlobalBodyHeightFallback:true,ambiguityPreserved:true}};
write('public/knowledge/acupoint-measurement-frame-bindings.json',out);
write('public/knowledge/acupoint-measurement-calibration-audit.json',audit);
console.log(JSON.stringify(audit,null,2));
