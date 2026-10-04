import type {AnatomyLocalization, AnatomyLocalizationMap, MeridianId, MeridianInfo} from './types';

export const MERIDIAN_INFO: Record<MeridianId, MeridianInfo> = {
  LU:{code:'LU',nameKo:'수태음폐경',nameHanja:'手太陰肺經'},
  LI:{code:'LI',nameKo:'수양명대장경',nameHanja:'手陽明大腸經'},
  ST:{code:'ST',nameKo:'족양명위경',nameHanja:'足陽明胃經'},
  SP:{code:'SP',nameKo:'족태음비경',nameHanja:'足太陰脾經'},
  HT:{code:'HT',nameKo:'수소음심경',nameHanja:'手少陰心經'},
  SI:{code:'SI',nameKo:'수태양소장경',nameHanja:'手太陽小腸經'},
  BL:{code:'BL',nameKo:'족태양방광경',nameHanja:'足太陽膀胱經'},
  KI:{code:'KI',nameKo:'족소음신경',nameHanja:'足少陰腎經'},
  PC:{code:'PC',nameKo:'수궐음심포경',nameHanja:'手厥陰心包經'},
  TE:{code:'TE',nameKo:'수소양삼초경',nameHanja:'手少陽三焦經'},
  GB:{code:'GB',nameKo:'족소양담경',nameHanja:'足少陽膽經'},
  LR:{code:'LR',nameKo:'족궐음간경',nameHanja:'足厥陰肝經'},
  GV:{code:'GV',nameKo:'독맥',nameHanja:'督脈'},
  CV:{code:'CV',nameKo:'임맥',nameHanja:'任脈'},
  EX:{code:'EX',nameKo:'경외기혈',nameHanja:'經外奇穴'},
  SA:{code:'SA',nameKo:'표면해부학',nameHanja:'表面解剖學'},
  AA:{code:'AA',nameKo:'이침',nameHanja:'耳鍼'},
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
