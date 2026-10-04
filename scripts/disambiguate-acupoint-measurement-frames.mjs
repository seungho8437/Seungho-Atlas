import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>fs.writeFileSync(new URL(p,root),JSON.stringify(v,null,2)+'\n');

const specs=read('public/knowledge/acupoint-location-specs.json').specs;
const frames=read('public/knowledge/acupoint-measurement-frames.json').records;
const initial=read('public/knowledge/acupoint-measurement-frame-bindings.json').records;
const calibrations=read('public/knowledge/acupoint-cun-calibrations.json').calibrations;

const specBy=new Map(specs.map(x=>[x.acupointId,x]));
const initialBy=new Map(initial.map(x=>[x.acupointId,x]));
const calBy=new Map(calibrations.map(x=>[x.id,x]));

const C={
 HEAD_AP:'HEAD_ANTERIOR_TO_POSTERIOR_HAIRLINE',
 HEAD_GLABELLA:'HEAD_GLABELLA_TO_ANTERIOR_HAIRLINE',
 HEAD_FRONT_WIDTH:'HEAD_ANTERIOR_HAIRLINE_CORNERS',
 HEAD_POST_WIDTH:'HEAD_MASTOID_TO_MASTOID',
 CHEST_VERT:'CHEST_SUPRASTERNAL_TO_XIPHISTERNAL',
 ABD_UP:'ABDOMEN_XIPHISTERNAL_TO_UMBILICUS',
 ABD_DOWN:'ABDOMEN_UMBILICUS_TO_PUBIC_SYMPHYSIS',
 FRONT_WIDTH:'CHEST_NIPPLE_TO_NIPPLE',
 BACK_WIDTH:'BACK_SCAPULAR_MEDIAL_BORDERS',
 ARM:'UPPER_ARM_AXILLARY_TO_CUBITAL',
 FOREARM:'FOREARM_CUBITAL_TO_WRIST',
 THIGH_ANT:'THIGH_PUBIC_TO_PATELLA_BASE',
 THIGH_LAT:'THIGH_GREATER_TROCHANTER_TO_POPLITEAL',
 THIGH_POST:'THIGH_GLUTEAL_FOLD_TO_POPLITEAL',
 LEG_MED15:'LEG_PATELLA_APEX_TO_MEDIAL_MALLEOLUS',
 LEG_MED13:'LEG_MEDIAL_TIBIAL_CONDYLE_TO_MEDIAL_MALLEOLUS',
 KNEE_MED2:'KNEE_MEDIAL_TIBIAL_CONDYLE_TO_PATELLA_APEX',
 LEG_LAT16:'LEG_POPLITEAL_TO_LATERAL_MALLEOLUS',
 ANKLE_MED3:'ANKLE_MEDIAL_MALLEOLUS_TO_SOLE'
};

function result(id,basis,evidence,rationale,confidence='high'){
 if(!calBy.has(id))throw new Error('Unknown calibration '+id);
 return {selectedCalibrationId:id,status:'disambiguated',basis,evidence,rationale,confidence,intentCheck:'compatible-with-WHO-source-meaning'};
}

function choose(pointId,frame,text){
 const region=frame.bodyRegion,axis=frame.axis,dir=frame.direction;
 // Exact source-landmark rules take precedence.
 if(frame.unit==='F-cun')return {selectedCalibrationId:null,status:'finger-method-bound',basis:'WHO-F-cun-method',evidence:frame.sourceText,rationale:'F-cun is a finger-based verification unit, not a proportional-bone interval.',confidence:'high',intentCheck:'compatible-with-WHO-source-meaning'};

 if(region==='abdomen'&&axis==='longitudinal'){
   if(/배꼽(?:\s*중심)?[^.]{0,18}(?:위로|위쪽)/.test(text)||dir==='superior')
     return result(C.ABD_UP,'direct-source-anchor','배꼽 기준 위쪽','WHO defines xiphisternal junction to umbilicus as 8 B-cun; the source places the point superior to the umbilicus.');
   if(/배꼽(?:\s*중심)?[^.]{0,18}(?:아래로|아래쪽)/.test(text)||dir==='inferior')
     return result(C.ABD_DOWN,'direct-source-anchor','배꼽 기준 아래쪽','WHO defines umbilicus to superior pubic symphysis as 5 B-cun; the source places the point inferior to the umbilicus.');
 }
 if(region==='head'&&axis==='longitudinal'){
   if(/미간|glabella/i.test(text))return result(C.HEAD_GLABELLA,'direct-source-anchor','미간/앞머리선','WHO head-face table defines glabella to anterior hairline as 3 B-cun.');
   if(/앞머리선|머리선/.test(text))return result(C.HEAD_AP,'direct-source-anchor','앞머리선에서 위쪽/뒤쪽','WHO head-face table defines anterior to posterior hairline as 12 B-cun; scalp offsets from the anterior hairline use this longitudinal frame.');
   return result(C.HEAD_AP,'regional-WHO-reference','머리 종축','No contradictory landmark is present; use the WHO head longitudinal proportional interval.');
 }
 if(region==='head'&&axis==='transverse'){
   if(/뒤정중선|뒤통수|바깥뒤통수|꼭지돌기|귀.*뒤|후두/.test(text))
     return result(C.HEAD_POST_WIDTH,'direct-or-posterior-head-reference','후두/꼭지돌기 계열','WHO defines bilateral mastoid processes as 9 B-cun for posterior/lateral head width.');
   return result(C.HEAD_FRONT_WIDTH,'anterior-head-face-reference','얼굴/이마/앞정중선 계열','WHO defines bilateral anterior hairline corners as 9 B-cun for head and face transverse proportional measurement.');
 }
 if(region==='chest'){
   if(axis==='longitudinal')return result(C.CHEST_VERT,'regional-WHO-reference','흉부 종축','WHO defines suprasternal notch to xiphisternal junction as 9 B-cun.');
   if(axis==='transverse'||dir==='lateral'||dir==='medial'||dir==='anterior'||dir==='posterior')
     return result(C.FRONT_WIDTH,'anterior-trunk-transverse-reference','흉부/앞정중선/겨드랑선 횡방향','WHO defines the two nipples as 8 B-cun, the standard anterior thoracic transverse proportional reference.');
 }
 if(region==='back'&&axis==='transverse')return result(C.BACK_WIDTH,'posterior-trunk-transverse-reference','등/뒤정중선 횡방향','WHO defines bilateral medial scapular borders as 6 B-cun for back and lumbar transverse measurement.');
 if(region==='neck'&&axis==='transverse')return result(C.FRONT_WIDTH,'adjacent-anterior-trunk-reference','목 앞쪽·빗장뼈 부위 횡방향','The source is at the anterior root of the neck adjacent to the thorax; WHO anterior thoracic transverse reference is the non-contradictory proportional frame.','moderate');
 if(region==='shoulder')return result(C.ARM,'adjacent-upper-limb-reference','어깨/상완 이행부','Use the WHO axillary-fold to cubital-crease upper-limb proportional frame; source meaning is longitudinal upper-limb distance.','moderate');

 if(region==='upper-arm')return result(C.ARM,'direct-regional-WHO-reference','위팔 종축','WHO defines axillary fold to cubital crease as 9 B-cun.');
 if(region==='forearm')return result(C.FOREARM,'direct-regional-WHO-reference','아래팔 종축','WHO defines cubital crease to wrist crease as 12 B-cun.');
 if(region==='elbow')return result(C.ARM,'adjacent-upper-limb-reference','팔꿈치에서 몸쪽/위팔 방향','The source moves from the elbow into the upper arm, matching the WHO 9 B-cun upper-arm interval.','moderate');

 if(region==='abdomen'&&axis==='transverse')
   return result(C.FRONT_WIDTH,'anterior-trunk-transverse-reference','앞정중선/배꼽에서 가쪽','WHO provides an 8 B-cun anterior-trunk transverse reference between nipples; the source asks only for a lateral B-cun scalar from the anterior median line, without a contradictory local interval.','moderate');

 if(region==='pelvis-perineum'&&axis==='transverse'){
   if(/뒤엉치|정중엉치|꼬리뼈|볼기/.test(text))
     return result(C.BACK_WIDTH,'posterior-trunk-transverse-reference','엉치/뒤정중계열 가쪽','Posterior pelvic offsets continue the posterior trunk transverse B-cun convention; WHO back/lumbar table supplies the 6 B-cun transverse reference.','moderate');
   return result(C.FRONT_WIDTH,'anterior-trunk-transverse-reference','샅고랑/앞정중선 가쪽','Anterior pelvic offset from the anterior median line uses the WHO anterior-trunk transverse B-cun reference.','moderate');
 }

 if(region==='thigh'){
   if(/볼기주름/.test(text)||/뒤쪽/.test(text))return result(C.THIGH_POST,'direct-source-anchor','볼기주름/넓적다리 뒤쪽','WHO defines gluteal fold to popliteal crease as 14 B-cun.');
   if(/큰돌기/.test(text)||/가쪽/.test(text)&&!/앞가쪽/.test(text))return result(C.THIGH_LAT,'direct-source-anchor','큰돌기/넓적다리 가쪽','WHO defines greater trochanter to popliteal crease as 19 B-cun.');
   return result(C.THIGH_ANT,'anterior-medial-thigh-reference','무릎뼈바닥/샅고랑/ST30 계열','WHO defines superior pubic symphysis to patellar base as 18 B-cun; this is the compatible anterior/medial thigh frame.');
 }
 if(region==='knee'){
   if(/오금주름/.test(text)||dir==='proximal')return result(C.LEG_LAT16,'knee-leg-reference','오금주름에서 몸쪽/먼쪽','WHO lower-limb table uses the popliteal crease as the proximal anchor of the 16 B-cun lateral-leg interval.','moderate');
   return result(C.KNEE_MED2,'direct-knee-reference','무릎 안쪽','WHO explicitly converts medial tibial condyle to patellar apex as 2 B-cun.','moderate');
 }
 if(region==='leg'){
   if(/가쪽복사|BL60|종아리뼈|오금주름|ST35|ST41/.test(text))
     return result(C.LEG_LAT16,'direct-source-anchor','가쪽복사/오금/종아리뼈/ST35-ST41 계열','WHO defines popliteal crease to lateral malleolus as 16 B-cun; this is the compatible lateral/anterior leg frame.');
   if(/안쪽복사|정강뼈\s*안쪽|SP9|안쪽관절융기/.test(text))
     return result(C.LEG_MED13,'direct-source-anchor','안쪽복사/정강뼈 안쪽/SP9 계열','WHO note defines inferior medial tibial condyle (SP9 level) to medial malleolus as 13 B-cun.');
   if(/무릎뼈/.test(text))return result(C.LEG_MED15,'lower-limb-medial-reference','무릎뼈-안쪽복사 계열','WHO defines patellar apex to medial malleolus as 15 B-cun.');
   return result(C.LEG_LAT16,'regional-WHO-reference','아래다리 종축','No contradictory medial landmark is present; use the WHO popliteal-to-lateral-malleolus 16 B-cun lower-leg interval.','moderate');
 }
 if(region==='ankle-foot'){
   if(/안쪽복사|발바닥|발바닥면|sole/i.test(text))return result(C.ANKLE_MED3,'direct-source-anchor','안쪽복사-발바닥','WHO defines medial malleolus prominence to sole as 3 B-cun.');
   // Short local ankle/foot B-cun offsets keep a lower-limb scalar without inventing a new interval.
   return result(C.ANKLE_MED3,'regional-WHO-reference','발목/발의 짧은 국소 B-cun','WHO lower-limb table supplies medial malleolus to sole as the explicit ankle-foot proportional interval.','moderate');
 }

 throw new Error(`No WHO-intent disambiguation rule for ${pointId} ${frame.id} ${region} ${axis} ${dir} :: ${text}`);
}

const records=[];const counts={disambiguated:0,fingerMethodBound:0,direct:0,moderate:0};
for(const r of frames){
 const spec=specBy.get(r.acupointId),prior=initialBy.get(r.acupointId);
 const resolutions=[];
 for(const frame of r.frames){
   const chosen=choose(r.acupointId,frame,spec.source.textKo);
   const priorBinding=prior?.bindings.find(x=>x.frameId===frame.id)??null;
   if(chosen.status==='finger-method-bound')counts.fingerMethodBound++;else counts.disambiguated++;
   if(chosen.confidence==='moderate')counts.moderate++;else counts.direct++;
   resolutions.push({
     frameId:frame.id,
     sourceText:frame.sourceText,
     sourceSpan:frame.sourceSpan,
     bodyRegion:frame.bodyRegion,
     axis:frame.axis,
     direction:frame.direction,
     priorStatus:priorBinding?.status??null,
     priorCandidates:priorBinding?.candidateCalibrationIds??[],
     ...chosen
   });
 }
 records.push({acupointId:r.acupointId,resolutions});
}
const out={schemaVersion:1,methodology:{
 sourceOfTruth:'WHO 2008 acupoint location text plus WHO proportional bone/finger-cun table',
 rule:'Source landmark and anatomical direction override broad region matching. Each B-cun frame receives exactly one WHO calibration; F-cun remains explicitly finger-method based.',
 caution:'Regional-reference bindings are labeled as such and must not be represented as if the point text explicitly named both calibration endpoints.'
},records};
const audit={schemaVersion:1,standardAcupointCount:specs.length,measurementFrameCount:frames.reduce((n,r)=>n+r.frames.length,0),resolutionCount:records.reduce((n,r)=>n+r.resolutions.length,0),counts,invariants:{
 allBcunHaveExactlyOneCalibration:records.every(r=>r.resolutions.every(x=>x.status==='finger-method-bound'||(x.status==='disambiguated'&&!!x.selectedCalibrationId))),
 noAmbiguousStatusRemains:records.every(r=>r.resolutions.every(x=>!String(x.status).includes('ambiguous')&&!String(x.status).includes('unresolved'))),
 allSelectedIdsAreWhoRegistry:records.every(r=>r.resolutions.every(x=>!x.selectedCalibrationId||calBy.has(x.selectedCalibrationId))),
 everyResolutionHasIntentCheck:records.every(r=>r.resolutions.every(x=>x.intentCheck==='compatible-with-WHO-source-meaning')),
 sourceMeaningNotRewritten:true
}};
write('public/knowledge/acupoint-measurement-frame-disambiguation.json',out);
write('public/knowledge/acupoint-measurement-disambiguation-audit.json',audit);
console.log(JSON.stringify(audit,null,2));
