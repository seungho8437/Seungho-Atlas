import type {AnatomyLocalization, AnatomyLocalizationMap, MeridianId, MeridianInfo} from './types';

export const MERIDIAN_INFO: Record<MeridianId, MeridianInfo> = {
  LU:{code:'LU',nameKo:'수태음폐경',nameHanja:'手太陰肺經',color:'#64748b'},
  LI:{code:'LI',nameKo:'수양명대장경',nameHanja:'手陽明大腸經',color:'#f97316'},
  ST:{code:'ST',nameKo:'족양명위경',nameHanja:'足陽明胃經',color:'#f59e0b'},
  SP:{code:'SP',nameKo:'족태음비경',nameHanja:'足太陰脾經',color:'#a855f7'},
  HT:{code:'HT',nameKo:'수소음심경',nameHanja:'手少陰心經',color:'#ef4444'},
  SI:{code:'SI',nameKo:'수태양소장경',nameHanja:'手太陽小腸經',color:'#fb7185'},
  BL:{code:'BL',nameKo:'족태양방광경',nameHanja:'足太陽膀胱經',color:'#3b82f6'},
  KI:{code:'KI',nameKo:'족소음신경',nameHanja:'足少陰腎經',color:'#1d4ed8'},
  PC:{code:'PC',nameKo:'수궐음심포경',nameHanja:'手厥陰心包經',color:'#be123c'},
  TE:{code:'TE',nameKo:'수소양삼초경',nameHanja:'手少陽三焦經',color:'#14b8a6'},
  GB:{code:'GB',nameKo:'족소양담경',nameHanja:'足少陽膽經',color:'#84cc16'},
  LR:{code:'LR',nameKo:'족궐음간경',nameHanja:'足厥陰肝經',color:'#22c55e'},
  GV:{code:'GV',nameKo:'독맥',nameHanja:'督脈',color:'#7c3aed'},
  CV:{code:'CV',nameKo:'임맥',nameHanja:'任脈',color:'#0f766e'},
  EX:{code:'EX',nameKo:'경외기혈',nameHanja:'經外奇穴',color:'#78716c'},
  SA:{code:'SA',nameKo:'표면해부학',nameHanja:'表面解剖學',color:'#475569'},
  AA:{code:'AA',nameKo:'이침',nameHanja:'耳鍼',color:'#6b7280'},
};

export function getAnatomyLocalization(
  map: AnatomyLocalizationMap,
  conceptId: string,
): AnatomyLocalization | null {
  return map[conceptId] ?? null;
}

export function anatomySearchTerms(
  englishName: string,
  localization?: AnatomyLocalization | null,
): string[] {
  return [
    englishName,
    localization?.nameKo,
    localization?.legacyKo,
    localization?.hanja,
    ...(localization?.aliases ?? []),
  ].filter((value): value is string => Boolean(value?.trim()));
}
