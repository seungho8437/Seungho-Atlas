import {readdirSync,readFileSync,statSync} from 'node:fs';
import {join,relative} from 'node:path';

const root='scripts/cv3';
const banned=[
 {label:'acupoint-placements',re:/acupoint-placements/i},
 {label:'acupoint-render',re:/acupoint-render/i},
 {label:'data/',re:/data\//}
];
const files=[];
function walk(dir){for(const name of readdirSync(dir)){const p=join(dir,name),st=statSync(p);if(st.isDirectory())walk(p);else files.push(p);}}
walk(root);
const hits=[];
for(const file of files){
 const text=readFileSync(file,'utf8'),lines=text.split(/\r?\n/);
 lines.forEach((line,i)=>{for(const b of banned)if(b.re.test(line))hits.push({file:relative('.',file),line:i+1,token:b.label,text:line.trim()});});
}
if(hits.length){for(const h of hits)console.error(`LEAK ${h.file}:${h.line} [${h.token}] ${h.text}`);console.error(`Placement isolation FAILED: ${hits.length} forbidden reference(s)`);process.exit(1);}
console.log(`Placement isolation PASS: scanned ${files.length} C v3 files; no acupoint-placements, acupoint-render, or data/ references.`);
