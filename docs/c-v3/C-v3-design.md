# C v3 — Canonical Design

Status: **S1 REDESIGN REQUIRED / implementation not started**

This document is the canonical C v3 design contract. Rejected S1 code, workflow, and G1 artifacts are not part of the active design.

## 0. Non-negotiable rules

1. B v2.1 is the semantic source graph. C must execute it; C must not silently reinterpret or replace it.
2. Legacy C v1/v2 coordinates are never solver inputs.
3. A plausible rendered point is not evidence of validity.
4. No point-specific coordinate override is permitted unless the WHO source itself requires an explicit point-specific exception and that exception is documented and regression-tested.
5. Generation, computation, local validation, family validation, point validation, and global validation are distinct states.
6. A failed gate blocks the next stage.
7. Rejected executable code/workflows/deployment artifacts are removed from the active tree rather than left as alternate pipelines.

---

# 1. Why the previous S1 is rejected

The rejected S1 attempted to assign every skin vertex to one exclusive coarse body region using:
- nearest skeletal segment axis;
- a radius threshold derived from bone radial p95;
- expanded hand/foot skeletal bounding boxes;
- mandible/clavicle Y cut-offs for head/neck;
- trunk as a residual fallback.

That construction is not a valid anatomical substrate for WHO acupoint localization.

It fails for structural reasons:

- **exclusive coarse partitioning is the wrong primitive**: many WHO locations are defined by overlapping surface, level, line, crease, interspace, boundary, and relation constraints rather than one body-region label;
- **nearest-bone logic is not semantic localization**: proximity to femur/ulna/etc. cannot establish that a point belongs to lateral abdomen, wrist crease, fourth intercostal space, etc.;
- **global-axis cut-offs do not model local anatomy**;
- **transition zones are not represented**;
- **surface topology is discarded when only vertices are classified**;
- **candidate multiplicity/uniqueness is not represented**;
- **no downstream relation can prove that a chosen candidate satisfies all source constraints**.

The user-provided visual failures are used only as evidence of these design defects, not as patch targets:

- GB23 appearing near the elbow shows that a lateral-thorax constraint can be lost and a geometrically unrelated candidate can survive.
- HT7 duplicated and displaced toward the ulnar elbow shows absence of candidate cardinality/uniqueness enforcement plus inadequate local wrist constraints.
- LU6 on the little finger shows failure to preserve a forearm line/interval constraint.
- LI7 producing three ipsilateral candidates shows that the pipeline can emit candidates without a one-point-per-side cardinality proof.
- GB26 on the femur shows that same-level + lateral-abdomen semantics are not acting as hard constraints.

These examples do **not** define the complete failure set.

---

# 2. S1 purpose: build a spatial substrate, not acupoint regions

S1 must not produce acupoint coordinates and must not try to pre-label the entire skin into a single mutually exclusive region map.

S1 produces an **acupoint-independent anatomical spatial substrate** capable of supporting later semantic execution.

## S1-A. Canonical mesh registry

For every BodyParts3D mesh/part used by C, record:

- stable part/concept identifier;
- anatomical name;
- system;
- laterality;
- parent/whole relationship when available;
- vertex count;
- triangle/index topology availability;
- axis-aligned bounds;
- centroid;
- source chunk and byte ranges;
- whether the mesh is surface, deep structure, or reference-only for C.

Required invariants:

- no unaccounted duplicated IDs;
- no silent left/right conflation;
- units and world coordinate convention fixed;
- every geometry lookup returns a stable typed object, never just an untyped vertex array.

## S1-B. Body frame and local anatomical frames

One global frame is insufficient.

S1 shall establish:

- global patient-left/right, superior/inferior, anterior/posterior frame;
- bilateral limb frames for upper arm, forearm, hand, thigh, lower leg, foot;
- joint-level frames for shoulder, elbow, wrist, hip, knee, ankle;
- trunk-local frame;
- head/neck frame.

Each frame must be derived from multiple independent anatomical references where possible.

Every frame record must include:
- defining structures;
- fitting method;
- residual/error measures;
- laterality;
- confidence/status.

A frame is invalid if its orientation depends on one arbitrary mesh extremum or a single global-axis cut-off.

## S1-C. Preserve the skin as a surface

The skin must be represented as a triangulated/topological surface, not merely a bag of labeled vertices.

S1 must support deterministic primitives for:

- nearest point on skin triangle;
- ray-surface intersection;
- plane-surface intersection;
- local surface normal;
- connected-component check;
- geodesic distance/path on skin;
- projection of a deep/internal candidate to the anatomically eligible skin;
- side-of-plane / interval / half-space queries.

Every surface result must preserve the triangle/face identity and barycentric coordinates so it can be reproduced exactly.

## S1-D. Anatomical constraints are overlapping masks, not one exclusive region label

S1 may construct reusable anatomical masks/fields, but they are **constraints**, not a global partition.

Examples:
- left/right;
- upper/lower limb segment interval;
- hand/foot envelope;
- anterior/posterior/medial/lateral surface aspect;
- trunk level slabs;
- thoracic/abdominal/pelvic eligibility;
- joint-neighborhood zones;
- intercostal candidate bands when constructible from ribs;
- proximity fields around explicit structures.

A skin point may satisfy multiple masks simultaneously.

No `else -> trunk` or equivalent residual fallback is permitted.

If a requested anatomical mask cannot be derived with justified geometry, the result is `UNRESOLVED`, not an inferred substitute.

## S1-E. Reusable spatial query API

S1 exposes typed primitives only; it does not know acupoint IDs.

Minimum query families:

- `entity_mesh(id, side)`
- `entity_subfeature(parent, feature_contract)`
- `local_frame(region_or_joint, side)`
- `surface_mask(predicate_set)`
- `level_plane(reference)`
- `line_between(a,b)`
- `plane_through(...)`
- `intersection(A,B,...)`
- `project_to_skin(candidate, eligibility_mask, direction_contract)`
- `nearest_on_skin(candidate, eligibility_mask)`
- `geodesic_distance(a,b, eligibility_mask)`

Every query returns:
- status: RESOLVED / MULTIPLE / UNRESOLVED / INVALID;
- zero or more candidates;
- provenance;
- residuals;
- eligibility constraints used.

S1 never converts MULTIPLE to RESOLVED by arbitrary nearest-neighbor choice.

---

# 3. G1 — S1 validation gate

G1 is not one visual page. It contains independent sub-gates.

## G1-A. Registry integrity

Pass conditions:
- all required atlas parts are readable;
- ID/name/laterality/system mappings are deterministic;
- no silent alias collision;
- mesh bounds and counts are reproducible;
- input hashes match G0.

## G1-B. Frame audit

Independent validator recomputes orientation tests without calling the S1 frame-building functions.

It must verify:
- left/right sign on multiple bilateral structures;
- superior/inferior order using multiple axial structures;
- anterior/posterior direction using independent structures;
- monotonic proximal-distal ordering of each limb;
- bilateral symmetry residuals within declared tolerances.

Any failed frame blocks G1.

## G1-C. Surface/topology audit

Pass conditions:
- skin topology is readable and deterministic;
- triangle-to-vertex references are valid;
- surface normals are internally consistent enough for queries;
- ray/nearest-point/plane-intersection round-trip tests pass;
- no unexpected disconnected component is silently merged;
- barycentric reconstruction residual is within tolerance.

## G1-D. Boundary and transition stress test

This is a predeclared challenge set based on anatomy, not on hand-picked acupoints.

It must cover at minimum:
- neck ↔ trunk;
- shoulder/axilla ↔ upper arm;
- elbow transition;
- wrist ↔ hand;
- thorax ↔ abdomen;
- abdomen/pelvis ↔ thigh/groin;
- knee/popliteal transition;
- ankle ↔ foot;
- medial/lateral/anterior/posterior surface aspects.

The challenge set is defined **before** observing the test output.

Success means the spatial masks/frames behave coherently at transitions. It does not mean all future landmark classes are solved.

## G1-E. Human visual QC

Human review visualizes:
- global/local frames;
- skin surface and normals;
- anatomical masks/fields;
- transition challenge probes;
- left/right and proximal/distal axes.

No acupoint coordinates are shown at G1.

Human QC is confirmatory. It must not be the primary mechanism for discovering routine structural errors.

### G1 pass rule

G1 = APPROVED only if G1-A through G1-E all pass.

Automatic tests cannot substitute for G1-E.
G1-E cannot override a failed automatic sub-gate.

---

# 4. S2 — exhaustive landmark realization layer

S2 begins only after G1 approval.

Input scope is the **entire B v2.1 landmark-node census**, not selected acupoints.

Each landmark node is assigned to a declared realization contract such as:

- direct entity mesh;
- entity subfeature;
- body/surface constraint;
- crease/border/notch/depression/orifice specialized anchor;
- anatomical/reference line;
- constructed geometry;
- reference-acupoint dependency;
- source-contextual unresolved.

S2 does not force every node to resolve. It guarantees that every node has a deterministic route and an explicit terminal state.

## G2

G2 audits every landmark class and realization contract:
- coverage;
- laterality;
- cardinality;
- geometry correctness;
- source compatibility;
- class-specific challenge cases;
- unresolved reason taxonomy.

No S3 until G2 passes.

---

# 5. S3 — relation-operation execution

S3 executes B v2.1 relation semantics using only validated S1/S2 primitives.

Examples:
- surface-landmark;
- relative-to;
- reference-acupoint;
- same-level;
- on-line;
- between;
- center-of;
- midpoint-between;
- at-junction;
- fraction-along-line;
- midpoint-of-entity;
- overlies.

Each relation operation must return a residual or explicit satisfaction test.

## G3

Validation unit is **relation family × landmark family** across the entire graph.

A relation family passes only when:
- operands are valid;
- expected cardinality is met;
- all hard constraints are satisfied;
- laterality and anatomical eligibility hold;
- MULTIPLE is not silently collapsed;
- no legacy coordinate was used.

---

# 6. S4 — 361-acupoint synthesis

Only after G3.

For each logical acupoint:

1. gather all hard source relations;
2. execute the dependency graph;
3. intersect constraints/candidate sets;
4. enforce cardinality:
   - midline point: exactly one valid coordinate unless source specifies otherwise;
   - bilateral point: exactly one valid coordinate per side;
5. require all hard relations to be computable and satisfied;
6. project to skin only through the validated projection contract;
7. otherwise return UNRESOLVED.

Examples such as two HT7 points on one side or three LI7 points on one side are therefore impossible to promote to VALIDATED: they fail cardinality before publication.

---

# 7. G4 — final 361-point audit

G4 contains:

- semantic source-consistency audit;
- relation residual audit;
- cardinality/uniqueness audit;
- laterality audit;
- skin adherence audit;
- anatomical eligibility audit;
- dependency-cycle audit;
- bilateral/global outlier audit;
- full human visual QC.

A coordinate may be published only after G4 approval.

---

# 8. State machine

Allowed states:

`DISCOVERED`
→ `CLASSIFIED`
→ `IMPLEMENTED`
→ `COMPUTABLE`
→ `LOCALLY_VALIDATED`
→ `FAMILY_VALIDATED`
→ `POINT_VALIDATED`
→ `GLOBAL_VALIDATED`

The word `VALIDATED` must not be used for generated-but-unverified coordinates.

---

# 9. Active C v3 state after rejection

- G0 input lock: retained and moved to `artifacts/c-v3/g0/inputs.lock.json`.
- rejected S1 executable: removed.
- rejected S1 GitHub Actions workflow: removed.
- rejected G1 body-frame/skin-region artifacts: removed.
- S1 implementation: **not started under this redesign**.
- next action: implement S1-A through S1-E exactly against this contract, then build independent G1-A through G1-D validators before asking for G1-E human review.
