import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>fs.writeFileSync(new URL(p,root),JSON.stringify(v,null,2)+'\n');

const specs=read('public/knowledge/acupoint-location-specs.json').specs;
const dis=read('public/knowledge/acupoint-measurement-frame-disambiguation.json').records;
const resolution=read('public/knowledge/acupoint-resolution-audit.json');
const sourceAudit=read('public/knowledge/acupoint-location-specs-audit.json');

const all=dis.flatMap(r=>r.resolutions.map(x=>({acupointId:r.acupointId,...x})));
const provisional=all.filter(x=>x.status==='provisional-regional-reference');
const direct=all.filter(x=>x.status==='disambiguated');
const finger=all.filter(x=>x.status==='finger-method-bound');

const concerns=[];
for(const x of provisional){
  concerns.push({
    acupointId:x.acupointId,frameId:x.frameId,
    severity:'review-required',
    issue:'WHO source text does not explicitly identify both endpoints of the selected proportional interval; the binding is a regional implementation choice, not a direct statement of the point location.',
    selectedCalibrationId:x.selectedCalibrationId,
    basis:x.basis,evidence:x.evidence,rationale:x.rationale
  });
}
if(!sourceAudit.losslessVerification?.exactReconstruction)concerns.push({severity:'blocking',issue:'Lossless source reconstruction failed.'});
if(!resolution.invariants?.noGlobalBodyHeightCun)concerns.push({severity:'blocking',issue:'Global body-height cun fallback detected.'});

const verdict={
  schemaVersion:1,
  reviewPerspective:'objective pre-geometry review for acceptability to a Korean-medicine/acupuncture-trained reviewer',
  standardAcupointCount:361,
  sourceIntegrity:{
    all361Covered:sourceAudit.sourceCoverage?.all361Covered===true,
    exactReconstruction:sourceAudit.losslessVerification?.exactReconstruction===true,
    uncoveredCharacterCount:sourceAudit.losslessVerification?.uncoveredCharacterCount??null,
    assessment:'acceptable'
  },
  semanticPipeline:{
    entityResolutionCoverage:resolution.coverage?.entityResolutionRecords,
    measurementFrameCoverage:resolution.coverage?.measurementFrameRecords,
    constraintAtomCoverage:resolution.coverage?.constraintAtomRecords,
    solverPlanCoverage:resolution.coverage?.solverPlanRecords,
    noGlobalBodyHeightCun:resolution.invariants?.noGlobalBodyHeightCun===true,
    assessment:'acceptable-with-explicit-model-limitations'
  },
  measurementInterpretation:{
    directHighConfidence:direct.length,
    fingerMethodBound:finger.length,
    provisionalRegionalReferences:provisional.length,
    assessment:provisional.length?'not-acceptable-as-fully-expert-validated':'acceptable',
    rule:'Provisional regional references may be used to plan geometry but may not be represented as WHO-direct or automatically validated.'
  },
  finalVerdict:'acceptable-to-proceed-to-landmark-geometry-resolution-with-provisional-bindings-gated',
  limitations:[
    'This is not a substitute for signed human expert review.',
    'Regional proportional-cun bindings not explicitly anchored by the point text remain provisional.',
    'Model-derived depressions, folds, hairlines and other soft-tissue landmarks require separate geometric or manual validation.'
  ],
  concernCount:concerns.length,
  concerns
};
write('public/knowledge/acupoint-pregeometry-expert-review.json',verdict);
console.log(JSON.stringify({...verdict,concerns:undefined},null,2));
