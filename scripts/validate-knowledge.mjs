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
const acupointCoordinateRegistry=read('acupoint-coordinates.json');

const concepts=new Map(atlas.concepts.map(concept=>[concept.id,concept]));
const sourceIds=new Set(Object.keys(sources));
const meridianIds=new Set(['LU','LI','ST','SP','HT','SI','BL','KI','PC','TE','GB','LR','GV','CV']);
const sinewMeridianIds=new Set(['LU','LI','ST','SP','HT','SI','BL','KI','PC','TE','GB','LR']);
const expectedPointCounts={LU:11,LI:20,ST:45,SP:21,HT:9,SI:19,BL:67,KI:27,PC:9,TE:23,GB:44,LR:14,GV:28,CV:24};

assert.equal(Object.keys(anatomyKo).length,atlas.concepts.length,'Every atlas concept must have a localization record.');
let verifiedLocalizations=0,derivedLocalizations=0,reviewNeededLocalizations=0;

for(const [conceptId,entry] of Object.entries(anatomyKo)){
  assert.ok(concepts.has(conceptId),`${conceptId}: localization points to a missing atlas concept`);
  assert.ok(['verified','derived','review-needed'].includes(entry.status),`${conceptId}: invalid localization status`);
  if(entry.status==='review-needed')reviewNeededLocalizations++;
  else if(entry.status==='verified')verifiedLocalizations++;else derivedLocalizations++;
  assert.equal(typeof entry.nameKo,'string',`${conceptId}: localization requires nameKo`);
  assert.ok(entry.nameKo.trim(),`${conceptId}: nameKo is empty`);
  assert.ok(typeof entry.legacyKo==='string'&&entry.legacyKo.trim(),`${conceptId}: localization requires legacyKo`);
  assert.ok(typeof entry.hanja==='string'&&entry.hanja.trim(),`${conceptId}: localization requires hanja`);
  if(entry.sourceNameEn!==undefined)assert.equal(entry.sourceNameEn,concepts.get(conceptId).name,`${conceptId}: source English name drift`);
  if(entry.descriptionKo!==undefined)assert.ok(typeof entry.descriptionKo==='string'&&entry.descriptionKo.trim(),`${conceptId}: descriptionKo is invalid`);
  for(const id of entry.sourceIds??[])assert.ok(sourceIds.has(id),`${conceptId}: missing localization source ${id}`);
  if(entry.aliases!==undefined){
    assert.ok(Array.isArray(entry.aliases),`${conceptId}: aliases must be an array`);
    const normalized=entry.aliases.map(value=>String(value).trim()).filter(Boolean);
    assert.equal(new Set(normalized).size,normalized.length,`${conceptId}: aliases contain duplicates`);
  }
}
assert.equal(verifiedLocalizations+derivedLocalizations+reviewNeededLocalizations,atlas.concepts.length,'Localization status counts must cover the atlas.');
assert.equal(reviewNeededLocalizations,0,'All 3,432 anatomy concepts must be resolved; review-needed entries are not allowed.');

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

assert.equal(acupointIds.size,361,'Expected exactly 361 standard acupuncture points.');
for(const [meridian,count] of Object.entries(expectedPointCounts))assert.equal(acupoints.filter(point=>point.meridian===meridian).length,count,`${meridian}: unexpected acupuncture point count`);

const sinewIds=new Set();
for(const sinew of meridianSinews){
  assert.ok(sinew.id&&!sinewIds.has(sinew.id),`${sinew.id}: duplicate or missing meridian sinew id`);
  sinewIds.add(sinew.id);
  assert.ok(sinewMeridianIds.has(sinew.meridian),`${sinew.id}: invalid meridian sinew channel`);
  assert.ok(sinew.name?.ko?.trim()&&sinew.name?.hanja?.trim()&&sinew.name?.en?.trim(),`${sinew.id}: names are incomplete`);
  assert.ok(typeof sinew.overviewKo==='string'&&sinew.overviewKo.trim(),`${sinew.id}: classical pathway summary is missing`);
  assert.ok((sinew.sourceIds??[]).includes('LINGSHU_JINGJIN'),`${sinew.id}: classical Jingjin source is required`);
  for(const id of sinew.sourceIds??[])assert.ok(sourceIds.has(id),`${sinew.id}: missing source ${id}`);
}
assert.equal(sinewIds.size,12,'Expected all twelve meridian sinews.');

for(const relation of anatomyAcupointRelations){
  assert.ok(concepts.has(relation.anatomyId),`${relation.anatomyId}: acupoint relation points to missing anatomy concept`);
  assert.ok(acupointIds.has(relation.acupointId),`${relation.acupointId}: missing acupoint`);
  for(const id of relation.sourceIds??[])assert.ok(sourceIds.has(id),`acupoint relation: missing source ${id}`);
}

assert.equal(acupointCoordinateRegistry.version,1,'Unsupported acupoint coordinate registry version');
assert.equal(acupointCoordinateRegistry.model,'BodyParts3D-4.0','Acupoint coordinates must be model-specific to BodyParts3D 4.0');
assert.ok(Array.isArray(acupointCoordinateRegistry.points),'Acupoint coordinate points must be an array');
for(const coordinate of acupointCoordinateRegistry.points){
  assert.ok(acupointIds.has(coordinate.acupointId),`${coordinate.acupointId}: coordinate points to missing acupoint`);
  assert.ok(['left','right','midline'].includes(coordinate.side),`${coordinate.acupointId}: invalid coordinate side`);
  assert.ok(Array.isArray(coordinate.position)&&coordinate.position.length===3&&coordinate.position.every(Number.isFinite),`${coordinate.acupointId}: invalid 3D coordinate`);
  assert.equal(coordinate.model,'BodyParts3D-4.0',`${coordinate.acupointId}: coordinate model mismatch`);
  assert.equal(coordinate.status,'validated',`${coordinate.acupointId}: only validated coordinates may render`);
  for(const id of coordinate.sourceIds??[])assert.ok(sourceIds.has(id),`${coordinate.acupointId}: missing coordinate source ${id}`);
}

const pointById=new Map(acupoints.map(point=>[point.id,point]));
assert.equal(pointById.get('ST36')?.name.ko,'족삼리','ST36 Korean name regression');
assert.equal(pointById.get('LI4')?.name.ko,'합곡','LI4 Korean name regression');
assert.equal(pointById.get('GV20')?.name.ko,'백회','GV20 Korean name regression');
assert.equal(pointById.get('CV17')?.name.ko,'전중','CV17 Korean name regression');
const sinewById=new Map(meridianSinews.map(sinew=>[sinew.id,sinew]));
assert.equal(sinewById.get('ST-JINGJIN')?.name.ko,'족양명위경근','ST meridian sinew name regression');
assert.ok(sinewById.get('ST-JINGJIN')?.overviewKo?.includes('정강이'),'ST meridian sinew pathway regression');

for(const relation of anatomyMeridianSinewRelations){
  assert.ok(concepts.has(relation.anatomyId),`${relation.anatomyId}: sinew relation points to missing anatomy concept`);
  assert.ok(sinewIds.has(relation.meridianSinewId),`${relation.meridianSinewId}: missing meridian sinew`);
  assert.ok(['direct-landmark','regional','interpretive'].includes(relation.correspondence),`${relation.anatomyId}: invalid correspondence`);
  for(const id of relation.sourceIds??[])assert.ok(sourceIds.has(id),`sinew relation: missing source ${id}`);
}

console.log(`Verified ${Object.keys(anatomyKo).length} anatomy localization records (${verifiedLocalizations} verified, ${derivedLocalizations} derived, ${reviewNeededLocalizations} review-needed), ${acupointIds.size} standard acupoints, ${sinewIds.size} meridian sinews, ${anatomyAcupointRelations.length} anatomy-acupoint relations, and ${anatomyMeridianSinewRelations.length} anatomy-sinew relations, plus ${acupointCoordinateRegistry.points.length} validated BodyParts3D acupoint coordinates against ${atlas.concepts.length} atlas concepts.`);
