import fs from 'node:fs';
import assert from 'node:assert/strict';

const root=new URL('../',import.meta.url);
const knowledge=new URL('public/knowledge/',root);
const read=name=>JSON.parse(fs.readFileSync(new URL(name,knowledge),'utf8'));
const write=(name,data)=>fs.writeFileSync(new URL(name,knowledge),JSON.stringify(data,null,2)+'\n');

const anatomy=read('anatomy-ko.json');
const kaaAudit=read('kaa-nameko-audit.json');

assert.equal(Object.keys(anatomy).length,3432,'Expected exactly 3,432 anatomy localization records');

const byEnglish=new Map(Object.entries(anatomy).map(([id,v])=>[String(v.sourceNameEn??'').toLowerCase(),{id,...v}]));
const directResults=new Set(['direct-verified','derived-from-KAA-component']);
const changed=[];
const protectedDirect=new Set();

for(const [id,record] of Object.entries(kaaAudit.records??{})){
  if(record.result!=='direct-verified')continue;
  protectedDirect.add(id);
  const entry=anatomy[id];
  if(!entry)continue;
  if(entry.nameKo!==record.nameKo){
    changed.push({id,field:'nameKo',from:entry.nameKo,to:record.nameKo,rule:'KAA-direct'});
    entry.nameKo=record.nameKo;
  }
  entry.nameKoVerification='direct-KAA';
  entry.nameKoSourceIds=['KAA_TERMINOLOGY_6'];
  if(record.pages?.length)entry.nameKoSourcePages=record.pages;
}

const trustedBase=id=>{
  const r=kaaAudit.records?.[id];
  return !!r&&directResults.has(r.result);
};

let lateralCandidates=0,lateralApplied=0;
for(const [id,entry] of Object.entries(anatomy)){
  if(protectedDirect.has(id)||entry.status==='verified')continue;
  const m=String(entry.sourceNameEn??'').match(/^(right|left)\s+(.+)$/i);
  if(!m)continue;
  // A leading side word is safe to inherit only when the exact suffix is a
  // standalone concept and does not itself contain laterality. This avoids
  // corrupting nested phrases such as "right anterior branch ... left coronary".
  if(/\b(?:right|left)\b/i.test(m[2]))continue;
  const base=byEnglish.get(m[2].toLowerCase());
  if(!base||!trustedBase(base.id))continue;
  lateralCandidates++;
  const right=m[1].toLowerCase()==='right';
  const expected={
    nameKo:(right?'오른':'왼')+base.nameKo,
    legacyKo:base.legacyKo?(right?'우':'좌')+base.legacyKo:entry.legacyKo,
    hanja:base.hanja?(right?'右':'左')+base.hanja:entry.hanja
  };
  for(const [field,value] of Object.entries(expected)){
    if(value&&entry[field]!==value){
      changed.push({id,field,from:entry[field],to:value,rule:'KAA-safe-lateral-base',baseId:base.id});
      entry[field]=value;
    }
  }
  entry.nameKoVerification='derived-from-KAA-lateral-base';
  entry.nameKoSourceIds=['KAA_TERMINOLOGY_6'];
  const pages=kaaAudit.records?.[base.id]?.pages;
  if(pages?.length)entry.nameKoSourcePages=pages;
  entry.legacyKoVerification='structural-inheritance-from-base';
  entry.hanjaVerification='structural-inheritance-from-base';
  entry.terminologyBaseId=base.id;
  lateralApplied++;

  const rec=kaaAudit.records[id]??{sourceNameEn:entry.sourceNameEn};
  rec.nameKo=entry.nameKo;
  rec.result='derived-from-KAA-lateral-base';
  rec.baseId=base.id;
  rec.note='Deterministic laterality inheritance from an exact KAA-supported base concept; legacyKo/hanja are structurally inherited from the base because the KAA PDF does not provide those fields.';
  if(pages?.length)rec.pages=pages;
  kaaAudit.records[id]=rec;
}

const directVerified=Object.values(kaaAudit.records??{}).filter(r=>r.result==='direct-verified').length;
const componentDerived=Object.values(kaaAudit.records??{}).filter(r=>r.result==='derived-from-KAA-component').length;
const lateralDerived=Object.values(kaaAudit.records??{}).filter(r=>r.result==='derived-from-KAA-lateral-base').length;
const notDirect=Object.values(kaaAudit.records??{}).filter(r=>r.result==='not-directly-listed-in-KAA-PDF').length;

kaaAudit.auditedAt=new Date().toISOString();
kaaAudit.scope='Exhaustive comparison of all 3,432 atlas concept nameKo values against the KAA PDF; safe right/left derivatives are inherited only from exact KAA-supported base concepts. legacyKo and hanja are structurally inherited from the matched base and are not claimed as directly verified by this PDF.';
kaaAudit.method=[
  'Exact/normalized English term matching against Korean-English-Latin KAA table rows.',
  'Controlled normalization for singular/plural forms and FMA omission of terminal muscle/bone where previously source-confirmed.',
  'Safe laterality derivation only for ^(right|left) + exact standalone base concepts with KAA support; nested laterality phrases are excluded.',
  'Current Korean name is inherited as 오른/왼 + verified base Korean name.',
  'legacyKo and hanja are inherited as 우/좌 and 右/左 + base values only; this is structural consistency, not direct KAA-PDF verification.',
  'Direct-verified targets are protected from derivation overrides.'
];
kaaAudit.summary={
  total:Object.keys(anatomy).length,
  directVerified,
  derivedFromKaaComponent:componentDerived,
  derivedFromKaaLateralBase:lateralDerived,
  notDirectlyListed:notDirect,
  safeLateralCandidates:lateralCandidates,
  normalizationChanges:changed.length
};

const hard=[];
for(const [id,r] of Object.entries(kaaAudit.records??{})){
  if(r.result==='direct-verified'&&anatomy[id]?.nameKo!==r.nameKo)hard.push({id,type:'direct-drift',expected:r.nameKo,actual:anatomy[id]?.nameKo});
}
for(const [id,entry] of Object.entries(anatomy)){
  const m=String(entry.sourceNameEn??'').match(/^(right|left)\s+(.+)$/i);
  if(!m||/\b(?:right|left)\b/i.test(m[2]))continue;
  const base=byEnglish.get(m[2].toLowerCase());
  if(!base||!trustedBase(base.id)||protectedDirect.has(id)||entry.status==='verified')continue;
  const right=m[1].toLowerCase()==='right';
  const expectedKo=(right?'오른':'왼')+base.nameKo;
  const expectedLegacy=base.legacyKo?(right?'우':'좌')+base.legacyKo:null;
  const expectedHanja=base.hanja?(right?'右':'左')+base.hanja:null;
  if(entry.nameKo!==expectedKo)hard.push({id,type:'safe-lateral-nameKo-drift',baseId:base.id,expected:expectedKo,actual:entry.nameKo});
  if(expectedLegacy&&entry.legacyKo!==expectedLegacy)hard.push({id,type:'safe-lateral-legacy-drift',baseId:base.id,expected:expectedLegacy,actual:entry.legacyKo});
  if(expectedHanja&&entry.hanja!==expectedHanja)hard.push({id,type:'safe-lateral-hanja-drift',baseId:base.id,expected:expectedHanja,actual:entry.hanja});
  if(base.nameKo?.endsWith('근')&&!entry.nameKo?.endsWith('근'))hard.push({id,type:'muscle-head-loss',baseId:base.id});
  if(base.hanja?.endsWith('筋')&&!entry.hanja?.endsWith('筋'))hard.push({id,type:'muscle-hanja-head-loss',baseId:base.id});
}

const report={
  version:2,
  generatedAt:new Date().toISOString(),
  source:{
    id:'KAA_TERMINOLOGY_6',
    description:'User-provided 218-page anatomical terminology PDF (Korean-English-Latin tables)',
    note:'The PDF directly supports current Korean/English matching. legacyKo/hanja are not direct PDF columns and are only structurally inherited from matched base records.'
  },
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

console.log(JSON.stringify({totalRecords:report.totalRecords,directVerified,componentDerived,lateralDerived,lateralCandidates,changedFieldCount:changed.length,hardFailureCount:hard.length},null,2));
if(hard.length)throw new Error('Terminology normalization left '+hard.length+' hard failure(s).');
