import fs from 'node:fs';
import zlib from 'node:zlib';
import crypto from 'node:crypto';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const write=(p,v)=>{const u=new URL(p,root);fs.mkdirSync(new URL('./',u),{recursive:true});fs.writeFileSync(u,JSON.stringify(v,null,2)+'\n');};
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const FROZEN_B_SHA='6dd00d386a6262d02900ec5a30ea9b18aace899f071159e772c12679740b1d06';
const now=new Date().toISOString();

const packed=Buffer.from(fs.readFileSync(new URL('scripts/data/anatomy-acupoint-relations-v1.json.gz.b64.txt',root),'utf8').trim(),'base64');
const graphBytes=zlib.gunzipSync(packed); if(hash(graphBytes)!==FROZEN_B_SHA)throw new Error('frozen B SHA mismatch');
const graph=JSON.parse(graphBytes.toString('utf8'));
const atlas=read('public/models/atlas.json');
const v1real=read('public/knowledge/acupoint-bodyparts3d-realization.json');
const v1coords=read('public/knowledge/acupoint-coordinates.json');
const solver=read('public/knowledge/acupoint-coordinate-solver.json');
const anchors=read('public/knowledge/acupoint-specialized-landmark-anchors.json');
const derived=read('public/knowledge/acupoint-derived-surface-landmarks.json');
const auditV1=read('public/knowledge/acupoint-coordinate-v1-error-attribution-audit.json');

const partById=new Map(atlas.parts.map(x=>[x.id,x]));
const conceptById=new Map(atlas.concepts.map(x=>[x.id,x]));
const partsByConcept=new Map();
for(const p of atlas.parts){const a=partsByConcept.get(p.conceptId)||[];a.push(p);partsByConcept.set(p.conceptId,a);}
const chunks=atlas.chunks.map(c=>fs.readFileSync(new URL('public/models/'+c.url.split('/').pop(),root)));
const posArr=p=>{const b=chunks[p.chunk];return new Float32Array(b.buffer,b.byteOffset+p.positions,p.vertexCount*3);};
const idxArr=p=>{const b=chunks[p.chunk];return new Uint32Array(b.buffer,b.byteOffset+p.indices,p.indexCount);};
function vertices(parts){const out=[];for(const p of parts||[]){const a=posArr(p);for(let i=0;i<a.length;i+=3)out.push([a[i],a[i+1],a[i+2]]);}return out;}
function stats(parts){const vs=vertices(parts);if(!vs.length)return null;const min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity],sum=[0,0,0];for(const v of vs)for(let k=0;k<3;k++){min[k]=Math.min(min[k],v[k]);max[k]=Math.max(max[k],v[k]);sum[k]+=v[k];}return {vertices:vs,min,max,center:sum.map(x=>x/vs.length),extent:max.map((x,i)=>x-min[i])};}
const skin=partById.get('FJ2810'); if(!skin)throw new Error('Skin FJ2810 missing');
const skinPos=posArr(skin),skinIdx=idxArr(skin),skinStats=stats([skin]);
const frame=derived.coordinateFrame;
const sup=frame.superiorInferiorAxis,lr=frame.leftRightAxis,ap=frame.anteriorPosteriorAxis,leftSign=frame.leftSign,antSign=frame.anteriorSign;
const bodyDiag=Math.hypot(...skinStats.extent);
const mid=skinStats.center;
const sideSign=s=>s==='left'?leftSign:s==='right'?-leftSign:0;
const distance=(a,b)=>Math.hypot(...a.map((v,i)=>v-b[i]));
const add=(a,b)=>a.map((v,i)=>v+b[i]),sub=(a,b)=>a.map((v,i)=>v-b[i]),mul=(a,s)=>a.map(v=>v*s);
const lerp=(a,b,t)=>a.map((v,i)=>v+(b[i]-v)*t);
const dot=(a,b)=>a.reduce((n,v,i)=>n+v*b[i],0);
const norm=a=>Math.hypot(...a);
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));

function pointTriangleClosest(p,a,b,c){
 const ab=sub(b,a),ac=sub(c,a),apv=sub(p,a),d1=dot(ab,apv),d2=dot(ac,apv);
 if(d1<=0&&d2<=0)return a;
 const bp=sub(p,b),d3=dot(ab,bp),d4=dot(ac,bp);if(d3>=0&&d4<=d3)return b;
 const vc=d1*d4-d3*d2;if(vc<=0&&d1>=0&&d3<=0){const v=d1/(d1-d3);return add(a,mul(ab,v));}
 const cp=sub(p,c),d5=dot(ab,cp),d6=dot(ac,cp);if(d6>=0&&d5<=d6)return c;
 const vb=d5*d2-d1*d6;if(vb<=0&&d2>=0&&d6<=0){const w=d2/(d2-d6);return add(a,mul(ac,w));}
 const va=d3*d6-d5*d4;if(va<=0&&(d4-d3)>=0&&(d5-d6)>=0){const w=(d4-d3)/((d4-d3)+(d5-d6));return add(b,mul(sub(c,b),w));}
 const denom=1/(va+vb+vc),v=vb*denom,w=vc*denom;return add(a,add(mul(ab,v),mul(ac,w)));
}
function projectSkin(target,side,{levelTol=bodyDiag*.08,regionCenter=null}={}){
 let best=null,bestD=Infinity,bestTri=-1;const ss=sideSign(side);
 for(let i=0;i<skinIdx.length;i+=3){
  const ids=[skinIdx[i],skinIdx[i+1],skinIdx[i+2]],vs=ids.map(q=>[skinPos[q*3],skinPos[q*3+1],skinPos[q*3+2]]);
  const cen=[0,1,2].map(k=>(vs[0][k]+vs[1][k]+vs[2][k])/3);
  if(ss && (cen[lr]-mid[lr])*ss<0)continue;
  if(side==='midline'&&Math.abs(cen[lr]-mid[lr])>skinStats.extent[lr]*.12)continue;
  if(regionCenter&&Math.abs(cen[sup]-regionCenter[sup])>levelTol)continue;
  const q=pointTriangleClosest(target,...vs),d=distance(target,q);if(d<bestD){bestD=d;best=q;bestTri=i/3;}
 }
 return best?{point:best,distance:bestD,triangleIndex:bestTri,meshId:'FJ2810'}:null;
}
function conceptParts(id,side=null){
 let ps=partsByConcept.get(id)||[]; if(!side)return ps;
 const re=side==='left'?/^left\b/i:/^right\b/i; const xs=ps.filter(p=>re.test(p.name));return xs.length?xs:ps.filter(p=>!/^(left|right)\b/i.test(p.name));
}
function conceptFeature(id,side,feature='center'){
 const st=stats(conceptParts(id,side));if(!st)return null;
 if(feature==='center')return st.center;
 const axis=feature.includes('superior')?sup:feature.includes('inferior')?sup:feature.includes('anterior')?ap:feature.includes('posterior')?ap:feature.includes('lateral')?lr:feature.includes('medial')?lr:null;
 if(axis==null)return null;
 let mode='max';
 if(feature.includes('inferior'))mode='min';
 if(feature.includes('posterior'))mode=antSign>0?'min':'max';
 if(feature.includes('anterior'))mode=antSign>0?'max':'min';
 if(feature.includes('lateral'))mode=sideSign(side)>0?'max':'min';
 if(feature.includes('medial'))mode=sideSign(side)>0?'min':'max';
 return st.vertices.reduce((best,v)=>!best||((mode==='max'?v[axis]>best[axis]:v[axis]<best[axis]))?v:best,null);
}

const accepted=new Map((anchors.records||[]).filter(x=>x.reviewStatus==='accepted').map(x=>[x.landmarkId,x]));
const derivedMap=new Map((derived.landmarks||[]).map(x=>[x.landmarkId,x]));
function existingAnchor(id,side){
 const a=accepted.get(id);if(a?.position)return {position:a.position,provenance:{kind:'accepted_specialized_anchor',id,method:a.method,surfaceProjection:a.surfaceProjection}};
 const d=derivedMap.get(id),g=d?.geometry;if(!g)return null;
 const s=g.sides?.[side];if(s?.position)return {position:s.position,provenance:{kind:'derived_geometry_v1',id,status:d.status,method:s.method||d.construction||null}};
 if(Array.isArray(g.position))return {position:g.position,provenance:{kind:'derived_geometry_v1',id,status:d.status,method:d.construction||null}};
 return null;
}
function correctedSuprasternal(){
 const st=stats(conceptParts('FMA7485')); if(!st)return null;
 const near=st.vertices.filter(v=>Math.abs(v[lr]-mid[lr])<skinStats.extent[lr]*.03);
 const src=near.length?near:st.vertices;const b=src.reduce((a,v)=>!a||v[sup]>a[sup]?v:a,null);
 const q=projectSkin(b,'midline',{levelTol:bodyDiag*.03,regionCenter:b});return q?{position:q.point,provenance:{kind:'v2_corrected_anchor',id:'suprasternal-notch',method:'superior sternum boundary nearest midline -> anterior Skin projection',sourceConcept:'FMA7485',surface:q}}:null;
}
function correctedPubic(){
 const cps=atlas.concepts.filter(c=>/pubic bone|pubis/i.test(c.name)&&!/^region/i.test(c.name));
 const vs=cps.flatMap(c=>vertices(partsByConcept.get(c.id)||[]));if(!vs.length)return null;
 const top=vs.reduce((m,v)=>Math.max(m,v[sup]),-Infinity),bottom=vs.reduce((m,v)=>Math.min(m,v[sup]),Infinity);
 const candidates=vs.filter(v=>v[sup]>bottom+(top-bottom)*.55).sort((a,b)=>Math.abs(a[lr]-mid[lr])-Math.abs(b[lr]-mid[lr]));
 const medial=candidates.slice(0,Math.max(20,Math.ceil(candidates.length*.03)));if(!medial.length)return null;
 const y=Math.max(...medial.map(v=>v[sup]));const guide=[mid[lr],y,0];guide[ap]=Math.max(...medial.map(v=>v[ap]*antSign))*antSign;
 const q=projectSkin(guide,'midline',{levelTol:bodyDiag*.04,regionCenter:guide});return q?{position:q.point,provenance:{kind:'v2_corrected_anchor',id:'superior-border-pubic-symphysis',method:'bilateral pubic-bone superomedial boundary -> anterior midline Skin',sourceConcepts:cps.map(c=>c.id),surface:q}}:null;
}
function correctedTibiaFeature(side,which){
 const c=atlas.concepts.find(x=>new RegExp('^'+side+' tibia$','i').test(x.name));if(!c)return null;const st=stats(partsByConcept.get(c.id)||[]);if(!st)return null;
 const lo=st.min[sup],hi=st.max[sup],ss=sideSign(side);let candidates;
 if(which==='medial-condyle-inferior'){
  const y0=hi-(hi-lo)*.18;candidates=st.vertices.filter(v=>Math.abs(v[sup]-y0)<(hi-lo)*.04);
  if(!candidates.length)candidates=st.vertices.filter(v=>v[sup]>hi-(hi-lo)*.25);
  const medMode=ss>0?'min':'max';const p=candidates.reduce((a,v)=>!a||((medMode==='min'?v[lr]<a[lr]:v[lr]>a[lr]))?v:a,null);
  return p?{position:p,provenance:{kind:'v2_corrected_anchor',id:'inferior-border-medial-condyle-tibia',method:'side-specific proximal tibia medial-condyle inferior band',sourceConcept:c.id}}:null;
 }
 if(which==='medial-malleolus'){
  candidates=st.vertices.filter(v=>v[sup]<lo+(hi-lo)*.22);const medMode=ss>0?'min':'max';const p=candidates.reduce((a,v)=>!a||((medMode==='min'?v[lr]<a[lr]:v[lr]>a[lr]))?v:a,null);
  return p?{position:p,provenance:{kind:'v2_corrected_anchor',id:'prominence-medial-malleolus',method:'side-specific distal tibia medial extremum',sourceConcept:c.id}}:null;
 }
 return null;
}
function anchorPos(id,side){
 if(id==='suprasternal-notch')return correctedSuprasternal();
 if(id==='superior-border-pubic-symphysis')return correctedPubic();
 if(id==='inferior-border-medial-condyle-tibia')return correctedTibiaFeature(side,'medial-condyle-inferior');
 if(id==='prominence-medial-malleolus')return correctedTibiaFeature(side,'medial-malleolus');
 return existingAnchor(id,side);
}

const solverByPoint=new Map((solver.records||[]).map(x=>[x.acupointId,x]));
const calibrationAudit=[];
const scaleByFrameSide=new Map();
for(const rec of solver.records||[])for(const f of rec.measurementFrames||[])for(const ss of f.sideScales||[]){
 if(!['left','right','midline'].includes(ss.side))continue;
 const chosen=ss.chosen;if(!chosen)continue;const A=anchorPos(chosen.from,ss.side),B=anchorPos(chosen.to,ss.side);
 let interval=null,scale=null;
 if(A&&B){
  const d=sub(B.position,A.position);
  if(f.calibration?.axis==='longitudinal')interval=Math.abs(d[sup]);
  else if(f.calibration?.axis==='transverse')interval=Math.abs(d[lr]);
  else interval=distance(A.position,B.position);
  scale=interval/(f.calibration?.cun||1);
 }
 const row={point_id:rec.acupointId,frame_id:f.id,side:ss.side,calibration_id:f.selectedCalibrationId,from:chosen.from,to:chosen.to,axis:f.calibration?.axis,expected_cun:f.calibration?.cun,interval,model_unit_per_cun:scale,endpoint_provenance:{from:A?.provenance||null,to:B?.provenance||null},status:'candidate',issues:[]};
 if(!A||!B)row.issues.push('endpoint_unresolved');
 if(scale!=null&&scale<bodyDiag*.003)row.issues.push('implausibly_small_vs_model');
 if(scale!=null&&scale>bodyDiag*.04)row.issues.push('implausibly_large_vs_model');
 calibrationAudit.push(row);scaleByFrameSide.set(f.id+':'+ss.side,row);
}
const validScales=calibrationAudit.filter(x=>x.model_unit_per_cun&&!x.issues.length).map(x=>x.model_unit_per_cun).sort((a,b)=>a-b);
const medScale=validScales[Math.floor(validScales.length/2)]||null;
for(const x of calibrationAudit){
 if(x.model_unit_per_cun&&medScale){x.ratio_to_global_sanity_median=x.model_unit_per_cun/medScale;if(x.ratio_to_global_sanity_median<.35||x.ratio_to_global_sanity_median>3.0)x.issues.push('cross_frame_ratio_outlier');}
 x.status=x.issues.length?'blocked':'usable';
}

const v1RealById=new Map(v1real.landmark_realizations.map(x=>[x.node_id,x]));
const geomById=new Map(graph.geometry_nodes.map(x=>[x.node_id,x]));
const graphLandmarkById=new Map(graph.landmark_nodes.map(x=>[x.node_id,x]));
const relByPoint=new Map();for(const r of graph.relation_instances){const id=String(r.subject_node_id||'').replace(/^P:/,'');const a=relByPoint.get(id)||[];a.push(r);relByPoint.set(id,a);}
const sourceById=new Map(graph.source_statements.map(x=>[x.source_statement_id,x]));
const bBlockPoints=new Set(auditV1.frozen_B_structural_coordinate_audit?.affected_points||[]);

function parseFraction(s){s=String(s||'').toLowerCase();const m=s.match(/(\d+)\s*\/\s*(\d+)/);if(m)return +m[1]/+m[2];const map={'one half':.5,'half':.5,'one third':1/3,'two thirds':2/3,'one fourth':.25,'three fourths':.75,'one quarter':.25,'three quarters':.75};for(const [k,v] of Object.entries(map))if(s.includes(k))return v;return null;}
function lineDistance(p,a,b){const ab=sub(b,a),den=dot(ab,ab);if(!den)return distance(p,a);const t=dot(sub(p,a),ab)/den,q=add(a,mul(ab,t));return {distance:distance(p,q),t,closest:q};}
function sideOfPoint(id){const old=v1coords.points.filter(x=>x.point_id===id).map(x=>x.side);return [...new Set(old.length?old:['midline'])];}
function selectDerived(real,side){for(const id of real?.derived_geometry_candidates||[]){const a=anchorPos(id,side);if(a)return a;}return null;}
function selectSpecial(real,side){for(const id of real?.specialized_anchor_candidates||[]){const a=anchorPos(id,side);if(a && (!id.startsWith('left-')&&!id.startsWith('right-')||id.startsWith(side+'-')))return a;}return null;}
function landmarkPoint(nid,side,solvedMap){
 const real=v1RealById.get(nid),n=graphLandmarkById.get(nid);if(!real)return null;
 if(real.realization_status==='specialized_anchor_resolved')return selectSpecial(real,side);
 if(real.realization_status==='constructed_geometry')return selectDerived(real,side);
 if(real.realization_status==='reference_acupoint'){const ref=real.reference_point_id,x=solvedMap.get(ref+':'+side)||solvedMap.get(ref+':midline');return x?.coordinate_projected?{position:x.coordinate_projected,provenance:{kind:'reference_acupoint',id:ref}}:null;}
 if(real.realization_status==='fma_mesh_resolved'){
  if(['body_region','surface_aspect'].includes(real.semantic_target_type)||real.landmark_specificity==='region_or_aggregate_mesh')return null;
  const raw=String(n?.source_raw||'').toLowerCase();let feature=null;
  if(/centre|center/.test(raw))feature='center';else if(/superior|upper/.test(raw))feature='superior';else if(/inferior|lower/.test(raw))feature='inferior';else if(/anterior/.test(raw))feature='anterior';else if(/posterior/.test(raw))feature='posterior';else if(/lateral/.test(raw))feature='lateral';else if(/medial/.test(raw))feature='medial';
  if(feature){const p=conceptFeature(real.fma_identity?.fma_id,side,feature);if(p)return {position:p,provenance:{kind:'fma_mesh_feature',fma_id:real.fma_identity.fma_id,feature}};}
 }
 return null;
}
function geometryValue(gid,side,solvedMap,stack=new Set()){
 if(stack.has(gid))return null;stack.add(gid);const g=geomById.get(gid);if(!g)return null;const deps=g.endpoint_node_ids||[];
 const ps=deps.map(id=>id.startsWith('G:')?geometryValue(id,side,solvedMap,stack):landmarkPoint(id,side,solvedMap));
 if((g.geometry_type==='constructed_line'||g.geometry_type==='reference_line')&&ps.length===2&&ps.every(Boolean))return {kind:'line',a:ps[0].position,b:ps[1].position,provenance:{geometry_node_id:gid,endpoints:deps}};
 if(String(g.geometry_type).includes('midpoint')&&ps.length===2&&ps.every(Boolean))return {kind:'point',position:lerp(ps[0].position,ps[1].position,.5),provenance:{geometry_node_id:gid,op:'midpoint'}};
 return null;
}
function argValue(id,side,solvedMap){if(id.startsWith('G:'))return geometryValue(id,side,solvedMap);const p=landmarkPoint(id,side,solvedMap);return p?{kind:'point',...p}:null;}

function measurementSeed(pointId,side,solvedMap){
 const rec=solverByPoint.get(pointId);if(!rec)return null;const frames=rec.measurementFrames||[];if(!frames.length)return null;
 const rels=relByPoint.get(pointId)||[];const availableAnchors=[];
 for(const r of rels)for(const id of r.argument_node_ids||[]){const v=argValue(id,side,solvedMap);if(v?.kind==='point')availableAnchors.push({node_id:id,...v});}
 const unique=[];for(const a of availableAnchors)if(!unique.some(x=>distance(x.position,a.position)<1e-6))unique.push(a);
 let target=null,anchorSource=null,executed=[];
 // Prefer an explicit source anchor that is also a calibration endpoint.
 for(const f of frames){
  const sc=scaleByFrameSide.get(f.id+':'+side);if(!sc||sc.status!=='usable')continue;
  const ids=[sc.from,sc.to];for(const a of unique){if(ids.some(id=>a.provenance?.id===id)){target=a.position.slice();anchorSource=a;break;}}if(target)break;
 }
 // If only one quantitative frame, source direction can select the proper calibration endpoint as the anchor.
 if(!target&&frames.length===1){
  const f=frames[0],sc=scaleByFrameSide.get(f.id+':'+side);if(sc?.status==='usable'){
   const A=anchorPos(sc.from,side),B=anchorPos(sc.to,side);if(A&&B){const dir=f.direction;let base=null;
    if(['superior','proximal'].includes(dir))base=A.position[sup]<=B.position[sup]?A:B;
    else if(['inferior','distal'].includes(dir))base=A.position[sup]>=B.position[sup]?A:B;
    if(base){target=base.position.slice();anchorSource=base;}
   }
  }
 }
 if(!target)return null;
 for(const f of frames){
  const sc=scaleByFrameSide.get(f.id+':'+side);if(!sc||sc.status!=='usable'||!Number.isFinite(f.value))return null;
  const amt=f.value*sc.model_unit_per_cun,dir=f.direction,ss=sideSign(side);const delta=[0,0,0];
  if(dir==='superior'||dir==='proximal')delta[sup]=amt;
  else if(dir==='inferior'||dir==='distal')delta[sup]=-amt;
  else if(dir==='lateral'){if(!ss)return null;delta[lr]=ss*amt;}
  else if(dir==='medial'){if(!ss)return null;delta[lr]=-ss*amt;}
  else if(dir==='anterior')delta[ap]=antSign*amt;
  else if(dir==='posterior')delta[ap]=-antSign*amt;
  else return null;
  target=add(target,delta);executed.push({frame_id:f.id,calibration_id:sc.calibration_id,direction:dir,value:f.value,model_unit_per_cun:sc.model_unit_per_cun,delta});
 }
 return {position:target,method:'native_proportional_measurement_offset',executed,anchor:anchorSource};
}

function nativeRaw(pointId,side,solvedMap){
 if(bBlockPoints.has(pointId))return {status:'blocked',reason:['frozen_B_structural_cardinality_blocker']};
 const rels=(relByPoint.get(pointId)||[]).filter(r=>r.source_section==='location');
 const candidates=[];
 for(const r of rels){
  const args=(r.argument_node_ids||[]).map(id=>argValue(id,side,solvedMap));
  if(r.relation_type==='midpoint-between'){
   if(args.length===2&&args.every(x=>x?.kind==='point'))candidates.push({position:lerp(args[0].position,args[1].position,.5),method:'midpoint-between',relation_ids:[r.relation_id]});
   else if(args.length===1&&args[0]?.kind==='line')candidates.push({position:lerp(args[0].a,args[0].b,.5),method:'midpoint-between-line',relation_ids:[r.relation_id]});
  }
  if(r.relation_type==='fraction-along-line'){
   const f=parseFraction(r.source_raw);if(f!=null&&args.length===1&&args[0]?.kind==='line')candidates.push({position:lerp(args[0].a,args[0].b,f),method:'fraction-along-line',relation_ids:[r.relation_id],fraction:f});
   else if(f!=null&&args.length===2&&args.every(x=>x?.kind==='point'))candidates.push({position:lerp(args[0].position,args[1].position,f),method:'fraction-along-line',relation_ids:[r.relation_id],fraction:f});
  }
 }
 const ms=measurementSeed(pointId,side,solvedMap);if(ms)candidates.push({...ms,relation_ids:rels.filter(r=>r.relation_type==='relative-to').map(r=>r.relation_id)});
 // Exact specialized anchor can uniquely locate points with no quantitative geometry when the source relation directly names it.
 const specials=[];
 for(const r of rels)for(const id of r.argument_node_ids||[]){const real=v1RealById.get(id);if(real?.realization_status==='specialized_anchor_resolved'){const p=selectSpecial(real,side);if(p)specials.push({position:p.position,method:'direct-specialized-anchor',relation_ids:[r.relation_id],anchor:p});}}
 if(!candidates.length&&specials.length===1)candidates.push(specials[0]);
 if(!candidates.length)return {status:'unresolved',reason:['no_unique_relation_native_coordinate_operator']};
 // Consensus requirement if multiple generators exist.
 candidates.sort((a,b)=>(a.method==='native_proportional_measurement_offset'?0:1)-(b.method==='native_proportional_measurement_offset'?0:1));
 const base=candidates[0],discord=candidates.filter(x=>distance(x.position,base.position)>bodyDiag*.025);
 if(discord.length)return {status:'blocked',reason:['native_generator_disagreement'],candidates};
 return {status:'executed',coordinate_raw:base.position,method:base.method,relation_ids:[...new Set(candidates.flatMap(x=>x.relation_ids||[]))],generator_evidence:candidates};
}

function relationResidual(r,p,side,solvedMap){
 const args=(r.argument_node_ids||[]).map(id=>argValue(id,side,solvedMap)),tol=bodyDiag*.008;let observed=null,residual=null,expected=null,status='uncomputable';
 if(r.relation_type==='midpoint-between'){
  let q=null;if(args.length===2&&args.every(x=>x?.kind==='point'))q=lerp(args[0].position,args[1].position,.5);else if(args.length===1&&args[0]?.kind==='line')q=lerp(args[0].a,args[0].b,.5);
  if(q){residual=distance(p,q);expected={point:q};observed={distance_to_expected:residual};status=residual<=tol?'pass':residual<=tol*2?'review':'fail';}
 } else if(r.relation_type==='fraction-along-line'){
  const f=parseFraction(r.source_raw);let q=null;if(f!=null&&args.length===1&&args[0]?.kind==='line')q=lerp(args[0].a,args[0].b,f);else if(f!=null&&args.length===2&&args.every(x=>x?.kind==='point'))q=lerp(args[0].position,args[1].position,f);
  if(q){residual=distance(p,q);expected={fraction:f,point:q};observed={distance_to_expected:residual};status=residual<=tol?'pass':residual<=tol*2?'review':'fail';}
 } else if(r.relation_type==='on-line'){
  const line=args.find(x=>x?.kind==='line');if(line){const q=lineDistance(p,line.a,line.b);residual=q.distance;expected={line:{a:line.a,b:line.b}};observed={distance_to_line:q.distance,t:q.t};status=residual<=tol?'pass':residual<=tol*2?'review':'fail';}
 } else if(r.relation_type==='between'){
  if(args.length>=2&&args[0]?.kind==='point'&&args[1]?.kind==='point'){const q=lineDistance(p,args[0].position,args[1].position);residual=q.distance+(q.t<0?-q.t*tol:q.t>1?(q.t-1)*tol:0);expected={segment:{a:args[0].position,b:args[1].position}};observed={distance_to_segment_line:q.distance,t:q.t};status=q.distance<=tol&&q.t>=-.05&&q.t<=1.05?'pass':q.distance<=tol*2&&q.t>=-.15&&q.t<=1.15?'review':'fail';}
 } else if(r.relation_type==='relative-to'){
  const a=args.find(x=>x?.kind==='point');if(a){const raw=String(r.source_raw||'').toLowerCase(),d=sub(p,a.position);let ok=null,val=null;
   if(/same level/.test(raw)){val=Math.abs(d[sup]);residual=val;ok=val<=tol;}
   else if(/superior|proximal/.test(raw)){val=d[sup];ok=val>=-tol;residual=Math.max(0,-val);}
   else if(/inferior|distal/.test(raw)){val=-d[sup];ok=val>=-tol;residual=Math.max(0,-val);}
   else if(/lateral/.test(raw)&&side!=='midline'){val=d[lr]*sideSign(side);ok=val>=-tol;residual=Math.max(0,-val);}
   else if(/medial/.test(raw)&&side!=='midline'){val=-d[lr]*sideSign(side);ok=val>=-tol;residual=Math.max(0,-val);}
   if(ok!=null){expected={direction:r.source_raw,reference:a.position};observed={signed_value:val};status=ok?'pass':'fail';}
  }
 } else if(r.relation_type==='surface-landmark'){
  const pr=projectSkin(p,side,{regionCenter:p});if(pr){residual=pr.distance;expected={surface_mesh_id:'FJ2810'};observed={distance_to_surface:pr.distance};status=pr.distance<=bodyDiag*.03?'pass':pr.distance<=bodyDiag*.06?'review':'fail';}
 } else if(r.relation_type==='overlies'){
  const a=args.find(x=>x?.kind==='point');if(a){residual=distance(p,a.position);expected={over_structure_anchor:a.position};observed={anchor_distance:residual};status=residual<=bodyDiag*.08?'pass':residual<=bodyDiag*.15?'review':'fail';}
 } else if(['at-border','at-junction'].includes(r.relation_type)){
  const a=args.find(x=>x?.kind==='point');if(a){residual=distance(p,a.position);expected={feature_point:a.position};observed={distance:residual};status=residual<=tol?'pass':residual<=tol*2?'review':'fail';}
 }
 return {relation_instance_id:r.relation_id,relation_type:r.relation_type,expected_constraint:expected,observed,residual,tolerance:tol,status,computable:status!=='uncomputable'};
}

const physicalKeys=[];for(const p of graph.points)for(const side of sideOfPoint(p.point_id))physicalKeys.push([p.point_id,side]);
const solvedMap=new Map(),records=[];
for(let pass=0;pass<8;pass++){
 let changed=0;
 for(const [id,side] of physicalKeys){const key=id+':'+side;if(solvedMap.has(key))continue;const raw=nativeRaw(id,side,solvedMap);if(raw.status!=='executed')continue;
  const rels=(relByPoint.get(id)||[]).filter(r=>r.source_section==='location');const rawQc=rels.map(r=>relationResidual(r,raw.coordinate_raw,side,solvedMap));
  const hardComputable=rawQc.filter(x=>x.computable),rawFail=hardComputable.some(x=>x.status==='fail');
  if(rawFail)continue;
  const pr=projectSkin(raw.coordinate_raw,side,{levelTol:bodyDiag*.08,regionCenter:raw.coordinate_raw});if(!pr)continue;
  const temp={point_id:id,side,coordinate_raw:raw.coordinate_raw,coordinate_projected:pr.point};solvedMap.set(key,temp);changed++;
 }
 if(!changed)break;
}
const legacyByKey=new Map(v1coords.points.map(x=>[x.point_id+':'+x.side,x]));
for(const [id,side] of physicalKeys){
 const key=id+':'+side,raw=nativeRaw(id,side,solvedMap),legacy=legacyByKey.get(key),rels=(relByPoint.get(id)||[]).filter(r=>r.source_section==='location');
 if(raw.status!=='executed'){
  records.push({point_id:id,side,status:'unresolved',dependency_ready:raw.status!=='blocked',relation_executed:false,relation_satisfied:false,surface_projected:false,visual_QC_passed:false,final_validated:false,coordinate_raw:null,coordinate_projected:null,solver_method:null,unresolved_reason:raw.reason||['native_solver_unresolved'],legacy_comparison:legacy?.legacy_candidate?{coordinate_raw:legacy.legacy_candidate.coordinate_raw,coordinate_projected:legacy.legacy_candidate.coordinate_projected}:null,source_statement_ids:[...new Set(rels.map(r=>r.source_statement_id).filter(Boolean))],relation_instance_ids:rels.map(r=>r.relation_id)});
  continue;
 }
 const rawQc=rels.map(r=>relationResidual(r,raw.coordinate_raw,side,solvedMap));const rawComputable=rawQc.filter(x=>x.computable),rawFailures=rawComputable.filter(x=>x.status==='fail');
 const pr=projectSkin(raw.coordinate_raw,side,{levelTol:bodyDiag*.08,regionCenter:raw.coordinate_raw});
 const projectedQc=pr?rels.map(r=>relationResidual(r,pr.point,side,solvedMap)):[];
 const projectedFailures=projectedQc.filter(x=>x.computable&&x.status==='fail');
 // Strict source-chain gate: every material location relation must be numerically computable and pass.
 const requiredTypes=new Set(['between','midpoint-between','fraction-along-line','on-line','at-border','at-junction','relative-to','surface-landmark','overlies','adjacent','deep-to']);
 const requiredRaw=rawQc.filter(x=>requiredTypes.has(x.relation_type));
 const requiredProjected=projectedQc.filter(x=>requiredTypes.has(x.relation_type));
 const relationSatisfied=requiredRaw.length>0 && requiredRaw.every(x=>x.computable&&x.status==='pass') && requiredProjected.length===requiredRaw.length && requiredProjected.every(x=>x.computable&&x.status==='pass');
 const status=pr&&relationSatisfied?'relation_satisfied_surface_projected_pending_visual_qc':pr?'surface_projected_relation_incomplete_or_review':'relation_executed_unprojected';
 const legacyP=legacy?.legacy_candidate?.coordinate_projected;const discrepancy=legacyP&&pr?distance(legacyP,pr.point):null;
 records.push({point_id:id,side,status,dependency_ready:true,relation_executed:true,relation_satisfied:relationSatisfied,surface_projected:!!pr,visual_QC_passed:false,final_validated:false,coordinate_raw:raw.coordinate_raw,coordinate_projected:pr?.point||null,solver_method:raw.method,native_relation_types_executed:[...new Set(raw.relation_ids.map(rid=>graph.relation_instances.find(x=>x.relation_id===rid)?.relation_type).filter(Boolean))],source_statement_ids:[...new Set(rels.map(r=>r.source_statement_id).filter(Boolean))],relation_instance_ids:rels.map(r=>r.relation_id),generator_evidence:raw.generator_evidence,measurement_dependencies:(solverByPoint.get(id)?.measurementFrames||[]).map(f=>scaleByFrameSide.get(f.id+':'+side)).filter(Boolean),required_relation_types:[...requiredTypes],raw_required_relation_count:requiredRaw.length,raw_uncomputable_required_relations:requiredRaw.filter(x=>!x.computable).map(x=>x.relation_instance_id),projected_uncomputable_required_relations:requiredProjected.filter(x=>!x.computable).map(x=>x.relation_instance_id),raw_relation_residuals:rawQc,projected_relation_residuals:projectedQc,projection:pr?{mesh_id:'FJ2810',distance:pr.distance,triangle_index:pr.triangleIndex}:null,legacy_comparison:legacyP?{coordinate_projected:legacyP,discrepancy_distance:discrepancy,flag:discrepancy>bodyDiag*.04?'large_discrepancy':null}:null,unresolved_reason:relationSatisfied?null:['relation_residual_or_projection_review_required']});
}

const realV2=v1real.landmark_realizations.map(x=>{
 const y={...x,v2_point_provider:false,v2_constraint_provider:false,v2_notes:[]};
 if(x.realization_status==='fma_mesh_resolved'&&(['body_region','surface_aspect'].includes(x.semantic_target_type)||x.landmark_specificity==='region_or_aggregate_mesh')){y.v2_realization_status='fma_mesh_region_constraint';y.v2_constraint_provider=true;y.v2_notes.push('aggregate FMA is a region/constraint, not a point source');}
 else if(x.realization_status==='fma_mesh_resolved'){y.v2_realization_status='fma_mesh_resolved';y.v2_constraint_provider=true;y.v2_notes.push('point feature only when source explicitly specifies center/superior/inferior/anterior/posterior/lateral/medial feature');}
 else if(x.realization_status==='specialized_anchor_resolved'){y.v2_realization_status='specialized_anchor_resolved';y.v2_point_provider=true;}
 else if(x.realization_status==='constructed_geometry'){y.v2_realization_status='constructed_geometry_audited';y.v2_point_provider=true;}
 else {y.v2_realization_status=x.realization_status;y.v2_constraint_provider=x.geometry_available===true;}
 return y;
});
const corrections=[
 {anchor_id:'suprasternal-notch',old:existingAnchor('suprasternal-notch','midline'),v2:correctedSuprasternal()},
 {anchor_id:'superior-border-pubic-symphysis',old:existingAnchor('superior-border-pubic-symphysis','midline'),v2:correctedPubic()},
 {anchor_id:'inferior-border-medial-condyle-tibia:left',old:existingAnchor('inferior-border-medial-condyle-tibia','left'),v2:correctedTibiaFeature('left','medial-condyle-inferior')},
 {anchor_id:'inferior-border-medial-condyle-tibia:right',old:existingAnchor('inferior-border-medial-condyle-tibia','right'),v2:correctedTibiaFeature('right','medial-condyle-inferior')},
 {anchor_id:'prominence-medial-malleolus:left',old:existingAnchor('prominence-medial-malleolus','left'),v2:correctedTibiaFeature('left','medial-malleolus')},
 {anchor_id:'prominence-medial-malleolus:right',old:existingAnchor('prominence-medial-malleolus','right'),v2:correctedTibiaFeature('right','medial-malleolus')}
].map(x=>({...x,shift:x.old?.position&&x.v2?.position?distance(x.old.position,x.v2.position):null}));

const residualRows=records.flatMap(x=>(x.raw_relation_residuals||[]).map(r=>({point_id:x.point_id,side:x.side,stage:'raw',...r})).concat((x.projected_relation_residuals||[]).map(r=>({point_id:x.point_id,side:x.side,stage:'projected',...r}))));
const relationTypes=[...new Set(graph.relation_instances.map(x=>x.relation_type))].sort();
const summary={
 physical_records:records.length,
 dependency_ready:records.filter(x=>x.dependency_ready).length,
 relation_executed:records.filter(x=>x.relation_executed).length,
 relation_satisfied:records.filter(x=>x.relation_satisfied).length,
 surface_projected:records.filter(x=>x.surface_projected).length,
 visual_QC_passed:0,
 final_validated:0,
 unresolved:records.filter(x=>x.status==='unresolved').length,
 pending_visual_qc:records.filter(x=>x.status==='relation_satisfied_surface_projected_pending_visual_qc').length,
 raw_relation_residual_pass:residualRows.filter(x=>x.stage==='raw'&&x.status==='pass').length,
 raw_relation_residual_review:residualRows.filter(x=>x.stage==='raw'&&x.status==='review').length,
 raw_relation_residual_fail:residualRows.filter(x=>x.stage==='raw'&&x.status==='fail').length,
 projected_relation_residual_pass:residualRows.filter(x=>x.stage==='projected'&&x.status==='pass').length,
 projected_relation_residual_review:residualRows.filter(x=>x.stage==='projected'&&x.status==='review').length,
 projected_relation_residual_fail:residualRows.filter(x=>x.stage==='projected'&&x.status==='fail').length,
 large_legacy_discrepancy:records.filter(x=>x.legacy_comparison?.flag==='large_discrepancy').length, relation_types_present:relationTypes
};

const v1KnownWrong=new Set(['CV1:midline','CV24:midline','GB26:left','GB26:right','ST29:left','ST29:right','ST35:left','ST35:right']);
const v1KnownControls=new Set(['ST7:left','TE16:left','GB23:left','SI14:left','HT4:left','PC8:left','ST31:left','ST31:right','LR2:left','CV12:midline','GV14:midline']);
const regressionSubset=records.filter(x=>v1KnownWrong.has(x.point_id+':'+x.side)||v1KnownControls.has(x.point_id+':'+x.side)).map(x=>({point_id:x.point_id,side:x.side,v1_visual_label:v1KnownWrong.has(x.point_id+':'+x.side)?'known_wrong_v1':'control_v1',status:x.status,relation_executed:x.relation_executed,relation_satisfied:x.relation_satisfied,surface_projected:x.surface_projected,visual_QC_passed:x.visual_QC_passed,coordinate_raw:x.coordinate_raw,coordinate_projected:x.coordinate_projected,legacy_discrepancy:x.legacy_comparison?.discrepancy_distance??null,uncomputable_required:x.raw_uncomputable_required_relations??[]}));

const realizationOut={schema_version:'2.0.0',artifact:'acupoint-bodyparts3d-realization-v2.json',generated_at:now,frozen_B_sha256:FROZEN_B_SHA,frozen_B_modified:false,principles:{aggregate_fma_is_constraint_not_point:true,no_internal_centroid_as_final_coordinate:true,side_specific_structure_selection:true},anchor_corrections:corrections,landmark_realizations:realV2};
const solverOut={schema_version:'2.0.0',artifact:'acupoint-coordinate-solver-input-v2.json',generated_at:now,frozen_B_sha256:FROZEN_B_SHA,blocked_B_records:auditV1.frozen_B_structural_coordinate_audit,relation_operators:{between:'segment constraint; non-unique alone', 'midpoint-between':'midpoint of two realized points or realized line','fraction-along-line':'lerp on realized line using source fraction','on-line':'numeric distance-to-line constraint','at-border':'only executable when border feature resolves to a point/geometry','at-junction':'only executable when junction feature resolves to a point/geometry','relative-to':'directional constraint; quantitative offset executed through audited proportional frame','surface-landmark':'Skin/region constraint','overlies':'structure-anchor proximity + final Skin projection'},calibration_audit:{median_model_unit_per_cun:medScale,records:calibrationAudit}};
const coordsOut={schema_version:'2.0.1',artifact:'acupoint-coordinates-v2.json',generated_at:now,standard:'WHO 2008 frozen B relation graph v1 -> BodyParts3D 4.0 native C v2',frozen_B_sha256:FROZEN_B_SHA,v1_baseline_preserved:true,status_semantics:{dependency_ready:'dependencies geometrically available; not correctness',relation_executed:'a native B relation/measurement operation generated the raw candidate',relation_satisfied:'all computable native residuals pass at raw and projected stages; at least one numeric relation is computable',surface_projected:'candidate projected to FJ2810 Skin with side/level constraint',visual_QC_passed:'requires explicit visual adjudication; never inferred from numeric QC',final_validated:'relation_satisfied + surface_projected + visual_QC_passed'},summary,points:records};
const qcOut={schema_version:'2.0.1',artifact:'acupoint-coordinate-qc-v2.json',generated_at:now,summary,numeric_relation_residuals:residualRows,anchor_corrections:corrections,calibration_blockers:calibrationAudit.filter(x=>x.status==='blocked'),B_minimal_reopen_candidates:auditV1.frozen_B_structural_coordinate_audit,regression_subset:regressionSubset,review_queue:records.filter(x=>!x.final_validated).map(x=>({point_id:x.point_id,side:x.side,status:x.status,reasons:x.unresolved_reason||['pending_visual_qc'],legacy_discrepancy:x.legacy_comparison?.discrepancy_distance??null}))};
write('public/knowledge/acupoint-bodyparts3d-realization-v2.json',realizationOut);
write('public/knowledge/acupoint-coordinate-solver-input-v2.json',solverOut);
write('public/knowledge/acupoint-coordinates-v2.json',coordsOut);
write('public/knowledge/acupoint-coordinate-qc-v2.json',qcOut);
const outputFiles=['public/knowledge/acupoint-bodyparts3d-realization-v2.json','public/knowledge/acupoint-coordinate-solver-input-v2.json','public/knowledge/acupoint-coordinates-v2.json','public/knowledge/acupoint-coordinate-qc-v2.json'];
const manifest={schema_version:'2.0.0',generated_at:now,frozen_B_sha256:FROZEN_B_SHA,frozen_B_modified:false,v1_baseline_preserved:true,outputs:Object.fromEntries(outputFiles.map(p=>[p,{sha256:hash(fs.readFileSync(new URL(p,root))),bytes:fs.statSync(new URL(p,root)).size}]))};
write('public/knowledge/acupoint-coordinate-manifest-v2.json',manifest);
console.log(JSON.stringify({summary,anchor_corrections:corrections.map(x=>({anchor_id:x.anchor_id,shift:x.shift,old:x.old?.position,v2:x.v2?.position})),calibration:{total:calibrationAudit.length,usable:calibrationAudit.filter(x=>x.status==='usable').length,blocked:calibrationAudit.filter(x=>x.status==='blocked').length},B:auditV1.frozen_B_structural_coordinate_audit},null,2));
