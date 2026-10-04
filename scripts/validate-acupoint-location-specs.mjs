import fs from 'node:fs';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';

const root=new URL('../',import.meta.url);
const readJson=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const acupoints=readJson('public/knowledge/acupoints.json');
const registry=readJson('public/knowledge/acupoint-location-specs.json');
const sha256=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');
const sourceById=new Map(acupoints.map(p=>[p.id,p]));

assert.equal(registry.schemaVersion,2,'Unsupported location-spec schema version');
assert.equal(registry.specs.length,361,'Location specs must contain all 361 standard acupoints');
assert.equal(new Set(registry.specs.map(s=>s.acupointId)).size,361,'Duplicate location spec ids');

let statementCount=0,measurementCount=0,fractionCount=0,pointReferenceCount=0;
let unspecifiedRegionCount=0;
const perPoint=[];

for(const spec of registry.specs){
 const point=sourceById.get(spec.acupointId);
 assert.ok(point,`${spec.acupointId}: spec points to missing acupoint`);
 const source=point.locationKo;
 assert.equal(spec.source.textKo,source,`${spec.acupointId}: source text drift`);
 assert.equal(spec.source.sha256,sha256(source),`${spec.acupointId}: source hash mismatch`);
 assert.equal(spec.context.laterality,point.laterality,`${spec.acupointId}: laterality drift`);
 assert.equal(spec.context.surface,'body-surface',`${spec.acupointId}: canonical target must remain body-surface`);
 assert.equal(spec.preservation.lossless,true,`${spec.acupointId}: lossless flag must be true`);
 assert.deepEqual(spec.preservation.lossyTransformations,[],`${spec.acupointId}: lossy transformation recorded`);
 assert.deepEqual(spec.preservation.uncoveredText,[],`${spec.acupointId}: uncovered text recorded`);
 if(spec.context.bodyRegion==='unspecified')unspecifiedRegionCount++;

 let cursor=0,reconstructed='';
 for(const s of spec.statements){
   assert.equal(s.start,cursor,`${spec.acupointId}: statement gap/overlap at ${cursor}`);
   assert.ok(s.end>s.start,`${spec.acupointId}: empty statement`);
   assert.equal(s.text,source.slice(s.start,s.end),`${spec.acupointId}: statement span text mismatch`);
   reconstructed+=s.text; cursor=s.end; statementCount++;
   assert.ok(Array.isArray(s.semanticTags)&&s.semanticTags.length,`${spec.acupointId}: statement lacks semantic classification`);
   const vc=spec.constraints.find(c=>c.id===s.verbatimConstraintId);
   assert.ok(vc,`${spec.acupointId}: missing verbatim constraint for ${s.id}`);
   assert.equal(vc.text,s.text,`${spec.acupointId}: verbatim constraint drift`);
   assert.deepEqual(vc.sourceSpan,{start:s.start,end:s.end},`${spec.acupointId}: verbatim span drift`);
 }
 assert.equal(cursor,source.length,`${spec.acupointId}: source tail is uncovered`);
 assert.equal(reconstructed,source,`${spec.acupointId}: exact reconstruction failed`);

 const expectedMeasurements=[...source.matchAll(/(\d+(?:\.\d+)?)\s*(B-cun|F-cun)/g)];
 assert.equal(spec.measurements.length,expectedMeasurements.length,`${spec.acupointId}: measurement token loss`);
 for(let i=0;i<expectedMeasurements.length;i++){
   const m=expectedMeasurements[i],got=spec.measurements[i];
   assert.equal(got.text,m[0],`${spec.acupointId}: measurement text drift`);
   assert.equal(got.start,m.index,`${spec.acupointId}: measurement span drift`);
   assert.equal(got.end,m.index+m[0].length,`${spec.acupointId}: measurement end drift`);
 } measurementCount+=spec.measurements.length;

 const expectedFractions=[...source.matchAll(/(\d+)\s*\/\s*(\d+)/g)];
 assert.equal(spec.fractions.length,expectedFractions.length,`${spec.acupointId}: fraction token loss`);
 for(let i=0;i<expectedFractions.length;i++){
   const m=expectedFractions[i],got=spec.fractions[i];
   assert.equal(got.text,m[0],`${spec.acupointId}: fraction text drift`);
   assert.equal(got.start,m.index,`${spec.acupointId}: fraction span drift`);
 } fractionCount+=spec.fractions.length;

 const expectedRefs=[...source.matchAll(/\b(?:LU|LI|ST|SP|HT|SI|BL|KI|PC|TE|GB|LR|GV|CV)\d+\b/g)];
 assert.equal(spec.pointReferences.length,expectedRefs.length,`${spec.acupointId}: acupoint-reference token loss`);
 for(let i=0;i<expectedRefs.length;i++){
   assert.equal(spec.pointReferences[i].acupointId,expectedRefs[i][0],`${spec.acupointId}: point-reference drift`);
   assert.equal(spec.pointReferences[i].start,expectedRefs[i].index,`${spec.acupointId}: point-reference span drift`);
 } pointReferenceCount+=spec.pointReferences.length;

 if(/남성/.test(source))assert.ok(spec.conditions.some(c=>c.type==='sex'&&c.value==='male'),`${spec.acupointId}: male alternative lost`);
 if(/여성/.test(source))assert.ok(spec.conditions.some(c=>c.type==='sex'&&c.value==='female'),`${spec.acupointId}: female alternative lost`);
 if(/굽혔|굽히면|폈|펴면|주먹|벌렸|모았/.test(source))assert.ok(spec.statements.some(s=>s.semanticTags.includes('POSTURE_CONDITION')),`${spec.acupointId}: posture semantics lost`);

 perPoint.push({id:spec.acupointId,sourceCharacters:source.length,reconstructedCharacters:reconstructed.length,statements:spec.statements.length,measurements:spec.measurements.length,fractions:spec.fractions.length,pointReferences:spec.pointReferences.length,lossless:true});
}

for(const point of acupoints)assert.ok(registry.specs.some(s=>s.acupointId===point.id),`${point.id}: missing location spec`);

const audit={
 schemaVersion:1,
 standardAcupointCount:acupoints.length,
 specificationCount:registry.specs.length,
 sourceCoverage:{missingAcupoints:[],duplicateAcupoints:[],all361Covered:true},
 losslessVerification:{
   exactSourceTextMatch:true,
   exactSha256Match:true,
   contiguousSpanCoverage:true,
   exactReconstruction:true,
   measurementTokensPreserved:true,
   fractionTokensPreserved:true,
   referencedAcupointTokensPreserved:true,
   conditionalSexSemanticsPreserved:true,
   postureSemanticsPreserved:true,
   lossyTransformationCount:0,
   uncoveredCharacterCount:0
 },
 counts:{statementCount,measurementCount,fractionCount,pointReferenceCount,unspecifiedRegionCount},
 perPoint
};
fs.writeFileSync(new URL('public/knowledge/acupoint-location-specs-audit.json',root),JSON.stringify(audit,null,2)+'\n');
console.log(JSON.stringify(audit.losslessVerification,null,2));
console.log(`Verified ${registry.specs.length}/361 acupoint location specifications with exact lossless reconstruction.`);
console.log(`Statements=${statementCount}, measurements=${measurementCount}, fractions=${fractionCount}, pointRefs=${pointReferenceCount}, unspecifiedRegions=${unspecifiedRegionCount}`);
