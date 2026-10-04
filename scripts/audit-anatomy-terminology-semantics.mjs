import fs from 'node:fs';
import assert from 'node:assert/strict';

const root=new URL('../',import.meta.url);
const knowledge=new URL('public/knowledge/',root);
const read=name=>JSON.parse(fs.readFileSync(new URL(name,knowledge),'utf8'));
const anatomy=read('anatomy-ko.json');
const kaaAudit=read('kaa-nameko-audit.json');

const ids=Object.keys(anatomy);
assert.equal(ids.length,3432,'Expected exactly 3,432 anatomy localization records');

const hard=[];
const review=[];
const directVerified=[];
const byEnglish=new Map(Object.entries(anatomy).map(([id,v])=>[String(v.sourceNameEn??'').toLowerCase(),{id,...v}]));

for(const [id,record] of Object.entries(kaaAudit.records??{})){
  if(record.result!=='direct-verified')continue;
  directVerified.push(id);
  const entry=anatomy[id];
  if(!entry){hard.push({id,type:'direct-source-missing-record'});continue;}
  if(entry.nameKo!==record.nameKo)hard.push({id,type:'direct-KAA-nameKo-drift',expected:record.nameKo,actual:entry.nameKo,pages:record.pages});
}

const trusted=id=>{
  const result=kaaAudit.records?.[id]?.result;
  return result==='direct-verified'||result==='derived-from-KAA-component'||anatomy[id]?.status==='verified';
};
const protectedTarget=id=>kaaAudit.records?.[id]?.result==='direct-verified'||anatomy[id]?.status==='verified';

let lateralityTotal=0,lateralityPaired=0,lateralityTrusted=0;
for(const [id,entry] of Object.entries(anatomy)){
  const en=String(entry.sourceNameEn??'');
  const match=en.match(/^(right|left)\s+(.+)$/i);
  if(!match)continue;
  lateralityTotal++;
  const side=match[1].toLowerCase(),baseEnglish=match[2];
  const koPrefix=side==='right'?'오른':'왼';
  const legacyPrefix=side==='right'?'우':'좌';
  const hanjaPrefix=side==='right'?'右':'左';
  if(!String(entry.nameKo??'').startsWith(koPrefix))hard.push({id,type:'laterality-nameKo-marker-missing',side,actual:entry.nameKo});
  if(!String(entry.legacyKo??'').startsWith(legacyPrefix))hard.push({id,type:'laterality-legacyKo-marker-missing',side,actual:entry.legacyKo});
  if(!String(entry.hanja??'').startsWith(hanjaPrefix))hard.push({id,type:'laterality-hanja-marker-missing',side,actual:entry.hanja});

  if(/\b(?:right|left)\b/i.test(baseEnglish)){
    review.push({id,type:'nested-laterality',sourceNameEn:en});
    continue;
  }
  const base=byEnglish.get(baseEnglish.toLowerCase());
  if(!base){
    review.push({id,type:'no-exact-base-concept',sourceNameEn:en});
    continue;
  }
  lateralityPaired++;

  // Morphologic safety net: a side-specific variant may not lose a core class
  // suffix that is present in its exact base concept.
  for(const [field,suffixes] of [
    ['nameKo',['근','근육','뼈','동맥','정맥','신경','인대','연골','샘','관','관절','근막']],
    ['hanja',['筋','骨','動脈','靜脈','神經','靱帶','軟骨','腺','管','關節','筋膜']]
  ]){
    const baseValue=String(base[field]??''),value=String(entry[field]??'');
    const suffix=suffixes.find(s=>baseValue.endsWith(s));
    if(suffix&&!value.endsWith(suffix)&&!protectedTarget(id))hard.push({id,type:'laterality-core-suffix-loss',field,suffix,baseId:base.id,base:baseValue,actual:value});
  }

  if(!trusted(base.id)){
    review.push({id,type:'untrusted-base',baseId:base.id,sourceNameEn:en});
    continue;
  }
  lateralityTrusted++;
  if(protectedTarget(id))continue;

  const expected={
    nameKo:koPrefix+base.nameKo,
    legacyKo:legacyPrefix+base.legacyKo,
    hanja:hanjaPrefix+base.hanja
  };
  for(const [field,value] of Object.entries(expected)){
    if(entry[field]!==value)hard.push({id,type:'laterality-base-drift',field,baseId:base.id,expected:value,actual:entry[field]});
  }
}

const report={
  version:1,
  generatedAt:new Date().toISOString(),
  totalRecords:ids.length,
  directVerifiedCount:directVerified.length,
  laterality:{total:lateralityTotal,exactBasePaired:lateralityPaired,trustedBase:lateralityTrusted},
  hardFailureCount:hard.length,
  reviewQueueCount:review.length,
  hardFailures:hard,
  reviewQueue:review
};

if(process.argv.includes('--write'))fs.writeFileSync(new URL('anatomy-terminology-validation-audit.json',knowledge),JSON.stringify(report,null,2)+'\n');

console.log(JSON.stringify({
  totalRecords:report.totalRecords,
  directVerifiedCount:report.directVerifiedCount,
  laterality:report.laterality,
  hardFailureCount:hard.length,
  reviewQueueCount:review.length
},null,2));

if(hard.length){
  console.error('First semantic terminology failures:');
  for(const item of hard.slice(0,80))console.error(JSON.stringify(item));
  throw new Error(`Anatomy terminology semantic audit failed with ${hard.length} hard failure(s).`);
}
