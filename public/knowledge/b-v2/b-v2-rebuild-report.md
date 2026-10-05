# B v2 source-first relation graph rebuild report

Final judgment: **B_V2_FREEZE_CANDIDATE**

## Completion
- Statements: 583
- Exact semantic matches: 583/583
- Remaining blocked/mismatched: 0
- Landmark nodes: 2528
- Relation instances: 885
- Geometry nodes: 81
- Conditional branches: 115
- Composite bindings: 210
- Proportional measurements: 288
- B-v2 source-backed derived landmarks: 72

## Known defect repair
- Repaired: 235/235
- Unresolved CRITICAL: 0
- Unresolved MAJOR: 0

## Mandatory regressions
- CV1: PASS
- CV12: PASS
- GB26: PASS
- ST35: PASS
- ST29: PASS

## Negative validator tests
- S:ST35:location|depression_argument_to_patellar_ligament: PASS
- S:CV12:note:1|remove_one_line_endpoint: PASS
- S:CV1:location|remove_sex_conditions: PASS
- S:LU5:note:1|remove_between_endpoint: PASS
- S:GB26:location|remove_composite_parent: PASS
- S:ST18:note:1|replace_intersection_operand: PASS

## Upstream regression
- Location identity-resolution finalization v1: UNCHANGED
- Notes anatomical identity mapping v1 (derived from frozen Notes semantic-role v0.3): UNCHANGED
- Remarks adjudication v1 (1A-backed): UNCHANGED

- Orphan references: 0
- Invalid FMA references: 0
- Deterministic rebuild hash: `7c636f1fbadb1d367343b4ee7d5cf6a803e38b350cb72d739e8b4486fabef5f0`
- Deterministic reproducibility: PASS

## v1 → v2 semantic diff
- added_landmark: 1051
- removed_landmark: 844
- rebound_relation_argument: 355
- changed_relation_type: 0
- added_relation_semantics: 882
- removed_relation_semantics: 2591
- added_geometry: 0
- removed_geometry: 16
- added_conditional_branch: 115
- composite_binding_change: 210
