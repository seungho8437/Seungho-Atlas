import fs from 'node:fs';import assert from 'node:assert/strict';
const root=new URL('../',import.meta.url),read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const d=read('public/knowledge/acupoint-derived-surface-landmarks.json'),a=read('public/knowledge/acupoint-derived-surface-landmarks-audit.json');
assert.equal(d.schemaVersion,1);assert.equal(a.landmarkCount,d.landmarks.length);
assert.equal(a.invariants.noAnthropometricGuessForHairlineNippleUmbilicus,true);
assert.equal(a.invariants.derivedSoftLandmarksLabeledByConfidence,true);
assert.equal(a.invariants.unresolvedLandmarksHaveNoFabricatedGeometry,true);
for(const l of d.landmarks){
 const txt=JSON.stringify(l.geometry);
 if(String(l.status).startsWith('constructed'))assert.ok(!txt.includes('NaN')&&!txt.includes('Infinity'),l.landmarkId+': invalid constructed geometry');
 if(l.status==='manual-or-specialized-detection-required')assert.equal(l.geometry,null,l.landmarkId+': unresolved landmark must not carry geometry');
}
console.log(JSON.stringify(a,null,2));
console.log('Derived surface landmark construction validated conservatively.');
