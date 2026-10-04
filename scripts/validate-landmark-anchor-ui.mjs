import fs from 'node:fs';
import assert from 'node:assert/strict';

const atlas=JSON.parse(fs.readFileSync('public/models/atlas.json','utf8'));
const required=[
 'Distal phalanx of left middle finger',
 'Middle phalanx of left middle finger',
 'Proximal phalanx of left middle finger',
 'Distal phalanx of right middle finger',
 'Middle phalanx of right middle finger',
 'Proximal phalanx of right middle finger'
];
for(const name of required){
 const part=atlas.parts.find(p=>p.name===name);
 assert.ok(part, `Missing detector anatomy: ${name}`);
 assert.equal(part.system,'skeletal',`${name}: detector anatomy must be skeletal`);
 assert.ok(Array.isArray(part.bounds)&&part.bounds.length===2,`${name}: bounds missing`);
}
for(const side of ['left','right']){
 const prox=atlas.parts.find(p=>p.name===`Proximal phalanx of ${side} middle finger`);
 const mid=atlas.parts.find(p=>p.name===`Middle phalanx of ${side} middle finger`);
 const dist=atlas.parts.find(p=>p.name===`Distal phalanx of ${side} middle finger`);
 const center=p=>p.bounds[0].map((v,i)=>(v+p.bounds[1][i])/2);
 const a=center(prox),b=center(mid),c=center(dist);
 const d1=Math.hypot(...a.map((v,i)=>v-b[i])),d2=Math.hypot(...b.map((v,i)=>v-c[i]));
 assert.ok(d1>0&&d2>0,`${side}: invalid phalanx center separation`);
}
const specs=JSON.parse(fs.readFileSync('public/knowledge/acupoint-specialized-landmark-specs.json','utf8'));
const detectorIds=new Set(specs.landmarks.filter(x=>x.detector?.type==='joint-plane-surface-intersection').map(x=>x.landmarkId));
assert.deepEqual([...detectorIds].sort(),[
 'radial-crease-distal-interphalangeal-middle-finger',
 'radial-crease-proximal-interphalangeal-middle-finger'
]);
console.log('Interactive PIP/DIP detector anatomy and specialized specs validated.');
