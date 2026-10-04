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
