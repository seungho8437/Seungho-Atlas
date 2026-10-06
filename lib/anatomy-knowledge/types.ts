export type AnatomyLocalization = {
  nameKo?: string;
  legacyKo?: string;
  hanja?: string;
  descriptionKo?: string;
  aliases?: string[];
  status?: 'verified' | 'derived' | 'review-needed';
  sourceIds?: string[];
  sourceNameEn?: string;
  unresolvedTokens?: string[];
};

export type AnatomyLocalizationMap = Record<string, AnatomyLocalization>;

export type MeridianId =
  | 'LU' | 'LI' | 'ST' | 'SP' | 'HT' | 'SI'
  | 'BL' | 'KI' | 'PC' | 'TE' | 'GB' | 'LR' | 'GV' | 'CV';

export type KnowledgeSource = {
  id: string;
  title: string;
  publisher?: string;
  year?: number;
  note?: string;
};

export type KnowledgeSourceMap = Record<string, KnowledgeSource>;

export type Acupoint = {
  id: string;
  meridian: MeridianId;
  number: number;
  who2008Page: number;
  name: {
    ko: string;
    hanja: string;
    pinyin?: string;
    en?: string;
  };
  locationKo?: string;
  laterality: 'midline' | 'bilateral';
  sourceIds: string[];
};

export type AcupointSemanticGraphV21 = {
  schema_version: string;
  artifact: string;
  source_statements: Array<{source_statement_id:string;point_id:string;section:'location'|'note'|'remarks';text_canonical:string;source?:{pdf_page?:number;printed_page?:number};audit_source_page?:number}>;
  landmark_nodes: Array<{node_id:string;source_statement_id:string;point_id:string;source_raw:string;derived_semantic_label?:string;fma_id?:string|null;cross_reference_point_id?:string}>;
  relation_instances: Array<{relation_id:string;subject_node_id:string;relation_type:string;argument_node_ids:string[];source_statement_id:string;cue_span?:{source_raw?:string};branch_id?:string|null}>;
  conditions: Array<{condition_id:string;source_statement_id:string;condition_type:string;source_span?:{source_raw?:string};branch_id?:string|null;branch_relation_ids?:string[];branch_landmark_ids?:string[]}>;
  proportional_measurements: Array<{measurement_id:string;source_statement_id:string;value:number;unit:string;direction?:string|null;cue_span?:{source_raw?:string};anchor_landmark_id?:string|null;branch_id?:string|null}>;
};
