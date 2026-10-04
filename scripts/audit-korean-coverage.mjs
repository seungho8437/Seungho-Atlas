import fs from 'node:fs';

const modelBase=new URL('../public/models/',import.meta.url);
const knowledgeBase=new URL('../public/knowledge/',import.meta.url);
const atlas=JSON.parse(fs.readFileSync(new URL('atlas.json',modelBase),'utf8'));
const anatomyKo=JSON.parse(fs.readFileSync(new URL('anatomy-ko.json',knowledgeBase),'utf8'));

const counts={verified:0,derived:0,'review-needed':0,missing:0};
const missing=[];
for(const concept of atlas.concepts){
  const entry=anatomyKo[concept.id];
  if(!entry){counts.missing++;missing.push({id:concept.id,name:concept.name});continue;}
  counts[entry.status??'verified']=(counts[entry.status??'verified']??0)+1;
}
const localized=atlas.concepts.length-counts.missing;
const pct=(localized/atlas.concepts.length*100).toFixed(1);
console.log(`Korean anatomy coverage: ${localized}/${atlas.concepts.length} (${pct}%)`);
console.log(JSON.stringify(counts,null,2));
if(missing.length){
  console.log('First 40 missing concepts:');
  for(const item of missing.slice(0,40))console.log(`- ${item.id}: ${item.name}`);
}
