export type LandmarkAnchorSide = 'left' | 'right';

export type LandmarkSurfaceProjection = {
  meshId: string;
  triangleIndex: number;
  barycentric: [number, number, number];
  distance: number;
};

export type LandmarkAnchorCandidate = {
  landmarkId: string;
  position: [number, number, number];
  surfaceProjection: LandmarkSurfaceProjection;
  method: 'manual-anchor' | 'specialized-detector' | 'specialized-detector+manual-confirmation';
  side?: LandmarkAnchorSide;
  detectorId?: string;
  detectorConfidence?: 'moderate' | 'high';
};

export type SpecializedLandmarkAnchorRecord = LandmarkAnchorCandidate & {
  modelRevision: string;
  reviewStatus: 'proposed' | 'reviewed' | 'accepted' | 'rejected';
  evidence: {
    views: string[];
    definitionCheck: boolean;
    detectorMetrics?: Record<string, number | string | boolean>;
    reviewerNote?: string;
  };
  provenance: {
    createdBy: string;
    createdAt: string;
    sourceSpecVersion: number;
  };
};

export type SpecializedLandmarkSpec = {
  landmarkId: string;
  class: string;
  laterality?: LandmarkAnchorSide;
  primaryMethod: string;
  detector: {
    type: string;
    status: string;
    requiredSignals: string[];
    forbiddenFallbacks: string[];
    output: string;
  };
  manualAnchor: {
    geometryType: string;
    definition: string;
    constraints: string[];
    requiredEvidence: string[];
  };
};
