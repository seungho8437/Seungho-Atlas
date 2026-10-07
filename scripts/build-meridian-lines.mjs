import {readFileSync,writeFileSync} from 'node:fs';
import {distance,loadBinding,triangle,vertex} from './lib/acupoint-placement.mjs';

const binding=loadBinding();
const acupoints=JSON.parse(readFileSync('public/knowledge/acupoints.json','utf8'));
const render=JSON.parse(readFileSync('public/knowledge/acupoint-render.json','utf8'));
const topology=JSON.parse(readFileSync('data/meridian-topology.json','utf8'));
if(render.mesh_binding?.atlas_sha256!==binding.hash.atlas_sha256)throw new Error('acupoint-render mesh hash mismatch');
const MERIDIANS=['LU','LI','ST','SP','HT','SI','BL','KI','PC','TE','GB','LR','GV','CV'];
const pointDef=new Map(acupoints.map(p=>[p.id,p]));
const renderByKey=new Map((render.points??[]).map(p=>[`${p.id}|${p.side}`,p]));

function addEdge(adj,a,b){
 if(a===b)return;const w=distance(vertex(binding,a),vertex(binding,b));
 const oldA=adj[a].get(b);if(oldA===undefined||w<oldA)adj[a].set(b,w);
 const oldB=adj[b].get(a);if(oldB===undefined||w<oldB)adj[b].set(a,w);
}
const n=binding.skin.vertexCount,adj=Array.from({length:n},()=>new Map()),incident=Array.from({length:n},()=>[]);
for(let tri=0;tri<binding.indices.length/3;tri++){
 const a=binding.indices[tri*3],b=binding.indices[tri*3+1],c=binding.indices[tri*3+2];
 addEdge(adj,a,b);addEdge(adj,b,c);addEdge(adj,c,a);incident[a].push(tri);incident[b].push(tri);incident[c].push(tri);
}
class Heap{
 constructor(){this.a=[];}
 push(node,d){const a=this.a;a.push([d,node]);let i=a.length-1;while(i){const p=(i-1)>>1;if(a[p][0]<=d)break;a[i]=a[p];i=p;}a[i]=[d,node];}
 pop(){const a=this.a;if(!a.length)return null;const root=a[0],last=a.pop();if(a.length){let i=0;while(true){let l=i*2+1,r=l+1;if(l>=a.length)break;let c=r<a.length&&a[r][0]<a[l][0]?r:l;if(a[c][0]>=last[0])break;a[i]=a[c];i=c;}a[i]=last;}return root;}
 get size(){return this.a.length;}
}
function nearestTriangleVertex(point){
 const tri=point.surface.triangle_index,ids=[binding.indices[tri*3],binding.indices[tri*3+1],binding.indices[tri*3+2]];
 return ids.reduce((best,id)=>distance(point.position,vertex(binding,id))<distance(point.position,vertex(binding,best))?id:best,ids[0]);
}
function dijkstra(start,target){
 if(start===target)return{vertices:[start],distance:0};
 const dist=new Float64Array(n);dist.fill(Infinity);const prev=new Int32Array(n);prev.fill(-1),seen=new Uint8Array(n),heap=new Heap();dist[start]=0;heap.push(start,0);
 while(heap.size){const item=heap.pop();if(!item)break;const [d,u]=item;if(seen[u]||d!==dist[u])continue;seen[u]=1;if(u===target)break;
  for(const [v,w] of adj[u]){const nd=d+w;if(nd<dist[v]){dist[v]=nd;prev[v]=u;heap.push(v,nd);}}
 }
 if(!Number.isFinite(dist[target]))throw new Error(`No skin path between vertices ${start} and ${target}`);
 const path=[];for(let u=target;u!==-1;u=prev[u]){path.push(u);if(u===start)break;}path.reverse();return{vertices:path,distance:dist[target]};
}
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]],add=(a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]],mul=(a,s)=>[a[0]*s,a[1]*s,a[2]*s],dot=(a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
function closestPointOnTriangle(p,a,b,c){
 const ab=sub(b,a),ac=sub(c,a),ap=sub(p,a),d1=dot(ab,ap),d2=dot(ac,ap);if(d1<=0&&d2<=0)return a;
 const bp=sub(p,b),d3=dot(ab,bp),d4=dot(ac,bp);if(d3>=0&&d4<=d3)return b;const vc=d1*d4-d3*d2;if(vc<=0&&d1>=0&&d3<=0){const v=d1/(d1-d3);return add(a,mul(ab,v));}
 const cp=sub(p,c),d5=dot(ab,cp),d6=dot(ac,cp);if(d6>=0&&d5<=d6)return c;const vb=d5*d2-d1*d6;if(vb<=0&&d2>=0&&d6<=0){const w=d2/(d2-d6);return add(a,mul(ac,w));}
 const va=d3*d6-d5*d4;if(va<=0&&(d4-d3)>=0&&(d5-d6)>=0){const bc=sub(c,b),w=(d4-d3)/((d4-d3)+(d5-d6));return add(b,mul(bc,w));}
 const den=1/(va+vb+vc),v=vb*den,w=vc*den;return add(a,add(mul(ab,v),mul(ac,w)));
}
function localResnap(candidate,vertexId){
 let best=null,bestD=Infinity,bestTri=-1;
 for(const tri of incident[vertexId]){const [a,b,c]=triangle(binding,tri),q=closestPointOnTriangle(candidate,a,b,c),d=distance(candidate,q);if(d<bestD){bestD=d;best=q;bestTri=tri;}}
 return{position:best??vertex(binding,vertexId),triangle_index:bestTri>=0?bestTri:incident[vertexId][0]??0};
}
function segment(a,b){
 const av=nearestTriangleVertex(a),bv=nearestTriangleVertex(b),path=dijkstra(av,bv),total=distance(a.position,vertex(binding,av))+path.distance+distance(vertex(binding,bv),b.position);
 const raw=[a.position,...path.vertices.map(v=>vertex(binding,v)),b.position],out=[{position:a.position,triangle_index:a.surface.triangle_index}];
 for(let i=1;i<raw.length-1;i++){
  const sourceVertex=path.vertices[Math.max(0,Math.min(path.vertices.length-1,i-1))];
  const candidate=add(mul(raw[i],.5),add(mul(raw[i-1],.25),mul(raw[i+1],.25)));
  const snapped=localResnap(candidate,sourceVertex);if(distance(out[out.length-1].position,snapped.position)>1e-6)out.push(snapped);
 }
 if(distance(out[out.length-1].position,b.position)>1e-6)out.push({position:b.position,triangle_index:b.surface.triangle_index});
 else out[out.length-1]={position:b.position,triangle_index:b.surface.triangle_index};
 return{vertices:out,length:total};
}
function topologyPaths(meridian){
 const override=topology.meridians?.[meridian]?.paths;if(override)return override;
 return [[...acupoints].filter(p=>p.meridian===meridian).sort((a,b)=>a.number-b.number).map(p=>p.id)];
}
const warnings=[],paths=[];
for(const meridian of MERIDIANS){
 const sides=meridian==='GV'||meridian==='CV'?['midline']:['left','right'];
 for(const side of sides){
  topologyPaths(meridian).forEach((ids,pathIndex)=>{
   const polylines=[];let current=null;
   const flush=()=>{if(current&&current.point_ids.length>=2&&current.vertices.length>=2)polylines.push(current);current=null;};
   for(let i=1;i<ids.length;i++){
    const from=renderByKey.get(`${ids[i-1]}|${side}`),to=renderByKey.get(`${ids[i]}|${side}`);
    if(!from||!to||from.status==='FLAGGED'||to.status==='FLAGGED'){flush();continue;}
    const seg=segment(from,to);
    if(seg.length>.35){warnings.push({meridian,side,from:from.id,to:to.id,message:`skin shortest path ${seg.length.toFixed(3)} m exceeds 0.35 m; segment omitted`});flush();continue;}
    if(!current)current={point_ids:[from.id,to.id],vertices:seg.vertices,skin_path_length_m:seg.length};
    else if(current.point_ids[current.point_ids.length-1]===from.id){current.point_ids.push(to.id);current.vertices.push(...seg.vertices.slice(1));current.skin_path_length_m+=seg.length;}
    else{flush();current={point_ids:[from.id,to.id],vertices:seg.vertices,skin_path_length_m:seg.length};}
   }
   flush();if(polylines.length)paths.push({meridian,side,topology_path_index:pathIndex,polylines});
  });
 }
}
const output={schema_version:1,mesh_binding:render.mesh_binding,generated_at:new Date().toISOString(),warnings,paths};
writeFileSync('public/knowledge/meridian-lines.json',JSON.stringify(output,null,2)+'\n');
console.log(`Built meridian-lines.json: ${paths.length} rendered paths, ${warnings.length} warning(s)`);
for(const w of warnings)console.warn('WARN',w.meridian,w.side,w.from+'→'+w.to,w.message);
