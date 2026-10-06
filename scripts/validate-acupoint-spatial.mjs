import fs from 'node:fs';

const root=new URL('../',import.meta.url);
const read=p=>JSON.parse(fs.readFileSync(new URL(p,root),'utf8'));
const coords=read('public/knowledge/acupoint-coordinates.json');
const audit=read('public/knowledge/acupoint-coordinates-audit.json');

const fail=(message,details)=>{throw new Error(message+(details?': '+JSON.stringify(details):''));};

if(audit.logicalAcupoints!==361)fail('Expected 361 logical acupoints',audit.logicalAcupoints);
if(audit.physicalCoordinates!==670||audit.expectedPhysicalCoordinates!==670)fail('Expected 670 physical coordinates',{physical:audit.physicalCoordinates,expected:audit.expectedPhysicalCoordinates});
if((audit.invalidGeometryOrLaterality??[]).length)fail('Surface/laterality invariant failed',audit.invalidGeometryOrLaterality);
if((audit.duplicateClusters??[]).length)fail('Near-duplicate invariant failed',audit.duplicateClusters);
if((audit.exactDuplicateClusters??[]).length)fail('Exact duplicate invariant failed',audit.exactDuplicateClusters);
if(!audit.spatialValidation?.regionConstrained)fail('Region-constrained projection was not applied to every coordinate');
if((audit.spatialValidation?.landmarkHardFailures??[]).length)fail('Landmark post-validation hard failures',audit.spatialValidation.landmarkHardFailures);
if((audit.spatialValidation?.topologyHardFailures??[]).length)fail('Meridian topology hard failures',audit.spatialValidation.topologyHardFailures);


const methodology=coords.methodology??{};
if(!String(methodology.anatomyConstraints??'').includes('anatomy-acupoint-relations-v2.1.json')) fail('C must consume B v2.1 directly',methodology.anatomyConstraints);
if(String(methodology.anatomyConstraints??'').includes('anatomy-acupoint-relations.json (B)')) fail('Legacy B registry is forbidden in C',methodology.anatomyConstraints);

const missingSemanticVersion=coords.points.filter(p=>p.validation?.semanticGraphVersion!=='2.1.0');
if(missingSemanticVersion.length) fail('Missing B v2.1 provenance',missingSemanticVersion.map(x=>x.acupointId+':'+x.side));

const logicalMultiplicity=new Map();
for(const p of coords.points){
  const sides=logicalMultiplicity.get(p.acupointId)??[];sides.push(p.side);logicalMultiplicity.set(p.acupointId,sides);
}
const badMultiplicity=[];
for(const [id,sides] of logicalMultiplicity){
  const expected=id.startsWith('CV')||id.startsWith('GV')?['midline']:['left','right'];
  const sorted=[...sides].sort(), exp=[...expected].sort();
  if(sorted.length!==exp.length||sorted.some((v,i)=>v!==exp[i])) badMultiplicity.push({id,sides,expected});
}
if(badMultiplicity.length) fail('Per-acupoint multiplicity invariant failed',badMultiplicity);

const noNativeOps=coords.points.filter(p=>(p.validation?.relationCount??0)>0&&(p.validation?.nativeOperationCount??0)===0);
if(noNativeOps.length>Math.ceil(coords.points.length*0.85)) fail('Native semantic execution coverage is effectively absent',{count:noNativeOps.length,total:coords.points.length});

const bad=coords.points.filter(p=>!p.validation?.surfaceProjected||!p.validation?.lateralityConsistent||!p.validation?.regionConstrained);
if(bad.length)fail('Coordinate-level spatial invariant failed',bad.map(x=>x.acupointId+':'+x.side));

const missingPost=coords.points.filter(p=>!p.validation?.landmarkPostValidation||!p.validation?.topologyValidation);
if(missingPost.length)fail('Missing post-validation metadata',missingPost.map(x=>x.acupointId+':'+x.side));

console.log('Acupoint spatial validation passed.');
console.log(JSON.stringify({
  logicalAcupoints:audit.logicalAcupoints,
  physicalCoordinates:audit.physicalCoordinates,
  projectionDistance:audit.projectionDistance,
  landmarkReviewCount:audit.spatialValidation.landmarkReviewCount,
  topologyReviewCount:audit.spatialValidation.topologyReviewCount,
  manualReviewQueue:(audit.spatialValidation.manualReviewQueue??[]).length
},null,2));
