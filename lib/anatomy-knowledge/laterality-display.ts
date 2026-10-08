import registry from '@/data/anatomy-laterality-display.json';
import type {AnatomyLocalization} from './types';

export type LateralityDisplay = {side:'left'|'right';ko:string;hanja:string;en:string};
const neutralized=registry.neutralized as Record<string,LateralityDisplay>;

export function anatomySideContext(conceptId:string):string|undefined {
 const record=neutralized[conceptId];
 return record ? (record.side==='left'?'측면: 왼쪽':'측면: 오른쪽') : undefined;
}
export function displayAnatomyNameEn(conceptId:string,sourceEnglish?:string):string {
 return neutralized[conceptId]?.en ?? sourceEnglish ?? '';
}
export function displayAnatomyNameHanja(conceptId:string,hanja?:string):string {
 return neutralized[conceptId]?.hanja ?? hanja ?? '';
}
export function displayAnatomyLegacyKo(conceptId:string,legacyKo?:string):string|undefined {
 const record=neutralized[conceptId];
 if(!record||!legacyKo)return legacyKo;
 return legacyKo.replace(record.side==='left'
   ? /^(왼쪽|왼|좌측|좌)\s*/
   : /^(오른쪽|오른|우측|우)\s*/,'');
}
export function displayAnatomyNameKo(conceptId:string,loc?:AnatomyLocalization,sourceEnglish?:string):string {
 // Approved symmetrical pair: show the shared structure term. Keep laterality in metadata.
 const record=neutralized[conceptId];
 if(record)return record.ko;
 const canonical=loc?.nameKo;
 if(!canonical)return sourceEnglish??'';
 // For excluded/semantically special records, retain the original explicit side rendering.
 const english=sourceEnglish??loc?.sourceNameEn??'';
 const match=english.match(/^(left|right)\s+(.+)$/i);
 if(!match)return canonical;
 const side=match[1].toLowerCase();
 if(/\b(?:left|right)\b/i.test(match[2]))return canonical;
 const prefix=side==='left'?'왼쪽':'오른쪽';
 let base=canonical.replace(/^(왼쪽|오른쪽)\s*/,'');
 if(side==='left')base=base.replace(/^왼(?=\S)/,'');
 else base=base.replace(/^오른(?=\S)/,'');
 return (prefix+' '+base).replace(/\s+/g,' ').trim();
}
