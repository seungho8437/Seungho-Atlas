import {readFileSync} from 'node:fs';
import {join} from 'node:path';

export const ROOT=process.cwd();
const readJson=(p)=>JSON.parse(readFileSync(join(ROOT,p),'utf8'));
const vsub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
const vadd=(a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]];
const vmul=(a,s)=>[a[0]*s,a[1]*s,a[2]*s];
const dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
export const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);

export function loadBinding(){
 const atlas=readJson('public/models/atlas.json');
 const hash=readJson('public/models/atlas.hash.json');
 const skin=atlas.parts.find(p=>p.id===hash.skin_part_id);
 if(!skin)throw new Error('Skin part '+hash.skin_part_id+' not found');
 if(skin.indexCount/3!==hash.skin_triangles)throw new Error('Skin triangle count differs from atlas.hash.json');
 const chunk=atlas.chunks[skin.chunk];
 if(!chunk?.url)throw new Error('Skin chunk URL missing');
 const buf=readFileSync(join(ROOT,'public',chunk.url.replace(/^\/+/,'')));
 const positions=new Float32Array(buf.buffer,buf.byteOffset+skin.positions,skin.vertexCount*3);
 const indices=new Uint32Array(buf.buffer,buf.byteOffset+skin.indices,skin.indexCount);
 const midlineX=0; // x_app=x_mm*0.001 preserves the anatomical midsagittal plane at x=0
 return {atlas,hash,skin,positions,indices,midlineX};
}
export function vertex(binding,i){const p=binding.positions;return[p[i*3],p[i*3+1],p[i*3+2]];}
export function triangle(binding,tri){
 if(!Number.isInteger(tri)||tri<0||tri*3+2>=binding.indices.length)throw new Error('triangle_index out of range: '+tri);
 return [vertex(binding,binding.indices[tri*3]),vertex(binding,binding.indices[tri*3+1]),vertex(binding,binding.indices[tri*3+2])];
}
export function reconstructSurface(binding,surface){
 if(surface.mesh_id!==binding.skin.id)throw new Error('surface.mesh_id must be '+binding.skin.id);
 const [a,b,c]=triangle(binding,surface.triangle_index),w=surface.barycentric;
 if(!Array.isArray(w)||w.length!==3||w.some(x=>!Number.isFinite(x)))throw new Error('invalid barycentric');
 if(Math.abs(w[0]+w[1]+w[2]-1)>1e-6||w.some(x=>x< -1e-6||x>1+1e-6))throw new Error('barycentric outside triangle');
 return [a[0]*w[0]+b[0]*w[1]+c[0]*w[2],a[1]*w[0]+b[1]*w[1]+c[1]*w[2],a[2]*w[0]+b[2]*w[1]+c[2]*w[2]];
}
function closestOnTriangle(p,a,b,c){
 const ab=vsub(b,a),ac=vsub(c,a),ap=vsub(p,a),d1=dot(ab,ap),d2=dot(ac,ap);
 if(d1<=0&&d2<=0)return{point:a,bary:[1,0,0]};
 const bp=vsub(p,b),d3=dot(ab,bp),d4=dot(ac,bp);
 if(d3>=0&&d4<=d3)return{point:b,bary:[0,1,0]};
 const vc=d1*d4-d3*d2;
 if(vc<=0&&d1>=0&&d3<=0){const v=d1/(d1-d3);return{point:vadd(a,vmul(ab,v)),bary:[1-v,v,0]};}
 const cp=vsub(p,c),d5=dot(ab,cp),d6=dot(ac,cp);
 if(d6>=0&&d5<=d6)return{point:c,bary:[0,0,1]};
 const vb=d5*d2-d1*d6;
 if(vb<=0&&d2>=0&&d6<=0){const w=d2/(d2-d6);return{point:vadd(a,vmul(ac,w)),bary:[1-w,0,w]};}
 const va=d3*d6-d5*d4;
 if(va<=0&&(d4-d3)>=0&&(d5-d6)>=0){const bc=vsub(c,b),w=(d4-d3)/((d4-d3)+(d5-d6));return{point:vadd(b,vmul(bc,w)),bary:[0,1-w,w]};}
 const denom=1/(va+vb+vc),v=vb*denom,w=vc*denom;return{point:vadd(a,vadd(vmul(ab,v),vmul(ac,w))),bary:[1-v-w,v,w]};
}
export function closestOnSkin(binding,p){
 let best=null,bestD=Infinity;const n=binding.indices.length/3;
 for(let tri=0;tri<n;tri++){
  const [a,b,c]=triangle(binding,tri),q=closestOnTriangle(p,a,b,c),d=distance(p,q.point);
  if(d<bestD){bestD=d;best={position:q.point,surface:{mesh_id:binding.skin.id,triangle_index:tri,barycentric:q.bary},distance:d};if(d<1e-9)break;}
 }
 return best;
}
export function mirrorAndSnap(binding,p){
 const raw=[2*binding.midlineX-p[0],p[1],p[2]],snap=closestOnSkin(binding,raw);
 return {...snap,raw};
}
export function buildRenderRegistry(source,acupoints,binding,generatedAt=new Date().toISOString()){
 if(source?.schema_version!==1)throw new Error('Unsupported placement schema_version');
 if(source?.mesh_binding?.atlas_sha256!==binding.hash.atlas_sha256)throw new Error('Source mesh hash mismatch');
 const byId=new Map(acupoints.map(p=>[p.id,p])),points=[];
 for(const item of source.points??[]){
  const def=byId.get(item.id);if(!def)throw new Error('Unknown acupoint '+item.id);
  if(item.status==='SKIPPED')continue;
  if(!item.position||!item.surface)throw new Error(item.id+' requires position and surface');
  points.push({...item,origin:'placed'});
  if(def.laterality==='bilateral'){
   const m=mirrorAndSnap(binding,item.position),side=item.side==='left'?'right':'left',flagged=m.distance>.003||item.status==='FLAGGED';
   points.push({id:item.id,side,position:m.position,surface:m.surface,status:flagged?'FLAGGED':item.status,origin:'mirrored',snap_distance_m:m.distance,note:item.note??''});
  }
 }
 const counts={source_entries:(source.points??[]).length,render_points:points.length,placed:points.filter(p=>p.origin==='placed').length,mirrored:points.filter(p=>p.origin==='mirrored').length,flagged:points.filter(p=>p.status==='FLAGGED').length,skipped:(source.points??[]).filter(p=>p.status==='SKIPPED').length};
 return {schema_version:1,mesh_binding:source.mesh_binding,midline_x:binding.midlineX,generated_at:generatedAt,counts,points};
}
export function refY(binding,name){
 const p=binding.atlas.parts.find(x=>x.name===name);if(!p)throw new Error('Reference part not found: '+name);return(p.bounds[0][1]+p.bounds[1][1])/2;
}
