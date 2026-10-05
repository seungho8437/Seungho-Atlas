# B relation graph semantic integrity audit v1 — final audit-only report

**Scope:** WHO 361 acupoints / 583 source statements (361 Location + 216 Notes + 6 Remarks).
**Mode:** audit only. No B patch, no C realization/calibration change, no native C solver, no C v2 coordinate generation.

## Audit completeness
- WHO source statements audited: **583/583**
- Primary-source text match: **583/583**
- Statements with no detected semantic mismatch: **373**
- Defect-containing statements: **210**
- Affected acupoints: **174/361**
- Defect records: **291**

## Defect classes
- `SOURCE_LANDMARK_EXTRACTION_OMISSION`: **17**
- `RELATION_ARGUMENT_MISBINDING`: **140**
- `REFERENCE_LINE_ENDPOINT_OMISSION`: **13**
- `COMPOSITE_PARENT_BINDING_ERROR`: **54**
- `CONDITIONAL_ENDPOINT_SCHEMA_OR_BINDING_GAP`: **9**
- `SOURCE_RELATION_OMISSION`: **17**
- `SOURCE_RELATION_OVERGENERATION`: **2**
- `RELATION_TYPE_MISCLASSIFICATION`: **39**
- `SOURCE_SPAN_MISMATCH`: **0**
- `LANDMARK_SEMANTIC_IDENTITY_MISMATCH`: **0**

## Severity
- CRITICAL: **231**
- MAJOR: **60**
- MINOR: **0**

## Source sections
- Location: **178** defect records / **137** statements
- Notes: **108** defect records / **70** statements
- Remarks: **5** defect records / **3** statements

## Endpoint / conditional / composite metrics
- Reference-line endpoint cardinality defects: **13**
- Expanded endpoint-cardinality defects (line + intersection + simple junction + fraction-distance): **42**
- Conditional schema/binding defects: **9**
- Composite parent-binding defects: **54**
- Source landmark omissions: **17**
- Argument misbindings: **140**

## Dominant repeated construction failures
- `depression`: **106** defects; meridian families: BL, CV, GB, GV, HT, KI, LI, LR, LU, PC, SI, SP, ST, TE
- `composite_parent`: **54** defects; meridian families: BL, CV, GB, HT, KI, LI, LR, LU, PC, SI, SP, ST, TE
- `intersection`: **24** defects; meridian families: BL, GB, GV, HT, LI, LR, LU, PC, SI, SP, ST, TE
- `midpoint_of_entity`: **15**
- `between`: **15**
- `operator_operand`: **14**
- `line_construct`: **14**
- `conditional`: **9**

## Mandatory permanent regression targets
- **CV1**: 10 defects
- **CV12**: 4 defects
- **GB26**: 0 detected B semantic defects
- **ST35**: 2 defects, both relation argument misbinding
- **ST29**: 0 detected B semantic defects

## Construction-level decision
**Case C — systemic construction failure.**

### Recommendation: `FULL_B_REBUILD_REQUIRED`

This recommendation refers to the **B relation-graph construction pipeline**, not to discarding all frozen upstream work. WHO source records and frozen upstream semantic/identity layers remain authoritative inputs. Where the audit proves an upstream source-landmark omission or binding defect, only that evidence-backed upstream exception should be reopened. The rebuilt B must then be regenerated and re-audited against the 583-statement ledger before re-freeze.

The conclusion is driven by repeated independent families rather than CV1/CV12 alone: 106 depression argument misbindings across 14 meridian families, 54 composite-parent failures across 13, 24 intersection type/geometry failures across 12, plus repeated between, midpoint-of-entity, line, conditional and generic operator→operand binding failures.

## Gate state
- B v1 remains **temporarily unfrozen**.
- No B patch was executed.
- C v2 remains **stopped**.
- No new freeze is declared.
