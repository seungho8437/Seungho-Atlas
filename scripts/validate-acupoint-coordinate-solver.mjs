import fs from 'node:fs';import assert from 'node:assert/strict';
const root=new URL('../',import.meta.url),read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const s=read('public/knowledge/acupoint-coordinate-solver.json'),a=read('public/knowledge/acupoint-coordinate-solver-audit.json'),d=read('public/knowledge/acupoint-coordinate-review-decisions.json');
assert.equal(s.schemaVersion,2);assert.equal(s.records.length,361);assert.equal(a.standardAcupointCount,361);assert.equal(a.measurementFrameCount,237);
assert.equal(d.endpointDecisions.length,15);assert.equal(d.regionalReferenceDecisions.length,40);assert.equal(d.fingerCunDecisions.length,11);
assert.equal(a.reviewResolution.surfacePathFramesResolved,2);assert.equal(a.reviewResolution.endpointAlternativeFramesResolved,15);assert.equal(a.reviewResolution.regionalReferenceFramesReviewed,40);assert.equal(a.reviewResolution.fingerCunFramesResolved,11);
assert.equal(a.connections.unresolvedMeasurementFrames,0);assert.equal(a.invariants.all237MeasurementFramesReady,true);assert.equal(a.invariants.noGlobalBodyHeightCun,true);assert.equal(a.invariants.skinGeodesicUsesFJ2810,true);
const bilateralGeo=a.geodesic.filter(x=>!x.key.endsWith(':midline'));
if(bilateralGeo.length===2){const lo=Math.min(...bilateralGeo.map(x=>x.intervalLength)),hi=Math.max(...bilateralGeo.map(x=>x.intervalLength));assert.ok(lo>0&&hi/lo<1.35,'bilateral Skin geodesic asymmetry too large: '+JSON.stringify(bilateralGeo));}
for(const r of s.records)for(const f of r.measurementFrames){assert.equal(f.autoSolveAllowed,true,f.id+': not ready');assert.equal(f.blocker,null,f.id+': blocker remains');assert.ok(f.selectedCalibrationId,f.id+': missing calibration');for(const x of f.sideScales){assert.ok(Number.isFinite(x.chosen?.cunLength)&&x.chosen.cunLength>0,f.id+': invalid cun '+x.side);}}
console.log(JSON.stringify(a,null,2));console.log('All 361 acupoints / 237 measurement frames are ready for coordinate regeneration.');
