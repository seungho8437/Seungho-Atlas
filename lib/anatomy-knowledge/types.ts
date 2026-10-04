export type AnatomyLocalization = {
  nameKo: string;
  legacyKo?: string;
  hanja?: string;
  descriptionKo?: string;
  aliases?: string[];
};

export type AnatomyLocalizationMap = Record<string, AnatomyLocalization>;

export type MeridianId =
  | 'LU' | 'LI' | 'ST' | 'SP' | 'HT' | 'SI'
  | 'BL' | 'KI' | 'PC' | 'TE' | 'GB' | 'LR';

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
