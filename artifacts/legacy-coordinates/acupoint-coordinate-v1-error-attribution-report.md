# acupoint-coordinate-v1 Error Attribution Audit — Decision Report

Generated from provisional C v1 baseline. Frozen B SHA-256: `6dd00d386a6262d02900ec5a30ea9b18aace899f071159e772c12679740b1d06`.

## Decision

- `acupoint-coordinate-v1` remains **provisional / NOT frozen**.
- The former 401 `solved/validated` physical records are reinterpreted for audit as `provisional_projected_candidate`; the original v1 files are preserved unchanged.
- Frozen B is **not globally invalid**.
- However, two repeated source-geometry cardinality defects are confirmed and qualify for a **minimal B reopen proposal only for the affected geometry records**: CV1 and CV12.
- C v2 must not treat any legacy coordinate as ground truth.

## Provenance census of the 401 former solved records

| Item | Count |
|---|---:|
| physical records previously marked solved | 401 |
| legacy BP3D coordinate candidate reused | 401 |
| native relation operation executed | 0 |
| reused legacy surface projection | 401 |
| records with specialized-anchor dependency | 88 |

Therefore v1 did not prove WHO anatomical correctness. It copied the legacy raw/projected coordinates after dependency/laterality gating.

## Representative error-attribution sample

23 physical records were traced across head/face, neck, thorax/abdomen, back, upper limb, hand, lower limb, foot, midline and bilateral groups.

| Metric | Count |
|---|---:|
| audited physical records | 23 |
| normal controls | 11 |
| visually wrong records | 6 |
| additional visual-review/problem records | 6 |
| first failure: RELATION_SOLVER_NOT_EXECUTED | 21 |
| first failure: MEASUREMENT_CALIBRATION_ERROR | 2 |
| B-layer structural error suspected/confirmed in sample | 2 |
| BP3D realization error counted in the representative point classifier | 0 |
| anchor/calibration error in representative point classifier | 2 |
| legacy candidate implicated | 23 |
| large projection-distance error (>0.1 model unit) | 5 |
| unknown | 0 |

The point-level classifier and the anchor/calibration audit are separate: independent anchor inspection found additional C-layer realization defects described below.

## Confirmed minimal B structural defects

### CV1
WHO source: “In the perineal region, at the midpoint of the line connecting the anus with the posterior border of the scrotum in males and the posterior commissure of labium majoris in females.”

Frozen B relation correctly contains a `midpoint-between` relation with two arguments, but geometry node `G:S:CV1:location:line:0` represents “line connecting” with only **one endpoint** (`L:1562`).

Classification: `B_SOURCE_OR_RELATION_ERROR` — geometry cardinality defect.

Minimal repair scope: reconstruct only this reference-line geometry dependency so that the two WHO endpoints are represented. Do not alter unrelated CV1 ontology identities or other B records unless subsequent source adjudication requires it.

### CV12
WHO note: “CV12 is located at the midpoint of the line connecting the xiphisternal junction and the centre of umbilicus.”

Frozen B geometry node `G:S:CV12:note:1:line:0` represents “line connecting” with only **one endpoint** (`N:CV12:1:m2`, xiphisternal junction), omitting the umbilicus endpoint.

Classification: `B_SOURCE_OR_RELATION_ERROR` — geometry cardinality defect.

Minimal repair scope: add the missing umbilicus endpoint to this one reference-line geometry record after source adjudication. Do not reopen the whole B graph.

## Confirmed C-layer anchor / realization defects

### Suprasternal notch
Current anchor is derived from `FMA7485 sternum`, feature `center`, at approximately:
`[0.000927, 1.316288, 0.084718]`.

This is not the jugular/suprasternal notch feature. It produces a suprasternal-to-xiphisternal vertical span of only ~0.050917 model units for 9 B-cun (~0.005657/unit per cun).

Classification: `BP3D_REALIZATION_ERROR` + downstream `MEASUREMENT_CALIBRATION_ERROR`.

### Superior border of pubic symphysis
Current constructed point:
`[0.082119, 1.009053, 0.083338]`.

A midline pubic-symphysis anchor should not be ~0.082 model units lateral to the median plane, and its superior-inferior separation from the umbilicus is only ~0.030 model units.

Classification: `BP3D_REALIZATION_ERROR` / anchor construction error, with downstream abdominal B-cun calibration failure.

### Inferior border of medial condyle of tibia
Current derived definition uses generic tibia feature `inferior`; both left and right entries resolve to the same coordinate:
`[0.055207, 0.072016, -0.014434]`.

This is anatomically the distal tibial extremum, not the inferior border of the medial condyle; identical bilateral coordinates also violate laterality.

Classification: `BP3D_REALIZATION_ERROR` + `LATERALITY_ERROR`, with downstream lower-leg B-cun calibration failure.

## Calibration audit

The current audit enumerated 38 physically used calibration-side records after excluding unused midline copies. Twelve carry review/blocker issues. The strongest blockers are:

- `CHEST_SUPRASTERNAL_TO_XIPHISTERNAL`: invalid suprasternal endpoint; 9 B-cun compressed to ~0.050917 model units.
- `ABDOMEN_UMBILICUS_TO_PUBIC_SYMPHYSIS`: pubic-symphysis anchor geometry is implausible; 5 B-cun compressed to ~0.029997 model units.
- `LEG_MEDIAL_TIBIAL_CONDYLE_TO_MEDIAL_MALLEOLUS`: proximal endpoint is actually derived from the tibial inferior extremum; ~0.0143 / ~0.0139 model-unit span for 13 B-cun.
- `ANKLE_MEDIAL_MALLEOLUS_TO_SOLE`: stored calibration interval does not match the current endpoint geometry and requires re-derivation before use.

Cross-axis ratio comparisons are not used as proof of error; ratios are meaningful only within anatomically comparable calibration frames.

## Representative full-trace conclusions

- **CV1**: WHO relation itself exposes a valid midpoint concept, but B line geometry loses one endpoint; the legacy coordinate is therefore not usable as evidence. First failing layer: `B_SOURCE_OR_RELATION_ERROR` for the geometry cardinality record, followed by `RELATION_SOLVER_NOT_EXECUTED`.
- **CV24**: B encodes face/depression constraints, but the legacy coordinate path never executes those relations. First failing layer: `RELATION_SOLVER_NOT_EXECUTED`.
- **GB26 L/R**: B contains the 11th-rib and umbilical-level evidence with side-specific rib meshes available. The wrong legacy location is not evidence that B is wrong. First failing layer: `RELATION_SOLVER_NOT_EXECUTED` / `LEGACY_COORDINATE_CANDIDATE_ERROR`.
- **ST29**: relation execution is absent and the abdominal vertical calibration is corrupted by the pubic-symphysis anchor. First failing layer: `MEASUREMENT_CALIBRATION_ERROR`.
- **ST35**: patella mesh is available but the relation “inferior/lateral depression” was never geometrically executed; the legacy point was merely projected. First failing layer: `RELATION_SOLVER_NOT_EXECUTED`.
- **LU5 / LI10 / PC7 / BL54 / BL65 / TE17** and controls: all still demonstrate that v1’s relation graph was used as a gate/provenance layer, not as the forward coordinate solver.

## Required next action

Do **not** generate a globally “validated” C v2 yet.

1. Reopen only the two confirmed frozen-B geometry records for CV1 and CV12, after recording the minimal patch.
2. Keep all other B records frozen.
3. Rebuild the realization/anchor layer, correcting the suprasternal notch, pubic symphysis, tibial-condyle and any other physical-side anchor failures found by the full anchor audit.
4. Recompute proportional calibration from corrected endpoints.
5. Implement the relation-native forward solver.
6. Compute numeric residuals before projection and again after projection.
7. Use legacy coordinates only as comparison/seed/fallback-review candidates.
8. Run fresh visual QC; only records passing relation residuals + surface + visual QC may become `final-validated`.

No frozen B record has been modified by this audit.
