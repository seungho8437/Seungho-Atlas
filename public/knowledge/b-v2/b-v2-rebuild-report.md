# B v2 source-first relation graph rebuild report

Final judgment: **B_V2_FREEZE_CANDIDATE**

## Completion
- Statements: 583
- Exact semantic matches: 583/583
- Remaining blocked/mismatched: 0
- Landmark nodes: 2408
- Relation instances: 1838
- Geometry nodes: 104
- Conditional branches: 115
- Composite bindings: 332
- Proportional measurements: 288
- B-v2 source-backed derived landmarks: 163

## Known defect repair
- Repaired: 235/235
- Unresolved CRITICAL: 0
- Unresolved MAJOR: 0

## Mandatory regressions
- CV1: PASS
- CV12: PASS
- ST35: PASS
- GB26: PASS
- ST29: PASS

## Negative validator tests
- S:ST35:location|depression_argument_to_patellar_ligament: PASS
- S:CV12:note:1|remove_one_line_endpoint: PASS
- S:CV1:location|remove_sex_conditions: PASS
- S:LU5:note:1|remove_between_endpoint: PASS
- S:GB26:location|remove_composite_parent: PASS
- S:ST18:note:1|replace_intersection_operand: PASS

## Upstream regression
- 1A v1.0.5: UNCHANGED
- Notes semantic-role v0.3: UNCHANGED
- Location semantic target v0.1: UNCHANGED
- Composite binding/decomposition v0.1: UNCHANGED
- Location identity-resolution finalization v1: UNCHANGED
- FMA registry resolution policy v0.3.1: UNCHANGED

- Orphan references: 0
- Invalid FMA references: 0
- Deterministic rebuild hash: `0b9aaf0d0ca29ebbc2a98a367e6fb7afdc513ae55e88fb0ed7600f4da8cbdae8`
- Deterministic reproducibility: PASS

## v1 → v2 semantic diff
- added_landmark: 1344
- removed_landmark: 1257
- rebound_relation_argument: 381
- changed_relation_type: 0
- added_relation_semantics: 1676
- removed_relation_semantics: 2547
- added_geometry: 7
- removed_geometry: 0
- added_conditional_branch: 115
- composite_binding_change: 332
