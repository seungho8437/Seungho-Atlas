import type {AnatomyLocalization, AnatomyLocalizationMap} from './types';

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
