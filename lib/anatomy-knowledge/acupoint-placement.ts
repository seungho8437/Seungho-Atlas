import type {MeridianId} from './types';

export type AcupointPlacementStatus='PLACED'|'SKIPPED'|'FLAGGED';
export type AcupointSide='left'|'right'|'midline';
export type AcupointOrigin='placed'|'mirrored';

export type AcupointSurface={
 mesh_id:string;
 triangle_index:number;
 barycentric:[number,number,number];
};

export type AcupointPlacementPoint={
 id:string;
 side:AcupointSide;
 position?:[number,number,number];
 surface?:AcupointSurface;
 status:AcupointPlacementStatus;
 placed_at:string;
 note:string;
};

export type AcupointMeshBinding={
 atlas_sha256:string;
 skin_part_id:string;
 frame:{units:'m';left:'+x';anterior:'+z';up:'+y'};
};

export type AcupointPlacementSource={
 schema_version:1;
 mesh_binding:AcupointMeshBinding;
 points:AcupointPlacementPoint[];
};

export type AcupointRenderPoint={
 id:string;
 side:AcupointSide;
 position:[number,number,number];
 surface:AcupointSurface;
 status:'PLACED'|'FLAGGED';
 origin:AcupointOrigin;
 snap_distance_m?:number;
 note?:string;
};

export type AcupointRenderRegistry={
 schema_version:1;
 mesh_binding:AcupointMeshBinding;
 midline_x:number;
 generated_at:string;
 counts:{source_entries:number;render_points:number;placed:number;mirrored:number;flagged:number;skipped:number};
 points:AcupointRenderPoint[];
};

export type AcupointPlacementCandidate={
 id:string;
 side:AcupointSide;
 position:[number,number,number];
 surface:AcupointSurface;
 mirror_preview?:{
  side:'left'|'right';
  position:[number,number,number];
  surface:AcupointSurface;
  snap_distance_m:number;
 };
};

export type MeridianLineVertex={
 position:[number,number,number];
 triangle_index:number;
};

export type MeridianLinePolyline={
 point_ids:string[];
 vertices:MeridianLineVertex[];
 skin_path_length_m:number;
};

export type MeridianLinePath={
 meridian:MeridianId;
 side:AcupointSide;
 topology_path_index:number;
 polylines:MeridianLinePolyline[];
};

export type MeridianLinesRegistry={
 schema_version:1;
 mesh_binding:AcupointMeshBinding;
 generated_at:string;
 warnings:Array<{meridian:MeridianId;side:AcupointSide;from:string;to:string;message:string}>;
 paths:MeridianLinePath[];
};
