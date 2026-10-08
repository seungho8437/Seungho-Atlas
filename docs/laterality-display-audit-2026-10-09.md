# Laterality display audit — 2026-10-09

Baseline: `feature/hand-placed-acupoints` at `061994eea8d0bc3eac9d942d3b81a94b254634f2`.

## Scope
- This change is **presentation-only**. It does not modify `anatomy-ko.json`, `atlas.json`, FMA IDs, WHO B v2.1, skin geometry, acupoint placements, or coordinate solver.
- The source's `sourceNameEn`, `nameKo`, and `hanja` remain authoritative as originally stored.
- For a conservative subset of paired homologues, display the shared Korean/Hanja/English name. Show `측면: 왼쪽/오른쪽` in search/detail metadata so each FMA object remains distinguishable.
- A name is neutralized only when exact opposite-side FMA records share an identical Korean/Hanja base after leading side removal, there is no nested laterality, and no protected anatomical family/source-authoritative sided term is involved.

## Classification
- Total FMA glossary concepts: 3432.
- Paired English-side groups examined: 574.
- Approved neutralized groups: 512 (FMA records: 1024).
- Protected intrinsic-anatomy groups: 43.
- Direct-KAA source-sided groups: 7.
- Pair-name disagreements: 12.
- Unpaired: 14.
- Nested laterality exclusions: 0.

## Examples
- `FMA4058`/`FMA3941` left/right common carotid artery: name `온목동맥 / 總頸動脈 / common carotid artery` + side metadata.
- `FMA7205`/`FMA7204` kidney: name `콩팥 / 腎臟 / kidney` + side metadata.
- `FMA7185`/`FMA7186` upper limb: name `위팔다리 / 上肢 / upper limb` + side metadata.
- `FMA7395`/`FMA7396` main bronchi: retain side-specific name.
- `FMA7254` aortic valve cusp: retain side-specific name.
- Parent-child descriptors such as `branch of left coronary artery` remain untouched; never strip internal side words.

## Verification and constraints
- Run `npm run validate:laterality` and the repository's existing `npm run audit:korean`, `npm run check`, `npm run build`.
- The approval is **algorithmically conservative, not a claim of clinical/terminological expert review**. All excluded groups remain a manual review queue in `data/anatomy-laterality-display.json`.
- UI-only change avoids corrupting ontological identities. `sourceNameEn` may still contain left/right in the raw reference data, as required for provenance and indexing.
- New isolated work branch must be explicitly checked against deployment settings; do not delete any prior branch during this change.
