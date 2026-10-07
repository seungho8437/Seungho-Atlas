import fs from 'node:fs';
const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const fail=m=>{throw new Error(m)};
const real=read('public/knowledge/acupoint-bodyparts3d-realization.json');
const input=read('public/knowledge/acupoint-coordinate-solver-input.json');
const coords=read('public/knowledge/acupoint-coordinates.json');
const qc=read('public/knowledge/acupoint-coordinate-qc.json');
const reg=read('public/knowledge/acupoint-coordinate-regression-report.json');
const manifest=read('public/knowledge/acupoint-coordinate-manifest.json');
if(real.landmark_realizations.length!==2325)fail('realization landmark count');
if(real.geometry_realizations.length!==97)fail('geometry realization count');
if(input.relation_plans.length!==2595)fail('relation plan count');
if(coords.logical_point_count!==361)fail('logical point count');
if(new Set(coords.points.map(x=>x.point_id)).size!==361)fail('361 coverage');
for(const p of coords.points){
 if(p.coordinate_status==='solved'){
  if(!Array.isArray(p.coordinate_raw)||!Array.isArray(p.coordinate_projected))fail('solved coordinate missing '+p.point_id+':'+p.side);
  if(p.validation?.surfacePartId!=='FJ2810')fail('solved point not Skin-projected '+p.point_id+':'+p.side);
 }
 if(p.side==='midline'&&p.mesh_object_provenance.some(x=>x.selection?.status==='side-matched'))fail('midline selected lateral object '+p.point_id);
 if(p.mesh_object_provenance.some(x=>x.selection?.status==='contralateral_or_ambiguous'))fail('contralateral object leaked '+p.point_id+':'+p.side);
}
if(Object.values(reg.checks).some(x=>x!==true))fail('regression invariant failure');
if(manifest.frozen_B_modified!==false||qc.frozen_B_modification!==false)fail('frozen B mutation marker');
console.log(JSON.stringify({PASS:true,realization:real.summary,coordinates:coords.status_summary,qc:qc.summary,regression:reg.checks},null,2));