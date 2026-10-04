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
  FMA23082:{nameKo:'목돌림근',pages:[55],result:'derived-from-KAA-component',evidence:'KAA: Rotatores cervicis muscles'},
  FMA22431:{nameKo:'가쪽넓은근',legacyKo:'외측광근',hanja:'外側廣筋',pages:[63],result:'direct-verified',evidence:'KAA: Vastus lateralis muscle'},
  FMA22653:{nameKo:'머리널판근',legacyKo:'두판상근',hanja:'頭板狀筋',pages:[55],result:'direct-verified',evidence:'KAA: Splenius capitis muscle'},
  FMA22702:{nameKo:'허리엉덩갈비근',legacyKo:'요장늑근',hanja:'腰腸肋筋',pages:[55],result:'direct-verified',evidence:'KAA: Iliocostalis lumborum muscle'},
  FMA22703:{nameKo:'등엉덩갈비근',legacyKo:'흉장늑근',hanja:'胸腸肋筋',pages:[55],result:'direct-verified',evidence:'KAA: Iliocostalis thoracis muscle'},
  FMA22704:{nameKo:'목엉덩갈비근',legacyKo:'경장늑근',hanja:'頸腸肋筋',pages:[55],result:'direct-verified',evidence:'KAA: Iliocostalis cervicis muscle'},
  FMA22709:{nameKo:'등가장긴근',legacyKo:'흉최장근',hanja:'胸最長筋',pages:[55],result:'direct-verified',evidence:'KAA: Longissimus thoracis muscle'},
  FMA22711:{nameKo:'목가장긴근',legacyKo:'경최장근',hanja:'頸最長筋',pages:[55],result:'direct-verified',evidence:'KAA: Longissimus cervicis muscle'},
  FMA22714:{nameKo:'머리가장긴근',legacyKo:'두최장근',hanja:'頭最長筋',pages:[55],result:'direct-verified',evidence:'KAA: Longissimus capitis muscle'},
  FMA22828:{nameKo:'등반가시근',legacyKo:'흉반극근',hanja:'胸半棘筋',pages:[55],result:'direct-verified',evidence:'KAA: Semispinalis thoracis muscle'},
  FMA22829:{nameKo:'목반가시근',legacyKo:'경반극근',hanja:'頸半棘筋',pages:[55],result:'direct-verified',evidence:'KAA: Semispinalis cervicis muscle'},
  FMA22830:{nameKo:'머리반가시근',legacyKo:'두반극근',hanja:'頭半棘筋',pages:[55],result:'direct-verified',evidence:'KAA: Semispinalis capitis muscle'},
  FMA9625:{nameKo:'붓목뿔근',legacyKo:'경상설골근',hanja:'莖狀舌骨筋',pages:[54],result:'direct-verified',evidence:'KAA: Stylohyoid muscle'},
  FMA13344:{nameKo:'방패목뿔근',legacyKo:'갑상설골근',hanja:'甲狀舌骨筋',pages:[54],result:'direct-verified',evidence:'KAA: Thyrohyoid muscle'},
  FMA50735:{nameKo:'간문맥',legacyKo:'간문맥',hanja:'肝門脈',pages:[140],result:'direct-verified',evidence:'KAA: Hepatic portal vein'},
  FMA265130:{nameKo:'기도',legacyKo:'기도',hanja:'氣道',pages:[83],result:'direct-verified',evidence:'KAA: 기도; 숨길 — Respiratory tract'},
  FMA32514:{nameKo:'척주앞근육',pages:[53],result:'direct-verified',evidence:'KAA: Prevertebral muscles'},
  FMA49143:{nameKo:'가쪽곧은근제한인대',legacyKo:'외직근제한인대',hanja:'外直筋制限靭帶',pages:[207],result:'direct-verified',evidence:'KAA: Check ligament of lateral rectus muscle'}
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
