import fs from 'node:fs';
import path from 'node:path';

const root=path.resolve('dist');
const MAX_FILES=20_000;
const MAX_FILE_BYTES=25*1024*1024;

if(!fs.existsSync(root))throw new Error('dist/ does not exist; run npm run build first.');
if(!fs.existsSync(path.join(root,'index.html')))throw new Error('dist/index.html is missing.');

const files=[];
const walk=dir=>{
  for(const entry of fs.readdirSync(dir,{withFileTypes:true})){
    const full=path.join(dir,entry.name);
    if(entry.isDirectory())walk(full);
    else if(entry.isFile())files.push(full);
  }
};
walk(root);

if(files.length>MAX_FILES)throw new Error(`Cloudflare Pages Free file limit exceeded: ${files.length} > ${MAX_FILES}`);

let largest={path:'',bytes:0};
for(const file of files){
  const bytes=fs.statSync(file).size;
  if(bytes>largest.bytes)largest={path:path.relative(root,file),bytes};
  if(bytes>MAX_FILE_BYTES)throw new Error(`Cloudflare Pages single-file limit exceeded: ${path.relative(root,file)} is ${(bytes/1024/1024).toFixed(2)} MiB > 25 MiB`);
}

console.log(JSON.stringify({
  cloudflarePagesStaticCheck:'pass',
  files:files.length,
  largestFile:largest.path,
  largestFileMiB:Number((largest.bytes/1024/1024).toFixed(2)),
  limits:{maxFiles:MAX_FILES,maxSingleFileMiB:25}
},null,2));
