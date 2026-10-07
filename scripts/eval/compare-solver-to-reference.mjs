import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {basename} from 'node:path';

const DISCLAIMER='기준은 사람이 배치한 참조값이며 정답이 아니다. 불일치는 솔버와 기준 중 어느 쪽이 틀렸는지 확인하라는 신호다.';
const candidatePath=process.argv[2];
if(!candidatePath){console.error('Usage: node scripts/eval/compare-solver-to-reference.mjs <candidate.json>');process.exit(2);}
const reference=JSON.parse(readFileSync('public/knowledge/acupoint-render.json','utf8'));
const candidate=JSON.parse(readFileSync(candidatePath,'utf8'));
if(!Array.isArray(reference.points))throw new Error('Reference acupoint-render.json has no points array');
if(!Array.isArray(candidate.points))throw new Error('Unknown candidate schema: expected top-level points[]');

const ref=reference.points.filter(p=>p.origin==='placed'||p.origin==='mirrored');
const refByKey=new Map(ref.map(p=>[`${p.id}|${p.side}`,p]));
const refById=new Map();for(const p of ref){const a=refById.get(p.id)??[];a.push(p);refById.set(p.id,a);}
const dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
const meridian=id=>String(id).match(/^[A-Z]+/)?.[0]??'UNKNOWN';
const percentile=(values,q)=>{if(!values.length)return null;const a=[...values].sort((x,y)=>x-y),i=(a.length-1)*q,lo=Math.floor(i),hi=Math.ceil(i);return a[lo]+(a[hi]-a[lo])*(i-lo);};
const summary=values=>({
 count:values.length,
 median_cm:values.length?percentile(values,.5)*100:null,
 p90_cm:values.length?percentile(values,.9)*100:null,
 max_cm:values.length?Math.max(...values)*100:null,
 buckets:{'≤1cm':values.filter(x=>x<=.01).length,'≤2cm':values.filter(x=>x>.01&&x<=.02).length,'≤5cm':values.filter(x=>x>.02&&x<=.05).length,'>5cm':values.filter(x=>x>.05).length}
});
const resolvedClaim=status=>['VALIDATED','RESOLVED'].includes(String(status??'').toUpperCase());
const safeFailure=status=>['UNRESOLVED','CONDITIONAL'].includes(String(status??'').toUpperCase());

let schema,records=[],safeFailureIds=new Set(),blockedIds=new Set();
const isStage3=candidate.points.every(p=>Object.prototype.hasOwnProperty.call(p,'stage3_status')&&Array.isArray(p.coordinates));
if(isStage3){
 schema='c-v3-stage3-output';
 for(const p of candidate.points){
  if(typeof p.point_id!=='string')throw new Error('C v3 schema error: point_id is required');
  if(p.coordinates.length>0)throw new Error(`C v3 coordinate adapter is intentionally undefined: ${p.point_id} has coordinates[]. Inspect the first real coordinate object and implement an explicit adapter before evaluation.`);
  if(safeFailure(p.stage3_status)&&refById.has(p.point_id))safeFailureIds.add(p.point_id);
  else if(refById.has(p.point_id))blockedIds.add(p.point_id);
 }
}else{
 schema='legacy-v1-or-fixc';
 for(const [i,p] of candidate.points.entries()){
  const id=p.acupointId??p.point_id;
  if(typeof id!=='string')throw new Error(`Candidate schema error at points[${i}]: acupointId or point_id is required`);
  if(p.position!==undefined){
   if(!Array.isArray(p.position)||p.position.length!==3||!p.position.every(Number.isFinite))throw new Error(`Candidate schema error at ${id}: position must be a finite [x,y,z]`);
   if(!['left','right','midline'].includes(p.side))throw new Error(`Candidate schema error at ${id}: side is required for a coordinate`);
   records.push({id,side:p.side,position:p.position,status:p.status??''});
  }else if(safeFailure(p.status)&&refById.has(id))safeFailureIds.add(id);
 }
 if(!candidate.points.some(p=>p.position!==undefined||safeFailure(p.status)))throw new Error('Unknown candidate schema: points[] does not match supported legacy/fixc coordinate records or explicit unresolved records');
}

const matches=[],candidateKeys=new Set();
for(const p of records){
 const key=`${p.id}|${p.side}`;if(candidateKeys.has(key))throw new Error(`Candidate duplicate side coordinate: ${key}`);candidateKeys.add(key);
 const r=refByKey.get(key);if(!r)continue;const error_m=dist(p.position,r.position);matches.push({id:p.id,side:p.side,meridian:meridian(p.id),candidate_status:p.status,error_m,error_cm:error_m*100});
}
const errors=matches.map(x=>x.error_m),byMeridian={};
for(const m of new Set(ref.map(p=>meridian(p.id)))){
 const vals=matches.filter(x=>x.meridian===m).map(x=>x.error_m),refs=ref.filter(x=>meridian(x.id)===m).length;
 byMeridian[m]={reference_sides:refs,matched_sides:vals.length,...summary(vals)};
}
const falseResolved=matches.filter(x=>resolvedClaim(x.candidate_status)&&x.error_m>.05).sort((a,b)=>b.error_m-a.error_m);
const safeReferenceSides=[...safeFailureIds].reduce((n,id)=>n+(refById.get(id)?.length??0),0);
const blockedReferenceSides=[...blockedIds].reduce((n,id)=>n+(refById.get(id)?.length??0),0);
const report={
 disclaimer:DISCLAIMER,
 generated_at:new Date().toISOString(),
 reference:{path:'public/knowledge/acupoint-render.json',mesh_binding:reference.mesh_binding,reference_sides:ref.length,human_placed_source_points:new Set(ref.filter(p=>p.origin==='placed').map(p=>p.id)).size},
 candidate:{path:candidatePath,file:basename(candidatePath),schema},
 coverage:{candidate_coordinate_sides:records.length,matched_reference_sides:matches.length,reference_sides:ref.length,rate:ref.length?matches.length/ref.length:null},
 error:summary(errors),
 approximate_cun_note:'1 cun ≈ 2 cm is an approximate reporting conversion only.',
 by_meridian:byMeridian,
 false_resolved_over_5cm:falseResolved,
 safe_failure:{candidate_point_ids:[...safeFailureIds].sort(),candidate_point_count:safeFailureIds.size,reference_side_count:safeReferenceSides},
 blocked_or_other_without_coordinate:{candidate_point_ids:[...blockedIds].sort(),candidate_point_count:blockedIds.size,reference_side_count:blockedReferenceSides}
};
const date=new Date().toISOString().slice(0,10),dir='artifacts/eval';mkdirSync(dir,{recursive:true});
const base=`${dir}/solver-vs-reference-${date}`;
writeFileSync(base+'.json',JSON.stringify(report,null,2)+'\n');
const fmt=v=>v===null?'—':Number(v).toFixed(2);
const rows=Object.entries(byMeridian).map(([m,x])=>`| ${m} | ${x.matched_sides}/${x.reference_sides} | ${fmt(x.median_cm)} | ${fmt(x.p90_cm)} | ${fmt(x.max_cm)} |`).join('\n')||'| — | 0/0 | — | — | — |';
const falseRows=falseResolved.length?falseResolved.map(x=>`- ${x.id} ${x.side}: ${x.error_cm.toFixed(2)} cm (${x.candidate_status})`).join('\n'):'- 없음';
const md=`${DISCLAIMER}

# Solver vs HUMAN_PLACED reference

- Candidate: \`${candidatePath}\`
- Schema: \`${schema}\`
- Coverage (side-level): **${matches.length}/${ref.length}**
- Median / p90 / max error: **${fmt(report.error.median_cm)} / ${fmt(report.error.p90_cm)} / ${fmt(report.error.max_cm)} cm**
- Error buckets: ≤1 cm ${report.error.buckets['≤1cm']}, ≤2 cm ${report.error.buckets['≤2cm']}, ≤5 cm ${report.error.buckets['≤5cm']}, >5 cm ${report.error.buckets['>5cm']}
- Safe failure (UNRESOLVED/CONDITIONAL): **${safeFailureIds.size} candidate point(s), ${safeReferenceSides} reference side(s)**
- 1 cun ≈ 2 cm is an **approximate reporting conversion only**.

## Meridian summary

| Meridian | matched/reference sides | median cm | p90 cm | max cm |
| --- | ---: | ---: | ---: | ---: |
${rows}

## False-resolved (>5 cm while candidate claims validated/RESOLVED)

${falseRows}
`;
writeFileSync(base+'.md',md);
console.log(`Wrote ${base}.json and .md; coverage ${matches.length}/${ref.length}; false-resolved ${falseResolved.length}`);
