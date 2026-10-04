import fs from 'node:fs';
import assert from 'node:assert/strict';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const specs=read('public/knowledge/acupoint-location-specs.json').specs;
const entities=read('public/knowledge/acupoint-entity-resolution.json').records;
const frames=read('public/knowledge/acupoint-measurement-frames.json').records;
const atoms=read('public/knowledge/acupoint-constraint-atoms.json').records;
const plans=read('public/knowledge/acupoint-solver-plans.json').records;
const audit=read('public/knowledge/acupoint-resolution-audit.json');

const by=(arr)=>new Map(arr.map(x=>[x.acupointId,x]));
const E=by(entities),F=by(frames),A=by(atoms),P=by(plans);

assert.equal(specs.length,361);
for(const arr of [entities,frames,atoms,plans]){
 assert.equal(arr.length,361,'Every resolution layer must cover all 361 points');
 assert.equal(new Set(arr.map(x=>x.acupointId)).size,361,'Duplicate acupoint in resolution layer');
}
for(const spec of specs){
 const e=E.get(spec.acupointId),f=F.get(spec.acupointId),a=A.get(spec.acupointId),p=P.get(spec.acupointId);
 assert.ok(e&&f&&a&&p,`${spec.acupointId}: missing resolution layer`);
 assert.equal(f.frames.length,spec.measurements.length,`${spec.acupointId}: measurement/frame count mismatch`);
 assert.ok(a.atoms.some(x=>x.type==='VERBATIM_STATEMENT'),`${spec.acupointId}: missing verbatim atom`);
 for(const s of spec.statements)assert.ok(a.atoms.some(x=>x.type==='VERBATIM_STATEMENT'&&x.statementId===s.id&&x.sourceText===s.text),`${spec.acupointId}: statement lost during atomization`);
 for(const m of spec.measurements){
   const mf=f.frames.find(x=>x.sourceSpan.start===m.start&&x.sourceSpan.end===m.end);
   assert.ok(mf,`${spec.acupointId}: measurement frame span mismatch`);
   assert.equal(mf.value,m.value);assert.equal(mf.unit,m.unit);
   if(m.unit==='B-cun')assert.notEqual(mf.path,'global-body-height',`${spec.acupointId}: forbidden global B-cun frame`);
 }
 assert.equal(p.canonicalSurface,'body-surface',`${spec.acupointId}: canonical surface drift`);
 assert.ok(p.executionOrder.at(-1)==='independent-constraint-validation',`${spec.acupointId}: independent validation must be final stage`);
 assert.equal(p.hardValidationRule,'all hard constraints must pass before status=validated');
 if(p.status==='solver-ready')assert.equal(p.blockers.length,0,`${spec.acupointId}: solver-ready plan has blockers`);
 else assert.ok(p.blockers.length>0,`${spec.acupointId}: review-required plan lacks blockers`);
}
assert.equal(audit.standardAcupointCount,361);
assert.equal(audit.coverage.all361Covered,true);
assert.equal(audit.invariants.canonicalSurfaceBodySurface,true);
assert.equal(audit.invariants.everySpecHasVerbatimAtom,true);
assert.equal(audit.invariants.everyMeasurementHasFrame,true);
assert.equal(audit.invariants.noGlobalBodyHeightCun,true);
assert.equal(audit.invariants.hardConstraintsGateValidation,true);

console.log(JSON.stringify(audit,null,2));
console.log('Verified entity resolution -> local measurement frames -> constraint atomization -> solver plans for all 361 acupoints.');
