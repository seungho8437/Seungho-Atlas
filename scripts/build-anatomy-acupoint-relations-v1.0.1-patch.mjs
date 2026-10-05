import fs from 'node:fs';
import zlib from 'node:zlib';
import crypto from 'node:crypto';

const root=new URL('../',import.meta.url);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const stable=v=>JSON.stringify(v);
const write=(p,v)=>{const u=new URL(p,root);fs.mkdirSync(new URL('./',u),{recursive:true});fs.writeFileSync(u,JSON.stringify(v,null,2)+'\n');};

const BASE_SHA='6dd00d386a6262d02900ec5a30ea9b18aace899f071159e772c12679740b1d06';
const packed=Buffer.from(fs.readFileSync(new URL('scripts/data/anatomy-acupoint-relations-v1.json.gz.b64.txt',root),'utf8').trim(),'base64');
const bytes=zlib.gunzipSync(packed);
if(sha(bytes)!==BASE_SHA) throw new Error('base frozen-B SHA mismatch');
const before=JSON.parse(bytes.toString('utf8'));
const after=structuredClone(before);

const geometryById=new Map(after.geometry_nodes.map(x=>[x.node_id,x]));
const landmarkById=new Map(after.landmark_nodes.map(x=>[x.node_id,x]));
const sourceById=new Map(after.source_statements.map(x=>[x.source_statement_id,x]));

const patches=[
  {
    node_id:'G:S:CV1:location:line:0',
    expected_before:['L:1562'],
    after:['L:1562','L:1563'],
    source_statement_id:'S:CV1:location',
    expected_source_terms:['midpoint','line connecting','anus'],
    evidence_note:'WHO Location requires the line joining anus to the sex-specific posterior genital landmark.'
  },
  {
    node_id:'G:S:CV12:note:1:line:0',
    expected_before:['N:CV12:1:m2'],
    after:['N:CV12:1:m2','L:1594'],
    source_statement_id:'S:CV12:note:1',
    expected_source_terms:['midpoint','line connecting','xiphisternal','umbilicus'],
    evidence_note:'WHO Note requires xiphisternal junction ↔ centre of umbilicus.'
  }
];

const affected=[];
for(const p of patches){
  const g=geometryById.get(p.node_id);
  if(!g)throw new Error('missing geometry '+p.node_id);
  if(stable(g.endpoint_node_ids??[])!==stable(p.expected_before))throw new Error('unexpected before endpoints '+p.node_id+' '+stable(g.endpoint_node_ids));
  const src=sourceById.get(p.source_statement_id);
  if(!src)throw new Error('missing source '+p.source_statement_id);
  const srcText=String(src.text_canonical??src.text??'').toLowerCase();
  for(const term of p.expected_source_terms)if(!srcText.includes(term))throw new Error('source evidence term missing '+p.node_id+': '+term);
  for(const id of p.after)if(!landmarkById.has(id))throw new Error('patch endpoint is not existing landmark node '+id);
  const beforeRecord=structuredClone(g);
  g.endpoint_node_ids=[...p.after];
  const afterRecord=structuredClone(g);
  affected.push({
    geometry_node_id:p.node_id,
    before:beforeRecord,
    after:afterRecord,
    source_evidence:src,
    endpoint_records:p.after.map(id=>landmarkById.get(id)),
    evidence_note:p.evidence_note
  });
}

// Exact minimal-diff proof: revert the two patched arrays and require full graph identity.
const reverted=structuredClone(after);
const revById=new Map(reverted.geometry_nodes.map(x=>[x.node_id,x]));
for(const p of patches)revById.get(p.node_id).endpoint_node_ids=[...p.expected_before];
if(stable(reverted)!==stable(before))throw new Error('diff outside the two authorized endpoint arrays');

const allNodeIds=new Set([...after.landmark_nodes.map(x=>x.node_id),...after.geometry_nodes.map(x=>x.node_id)]);
const orphanArguments=[];
for(const r of after.relation_instances)for(const id of r.argument_node_ids??[])if(!allNodeIds.has(id))orphanArguments.push({relation_id:r.relation_id,node_id:id});
for(const g of after.geometry_nodes)for(const id of g.endpoint_node_ids??[])if(!allNodeIds.has(id))orphanArguments.push({geometry_node_id:g.node_id,node_id:id});

const cardinalityErrors=[];
for(const g of after.geometry_nodes){
  const n=(g.endpoint_node_ids??[]).length;
  if(['constructed_line','reference_line'].includes(g.geometry_type)&&n!==2)cardinalityErrors.push({kind:'geometry_line',node_id:g.node_id,count:n});
  if(String(g.geometry_type??'').includes('midpoint')&&n!==2)cardinalityErrors.push({kind:'geometry_midpoint',node_id:g.node_id,count:n});
}
for(const r of after.relation_instances){
  const n=(r.argument_node_ids??[]).length;
  if(['between','midpoint-between','fraction-along-line'].includes(r.relation_type)&&n<2)cardinalityErrors.push({kind:'relation',relation_id:r.relation_id,type:r.relation_type,count:n});
}

const atlas=JSON.parse(fs.readFileSync(new URL('public/models/atlas.json',root),'utf8'));
const conceptIds=new Set(atlas.concepts.map(x=>x.id));
const invalidFma=after.landmark_nodes.filter(x=>x.fma_id&&!conceptIds.has(x.fma_id)).map(x=>({node_id:x.node_id,fma_id:x.fma_id}));

const sourcePreserved=stable(after.source_statements)===stable(before.source_statements);
const landmarksPreserved=stable(after.landmark_nodes)===stable(before.landmark_nodes);
const relationsPreserved=stable(after.relation_instances)===stable(before.relation_instances);
const pointsPreserved=stable(after.points)===stable(before.points);

const provenanceLoss=[];
for(const s of after.source_statements){
  if(!s.frozen_source_sha256)provenanceLoss.push({source_statement_id:s.source_statement_id,missing:'frozen_source_sha256'});
  if(s.section==='location'&&!s.source?.primary_source)provenanceLoss.push({source_statement_id:s.source_statement_id,missing:'source.primary_source'});
}
const lineageFields=['component_lineage','component_id','parent_component_id','source_mention_node_id','source_statement_id','point_id'];
let lineagePreserved=true;
for(let i=0;i<before.landmark_nodes.length;i++)for(const k of lineageFields)if(stable(before.landmark_nodes[i][k])!==stable(after.landmark_nodes[i][k]))lineagePreserved=false;
for(let i=0;i<before.geometry_nodes.length;i++)for(const k of lineageFields)if(stable(before.geometry_nodes[i][k])!==stable(after.geometry_nodes[i][k]))lineagePreserved=false;

const afterText=JSON.stringify(after,null,2)+'\n';
const afterBytes=Buffer.from(afterText);
const patchSha=sha(afterBytes);
const compressed=zlib.gzipSync(afterBytes,{level:9});
fs.mkdirSync(new URL('scripts/data/',root),{recursive:true});
fs.writeFileSync(new URL('scripts/data/anatomy-acupoint-relations-v1.0.1-patch.json.gz.b64.txt',root),compressed.toString('base64')+'\n');

const regression={
  schema_version:'1.0.0',
  artifact:'anatomy-acupoint-relations-v1.0.1-patch-regression.json',
  base_sha256:BASE_SHA,
  patched_sha256:patchSha,
  authorized_patch_nodes:patches.map(x=>x.node_id),
  checks:{
    points_361:after.points.length===361,
    landmark_nodes_2325:after.landmark_nodes.length===2325,
    source_statements_preserved:sourcePreserved,
    landmarks_preserved:landmarksPreserved,
    relation_instances_preserved:relationsPreserved,
    points_preserved:pointsPreserved,
    cv1_cv12_only_diff:true,
    orphan_argument_zero:orphanArguments.length===0,
    relation_cardinality_error_zero:cardinalityErrors.length===0,
    invalid_fma_id_zero:invalidFma.length===0,
    source_provenance_loss_zero:provenanceLoss.length===0,
    component_lineage_preserved:lineagePreserved
  },
  counts:{
    points:after.points.length,
    landmark_nodes:after.landmark_nodes.length,
    geometry_nodes:after.geometry_nodes.length,
    relation_instances:after.relation_instances.length,
    source_statements:after.source_statements.length,
    orphan_arguments:orphanArguments.length,
    relation_cardinality_errors:cardinalityErrors.length,
    invalid_fma_ids:invalidFma.length,
    source_provenance_loss:provenanceLoss.length
  },
  failures:{orphanArguments,cardinalityErrors,invalidFma,provenanceLoss}
};
if(Object.values(regression.checks).some(x=>x!==true))throw new Error('B patch regression failed '+JSON.stringify(regression,null,2));

const report={
  schema_version:'1.0.0',
  patch_version:'anatomy-acupoint-relations v1.0.1 minimal geometry-cardinality patch',
  base_frozen_sha256:BASE_SHA,
  patched_sha256:patchSha,
  frozen_base_preserved:true,
  scope:'CV1/CV12 reference-line endpoint_node_ids only',
  affected_records:affected,
  regression
};
write('public/knowledge/anatomy-acupoint-relations-v1.0.1-patch-report.json',report);
write('public/knowledge/anatomy-acupoint-relations-v1.0.1-patch-regression.json',regression);
console.log(JSON.stringify({patched_sha256:patchSha,affected:affected.map(x=>({id:x.geometry_node_id,before:x.before.endpoint_node_ids,after:x.after.endpoint_node_ids})),regression},null,2));
