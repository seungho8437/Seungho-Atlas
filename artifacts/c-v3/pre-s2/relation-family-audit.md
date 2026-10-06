# C v3 — relation-family design audit

## 판정

**맞다.** 남은 unresolved를 줄이는 단위는 개별 혈자리가 아니라 **relation family × landmark family**다.

이 작업은 일부 혈자리에서 사용했던 "WHO 의미 → landmark realization → geometric operation → surface projection → QC" 절차를 혈자리별 수동 보정으로 반복하는 것이 아니다. 반복되는 의미 구조를 resolver로 일반화하고, 그 resolver가 같은 유형의 **모든 relation instance**를 만족하는지 검증한 뒤 361혈 전체 회귀검증을 수행하는 방식이다.

따라서 이것은 **C의 설계/구현 단계**다. B v2.1의 의미 그래프는 입력 계약이며, 여기서 B를 혈자리별로 다시 고치는 작업으로 돌아가면 안 된다.

## 현재 B v2.1 정적 재집계

- B v2.1 SHA-256: `8126e20938a478a2d214f4a8487cabeebc8f3115f7a81ad30e46b594958fb2c1`
- source statements: **583**
- landmark nodes: **2,524**
- geometry nodes: **107**
- relation instances: **1,993**
- relation types: **16**
- hard-unresolved terminal disposition을 argument로 포함하는 relation: **275**
- 그 relation들이 걸쳐 있는 logical acupoint: **147**
- `registry_limited` 또는 `specialized_anchor` dependency를 포함하는 relation: **575**

중요: 위 275/575는 **C runtime unresolved 개수와 같은 수치가 아니다.** 현재 relation graph를 어떤 resolver군으로 쪼개야 하는지 보기 위한 정적 dependency incidence다. 과거의 "약 320 unresolved"를 그대로 진실값으로 승계하지 않는다.

## relation type 분포

| relation type | count |
|---|---:|
| `surface-landmark` | 655 |
| `relative-to` | 542 |
| `reference-acupoint` | 268 |
| `same-level` | 117 |
| `on-line` | 113 |
| `between` | 106 |
| `center-of` | 63 |
| `midpoint-between` | 35 |
| `at-junction` | 34 |
| `fraction-along-line` | 23 |
| `midpoint-of-entity` | 21 |
| `overlies` | 9 |
| `superior-to` | 2 |
| `inferior-to` | 2 |
| `cross-reference` | 2 |
| `among` | 1 |

## 가장 큰 relation type × landmark class 군

| relation type | landmark class | incidence |
|---|---|---:|
| `reference-acupoint` | `acupoint_reference` | 268 |
| `surface-landmark` | `region.body_region` | 242 |
| `surface-landmark` | `fossa_or_depression` | 133 |
| `surface-landmark` | `surface.aspect` | 133 |
| `relative-to` | `acupoint_reference` | 90 |
| `relative-to` | `line.anatomical_line` | 86 |
| `relative-to` | `bone.process_or_prominence` | 74 |
| `on-line` | `line.anatomical_line` | 46 |
| `same-level` | `bone.bone` | 45 |
| `surface-landmark` | `line.anatomical_line` | 44 |
| `relative-to` | `orifice_or_cavity` | 40 |
| `center-of` | `orifice_or_cavity` | 40 |

## 구현/검증 계약

1. **구현 단위**는 혈자리 ID가 아니라 반복되는 relation family × landmark family다.
2. resolver 하나를 추가하면 그 유형의 **모든 instance**를 전수 재실행한다.
3. family-level 검사에는 semantic operand resolution, laterality, body-region restriction, constructed geometry, skin/surface projection, relation-satisfaction residual을 포함한다.
4. 그 뒤에만 361혈 전체 global QC를 수행한다.
5. 특정 혈자리만 맞추는 좌표 override는 금지한다. WHO source 자체가 point-specific exception을 요구할 때만 명시적 exception으로 허용하고 regression test를 붙인다.
6. 화면에서 그럴듯해 보이는 것은 validity가 아니다. **hard source constraint가 계산 가능하고 만족되어야** valid다.
7. C v1/v2 좌표는 audit reference로만 사용할 수 있고 solver input으로 재사용하지 않는다.

## 다음 resolver 순서

1. reference-point dependency
2. surface feature / body-region constraint
3. anatomical/reference-line construction
4. between / midpoint
5. entity center / midpoint-of-entity
6. junction / intersection
7. directional relative
8. same-level plane
9. deep-entity → skin projection
10. 남는 source-backed contextual exception class

이 순서로 unresolved를 줄여야 한다. 앞 단계가 뒤 단계의 operand가 되는 dependency chain이 많기 때문이다.

## 현재 C v3 gate와의 관계

현재 branch의 최신 G1 artifact는 body-frame/skin-region 산출까지 완료했지만 `G1 = AWAITING_HUMAN_REVIEW`, `S2_started = false` 상태다. 그러므로 이 audit는 **S2 구현 전 설계/coverage audit**로 추가하며, human G1 승인 없이 좌표 solver를 선행시키지 않는다.
