# Nested laterality terminology audit (2026-10-09)

## Scope and root cause
- Existing `displayAnatomyNameKo` only auto-detects English names beginning with `left/right`, leaving source names like `lateral head of left triceps brachii` visible with a redundant left-specific modifier.
- Resolve this by extending the **already-existing display policy registry**, not rewriting canonical source names or adding a second render rule.
- Original `anatomy-ko.json`, WHO B v2.1, `atlas.json`, FMA identifiers, and acupoint placement data are not modified.

## Approved classifications
- Previously neutralized: 512 pairs / 1,024 FMA records.
- Newly neutralized nested-in-English side: 96 pairs / 192 FMA records.
- Total: 608 pairs / 1216 FMA records.
- Exact counterpart pairing + English one-token laterality match + Korean/Hanja base match are all required. A conservative musculoskeletal whitelist applies.
- No inferred equivalence for unmatched, conflicting, nested-multiple, intrinsically asymmetric or organ-/vessel-identity-specific left/right names.

## Specific regression
| FMA ID | Side | Before (Korean / hanja / English) | Display after |
|---|---|---|---|
| FMA37698 | left | 왼위팔세갈래근 가쪽갈래 / 左上腕三頭筋外側頭 / lateral head of left triceps brachii | 위팔세갈래근 가쪽갈래 / 上腕三頭筋外側頭 / lateral head of triceps brachii |
| FMA37697 | right | 오른위팔세갈래근 가쪽갈래 / 右上腕三頭筋外側頭 / lateral head of right triceps brachii | 위팔세갈래근 가쪽갈래 / 上腕三頭筋外側頭 / lateral head of triceps brachii |

Side context is displayed separately, and original source labels remain searchable and retained as evidence; neither FMA identity nor spatial laterality is collapsed.

## Audit restrictions and safety
- Read-only source hierarchy: original multilingual glossary and WHO ontology are unchanged.
- Existing UI entrypoints (search label/secondary, anatomy details, 3D hover) already use `anatomy-laterality-display.json`; no rendering component changes are necessary.
- Signatures examined for one-side-word records not already neutralized: 378.
- Excluded signatures: unpaired / ambiguous 171, inconsistent 6, structurally sensitive 105.
- Exclusions are an explicit review queue and must not be globally stripped by a regex.
- Added `npm run validate:laterality` runnable check; CI build and manual visual confirmation are separate gates.

## Manual check
1. Choose FMA37698, FMA37697, FMA37696 and FMA37700 in the explorer: all should show neutral Korean/Hanja/English names, with side metadata.
2. Search using original terms like `left triceps`: result should remain discoverable; do not replace the source search index.
3. Check FMA7396/7395 (main bronchi), FMA3855/3802 (coronary trunks) and FMA7254/7247 (cardiac valve cusps): left/right remain visible.
4. Confirm branch deployment, run npm validation scripts and inspect Vercel/Cloudflare checks before promoting to production.
