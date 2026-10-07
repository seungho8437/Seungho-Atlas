import {useEffect,useRef} from 'react';
import * as T from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js';
import {mergeGeometries} from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import {createExplosionLayout} from './explosion-layout';
import {decodeModelResponse} from './model-download';
import {PointerTap} from './pointer-tap';
import {SYSTEMS,type Atlas,type SceneState} from './anatomy';
import type {AcupointPlacementCandidate,AcupointPlacementPoint,AcupointRenderPoint} from '@/lib/anatomy-knowledge/acupoint-placement';
import type {LandmarkAnchorCandidate,LandmarkAnchorSide} from '@/lib/anatomy-knowledge/landmark-anchors';
interface Props {
 atlas:Atlas;state:SceneState;acupointRender:AcupointRenderPoint[];showAcupoints:boolean;visibleMeridians:string[];
 placementMode:boolean;placementTarget:{id:string;laterality:'midline'|'bilateral'}|null;placementPoints:AcupointPlacementPoint[];placementDraft:AcupointPlacementCandidate|null;onPlacementPick:(candidate:AcupointPlacementCandidate)=>void;
 anchorTarget:string|null;anchorDraft:LandmarkAnchorCandidate|null;detectorProposal:LandmarkAnchorCandidate|null;detectorSide:LandmarkAnchorSide;
 onAnchorPick:(candidate:LandmarkAnchorCandidate)=>void;onDetectorProposal:(candidate:LandmarkAnchorCandidate|null)=>void;
 onSelect:(id:string)=>void;onSelectAcupoint:(id:string)=>void;onProgress:(n:number)=>void;onError:(s:string)=>void
}
export default function AnatomyScene({atlas,state,acupointRender,showAcupoints,visibleMeridians,placementMode,placementTarget,placementPoints,placementDraft,onPlacementPick,anchorTarget,anchorDraft,detectorProposal,detectorSide,onAnchorPick,onDetectorProposal,onSelect,onSelectAcupoint,onProgress,onError}:Props){
 const host=useRef<HTMLDivElement>(null),latest=useRef(state),select=useRef(onSelect),selectAcupoint=useRef(onSelectAcupoint),showAcupointsRef=useRef(showAcupoints);
 const renderPointsRef=useRef(acupointRender),visibleMeridiansRef=useRef(visibleMeridians),placementModeRef=useRef(placementMode),placementTargetRef=useRef(placementTarget),placementPointsRef=useRef(placementPoints),placementDraftRef=useRef(placementDraft),placementPickRef=useRef(onPlacementPick),markerVersionRef=useRef(0);
 const anchorTargetRef=useRef(anchorTarget),anchorDraftRef=useRef(anchorDraft),detectorProposalStateRef=useRef(detectorProposal),detectorSideRef=useRef(detectorSide),anchorPickRef=useRef(onAnchorPick),detectorProposalRef=useRef(onDetectorProposal);
 latest.current=state;select.current=onSelect;selectAcupoint.current=onSelectAcupoint;showAcupointsRef.current=showAcupoints;
 renderPointsRef.current=acupointRender;visibleMeridiansRef.current=visibleMeridians;placementModeRef.current=placementMode;placementTargetRef.current=placementTarget;placementPointsRef.current=placementPoints;placementDraftRef.current=placementDraft;placementPickRef.current=onPlacementPick;markerVersionRef.current++;
 anchorTargetRef.current=anchorTarget;anchorDraftRef.current=anchorDraft;detectorProposalStateRef.current=detectorProposal;detectorSideRef.current=detectorSide;anchorPickRef.current=onAnchorPick;detectorProposalRef.current=onDetectorProposal;
 useEffect(()=>{
  const el=host.current!;let disposed=false,frame=0,dirty=true,ready=false,lastView='',lastReset=-1,lastIsolate='',layoutKey='',amount=0;
  let lastState:SceneState|null=null;
  const abort=new AbortController();
  let renderer:T.WebGLRenderer;
  try{renderer=new T.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});}catch{onError('This browser could not start the 3D viewer. Please try a browser with WebGL enabled.');return;}
  renderer.setPixelRatio(Math.min(devicePixelRatio,innerWidth<768?1.5:2));renderer.setClearColor('#f2f3f3');renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.12;el.appendChild(renderer.domElement);
  renderer.domElement.setAttribute('aria-label','Interactive human anatomy. Drag to orbit, pinch or scroll to zoom, and tap a structure to inspect it.');
  const scene=new T.Scene(),camera=new T.PerspectiveCamera(34,1,.005,100),controls=new OrbitControls(camera,renderer.domElement);
  camera.position.set(1.4,1.05,3.6);controls.target.set(0,.85,0);controls.enableDamping=true;controls.dampingFactor=.085;controls.minDistance=.07;controls.maxDistance=40;controls.maxPolarAngle=Math.PI*.96;controls.zoomToCursor=true;controls.touches.TWO=T.TOUCH.DOLLY_PAN;controls.addEventListener('change',()=>{dirty=true;});
  const pmrem=new T.PMREMGenerator(renderer),room=new RoomEnvironment(),env=pmrem.fromScene(room,.04);scene.environment=env.texture;room.dispose();pmrem.dispose();
  scene.add(new T.HemisphereLight(0xffffff,0xa7acb2,1.05));
  const key=new T.DirectionalLight(0xfffaf4,2.3);key.position.set(-2,4,3);scene.add(key);
  const rim=new T.DirectionalLight(0xe9f0ff,1.8);rim.position.set(2,2,-3);scene.add(rim);
  const ground=new T.Mesh(new T.CircleGeometry(30,96),new T.MeshStandardMaterial({color:0xd5d9dc,roughness:1}));ground.rotation.x=-Math.PI/2;ground.position.y=-.019;scene.add(ground);
  const platform=new T.Mesh(new T.CylinderGeometry(.68,.7,.028,100),new T.MeshStandardMaterial({color:0xeeeeec,metalness:.12,roughness:.67}));platform.position.y=-.016;scene.add(platform);
  const ring=new T.Mesh(new T.RingGeometry(.63,.632,128),new T.MeshBasicMaterial({color:0x8c969f,transparent:true,opacity:.4,side:T.DoubleSide}));ring.rotation.x=-Math.PI/2;ring.position.y=.001;scene.add(ring);
  const innerRing=new T.Mesh(new T.RingGeometry(.55,.551,128),new T.MeshBasicMaterial({color:0xa4aeb8,transparent:true,opacity:.16,side:T.DoubleSide}));innerRing.rotation.x=-Math.PI/2;innerRing.position.y=.001;scene.add(innerRing);
  const width=T.MathUtils.ceilPowerOfTwo(atlas.parts.length),data=new Float32Array(width*4),partTexture=new T.DataTexture(data,width,1,T.RGBAFormat,T.FloatType);partTexture.needsUpdate=true;
  const selectedData=new Uint8Array(width*4),selectionTexture=new T.DataTexture(selectedData,width,1);selectionTexture.needsUpdate=true;
  const materials:T.Material[]=[],geometries:T.BufferGeometry[]=[],pickers:(T.Mesh|undefined)[]=[],centers=atlas.parts.map(p=>new T.Vector3().fromArray(p.bounds[0]).add(new T.Vector3().fromArray(p.bounds[1])).multiplyScalar(.5));
  const offsets:T.Vector3[]=[],bounds=atlas.parts.map(p=>new T.Box3(new T.Vector3().fromArray(p.bounds[0]),new T.Vector3().fromArray(p.bounds[1])));
  let packingWidth=1,packingHeight=1;
  const markerPositions=new Float32Array(atlas.parts.length*3),markerGeometry=new T.BufferGeometry();markerGeometry.setAttribute('position',new T.BufferAttribute(markerPositions,3));
  const markerMaterial=new T.PointsMaterial({color:0x64748b,size:5,sizeAttenuation:false,transparent:true,opacity:.72,depthTest:false});
  markerMaterial.onBeforeCompile=shader=>{shader.fragmentShader=shader.fragmentShader.replace('#include <clipping_planes_fragment>','#include <clipping_planes_fragment>\nif (distance(gl_PointCoord, vec2(0.5)) > 0.5) discard;');};
  const markers=new T.Points(markerGeometry,markerMaterial);markers.frustumCulled=false;markers.renderOrder=10;markers.visible=false;scene.add(markers);
  const MAX_ACUPOINT_MARKERS=1024,acupointPositions=new Float32Array(MAX_ACUPOINT_MARKERS*3),acupointColors=new Float32Array(MAX_ACUPOINT_MARKERS*3);
  const acupointGeometry=new T.BufferGeometry();acupointGeometry.setAttribute('position',new T.BufferAttribute(acupointPositions,3));acupointGeometry.setAttribute('color',new T.BufferAttribute(acupointColors,3));acupointGeometry.setDrawRange(0,0);
  const markerCanvas=document.createElement('canvas');markerCanvas.width=markerCanvas.height=64;const markerCtx=markerCanvas.getContext('2d')!;markerCtx.beginPath();markerCtx.arc(32,32,25,0,Math.PI*2);markerCtx.fillStyle='#fff';markerCtx.fill();markerCtx.lineWidth=8;markerCtx.strokeStyle='#fff';markerCtx.stroke();
  const acupointTexture=new T.CanvasTexture(markerCanvas);acupointTexture.colorSpace=T.SRGBColorSpace;acupointTexture.needsUpdate=true;
  const acupointMaterial=new T.PointsMaterial({map:acupointTexture,vertexColors:true,size:.009,sizeAttenuation:true,transparent:true,alphaTest:.18,opacity:1,depthTest:true,depthWrite:false,toneMapped:false});
  const acupointMarkers=new T.Points(acupointGeometry,acupointMaterial);acupointMarkers.frustumCulled=false;acupointMarkers.renderOrder=20;acupointMarkers.visible=false;scene.add(acupointMarkers);
  const flaggedPositions=new Float32Array(MAX_ACUPOINT_MARKERS*3),flaggedGeometry=new T.BufferGeometry();flaggedGeometry.setAttribute('position',new T.BufferAttribute(flaggedPositions,3));flaggedGeometry.setDrawRange(0,0);
  const flagCanvas=document.createElement('canvas');flagCanvas.width=flagCanvas.height=64;const flagCtx=flagCanvas.getContext('2d')!;flagCtx.beginPath();flagCtx.arc(32,32,25,0,Math.PI*2);flagCtx.lineWidth=10;flagCtx.strokeStyle='#f97316';flagCtx.stroke();
  const flaggedTexture=new T.CanvasTexture(flagCanvas);flaggedTexture.colorSpace=T.SRGBColorSpace;flaggedTexture.needsUpdate=true;
  const flaggedMaterial=new T.PointsMaterial({map:flaggedTexture,color:0xffffff,size:.012,sizeAttenuation:true,transparent:true,alphaTest:.1,depthTest:true,depthWrite:false,toneMapped:false});
  const flaggedMarkers=new T.Points(flaggedGeometry,flaggedMaterial);flaggedMarkers.frustumCulled=false;flaggedMarkers.renderOrder=21;flaggedMarkers.visible=false;scene.add(flaggedMarkers);
  type MarkerRecord={id:string;side:'left'|'right'|'midline';status:'PLACED'|'FLAGGED';origin:'placed'|'mirrored';position:[number,number,number]};let markerRecords:MarkerRecord[]=[];
  const placementMarker=new T.Mesh(new T.SphereGeometry(.005,18,18),new T.MeshBasicMaterial({color:0x16a34a,depthTest:true,depthWrite:false,toneMapped:false}));placementMarker.visible=false;placementMarker.renderOrder=27;scene.add(placementMarker);
  const mirrorMarker=new T.Mesh(new T.SphereGeometry(.005,18,18),new T.MeshBasicMaterial({color:0x06b6d4,depthTest:true,depthWrite:false,toneMapped:false,transparent:true,opacity:.9}));mirrorMarker.visible=false;mirrorMarker.renderOrder=26;scene.add(mirrorMarker);
  const anchorMarkerMaterial=new T.MeshBasicMaterial({color:0x16a34a,depthTest:true,depthWrite:false,toneMapped:false});
  const anchorMarker=new T.Mesh(new T.SphereGeometry(.006,18,18),anchorMarkerMaterial);anchorMarker.visible=false;anchorMarker.renderOrder=25;scene.add(anchorMarker);
  const proposalMarkerMaterial=new T.MeshBasicMaterial({color:0xf59e0b,depthTest:true,depthWrite:false,toneMapped:false,transparent:true,opacity:.95});
  const proposalMarker=new T.Mesh(new T.SphereGeometry(.007,18,18),proposalMarkerMaterial);proposalMarker.visible=false;proposalMarker.renderOrder=24;scene.add(proposalMarker);
  const hover=document.createElement('div');hover.className='part-hover';hover.setAttribute('role','tooltip');hover.hidden=true;el.appendChild(hover);
  type Target={index:number;x:number;y:number;left:number;right:number;top:number;bottom:number};let targets:Target[]=[];
  const projected=new T.Vector3();
  const findTarget=(x:number,y:number,radius:number)=>{
   let best=-1,score=Infinity;
   for(const t of targets){const dx=Math.max(t.left-x,0,x-t.right),dy=Math.max(t.top-y,0,y-t.bottom),distance=Math.hypot(dx,dy);if(distance>radius)continue;const candidate=distance+Math.hypot(t.x-x,t.y-y)*.025;if(candidate<score){score=candidate;best=t.index;}}
   return best;
  };
  const materialFor=(system:string)=>{
   const m=new T.MeshStandardMaterial({color:SYSTEMS.find(s=>s.id===system)?.color??'#aebbb8',metalness:.08,roughness:.53,side:T.DoubleSide,transparent:system==='integumentary',opacity:system==='integumentary'?.1:1,depthWrite:system!=='integumentary'});
   m.onBeforeCompile=shader=>{
    shader.uniforms.partState={value:partTexture};shader.uniforms.selectionState={value:selectionTexture};shader.uniforms.stateWidth={value:width};
    shader.vertexShader='attribute float partIndex; uniform sampler2D partState; uniform sampler2D selectionState; uniform float stateWidth; varying float partVisible; varying float partSelected;\n'+shader.vertexShader;
    shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvec2 stateUv = vec2((partIndex + 0.5) / stateWidth, 0.5); vec4 state = texture2D(partState, stateUv); transformed += state.xyz; partVisible = state.w; partSelected = texture2D(selectionState, stateUv).r;');
    shader.fragmentShader='varying float partVisible; varying float partSelected;\n'+shader.fragmentShader;
    shader.fragmentShader=shader.fragmentShader.replace('#include <clipping_planes_fragment>','#include <clipping_planes_fragment>\nif (partVisible < 0.5) discard;');
    shader.fragmentShader=shader.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\ndiffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.42, 0.85, 0.78), partSelected * 0.75);');
   };materials.push(m);return m;
  };
  const mats=new Map(SYSTEMS.map(s=>[s.id,materialFor(s.id)]));
  let loaded=0;
  const loadChunk=async(ci:number)=>{
   const chunk=atlas.chunks[ci],compressed=!!chunk.gzip&&typeof DecompressionStream!=='undefined';const response=await fetch(compressed?chunk.gzip!:chunk.url,{signal:abort.signal});const buffer=await decodeModelResponse(response,chunk.bytes,compressed);if(disposed)return;
   const groups=new Map<string,T.BufferGeometry[]>();
   atlas.parts.forEach((p,i)=>{
    if(p.chunk!==ci)return;
    const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(new Float32Array(buffer,p.positions,p.vertexCount*3),3));
    // GPU normalized signed-short normals keep the complete atlas compact in memory.
    g.setAttribute('normal',new T.BufferAttribute(new Int16Array(buffer,p.normals,p.vertexCount*3),3,true));g.setIndex(new T.BufferAttribute(new Uint32Array(buffer,p.indices,p.indexCount),1));
    g.boundingBox=bounds[i].clone();g.computeBoundingSphere();const pick=new T.Mesh(g);pick.matrixAutoUpdate=false;pickers[i]=pick;geometries.push(g);
    g.setAttribute('partIndex',new T.BufferAttribute(new Float32Array(p.vertexCount).fill(i),1));
    const list=groups.get(p.system)??[];list.push(g);groups.set(p.system,list);
   });
   groups.forEach((gs,system)=>{const geometry=mergeGeometries(gs,false);if(!geometry)throw new Error('Could not assemble anatomy geometry.');geometries.push(geometry);const mesh=new T.Mesh(geometry,mats.get(system as never));mesh.frustumCulled=false;scene.add(mesh);});
   lastState=null;loaded++;onProgress(Math.round(loaded/atlas.chunks.length*100));dirty=true;
  };
  (async()=>{try{let cursor=0;await Promise.all(Array.from({length:3},async()=>{while(cursor<atlas.chunks.length){const i=cursor++;await loadChunk(i);}}));if(!disposed){ready=true;dirty=true;}}catch(e){if(!disposed)onError(e instanceof Error?e.message:'Could not load the anatomy.');}})();
  const fit=(view:string,extent=0)=>{
   const aspect=camera.aspect,mobile=el.clientWidth<768,normalDistance=mobile?Math.max(4.5,1.8*el.clientHeight/Math.max(160,el.clientHeight-350)/(2*Math.tan(T.MathUtils.degToRad(camera.fov/2)))):4;
   const reservedHeight=mobile?350:270;const availableAspect=Math.max(.35,(el.clientWidth-(mobile?40:340))/Math.max(160,el.clientHeight-reservedHeight));const atlasDistance=Math.max(packingHeight,packingWidth/availableAspect)/(2*Math.tan(T.MathUtils.degToRad(camera.fov/2)))*(el.clientHeight/Math.max(160,el.clientHeight-reservedHeight))*1.08;
   const distance=T.MathUtils.lerp(normalDistance,Math.max(.2,atlasDistance),extent);if(extent>.8)view='front';
   const direction=view==='front'?new T.Vector3(0,.02,1):view==='back'?new T.Vector3(0,.02,-1):view==='side'?new T.Vector3(1,.02,0):new T.Vector3(.35,.06,1).normalize();
   controls.target.set(extent>.1&&el.clientWidth>767?-packingWidth*.12:0,extent>.1||mobile?.85:.68,0);camera.position.copy(controls.target).addScaledVector(direction,distance);controls.update();dirty=true;
  };
  const resize=()=>{layoutKey='';lastState=null;renderer.setPixelRatio(Math.min(devicePixelRatio,el.clientWidth<768||el.clientHeight<600?1.5:2));camera.aspect=el.clientWidth/el.clientHeight;camera.updateProjectionMatrix();renderer.setSize(el.clientWidth,el.clientHeight);if(!anchorTargetRef.current)fit(latest.current.view,amount);};const observer=new ResizeObserver(resize);observer.observe(el);
  const raycaster=new T.Raycaster(),pointer=new T.Vector2(),tap=new PointerTap(),worldBox=new T.Box3(),hitPoint=new T.Vector3();raycaster.params.Points={threshold:.006};
  const baryA=new T.Vector3(),baryB=new T.Vector3(),baryC=new T.Vector3(),baryP=new T.Vector3(),baryOut=new T.Vector3();
  const candidateFromHit=(landmarkId:string,partIndex:number,hit:T.Intersection<T.Object3D>,method:LandmarkAnchorCandidate['method'],side?:LandmarkAnchorSide,detectorId?:string):LandmarkAnchorCandidate|null=>{
   if(hit.faceIndex===undefined||hit.faceIndex<0)return null;
   const mesh=pickers[partIndex];if(!mesh)return null;
   const geometry=mesh.geometry,index=geometry.index,position=geometry.getAttribute('position');if(!index||!position)return null;
   const tri=hit.faceIndex,i0=index.getX(tri*3),i1=index.getX(tri*3+1),i2=index.getX(tri*3+2);
   baryA.fromBufferAttribute(position,i0);baryB.fromBufferAttribute(position,i1);baryC.fromBufferAttribute(position,i2);
   baryP.copy(hit.point);mesh.worldToLocal(baryP);T.Triangle.getBarycoord(baryP,baryA,baryB,baryC,baryOut);
   if(!Number.isFinite(baryOut.x)||!Number.isFinite(baryOut.y)||!Number.isFinite(baryOut.z))return null;
   return {
    landmarkId,
    position:[hit.point.x,hit.point.y,hit.point.z],
    surfaceProjection:{meshId:atlas.parts[partIndex].id,triangleIndex:tri,barycentric:[baryOut.x,baryOut.y,baryOut.z],distance:0},
    method,side,detectorId,detectorConfidence:detectorId?'moderate':undefined
   };
  };
  const nearestSkinHit=(rc:T.Raycaster):{partIndex:number;hit:T.Intersection<T.Object3D>}|null=>{
   let bestPartIndex=-1,bestHit:T.Intersection<T.Object3D>|null=null;
   for(let i=0;i<atlas.parts.length;i++){
    const p=atlas.parts[i];if(p.system!=='integumentary'||p.name!=='Skin')continue;
    const mesh=pickers[i];if(!mesh)continue;
    const hit=rc.intersectObject(mesh,false)[0];
    if(hit&&(!bestHit||hit.distance<bestHit.distance)){bestPartIndex=i;bestHit=hit;}
   }
   return bestHit&&bestPartIndex>=0?{partIndex:bestPartIndex,hit:bestHit}:null;
  };
  const skinPartIndex=atlas.parts.findIndex(p=>p.id==='FJ2810'),skinPart=skinPartIndex>=0?atlas.parts[skinPartIndex]:null,midlineX=skinPart?(skinPart.bounds[0][0]+skinPart.bounds[1][0])/2:0;
  const closestSkinSurface=(worldPoint:T.Vector3)=>{
   const mesh=skinPartIndex>=0?pickers[skinPartIndex]:undefined;if(!mesh)return null;const geometry=mesh.geometry,index=geometry.index,position=geometry.getAttribute('position');if(!index||!position)return null;
   const local=mesh.worldToLocal(worldPoint.clone()),a=new T.Vector3(),b=new T.Vector3(),c=new T.Vector3(),q=new T.Vector3(),best=new T.Vector3(),triObj=new T.Triangle(),bary=new T.Vector3(),bestBary=new T.Vector3();let bestTri=-1,bestD=Infinity;
   for(let tri=0;tri<index.count/3;tri++){a.fromBufferAttribute(position,index.getX(tri*3));b.fromBufferAttribute(position,index.getX(tri*3+1));c.fromBufferAttribute(position,index.getX(tri*3+2));triObj.set(a,b,c).closestPointToPoint(local,q);const d=q.distanceToSquared(local);if(d<bestD){bestD=d;bestTri=tri;best.copy(q);T.Triangle.getBarycoord(q,a,b,c,bary);bestBary.copy(bary);if(d<1e-14)break;}}
   if(bestTri<0)return null;const world=mesh.localToWorld(best.clone());return{position:[world.x,world.y,world.z] as [number,number,number],surface:{mesh_id:'FJ2810',triangle_index:bestTri,barycentric:[bestBary.x,bestBary.y,bestBary.z] as [number,number,number]},distance:Math.sqrt(bestD)};
  };
  const placementCandidateFromHit=(target:{id:string;laterality:'midline'|'bilateral'},partIndex:number,hit:T.Intersection<T.Object3D>):AcupointPlacementCandidate|null=>{
   const base=candidateFromHit(target.id,partIndex,hit,'manual-anchor');if(!base)return null;const side=target.laterality==='midline'?'midline':hit.point.x>midlineX?'left':'right';
   const candidate:AcupointPlacementCandidate={id:target.id,side,position:base.position,surface:{mesh_id:base.surfaceProjection.meshId,triangle_index:base.surfaceProjection.triangleIndex,barycentric:base.surfaceProjection.barycentric}};
   if(side!=='midline'){const snap=closestSkinSurface(new T.Vector3(2*midlineX-hit.point.x,hit.point.y,hit.point.z));if(snap)candidate.mirror_preview={side:side==='left'?'right':'left',position:snap.position,surface:snap.surface,snap_distance_m:snap.distance};}
   return candidate;
  };
  const partSearchText=(i:number)=>`${atlas.parts[i].name} ${atlas.concepts.find(c=>c.id===atlas.parts[i].conceptId)?.name??''}`.toLowerCase();
  const findPhalanxPart=(side:LandmarkAnchorSide,segment:'proximal'|'middle'|'distal')=>{
   const sideRe=side==='left'?/left|sinister/:/right|dexter/;
   const fingerRe=/middle finger|third finger|3rd finger|digit iii|digit 3|third digit/;
   const segRe=segment==='proximal'?/proximal phalanx/:segment==='middle'?/middle phalanx|intermediate phalanx/:/distal phalanx/;
   let fallback=-1;
   for(let i=0;i<atlas.parts.length;i++){
    const text=partSearchText(i);if(!segRe.test(text)||!sideRe.test(text))continue;
    if(fingerRe.test(text))return i;
    if(fallback<0&&/finger|digit/.test(text))fallback=i;
   }
   return fallback;
  };
  const findPartByName=(name:string)=>atlas.parts.findIndex(p=>p.name===name);
  const computeHairBoundaryPoints=()=>{
   const hairIndex=findPartByName('Hair of head'),mesh=hairIndex>=0?pickers[hairIndex]:undefined;if(!mesh)return[] as T.Vector3[];
   const geometry=mesh.geometry,index=geometry.index,position=geometry.getAttribute('position');if(!index||!position)return[] as T.Vector3[];
   const edges=new Map<string,{a:number;b:number;count:number}>();
   const addEdge=(a:number,b:number)=>{const lo=Math.min(a,b),hi=Math.max(a,b),key=`${lo}:${hi}`,entry=edges.get(key);if(entry)entry.count++;else edges.set(key,{a:lo,b:hi,count:1});};
   for(let i=0;i<index.count;i+=3){const a=index.getX(i),b=index.getX(i+1),c=index.getX(i+2);addEdge(a,b);addEdge(b,c);addEdge(c,a);}
   const boundary=new Set<number>();edges.forEach(edge=>{if(edge.count===1){boundary.add(edge.a);boundary.add(edge.b);}});
   const source=boundary.size?[...boundary]:Array.from({length:position.count},(_,i)=>i);
   return source.map(i=>new T.Vector3().fromBufferAttribute(position,i).applyMatrix4(mesh.matrixWorld));
  };
  const computeHairlineProposal=(landmarkId:string):LandmarkAnchorCandidate|null=>{
   const hairlineIds=['midpoint-anterior-hairline','midpoint-posterior-hairline','left-anterior-hairline-corner','right-anterior-hairline-corner'];
   if(!hairlineIds.includes(landmarkId))return null;
   const points=computeHairBoundaryPoints();if(points.length<4)return null;
   const midline=points.filter(p=>Math.abs(p.x)<.016),midCandidates=midline.length?midline:points.slice().sort((a,b)=>Math.abs(a.x)-Math.abs(b.x)).slice(0,Math.max(8,Math.floor(points.length*.08)));
   const anterior=midCandidates.reduce((best,p)=>p.z>best.z?p:best,midCandidates[0]);
   const posterior=midCandidates.reduce((best,p)=>p.z<best.z?p:best,midCandidates[0]);
   let seed:T.Vector3;
   if(landmarkId==='midpoint-anterior-hairline')seed=anterior;
   else if(landmarkId==='midpoint-posterior-hairline')seed=posterior;
   else{
    const frontBand=points.filter(p=>p.z>=anterior.z-.055&&Math.abs(p.y-anterior.y)<=.085);
    const candidates=frontBand.length?frontBand:points.filter(p=>p.z>(anterior.z+posterior.z)/2),left=landmarkId.startsWith('left-');
    seed=candidates.reduce((best,p)=>left?(p.x>best.x?p:best):(p.x<best.x?p:best),candidates[0]);
   }
   const hairIndex=findPartByName('Hair of head'),hairCenter=hairIndex>=0?bounds[hairIndex].getCenter(new T.Vector3()):new T.Vector3(0,1.63,0);
   const outward=seed.clone().sub(hairCenter);if(outward.lengthSq()<1e-8)outward.set(0,0,landmarkId.includes('posterior')?-1:1);outward.normalize();
   const detectorRay=new T.Raycaster(seed.clone().addScaledVector(outward,.035),outward.clone().multiplyScalar(-1),0,.22);
   let hit=nearestSkinHit(detectorRay);
   if(!hit){
    const inward=new T.Vector3(-seed.x,0,-seed.z);
    if(inward.lengthSq()>1e-8){inward.normalize();detectorRay.ray.origin.copy(seed.clone().addScaledVector(inward,-.03));detectorRay.ray.direction.copy(inward);hit=nearestSkinHit(detectorRay);}
   }
   if(!hit)return null;
   return candidateFromHit(landmarkId,hit.partIndex,hit.hit,'specialized-detector',landmarkId.startsWith('left-')?'left':landmarkId.startsWith('right-')?'right':undefined,`bodyparts3d-hair-boundary:${landmarkId}`);
  };
  const computeFingerProposal=(landmarkId:string,side:LandmarkAnchorSide):LandmarkAnchorCandidate|null=>{
   const pip=landmarkId==='radial-crease-proximal-interphalangeal-middle-finger';
   const dip=landmarkId==='radial-crease-distal-interphalangeal-middle-finger';
   if(!pip&&!dip)return null;
   const a=findPhalanxPart(side,pip?'proximal':'middle'),b=findPhalanxPart(side,pip?'middle':'distal');if(a<0||b<0)return null;
   const ca=centers[a].clone(),cb=centers[b].clone(),axis=cb.clone().sub(ca);if(axis.lengthSq()<1e-8)return null;axis.normalize();
   const halfA=bounds[a].getSize(new T.Vector3()).multiplyScalar(.5),halfB=bounds[b].getSize(new T.Vector3()).multiplyScalar(.5);
   const support=(half:T.Vector3,dir:T.Vector3)=>Math.abs(dir.x)*half.x+Math.abs(dir.y)*half.y+Math.abs(dir.z)*half.z;
   const jointA=ca.clone().addScaledVector(axis,support(halfA,axis)),jointB=cb.clone().addScaledVector(axis,-support(halfB,axis)),joint=jointA.add(jointB).multiplyScalar(.5);
   let leftMean=0,rightMean=0,leftN=0,rightN=0;
   atlas.parts.forEach((p,i)=>{const txt=partSearchText(i);if(/left/.test(txt)){leftMean+=centers[i].x;leftN++;}if(/right/.test(txt)){rightMean+=centers[i].x;rightN++;}});
   const leftX=leftN?leftMean/leftN:-1,rightX=rightN?rightMean/rightN:1,leftPositive=leftX>rightX;
   const outward=(side==='left'?(leftPositive?1:-1):(leftPositive?-1:1)),radial=new T.Vector3(outward,0,0);
   const radialHalf=Math.max(halfA.x,halfB.x),originOffset=Math.max(.014,radialHalf+.01),maxTravel=Math.max(.035,radialHalf*2+.018);
   const outside=joint.clone().addScaledVector(radial,originOffset),detectorRay=new T.Raycaster(outside,radial.clone().multiplyScalar(-1),0,maxTravel);
   const hit=nearestSkinHit(detectorRay);if(!hit)return null;
   const candidate=candidateFromHit(landmarkId,hit.partIndex,hit.hit,'specialized-detector',side,pip?'middle-finger-pip-radial-joint-surface-local':'middle-finger-dip-radial-joint-surface-local');
   if(!candidate)return null;
   const hitPoint=new T.Vector3().fromArray(candidate.position),jointDistance=hitPoint.distanceTo(joint),axialError=Math.abs(hitPoint.clone().sub(joint).dot(axis));
   if(jointDistance>maxTravel+.006||axialError>.018)return null;
   return {...candidate,detectorConfidence:'high'};
  };
  const computeLandmarkProposal=(landmarkId:string,side:LandmarkAnchorSide)=>computeFingerProposal(landmarkId,side)??computeHairlineProposal(landmarkId);
  const focusLandmark=(landmarkId:string,side:LandmarkAnchorSide,proposal:LandmarkAnchorCandidate|null)=>{
   let target:T.Vector3,distance=.58,direction=new T.Vector3(0,.02,1);
   if(proposal)target=new T.Vector3().fromArray(proposal.position);
   else if(landmarkId==='umbilicus-center')target=new T.Vector3(0,.97,.105);
   else if(landmarkId==='left-nipple-center')target=new T.Vector3(.105,1.25,.105);
   else if(landmarkId==='right-nipple-center')target=new T.Vector3(-.105,1.25,.105);
   else if(landmarkId.includes('hairline')){const hairIndex=findPartByName('Hair of head');target=hairIndex>=0?bounds[hairIndex].getCenter(new T.Vector3()):new T.Vector3(0,1.63,0);distance=.42;}
   else if(landmarkId.includes('middle-finger')){const middle=findPhalanxPart(side,'middle');target=middle>=0?centers[middle].clone():new T.Vector3(side==='left'?.27:-.27,.75,.07);distance=.19;}
   else target=controls.target.clone();
   if(landmarkId.includes('middle-finger')){direction.set(side==='left'?.55:-.55,.12,1).normalize();distance=.19;}
   else if(landmarkId==='midpoint-posterior-hairline')direction.set(0,.05,-1).normalize();
   else if(landmarkId==='left-anterior-hairline-corner')direction.set(.45,.04,1).normalize();
   else if(landmarkId==='right-anterior-hairline-corner')direction.set(-.45,.04,1).normalize();
   camera.clearViewOffset();controls.target.copy(target);camera.position.copy(target).addScaledVector(direction,distance);controls.update();dirty=true;
  };
  const down=(e:PointerEvent)=>{hover.hidden=true;tap.down(e.pointerId,e.clientX,e.clientY,e.pointerType==='touch'?12:5);};
  const move=(e:PointerEvent)=>{tap.move(e.pointerId,e.clientX,e.clientY);if(anchorTargetRef.current||placementModeRef.current){hover.hidden=true;renderer.domElement.style.cursor='crosshair';return;}if(e.buttons||e.pointerType==='touch'){hover.hidden=true;renderer.domElement.style.cursor='grab';return;}const rect=el.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
   if(amount<.5&&acupointMarkers.visible){pointer.set(x/rect.width*2-1,-y/rect.height*2+1);raycaster.setFromCamera(pointer,camera);const pointHit=raycaster.intersectObject(acupointMarkers,false)[0],skinHit=nearestSkinHit(raycaster);if(pointHit&&pointHit.index!==undefined&&(!skinHit||pointHit.distance<=skinHit.hit.distance+.018)){const point=markerRecords[pointHit.index];if(point){const side=point.side==='left'?'환자 왼쪽':point.side==='right'?'환자 오른쪽':'정중선',origin=point.origin==='placed'?'직접 배치':'좌우 미러';hover.hidden=false;hover.textContent=`${point.id} · ${side} · ${origin} · ${point.status}`;hover.style.left=`${Math.max(8,Math.min(x+14,el.clientWidth-300))}px`;hover.style.top=`${Math.max(8,Math.min(y+18,el.clientHeight-55))}px`;renderer.domElement.style.cursor='pointer';return;}}}
   if(amount<.5){hover.hidden=true;renderer.domElement.style.cursor='grab';return;}const index=findTarget(x,y,12);hover.hidden=index<0;renderer.domElement.style.cursor=index<0?'grab':'pointer';if(index>=0){hover.textContent=atlas.parts[index].name;hover.style.left=`${Math.max(8,Math.min(x+14,el.clientWidth-260))}px`;hover.style.top=`${Math.max(8,Math.min(y+18,el.clientHeight-55))}px`;}};
  const cancel=(e:PointerEvent)=>tap.cancel(e.pointerId);
  const up=(e:PointerEvent)=>{
   const validTap=tap.up(e.pointerId,e.clientX,e.clientY);if(!validTap||!ready)return;const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);
   const activeAnchor=anchorTargetRef.current;
   if(activeAnchor){
    const skinHit=nearestSkinHit(raycaster);
    if(skinHit){
     const candidate=candidateFromHit(activeAnchor,skinHit.partIndex,skinHit.hit,'manual-anchor');
     if(candidate){hover.hidden=true;anchorPickRef.current(candidate);return;}
    }
   }
   const activePlacement=placementTargetRef.current;if(placementModeRef.current&&activePlacement){const skinHit=nearestSkinHit(raycaster);if(skinHit){const candidate=placementCandidateFromHit(activePlacement,skinHit.partIndex,skinHit.hit);if(candidate){hover.hidden=true;placementPickRef.current(candidate);return;}}}
   let nearest=Infinity,found=-1;const hasSolid=atlas.parts.some((p,i)=>p.system!=='integumentary'&&data[i*4+3]>.5);
   pickers.forEach((mesh,i)=>{if(!mesh||data[i*4+3]<.5||(hasSolid&&atlas.parts[i].system==='integumentary'))return;worldBox.copy(bounds[i]).translate(mesh.position);if(!raycaster.ray.intersectBox(worldBox,hitPoint))return;const hits=raycaster.intersectObject(mesh,false);if(hits[0]&&hits[0].distance<nearest){nearest=hits[0].distance;found=i;}});
   if(acupointMarkers.visible){
    const acupointHit=raycaster.intersectObject(acupointMarkers,false)[0];
    // Match visual occlusion for picking: a point hidden behind anatomy must not
    // be selectable through the body. A small tolerance accounts for a marker
    // sitting immediately outside the visible surface.
    if(acupointHit&&acupointHit.index!==undefined&&acupointHit.distance<=nearest+.018){
     const point=markerRecords[acupointHit.index];
     if(point){hover.hidden=true;selectAcupoint.current(point.id);return;}
    }
   }
   if(found<0&&amount>.45)found=findTarget(e.clientX-rect.left,e.clientY-rect.top,e.pointerType==='touch'?24:16);if(found>=0){hover.hidden=true;select.current(atlas.parts[found].id);}
  };
  renderer.domElement.addEventListener('pointerdown',down);renderer.domElement.addEventListener('pointermove',move);renderer.domElement.addEventListener('pointerup',up);renderer.domElement.addEventListener('pointercancel',cancel);
  const clock=new T.Clock();let lastExtent=-1,lastShowAcupoints=showAcupointsRef.current,lastDetectorKey='',lastMarkerVersion=-1,lastPlacementMode=placementModeRef.current;
  const animate=()=>{
   if(disposed)return;frame=requestAnimationFrame(animate);const dt=Math.min(clock.getDelta(),.05),s=latest.current;
   const placementChanged=lastPlacementMode!==placementModeRef.current;if(placementChanged){lastPlacementMode=placementModeRef.current;layoutKey='';}\n   const changed=lastState?.visible!==s.visible||lastState?.selected!==s.selected||lastState?.isolate!==s.isolate;
   if(markerVersionRef.current!==lastMarkerVersion){
    lastMarkerVersion=markerVersionRef.current;const meridians=new Set(visibleMeridiansRef.current);
    const local=placementPointsRef.current.filter(p=>p.status!=='SKIPPED'&&p.position).map(p=>({id:p.id,side:p.side,status:p.status as 'PLACED'|'FLAGGED',origin:'placed' as const,position:p.position!}));
    markerRecords=(placementModeRef.current?local:renderPointsRef.current.filter(p=>meridians.has(p.id.replace(/\d+$/,''))).map(p=>({id:p.id,side:p.side,status:p.status,origin:p.origin,position:p.position}))).slice(0,MAX_ACUPOINT_MARKERS);
    let flags=0;const placedColor=new T.Color('#dc2626'),mirroredColor=new T.Color('#fca5a5');
    markerRecords.forEach((p,i)=>{acupointPositions.set(p.position,i*3);const color=p.origin==='mirrored'?mirroredColor:placedColor;acupointColors.set([color.r,color.g,color.b],i*3);if(p.status==='FLAGGED'){flaggedPositions.set(p.position,flags*3);flags++;}});
    acupointGeometry.setDrawRange(0,markerRecords.length);flaggedGeometry.setDrawRange(0,flags);(acupointGeometry.getAttribute('position') as T.BufferAttribute).needsUpdate=true;(acupointGeometry.getAttribute('color') as T.BufferAttribute).needsUpdate=true;(flaggedGeometry.getAttribute('position') as T.BufferAttribute).needsUpdate=true;dirty=true;
   }
   const moving=Math.abs(amount-s.explode)>.0001;
   if(moving){amount=T.MathUtils.damp(amount,s.explode,8,dt);dirty=true;}
   if(changed||moving||lastExtent<0||placementChanged){
    const visible=new Set(s.visible),selection=new Set(s.selected);
    const visibleParts=atlas.parts.filter(p=>s.isolate?selection.has(p.id):visible.has(p.system)||selection.has(p.id)||(placementModeRef.current&&p.id==='FJ2810'));
    const nextLayoutKey=visibleParts.map(p=>p.id).join(',')+':'+camera.aspect.toFixed(3);
    if(nextLayoutKey!==layoutKey){const layout=createExplosionLayout(visibleParts,camera.aspect);packingWidth=layout.width;packingHeight=layout.height;atlas.parts.forEach((p,i)=>{const cell=layout.cells.get(p.id);offsets[i]=cell?new T.Vector3(cell.x,cell.y+.85,0):centers[i].clone();});layoutKey=nextLayoutKey;if(amount>.05&&!s.isolate)fit(s.view,Math.max(0,(amount-.3)/.7));}

    atlas.parts.forEach((p,i)=>{
     const c=centers[i],destination=offsets[i];let dx=0,dy=0,dz=0;
     if(amount<=.45){const t=amount/.45;const group=SYSTEMS.findIndex(sys=>sys.id===p.system);const angle=group/SYSTEMS.length*Math.PI*2;dx=Math.sin(angle)*t*.48;dy=(c.y-.85)*t*.28;dz=Math.cos(angle)*t*.48;}
     else {const t=(amount-.45)/.55,group=SYSTEMS.findIndex(sys=>sys.id===p.system),angle=group/SYSTEMS.length*Math.PI*2;dx=T.MathUtils.lerp(Math.sin(angle)*.48,destination.x-c.x,t);dy=T.MathUtils.lerp((c.y-.85)*.28,destination.y-c.y,t);dz=T.MathUtils.lerp(Math.cos(angle)*.48,-c.z,t);}
     const selected=selection.has(p.id),placementSkin=placementModeRef.current&&p.id==='FJ2810';data.set([dx,dy,dz,(s.isolate?selected:visible.has(p.system)||selected||placementSkin)?1:0],i*4);selectedData[i*4]=selected?255:0;
     markerPositions.set(data[i*4+3]>.5?[c.x+dx,c.y+dy,c.z+dz]:[10000,10000,10000],i*3);const mesh=pickers[i];if(mesh){mesh.position.set(dx,dy,dz);mesh.updateMatrix();mesh.updateMatrixWorld(true);}
    });partTexture.needsUpdate=true;selectionTexture.needsUpdate=true;markerGeometry.attributes.position.needsUpdate=true;lastState=s;lastExtent=amount;dirty=true;
   }
   if(s.view!==lastView||s.reset!==lastReset){fit(s.view,amount);lastView=s.view;lastReset=s.reset;}
   if(moving&&!s.isolate)fit(amount>.5?'front':s.view,Math.max(0,(amount-.3)/.7));
   const isolateKey=s.isolate?s.selected.join(',')+':'+s.reset+':'+s.inspectorOpen+':'+camera.aspect:'';
   if(isolateKey!==lastIsolate||(s.isolate&&moving)){
    if(s.isolate){const box=new T.Box3();atlas.parts.forEach((p,i)=>{if(s.selected.includes(p.id))box.union(bounds[i].clone().translate(new T.Vector3(data[i*4],data[i*4+1],data[i*4+2])));});
     if(!box.isEmpty()){const center=box.getCenter(new T.Vector3()),size=box.getSize(new T.Vector3());const w=el.clientWidth,h=el.clientHeight,mobile=w<768,landscape=w>h&&h<=600;let left=20,right=w-20,top=mobile?175:110,bottom=h-170;if(s.inspectorOpen){if(landscape){right=w-335;top=100;bottom=h-125;}else if(mobile){const sheet=document.querySelector('.detail-sheet')?.getBoundingClientRect(),header=document.querySelector('.identity')?.getBoundingClientRect();top=(header?.bottom??94)+16;bottom=(sheet?.top??h*.58-139)-16;}else{right=w-370;left=w>1100?285:25;}}const availableWidth=Math.max(150,right-left),availableHeight=Math.max(40,bottom-top);camera.setViewOffset(w,h,w/2-(left+right)/2,h/2-(top+bottom)/2,w,h);const distance=Math.max(.07,Math.max(size.y*h/availableHeight,size.x*w/availableWidth/camera.aspect,size.z)/(2*Math.tan(T.MathUtils.degToRad(camera.fov/2)))*1.35);controls.maxDistance=Math.max(40,distance*2);controls.target.copy(center);camera.position.copy(center).add(new T.Vector3(.2,.1,1).normalize().multiplyScalar(distance));controls.update();dirty=true;}
    }else if(lastIsolate){camera.clearViewOffset();fit(s.view,amount);}
    lastIsolate=isolateKey;
   }
   const detectorKey=ready&&anchorTargetRef.current?`${anchorTargetRef.current}:${detectorSideRef.current}`:'';
   if(detectorKey!==lastDetectorKey){
    lastDetectorKey=detectorKey;
    const proposal=detectorKey?computeLandmarkProposal(anchorTargetRef.current!,detectorSideRef.current):null;
    detectorProposalRef.current(proposal);
    if(detectorKey)focusLandmark(anchorTargetRef.current!,detectorSideRef.current,proposal);
    dirty=true;
   }
   const draft=anchorDraftRef.current,proposalState=detectorProposalStateRef.current;
   const integumentaryMaterial=mats.get('integumentary') as T.MeshStandardMaterial|undefined;
   if(integumentaryMaterial){const opacity=(anchorTargetRef.current?.length||placementModeRef.current)?.55:.1;if(integumentaryMaterial.opacity!==opacity){integumentaryMaterial.opacity=opacity;integumentaryMaterial.needsUpdate=true;dirty=true;}}
   const placementState=placementDraftRef.current;placementMarker.visible=!!placementState&&placementModeRef.current;mirrorMarker.visible=!!placementState?.mirror_preview&&placementModeRef.current;if(placementState)placementMarker.position.fromArray(placementState.position);if(placementState?.mirror_preview)mirrorMarker.position.fromArray(placementState.mirror_preview.position);
   anchorMarker.visible=!!draft&&!!anchorTargetRef.current;proposalMarker.visible=!!proposalState&&!!anchorTargetRef.current;
   if(draft)anchorMarker.position.fromArray(draft.position);
   if(proposalState)proposalMarker.position.fromArray(proposalState.position);
   const fingerQc=!!anchorTargetRef.current?.includes('middle-finger');anchorMarker.scale.setScalar(fingerQc?.55:1);proposalMarker.scale.setScalar(fingerQc?.5:1);
   controls.enableRotate=amount<.8;controls.mouseButtons.LEFT=amount<.8?T.MOUSE.ROTATE:T.MOUSE.PAN;controls.touches.ONE=amount<.8?T.TOUCH.ROTATE:T.TOUCH.PAN;ground.visible=platform.visible=ring.visible=innerRing.visible=amount<.5&&!s.isolate;markers.visible=amount>.75;const nextShowAcupoints=(placementModeRef.current||showAcupointsRef.current)&&markerRecords.length>0&&amount<.45&&!s.isolate&&!anchorTargetRef.current;if(nextShowAcupoints!==lastShowAcupoints){lastShowAcupoints=nextShowAcupoints;dirty=true;}acupointMarkers.visible=nextShowAcupoints;flaggedMarkers.visible=nextShowAcupoints&&flaggedGeometry.drawRange.count>0;controls.autoRotate=s.rotate&&!s.isolate&&amount<.4&&!anchorTargetRef.current&&!placementModeRef.current;controls.autoRotateSpeed=.65;controls.update();if(controls.autoRotate)dirty=true;
   if(dirty){renderer.render(scene,camera);targets=[];if(amount>.45){const hasSolid=atlas.parts.some((p,i)=>p.system!=='integumentary'&&data[i*4+3]>.5);atlas.parts.forEach((p,i)=>{if(data[i*4+3]<.5||(hasSolid&&p.system==='integumentary'))return;let left=Infinity,right=-Infinity,top=Infinity,bottom=-Infinity;for(let corner=0;corner<8;corner++){projected.set(p.bounds[(corner&1)?1:0][0]+data[i*4],p.bounds[(corner&2)?1:0][1]+data[i*4+1],p.bounds[(corner&4)?1:0][2]+data[i*4+2]).project(camera);const x=(projected.x+1)*el.clientWidth/2,y=(1-projected.y)*el.clientHeight/2;left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}projected.copy(centers[i]).add(new T.Vector3(data[i*4],data[i*4+1],data[i*4+2])).project(camera);if(projected.z< -1||projected.z>1)return;targets.push({index:i,x:(projected.x+1)*el.clientWidth/2,y:(1-projected.y)*el.clientHeight/2,left,right,top,bottom});});}dirty=false;}

  };animate();
  const contextLost=(e:Event)=>{e.preventDefault();onError('The 3D session was paused by your device. Reload to continue.');};renderer.domElement.addEventListener('webglcontextlost',contextLost);
  return()=>{disposed=true;abort.abort();cancelAnimationFrame(frame);observer.disconnect();controls.dispose();acupointTexture.dispose();flaggedTexture.dispose();acupointGeometry.dispose();flaggedGeometry.dispose();acupointMaterial.dispose();flaggedMaterial.dispose();geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());scene.traverse(o=>{if(o instanceof T.Mesh&&!geometries.includes(o.geometry)){o.geometry.dispose();const ms=Array.isArray(o.material)?o.material:[o.material];ms.forEach(m=>m.dispose());}});env.dispose();partTexture.dispose();selectionTexture.dispose();markerGeometry.dispose();markerMaterial.dispose();hover.remove();renderer.dispose();renderer.domElement.remove();};
 },[atlas]);
 return <div className="scene" ref={host}/>;
}
