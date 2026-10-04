import fs from 'node:fs';
import assert from 'node:assert/strict';

const modelBase=new URL('../public/models/',import.meta.url);
const knowledgeBase=new URL('../public/knowledge/',import.meta.url);

const read=name=>JSON.parse(fs.readFileSync(new URL(name,knowledgeBase),'utf8'));
const atlas=JSON.parse(fs.readFileSync(new URL('atlas.json',modelBase),'utf8'));
const anatomyKo=read('anatomy-ko.json');
const sources=read('sources.json');
const acupoints=read('acupoints.json');
const meridianSinews=read('meridian-sinews.json');
const anatomyAcupointRelations=read('anatomy-acupoint-relations.json');
const anatomyMeridianSinewRelations=read('anatomy-meridian-sinew-relations.json');

const concepts=new Map(atlas.concepts.map(concept=>[concept.id,concept]));
const sourceIds=new Set(Object.keys(sources));
const meridianIds=new Set(['LU','LI','ST','SP','HT','SI','BL','KI','PC','TE','GB','LR']);

assert.ok(Object.keys(anatomyKo).length>0,'Korean anatomy localization is empty.');

for(const [conceptId,entry] of Object.entries(anatomyKo)){
  assert.ok(concepts.has(conceptId),`${conceptId}: localization points to a missing atlas concept`);
  assert.equal(typeof entry.nameKo,'string',`${conceptId}: nameKo must be a string`);
  assert.ok(entry.nameKo.trim(),`${conceptId}: nameKo is empty`);
  if(entry.legacyKo!==undefined)assert.ok(typeof entry.legacyKo==='string'&&entry.legacyKo.trim(),`${conceptId}: legacyKo is invalid`);
  if(entry.hanja!==undefined)assert.ok(typeof entry.hanja==='string'&&entry.hanja.trim(),`${conceptId}: hanja is invalid`);
  if(entry.descriptionKo!==undefined)assert.ok(typeof entry.descriptionKo==='string'&&entry.descriptionKo.trim(),`${conceptId}: descriptionKo is invalid`);
  if(entry.aliases!==undefined){
    assert.ok(Array.isArray(entry.aliases),`${conceptId}: aliases must be an array`);
    const normalized=entry.aliases.map(value=>String(value).trim()).filter(Boolean);
    assert.equal(new Set(normalized).size,normalized.length,`${conceptId}: aliases contain duplicates`);
  }
}

for(const [sourceId,source] of Object.entries(sources)){
  assert.equal(source.id,sourceId,`${sourceId}: source id must match its object key`);
  assert.ok(typeof source.title==='string'&&source.title.trim(),`${sourceId}: source title is missing`);
}

const acupointIds=new Set();
for(const point of acupoints){
  assert.ok(point.id&&!acupointIds.has(point.id),`${point.id}: duplicate or missing acupoint id`);
  acupointIds.add(point.id);
  assert.ok(meridianIds.has(point.meridian),`${point.id}: invalid meridian`);
  assert.ok(point.name?.ko?.trim()&&point.name?.hanja?.trim(),`${point.id}: Korean/Hanja name is required`);
  assert.ok(['midline','bilateral'].includes(point.laterality),`${point.id}: invalid laterality`);
  assert.ok(Array.isArray(point.sourceIds)&&point.sourceIds.length,`${point.id}: sourceIds are required`);
  for(const id of point.sourceIds)assert.ok(sourceIds.has(id),`${point.id}: missing source ${id}`);
}

const sinewIds=new Set();
for(const sinew of meridianSinews){
  assert.ok(sinew.id&&!sinewIds.has(sinew.id),`${sinew.id}: duplicate or missing meridian sinew id`);
  sinewIds.add(sinew.id);
  assert.ok(meridianIds.has(sinew.meridian),`${sinew.id}: invalid meridian`);
  assert.ok(sinew.name?.ko?.trim()&&sinew.name?.hanja?.trim()&&sinew.name?.en?.trim(),`${sinew.id}: names are incomplete`);
  for(const id of sinew.sourceIds??[])assert.ok(sourceIds.has(id),`${sinew.id}: missing source ${id}`);
}
assert.equal(sinewIds.size,12,'Expected all twelve meridian sinews.');

for(const relation of anatomyAcupointRelations){
  assert.ok(concepts.has(relation.anatomyId),`${relation.anatomyId}: acupoint relation points to missing anatomy concept`);
  assert.ok(acupointIds.has(relation.acupointId),`${relation.acupointId}: missing acupoint`);
  for(const id of relation.sourceIds??[])assert.ok(sourceIds.has(id),`acupoint relation: missing source ${id}`);
}

for(const relation of anatomyMeridianSinewRelations){
  assert.ok(concepts.has(relation.anatomyId),`${relation.anatomyId}: sinew relation points to missing anatomy concept`);
  assert.ok(sinewIds.has(relation.meridianSinewId),`${relation.meridianSinewId}: missing meridian sinew`);
  assert.ok(['direct-landmark','regional','interpretive'].includes(relation.correspondence),`${relation.anatomyId}: invalid correspondence`);
  for(const id of relation.sourceIds??[])assert.ok(sourceIds.has(id),`sinew relation: missing source ${id}`);
}

console.log(`Verified ${Object.keys(anatomyKo).length} Korean anatomy localizations, ${acupointIds.size} pilot acupoints, ${sinewIds.size} meridian sinews, ${anatomyAcupointRelations.length} anatomy-acupoint relations, and ${anatomyMeridianSinewRelations.length} anatomy-sinew relations against ${atlas.concepts.length} atlas concepts.`);
