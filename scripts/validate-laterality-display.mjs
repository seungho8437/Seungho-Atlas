import fs from 'node:fs';
import assert from 'node:assert/strict';
const localization=JSON.parse(fs.readFileSync('public/knowledge/anatomy-ko.json','utf8'));
const atlas=JSON.parse(fs.readFileSync('public/models/atlas.json','utf8'));
const policy=JSON.parse(fs.readFileSync('data/anatomy-laterality-display.json','utf8'));
const entries=policy.neutralized;
const allConcepts=new Set(atlas.concepts.map(x=>x.id));
const stripKo=(s,side)=>(s??'').replace(side==='left'?/^(왼쪽|왼|좌측|좌)\s*/:/^(오른쪽|오른|우측|우)\s*/,'');
const stripHan=(s,side)=>(s??'').replace(side==='left'?/^左/:/^右/,'');
assert.equal(Object.keys(localization).length,3432,'Canonical vocabulary must be unchanged');
assert.equal(Object.keys(entries).length,1216,'Display policy unexpectedly changed');
assert.equal(policy.source_commit,'061994eea8d0bc3eac9d942d3b81a94b254634f2');
const byName=new Map();
let nestedCount=0,prefixCount=0;
for(const [id,row] of Object.entries(entries)){
 const original=localization[id];
 assert.ok(original&&allConcepts.has(id),'Orphan FMA ID '+id);
 const sideWords=[...original.sourceNameEn.matchAll(/\b(left|right)\b/gi)];
 assert.equal(sideWords.length,1,'Source must have exactly one side word '+id);
 const match=sideWords[0],side=match[0].toLowerCase();
 assert.equal(side,row.side,'Incorrect side '+id);
 assert.equal(original.sourceNameEn.replace(/\b(left|right)\b\s*/i,'').trim().replace(/\s+/g,' ').toLowerCase(),row.en,'English base differs '+id);
 assert.ok(!/\b(left|right)\b/i.test(row.en),'Nested laterality remains '+id);
 assert.equal(stripKo(original.nameKo,row.side),row.ko,'Korean base differs '+id);
 assert.equal(stripHan(original.hanja,row.side),row.hanja,'Hanja base differs '+id);
 const key=row.en;
 if(!byName.has(key))byName.set(key,{});
 assert.ok(!byName.get(key)[row.side],'Duplicate side '+key);
 byName.get(key)[row.side]=id;
 if(match.index===0)prefixCount++;else nestedCount++;
}
assert.equal(byName.size,608,'Expected total 608 neutralized pairs');
for(const [base,sides] of byName)assert.ok(sides.left&&sides.right,'Unpaired '+base);
assert.equal(prefixCount,1024,'Baseline 512 pairs must remain');
assert.equal(nestedCount,192,'Added 96 nested-side pairs must remain');
for(const id of ['FMA7396','FMA7395','FMA7254','FMA7247','FMA71708','FMA71710','FMA3855','FMA3802']){
 assert.ok(!entries[id],'Protected essential sided structure changed: '+id);
}
const check=(id,side,label,hanja,english)=>{
 assert.deepEqual(entries[id],{side,ko:label,hanja,en:english},'Incorrect visible names '+id);
};
check('FMA37698','left','위팔세갈래근 가쪽갈래','上腕三頭筋外側頭','lateral head of triceps brachii');
check('FMA37697','right','위팔세갈래근 가쪽갈래','上腕三頭筋外側頭','lateral head of triceps brachii');
check('FMA37696','left','위팔세갈래근 안쪽갈래','上腕三頭筋內側頭','medial head of triceps brachii');
check('FMA37700','left','위팔세갈래근 긴갈래','上腕三頭筋長頭','long head of triceps brachii');
check('FMA4058','left','온목동맥','總頸動脈','common carotid artery');
check('FMA7205','left','콩팥','腎臟','kidney');
console.log('PASS: all 3432 canonical terms unchanged; 608 paired display names; 1216 side-specific FMA objects; 96 newly covered nested-side pairs; protected essential sides intact.');
