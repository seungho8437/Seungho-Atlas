import fs from 'node:fs';
import assert from 'node:assert/strict';

const modelBase=new URL('../public/models/',import.meta.url);
const knowledgeBase=new URL('../public/knowledge/',import.meta.url);
const atlas=JSON.parse(fs.readFileSync(new URL('atlas.json',modelBase),'utf8'));
const anatomyKo=JSON.parse(fs.readFileSync(new URL('anatomy-ko.json',knowledgeBase),'utf8'));

const counts={verified:0,derived:0,'review-needed':0,missing:0};
const issues=[];
const atlasIds=new Set(atlas.concepts.map(concept=>concept.id));

for(const concept of atlas.concepts){
  const entry=anatomyKo[concept.id];
  if(!entry){counts.missing++;issues.push(`${concept.id}: missing record`);continue;}
  counts[entry.status??'verified']=(counts[entry.status??'verified']??0)+1;
  if(entry.sourceNameEn!==concept.name)issues.push(`${concept.id}: sourceNameEn drift`);
  for(const field of ['nameKo','legacyKo','hanja']){
    if(typeof entry[field]!=='string'||!entry[field].trim())issues.push(`${concept.id}: missing ${field}`);
  }
  if(entry.status==='review-needed')issues.push(`${concept.id}: unresolved review-needed status`);
}
for(const id of Object.keys(anatomyKo))if(!atlasIds.has(id))issues.push(`${id}: orphan localization record`);

const resolved=atlas.concepts.length-counts.missing-counts['review-needed'];
const pct=(resolved/atlas.concepts.length*100).toFixed(1);
console.log(`Korean anatomy resolved coverage: ${resolved}/${atlas.concepts.length} (${pct}%)`);
console.log(JSON.stringify(counts,null,2));
if(issues.length){
  console.log('First 80 coverage issues:');
  for(const issue of issues.slice(0,80))console.log(`- ${issue}`);
}
assert.equal(Object.keys(anatomyKo).length,atlas.concepts.length,'Localization record count must equal atlas concept count');
assert.equal(counts.missing,0,'No atlas concept may be missing localization');
assert.equal(counts['review-needed'],0,'No localization may remain review-needed');
assert.equal(issues.length,0,'Korean localization audit found integrity issues');
