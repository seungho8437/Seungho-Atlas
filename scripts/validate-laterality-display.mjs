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
assert.equal(Object.keys(entries).length,1024,'Approved display-only policy changed unexpectedly');
assert.equal(policy.source_commit,'061994eea8d0bc3eac9d942d3b81a94b254634f2');
const byName=new Map();
for(const [id,row] of Object.entries(entries)){
  const original=localization[id];
  assert.ok(original&&allConcepts.has(id),'Orphan FMA ID '+id);
  const m=original.sourceNameEn.match(/^(left|right)\s+(.+)$/i);
  assert.ok(m,'No source laterality '+id);
  assert.equal(m[1].toLowerCase(),row.side,'Incorrect side '+id);
  assert.equal(m[2].toLowerCase(),row.en,'English base differs '+id);
  assert.ok(!/\b(left|right)\b/i.test(row.en),'Nested laterality '+id);
  assert.equal(stripKo(original.nameKo,row.side),row.ko,'Korean base differs '+id);
  assert.equal(stripHan(original.hanja,row.side),row.hanja,'Hanja base differs '+id);
  const key=row.en;
  if(!byName.has(key))byName.set(key,{});
  assert.ok(!byName.get(key)[row.side],'Duplicate side '+key);
  byName.get(key)[row.side]=id;
}
assert.equal(byName.size,512);
for(const [base,sides] of byName)assert.ok(sides.left&&sides.right,'Unpaired '+base);
for(const id of ['FMA7396','FMA7395','FMA7254','FMA7247','FMA71708','FMA71710']){
  assert.ok(!entries[id],'Protected laterality should remain explicit: '+id);
}
assert.equal(entries.FMA4058.ko,'온목동맥');
assert.equal(entries.FMA3941.ko,'온목동맥');
assert.equal(entries.FMA7205.en,'kidney');
assert.equal(entries.FMA7185.hanja,'上肢');
console.log('PASS: 3432 canonical FMA records untouched; 512 reversible neutralized pairs; 1024 side-safe display records; protected structures retained.');
