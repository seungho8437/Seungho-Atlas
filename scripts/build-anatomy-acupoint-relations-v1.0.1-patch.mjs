import fs from 'node:fs';
import zlib from 'node:zlib';
import crypto from 'node:crypto';

const root=new URL('../',import.meta.url);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const BASE_SHA='6dd00d386a6262d02900ec5a30ea9b18aace899f071159e772c12679740b1d06';
const packed=Buffer.from(fs.readFileSync(new URL('scripts/data/anatomy-acupoint-relations-v1.json.gz.b64.txt',root),'utf8').trim(),'base64');
const bytes=zlib.gunzipSync(packed);
if(sha(bytes)!==BASE_SHA)throw new Error('base frozen-B SHA mismatch');
const g=JSON.parse(bytes.toString('utf8'));
const nodesByStatement=sid=>g.landmark_nodes.filter(x=>x.source_statement_id===sid);
const cv1=nodesByStatement('S:CV1:location');
const cv12=nodesByStatement('S:CV12:note:1');
const req={
 cv1_anus:cv1.find(x=>x.source_raw==='anus')??null,
 cv1_scrotum:cv1.find(x=>/scrotum/i.test(x.source_raw??''))??null,
 cv1_posterior_commissure:cv1.find(x=>/posterior commissure/i.test(x.source_raw??''))??null,
 cv1_labium_majoris:cv1.find(x=>/labium majoris/i.test(x.source_raw??''))??null,
 cv12_xiphisternal:cv12.find(x=>/xiphisternal/i.test(x.source_raw??''))??null,
 cv12_umbilicus:cv12.find(x=>/umbilicus/i.test(x.source_raw??''))??null
};
const missing=Object.entries(req).filter(([,v])=>!v).map(([k])=>k);
if(missing.length){
 throw new Error('SAFE BLOCK: requested two-geometry-record-only patch cannot represent WHO endpoints because frozen B lacks required source landmark nodes: '+missing.join(', ')+'. Do not fabricate or cross-bind endpoints. See public/knowledge/anatomy-acupoint-relations-v1.0.1-patch-preflight-blocker.json');
}
throw new Error('SAFE BLOCK: semantic preflight unexpectedly passed; patch implementation intentionally disabled pending explicit minimal-scope approval.');
