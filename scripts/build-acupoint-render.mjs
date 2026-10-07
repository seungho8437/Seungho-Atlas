import {readFileSync,writeFileSync} from 'node:fs';
import {buildRenderRegistry,loadBinding} from './lib/acupoint-placement.mjs';
const source=JSON.parse(readFileSync('data/acupoint-placements.source.json','utf8'));
const acupoints=JSON.parse(readFileSync('public/knowledge/acupoints.json','utf8'));
const binding=loadBinding();
const render=buildRenderRegistry(source,acupoints,binding);
writeFileSync('public/knowledge/acupoint-render.json',JSON.stringify(render,null,2)+'\n');
console.log('Built acupoint-render.json',render.counts);
