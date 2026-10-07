import fs from 'node:fs';import assert from 'node:assert/strict';
const root=new URL('../',import.meta.url);const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const g=read('public/knowledge/acupoint-landmark-geometry.json');
const a=read('public/knowledge/acupoint-landmark-geometry-audit.json');
assert.equal(g.schemaVersion,1);
assert.equal(g.acupointEntityGeometry.length,361,'All 361 acupoints require entity-geometry records');
assert.equal(a.acupointEntityRecords,361);
assert.equal(a.calibrationEndpoints.unmappedDefinition,0,'Every WHO calibration endpoint must have a geometry-resolution definition');
assert.equal(a.invariants.noProxyUsedAsHardLandmark,true);
assert.equal(a.invariants.noFabricatedCoordinateForDerivedLandmark,true);
assert.equal(a.invariants.everyCalibrationEndpointAudited,true);
assert.equal(a.invariants.canonicalCoordinatesOnlyFromActualModelVerticesOrCentroids,true);
for(const l of g.calibrationLandmarks){
 if(l.status==='resolved-atlas-geometry'){
   const geo=l.geometry;
   if(geo.type==='concept-feature')assert.ok(Array.isArray(geo.position)&&geo.position.length===3&&geo.position.every(Number.isFinite),l.landmarkId+': invalid position');
   if(geo.type==='bilateral-feature')for(const side of ['left','right'])assert.ok(Array.isArray(geo.sides[side].position)&&geo.sides[side].position.length===3&&geo.sides[side].position.every(Number.isFinite),l.landmarkId+': invalid '+side+' position');
 }
 if(l.status==='model-derived-required')assert.equal(l.geometry,null,l.landmarkId+': derived landmark must not receive fabricated coordinate');
}
console.log(JSON.stringify(a,null,2));
console.log('Landmark geometry resolution validated without promoting proxies or soft-tissue guesses to hard landmarks.');
