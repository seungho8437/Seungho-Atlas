import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const readJson=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const atlas=readJson('public/models/atlas.json');
const coords=readJson('public/knowledge/acupoint-coordinates.json');
const audit=readJson('public/knowledge/acupoint-coordinates-audit.json');
const chunks=atlas.chunks.map(c=>fs.readFileSync(new URL('public/models/'+c.url.split('/').pop(),root)));
const surface=atlas.parts.filter(p=>p.system==='integumentary');
const axes=audit.axes.axes,{leftRight:lr,superiorInferior:sup,anteriorPosterior:ap}=axes;
const bounds=audit.bodyBounds,diag=bounds.bodyDiag;
const pos=p=>new Float32Array(chunks[p.chunk].buffer,chunks[p.chunk].byteOffset+p.positions,p.vertexCount*3);
const point=(id,side)=>coords.points.find(p=>p.acupointId===id&&p.side===side);
const sides=id=>coords.points.filter(p=>p.acupointId===id).map(p=>p.side);
const unique=a=>[...new Set(a)], distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));

const defs=[
 ['BL35','low-confidence',['BL35'],'꼬리뼈 끝에서 가쪽 0.5 B-cun: 꼬리뼈/볼기 영역 체표에 있어야 한다.'],
 ['BL36','low-confidence',['BL36'],'볼기주름 중점: 좌우 볼기 아래 경계 체표에 있어야 한다.'],
 ['GB28','low-confidence',['GB28'],'ASIS의 안쪽·아래쪽 0.5 B-cun: 하복부-서혜부 경계에 있어야 한다.'],
 ['GB29','low-confidence',['GB29'],'ASIS-큰돌기 연결선 중점: 가쪽 골반/볼기 영역에 있어야 한다.'],
 ['ST17_GB23','former-near-cluster',['ST17','GB23'],'같은 제4늑간 높이지만 GB23이 ST17보다 가쪽이어야 한다.'],
 ['ST43_GB42','former-near-cluster',['ST43','GB42'],'GB42(4-5 발허리뼈 사이)가 ST43(2-3 사이)보다 가쪽이어야 한다.'],
 ['BL62_KI4','former-near-cluster',['BL62','KI4'],'BL62는 가쪽복사 아래, KI4는 안쪽복사 뒤아래로 분리되어야 한다.'],
 ['BL63_GB41','former-near-cluster',['BL63','GB41'],'BL63은 가쪽/뒤쪽 발, GB41은 발등 4-5 발허리뼈 바닥 먼쪽으로 분리되어야 한다.'],
 ['TE3_TE4','former-near-cluster',['TE3','TE4'],'TE3은 손허리뼈 사이, TE4는 손목주름으로 손-손목 축에서 분리되어야 한다.'],
 ['GV9_GV10','former-near-cluster',['GV9','GV10'],'GV10(T6)가 GV9(T7)보다 위쪽이어야 한다.'],
 ['GV13_GV15','former-near-cluster',['GV13','GV15'],'GV15(C2)는 GV13(T1)보다 위쪽이고 GV16보다 아래쪽이어야 한다.']
].map(([key,kind,ids,expected])=>({key,kind,ids,expected}));

function evaluate(d){
  const records=d.ids.flatMap(id=>coords.points.filter(p=>p.acupointId===id));
  const common=d.ids.length===2?unique(sides(d.ids[0]).filter(s=>sides(d.ids[1]).includes(s))):[];
  const pairDistances=common.map(side=>({side,distance:+distance(point(d.ids[0],side).position,point(d.ids[1],side).position).toFixed(4)}));
  let directional=true;
  if(d.key==='ST17_GB23') directional=common.every(s=>Math.abs(point('GB23',s).position[lr])>Math.abs(point('ST17',s).position[lr]));
  if(d.key==='ST43_GB42') directional=common.every(s=>Math.abs(point('GB42',s).position[lr])>Math.abs(point('ST43',s).position[lr]));
  if(d.key==='BL62_KI4') directional=common.every(s=>Math.abs(point('BL62',s).position[lr])>Math.abs(point('KI4',s).position[lr]));
  if(d.key==='GV9_GV10') directional=point('GV10','midline').position[sup]>point('GV9','midline').position[sup];
  if(d.key==='GV13_GV15') directional=point('GV15','midline').position[sup]>point('GV13','midline').position[sup]&&point('GV15','midline').position[sup]<point('GV16','midline').position[sup];
  const surfaceOk=records.every(p=>p.validation.surfaceProjected&&p.validation.lateralityConsistent);
  const separated=pairDistances.every(x=>x.distance>diag*.01);
  const confidence=records.map(p=>p.confidence);
  const lowGone=d.kind!=='low-confidence'||confidence.every(x=>x!=='low');
  const modelCaveat=d.kind==='low-confidence'&&records.some(p=>(p.validation.specificLandmarkCount||0)===0);
  const quarantined=records.some(p=>p.status==='review-needed');
  const pass=surfaceOk&&separated&&directional&&lowGone;
  return {...d,status:pass?(modelCaveat?'accepted-with-model-caveat':'pass'):(quarantined?'quarantined-review-needed':'review-required'),
    surfaceAndLaterality:surfaceOk,directionalConstraint:directional,separationThreshold:+(diag*.01).toFixed(4),
    pairDistances,confidence,projectionDistances:records.map(p=>({id:p.acupointId,side:p.side,distance:p.validation.projectionDistance})),
    caveat:modelCaveat?'WHO textual constraints and BodyParts3D surface projection carry this localization because no specific B-landmark mesh was counted.':null};
}
const reviews=defs.map(evaluate), reviewedIds=unique(defs.flatMap(d=>d.ids));
const report={version:1,generatedAt:new Date().toISOString(),
  scope:'Focused visual/anatomical exception review: four formerly low-confidence acupoints plus seven formerly near-duplicate clusters.',
  coordinateModel:coords.model,reviewedLogicalAcupoints:reviewedIds.length,reviewedGroups:reviews.length,
  checks:{allReviewedPointsPresent:reviewedIds.every(id=>coords.points.some(p=>p.acupointId===id)),
    invalidGeometryOrLaterality:audit.invalidGeometryOrLaterality,globalNearDuplicateClusters:audit.duplicateClusters,
    globalExactDuplicateClusters:audit.exactDuplicateClusters,
    formerlyLowConfidenceNowLow:defs.filter(d=>d.kind==='low-confidence').flatMap(d=>d.ids).flatMap(id=>coords.points.filter(p=>p.acupointId===id&&p.confidence==='low').map(p=>id+':'+p.side))},
  reviews};
fs.writeFileSync(new URL('public/knowledge/acupoint-coordinate-exception-review.json',root),JSON.stringify(report,null,2)+'\n');

const samples=[];
for(const p of surface){const a=pos(p),stride=Math.max(3,Math.floor(a.length/3/4500)*3);for(let i=0;i<a.length;i+=stride)samples.push([a[i],a[i+1],a[i+2]]);}
function silhouette(axis){
  const n=180,loY=bounds.min[sup],hiY=bounds.max[sup],rows=Array.from({length:n},()=>({lo:Infinity,hi:-Infinity}));
  for(const v of samples){const b=Math.max(0,Math.min(n-1,Math.floor((v[sup]-loY)/(hiY-loY)*n)));rows[b].lo=Math.min(rows[b].lo,v[axis]);rows[b].hi=Math.max(rows[b].hi,v[axis]);}
  const lo=[],hi=[];rows.forEach((r,i)=>{if(Number.isFinite(r.lo)){const y=loY+(i+.5)/n*(hiY-loY);lo.push([r.lo,y]);hi.push([r.hi,y]);}});return{lo,hi};
}
const W=1600,H=1840,front=silhouette(lr),side=silhouette(ap);
const panels=[{x:70,y:120,w:680,h:790,axis:lr,title:'Front projection',sil:front},{x:850,y:120,w:680,h:790,axis:ap,title:'Side projection',sil:side}];
const sx=(p,v)=>p.x+(v-bounds.min[p.axis])/(bounds.max[p.axis]-bounds.min[p.axis])*p.w;
const sy=(p,v)=>p.y+p.h-(v-bounds.min[sup])/(bounds.max[sup]-bounds.min[sup])*p.h;
const path=(p,a)=>a.map((q,i)=>(i?'L':'M')+sx(p,q[0]).toFixed(1)+' '+sy(p,q[1]).toFixed(1)).join(' ');
let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="100%" height="100%" fill="white"/><style>text{font-family:Arial,'Noto Sans KR',sans-serif;fill:#111}.t{font-size:28px;font-weight:700}.s{font-size:15px}.p{fill:none;stroke:#bbb}.o{fill:none;stroke:#777;stroke-width:1.2}.d{fill:#111}.l{font-size:12px;font-weight:700}.r{font-size:14px}.b{font-weight:700}</style><text x="70" y="55" class="t">Acupoint coordinate exception review</text><text x="70" y="84" class="s">BodyParts3D surface silhouette + reviewed exception coordinates</text>`;
for(const p of panels){
  svg+=`<rect class="p" x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}"/><text x="${p.x}" y="${p.y-14}" class="s">${p.title}</text><path class="o" d="${path(p,p.sil.lo)}"/><path class="o" d="${path(p,p.sil.hi)}"/>`;
  for(const id of reviewedIds)for(const q of coords.points.filter(x=>x.acupointId===id)){const x=sx(p,q.position[p.axis]),y=sy(p,q.position[sup]);svg+=`<circle class="d" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.2"/>`;if(q.side==='left'||q.side==='midline')svg+=`<text class="l" x="${(x+5).toFixed(1)}" y="${(y-4).toFixed(1)}">${esc(id)}</text>`;}
}
svg+=`<text x="70" y="970" class="t" style="font-size:22px">Group findings</text>`;let y=1010;
for(const r of reviews){const ds=r.pairDistances.length?' · d='+r.pairDistances.map(x=>x.side+':'+x.distance).join(', '):'';svg+=`<text x="70" y="${y}" class="r b">${esc(r.key)} — ${esc(r.status)}${esc(ds)}</text>`;y+=22;svg+=`<text x="92" y="${y}" class="r">${esc(r.expected)}</text>`;y+=26;}
svg+=`<text x="70" y="${H-55}" class="s">Global QC: near clusters ${audit.duplicateClusters.length}; exact duplicates ${audit.exactDuplicateClusters.length}; invalid geometry/laterality ${audit.invalidGeometryOrLaterality.length}. Model-level anatomical QC; not cadaveric/imaging validation.</text></svg>`;
fs.writeFileSync(new URL('public/knowledge/acupoint-coordinate-exception-review.svg',root),svg);
const reviewRequired=report.reviews.filter(r=>r.status==='review-required');
if(reviewRequired.length)throw new Error('Focused acupoint exception review failed: '+JSON.stringify(reviewRequired.map(r=>r.key)));
console.log(JSON.stringify({reviewedGroups:reviews.length,statuses:reviews.reduce((m,r)=>(m[r.status]=(m[r.status]||0)+1,m),{}),quarantinedGroups:reviews.filter(r=>r.status==='quarantined-review-needed').length},null,2));
