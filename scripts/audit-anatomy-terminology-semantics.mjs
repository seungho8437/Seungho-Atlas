import fs from 'node:fs';
import assert from 'node:assert/strict';

const root=new URL('../',import.meta.url);
const knowledge=new URL('public/knowledge/',root);
const read=name=>JSON.parse(fs.readFileSync(new URL(name,knowledge),'utf8'));
const anatomy=read('anatomy-ko.json');
const kaaAudit=read('kaa-nameko-audit.json');

const norm=s=>String(s??'').trim().toLowerCase().replace(/[‐‑–—]/g,'-').replace(/\s+/g,' ');
const ids=Object.keys(anatomy);
assert.equal(ids.length,3432,'Expected exactly 3,432 anatomy localization records');

const hard=[];
const review=[];
const byEnglish=new Map(Object.entries(anatomy).map(([id,v])=>[norm(v.sourceNameEn),{id,...v}]));
const sourceBacked=new Set(['direct-verified','derived-from-KAA-component']);

// Direct source rows are immutable Korean-English pairs.
let directVerified=0;
for(const [id,record] of Object.entries(kaaAudit.records??{})){
  const entry=anatomy[id];
  if(!entry){hard.push({id,type:'missing-anatomy-record'});continue;}
  if(norm(record.sourceNameEn)!==norm(entry.sourceNameEn))hard.push({id,type:'english-source-drift',expected:record.sourceNameEn,actual:entry.sourceNameEn});
  if(record.result==='direct-verified'){
    directVerified++;
    if(entry.nameKo!==record.nameKo)hard.push({id,type:'direct-KAA-nameKo-drift',expected:record.nameKo,actual:entry.nameKo,pages:record.pages});
  }
}

// Safe deterministic laterality: exact base concept only.
let lateralTotal=0,lateralSafe=0;
for(const [id,entry] of Object.entries(anatomy)){
  const m=String(entry.sourceNameEn??'').match(/^(right|left)\s+(.+)$/i);
  if(!m)continue;
  lateralTotal++;
  if(/\b(?:right|left)\b/i.test(m[2])){review.push({id,type:'nested-laterality',sourceNameEn:entry.sourceNameEn});continue;}
  const base=byEnglish.get(norm(m[2]));
  if(!base){review.push({id,type:'no-exact-base-concept',sourceNameEn:entry.sourceNameEn});continue;}
  if(!sourceBacked.has(kaaAudit.records?.[base.id]?.result)){review.push({id,type:'base-not-KAA-backed',baseId:base.id,sourceNameEn:entry.sourceNameEn});continue;}
  lateralSafe++;
  const expected=(m[1].toLowerCase()==='right'?'오른쪽 ':'왼쪽 ')+base.nameKo;
  if(entry.nameKo!==expected)hard.push({id,type:'safe-lateral-nameKo-drift',baseId:base.id,expected,actual:entry.nameKo});
  if(base.nameKo?.endsWith('근')&&!entry.nameKo?.endsWith('근'))hard.push({id,type:'muscle-head-loss',baseId:base.id,base:base.nameKo,actual:entry.nameKo});
  const prefix=m[1].toLowerCase()==='right'?'오른쪽 ':'왼쪽 ';
  if(!entry.nameKo.startsWith(prefix))hard.push({id,type:'laterality-spacing-drift',baseId:base.id,expectedPrefix:prefix,actual:entry.nameKo});
}

console.log(JSON.stringify({
  totalRecords:ids.length,
  directVerified,
  lateral:{total:lateralTotal,safeKaaBacked:lateralSafe},
  hardFailureCount:hard.length,
  reviewQueueCount:review.length
},null,2));

if(hard.length){
  console.error('First Korean-English terminology failures:');
  for(const item of hard.slice(0,80))console.error(JSON.stringify(item));
  throw new Error('Korean-English semantic terminology audit failed with '+hard.length+' hard failure(s).');
}
