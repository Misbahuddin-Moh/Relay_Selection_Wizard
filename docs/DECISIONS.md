# Foundation decisions

| ID | Date | Decision and rationale | Revisit trigger |
|---|---|---|---|
| F01 | 2026-11-13 | Deploy to a separate staging branch/service. Existing production follows main and is older than current source. | Explicit production promotion after release gates. |
| F02 | 2026-11-13 | Public provider routes stay disabled, even if credentials are accidentally present. Manual entry and deterministic station checks remain available. | Authentication, object ownership, consent, concurrency/request/cost controls and their tests are implemented. |
| F03 | 2026-11-13 | Counts store value-bound origin/revision metadata. Missing or mismatched metadata becomes unknown origin. All facts remain unreviewed. | Full fact-history and reviewer model; never infer review from numeric presence. |
| F04 | 2026-11-13 | Rename confirmed_bay_cts to modeled_bay_cts; preserve measurement arithmetic in historical tests. | Versioned API migration when external consumers exist. |
| F05 | 2026-11-13 | Suppress hardware candidates outside three collector breakers or with a measured auxiliary tap. Retain modeled functions/quantities and specific scope reasons. | Independent worked examples and reviewed expanded policy. |
| F06 | 2026-11-13 | Every illustrative digital budget remains partial, including edited budgets with zero unresolved routes. It cannot grant complete fit or purchase readiness. | Reviewed per-category completeness, endpoint ownership, electrical classes and backend allocation. |
| F07 | 2026-11-13 | Retain historical catalog arithmetic tests at the low-level screening function; assert unsupported cases yield no public candidates. | Verified manufacturer records replace historical prototype examples. |
