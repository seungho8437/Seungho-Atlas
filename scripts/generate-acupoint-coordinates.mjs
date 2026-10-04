import fs from 'node:fs';

const root = new URL('../', import.meta.url);
const readJson = p => JSON.parse(fs.readFileSync(new URL(p, root), 'utf8'));
const atlas = readJson('public/models/atlas.json');
const acupoints = readJson('public/knowledge/acupoints.json');
const relations = readJson('public/knowledge/anatomy-acupoint-relations.json');
const anatomyKo = readJson('public/knowledge/anatomy-ko.json');

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

const regionRules = [
  [/vertex|머리꼭대기|정수리|두정부|머리 위/, .97, .50],
  [/forehead|이마|눈썹|미간|코|입술|턱|얼굴|눈|귀|관자/, .91, .82],
  [/occip|뒤통수|후두|뒷머리/, .91, .18],
  [/neck|목|경부|목덜미/, .82, .52],
  [/shoulder|어깨|견갑|빗장|쇄골/, .76, .58],
  [/chest|가슴|흉부|갈비|늑간|유두/, .69, .78],
  [/upper abdomen|윗배|상복부|명치/, .59, .76],
  [/abdomen|배꼽|복부|배 부위/, .50, .77],
  [/pelvis|샅|회음|두덩|치골|엉덩|볼기|천골/, .38, .50],
  [/upper arm|위팔|상완/, .66, .60],
  [/elbow|팔꿈치|주와/, .55, .58],
  [/forearm|아래팔|전완/, .47, .58],
  [/wrist|손목/, .38, .60],
  [/hand|손등|손바닥|손가락|엄지|새끼손가락/, .32, .64],
  [/thigh|넓적다리|대퇴/, .31, .53],
  [/knee|무릎|오금|슬부/, .20, .50],
  [/leg|종아리|정강|하퇴/, .12, .52],
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
  t[lrAxis]=bodyCenter[lrAxis]+s*(extent[lrAxis]/2)*lateralFrac;
  return t;
}

const cunY=extent[supAxis]/75;
const ordinalIntercostal={첫째:1,둘째:2,셋째:3,넷째:4,다섯째:5,여섯째:6,일곱째:7};
function applyWhoConstraints(input,text,side){
  const t=[...input]; let count=0;
  const sideSign=side==='left'?leftSign:side==='right'?-leftSign:0;
  const lateral=text.match(/정중선[^,.]{0,45}?가쪽(?:으로)?\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(lateral&&sideSign){
    const n=Number(lateral[1]);
    const frac=Math.min(.92,n/6*.84);
    t[lrAxis]=bodyCenter[lrAxis]+sideSign*(extent[lrAxis]/2)*frac;
    count++;
  }
  const nav=text.match(/배꼽(?:\s*중심)?(?:보다|에서)?\s*(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/);
  if(nav){
    const n=Number(nav[2]), navel=norm(supAxis,.455);
    t[supAxis]=nav[1]==='위'?navel+n*cunY:navel-n*cunY;
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
    [/손바닥쪽\s*손목주름[^,.]{0,35}?(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/, .385],
    [/손등쪽\s*손목주름[^,.]{0,35}?(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/, .385],
    [/팔오금주름[^,.]{0,35}?(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/, .55],
    [/무릎뼈바닥[^,.]{0,35}?(위|아래)로\s*(\d+(?:\.\d+)?)\s*B-cun/, .215],
    [/ST35[^,.]{0,35}?(위|아래)(?:쪽)?으로\s*(\d+(?:\.\d+)?)\s*B-cun/, .20],
    [/팔꿈치머리\s*융기[^,.]{0,35}?(몸쪽|먼쪽|위|아래)으로\s*(\d+(?:\.\d+)?)\s*B-cun/, .55],
  ];
  for(const [re,base] of refs){
    const m=text.match(re); if(!m)continue;
    const n=Number(m[2]), up=(m[1]==='위'||m[1]==='몸쪽');
    t[supAxis]=norm(supAxis,base)+(up?1:-1)*n*cunY; count++; break;
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
function project(target, side){
  const base=target.map(v=>Math.floor(v/cell)); let best=null,bestD=Infinity,bestPart=null;
  for(let r=0;r<=8;r++){
    let found=false;
    for(let x=-r;x<=r;x++)for(let y=-r;y<=r;y++)for(let z=-r;z<=r;z++){
      if(Math.max(Math.abs(x),Math.abs(y),Math.abs(z))!==r)continue;
      const ids=grid.get([base[0]+x,base[1]+y,base[2]+z].join(',')); if(!ids)continue; found=true;
      for(const id of ids){const T=surfaceTriangles[id];
        if(side==='left' && Math.sign((T.c[lrAxis]-bodyCenter[lrAxis])||0)!==leftSign) continue;
        if(side==='right' && Math.sign((T.c[lrAxis]-bodyCenter[lrAxis])||0)!==-leftSign) continue;
        const q=closestOnTri(target,...T.tri);
        if(side==='left' && Math.sign((q[lrAxis]-bodyCenter[lrAxis])||0)!==leftSign) continue;
        if(side==='right' && Math.sign((q[lrAxis]-bodyCenter[lrAxis])||0)!==-leftSign) continue;
        const d=dist2(target,q);if(d<bestD){bestD=d;best=q;bestPart=T.part;}}
    }
    if(found && best && Math.sqrt(bestD) < (r+1)*cell) break;
  }
  if(!best){for(const T of surfaceTriangles){
    if(side==='left' && Math.sign((T.c[lrAxis]-bodyCenter[lrAxis])||0)!==leftSign) continue;
    if(side==='right' && Math.sign((T.c[lrAxis]-bodyCenter[lrAxis])||0)!==-leftSign) continue;
    const q=closestOnTri(target,...T.tri);
    if(side==='left' && Math.sign((q[lrAxis]-bodyCenter[lrAxis])||0)!==leftSign) continue;
    if(side==='right' && Math.sign((q[lrAxis]-bodyCenter[lrAxis])||0)!==-leftSign) continue;
    const d=dist2(target,q);if(d<bestD){bestD=d;best=q;bestPart=T.part;}}}
  return {point:best,distance:Math.sqrt(bestD),part:bestPart};
}

const relByPoint=new Map();
for(const r of relations){if(!relByPoint.has(r.acupointId))relByPoint.set(r.acupointId,[]);relByPoint.get(r.acupointId).push(r);}
const broad=/muscle of upper limb|muscle of lower limb|neck$|abdomen$|chest$|back$|head$|pelvis$|hand$|foot$/i;
function relationTarget(point, side){
  const rels=relByPoint.get(point.id)||[]; const text=point.locationKo||''; const rt=regionTarget(text,side);
  let acc=[0,0,0], wsum=0, specific=0;
  const sideSign=side==='left'?1:side==='right'?-1:0;
  for(const r of rels){
    const st=conceptStats(r.anatomyId,sideSign,lrAxis,leftSign)||conceptStats(r.anatomyId,0,lrAxis,leftSign); if(!st)continue;
    const en=anatomyKo[r.anatomyId]?.sourceNameEn || '';
    const isBroad=broad.test(en);
    if(r.relation==='surface-landmark'&&isBroad) continue;
    const relationWeight={adjacent:4,between:4,'deep-to':3.5,overlies:3.5,'reference-landmark':3,'surface-landmark':1}[r.relation]||1;
    const specificity=Math.max(.25,Math.min(4,bodyDiag/(st.diag*9+1)));
    const w=relationWeight*specificity;
    for(let k=0;k<3;k++)acc[k]+=st.center[k]*w; wsum+=w;
    specific++;
  }
  const blended=wsum ? (()=>{const g=acc.map(v=>v/wsum),alpha=specific>=2?.82:.68;return g.map((v,i)=>v*alpha+rt[i]*(1-alpha));})() : rt;
  const who=applyWhoConstraints(blended,text,side);
  return {target:who.target,specific,rels:rels.length,whoConstraints:who.count};
}

const results=[];
for(const p of acupoints){
  const sides=p.laterality==='midline'?['midline']:['left','right'];
  for(const side of sides){
    const {target,specific,rels,whoConstraints}=relationTarget(p,side);
    if(side==='left' && Math.sign((target[lrAxis]-bodyCenter[lrAxis])||0)!==leftSign) target[lrAxis]=bodyCenter[lrAxis]+leftSign*Math.abs(target[lrAxis]-bodyCenter[lrAxis]);
    if(side==='right' && Math.sign((target[lrAxis]-bodyCenter[lrAxis])||0)!==-leftSign) target[lrAxis]=bodyCenter[lrAxis]-leftSign*Math.abs(target[lrAxis]-bodyCenter[lrAxis]);
    if(side==='midline') target[lrAxis]=bodyCenter[lrAxis];
    const projected=project(target,side);
    const sideExpected=side==='left'?leftSign:side==='right'?-leftSign:0;
    const lateral=(projected.point[lrAxis]-bodyCenter[lrAxis]);
    const sideOk=side==='midline'?Math.abs(lateral)<=extent[lrAxis]*.12:Math.sign(lateral||0)===sideExpected;
    const surfaceOk=Number.isFinite(projected.distance);
    const confidence=(specific>=2||whoConstraints>=2)?'high':(specific===1||whoConstraints===1)?'moderate':'low';
    results.push({
      acupointId:p.id,side,position:projected.point.map(v=>+v.toFixed(4)),model:'BodyParts3D-4.0',status:'validated',
      method:'WHO+B-landmarks+laterality+surface-projection',confidence,
      validation:{surfaceProjected:surfaceOk,lateralityConsistent:sideOk,projectionDistance:+projected.distance.toFixed(4),surfacePartId:projected.part,relationCount:rels,specificLandmarkCount:specific,whoConstraintCount:whoConstraints},
      sourceIds:['WHO_ACUPOINT_2008','BODY_PARTS_3D_4','TARA_ACUPOINT_CURATED']
    });
  }
}
const expected=acupoints.reduce((n,p)=>n+(p.laterality==='midline'?1:2),0);
if(results.length!==expected)throw new Error('Physical point count mismatch');
const invalid=results.filter(x=>!x.validation.surfaceProjected||!x.validation.lateralityConsistent);
const coordKey=x=>x.position.map(v=>Math.round(v/(bodyDiag*0.0008))).join(',');
const dup=new Map(); for(const x of results){const k=x.side+':'+coordKey(x);if(!dup.has(k))dup.set(k,[]);dup.get(k).push(x.acupointId);}
const duplicateClusters=[...dup.values()].filter(v=>v.length>1);
const out={version:1,model:'BodyParts3D-4.0',generatedAt:new Date().toISOString(),coordinateFrame:{source:'native BodyParts3D 4.0 atlas coordinates',axes:{superiorInferior:supAxis,leftRight:lrAxis,anteriorPosterior:apAxis},signs:{left:leftSign,anterior:anteriorSign}},methodology:{primary:'WHO 2008 location text',anatomyConstraints:'anatomy-acupoint-relations.json (B)',laterality:'bilateral points generated independently by side; GV/CV retained on midline',projection:'nearest point on actual integumentary mesh triangle, not bounding-box or vertex-only snapping'},points:results};
fs.writeFileSync(new URL('public/knowledge/acupoint-coordinates.json',root),JSON.stringify(out,null,2)+'\n');
const audit={generatedAt:new Date().toISOString(),logicalAcupoints:acupoints.length,physicalCoordinates:results.length,expectedPhysicalCoordinates:expected,surfaceTriangleCount:surfaceTriangles.length,integumentaryPartCount:surfaceParts.length,invalidGeometryOrLaterality:invalid.map(x=>x.acupointId+':'+x.side),duplicateClusters,confidenceCounts:results.reduce((m,x)=>(m[x.confidence]=(m[x.confidence]||0)+1,m),{}),projectionDistance:{max:Math.max(...results.map(x=>x.validation.projectionDistance)),mean:results.reduce((n,x)=>n+x.validation.projectionDistance,0)/results.length},axes:out.coordinateFrame};
fs.writeFileSync(new URL('public/knowledge/acupoint-coordinates-audit.json',root),JSON.stringify(audit,null,2)+'\n');
if(invalid.length){console.error('INVALID_COORDINATES',JSON.stringify(invalid.map(x=>({id:x.acupointId,side:x.side,position:x.position,validation:x.validation})),null,2));throw new Error('Coordinate validation failed: '+invalid.length+' side/surface errors');}
console.log(JSON.stringify(audit,null,2));
