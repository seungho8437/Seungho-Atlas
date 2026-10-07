import fs from 'node:fs';import assert from 'node:assert/strict';
const root=new URL('../',import.meta.url);const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const frames=read('public/knowledge/acupoint-measurement-frames.json').records;
const bindings=read('public/knowledge/acupoint-measurement-frame-bindings.json').records;
const registry=read('public/knowledge/acupoint-cun-calibrations.json').calibrations;
const ids=new Set(registry.map(x=>x.id));const B=new Map(bindings.map(x=>[x.acupointId,x]));
let n=0;
for(const r of frames){const b=B.get(r.acupointId);assert.ok(b,`${r.acupointId}: missing binding record`);assert.equal(b.bindings.length,r.frames.length,`${r.acupointId}: binding count mismatch`);for(const f of r.frames){const x=b.bindings.find(y=>y.frameId===f.id);assert.ok(x,`${f.id}: missing binding`);n++;for(const id of x.candidateCalibrationIds)assert.ok(ids.has(id),`${f.id}: unknown calibration ${id}`);if(f.unit==='B-cun')assert.notEqual(x.selectionRule,'global-body-height');if(x.status==='candidate-bound')assert.equal(x.candidateCalibrationIds.length,1);if(x.status==='unresolved-no-who-interval')assert.equal(x.candidateCalibrationIds.length,0);}}
assert.equal(n,frames.reduce((a,r)=>a+r.frames.length,0));
console.log(`Verified ${n} measurement-frame calibration bindings with no global body-height fallback.`);
