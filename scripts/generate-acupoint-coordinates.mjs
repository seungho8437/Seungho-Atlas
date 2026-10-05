import fs from 'node:fs';

const root = new URL('../', import.meta.url);
const readJson = p => JSON.parse(fs.readFileSync(new URL(p, root), 'utf8'));
const atlas = readJson('public/models/atlas.json');
const acupoints = readJson('public/knowledge/acupoints.json');
const relations = readJson('public/knowledge/anatomy-acupoint-relations.json');
const anatomyKo = readJson('public/knowledge/anatomy-ko.json');
const coordinateSolver = readJson('public/knowledge/acupoint-coordinate-solver.json');
const solverFramesByPoint = new Map(coordinateSolver.records.map(r => [r.acupointId, r.measurementFrames]));

const chunks = atlas.chunks.map(c => fs.readFileSync(new URL('public/models/' + c.url.split('/').pop(), root)));
const partsById = new Map(atlas.parts.map(p => [p.id, p]));
const partsByConcept = new Map();
for (const c of atlas.concepts) {
  const mapped = (c.elements ?? []).map(id => partsById.get(id)).filter(Boolean);
  if (mapped.length) partsByConcept.set(c.id, mapped);
}
for (const p of atlas.parts) {
  const mapped = partsByConcept.get(p.conceptId) ?? [];
  if (!mapped.some(x => x.id === p.id)) mapped.push(p);
  partsByConcept.set(p.conceptId, mapped);
}

function positionsOfPart(p) {
  const b = chunks[p.chunk];
  return new Float32Array(b.buffer, b.byteOffset + p.positions, p.vertexCount * 3);
}
function indicesOfPart(p) {
  const b = chunks[p.chunk];
  return new Uint32Array(b.buffer, b.byteOffset + p.indices, p.indexCount);
}
function centerBounds(parts, sideSign = 0, lrAxis = 0, leftSign = 1) {
  let min=[Infinity,Infinity,Infinity], max=[-Infinity,-Infinity,-Infinity], sum=[0,0,0], n=0;
  for (const p of parts || []) {
    const a=positionsOfPart(p);
    for(let i=0;i<a.length;i+=3){
      const v=[a[i],a[i+1],a[i+2]];
      if(sideSign && Math.sign(v[lrAxis] || 0)!==sideSign*leftSign) continue;
      for(let k=0;k<3;k++){min[k]=Math.min(min[k],v[k]);max[k]=Math.max(max[k],v[k]);sum[k]+=v[k];}
      n++;
    }
  }
  if(!n) return null;
  return {center:sum.map(x=>x/n),min,max,n,diag:Math.hypot(max[0]-min[0],max[1]-min[1],max[2]-min[2])};
}
function conceptStats(id, sideSign=0, lrAxis=0, leftSign=1){return centerBounds(partsByConcept.get(id),sideSign,lrAxis,leftSign);}

const surfaceParts = atlas.parts.filter(p => p.system === 'integumentary');
if (!surfaceParts.length) throw new Error('No integumentary/body-surface mesh found.');
const allStats = centerBounds(surfaceParts);
const extent=allStats.max.map((v,i)=>v-allStats.min[i]);
const supAxis = extent.indexOf(Math.max(...extent));
const remaining=[0,1,2].filter(i=>i!==supAxis);

function namedCentroid(re){
  const ps=atlas.parts.filter(p=>re.test(p.name));
  return centerBounds(ps)?.center ?? null;
}
let lrAxis=remaining[0], leftSign=1;
const lc=namedCentroid(/\bleft\b/i), rc=namedCentroid(/\bright\b/i);
if(lc&&rc){
  lrAxis=remaining.reduce((best,a)=>Math.abs(lc[a]-rc[a])>Math.abs(lc[best]-rc[best])?a:best,remaining[0]);
  leftSign=Math.sign((lc[lrAxis]-rc[lrAxis])||1);
}
const apAxis=[0,1,2].find(i=>i!==supAxis&&i!==lrAxis);
let anteriorSign=1;
const sternum=namedCentroid(/sternum/i), vertebra=namedCentroid(/vertebra/i);
if(sternum&&vertebra) anteriorSign=Math.sign((sternum[apAxis]-vertebra[apAxis])||1);

const bodyCenter=allStats.center, bodyMin=allStats.min, bodyMax=allStats.max;
const bodyDiag=allStats.diag;
const norm=(axis,t)=>bodyMin[axis]+extent[axis]*t;
const surfaceCrossSectionSamples=[];
for(const p of surfaceParts){
  const a=positionsOfPart(p);
  for(let i=0;i<a.length;i+=3)surfaceCrossSectionSamples.push([a[lrAxis],a[supAxis]]);
}
const widthCache=new Map();
function localHalfWidth(y){
  const step=extent[supAxis]*.012, bucket=Math.round((y-bodyMin[supAxis])/step);
  if(widthCache.has(bucket))return widthCache.get(bucket);
  let band=extent[supAxis]*.018,vals=[];
  for(let pass=0;pass<3&&!vals.length;pass++,band*=1.8){
    vals=surfaceCrossSectionSamples.filter(v=>Math.abs(v[1]-y)<=band).map(v=>Math.abs(v[0]-bodyCenter[lrAxis]));
  }
  if(!vals.length)return extent[lrAxis]/2;
  vals.sort((a,b)=>a-b);
  const q=vals[Math.min(vals.length-1,Math.floor(vals.length*.72))];
  const value=Math.max(extent[lrAxis]*.035,Math.min(extent[lrAxis]/2,q));
  widthCache.set(bucket,value);return value;
}
function localSideLateral(y, sideSign, frac){
  let band=extent[supAxis]*.018, vals=[];
  for(let pass=0;pass<3&&!vals.length;pass++,band*=1.8){
    vals=surfaceCrossSectionSamples
      .filter(v=>Math.abs(v[1]-y)<=band)
      .map(v=>(v[0]-bodyCenter[lrAxis])*sideSign)
      .filter(v=>v>0);
  }
  if(!vals.length)return bodyCenter[lrAxis]+sideSign*localHalfWidth(y)*frac;
  vals.sort((a,b)=>a-b);
  const q=(p)=>vals[Math.min(vals.length-1,Math.max(0,Math.floor((vals.length-1)*p)))];
  const inner=q(.12), outer=q(.88);
  return bodyCenter[lrAxis]+sideSign*(inner+(outer-inner)*Math.max(0,Math.min(1,frac)));
}

const regionRules = [
  [/vertex|머리꼭대기|정수리|두정부|머리 위/, .97, .50],
  [/forehead|이마|눈썹|미간|코|입술|턱|얼굴|눈|귀|관자/, .91, .82],
  [/occip|뒤통수|후두|뒷머리/, .91, .18],
  [/head|머리|두피/, .93, .55],
  [/neck|목|경부|목덜미/, .82, .52],
  [/shoulder|어깨|견갑|빗장|쇄골/, .76, .58],
  [/chest|가슴|흉부|갈비|늑간|유두/, .69, .78],
  [/upper abdomen|윗배|상복부|명치/, .59, .76],
  [/abdomen|배꼽|복부|배 부위|아랫배/, .50, .77],
  [/pelvis|샅|회음|두덩|치골|엉덩|볼기|천골|엉치/, .38, .50],
  [/upper arm|위팔|상완/, .66, .60],
  [/elbow|팔꿈치|주와/, .55, .58],
  [/forearm|아래팔|전완/, .47, .58],
  [/wrist|손목/, .38, .60],
  [/hand|손등|손바닥|손가락|엄지|새끼손가락/, .32, .64],
  [/thigh|넓적다리|대퇴/, .31, .53],
  [/knee|무릎|오금|슬부/, .20, .50],
  [/leg|종아리|정강|하퇴|아래다리/, .12, .52],
  [/ankle|복사|발목/, .055, .53],
  [/foot|발등|발바닥|발가락|엄지발가락/, .025, .62],
];

function regionTarget(text, side){
  let z=.50, a=.55;
  for(const [re,zz,aa] of regionRules){ if(re.test(text)){z=zz;a=aa;break;} }
  const t=[...bodyCenter];
  t[supAxis]=norm(supAxis,z);
  const apHalf=extent[apAxis]/2;
  t[apAxis]=bodyCenter[apAxis]+anteriorSign*apHalf*((a-.5)*1.75);
  if(/뒤|posterior|등쪽|배측/.test(text)) t[apAxis]=bodyCenter[apAxis]-anteriorSign*apHalf*.75;
  if(/앞|anterior|배쪽|손바닥쪽/.test(text)) t[apAxis]=bodyCenter[apAxis]+anteriorSign*apHalf*.72;
  const lateralFrac = /정중|median|midline/.test(text) ? 0 : (/가쪽|lateral|외측/.test(text)?.62:.43);
  const s=side==='left'?leftSign:side==='right'?-leftSign:0;
  const coreRegion=/머리|두피|얼굴|이마|눈|귀|코|입술|턱|목|가슴|흉부|갈비|배|복부|배꼽|엉치|볼기|골반|등|천골|pelvis|chest|abdomen|head|face|neck|back/i.test(text);
  const half=coreRegion?localHalfWidth(t[supAxis]):extent[lrAxis]/2;
  t[lrAxis]=bodyCenter[lrAxis]+s*half*lateralFrac;
  return t;
}

const cunY=extent[supAxis]/75;
function solverCun(pointId,side,direction,unit='B-cun'){
  const fs=solverFramesByPoint.get(pointId)||[];
  const exact=fs.find(f=>f.unit===unit&&f.direction===direction)??fs.find(f=>f.unit===unit);
  const ss=exact?.sideScales?.find(x=>x.side===side)??exact?.sideScales?.find(x=>x.side==='midline');
  return Number.isFinite(ss?.chosen?.cunLength)?ss.chosen.cunLength:null;
}
const ordinalIntercostal={첫째:1,둘째:2,셋째:3,넷째:4,다섯째:5,여섯째:6,일곱째:7};
function applyWhoConstraints(input,text,side,pointId){
  const t=[...input]; let count=0;
  const explicitFoot=/발등|발바닥|발가락|발허리|발꿈치|복사|발목/.test(text) && !/아래다리|넓적다리|무릎/.test(text);
  if(explicitFoot){
    const ceiling=norm(supAxis,.115), floor=norm(supAxis,.008);
    t[supAxis]=Math.max(floor,Math.min(ceiling,t[supAxis]));
    count++;
  }
  const sideSign=side==='left'?leftSign:side==='right'?-leftSign:0;
  const fmatch=text.match(/(\d+(?:\.\d+)?)\s*F-cun/);
  if(fmatch&&pointId){
    const fs=(solverFramesByPoint.get(pointId)||[]).find(f=>f.unit==='F-cun');
    const scale=solverCun(pointId,side,fs?.direction,'F-cun');
    if(scale&&fs){
      const amount=Number(fmatch[1])*scale,dir=fs.direction;
      if(dir==='lateral')t[lrAxis]+=sideSign*amount;
      else if(dir==='medial')t[lrAxis]-=sideSign*amount;
      else if(dir==='superior'||dir==='proximal')t[supAxis]+=amount;
      else if(dir==='inferior'||dir==='distal')t[supAxis]-=amount;
      else if(dir==='anterior')t[apAxis]+=anteriorSign*amount;
      else if(dir==='posterior')t[apAxis]-=anteriorSign*amount;
      count++;
    }
  }
  const lateral=text.match(/정중선[^,.]{0,45}?가쪽(?:으로)?\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(lateral&&sideSign){
    const n=Number(lateral[1]);
    const frac=Math.min(.92,n/6*.84);
    const baseOffset=localHalfWidth(t[supAxis])*frac;
    const reviewed=solverCun(pointId,side,'lateral','B-cun');
    const offset=reviewed?n*reviewed:(/배|복부/.test(text)?Math.max(baseOffset,n*cunY):baseOffset);
    t[lrAxis]=bodyCenter[lrAxis]+sideSign*offset;
    count++;
  }
  const nav=text.match(/배꼽(?:\s*중심)?(?:보다|에서)?\s*(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(nav){
    const n=Number(nav[2]), navel=norm(supAxis,.455);
    const sc=solverCun(pointId,side,nav[1]==='위'?'superior':'inferior','B-cun')??cunY;
    t[supAxis]=nav[1]==='위'?navel+n*sc:navel-n*sc;
    count++;
  }
  const navLat=text.match(/배꼽(?:\s*중심)?으로부터\s*가쪽으로\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(navLat&&sideSign){
    const n=Number(navLat[1]);
    t[supAxis]=norm(supAxis,.455);
    t[lrAxis]=bodyCenter[lrAxis]+sideSign*localHalfWidth(t[supAxis])*Math.min(.82,n/4*.62);
    count+=2;
  }
  const sacral=text.match(/(첫째|둘째|셋째|넷째)\s*뒤엉치뼈구멍/);
  if(sacral){
    const ord={첫째:1,둘째:2,셋째:3,넷째:4}[sacral[1]];
    t[supAxis]=norm(supAxis,.405-(ord-1)*.026);
    count++;
  }
  const hair=text.match(/(?:앞머리선|머리선)[^,.]{0,35}?(?:위로|안쪽으로)\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(hair){
    const sc=solverCun(pointId,side,'superior','B-cun')??cunY;
    t[supAxis]=norm(supAxis,.895)+Number(hair[1])*sc;
    count++;
  }
  const ic=text.match(/(첫째|둘째|셋째|넷째|다섯째|여섯째|일곱째)\s*갈비사이공간/);
  if(ic){
    const n=ordinalIntercostal[ic[1]];
    t[supAxis]=norm(supAxis,.735-(n-1)*.027);
    count++;
  }
  const refs=[
    [/앞겨드랑주름[^,.]{0,35}?(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/, .735],
    [/뒤겨드랑주름[^,.]{0,35}?(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/, .735],
    [/봉우리각[^,.]{0,35}?(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/, .76],
    [/손바닥쪽\s*손목주름[^,.]{0,35}?(위로|아래로|몸쪽으로|먼쪽으로)\s*(\d+(?:\.\d+)?)\s*B-cun/, .385],
    [/손등쪽\s*손목주름[^,.]{0,35}?(위로|아래로|몸쪽으로|먼쪽으로)\s*(\d+(?:\.\d+)?)\s*B-cun/, .385],
    [/팔오금주름[^,.]{0,35}?(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/, .55],
    [/무릎뼈바닥[^,.]{0,35}?(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/, .215],
    [/ST35[^,.]{0,35}?(위로|위쪽으로|아래로|아래쪽으로)\s*(\d+(?:\.\d+)?)\s*B-cun/, .20],
    [/팔꿈치머리\s*융기[^,.]{0,35}?(몸쪽|먼쪽|위|아래)으로\s*(\d+(?:\.\d+)?)\s*B-cun/, .55],
  ];
  for(const [re,base] of refs){
    const m=text.match(re); if(!m)continue;
    const n=Number(m[2]), up=(m[1].startsWith('위')||m[1].startsWith('몸쪽'));
    const sc=solverCun(pointId,side,up?'superior':'inferior','B-cun')??solverCun(pointId,side,up?'proximal':'distal','B-cun')??cunY;
    t[supAxis]=norm(supAxis,base)+(up?1:-1)*n*sc; count++; break;
  }
  const sacLat=text.match(/정중엉치뼈능선[^,.]{0,30}?가쪽으로\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(sacLat&&sideSign){
    const n=Number(sacLat[1]);
    t[lrAxis]=bodyCenter[lrAxis]+sideSign*localHalfWidth(t[supAxis])*Math.min(.92,n/3*.7);
    count++;
  }
  const malleolus=text.match(/(안쪽|가쪽)복사(?:\s*융기)?에서[^,.]{0,30}?(위로|아래로|몸쪽으로|먼쪽으로)\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(malleolus){
    const up=(malleolus[2].startsWith('위')||malleolus[2].startsWith('몸쪽'));
    const sc=solverCun(pointId,side,up?'superior':'inferior','B-cun')??solverCun(pointId,side,up?'proximal':'distal','B-cun')??cunY;
    t[supAxis]=norm(supAxis,.055)+(up?1:-1)*Number(malleolus[3])*sc;count++;
  }
  const popliteal=text.match(/(?<!팔)오금주름에서[^,.]{0,30}?(위로|아래로|몸쪽으로|먼쪽으로)\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(popliteal){
    const up=(popliteal[1].startsWith('위')||popliteal[1].startsWith('몸쪽'));
    const sc=solverCun(pointId,side,up?'superior':'inferior','B-cun')??solverCun(pointId,side,up?'proximal':'distal','B-cun')??cunY;
    t[supAxis]=norm(supAxis,.20)+(up?1:-1)*Number(popliteal[2])*sc;count++;
  }
  if(/팔오금주름\s*위/.test(text)&&!/[0-9]\s*B-cun/.test(text)){t[supAxis]=norm(supAxis,.55);count++;}
  if(/손바닥쪽\s*손목주름\s*위에/.test(text)){t[supAxis]=norm(supAxis,.385);count++;}
  if(!/팔오금주름/.test(text)&&/오금주름의\s*가운데|오금주름\s*위/.test(text)){t[supAxis]=norm(supAxis,.20);count++;}
  if(/코끝/.test(text)){t[supAxis]=norm(supAxis,.865);t[apAxis]=bodyCenter[apAxis]+anteriorSign*extent[apAxis]*.46;count+=2;}
  if(/인중(?:의)?\s*정중선|인중의\s*중점/.test(text)){t[supAxis]=norm(supAxis,.835);count++;}
  if(/윗입술결절/.test(text)){t[supAxis]=norm(supAxis,.82);count++;}
  if(/윗입술소대/.test(text)){t[supAxis]=norm(supAxis,.808);count++;}
  if(/턱입술고랑/.test(text)){t[supAxis]=norm(supAxis,.855);count++;}
  if(/안쪽눈구석/.test(text)&&sideSign){t[lrAxis]=bodyCenter[lrAxis]+sideSign*localHalfWidth(t[supAxis])*.16;count++;}
  if(/눈확아래구멍/.test(text)){t[supAxis]-=2.0*cunY;count++;}
  if(/콧방울\s*아래모서리와\s*같은\s*높이/.test(text)){t[supAxis]=norm(supAxis,.855);count++;}
  if(/목빗근[^,.]{0,18}?뒤/.test(text)){t[apAxis]-=anteriorSign*extent[apAxis]*.035;count++;}
  if(/목빗근[^,.]{0,18}?앞/.test(text)){t[apAxis]+=anteriorSign*extent[apAxis]*.035;count++;}
  if(/손바닥/.test(text)){t[apAxis]=bodyCenter[apAxis]+anteriorSign*extent[apAxis]*.16;count++;}
  if(/손등/.test(text)){t[apAxis]=bodyCenter[apAxis]-anteriorSign*extent[apAxis]*.10;count++;}
  if(/발바닥/.test(text)){t[apAxis]=bodyCenter[apAxis]-anteriorSign*extent[apAxis]*.16;count++;}
  if(/발등/.test(text)){t[apAxis]=bodyCenter[apAxis]+anteriorSign*extent[apAxis]*.08;count++;}
  if(/꼭지돌기[^,.]{0,24}?앞쪽/.test(text)){t[apAxis]+=anteriorSign*extent[apAxis]*.055;count++;}
  if(/꼭지돌기[^,.]{0,24}?뒤/.test(text)){t[apAxis]-=anteriorSign*extent[apAxis]*.055;count++;}
  if(/귓바퀴\s*꼭대기\s*바로\s*위/.test(text)&&!/머리선[^,.]{0,40}B-cun/.test(text)){t[supAxis]=norm(supAxis,.91);count++;}
  if(/광대활/.test(text)){t[supAxis]=norm(supAxis,.87);count++;}
  if(/귀구슬위패임/.test(text)){t[supAxis]=norm(supAxis,.872);count++;}
  if(/귀구슬\s*중심/.test(text)){t[supAxis]=norm(supAxis,.858);count++;}
  if(/귀구슬사이패임/.test(text)){t[supAxis]=norm(supAxis,.846);count++;}
  const browUp=text.match(/눈썹보다\s*위로\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(browUp){t[supAxis]=norm(supAxis,.885)+Number(browUp[1])*cunY;count++;}
  if(/눈썹\s*안쪽끝/.test(text)){t[supAxis]=norm(supAxis,.885);count++;}
  if(/앞위쪽/.test(text)){t[supAxis]+=cunY*.7;count++;}
  if(/배꼽\s*중심과\s*같은\s*높이/.test(text)){t[supAxis]=norm(supAxis,.455);count++;}
  if(/가쪽배/.test(text)&&sideSign){
    // Keep lateral abdominal points on the torso rather than allowing a
    // same-height arm/hand surface to dominate the cross-section sampler.
    t[lrAxis]=bodyCenter[lrAxis]+sideSign*extent[lrAxis]*.18;
    count++;
  }
  if(/무릎뼈의\s*아래가쪽\s*오목|무릎인대\s*가쪽의\s*오목/.test(text)&&sideSign){
    // ST35: inferolateral patellar depression.
    t[supAxis]=norm(supAxis,.205);
    t[lrAxis]=localSideLateral(t[supAxis],sideSign,.60);
    t[apAxis]=bodyCenter[apAxis]+anteriorSign*extent[apAxis]*.18;
    count+=3;
  }
  if(/배꼽(?:\s*중심)?에\s*있다/.test(text)){t[supAxis]=norm(supAxis,.455);count++;}
  if(/꼬리뼈\s*끝/.test(text)&&sideSign){
    t[supAxis]=norm(supAxis,.38);
    t[lrAxis]=localSideLateral(t[supAxis],sideSign,.20);
    t[apAxis]=bodyCenter[apAxis]-anteriorSign*extent[apAxis]*.18;
    count+=3;
  }
  if(/볼기주름의\s*중점/.test(text)&&sideSign){
    t[supAxis]=norm(supAxis,.38);
    t[lrAxis]=localSideLateral(t[supAxis],sideSign,.36);
    t[apAxis]=bodyCenter[apAxis]-anteriorSign*extent[apAxis]*.16;
    count+=3;
  }
  if(/위앞엉덩뼈가시보다\s*안쪽[·ㆍ]?아래쪽으로\s*0\.5\s*B-cun/.test(text)&&sideSign){
    t[supAxis]=norm(supAxis,.405);
    t[lrAxis]=localSideLateral(t[supAxis],sideSign,.68);
    t[apAxis]=bodyCenter[apAxis]+anteriorSign*extent[apAxis]*.18;
    count+=3;
  }
  if(/위앞엉덩뼈가시와\s*큰돌기\s*융기를\s*잇는\s*선의\s*중점/.test(text)&&sideSign){
    t[supAxis]=norm(supAxis,.37);
    t[lrAxis]=localSideLateral(t[supAxis],sideSign,.76);
    t[apAxis]=bodyCenter[apAxis]-anteriorSign*extent[apAxis]*.02;
    count+=3;
  }
  if(/젖꼭지의\s*중심/.test(text)&&sideSign){
    t[lrAxis]=bodyCenter[lrAxis]+sideSign*localHalfWidth(t[supAxis])*.48;
    count++;
  }
  if(/중간겨드랑선보다\s*앞쪽으로\s*1\s*B-cun/.test(text)&&sideSign){
    t[lrAxis]=bodyCenter[lrAxis]+sideSign*localHalfWidth(t[supAxis])*.82;
    t[apAxis]=bodyCenter[apAxis]+anteriorSign*extent[apAxis]*.10;
    count+=2;
  }
  if(/가쪽복사\s*융기\s*바로\s*아래/.test(text)&&sideSign){
    t[lrAxis]=localSideLateral(t[supAxis],sideSign,.90);
    count++;
  }
  if(/안쪽복사의\s*뒤아래쪽/.test(text)&&sideSign){
    t[lrAxis]=localSideLateral(t[supAxis],sideSign,.14);
    t[apAxis]-=anteriorSign*extent[apAxis]*.035;
    count+=2;
  }
  if(/둘째와\s*셋째발허리뼈\s*사이/.test(text)&&sideSign){
    t[lrAxis]=localSideLateral(t[supAxis],sideSign,.35);
    count++;
  }
  if(/넷째와\s*다섯째발허리뼈\s*사이/.test(text)&&sideSign){
    t[lrAxis]=localSideLateral(t[supAxis],sideSign,.72);
    count++;
  }
  if(/발목/.test(text)&&!/B-cun/.test(text)){t[supAxis]=norm(supAxis,.06);count++;}
  if(/발허리발가락관절[^,.]{0,12}먼쪽/.test(text)){t[apAxis]+=anteriorSign*extent[apAxis]*.045;count++;}
  if(/발허리발가락관절[^,.]{0,12}몸쪽/.test(text)){t[apAxis]-=anteriorSign*extent[apAxis]*.035;count++;}
  if(/손허리손가락관절[^,.]{0,12}먼쪽/.test(text)){t[supAxis]-=cunY*.8;count++;}
  if(/손허리손가락관절[^,.]{0,12}몸쪽/.test(text)){t[supAxis]+=cunY*.8;count++;}
  if(/어깨뼈가시\s*중점\s*바로\s*위/.test(text)){t[supAxis]=norm(supAxis,.735);count++;}
  if(/어깨뼈\s*위각\s*위쪽/.test(text)){t[supAxis]=norm(supAxis,.775);count++;}
  if(/어깨뼈가시\s*중점과\s*어깨뼈\s*아래각/.test(text)){t[supAxis]=norm(supAxis,.70);count++;}
  if(/어깨뼈\s*부위/.test(text)){t[apAxis]=bodyCenter[apAxis]-anteriorSign*extent[apAxis]*.22;count++;}
  if(/어깨세모근[^,.]{0,24}?앞쪽/.test(text)){t[apAxis]=bodyCenter[apAxis]+anteriorSign*extent[apAxis]*.13;count++;}
  if(/귀구슬|귓바퀴|꼭지돌기/.test(text)&&sideSign){
    t[lrAxis]=bodyCenter[lrAxis]+sideSign*localHalfWidth(t[supAxis])*.86;count++;
  }
  if(/동공/.test(text)&&sideSign){t[lrAxis]=bodyCenter[lrAxis]+sideSign*localHalfWidth(t[supAxis])*.34;count++;}
  if(/가쪽눈구석/.test(text)&&sideSign){
    t[lrAxis]=bodyCenter[lrAxis]+sideSign*localHalfWidth(t[supAxis])*.55;
    t[apAxis]=bodyCenter[apAxis]+anteriorSign*extent[apAxis]*.28;count+=2;
    if(/바로\s*아래/.test(text)){t[supAxis]-=cunY*1.25;count++;}
    const canthusLat=text.match(/가쪽눈구석에서\s*가쪽으로\s*(\d+(?:\.\d+)?)\s*B-cun/);
    if(canthusLat){t[lrAxis]+=sideSign*localHalfWidth(t[supAxis])*(Number(canthusLat[1])*.18);count++;}
  }
  if(/관자부\s*머리선|머리선\s*뒤모서리/.test(text)){t[apAxis]=bodyCenter[apAxis]-anteriorSign*extent[apAxis]*.08;count++;}
  if(/아래팔|손목|손등|손바닥|손가락/.test(text)&&sideSign){
    const half=localHalfWidth(t[supAxis]);
    if(/뒤가쪽|앞가쪽|\b노쪽\b|노뼈/.test(text)){t[lrAxis]+=sideSign*half*.10;count++;}
    if(/뒤안쪽|앞안쪽|\b자쪽\b|자뼈/.test(text)){t[lrAxis]-=sideSign*half*.10;count++;}
  }
  if(/발등|발바닥|발가락|발허리|발목|복사|발꿈치/.test(text)&&sideSign){
    const half=localHalfWidth(t[supAxis]);
    let frac=null;
    if(/엄지발가락|첫째\s*발허리/.test(text))frac=.22;
    else if(/둘째(?:발가락|\s*발허리)/.test(text))frac=.34;
    else if(/셋째(?:발가락|\s*발허리)/.test(text))frac=.43;
    else if(/넷째(?:발가락|\s*발허리)/.test(text))frac=.55;
    else if(/새끼발가락|다섯째(?:발가락|\s*발허리)/.test(text))frac=.68;
    if(frac!==null){t[lrAxis]=bodyCenter[lrAxis]+sideSign*half*frac;count++;}
    if(/끝마디뼈/.test(text)){
      if(/안쪽(?:에서|모서리)/.test(text)){t[lrAxis]-=sideSign*half*.055;count++;}
      if(/가쪽(?:에서|모서리)/.test(text)){t[lrAxis]+=sideSign*half*.055;count++;}
    }
    if(/발꿈치뼈/.test(text)){t[apAxis]-=anteriorSign*extent[apAxis]*.10;count++;}
    if(/발허리발가락관절[^,.]{0,20}먼쪽/.test(text)){t[supAxis]-=cunY*.65;count++;}
    if(/발허리발가락관절[^,.]{0,20}몸쪽/.test(text)){t[supAxis]+=cunY*.65;count++;}
  }
  if(/아래팔/.test(text)&&sideSign){
    const half=localHalfWidth(t[supAxis]);
    if(/뒤가쪽/.test(text)) {t[lrAxis]=bodyCenter[lrAxis]+sideSign*half*.72;count++;}
    if(/노뼈와\s*자뼈\s*사이/.test(text)) {t[lrAxis]=bodyCenter[lrAxis]+sideSign*half*.55;count++;}
    if(/자뼈\s*바로\s*노쪽|뒤안쪽/.test(text)) {t[lrAxis]=bodyCenter[lrAxis]+sideSign*half*.40;count++;}
  }
  if(/다섯째\s*손허리손가락관절/.test(text)){
    if(/먼쪽/.test(text)){t[supAxis]-=cunY*1.4;count++;}
    if(/몸쪽/.test(text)){t[supAxis]+=cunY*1.4;count++;}
  }
  if(/발등/.test(text)&&sideSign){
    const half=localHalfWidth(t[supAxis]);
    if(/가쪽복사\s*앞모서리/.test(text)){t[lrAxis]=bodyCenter[lrAxis]+sideSign*half*.72;t[apAxis]-=anteriorSign*extent[apAxis]*.035;count+=2;}
    if(/넷째와\s*다섯째발허리뼈/.test(text)){t[lrAxis]=bodyCenter[lrAxis]+sideSign*half*.58;t[apAxis]+=anteriorSign*extent[apAxis]*.025;count+=2;}
  }
  if(/발바닥/.test(text)&&/앞쪽\s*1\/3/.test(text)){t[supAxis]=norm(supAxis,.018);t[apAxis]+=anteriorSign*extent[apAxis]*.055;count+=2;}
  if(/새끼손가락\s*끝마디뼈/.test(text)&&sideSign){
    const half=localHalfWidth(t[supAxis]);
    if(/노쪽/.test(text)){t[lrAxis]+=sideSign*half*.05;count++;}
    if(/자쪽/.test(text)){t[lrAxis]-=sideSign*half*.05;count++;}
  }
  if(side==='midline'){t[lrAxis]=bodyCenter[lrAxis];count++;}
  return {target:t,count};
}

const surfaceTriangles=[];
for(const p of surfaceParts){
  const pos=positionsOfPart(p), ind=indicesOfPart(p);
  for(let i=0;i<ind.length;i+=3){
    const tri=[];
    for(let q=0;q<3;q++){const j=ind[i+q]*3;tri.push([pos[j],pos[j+1],pos[j+2]]);}
    const c=[(tri[0][0]+tri[1][0]+tri[2][0])/3,(tri[0][1]+tri[1][1]+tri[2][1])/3,(tri[0][2]+tri[1][2]+tri[2][2])/3];
    surfaceTriangles.push({tri,c,part:p.id});
  }
}
const cell=bodyDiag/70;
const grid=new Map();
const key=p=>p.map(v=>Math.floor(v/cell)).join(',');
for(let i=0;i<surfaceTriangles.length;i++){
  const k=key(surfaceTriangles[i].c); if(!grid.has(k))grid.set(k,[]); grid.get(k).push(i);
}
function closestOnTri(p,a,b,c){
  const sub=(u,v)=>u.map((x,i)=>x-v[i]), dot=(u,v)=>u[0]*v[0]+u[1]*v[1]+u[2]*v[2];
  const ab=sub(b,a), ac=sub(c,a), ap=sub(p,a), d1=dot(ab,ap), d2=dot(ac,ap);
  if(d1<=0&&d2<=0)return a;
  const bp=sub(p,b), d3=dot(ab,bp), d4=dot(ac,bp); if(d3>=0&&d4<=d3)return b;
  const vc=d1*d4-d3*d2; if(vc<=0&&d1>=0&&d3<=0){const v=d1/(d1-d3);return a.map((x,i)=>x+v*ab[i]);}
  const cp=sub(p,c), d5=dot(ab,cp), d6=dot(ac,cp); if(d6>=0&&d5<=d6)return c;
  const vb=d5*d2-d1*d6; if(vb<=0&&d2>=0&&d6<=0){const w=d2/(d2-d6);return a.map((x,i)=>x+w*ac[i]);}
  const va=d3*d6-d5*d4; if(va<=0&&(d4-d3)>=0&&(d5-d6)>=0){const w=(d4-d3)/((d4-d3)+(d5-d6));return b.map((x,i)=>x+w*(c[i]-b[i]));}
  const denom=1/(va+vb+vc), v=vb*denom, w=vc*denom; return a.map((x,i)=>x+ab[i]*v+ac[i]*w);
}
function dist2(a,b){return (a[0]-b[0])**2+(a[1]-b[1])**2+(a[2]-b[2])**2}
function barycentric2D(px,py,a,b,c,ax1,ax2){
  const x1=a[ax1],y1=a[ax2],x2=b[ax1],y2=b[ax2],x3=c[ax1],y3=c[ax2];
  const den=(y2-y3)*(x1-x3)+(x3-x2)*(y1-y3);
  if(Math.abs(den)<1e-12)return null;
  const u=((y2-y3)*(px-x3)+(x3-x2)*(py-y3))/den;
  const v=((y3-y1)*(px-x3)+(x1-x3)*(py-y3))/den;
  const w=1-u-v;
  if(u < -1e-5 || v < -1e-5 || w < -1e-5)return null;
  return [u,v,w];
}
function midlineSliceProjection(target){
  let best=null,bestScore=Infinity,bestPart=null;
  const y=target[supAxis];
  for(const T of surfaceTriangles){
    const hits=[];
    for(const [i,j] of [[0,1],[1,2],[2,0]]){
      const a=T.tri[i],b=T.tri[j],da=a[supAxis]-y,db=b[supAxis]-y;
      if(Math.abs(da)<1e-9)hits.push(a);
      if(da*db<0 || Math.abs(db)<1e-9){
        const den=b[supAxis]-a[supAxis];
        if(Math.abs(den)>1e-12){
          const u=(y-a[supAxis])/den;
          if(u>=-1e-8&&u<=1+1e-8)hits.push(a.map((v,k)=>v+u*(b[k]-v)));
        }
      }
    }
    if(!hits.length)continue;
    const candidates=hits.length===1?[hits[0]]:[hits[0],hits[1],
      hits[0].map((v,k)=>(v+hits[1][k])/2)];
    for(const q of candidates){
      const lateral=q[lrAxis]-bodyCenter[lrAxis];
      if(Math.abs(lateral)>extent[lrAxis]*.16)continue;
      const score=1800*lateral*lateral + 12*(q[apAxis]-target[apAxis])**2;
      if(score<bestScore){bestScore=score;best=q;bestPart=T.part;}
    }
  }
  return best?{point:best,distance:Math.sqrt(dist2(target,best)),part:bestPart,constrained:true,midlineSlice:true}:null;
}
function constrainedSurfaceProjection(target,side,locks){
  const locked=[];
  if(locks.lr)locked.push(lrAxis);
  if(locks.sup)locked.push(supAxis);
  if(locks.ap)locked.push(apAxis);
  if(locked.length<2)return null;
  // Preserve the two strongest WHO axes exactly through the final skin projection.
  // sup+lr is preferred for torso/head; sup+ap for hands/feet; lr+ap otherwise.
  let ax1,ax2;
  if(locks.sup&&locks.lr){ax1=supAxis;ax2=lrAxis;}
  else if(locks.sup&&locks.ap){ax1=supAxis;ax2=apAxis;}
  else {ax1=lrAxis;ax2=apAxis;}
  const free=[0,1,2].find(a=>a!==ax1&&a!==ax2);
  let best=null,bestD=Infinity,bestPart=null;
  for(const T of surfaceTriangles){
    const bc=barycentric2D(target[ax1],target[ax2],T.tri[0],T.tri[1],T.tri[2],ax1,ax2);
    if(!bc)continue;
    const q=[0,0,0];
    for(let k=0;k<3;k++)q[k]=bc[0]*T.tri[0][k]+bc[1]*T.tri[1][k]+bc[2]*T.tri[2][k];
    const sideCoord=q[lrAxis]-bodyCenter[lrAxis];
    if(side==='left' && Math.sign(sideCoord||0)!==leftSign)continue;
    if(side==='right' && Math.sign(sideCoord||0)!==-leftSign)continue;
    if(side==='midline' && Math.abs(sideCoord)>extent[lrAxis]*.12)continue;
    const d=Math.abs(q[free]-target[free]);
    if(d<bestD){bestD=d;best=q;bestPart=T.part;}
  }
  return best?{point:best,distance:Math.sqrt(dist2(target,best)),part:bestPart,constrained:true}:null;
}
function weightedClosestOnSegment(target,a,b,weights){
  const d=b.map((v,i)=>v-a[i]);
  let num=0,den=0;
  for(let i=0;i<3;i++){num+=weights[i]*d[i]*(target[i]-a[i]);den+=weights[i]*d[i]*d[i];}
  const u=den>1e-15?Math.max(0,Math.min(1,num/den)):0;
  return a.map((v,i)=>v+d[i]*u);
}
function trianglePlaneIntersection(tri,axis,value){
  const eps=1e-8, pts=[];
  const add=p=>{if(!pts.some(q=>dist2(p,q)<1e-14))pts.push(p);};
  for(const p of tri)if(Math.abs(p[axis]-value)<=eps)add([...p]);
  for(const [i,j] of [[0,1],[1,2],[2,0]]){
    const a=tri[i],b=tri[j],da=a[axis]-value,db=b[axis]-value;
    if(da*db<0){
      const u=(value-a[axis])/(b[axis]-a[axis]);
      add(a.map((v,k)=>v+(b[k]-v)*u));
    }
  }
  return pts;
}
function projectLockedToSurface(target,side,locks){
  const primary=locks.sup?supAxis:locks.lr?lrAxis:locks.ap?apAxis:null;
  if(primary===null)return null;
  const weights=[1,1,1];
  if(locks.sup)weights[supAxis]=180;
  if(locks.lr)weights[lrAxis]=120;
  if(locks.ap)weights[apAxis]=45;
  let best=null,bestScore=Infinity,bestD=Infinity,bestPart=null;
  for(const T of surfaceTriangles){
    const vals=T.tri.map(p=>p[primary]);
    if(target[primary]<Math.min(...vals)-1e-8||target[primary]>Math.max(...vals)+1e-8)continue;
    const ints=trianglePlaneIntersection(T.tri,primary,target[primary]);
    if(!ints.length)continue;
    let q;
    if(ints.length===1)q=ints[0];
    else q=weightedClosestOnSegment(target,ints[0],ints[1],weights);
    if(side==='left' && Math.sign((q[lrAxis]-bodyCenter[lrAxis])||0)!==leftSign)continue;
    if(side==='right' && Math.sign((q[lrAxis]-bodyCenter[lrAxis])||0)!==-leftSign)continue;
    if(side==='midline' && Math.abs(q[lrAxis]-bodyCenter[lrAxis])>extent[lrAxis]*.035)continue;
    let score=0;
    for(let i=0;i<3;i++)score+=weights[i]*(q[i]-target[i])**2;
    const d=dist2(q,target);
    if(score<bestScore){bestScore=score;bestD=d;best=q;bestPart=T.part;}
  }
  return best?{point:best,distance:Math.sqrt(bestD),part:bestPart}:null;
}
function projectionRegion(text,target){
  // A region envelope prevents a mathematically-near triangle in another body region
  // from stealing a WHO/landmark target. It is deliberately centered on the
  // evidence-derived target rather than on hard-coded atlas coordinates.
  const local=/손목|손등|손바닥|손가락|손허리|발목|발등|발바닥|발가락|발허리|눈|눈썹|귀|귓바퀴|관자|코|입술|턱|목아래오목|목뿔뼈|방패연골|빗장|쇄골|갈비사이공간|늑간|배꼽|뒤엉치뼈구멍|복사/.test(text);
  const regional=/머리|두피|얼굴|가슴|흉부|복부|윗배|아랫배|어깨|팔꿈치|아래팔|위팔|넓적다리|무릎|종아리|정강|볼기|엉치|골반/.test(text);
  const sup=bodyDiag*(local?.055:regional?.085:.11);
  const lr=bodyDiag*(local?.10:.15);
  const ap=bodyDiag*(local?.10:.15);
  return {center:[...target],max:[lrAxis===0?lr:supAxis===0?sup:ap,lrAxis===1?lr:supAxis===1?sup:ap,lrAxis===2?lr:supAxis===2?sup:ap]};
}
function insideProjectionRegion(q,region){
  if(!region)return true;
  for(let i=0;i<3;i++) if(Math.abs(q[i]-region.center[i])>region.max[i]+1e-9)return false;
  return true;
}
function project(target, side, locks={}, region=null){
  if(side==='midline'&&locks.sup){const slice=midlineSliceProjection(target);if(slice&&insideProjectionRegion(slice.point,region))return slice;}
  const exact=constrainedSurfaceProjection(target,side,locks);
  if(exact&&insideProjectionRegion(exact.point,region))return exact;
  const locked=projectLockedToSurface(target,side,locks);
  if(locked&&insideProjectionRegion(locked.point,region))return locked;
  const base=target.map(v=>Math.floor(v/cell)); let best=null,bestD=Infinity,bestScore=Infinity,bestPart=null;
  const consider=T=>{
    const q=closestOnTri(target,...T.tri);
    if(!insideProjectionRegion(q,region))return;
    const sideCoord=q[lrAxis]-bodyCenter[lrAxis];
    if(side==='left' && Math.sign(sideCoord||0)!==leftSign)return;
    if(side==='right' && Math.sign(sideCoord||0)!==-leftSign)return;
    if(side==='midline' && Math.abs(sideCoord)>extent[lrAxis]*.12)return;
    const d=dist2(target,q); let score=d;
    if(locks.sup) score+=5200*(q[supAxis]-target[supAxis])**2;
    if(locks.lr) score+=2400*(q[lrAxis]-target[lrAxis])**2;
    if(locks.ap) score+=420*(q[apAxis]-target[apAxis])**2;
    if(score<bestScore){bestScore=score;bestD=d;best=q;bestPart=T.part;}
  };
  for(let r=0;r<=8;r++){
    let found=false;
    for(let x=-r;x<=r;x++)for(let y=-r;y<=r;y++)for(let z=-r;z<=r;z++){
      if(Math.max(Math.abs(x),Math.abs(y),Math.abs(z))!==r)continue;
      const ids=grid.get([base[0]+x,base[1]+y,base[2]+z].join(','));if(!ids)continue;found=true;
      for(const id of ids)consider(surfaceTriangles[id]);
    }
    if(found&&best&&Math.sqrt(bestD)<(r+1)*cell)break;
  }
  if(!best)for(const T of surfaceTriangles)consider(T);
  if(!best)throw new Error('No anatomically local surface triangle found for projection target '+JSON.stringify(target));
  return {point:best,distance:Math.sqrt(bestD),part:bestPart,constrained:false,regionConstrained:!!region};
}

const relByPoint=new Map();
for(const r of relations){if(!relByPoint.has(r.acupointId))relByPoint.set(r.acupointId,[]);relByPoint.get(r.acupointId).push(r);}
const broad=/muscle of upper limb|muscle of lower limb|upper limb$|lower limb$|neck$|abdomen$|chest$|back$|head$|pelvis$|hand$|foot$/i;
const genericKoTerms=new Set(['근육','뼈','관절','머리','얼굴','목','가슴','복부','배꼽','팔꿈치','손목','손등','손바닥','손가락','발목','발등','발바닥','발가락','무릎','엉치','볼기','오목한곳','중심','중점']);
const localizationTerms=[];
for(const [id,loc] of Object.entries(anatomyKo)){
  if(!partsByConcept.has(id))continue;
  const terms=[loc.nameKo,loc.legacyKo,...(loc.aliases??[])].filter(Boolean);
  for(const raw of new Set(terms)){
    const term=String(raw).replace(/\s+/g,'').replace(/[()]/g,'');
    if(term.length<3||genericKoTerms.has(term))continue;
    localizationTerms.push({id,term});
  }
}

function whoTextLandmarks(text,sideSign){
  const compact=text.replace(/\s+/g,'');
  const hits=[],seen=new Set();
  for(const item of localizationTerms){
    if(seen.has(item.id)||!compact.includes(item.term))continue;
    const st=conceptStats(item.id,sideSign,lrAxis,leftSign)||conceptStats(item.id,0,lrAxis,leftSign);
    if(!st)continue;
    const en=anatomyKo[item.id]?.sourceNameEn||'';
    if(broad.test(en))continue;
    const specificity=Math.max(.2,Math.min(5,bodyDiag/(st.diag*8+1)));
    hits.push({...item,st,score:item.term.length*specificity});
    seen.add(item.id);
  }
  hits.sort((a,b)=>b.score-a.score||b.term.length-a.term.length);
  return hits.slice(0,6);
}
function semanticConceptHits(text,side){
  const sideWord=side==='left'?'left':side==='right'?'right':null;
  const patterns=[];
  if(/엄지(?:손가락)?[^,.]{0,12}끝마디뼈/.test(text))patterns.push(/distal phalanx of (?:left |right )?thumb/i);
  if(/집게손가락[^,.]{0,12}끝마디뼈/.test(text))patterns.push(/distal phalanx of (?:left |right )?index finger/i);
  if(/새끼손가락[^,.]{0,12}끝마디뼈/.test(text))patterns.push(/distal phalanx of (?:left |right )?little finger/i);
  if(/넷째손가락[^,.]{0,12}끝마디뼈/.test(text))patterns.push(/distal phalanx of (?:left |right )?(?:ring|fourth) finger/i);
  if(/가운데손가락\s*끝/.test(text))patterns.push(/(?:left |right )?middle finger$/i);
  if(/둘째발가락[^,.]{0,12}끝마디뼈/.test(text))patterns.push(/distal phalanx of (?:left |right )?(?:second|2nd) toe/i);
  if(/새끼발가락[^,.]{0,12}끝마디뼈/.test(text))patterns.push(/distal phalanx of (?:left |right )?(?:little|fifth|5th) toe/i);
  if(/넷째발가락[^,.]{0,12}끝마디뼈/.test(text))patterns.push(/distal phalanx of (?:left |right )?(?:fourth|4th) toe/i);
  if(/둘째\s*손허리손가락관절/.test(text)){
    patterns.push(/(?:second|2nd).*metacarpophalangeal|metacarpophalangeal.*(?:index|second)/i);
    patterns.push(/proximal phalanx of (?:left |right )?index finger/i);
  }
  if(/다섯째\s*손허리손가락관절/.test(text)){
    patterns.push(/(?:fifth|5th).*metacarpophalangeal|metacarpophalangeal.*(?:little|fifth)/i);
    patterns.push(/proximal phalanx of (?:left |right )?little finger/i);
  }
  if(/둘째와\s*셋째발가락\s*사이/.test(text)){
    patterns.push(/proximal phalanx of (?:left |right )?(?:second|2nd) toe/i);
    patterns.push(/proximal phalanx of (?:left |right )?(?:third|3rd) toe/i);
  }
  if(/넷째와\s*다섯째발가락\s*사이/.test(text)){
    patterns.push(/proximal phalanx of (?:left |right )?(?:fourth|4th) toe/i);
    patterns.push(/proximal phalanx of (?:left |right )?(?:fifth|5th|little) toe/i);
  }
  if(/첫째\s*발허리발가락관절/.test(text))patterns.push(/(?:first|1st).*metatarsophalangeal|metatarsophalangeal.*(?:big|first)/i);
  if(/다섯째\s*발허리발가락관절/.test(text))patterns.push(/(?:fifth|5th).*metatarsophalangeal|metatarsophalangeal.*(?:little|fifth)/i);
  if(/꼭지돌기/.test(text))patterns.push(/mastoid process/i);
  if(/광대활/.test(text))patterns.push(/zygomatic arch/i);
  if(/아래턱뼈/.test(text))patterns.push(/^((?:left|right) )?mandible$|angle of (?:left |right )?mandible|condylar process of (?:left |right )?mandible/i);
  if(/노뼈붓돌기/.test(text))patterns.push(/styloid process of (?:left |right )?radius/i);
  if(/자뼈붓돌기/.test(text))patterns.push(/styloid process of (?:left |right )?ulna/i);
  if(/가쪽위관절융기/.test(text))patterns.push(/lateral epicondyle of (?:left |right )?humerus/i);
  if(/안쪽위관절융기/.test(text))patterns.push(/medial epicondyle of (?:left |right )?humerus/i);
  if(/안쪽복사/.test(text))patterns.push(/medial malleolus/i);
  if(/가쪽복사/.test(text))patterns.push(/lateral malleolus/i);
  if(/봉우리/.test(text))patterns.push(/(?:left |right )?acromion/i);
  if(/부리돌기/.test(text))patterns.push(/coracoid process/i);
  if(/어깨뼈가시/.test(text))patterns.push(/spine of (?:left |right )?scapula/i);
  if(/위앞엉덩뼈가시/.test(text))patterns.push(/anterior superior iliac spine/i);
  if(/큰돌기/.test(text))patterns.push(/greater trochanter/i);
  if(/꼬리뼈/.test(text))patterns.push(/coccyx/i);
  if(/(?:둘째목뼈|C2)/.test(text))patterns.push(/second cervical vertebra|C2 vertebra/i);
  if(/무릎뼈/.test(text))patterns.push(/(?:left |right )?patella/i);
  if(/발꿈치뼈/.test(text))patterns.push(/(?:left |right )?calcaneus/i);
  if(/눈확/.test(text))patterns.push(/(?:left |right )?orbit$/i);
  const hits=[];
  for(const re of patterns){
    let best=null;
    for(const [id,loc] of Object.entries(anatomyKo)){
      const en=loc.sourceNameEn||''; if(!re.test(en)||!partsByConcept.has(id))continue;
      const enLower=en.toLowerCase();
      if(sideWord && /(left|right)/.test(enLower) && !enLower.includes(sideWord))continue;
      const st=conceptStats(id,side==='left'?1:side==='right'?-1:0,lrAxis,leftSign)||conceptStats(id,0,lrAxis,leftSign);
      if(!st)continue;
      const sideBonus=sideWord&&enLower.includes(sideWord)?3:0;
      const score=sideBonus+Math.max(.1,Math.min(4,bodyDiag/(st.diag*7+1)));
      if(!best||score>best.score)best={id,st,score};
    }
    if(best)hits.push(best);
  }
  return hits;
}
function relationTarget(point, side){
  const rels=relByPoint.get(point.id)||[]; const text=point.locationKo||''; let rt=regionTarget(text,side);
  let acc=[0,0,0], wsum=0, specific=0, textLandmarkCount=0, broadAcc=[0,0,0], broadN=0, vertebralSup=[];
  const sideSign=side==='left'?1:side==='right'?-1:0;
  for(const r of rels){
    const st=conceptStats(r.anatomyId,sideSign,lrAxis,leftSign)||conceptStats(r.anatomyId,0,lrAxis,leftSign); if(!st)continue;
    const en=anatomyKo[r.anatomyId]?.sourceNameEn || '';
    const isBroad=broad.test(en);
    if(/^(?:GV9|GV10|GV13|GV15)$/.test(point.id) && /(?:thoracic|cervical) vertebra$/i.test(en)) vertebralSup.push(st.center[supAxis]);
    if(r.relation==='surface-landmark'&&isBroad){
      for(let k=0;k<3;k++)broadAcc[k]+=st.center[k];
      broadN++;continue;
    }
    const relationWeight={adjacent:4,between:4,'deep-to':3.5,overlies:3.5,'reference-landmark':3,'surface-landmark':1}[r.relation]||1;
    const specificity=Math.max(.25,Math.min(4,bodyDiag/(st.diag*9+1)));
    const w=relationWeight*specificity;
    for(let k=0;k<3;k++)acc[k]+=st.center[k]*w; wsum+=w;
    specific++;
  }
  if(broadN){
    const bg=broadAcc.map(v=>v/broadN);
    const base=[...rt];
    rt=bg.map((v,i)=>i===supAxis?base[i]:v*.64+base[i]*.36);
  }
  const textHits=whoTextLandmarks(text,sideSign);
  for(const hit of textHits){
    const w=Math.max(.6,Math.min(4,hit.score/4));
    for(let k=0;k<3;k++)acc[k]+=hit.st.center[k]*w;
    wsum+=w;textLandmarkCount++;
  }
  const semanticHits=semanticConceptHits(text,side);
  for(const hit of semanticHits){
    const w=3.2;
    for(let k=0;k<3;k++)acc[k]+=hit.st.center[k]*w;
    wsum+=w;textLandmarkCount++;
    const en=anatomyKo[hit.id]?.sourceNameEn||'';
    if(/^(?:GV9|GV10|GV13|GV15)$/.test(point.id) && /(?:thoracic|cervical) vertebra$/i.test(en)) vertebralSup.push(hit.st.center[supAxis]);
  }
  const blended=wsum ? (()=>{const g=acc.map(v=>v/wsum),alpha=specific>=2?.82:.68;return g.map((v,i)=>v*alpha+rt[i]*(1-alpha));})() : rt;
  if(vertebralSup.length) blended[supAxis]=vertebralSup.reduce((a,b)=>a+b,0)/vertebralSup.length;
  const who=applyWhoConstraints(blended,text,side,point.id);
  return {target:who.target,specific,rels:rels.length,whoConstraints:who.count,textLandmarkCount};
}

const results=[];
for(const p of acupoints){
  const sides=p.laterality==='midline'?['midline']:['left','right'];
  for(const side of sides){
    const {target,specific,rels,whoConstraints,textLandmarkCount}=relationTarget(p,side);
    if(side==='left' && Math.sign((target[lrAxis]-bodyCenter[lrAxis])||0)!==leftSign) target[lrAxis]=bodyCenter[lrAxis]+leftSign*Math.abs(target[lrAxis]-bodyCenter[lrAxis]);
    if(side==='right' && Math.sign((target[lrAxis]-bodyCenter[lrAxis])||0)!==-leftSign) target[lrAxis]=bodyCenter[lrAxis]-leftSign*Math.abs(target[lrAxis]-bodyCenter[lrAxis]);
    if(side==='midline') target[lrAxis]=bodyCenter[lrAxis];
    const locText=p.locationKo||'';
    const locks={
      sup:(/B-cun/.test(locText)&&/(위로|아래로|위쪽으로|아래쪽으로|몸쪽으로|먼쪽으로|머리선|같은 높이|뒤엉치뼈구멍)/.test(locText))||/갈비사이공간|칼몸통결합|F-cun|귀구슬위패임|귀구슬\s*중심|귀구슬사이패임|발등|발바닥|발가락|발허리|발꿈치|복사|발목|손목|손등|손바닥|손가락|손허리|가쪽눈구석|안쪽눈구석|눈확|광대뼈|광대활|관자부|귓바퀴|꼭지돌기|목아래오목|목뿔뼈|방패연골|빗장아래오목|빗장뼈|쇄골|배꼽/.test(locText),
      lr:side==='midline'||/앞정중선\s*위|가쪽(?:으로)?\s*\d+(?:\.\d+)?\s*B-cun|가쪽배|노뼈와\s*자뼈\s*사이|자뼈\s*바로\s*노쪽|뒤가쪽|앞가쪽|뒤안쪽|앞안쪽|동공|귀구슬|귓바퀴|가쪽눈구석|젖꼭지|중간겨드랑선|손허리|손가락|발허리|발가락|가쪽복사|안쪽복사|무릎뼈의\s*아래가쪽|무릎인대\s*가쪽/.test(locText),
      ap:/손바닥|손등|발바닥|발등|손허리|손가락|발허리|발가락|어깨뼈\s*부위|어깨세모근|가쪽눈구석|관자부|앞가슴|아랫배|복부|배꼽|앞정중선/.test(locText)
    };
    const region=projectionRegion(locText,target);
    const projected=project(target,side,locks,region);
    const sideExpected=side==='left'?leftSign:side==='right'?-leftSign:0;
    const lateral=(projected.point[lrAxis]-bodyCenter[lrAxis]);
    const sideOk=side==='midline'?Math.abs(lateral)<=extent[lrAxis]*.12:Math.sign(lateral||0)===sideExpected;
    const surfaceOk=Number.isFinite(projected.distance);
    const evidence=specific+whoConstraints+Math.min(2,textLandmarkCount); const confidence=evidence>=3?'high':evidence>=1?'moderate':'low';
    results.push({
      acupointId:p.id,side,position:projected.point.map(v=>+v.toFixed(4)),model:'BodyParts3D-4.0',status:'validated',
      method:'WHO+reviewed-local-cun-solver+B-landmarks+laterality+surface-projection',confidence,
      validation:{surfaceProjected:surfaceOk,lateralityConsistent:sideOk,projectionDistance:+projected.distance.toFixed(4),projectionDelta:projected.point.map((v,i)=>+(v-target[i]).toFixed(4)),regionConstrained:true,surfacePartId:projected.part,preProjectionTarget:target.map(v=>+v.toFixed(4)),relationCount:rels,specificLandmarkCount:specific,whoConstraintCount:whoConstraints,whoTextLandmarkCount:textLandmarkCount},
      sourceIds:['WHO_ACUPOINT_2008','BODY_PARTS_3D_4','TARA_ACUPOINT_CURATED']
    });
  }
}
const resultByKey=new Map(results.map(x=>[x.acupointId+':'+x.side,x]));
const acupointById=new Map(acupoints.map(x=>[x.id,x]));

function applyReviewedExceptionProjection(item){
  const sideSign=item.side==='left'?leftSign:item.side==='right'?-leftSign:0;
  const mark=(target,locks,rule)=>{
    const text=acupointById.get(item.acupointId)?.locationKo||'';
    const pr=project(target,item.side,locks,projectionRegion(text,target));
    item.position=pr.point.map(v=>+v.toFixed(4));
    item.validation.projectionDistance=+pr.distance.toFixed(4);
    item.validation.projectionDelta=pr.point.map((v,i)=>+(v-target[i]).toFixed(4));
    item.validation.regionConstrained=true;
    item.validation.surfacePartId=pr.part;
    item.validation.preProjectionTarget=target.map(v=>+v.toFixed(4));
    item.validation.reviewedException=rule;
  };

  if(item.acupointId==='CV1'){
    const anus=conceptStats('FMA21930',0,lrAxis,leftSign);
    const perineal=conceptStats('FMA19728',0,lrAxis,leftSign)||conceptStats('FMA9623',0,lrAxis,leftSign);
    if(anus&&perineal){
      const target=anus.center.map((v,i)=>(v+perineal.center[i])/2);
      target[lrAxis]=bodyCenter[lrAxis];
      mark(target,{lr:true},'reviewed-CV1-external-anal-sphincter-perineal-muscle-midpoint');
      return true;
    }
  }

  if(item.acupointId==='BL67'){
    const p1=resultByKey.get('BL66:'+item.side),p2=resultByKey.get('BL65:'+item.side);
    if(p1&&p2){
      const target=p1.position.map((v,i)=>v+(p1.position[i]-p2.position[i])*1.15);
      mark(target,{sup:true,lr:true},'reviewed-BL67-distal-continuation-from-BL65-BL66');
      return true;
    }
  }
  if(item.acupointId==='GB44'){
    const p1=resultByKey.get('GB43:'+item.side),p2=resultByKey.get('GB42:'+item.side);
    if(p1&&p2){
      const target=p1.position.map((v,i)=>v+(p1.position[i]-p2.position[i])*.55);
      mark(target,{sup:true,lr:true},'reviewed-GB44-distal-continuation-from-GB42-GB43');
      return true;
    }
  }
  if(item.acupointId==='GB7'){
    const target=[...item.validation.preProjectionTarget];
    mark(target,{sup:true,ap:true},'reviewed-GB7-temporal-hairline');
    return true;
  }
  if(item.acupointId==='GB8'){
    const gb7=resultByKey.get('GB7:'+item.side);
    if(gb7){
      const target=[...gb7.position];
      target[supAxis]+=1.5*cunY;
      mark(target,{sup:true,ap:true},'reviewed-GB8-1.5-cun-superior-to-GB7-hairline-level');
      return true;
    }
  }

  if(item.acupointId==='ST43'){
    const proximal=resultByKey.get('ST42:'+item.side), distal=resultByKey.get('ST44:'+item.side);
    if(proximal&&distal){
      const target=proximal.position.map((v,i)=>v*.40+distal.position[i]*.60);
      mark(target,{sup:true,lr:true},'reviewed-ST43-between-ST42-ST44');
      return true;
    }
  }
  if(item.acupointId==='GB41'){
    const ankle=resultByKey.get('GB40:'+item.side),web=resultByKey.get('GB43:'+item.side);
    if(ankle&&web){
      const target=ankle.position.map((v,i)=>v*.62+web.position[i]*.38);
      mark(target,{sup:true,lr:true},'reviewed-GB41-between-GB40-GB43');
      return true;
    }
  }
  if(item.acupointId==='GB42'){
    const gb41=resultByKey.get('GB41:'+item.side),gb43=resultByKey.get('GB43:'+item.side);
    if(gb41&&gb43){
      const f=.70;
      const target=gb41.position.map((v,i)=>v*(1-f)+gb43.position[i]*f);
      mark(target,{sup:true,lr:true},'reviewed-GB42-between-GB41-GB43');
      return true;
    }
  }
  if(item.acupointId==='BL63'){
    const ankle=resultByKey.get('BL62:'+item.side), distal=resultByKey.get('BL64:'+item.side);
    if(ankle&&distal){
      const target=ankle.position.map((v,i)=>v*.62+distal.position[i]*.38);
      mark(target,{sup:true,lr:true},'reviewed-BL63-between-BL62-BL64');
      return true;
    }
  }

  if(item.acupointId==='TE4'){
    const distal=resultByKey.get('TE3:'+item.side);
    const proximal=resultByKey.get('TE5:'+item.side);
    if(distal&&proximal){
      const target=distal.position.map((v,i)=>v*.55+proximal.position[i]*.45);
      mark(target,{sup:true,lr:true},'reviewed-wrist-between-TE3-TE5');
      return true;
    }
  }

  if(item.acupointId==='LR10'){
    const st30=resultByKey.get('ST30:'+item.side);
    if(st30){
      const target=[...st30.position];
      target[supAxis]-=3*cunY;
      mark(target,{sup:true,lr:true},'reviewed-LR10-3-cun-distal-to-ST30');
      item.confidence='moderate';
      return true;
    }
  }

  if(item.acupointId==='GV15'){
    const gv16=resultByKey.get('GV16:midline');
    if(gv16){
      const target=[...item.validation.preProjectionTarget];
      target[lrAxis]=bodyCenter[lrAxis];
      target[supAxis]=gv16.position[supAxis]-.5*cunY;
      mark(target,{sup:true},'reviewed-GV15-0.5-cun-inferior-to-GV16');
      return true;
    }
  }
  if(item.acupointId==='TE6'){
    const te5=resultByKey.get('TE5:'+item.side),scale=solverCun('TE6',item.side,'proximal','B-cun')??solverCun('TE6',item.side,'superior','B-cun');
    if(te5&&scale){const target=[...te5.position];target[supAxis]+=scale;mark(target,{sup:true,lr:true},'reviewed-TE6-one-cun-proximal-from-TE5-on-posterior-interosseous-line');return true;}
  }
  if(item.acupointId==='SP6'){
    const ki8=resultByKey.get('KI8:'+item.side),scale=solverCun('SP6',item.side,'superior','B-cun');
    if(ki8&&scale){const target=[...ki8.position];target[supAxis]+=scale;mark(target,{sup:true,lr:true},'reviewed-SP6-one-cun-superior-to-KI8-on-posterior-medial-tibial-border');return true;}
  }
  if(item.acupointId==='SP21'){
    const lr14=resultByKey.get('LR14:'+item.side);
    if(lr14){const target=[...lr14.position];target[lrAxis]+=sideSign*bodyDiag*.035;target[apAxis]-=anteriorSign*bodyDiag*.008;mark(target,{sup:true,lr:true},'reviewed-SP21-midaxillary-sixth-intercostal-lateral-to-LR14');return true;}
  }
  return false;
}
for(const item of results) applyReviewedExceptionProjection(item);
function updateFromRelativeDefinition(item,text){
  const pair=text.match(/([A-Z]{1,2}\d+)\s*(?:와|과)\s*([A-Z]{1,2}\d+)(?:을|를)\s*잇는\s*(?:곡선|선)/);
  if(!pair)return false;
  const a=resultByKey.get(pair[1]+':'+item.side), b=resultByKey.get(pair[2]+':'+item.side);
  if(!a||!b)return false;
  let target=null,rule=null;
  if(/중점/.test(text)){target=a.position.map((v,i)=>(v+b.position[i])/2);rule='relative-midpoint';}
  const vertical=text.match(/위쪽\s*(\d+)\/(\d+)(?:와|과)\s*아래쪽\s*(\d+)\/(\d+)\s*경계/);
  if(vertical){
    const f=Number(vertical[1])/Number(vertical[2]);
    const upper=a.position[supAxis]>=b.position[supAxis]?a:b, lower=upper===a?b:a;
    target=upper.position.map((v,i)=>v*(1-f)+lower.position[i]*f);rule='relative-vertical-fraction';
  }
  const lateral=text.match(/가쪽\s*(\d+)\/(\d+)(?:와|과)\s*안쪽\s*(\d+)\/(\d+)\s*경계/);
  if(lateral){
    const f=Number(lateral[1])/Number(lateral[2]);
    const outer=Math.abs(a.position[lrAxis]-bodyCenter[lrAxis])>=Math.abs(b.position[lrAxis]-bodyCenter[lrAxis])?a:b;
    const inner=outer===a?b:a;
    target=outer.position.map((v,i)=>v*(1-f)+inner.position[i]*f);rule='relative-lateral-fraction';
  }
  if(!target)return false;
  const pr=project(target,item.side,{sup:true,lr:true},projectionRegion(text,target));
  item.position=pr.point.map(v=>+v.toFixed(4));
  item.validation.projectionDistance=+pr.distance.toFixed(4);
  item.validation.projectionDelta=pr.point.map((v,i)=>+(v-target[i]).toFixed(4));
  item.validation.regionConstrained=true;
  item.validation.surfacePartId=pr.part;
  item.validation.preProjectionTarget=target.map(v=>+v.toFixed(4));
  item.validation.relativeConstraint=rule;
  if(item.confidence==='low')item.confidence='moderate';
  return true;
}
for(const item of results){
  const text=acupointById.get(item.acupointId)?.locationKo||'';
  updateFromRelativeDefinition(item,text);
}
for(const item of results){
  if(item.acupointId==='GB11'){
    const sideSign=item.side==='left'?leftSign:item.side==='right'?-leftSign:0;
    const target=[...item.position];
    target[apAxis]-=anteriorSign*bodyDiag*.008;
    target[supAxis]+=bodyDiag*.003;
    const text=acupointById.get(item.acupointId)?.locationKo||'';
    const pr=project(target,item.side,{sup:true,ap:true},projectionRegion(text,target));
    item.position=pr.point.map(v=>+v.toFixed(4));
    item.validation.projectionDistance=+pr.distance.toFixed(4);
    item.validation.projectionDelta=pr.point.map((v,i)=>+(v-target[i]).toFixed(4));
    item.validation.regionConstrained=true;
    item.validation.surfacePartId=pr.part;
    item.validation.preProjectionTarget=target.map(v=>+v.toFixed(4));
    item.validation.reviewedException='reviewed-GB11-posterosuperior-to-mastoid-separate-from-TE18';
  }
}

const modelLimitationKeys=new Set([
  'GB28:left','GB28:right','BL65:left','BL65:right','BL66:left','BL66:right',
  'TE17:left','TE17:right','LI1:left','LI1:right','BL53:left','BL53:right',
  'BL54:left','BL54:right','GB10:left','GB10:right','GB12:left','GB12:right',
  'GB29:left','GB29:right','LI9:left','LI10:left','LI10:right','GV18:midline',
  'PC7:left','PC7:right','CV17:midline','BL39:right','LI5:left','LI5:right',
  'LR4:left','LR4:right','GB32:left','GB32:right'
]);
const reviewNeededIds=new Set(['LU5','BL40','LR9','KI13','KI14','KI15','LR10','HT7']);
for(const item of results){
  const key=item.acupointId+':'+item.side;
  if(modelLimitationKeys.has(key)){
    item.status='model-limitation';
    item.validation.visualAuditDisposition='model-limitation';
  }else if(reviewNeededIds.has(item.acupointId)){
    item.status='review-needed';
    item.validation.visualAuditDisposition='review-needed';
  }else{
    item.status='validated';
    item.validation.visualAuditDisposition='validated';
  }
}

function pointToBoundsDistance(point,st){
  let d2=0;
  for(let i=0;i<3;i++){
    const d=point[i]<st.min[i]?st.min[i]-point[i]:point[i]>st.max[i]?point[i]-st.max[i]:0;
    d2+=d*d;
  }
  return Math.sqrt(d2);
}
function postValidateLandmarks(item){
  const sideSign=item.side==='left'?leftSign:item.side==='right'?-leftSign:0;
  const issues=[]; let maxDistance=0,checked=0;
  for(const r of relByPoint.get(item.acupointId)??[]){
    const st=conceptStats(r.anatomyId,sideSign,lrAxis,leftSign)||conceptStats(r.anatomyId,0,lrAxis,leftSign);
    const en=anatomyKo[r.anatomyId]?.sourceNameEn||'';
    if(!st||broad.test(en))continue;
    const d=pointToBoundsDistance(item.position,st); checked++; maxDistance=Math.max(maxDistance,d);
    const reviewTol=Math.max(bodyDiag*.07,Math.min(bodyDiag*.14,st.diag*1.4+bodyDiag*.025));
    const failTol=Math.max(bodyDiag*.13,Math.min(bodyDiag*.20,st.diag*2.2+bodyDiag*.04));
    const strong=/^(?:adjacent|between|overlies|deep-to|surface-landmark)$/.test(r.relation);
    if(d>reviewTol)issues.push({anatomyId:r.anatomyId,relation:r.relation,distance:+d.toFixed(4),reviewTolerance:+reviewTol.toFixed(4),fail:strong&&d>failTol});
  }
  const hard=issues.some(x=>x.fail);
  item.validation.landmarkPostValidation={status:hard?'fail':issues.length?'review':'pass',checked,maxDistance:+maxDistance.toFixed(4),issues};
  return hard;
}
const landmarkHardFailures=[];
for(const item of results)if(postValidateLandmarks(item))landmarkHardFailures.push(item.acupointId+':'+item.side);

function topologyValidation(){
  const grouped=new Map();
  for(const item of results){
    const m=item.acupointId.match(/^([A-Z]+)(\d+)$/); if(!m)continue;
    const key=m[1]+':'+item.side;
    const list=grouped.get(key)??[]; list.push({...item,n:Number(m[2])}); grouped.set(key,list);
  }
  const reviews=[],hard=[];
  const distance=(a,b)=>Math.sqrt(dist2(a.position,b.position));
  for(const [key,list] of grouped){
    list.sort((a,b)=>a.n-b.n);
    for(let i=1;i<list.length-1;i++){
      if(list[i-1].n+1!==list[i].n||list[i].n+1!==list[i+1].n)continue;
      const a=list[i-1],b=list[i],c=list[i+1];
      const ab=distance(a,b),bc=distance(b,c),ac=distance(a,c);
      const ratio=(ab+bc)/Math.max(ac,bodyDiag*.003);
      if(ratio>4.5){
        const row={key,id:b.acupointId,side:b.side,ratio:+ratio.toFixed(3),previous:a.acupointId,next:c.acupointId,distances:{previous:+ab.toFixed(4),next:+bc.toFixed(4),shortcut:+ac.toFixed(4)},hard:ratio>10&&Math.max(ab,bc)>bodyDiag*.16};
        reviews.push(row); if(row.hard)hard.push(b.acupointId+':'+b.side);
      }
    }
  }
  return {reviews,hard};
}
const topology=topologyValidation();
for(const item of results){
  const hit=topology.reviews.find(x=>x.id===item.acupointId&&x.side===item.side);
  item.validation.topologyValidation=hit?{status:hit.hard?'fail':'review',...hit}:{status:'pass'};
}
const expected=acupoints.reduce((n,p)=>n+(p.laterality==='midline'?1:2),0);
if(results.length!==expected)throw new Error('Physical point count mismatch');
const invalid=results.filter(x=>!x.validation.surfaceProjected||!x.validation.lateralityConsistent);
const coordKey=x=>x.position.map(v=>Math.round(v/(bodyDiag*0.0008))).join(',');
const dup=new Map(); for(const x of results){const k=x.side+':'+coordKey(x);if(!dup.has(k))dup.set(k,[]);dup.get(k).push(x.acupointId);}
const duplicateClusters=[...dup.values()].filter(v=>v.length>1);
const exactMap=new Map();
for(const x of results){const k=x.side+':'+x.position.join(',');if(!exactMap.has(k))exactMap.set(k,[]);exactMap.get(k).push(x.acupointId);}
const exactDuplicateClusters=[...exactMap.values()].filter(v=>v.length>1);
const out={version:1,model:'BodyParts3D-4.0',generatedAt:new Date().toISOString(),coordinateFrame:{source:'native BodyParts3D 4.0 atlas coordinates',axes:{superiorInferior:supAxis,leftRight:lrAxis,anteriorPosterior:apAxis},signs:{left:leftSign,anterior:anteriorSign}},methodology:{primary:'WHO 2008 location text',anatomyConstraints:'anatomy-acupoint-relations.json (B)',laterality:'bilateral points generated independently by side; GV/CV retained on midline',projection:'nearest point on actual integumentary mesh triangle, not bounding-box or vertex-only snapping',measurementScale:'reviewed acupoint-coordinate-solver v2; Skin FJ2810 geodesic for medial-malleolus-to-sole interval; no global body-height cun'},points:results};
fs.writeFileSync(new URL('public/knowledge/acupoint-coordinates.json',root),JSON.stringify(out,null,2)+'\n');
const sortedProjection=results.slice().sort((a,b)=>b.validation.projectionDistance-a.validation.projectionDistance);
const manualReviewQueue=sortedProjection.filter((x,i)=>i<Math.ceil(results.length*.05)||x.validation.landmarkPostValidation.status==='review'||x.validation.topologyValidation.status==='review').map(x=>({acupointId:x.acupointId,side:x.side,projectionDistance:x.validation.projectionDistance,projectionDelta:x.validation.projectionDelta,landmarkStatus:x.validation.landmarkPostValidation.status,topologyStatus:x.validation.topologyValidation.status}));
const statusCounts=results.reduce((m,x)=>(m[x.status]=(m[x.status]||0)+1,m),{});
const audit={generatedAt:new Date().toISOString(),logicalAcupoints:acupoints.length,physicalCoordinates:results.length,expectedPhysicalCoordinates:expected,surfaceTriangleCount:surfaceTriangles.length,integumentaryPartCount:surfaceParts.length,invalidGeometryOrLaterality:invalid.map(x=>x.acupointId+':'+x.side),duplicateClusters,exactDuplicateClusters,confidenceCounts:results.reduce((m,x)=>(m[x.confidence]=(m[x.confidence]||0)+1,m),{}),statusCounts,projectionDistance:{max:Math.max(...results.map(x=>x.validation.projectionDistance)),mean:results.reduce((n,x)=>n+x.validation.projectionDistance,0)/results.length},spatialValidation:{regionConstrained:results.every(x=>x.validation.regionConstrained),landmarkHardFailures,landmarkReviewCount:results.filter(x=>x.validation.landmarkPostValidation.status==='review').length,topologyHardFailures:topology.hard,topologyReviewCount:topology.reviews.length,manualReviewQueue,nonValidatedReviewQueue:results.filter(x=>x.status!=='validated').map(x=>({acupointId:x.acupointId,side:x.side,status:x.status,landmarkStatus:x.validation.landmarkPostValidation.status,topologyStatus:x.validation.topologyValidation.status}))},axes:out.coordinateFrame,bodyBounds:{min:bodyMin,max:bodyMax,center:bodyCenter,extent,bodyDiag}};
fs.writeFileSync(new URL('public/knowledge/acupoint-coordinates-audit.json',root),JSON.stringify(audit,null,2)+'\n');
if(invalid.length||duplicateClusters.length||exactDuplicateClusters.length||landmarkHardFailures.length||topology.hard.length){
  throw new Error('Spatial validation failed: '+JSON.stringify({invalid:invalid.map(x=>x.acupointId+':'+x.side),duplicateClusters,exactDuplicateClusters,landmarkHardFailures,topologyHardFailures:topology.hard}));
}
if(exactDuplicateClusters.length){console.error('EXACT_DUPLICATE_COORDINATES',JSON.stringify(exactDuplicateClusters,null,2));throw new Error('Coordinate validation failed: '+exactDuplicateClusters.length+' exact duplicate clusters');}
if(invalid.length){console.error('INVALID_COORDINATES',JSON.stringify(invalid.map(x=>({id:x.acupointId,side:x.side,position:x.position,validation:x.validation})),null,2));throw new Error('Coordinate validation failed: '+invalid.length+' side/surface errors');}
console.log(JSON.stringify(audit,null,2));
