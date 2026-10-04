import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const atlas=read('public/models/atlas.json');
const coords=read('public/knowledge/acupoint-coordinates.json');
const audit=read('public/knowledge/acupoint-coordinates-audit.json');
const acupoints=read('public/knowledge/acupoints.json');
const relations=read('public/knowledge/anatomy-acupoint-relations.json');
const anatomyKo=read('public/knowledge/anatomy-ko.json');

const outDir=new URL('artifacts/acupoint-visual-audit/',root);
fs.rmSync(outDir,{recursive:true,force:true});fs.mkdirSync(outDir,{recursive:true});
const chunks=atlas.chunks.map(c=>fs.readFileSync(new URL('public/models/'+c.url.split('/').pop(),root)));
const partsById=new Map(atlas.parts.map(p=>[p.id,p]));
const partsByConcept=new Map();
for(const c of atlas.concepts){const ps=(c.elements??[]).map(id=>partsById.get(id)).filter(Boolean);if(ps.length)partsByConcept.set(c.id,ps);}
for(const p of atlas.parts){const ps=partsByConcept.get(p.conceptId)??[];if(!ps.some(x=>x.id===p.id))ps.push(p);partsByConcept.set(p.conceptId,ps);}
const axes=audit.axes.axes,{leftRight:lr,superiorInferior:sup,anteriorPosterior:ap}=axes;
const bounds=audit.bodyBounds,diag=bounds.bodyDiag;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const pos=p=>new Float32Array(chunks[p.chunk].buffer,chunks[p.chunk].byteOffset+p.positions,p.vertexCount*3);
const coordMap=new Map(coords.points.map(p=>[p.acupointId+':'+p.side,p]));
const acuMap=new Map(acupoints.map(p=>[p.id,p]));
const relMap=new Map();
for(const r of relations){const a=relMap.get(r.acupointId)??[];a.push(r);relMap.set(r.acupointId,a);}

const surfaceParts=atlas.parts.filter(p=>p.system==='integumentary');
const surfaceSamples=[];
for(const p of surfaceParts){const a=pos(p),step=Math.max(3,Math.floor((a.length/3)/1200)*3);for(let i=0;i<a.length;i+=step)surfaceSamples.push([a[i],a[i+1],a[i+2]]);}

function conceptSamples(id,limit=1000){
 const out=[];for(const p of partsByConcept.get(id)??[]){const a=pos(p),step=Math.max(3,Math.floor((a.length/3)/Math.max(50,limit/(partsByConcept.get(id)?.length||1)))*3);for(let i=0;i<a.length;i+=step)out.push([a[i],a[i+1],a[i+2]]);}return out.slice(0,limit);
}
function rangeFor(points,a1,a2,pad=.08){
 let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;
 for(const p of points){x0=Math.min(x0,p[a1]);x1=Math.max(x1,p[a1]);y0=Math.min(y0,p[a2]);y1=Math.max(y1,p[a2]);}
 if(!Number.isFinite(x0)){x0=bounds.min[a1];x1=bounds.max[a1];y0=bounds.min[a2];y1=bounds.max[a2];}
 const dx=Math.max((x1-x0)*pad,diag*.018),dy=Math.max((y1-y0)*pad,diag*.018);
 return [x0-dx,x1+dx,y0-dy,y1+dy];
}
function panel({x,y,w,h,title,a1,a2,range,surface=[],landmarks=[],point,pre,neighbors=[]}){
 const [x0,x1,y0,y1]=range,sx=v=>x+(v-x0)/(x1-x0)*w,sy=v=>y+h-(v-y0)/(y1-y0)*h;
 let z=`<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#fbfbfb" stroke="#bbb"/><text x="${x}" y="${y-10}" class="st">${esc(title)}</text>`;
 for(const q of surface)if(q[a1]>=x0&&q[a1]<=x1&&q[a2]>=y0&&q[a2]<=y1)z+=`<circle cx="${sx(q[a1]).toFixed(1)}" cy="${sy(q[a2]).toFixed(1)}" r="0.65" fill="#d2d5d8"/>`;
 landmarks.forEach((L,j)=>{const col=['#008c95','#7b61a8','#a36b00','#2774ae','#7b4b2a','#337a42'][j%6];for(const q of L.samples)if(q[a1]>=x0&&q[a1]<=x1&&q[a2]>=y0&&q[a2]<=y1)z+=`<circle cx="${sx(q[a1]).toFixed(1)}" cy="${sy(q[a2]).toFixed(1)}" r="1.25" fill="${col}" opacity=".62"/>`;});
 for(const n of neighbors){z+=`<circle cx="${sx(n.position[a1]).toFixed(1)}" cy="${sy(n.position[a2]).toFixed(1)}" r="5" fill="#6253a6"/><text x="${(sx(n.position[a1])+6).toFixed(1)}" y="${(sy(n.position[a2])-5).toFixed(1)}" class="lab">${esc(n.acupointId)}</text>`;}
 if(pre)z+=`<line x1="${sx(pre[a1]).toFixed(1)}" y1="${sy(pre[a2]).toFixed(1)}" x2="${sx(point.position[a1]).toFixed(1)}" y2="${sy(point.position[a2]).toFixed(1)}" stroke="#e38a22" stroke-width="2"/><circle cx="${sx(pre[a1]).toFixed(1)}" cy="${sy(pre[a2]).toFixed(1)}" r="5" fill="none" stroke="#e38a22" stroke-width="2"/>`;
 z+=`<circle cx="${sx(point.position[a1]).toFixed(1)}" cy="${sy(point.position[a2]).toFixed(1)}" r="7" fill="#c2262d" stroke="white" stroke-width="2"/><text x="${(sx(point.position[a1])+9).toFixed(1)}" y="${(sy(point.position[a2])-7).toFixed(1)}" class="pt">${esc(point.acupointId)} ${esc(point.side)}</text>`;
 return z;
}
function neighborsOf(point){
 const m=point.acupointId.match(/^([A-Z]+)(\d+)$/);if(!m)return[];
 const mer=m[1],n=Number(m[2]),out=[];
 for(const k of [n-1,n+1]){const p=coordMap.get(mer+k+':'+point.side);if(p)out.push(p);}return out;
}
function detailSvg(point,index){
 const acu=acuMap.get(point.acupointId),rels=relMap.get(point.acupointId)??[];
 const landmarks=rels.filter(r=>partsByConcept.has(r.anatomyId)).slice(0,6).map(r=>({r,samples:conceptSamples(r.anatomyId,800)}));
 const neighbors=neighborsOf(point),pre=point.validation.preProjectionTarget;
 const localPoints=[point.position,pre,...neighbors.map(n=>n.position),...landmarks.flatMap(x=>x.samples)];
 const localFront=rangeFor(localPoints,lr,sup,.10),localSide=rangeFor(localPoints,ap,sup,.10);
 const fullFront=[bounds.min[lr],bounds.max[lr],bounds.min[sup],bounds.max[sup]],fullSide=[bounds.min[ap],bounds.max[ap],bounds.min[sup],bounds.max[sup]];
 let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1200" viewBox="0 0 1600 1200"><rect width="100%" height="100%" fill="white"/><style>text{font-family:Arial,'Noto Sans KR',sans-serif;fill:#171717}.title{font-size:28px;font-weight:700}.meta{font-size:16px}.st{font-size:16px;font-weight:700}.lab{font-size:13px}.pt{font-size:14px;font-weight:700}.rel{font-size:14px}</style>`;
 svg+=`<text x="45" y="42" class="title">${esc(point.acupointId)} · ${esc(acu?.name?.ko)} · ${esc(point.side)} — visual audit ${index+1}</text>`;
 svg+=`<text x="45" y="70" class="meta">projectionDistance=${point.validation.projectionDistance} · landmark=${esc(point.validation.landmarkPostValidation?.status)} · topology=${esc(point.validation.topologyValidation?.status)} · confidence=${esc(point.confidence)}</text>`;
 svg+=panel({x:45,y:115,w:720,h:430,title:'LOCAL FRONT (LR × SI)',a1:lr,a2:sup,range:localFront,surface:surfaceSamples,landmarks,point,pre,neighbors});
 svg+=panel({x:835,y:115,w:720,h:430,title:'LOCAL SIDE (AP × SI)',a1:ap,a2:sup,range:localSide,surface:surfaceSamples,landmarks,point,pre,neighbors});
 svg+=panel({x:45,y:610,w:720,h:430,title:'FULL FRONT',a1:lr,a2:sup,range:fullFront,surface:surfaceSamples,landmarks,point,pre,neighbors});
 svg+=panel({x:835,y:610,w:720,h:430,title:'FULL SIDE',a1:ap,a2:sup,range:fullSide,surface:surfaceSamples,landmarks,point,pre,neighbors});
 svg+=`<text x="45" y="1080" class="meta">WHO: ${esc(acu?.locationKo)}</text>`;
 let yy=1106;for(const L of landmarks){const a=anatomyKo[L.r.anatomyId];svg+=`<text x="65" y="${yy}" class="rel">• ${esc(L.r.relation)} — ${esc(a?.nameKo||a?.sourceNameEn||L.r.anatomyId)} (${esc(L.r.anatomyId)})</text>`;yy+=20;if(yy>1180)break;}
 return svg+'</svg>';
}

const high=audit.spatialValidation.manualReviewQueue.map(q=>coordMap.get(q.acupointId+':'+q.side)).filter(Boolean);
const detailFiles=[];
high.forEach((p,i)=>{const name=`detail-${String(i+1).padStart(3,'0')}-${p.acupointId}-${p.side}.svg`;fs.writeFileSync(new URL(name,outDir),detailSvg(p,i));detailFiles.push(name);});

const meridians=[...new Set(acupoints.map(x=>x.meridian))];
function sweepSvg(meridian){
 const pts=coords.points.filter(p=>p.acupointId.startsWith(meridian)&&/^([A-Z]+)\d+$/.test(p.acupointId));
 const W=1600,H=1050;
 const fullFront=[bounds.min[lr],bounds.max[lr],bounds.min[sup],bounds.max[sup]],fullSide=[bounds.min[ap],bounds.max[ap],bounds.min[sup],bounds.max[sup]];
 const draw=(x,y,w,h,a1,a2,range,title)=>{
  const [x0,x1,y0,y1]=range,sx=v=>x+(v-x0)/(x1-x0)*w,sy=v=>y+h-(v-y0)/(y1-y0)*h;
  let z=`<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#fbfbfb" stroke="#bbb"/><text x="${x}" y="${y-12}" class="st">${title}</text>`;
  for(const q of surfaceSamples)z+=`<circle cx="${sx(q[a1]).toFixed(1)}" cy="${sy(q[a2]).toFixed(1)}" r=".55" fill="#d5d7da"/>`;
  for(const side of ['left','right','midline']){const spts=pts.filter(p=>p.side===side).sort((a,b)=>Number(a.acupointId.match(/\d+/)?.[0])-Number(b.acupointId.match(/\d+/)?.[0]));
   if(spts.length>1)z+=`<polyline fill="none" stroke="#7f8c99" stroke-width="1.4" points="${spts.map(p=>sx(p.position[a1]).toFixed(1)+','+sy(p.position[a2]).toFixed(1)).join(' ')}"/>`;
   for(const p of spts){z+=`<circle cx="${sx(p.position[a1]).toFixed(1)}" cy="${sy(p.position[a2]).toFixed(1)}" r="4.5" fill="#c2262d"/><text x="${(sx(p.position[a1])+5).toFixed(1)}" y="${(sy(p.position[a2])-4).toFixed(1)}" class="lab">${p.acupointId}</text>`;}}
  return z;
 };
 let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="100%" height="100%" fill="white"/><style>text{font-family:Arial,'Noto Sans KR',sans-serif;fill:#171717}.title{font-size:30px;font-weight:700}.st{font-size:17px;font-weight:700}.lab{font-size:10px;font-weight:700}</style><text x="45" y="45" class="title">${meridian} meridian — full coordinate sweep (${pts.length} physical points)</text>`;
 svg+=draw(45,105,720,850,lr,sup,fullFront,'FRONT / LR × SI');
 svg+=draw(835,105,720,850,ap,sup,fullSide,'SIDE / AP × SI');
 return svg+'</svg>';
}
const sweepFiles=[];for(const m of meridians){const name=`sweep-${m}.svg`;fs.writeFileSync(new URL(name,outDir),sweepSvg(m));sweepFiles.push(name);}

const contactFiles=[];
for(let i=0;i<high.length;i+=4){
  const batch=high.slice(i,i+4);
  let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="3200" height="2400" viewBox="0 0 3200 2400"><rect width="100%" height="100%" fill="white"/>`;
  batch.forEach((p,j)=>{
    const inner=detailSvg(p,i+j).replace(/^<svg[^>]*>/,'').replace(/<\/svg>$/,'');
    const x=(j%2)*1600,y=Math.floor(j/2)*1200;
    svg+=`<g transform="translate(${x} ${y})">${inner}</g>`;
  });
  svg+='</svg>';
  const name=`contact-high-risk-${String(i/4+1).padStart(2,'0')}.svg`;
  fs.writeFileSync(new URL(name,outDir),svg);contactFiles.push(name);
}

const manifest={generatedAt:new Date().toISOString(),coordinateGeneratedAt:coords.generatedAt,highRiskCount:high.length,detailFiles,contactFiles,sweepFiles,coverage:{physicalCoordinates:coords.points.length,logicalAcupoints:acupoints.length,meridians}};
fs.writeFileSync(new URL('manifest.json',outDir),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify({highRisk:detailFiles.length,sweeps:sweepFiles.length,outDir:'artifacts/acupoint-visual-audit'},null,2));
