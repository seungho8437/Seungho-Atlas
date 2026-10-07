import {createHash} from 'node:crypto';
import {readdirSync,readFileSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';

const modelDir='public/models';
const bodyFiles=readdirSync(modelDir).filter(name=>/^body-\d+\.bin$/.test(name)).sort((a,b)=>Number(a.match(/\d+/)?.[0])-Number(b.match(/\d+/)?.[0]));
const files=['atlas.json',...bodyFiles];
const hash=createHash('sha256');
for(const name of files)hash.update(readFileSync(join(modelDir,name)));
const atlas=JSON.parse(readFileSync(join(modelDir,'atlas.json'),'utf8'));
const skin=atlas.parts.find(part=>part.id==='FJ2810');
if(!skin)throw new Error('Skin part FJ2810 not found');
const out={atlas_sha256:hash.digest('hex'),skin_part_id:'FJ2810',skin_triangles:skin.indexCount/3};
if(process.argv.includes('--stdout'))console.log('ATLAS_SHA256='+out.atlas_sha256);
else if(process.argv.includes('--check')){
 const saved=JSON.parse(readFileSync(join(modelDir,'atlas.hash.json'),'utf8'));
 if(saved.atlas_sha256!==out.atlas_sha256||saved.skin_part_id!==out.skin_part_id||saved.skin_triangles!==out.skin_triangles){
  console.error('atlas.hash.json is stale', {expected:out,actual:saved});process.exit(1);
 }
 console.log('Atlas hash binding PASS',out.atlas_sha256);
}else{writeFileSync(join(modelDir,'atlas.hash.json'),JSON.stringify(out,null,2)+'\n');console.log('Wrote public/models/atlas.hash.json',out.atlas_sha256);}
