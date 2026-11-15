# Protection approach comparison and accuracy boundary

## Visible workflow

After entering/importing a study and confirming analysis, step 2 now shows the
three reference approaches together. Select **Inspect approach** in a column to
see the chosen zone boundaries, hosting relay roles, provisional trip targets,
modeled phase-input envelope, design blockers and evidence still required.

Dedicated and shared hardware keep separate transformer and bus zones. Their
hardware hosting differs; they are not presented as different zone boundaries.
The combined approach uses one extended Primary zone with transformer-only
Secondary. The comparison is deterministic for this modeled station; it is not
an exhaustive search of every owner-approved protection philosophy.

The comparison remains visible before hardware screening. The signal and model
screens retain their separate used-point/capacity detail. Analog nominal capacity
is now displayed beside measurement applicability: an absent CT blocks that
application even if nominal channels fit; unknown measurements or independent
Secondary assignments remain unresolved.

## Readiness semantics

- `blocked`: an absent modeled measurement prevents a required path in the
  proposed design. Individual zones identify the absent measurement. A missing
  transformer LV bank blocks separate Primary and Secondary; combined Primary
  does not use that bank, but its transformer-only Secondary still needs it.
- `conditional`: the comparison still has unresolved engineering evidence. Even
  positive CT counts cannot establish suitable cores, independence or approval.
- `outside_scope`: retain a draft comparison but provide no reference hardware
  configuration. This includes non-three-breaker layouts, a measured auxiliary
  tap without a reviewed policy, and HV voltage not greater than collector voltage.

No state grants procurement readiness. The old measurement-only machine statuses
remain for existing clients; the new review gate explains the separate engineering
limitations. All voltage fields require actual finite positive numbers for
analysis; draft numeric zero remains a draft. Boolean/string/nonfinite voltage
requests fail validation. Invalid request responses do not echo source inputs.

## Explicit unresolved engineering work

Each approach retains the following review items rather than inferring a design:

- CT ratios, polarity, class, burden, saturation and actual terminal orientation.
- Primary/Secondary core, DC supply, trip-coil and wiring independence.
- Every credible source path, zone overlap/end-fault coverage and a cause-and-effect
  trip matrix. The reference trip list assumes possible collector backfeed and no
  LV main; it does not establish a proven clearing path.
- BF initiation, current detection, retrip, timing, escalation and remote isolation.
- Direct-trip/86 contact development, reset policy, output duty and independent trips.
- Overcurrent/distance coordination and actual inverter fault-response behavior.
- Transformer grounding, vector group and phase/neutral CT assignment for REF.
- Exact manufacturer model/function/firmware/module-slot compatibility.
- Complete project I/O including mechanical, supervision and control interfaces.
- Optional 87L peer, remote CT, communications, DTT disposition and remote clearing.

The comparison cannot replace project fault/coordination studies, utility/owner
requirements, manufacturer application confirmation or independent engineering
review. It does not calculate relay settings, complete order codes or an approved BOM.

## Research and project evidence

Existing curated research pointers are attached to relevant findings with their
locators. They provide context, not a verified project drawing number or acceptance.
Primary sources consulted during this slice include:

- [SEL/BODEC collector-substation protection paper (2024)](https://selinc.com/api/download/140376/)
- [SEL-487E manufacturer product/application information](https://selinc.com/products/487e/)

This check does not revalidate every inherited document or establish applicability
of any utility-specific requirement to another project. The UI identifies the
project material still required. No project document is sent to a provider.

## Identity and revision safeguards

Role purpose and equipment identity are semantic. Renaming a feeder to a reserved
label such as Transformer Secondary cannot reassign Secondary budgets or change
its UUID. Existing ordinary role IDs are preserved. The frontend resolves feeder
roles by equipment UUID and transformer roles by kind/purpose.

Preview responses belong to the current full study and request revision. Old
choices disappear immediately during recalculation; obsolete responses and failed
requests cannot restore an older comparison. Role selection is clamped when the
available role list changes. Inputs and partial decisions remain recoverable via
the existing portable-project/browser recovery mechanisms.

## Verification trace

| Requirement | Independent check |
|---|---|
| Three approaches, zone/hosting differences, missing/unknown CTs | tests/test_protection_comparison.py |
| Provisional trips, common gaps, remote-line limitations, unsupported scope | tests/test_protection_comparison.py |
| No role collisions from display labels, stable ordinary IDs | tests/test_role_collisions.py |
| Analog capacity distinguished from measurement applicability | tests/test_protection_comparison.py |
| Nonfinite/bool/string voltage rejection and no input echo | tests/test_protection_comparison.py |
| Visible comparison, selected details, scope/measurement messages, stale/retry behavior | scripts/protection-review-smoke.mjs |
| Earlier digital, analog, save/recovery and provider denial behavior | Existing backend/frontend suites and three earlier browser gates |

All four browser gates are required by scripts/verify.sh in CI before staging
promotion. Passing software tests verifies these modeled behaviors, not project
engineering acceptance. The original live app is not the feature release target.
