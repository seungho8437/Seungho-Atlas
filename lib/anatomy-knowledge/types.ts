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

export type MeridianSinew = {
  id: string;
  meridian: MeridianId;
  name: {
    ko: string;
    hanja: string;
    en: string;
  };
  overviewKo?: string;
  sourceIds: string[];
};

export type AnatomyAcupointRelation = {
  anatomyId: string;
  acupointId: string;
  relation:
    | 'surface-landmark'
    | 'overlies'
    | 'adjacent'
    | 'between'
    | 'deep-to'
    | 'reference-landmark';
  noteKo?: string;
  sourceIds: string[];
};

export type AnatomyMeridianSinewRelation = {
  anatomyId: string;
  meridianSinewId: string;
  relation:
    | 'course-region'
    | 'binding-region'
    | 'branch-region'
    | 'termination-region';
  correspondence:
    | 'direct-landmark'
    | 'regional'
    | 'interpretive';
  noteKo?: string;
  sourceIds: string[];
};

export type AcupointCoordinate = {
  acupointId: string;
  side: 'left' | 'right' | 'midline';
  position: [number, number, number];
  model: 'BodyParts3D-4.0';
  status: 'validated' | 'review-needed' | 'model-limitation';
  sourceIds: string[];
};
