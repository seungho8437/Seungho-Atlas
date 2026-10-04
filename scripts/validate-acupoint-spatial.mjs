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
