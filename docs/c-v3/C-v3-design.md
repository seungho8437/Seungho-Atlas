# C v3 — Canonical Four-Stage Design

Status: **Stage 1 APPROVED · Stage 2 IN PROGRESS**

This document is the canonical C v3 contract. Rejected S1/G1 implementations are not active.

## Non-negotiable rules

1. B v2.1 is the semantic source graph. C executes it; C does not silently reinterpret it.
2. Legacy C v1/v2 coordinates are never solver inputs.
3. Plausible rendering is not validity.
4. No point-specific coordinate override is allowed unless the WHO source itself requires an explicit point-specific exception and that exception is documented and regression-tested.
5. GENERATED, COMPUTABLE, LOCALLY_VALIDATED, FAMILY_VALIDATED, POINT_VALIDATED and GLOBAL_VALIDATED are distinct states.
6. A failed stage blocks the next stage.
7. Rejected executable code/workflows/deployment artifacts are removed from the active tree.
8. The skin is a component-aware indexed triangle surface. No closed-manifold assumption is made.
9. Spatial eligibility is expressed as overlapping constraints/masks, never as one exclusive whole-body region partition and never by an `else -> trunk` fallback.
10. MULTIPLE and UNRESOLVED are first-class outcomes; neither may be silently collapsed to RESOLVED.


## Stage 2–4 cross-stage execution and validation invariants

These requirements are mandatory and apply in addition to each stage's local contract.

1. **Surface-expression geometry registry — human-frozen Stage 2 input.**
   Expressions such as `dorsum`, `palmar/plantar aspect`, `median line`, `crease`, `border`, `interspace`, `fossa/depression`, `anterior/posterior/medial/lateral aspect`, and comparable WHO surface-language constructs must have explicit geometric definitions in a dedicated registry before they may execute. The registry is a human-review input and must record source term, geometric construction, admissible anatomical scope, laterality/aspect semantics, expected cardinality, tolerances, and provenance. **An expression with no frozen definition returns `UNRESOLVED`; no nearest-object or lexical fallback is permitted.**

2. **B-cun / F-cun calibration — human-frozen with WHO citation.**
   Stage 2 shall produce a calibration table for every proportional-measurement interval used by the graph. Each row must carry the WHO citation needed to audit it: source document/edition, page, section or point, exact source span/quotation locator, anatomical endpoints, unit type (B-cun/F-cun), nominal cun length/partition rule, pose assumptions, and geometry realization route. Solver execution may use only the human-frozen calibration table. Missing or disputed calibration remains `UNRESOLVED`.

3. **Final skin projection — aspect-directed ray cast is primary.**
   A solved internal/geometric candidate is projected to skin by a ray whose direction is determined by the frozen anatomical aspect/local-frame contract. `nearest_on_skin` is a validation/comparison primitive only and must not be the production final projector. Every projection family must declare a **projection-distance budget** (absolute and/or anatomy-normalized) before execution. A missing eligible ray hit, multiple non-disambiguated hits, wrong aspect/component, or distance beyond budget is not solved.

4. **Execution trace required for every solved physical coordinate.**
   Every solved coordinate must include a machine-auditable trace from B v2.1 source statement(s) through landmark realization, calibration/condition selection, relation operations, candidate intersection, aspect ray, skin hit, residuals, cardinality decision, and final coordinate. A coordinate without a complete trace cannot be promoted beyond generated state.

   The independent validator must additionally load C v1 coordinates **only as adversarial audit data, never as solver input**, and report suspicious exact/near-exact coordinate collisions. Its negative suite must include an explicit **“copy a v1 coordinate + fabricate a syntactically valid execution trace”** mutation; the validator must reject it by independently recomputing the semantic/geometric constraints rather than trusting the submitted trace.

5. **Permanent regression sets.**
   Stage 3 and Stage 4 must always run the frozen known-error regression set, including the currently observed failure examples **GB23, HT7, LU6, LI7, GB26**, plus the exact **B permanent-15** set from the frozen B regression/defect artifacts. The B permanent-15 membership is imported by immutable IDs from the B artifact rather than re-created or renamed in C. Regression membership is not a special solver path: the cases use the same family executors as every other point.

6. **Pose-incompatible branches remain conditional.**
   The atlas default pose is an explicit execution precondition. A WHO conditional branch that requires a body pose incompatible with the BodyParts3D default pose is not numerically forced onto the default mesh. Its terminal state remains `CONDITIONAL` / not computed, with the required pose and source branch preserved. A compatible branch may execute only when its pose predicate is independently satisfied.

7. **Validator independence is structural, not nominal.**
   Stage 2–4 validators must not import or share the solver's execution spec, numeric tolerances/constants, geometric-definition registry objects, calibration tables, projection budgets, or relation implementation functions. Validator-side expectations are built from separately frozen review inputs / source-derived contracts and independent code paths. Sharing B v2.1 and immutable primary-source evidence is allowed; sharing solver-derived expected values is not. Any validator that merely replays solver constants or accepts solver trace claims without recomputation is invalid.

---

# Stage 1 — Spatial substrate

Purpose: make BodyParts3D geometrically trustworthy and queryable without knowing any acupoint ID.

Stage 1 contains the following responsibilities; these are subtests, not separate project stages.

### 1A. Canonical mesh registry

For every BodyParts3D part/concept used by C:
- stable IDs and names;
- anatomical system;
- laterality including explicit bilateral cases;
- binary chunk/offsets;
- vertex/index/triangle counts;
- bounds;
- concept-to-part bindings;
- source hashes.

### 1B. Global and local anatomical frames

Required frames:
- global patient left/right, superior/inferior, anterior/posterior;
- trunk and head/neck;
- bilateral upper arm, forearm, hand, thigh, lower leg, foot;
- shoulder, elbow, wrist, hip, knee, ankle centers.

Frame orientation must be derived from explicit neighboring skeletal anatomy and independently validated. A generic distance-to-trunk heuristic or a single world-axis cutoff is forbidden.

Hands and feet use anatomically appropriate surface axes:
- hand: proximal/distal, outward, palmar;
- foot: proximal/distal, outward, dorsal.

### 1C. Topology-preserving skin surface

The skin is represented as indexed triangles with:
- triangle identity;
- barycentric coordinates;
- nearest triangle point;
- ray-surface intersection;
- plane-surface intersection;
- triangle normal;
- connected-component membership;
- mesh-edge geodesic;
- deterministic reconstruction.

The source skin may contain multiple components and isolated topology defects. These must be measured and exposed, not hidden. Invalid indices, degenerate triangles, or component coverage loss are fatal.

### 1D. Typed spatial query layer

Queries return one of:
- `RESOLVED`
- `MULTIPLE`
- `UNRESOLVED`
- `INVALID`

and preserve candidates, provenance and residuals.

Reusable primitives include:
- entity mesh/subfeature lookup;
- local frame lookup;
- half-space and interval masks;
- intersections/unions of masks;
- lines/planes/intersections;
- nearest eligible skin point;
- ray/plane surface intersections;
- component-aware geodesic distance.

No WHO acupoint ID is used in Stage 1.

### Stage 1 pass contract

Automatic validation must independently establish:
- complete atlas/binary integrity;
- registry reproducibility;
- global/local frame orientation and anatomical chain order;
- bilateral consistency;
- topology/index validity;
- component coverage;
- actual-atlas nearest/ray/plane/barycentric query round-trips;
- no legacy coordinate input;
- no exclusive region partition;
- no acupoint-specific logic.

A separate human review artifact shows only body surface, frames and joints. No acupoints are rendered.

Stage 1 is fully approved only after the automatic suite passes and the human visual review is accepted.

---

# Stage 2 — Semantic execution layer

Purpose: execute the complete B v2.1 WHO spatial ontology on the Stage 1 substrate.

Input scope is the entire B v2.1 graph, not selected example points.

Stage 2 must cover:
- every landmark class;
- every relation type;
- every proportional measurement;
- every conditional branch;
- every reference-acupoint dependency;
- every constructed geometry.

Examples include `same-level`, `between`, `on-line`, `relative-to`, `surface-landmark`, B/F-cun, creases, interspaces, borders and reference lines.

Each B node/relation obtains a deterministic execution route and explicit terminal state. Stage 2 does not force all items to resolve.

Stage 2 validation is exhaustive by semantic family × landmark family and checks:
- coverage;
- laterality;
- cardinality;
- landmark realization;
- relation residuals;
- source compatibility;
- unresolved taxonomy;
- no legacy-coordinate leakage.

Stage 2 answers: **Can the ontology's WHO spatial meaning actually be executed on BodyParts3D?**

---

# Stage 3 — 361-acupoint synthesis

Purpose: synthesize coordinates only from Stage 2-validated semantic dependencies.

For each logical acupoint:
1. gather all hard source constraints;
2. execute the dependency graph;
3. intersect eligible candidate sets;
4. enforce cardinality;
5. require every hard constraint to be computable and satisfied;
6. project to skin only through validated Stage 1/2 contracts;
7. otherwise return UNRESOLVED.

Cardinality:
- midline point: exactly one valid coordinate unless the source explicitly says otherwise;
- bilateral point: exactly one valid coordinate per side.

Multiple candidates can never be published as a validated coordinate.

---

# Stage 4 — Global validation

Purpose: decide whether the complete 361-point product is publishable.

Required audits:
- source-semantic consistency;
- relation residuals;
- cardinality/uniqueness;
- laterality;
- surface adherence;
- anatomical eligibility;
- dependency cycles;
- bilateral/global outliers;
- complete human visual QC.

Only Stage 4 approval permits `GLOBAL_VALIDATED`.

---

# Current state

- B v2.1 input lock: retained.
- rejected earlier S1/G1 executable and generated artifacts: removed from the active tree.
- Stage 1 implementation: present under `scripts/cv3/`.
- Stage 1 automatic validation on BodyParts3D: **PASS**.
- Stage 1 human visual review: **APPROVED by user after z-buffer hidden-surface QC**.
- Stage 1: **APPROVED**.
- Stage 2: **IN PROGRESS**.
- No new acupoint coordinates have been generated or deployed.
