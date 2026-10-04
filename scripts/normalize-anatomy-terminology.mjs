import fs from 'node:fs';
import assert from 'node:assert/strict';

const root=new URL('../',import.meta.url);
const knowledge=new URL('public/knowledge/',root);
const read=name=>JSON.parse(fs.readFileSync(new URL(name,knowledge),'utf8'));
const write=(name,data)=>fs.writeFileSync(new URL(name,knowledge),JSON.stringify(data,null,2)+'\n');

const anatomy=read('anatomy-ko.json');
const kaaAudit=read('kaa-nameko-audit.json');

assert.equal(Object.keys(anatomy).length,3432,'Expected exactly 3,432 anatomy localization records');

const norm=s=>String(s??'').trim().toLowerCase().replace(/[‐‑–—]/g,'-').replace(/\s+/g,' ');
const byEnglish=new Map(Object.entries(anatomy).map(([id,v])=>[norm(v.sourceNameEn),{id,...v}]));
const sourceBacked=new Set(['direct-verified','derived-from-KAA-component']);
const changed=[];
const protectedDirect=new Set();

// Rule 1: direct PDF-verified Korean-English pairs are authoritative.
for(const [id,record] of Object.entries(kaaAudit.records??{})){
  if(record.result!=='direct-verified')continue;
  protectedDirect.add(id);
  const entry=anatomy[id];
  if(!entry)continue;
  assert.equal(norm(entry.sourceNameEn),norm(record.sourceNameEn),id+': direct English source drift');
  if(entry.nameKo!==record.nameKo){
    changed.push({id,field:'nameKo',from:entry.nameKo,to:record.nameKo,rule:'KAA-direct'});
    entry.nameKo=record.nameKo;
  }
  entry.nameKoVerification='direct-KAA';
  entry.nameKoSourceIds=['KAA_TERMINOLOGY_6'];
  if(record.pages?.length)entry.nameKoSourcePages=record.pages;
}

// Rule 2: only a leading right/left token may be inherited automatically,
// and only when the exact remaining English phrase exists as a standalone,
// KAA-supported base concept. Nested laterality is deliberately excluded.
let lateralCandidates=0;
for(const [id,entry] of Object.entries(anatomy)){
  if(protectedDirect.has(id)||entry.status==='verified')continue;
  const m=String(entry.sourceNameEn??'').match(/^(right|left)\s+(.+)$/i);
  if(!m||/\b(?:right|left)\b/i.test(m[2]))continue;
  const base=byEnglish.get(norm(m[2]));
  if(!base||!sourceBacked.has(kaaAudit.records?.[base.id]?.result))continue;
  lateralCandidates++;

  const expected=(m[1].toLowerCase()==='right'?'오른':'왼')+base.nameKo;
  if(entry.nameKo!==expected){
    changed.push({id,field:'nameKo',from:entry.nameKo,to:expected,rule:'KAA-safe-lateral-base',baseId:base.id});
    entry.nameKo=expected;
  }
  entry.nameKoVerification='derived-from-KAA-lateral-base';
  entry.nameKoSourceIds=['KAA_TERMINOLOGY_6'];
  const pages=kaaAudit.records?.[base.id]?.pages;
  if(pages?.length)entry.nameKoSourcePages=pages;
  entry.terminologyBaseId=base.id;

  const rec=kaaAudit.records[id]??{sourceNameEn:entry.sourceNameEn};
  rec.sourceNameEn=entry.sourceNameEn;
  rec.nameKo=entry.nameKo;
  rec.result='derived-from-KAA-lateral-base';
  rec.baseId=base.id;
  rec.note='Deterministic Korean-name inheritance from an exact KAA-supported English base concept: right/left + base English -> 오른/왼 + base Korean.';
  if(pages?.length)rec.pages=pages;
  kaaAudit.records[id]=rec;
}

// Rule 3: do not rewrite English. BodyParts3D/FMA sourceNameEn is the identity
// key; this pass only validates/matches it to KAA-supported Korean terminology.
for(const [id,entry] of Object.entries(anatomy)){
  const rec=kaaAudit.records?.[id];
  if(rec?.sourceNameEn&&norm(rec.sourceNameEn)!==norm(entry.sourceNameEn)){
    throw new Error(id+': sourceNameEn drift between atlas localization and KAA audit record');
  }
}

const directVerified=Object.values(kaaAudit.records??{}).filter(r=>r.result==='direct-verified').length;
const componentDerived=Object.values(kaaAudit.records??{}).filter(r=>r.result==='derived-from-KAA-component').length;
const lateralDerived=Object.values(kaaAudit.records??{}).filter(r=>r.result==='derived-from-KAA-lateral-base').length;
const unresolved=Object.values(kaaAudit.records??{}).filter(r=>r.result==='not-directly-listed-in-KAA-PDF').length;

kaaAudit.sourceId='KAA_TERMINOLOGY_6';
kaaAudit.sourceDescription='User-provided 218-page anatomical terminology PDF (Korean-English-Latin tables); this audit uses only the Korean and English columns.';
kaaAudit.scope='All 3,432 atlas concepts: direct Korean-English pairs where the PDF lists the term, plus deterministic right/left derivation only from exact KAA-supported base concepts.';
kaaAudit.method=[
  'Preserve BodyParts3D/FMA sourceNameEn as the immutable English identity.',
  'Use direct KAA Korean-English matches as authoritative for nameKo.',
  'Allow automatic laterality only for ^(right|left) + exact standalone base English concept with direct/component KAA support.',
  'Derive Korean laterality as 오른/왼 + the KAA-supported base Korean name.',
  'Exclude nested laterality phrases from automatic rewriting.',
  'Do not modify or claim verification of legacyKo or hanja in this Korean-English normalization pass.'
];
kaaAudit.summary={
  total:Object.keys(anatomy).length,
  directVerified,
  derivedFromKaaComponent:componentDerived,
  derivedFromKaaLateralBase:lateralDerived,
  notDirectlyListed:unresolved,
  safeLateralCandidates:lateralCandidates
};

const hard=[];
for(const [id,r] of Object.entries(kaaAudit.records??{})){
  const entry=anatomy[id];
  if(!entry){hard.push({id,type:'missing-anatomy-record'});continue;}
  if(norm(entry.sourceNameEn)!==norm(r.sourceNameEn))hard.push({id,type:'english-source-drift',expected:r.sourceNameEn,actual:entry.sourceNameEn});
  if(r.result==='direct-verified'&&entry.nameKo!==r.nameKo)hard.push({id,type:'direct-KAA-nameKo-drift',expected:r.nameKo,actual:entry.nameKo});
}
for(const [id,entry] of Object.entries(anatomy)){
  const m=String(entry.sourceNameEn??'').match(/^(right|left)\s+(.+)$/i);
  if(!m||/\b(?:right|left)\b/i.test(m[2]))continue;
  const base=byEnglish.get(norm(m[2]));
  if(!base||!sourceBacked.has(kaaAudit.records?.[base.id]?.result)||protectedDirect.has(id)||entry.status==='verified')continue;
  const expected=(m[1].toLowerCase()==='right'?'오른':'왼')+base.nameKo;
  if(entry.nameKo!==expected)hard.push({id,type:'safe-lateral-nameKo-drift',baseId:base.id,expected,actual:entry.nameKo});
  if(base.nameKo?.endsWith('근')&&!entry.nameKo?.endsWith('근'))hard.push({id,type:'muscle-head-loss',baseId:base.id,base:base.nameKo,actual:entry.nameKo});
}

const report={
  version:3,
  sourceId:'KAA_TERMINOLOGY_6',
  scope:'Korean-English matching only',
  totalRecords:Object.keys(anatomy).length,
  directVerified,
  derivedFromKaaComponent:componentDerived,
  derivedFromKaaLateralBase:lateralDerived,
  safeLateralCandidates:lateralCandidates,
  changedFieldCount:changed.length,
  changed,
  hardFailureCount:hard.length,
  hardFailures:hard
};

write('anatomy-ko.json',anatomy);
write('kaa-nameko-audit.json',kaaAudit);
write('anatomy-terminology-validation-audit.json',report);

console.log(JSON.stringify({
  totalRecords:report.totalRecords,
  directVerified,
  componentDerived,
  lateralDerived,
  lateralCandidates,
  changedFieldCount:changed.length,
  hardFailureCount:hard.length
},null,2));
if(hard.length)throw new Error('Korean-English terminology normalization left '+hard.length+' hard failure(s).');
