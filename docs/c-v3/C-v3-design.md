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
