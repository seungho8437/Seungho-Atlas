import fs from 'node:fs';
const root=new URL('../',import.meta.url),read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const c=read('public/knowledge/acupoint-coordinates-v2.json'),q=read('public/knowledge/acupoint-coordinate-qc-v2.json'),r=read('public/knowledge/acupoint-bodyparts3d-realization-v2.json'),m=read('public/knowledge/acupoint-coordinate-manifest-v2.json');
const fail=x=>{throw new Error(x)};
if(c.frozen_B_sha256!=='6dd00d386a6262d02900ec5a30ea9b18aace899f071159e772c12679740b1d06')fail('frozen B hash');
if(m.frozen_B_modified!==false||!m.v1_baseline_preserved)fail('baseline/frozen invariant');
if(c.points.length!==670)fail('physical count');
if(new Set(c.points.map(x=>x.point_id)).size!==361)fail('logical count');
if(c.points.some(x=>x.final_validated))fail('v2 must not auto-final-validate before visual QC');
for(const x of c.points){
 if(x.relation_satisfied&&!x.relation_executed)fail('satisfied without execution '+x.point_id);
 if(x.surface_projected&&(!Array.isArray(x.coordinate_projected)||x.coordinate_projected.length!==3))fail('projection missing '+x.point_id);
 if(x.status==='relation_satisfied_surface_projected_pending_visual_qc'&&(!x.relation_satisfied||!x.surface_projected))fail('status invariant '+x.point_id);
}
if((q.B_minimal_reopen_candidates?.issue_count??0)!==2)fail('expected exactly 2 adjudicated B geometry blockers');
if(!r.anchor_corrections.some(x=>x.anchor_id==='suprasternal-notch'))fail('anchor correction missing');
console.log(JSON.stringify({PASS:true,summary:c.summary,B:q.B_minimal_reopen_candidates},null,2));
