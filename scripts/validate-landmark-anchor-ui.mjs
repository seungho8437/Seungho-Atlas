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

const skin=atlas.parts.find(p=>p.name==='Skin');
const hair=atlas.parts.find(p=>p.name==='Hair of head');
assert.ok(skin&&skin.system==='integumentary','BodyParts3D Skin mesh required for canonical anchor projection');
assert.ok(hair&&hair.system==='integumentary','BodyParts3D Hair of head mesh required for hairline segmentation proposals');
assert.ok(hair.bounds[0][1]>skin.bounds[0][1]&&hair.bounds[1][1]<=skin.bounds[1][1]+0.02,'Hair of head bounds must lie in the cranial Skin envelope');
const hairlineIds=['midpoint-anterior-hairline','midpoint-posterior-hairline','left-anterior-hairline-corner','right-anterior-hairline-corner'];
for(const id of hairlineIds){
 const spec=specs.landmarks.find(x=>x.landmarkId===id);
 assert.equal(spec?.detector?.type,'bodyparts3d-hair-boundary-to-skin-projection',`${id}: explicit hair segmentation detector required`);
 assert.equal(spec?.detector?.status,'requires-manual-confirmation',`${id}: detector must remain manual-confirmation gated`);
}
const sceneSource=fs.readFileSync('app/scene.tsx','utf8');
assert.match(sceneSource,/controls\.zoomToCursor=true/,'Cursor-centered zoom must remain enabled');
assert.match(sceneSource,/controls\.touches\.TWO=T\.TOUCH\.DOLLY_PAN/,'Mobile two-finger pinch/pan must remain enabled');
assert.match(sceneSource,/computeHairlineProposal/,'Hairline segmentation proposal code missing');
assert.match(sceneSource,/focusLandmark/,'Landmark auto-focus code missing');
assert.match(sceneSource,/p\.name!==['"]Skin['"]/,'Canonical anchor raycasts must be restricted to Skin');

assert.match(sceneSource,/middle-finger-pip-radial-joint-surface-local/,'PIP detector must use local middle-finger surface search');
assert.match(sceneSource,/middle-finger-dip-radial-joint-surface-local/,'DIP detector must use local middle-finger surface search');
assert.match(sceneSource,/originOffset=Math\.max\(\.014,radialHalf\+\.01\)/,'Finger detector origin must remain local to the target digit');
assert.match(sceneSource,/jointDistance>maxTravel\+\.006\|\|axialError>\.018/,'Finger detector must reject nonlocal or off-joint skin hits');
