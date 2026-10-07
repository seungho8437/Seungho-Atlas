import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {buildRenderRegistry,closestOnSkin,distance,loadBinding,reconstructSurface,refY,triangle} from './lib/acupoint-placement.mjs';

const acupoints=JSON.parse(readFileSync('public/knowledge/acupoints.json','utf8'));
const ranges=JSON.parse(readFileSync('scripts/data/plausibility-ranges.json','utf8'));
const binding=loadBinding(),defs=new Map(acupoints.map(p=>[p.id,p]));
const liveSource=JSON.parse(readFileSync('data/acupoint-placements.source.json','utf8'));
const liveRender=JSON.parse(readFileSync('public/knowledge/acupoint-render.json','utf8'));
const issue=(code,id,message)=>({code,id,message});
function validate(source,render){
 const errors=[],warns=[],seen=new Set();
 if(source.schema_version!==1)errors.push(issue('SCHEMA',null,'schema_version must be 1'));
 if(source.mesh_binding?.atlas_sha256!==binding.hash.atlas_sha256)errors.push(issue('HASH_MISMATCH',null,'source atlas_sha256 differs from atlas.hash.json'));
 if(source.mesh_binding?.skin_part_id!==binding.skin.id)errors.push(issue('SKIN_ID',null,'skin_part_id differs from atlas'));
 for(const p of source.points??[]){
  const def=defs.get(p.id);
  if(!def){errors.push(issue('UNKNOWN_ID',p.id,'id not in acupoints.json'));continue;}
  if(seen.has(p.id))errors.push(issue('DUPLICATE_ID',p.id,'source id duplicated'));seen.add(p.id);
  if(!['PLACED','SKIPPED','FLAGGED'].includes(p.status))errors.push(issue('STATUS',p.id,'invalid status'));
  if(def.laterality==='midline'&&p.side!=='midline')errors.push(issue('LATERALITY',p.id,'midline point must use side=midline'));
  if(def.laterality==='bilateral'&&!['left','right'].includes(p.side))errors.push(issue('LATERALITY',p.id,'bilateral point must use left or right'));
  if(p.status==='SKIPPED')continue;
  if(!Array.isArray(p.position)||!p.surface){errors.push(issue('SURFACE_REQUIRED',p.id,'placed/flagged point requires position and surface'));continue;}
  try{
   const r=reconstructSurface(binding,p.surface),delta=distance(r,p.position),skin=closestOnSkin(binding,p.position)?.distance??Infinity;
   if(delta>1e-6)errors.push(issue('SURFACE_RECONSTRUCTION',p.id,'position differs from barycentric reconstruction by '+delta));
   if(skin>.001)errors.push(issue('OFF_SKIN',p.id,'nearest skin distance '+skin+' m exceeds 1 mm'));
  }catch(e){errors.push(issue('SURFACE_INVALID',p.id,e.message));}
  if(p.side==='left'&&!(p.position[0]>binding.midlineX))errors.push(issue('SIDE_SIGN',p.id,'left requires x > midline_x'));
  if(p.side==='right'&&!(p.position[0]<binding.midlineX))errors.push(issue('SIDE_SIGN',p.id,'right requires x < midline_x'));
  if(p.side==='midline'&&Math.abs(p.position[0]-binding.midlineX)>.005)errors.push(issue('MIDLINE',p.id,'midline point exceeds 5 mm from midline_x'));
 }
 if(render.mesh_binding?.atlas_sha256!==binding.hash.atlas_sha256)errors.push(issue('RENDER_HASH',null,'render atlas_sha256 differs from atlas.hash.json'));
 for(const p of render.points??[])if(p.origin==='mirrored'&&p.snap_distance_m>.003){
  if(p.status!=='FLAGGED')errors.push(issue('MIRROR_FLAG',p.id,'mirror snap >3 mm must be FLAGGED'));
  warns.push(issue('MIRROR_SNAP',p.id,'mirror snap '+(p.snap_distance_m*1000).toFixed(2)+' mm'));
 }
 const ordered=(source.points??[]).filter(p=>p.status!=='SKIPPED'&&p.position).sort((a,b)=>{const da=defs.get(a.id),db=defs.get(b.id);return da.meridian.localeCompare(db.meridian)||da.number-db.number;});
 const groups=new Map();for(const p of ordered){const m=defs.get(p.id).meridian,arr=groups.get(m)??[];arr.push(p);groups.set(m,arr);}
 for(const [m,arr] of groups){
  for(let i=1;i<arr.length;i++){
   const a=arr[i-1],b=arr[i],d=distance(a.position,b.position);if(d>.35)warns.push(issue('LONG_GAP',b.id,m+' consecutive gap '+d.toFixed(3)+' m'));
   if(m==='CV'&&b.position[1]<a.position[1]-.005)warns.push(issue('ORDER_Y',b.id,'CV should generally rise CV1→CV24'));
   if(m==='GV'&&defs.get(a.id).number<20&&defs.get(b.id).number<=20&&b.position[1]<a.position[1]-.005)warns.push(issue('ORDER_Y',b.id,'GV1→GV20 should generally rise'));
   if(m==='GV'&&defs.get(a.id).number>=20&&b.position[1]>a.position[1]+.005)warns.push(issue('ORDER_Y',b.id,'GV20→GV28 should generally descend'));
  }
 }
 for(const p of source.points??[]){
  if(p.status==='SKIPPED'||!p.position||!ranges[p.id])continue;const rule=ranges[p.id];if(rule.side&&p.side!==rule.side)continue;
  let lo,hi;if(rule.absolute_y_m){[lo,hi]=rule.absolute_y_m;}else if(rule.reference){
   const base=rule.reference.skin_top?binding.skin.bounds[1][1]:refY(binding,rule.reference.part_name);lo=base+rule.reference.offset_y_m[0];hi=base+rule.reference.offset_y_m[1];
  }
  if(p.position[1]<lo||p.position[1]>hi)warns.push(issue('PLAUSIBILITY_Y',p.id,'y='+p.position[1].toFixed(3)+' outside '+lo.toFixed(3)+'..'+hi.toFixed(3)+' m'));
 }
 return{errors,warns};
}
function centroidSurface(tri){const [a,b,c]=triangle(binding,tri);return{position:[(a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3,(a[2]+b[2]+c[2])/3],surface:{mesh_id:binding.skin.id,triangle_index:tri,barycentric:[1/3,1/3,1/3]}};}
function findTri(test){for(let t=0;t<binding.indices.length/3;t++){const c=centroidSurface(t);if(test(c.position))return c;}throw new Error('fixture triangle not found');}
function fixture(){
 const left1=findTri(p=>p[0]>binding.midlineX+.05),left2=findTri(p=>p[0]>binding.midlineX+.08&&p[1]>.2),mid=findTri(p=>Math.abs(p[0]-binding.midlineX)<.004);
 const mk=(id,side,c)=>({id,side,position:c.position,surface:c.surface,status:'PLACED',placed_at:'2026-10-07T00:00:00Z',note:''});
 const src={schema_version:1,mesh_binding:{atlas_sha256:binding.hash.atlas_sha256,skin_part_id:binding.skin.id,frame:{units:'m',left:'+x',anterior:'+z',up:'+y'}},points:[mk('LU1','left',left1),mk('LI1','left',left2),mk('CV24','midline',mid)]};
 return src;
}
function selfTest(){
 const src=fixture(),render=buildRenderRegistry(src,acupoints,binding,'TEST');let r=validate(src,render);assert.equal(r.errors.length,0,'3-point positive fixture must pass');
 const flip=structuredClone(src);flip.points[0].position[0]=2*binding.midlineX-flip.points[0].position[0];r=validate(flip,buildRenderRegistry(src,acupoints,binding,'TEST'));assert(r.errors.some(e=>e.code==='SIDE_SIGN'),'left/right inversion must fail');
 const off=structuredClone(src);off.points[0].position[2]+=.01;r=validate(off,render);assert(r.errors.some(e=>e.code==='OFF_SKIN'||e.code==='SURFACE_RECONSTRUCTION'),'off-skin fixture must fail');
 const bad=structuredClone(src);bad.mesh_binding.atlas_sha256='0'.repeat(64);r=validate(bad,render);assert(r.errors.some(e=>e.code==='HASH_MISMATCH'),'hash mismatch must fail');
 console.log('Fixture tests: 3-point PASS; side inversion FAIL; off-skin FAIL; hash mismatch FAIL');
}
const result=validate(liveSource,liveRender);
for(const w of result.warns)console.warn('WARN',w.code,w.id??'-',w.message);
for(const e of result.errors)console.error('ERROR',e.code,e.id??'-',e.message);
selfTest();
if(result.errors.length){console.error('Placement validation failed with '+result.errors.length+' error(s)');process.exit(1);}
console.log('Placement validation PASS; warnings='+result.warns.length);
