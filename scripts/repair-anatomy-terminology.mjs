import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const knowledge=new URL('public/knowledge/',root);
const read=name=>JSON.parse(fs.readFileSync(new URL(name,knowledge),'utf8'));
const write=(name,value)=>fs.writeFileSync(new URL(name,knowledge),JSON.stringify(value,null,2)+'\n');

const anatomy=read('anatomy-ko.json');
const kaaAudit=read('kaa-nameko-audit.json');

// These rows were re-checked against the user-provided Korean Association of
// Anatomists terminology PDF. The atlas/FMA English headword is sometimes
// shortened or an alias, so exact-headword matching alone previously missed it.
const sourceConfirmedBases={
  FMA13335:{nameKo:'배바깥빗근',pages:[57],result:'derived-from-KAA-component',evidence:'KAA: External abdominal oblique muscle'},
  FMA22310:{nameKo:'엉덩근',pages:[62],result:'direct-verified',evidence:'KAA: Iliacus muscle'},
  FMA18060:{nameKo:'큰허리근',pages:[62],result:'direct-verified',evidence:'KAA: Psoas major muscle'},
  FMA22542:{nameKo:'가자미근',pages:[64],result:'direct-verified',evidence:'KAA: Soleus muscle'},
  FMA22681:{nameKo:'목널판근',pages:[55],result:'direct-verified',evidence:'KAA: Splenius cervicis muscle'},
  FMA22765:{nameKo:'등가시근',pages:[55],result:'direct-verified',evidence:'KAA: Spinalis thoracis muscle'},
  FMA22846:{nameKo:'등가시사이근',pages:[55],result:'derived-from-KAA-component',evidence:'KAA: Interspinales thoracis muscles'},
  FMA23084:{nameKo:'허리돌림근',pages:[55],result:'derived-from-KAA-component',evidence:'KAA: Rotatores lumborum muscles'},
  FMA37452:{nameKo:'발바닥네모근',legacyKo:'족저방형근',hanja:'足底方形筋',pages:[64],result:'derived-from-KAA-component',evidence:'KAA: Quadratus plantae muscle; Latin alias M. flexor accessorius'},
  FMA22430:{nameKo:'넙다리곧은근',pages:[63],result:'direct-verified',evidence:'KAA: Rectus femoris muscle'},
  FMA22432:{nameKo:'안쪽넓은근',pages:[63],result:'direct-verified',evidence:'KAA: Vastus medialis muscle'},
  FMA22433:{nameKo:'중간넓은근',pages:[63],result:'direct-verified',evidence:'KAA: Vastus intermedius muscle'},
  FMA19090:{nameKo:'두덩꼬리근',pages:[59],result:'direct-verified',evidence:'KAA: Pubococcygeus muscle'},
  FMA19091:{nameKo:'두덩곧창자근',pages:[59],result:'direct-verified',evidence:'KAA: Puborectalis muscle'},
  FMA19092:{nameKo:'엉덩꼬리근',pages:[59],result:'direct-verified',evidence:'KAA: Iliococcygeus muscle'},
  FMA46576:{nameKo:'뒤반지모뿔근',pages:[86],result:'direct-verified',evidence:'KAA: Posterior cricoarytenoid muscle'},
  FMA46579:{nameKo:'가쪽반지모뿔근',pages:[86],result:'direct-verified',evidence:'KAA: Lateral cricoarytenoid muscle'},
  FMA46588:{nameKo:'방패모뿔근',pages:[86],result:'direct-verified',evidence:'KAA: Thyroarytenoid muscle'},
  FMA46621:{nameKo:'위인두수축근',pages:[74],result:'direct-verified',evidence:'KAA: Superior pharyngeal constrictor muscle'},
  FMA46622:{nameKo:'중간인두수축근',pages:[75],result:'direct-verified',evidence:'KAA: Middle pharyngeal constrictor muscle'},
  FMA46623:{nameKo:'아래인두수축근',pages:[75],result:'direct-verified',evidence:'KAA: Inferior pharyngeal constrictor muscle'},
  FMA23082:{nameKo:'목돌림근',pages:[55],result:'derived-from-KAA-component',evidence:'KAA: Rotatores cervicis muscles'}
};

const changes=[];
for(const [id,fix] of Object.entries(sourceConfirmedBases)){
  const entry=anatomy[id];
  if(!entry)throw new Error(`Missing source-confirmed anatomy concept ${id}`);
  for(const field of ['nameKo','legacyKo','hanja']){
    if(fix[field]&&entry[field]!==fix[field]){
      changes.push({id,field,before:entry[field],after:fix[field],reason:'KAA-base-correction'});
      entry[field]=fix[field];
    }
  }
  const rec=kaaAudit.records[id]??={sourceNameEn:entry.sourceNameEn};
  rec.nameKo=fix.nameKo;
  rec.result=fix.result;
  rec.pages=fix.pages;
  rec.note=`${fix.evidence}; manually re-checked against the source PDF during semantic re-audit.`;
  kaaAudit.records[id]=rec;
}

const byEnglish=new Map(Object.entries(anatomy).map(([id,v])=>[String(v.sourceNameEn??'').toLowerCase(),{id,...v}]));
const baseTrusted=id=>{
  const result=kaaAudit.records?.[id]?.result;
  return result==='direct-verified'||result==='derived-from-KAA-component'||anatomy[id]?.status==='verified';
};
const targetProtected=id=>kaaAudit.records?.[id]?.result==='direct-verified'||anatomy[id]?.status==='verified';

let pairedLaterality=0,canonicalizedLaterality=0;
for(const [id,entry] of Object.entries(anatomy)){
  const match=String(entry.sourceNameEn??'').match(/^(right|left)\s+(.+)$/i);
  if(!match)continue;
  const side=match[1].toLowerCase();
  const baseEnglish=match[2];
  if(/\b(?:right|left)\b/i.test(baseEnglish))continue; // nested laterality is not safe to synthesize
  const base=byEnglish.get(baseEnglish.toLowerCase());
  if(!base||!baseTrusted(base.id)||targetProtected(id))continue;
  pairedLaterality++;
  const expected={
    nameKo:(side==='right'?'오른':'왼')+base.nameKo,
    legacyKo:(side==='right'?'우':'좌')+base.legacyKo,
    hanja:(side==='right'?'右':'左')+base.hanja
  };
  let changed=false;
  for(const field of Object.keys(expected)){
    if(entry[field]!==expected[field]){
      changes.push({id,field,before:entry[field],after:expected[field],reason:`laterality-from-base:${base.id}`});
      entry[field]=expected[field];changed=true;
    }
  }
  if(changed)canonicalizedLaterality++;
}

const semanticAudit={
  version:1,
  generatedAt:new Date().toISOString(),
  source:'대한해부학회 해부학용어 제6판 + atlas/FMA semantic inheritance',
  totalRecords:Object.keys(anatomy).length,
  sourceConfirmedBaseCount:Object.keys(sourceConfirmedBases).length,
  pairedLaterality,
  canonicalizedLaterality,
  fieldChangeCount:changes.length,
  changes,
  rules:{
    directVerifiedTargetsProtected:true,
    verifiedTargetsProtected:true,
    nestedLateralityAutoRepair:false,
    lateralityDerivedOnlyFromTrustedExactBase:true,
    nameKoPrefix:{right:'오른',left:'왼'},
    legacyKoPrefix:{right:'우',left:'좌'},
    hanjaPrefix:{right:'右',left:'左'}
  }
};

kaaAudit.summary=kaaAudit.summary??{};
kaaAudit.summary.semanticReauditAt=semanticAudit.generatedAt;
kaaAudit.summary.semanticReauditSourceConfirmedBases=Object.keys(sourceConfirmedBases).length;

write('anatomy-ko.json',anatomy);
write('kaa-nameko-audit.json',kaaAudit);
write('anatomy-terminology-semantic-audit.json',semanticAudit);

console.log(JSON.stringify({
  totalRecords:semanticAudit.totalRecords,
  sourceConfirmedBaseCount:semanticAudit.sourceConfirmedBaseCount,
  pairedLaterality,
  canonicalizedLaterality,
  fieldChangeCount:changes.length
},null,2));
