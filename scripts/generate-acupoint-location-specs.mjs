import fs from 'node:fs';
import crypto from 'node:crypto';

const root=new URL('../',import.meta.url);
const readJson=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const acupoints=readJson('public/knowledge/acupoints.json');

const sha256=s=>crypto.createHash('sha256').update(s,'utf8').digest('hex');

const REGION_RULES=[
 ['forearm',/아래팔|전완/],
 ['upper-arm',/위팔|상완|겨드랑/],
 ['elbow',/팔꿈치|팔오금/],
 ['wrist-hand',/손목|손바닥|손등|손가락|손허리|손톱|엄지|집게손가락|새끼손가락/],
 ['ankle-foot',/발목|복사|발등|발바닥|발가락|발허리|발꿈치|발톱/],
 ['leg',/아래다리|하퇴|종아리|정강/],
 ['knee',/무릎|(?<!팔)오금/],
 ['thigh',/넓적다리|대퇴/],
 ['shoulder',/어깨|견갑|빗장|쇄골/],
 ['pelvis-perineum',/볼기|엉덩|엉치|회음|샅고랑|항문|음낭|대음순|두덩|골반/],
 ['chest',/앞가슴|가슴|흉부|갈비사이|젖꼭지/],
 ['abdomen',/배꼽|복부|아랫배|윗배|가쪽배|배 부위|명치/],
 ['back',/등쪽|등 위쪽|등 부위|등뼈|허리|뒤정중선/],
 ['neck',/(?:^|\s)목(?:에서|\s|앞|뒤|부위|덜미)|경부|목덜미/],
 ['head',/(?:^|\s)머리(?:에서|\s|부위|위)|두피|얼굴|이마|눈썹|눈구석|눈확|콧|코끝|인중|입술|턱|귀|관자|꼭지돌기|뒤통수/],
];
const TAG_RULES=[
 ['REGION_CONTEXT',/앞가슴|가슴|흉부|배|복부|아랫배|윗배|등|목|머리|얼굴|어깨|위팔|팔꿈치|아래팔|손목|손바닥|손등|손가락|볼기|회음|넓적다리|무릎|아래다리|종아리|발목|발등|발바닥|발가락/],
 ['BETWEEN',/사이/],
 ['MIDPOINT',/중점|가운데/],
 ['INTERSPACE',/갈비사이공간|뼈사이공간|틈새|공간/],
 ['DEPRESSION',/오목|패인 곳/],
 ['BORDER_MARGIN',/경계|모서리|가장자리|끝/],
 ['FOLD',/주름/],
 ['LINE_BETWEEN',/잇는 선|연결하는 선|선 위/],
 ['CURVE_BETWEEN',/잇는 곡선|곡선/],
 ['SAME_LEVEL',/같은 높이/],
 ['INTERSECTION',/만나는 지점|교차/],
 ['MIDLINE',/앞정중선|뒤정중선|정중선/],
 ['DIRECTIONAL_RELATION',/위로|아래로|위쪽|아래쪽|앞쪽|뒤쪽|안쪽|가쪽|몸쪽|먼쪽|노쪽|자쪽/],
 ['OFFSET_B_CUN',/B-cun/],
 ['OFFSET_F_CUN',/F-cun/],
 ['SEGMENT_FRACTION',/\d+\s*\/\s*\d+/],
 ['POINT_REFERENCE',/\b(?:LU|LI|ST|SP|HT|SI|BL|KI|PC|TE|GB|LR|GV|CV)\d+\b/],
 ['POSTURE_CONDITION',/굽혔|굽히면|폈|펴면|주먹|벌렸|모았/],
 ['SEX_CONDITION',/남성|여성/],
 ['NAIL_REFERENCE',/손톱|발톱/],
 ['ORDINAL_SPACE',/(첫째|둘째|셋째|넷째|다섯째|여섯째|일곱째)\s*갈비사이공간/],
 ['SURFACE_BOUNDARY',/피부가 만나는 경계/],
 ['LANDMARK_FEATURE',/융기|돌기|가시|각|능선|오목|주름|고랑|구멍|결절|모서리|중심|끝/],
];
const DIR_RULES=[
 ['superior',/위로|위쪽/],['inferior',/아래로|아래쪽/],
 ['anterior',/앞쪽/],['posterior',/뒤쪽/],
 ['medial',/안쪽/],['lateral',/가쪽/],
 ['proximal',/몸쪽/],['distal',/먼쪽/],
 ['radial',/노쪽/],['ulnar',/자쪽/],
];

function statements(text){
 const out=[]; let start=0;
 for(let i=0;i<text.length;i++){
  const ch=text[i];
  if((ch==='.'||ch==='!'||ch==='?') && !(ch==='.' && /\d/.test(text[i-1]??'') && /\d/.test(text[i+1]??''))){
   let end=i+1; while(end<text.length && /\s/.test(text[end]))end++;
   out.push({start,end,text:text.slice(start,end)}); start=end; i=end-1;
  }
 }
 if(start<text.length)out.push({start,end:text.length,text:text.slice(start)});
 return out;
}
function regionOf(text){
 // Body-region context is normally stated near the beginning. Choose the
 // earliest explicit regional expression rather than whichever regex is listed
 // first; this prevents false matches such as 팔꿈치머리 -> 머리 or 오목 -> 목.
 let best=null;
 for(const [id,re] of REGION_RULES){
   const m=text.match(re); if(!m)continue;
   const index=m.index??0;
   if(index>32)continue;
   if(!best||index<best.index)best={id,evidence:m[0].trim(),index};
 }
 return best?{id:best.id,evidence:best.evidence}:{id:'unspecified',evidence:null};
}
function findAll(re,text,mapper){
 const flags=re.flags.includes('g')?re.flags:re.flags+'g',rx=new RegExp(re.source,flags),out=[];let m;
 while((m=rx.exec(text))){out.push(mapper(m));if(m[0].length===0)rx.lastIndex++;}
 return out;
}
function nearestDirection(text,index,length=0){
 // Korean location statements usually place the anatomical direction either
 // immediately before "...으로 N B-cun" or just after "N B-cun 아래/위".
 // Select the closest directional token to the measurement rather than the
 // first direction in a broad window (which can describe the region/aspect).
 const suffix=text.slice(index+length,index+length+14);
 const suffixMatch=suffix.match(/^\s*(위|아래)(?:쪽)?(?:에|로|으로|이다|해당|높이)?/);
 if(suffixMatch)return {id:suffixMatch[1]==='위'?'superior':'inferior',evidence:suffixMatch[1]};
 const lo=Math.max(0,index-28),hi=Math.min(text.length,index+28),window=text.slice(lo,hi),relative=index-lo;
 const candidates=[];
 for(const [id,re] of DIR_RULES){
   const rx=new RegExp(re.source,re.flags.includes('g')?re.flags:re.flags+'g');let m;
   while((m=rx.exec(window))){
     const center=m.index+m[0].length/2,dist=Math.abs(center-relative);
     candidates.push({id,evidence:m[0],dist,index:m.index});
     if(!m[0].length)rx.lastIndex++;
   }
 }
 if(!candidates.length)return null;
 candidates.sort((a,b)=>a.dist-b.dist||b.index-a.index);
 const best=candidates[0];
 return {id:best.id,evidence:best.evidence};
}
function build(point){
 const text=point.locationKo;
 const region=regionOf(text);
 const ss=statements(text);
 const measurements=findAll(/(\d+(?:\.\d+)?)\s*(B-cun|F-cun)/g,text,m=>({
   value:Number(m[1]),unit:m[2],text:m[0],start:m.index,end:m.index+m[0].length,direction:nearestDirection(text,m.index,m[0].length)
 }));
 const fractions=findAll(/(\d+)\s*\/\s*(\d+)/g,text,m=>({
   numerator:Number(m[1]),denominator:Number(m[2]),value:Number(m[1])/Number(m[2]),text:m[0],start:m.index,end:m.index+m[0].length
 }));
 const pointReferences=findAll(/\b(?:LU|LI|ST|SP|HT|SI|BL|KI|PC|TE|GB|LR|GV|CV)\d+\b/g,text,m=>({
   acupointId:m[0],start:m.index,end:m.index+m[0].length
 }));
 const conditions=[];
 if(/남성/.test(text))conditions.push({type:'sex',value:'male',evidence:'남성'});
 if(/여성/.test(text))conditions.push({type:'sex',value:'female',evidence:'여성'});
 for(const evidence of ['굽혔을 때','굽히면','폈을 때','펴면','주먹을 쥐었을 때','벌렸을 때','모았을 때']){
   if(text.includes(evidence))conditions.push({type:'posture',value:'source-defined',evidence});
 }
 const specs=ss.map((s,idx)=>{
   const tags=TAG_RULES.filter(([,re])=>re.test(s.text)).map(([tag])=>tag);
   if(!tags.length)tags.push('DIRECT_LOCATION');
   const cId=`${point.id}-S${idx+1}-V`;
   return {...s,id:`${point.id}-S${idx+1}`,semanticTags:tags,verbatimConstraintId:cId};
 });
 const constraints=specs.map(s=>({
   id:s.verbatimConstraintId,
   type:'VERBATIM_STATEMENT',
   strength:'hard',
   sourceSpan:{start:s.start,end:s.end},
   text:s.text,
   semanticTags:s.semanticTags,
   normalizationStatus:'lossless-intermediate'
 }));
 return {
   schemaVersion:2,
   acupointId:point.id,
   source:{
     textKo:text,
     sha256:sha256(text),
     sourceIds:point.sourceIds,
     who2008Page:point.who2008Page
   },
   context:{
     bodyRegion:region.id,
     regionEvidence:region.evidence,
     surface:'body-surface',
     laterality:point.laterality,
     aspectEvidence:DIR_RULES.filter(([,re])=>re.test(text)).map(([id])=>id)
   },
   statements:specs,
   measurements,
   fractions,
   pointReferences,
   conditions,
   constraints,
   preservation:{
     lossless:true,
     encoding:'UTF-8 exact source spans',
     reconstruction:'concatenate statements[].text in order',
     lossyTransformations:[],
     uncoveredText:[]
   },
   resolution:{
     anatomyEntityMapping:'pending',
     measurementFrameMapping:'pending',
     solverPlan:'pending'
   }
 };
}

const specs=acupoints.map(build);
const out={
  schemaVersion:2,
  title:'Lossless WHO acupoint location specifications',
  methodology:{
    sourceOfTruth:'public/knowledge/acupoints.json locationKo',
    principle:'Preserve every source character and attach normalized semantic annotations without replacing source meaning.',
    canonicalSurface:'body-surface',
    normalizedStage:'lossless semantic intermediate representation; anatomy entity resolution and solver mapping follow separately'
  },
  specs
};
fs.writeFileSync(new URL('public/knowledge/acupoint-location-specs.json',root),JSON.stringify(out,null,2)+'\n');
console.log(`Generated ${specs.length} lossless acupoint location specifications.`);
