import fs from 'node:fs';
import assert from 'node:assert/strict';

const modelBase=new URL('../public/models/',import.meta.url);
const knowledgeBase=new URL('../public/knowledge/',import.meta.url);

const atlas=JSON.parse(fs.readFileSync(new URL('atlas.json',modelBase),'utf8'));
const anatomyKo=JSON.parse(fs.readFileSync(new URL('anatomy-ko.json',knowledgeBase),'utf8'));
const sources=JSON.parse(fs.readFileSync(new URL('sources.json',knowledgeBase),'utf8'));

const concepts=new Map(atlas.concepts.map(concept=>[concept.id,concept]));
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

console.log(`Verified ${Object.keys(anatomyKo).length} Korean anatomy localizations against ${atlas.concepts.length} atlas concepts and ${Object.keys(sources).length} knowledge sources.`);
