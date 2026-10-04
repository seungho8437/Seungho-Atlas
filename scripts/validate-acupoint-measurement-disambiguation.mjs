import fs from 'node:fs';import assert from 'node:assert/strict';
const root=new URL('../',import.meta.url);const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const specs=read('public/knowledge/acupoint-location-specs.json').specs;
const frames=read('public/knowledge/acupoint-measurement-frames.json').records;
const registry=read('public/knowledge/acupoint-cun-calibrations.json').calibrations;
const dis=read('public/knowledge/acupoint-measurement-frame-disambiguation.json').records;
const audit=read('public/knowledge/acupoint-measurement-disambiguation-audit.json');
const ids=new Set(registry.map(x=>x.id)),D=new Map(dis.map(x=>[x.acupointId,x])),S=new Map(specs.map(x=>[x.acupointId,x]));
let n=0;
for(const r of frames){
 const d=D.get(r.acupointId),s=S.get(r.acupointId);assert.ok(d&&s,`${r.acupointId}: missing disambiguation/source`);
 assert.equal(d.resolutions.length,r.frames.length,`${r.acupointId}: resolution count mismatch`);
 for(const f of r.frames){
   const x=d.resolutions.find(y=>y.frameId===f.id);assert.ok(x,`${f.id}: missing resolution`);n++;
   assert.equal(x.sourceText,f.sourceText,`${f.id}: measurement source text drift`);
   assert.deepEqual(x.sourceSpan,f.sourceSpan,`${f.id}: measurement source span drift`);
   assert.ok(s.source.textKo.slice(f.sourceSpan.start,f.sourceSpan.end)===f.sourceText,`${f.id}: source span no longer matches WHO-derived location text`);
   assert.equal(x.intentCheck,'compatible-with-WHO-source-meaning',`${f.id}: WHO-intent check failed`);
   assert.ok(['high','moderate'].includes(x.confidence),`${f.id}: invalid confidence`);
   if(f.unit==='F-cun'){assert.equal(x.status,'finger-method-bound');assert.equal(x.selectedCalibrationId,null);}
   else {assert.equal(x.status,'disambiguated');assert.ok(ids.has(x.selectedCalibrationId),`${f.id}: selected calibration is not in WHO registry`);}
   assert.ok(x.evidence&&x.rationale,`${f.id}: source-evidence/rationale required`);
 }
}
assert.equal(n,audit.measurementFrameCount);
assert.equal(audit.resolutionCount,n);
assert.equal(audit.invariants.allBcunHaveExactlyOneCalibration,true);
assert.equal(audit.invariants.noAmbiguousStatusRemains,true);
assert.equal(audit.invariants.allSelectedIdsAreWhoRegistry,true);
assert.equal(audit.invariants.everyResolutionHasIntentCheck,true);
assert.equal(audit.invariants.sourceMeaningNotRewritten,true);
console.log(JSON.stringify(audit,null,2));
console.log(`Verified WHO-intent-preserving disambiguation for all ${n} measurement frames.`);
