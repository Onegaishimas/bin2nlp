# Master Software Developer Principles

**Focus:** quality, resiliency, defensive coding, and rigorous UAT & resolution.

## 1) Mindset & Ethics

* Own outcomes end-to-end: design → code → test → deploy → observe → fix.
* Optimize for safety and clarity before cleverness; readability is a feature.
* Prefer least surprise: predictable interfaces, explicit contracts, and stable behavior.
* Assume faults will happen; design so they don’t cascade.

## 2) Design & Architecture (resiliency first)

* Prefer simple, composable components; minimize implicit coupling.
* Make failure modes explicit: timeouts, retries with jitter, backoff, circuit breakers.
* Idempotency for writes; deduplication where events can repeat.
* Enforce input/output contracts with schema validation (at boundaries).
* Design for graceful degradation and feature flags/kill switches.
* Plan for concurrency: immutability where possible; lock scope minimal; avoid shared mutable state.

## 3) Defensive Coding Standards

* Validate all inputs (type, range, shape, encoding) at boundaries.
* Fail fast with actionable errors; never swallow or log-spam exceptions.
* Enforce null/undefined safety; prefer total functions where feasible.
* Wrap external calls with timeouts and circuit breakers; retry only safe operations.
* Avoid partial writes: transactions, two-phase commits, or compensating actions.
* Secure by default: principle of least privilege, safe defaults, escaped outputs.

## 4) Testing Strategy (shift left)

* Unit tests: behavior-driven, fast, deterministic; cover happy paths and edge cases.
* Property-based tests for invariants; fuzz testing for parsers and inputs.
* Integration tests for critical flows and service boundaries.
* Contract tests for APIs/queues to prevent breaking changes.
* Non-functional tests: performance baselines, load/soak, chaos drills for critical services.
* Mutation testing (where feasible) to harden assertions.
* Coverage: value-oriented; emphasize risk/complexity hotspots over raw %.

## 5) UAT (User Acceptance Testing) Discipline

* Define UAT scenarios from real user jobs-to-be-done and acceptance criteria.
* Prepare production-like data sets with edge conditions and privacy safeguards.
* Run UAT in an environment that mirrors production toggles and integrations.
* Capture UX, correctness, and performance feedback; triage findings to severity/SLO impact.
* Exit gates: all Sev-1/Sev-2 UAT defects resolved or explicitly waived by product owner.

## 6) Bug/Incident Resolution

* Reproduce → root cause (RC) → fix → test → prevent: each step documented.
* Add a regression test for every fix.
* Prefer systemic prevention (linters, type rules, CI checks) over one-off patches.
* Post-incident: update runbooks, dashboards, alerts, and guardrails.

## 7) Observability & Operations

* Structured, contextual logs; no PII secrets; trace IDs across services.
* Metrics: RED (Rate/Errors/Duration) and USE (Utilization/Saturation/Errors).
* SLOs with alerts tuned to user impact; no noisy alarms.
* Health/readiness endpoints reflect real dependency state.
* Dark-launch/feature flags; progressive delivery (canary, blue-green).

## 8) Security & Compliance (always-on)

* Threat model for critical changes; secure defaults; defense in depth.
* Secrets management (vaulted), signed artifacts, SBOM, dependency pinning and SCA.
* Input sanitization, output encoding, CSRF/CORS rules, authZ/authN enforced at boundaries.
* Audit trails for data-touching actions; GDPR/PII handling controls.

## 9) Performance & Efficiency

* Set explicit performance budgets and test against them.
* Choose data structures/algorithms based on measured complexity and usage.
* Control memory and connection pools; backpressure instead of buffer bloat.
* Cache with correctness (TTL, stampede protection, invalidation strategies).

## 10) Collaboration & Review

* Small, focused PRs with context, risks, and rollback plan.
* Reviews check for correctness, security, readability, and resiliency patterns.
* Document public contracts and failure modes; keep runbooks current.
* Communicate risks early; escalate when ambiguity blocks quality.

## 11) Definition of Done (DoD)

* ✅ All acceptance criteria met; feature flags in place.
* ✅ Unit/integration/contract tests added; regression test for new fixes.
* ✅ Security checks (SAST/SCA/secrets) and lint/type checks clean.
* ✅ Observability added (metrics, logs, traces, alerts).
* ✅ UAT passed per exit gates; rollback plan documented.
* ✅ Docs updated (README, runbook, API contracts, changelog).

## 12) Non-Negotiables (never ship with)

* Silent catch/ignore of exceptions.
* Network calls without timeouts.
* State-changing endpoints without idempotency/validation.
* Secrets in code/logs; unpinned high-risk dependencies.
* “Works on my machine” changes lacking CI verification.
