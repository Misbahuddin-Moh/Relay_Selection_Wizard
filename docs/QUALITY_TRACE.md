# Foundation acceptance trace

| Plan requirement | Implementation | Evidence / test |
|---|---|---|
| Q01 Baseline | clean clone / staging branch | STATUS.md baseline SHAs; inherited 15 tests and frontend build |
| Q02 CT provenance | main.Study/CtProvenance, assessment.assess, model.ts and CT editor | test_quality_gates origin, mismatch, legacy and null/zero/positive cases; browser defaults workflow |
| Q04 Scope guards | assessment.assess, options.device_requirements/present_options | HTTP 1/2/4/12-breaker and measured auxiliary tests; empty public candidates; browser fourth-breaker flow |
| Q10 Partial budget | digitalBudget.ts / DigitalIO / PrimaryOrderDraft | frontend digital-budget tests and browser partial status/ordering gate |
| Q23 Reproducibility | assessment fingerprint | repeatability/key-order/edit tests; renamed study cache expectations |
| Q27 Paid endpoint protection | provider_guard deny-all alpha boundary | provider mocks untouched across actual HTTP requests with fake keys; disabled statuses |
| Q30 Honest UI | assessment panel, default/user origin labels, stale draft notice | browser workflow; independent planning-agent review |
| Q33 Deployment | health revision, verify/release scripts, CI, Docker test stages | tested commit and observed Render deploy; post-deploy smoke |

These rows cover implemented subsets only. They do not close entire Q families or imply complete engineering coverage. The three original test files retain prototype arithmetic and provider-format regression fixtures; generated catalog output is not an independent engineering oracle.
