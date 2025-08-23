# Master Application Architect Principles

**Focus:** quality, resiliency, security, operability, and sustainable evolution across applications and platforms.

---

## 1) Mindset & Ethics for Architects

* Steward outcomes end-to-end: requirements → design → build → operate → evolve.
* Optimize for clarity and sustainability over cleverness; simplicity is a feature.
* Favor predictability and user trust: explicit contracts, stable APIs, clear boundaries.
* Assume failure is inevitable; design so failures are isolated and recoverable.
* Act as a bridge: translate business intent into safe, scalable, and operable systems.

---

## 2) Architecture Pillars & Targets

* **Reliability:** Define and honor SLOs; design for graceful degradation; manage error budgets.
* **Security & Privacy:** Default to least privilege, defense in depth, and privacy by design.
* **Performance & Scale:** Plan capacity, manage backpressure, and enforce performance budgets.
* **Operability & Observability:** Logs, metrics, traces, dashboards, and actionable alerts.
* **Cost & Efficiency:** Optimize for cost-per-unit of value; enforce cost SLOs.
* **Evolvability & Modularity:** Use clear contracts and modular boundaries to support change.
* **Interoperability & Data Quality:** Enforce schemas, lineage, and quality standards.

---

## 3) Core Principles

### AP-01: API-First, Contract-Driven

* All external interfaces are explicit, versioned, documented, and tested.
* Breaking changes require deprecation paths and contract tests.

### AP-02: Clean Domain Boundaries (DDD)

* Use ubiquitous language to define bounded contexts.
* Apply anti-corruption layers at integration points.

### AP-03: Fail-Well, Not Just Fail-Fast

* Enforce timeouts, retries with jitter, circuit breakers, and bulkheads.
* Provide graceful degradation and fallback strategies.

### AP-04: Idempotency & Consistency

* Design state-changing operations to be idempotent.
* Use outbox pattern, sagas, or transactions for distributed consistency.

### AP-05: Event-Driven Where It Fits

* Prefer asynchronous workflows to decouple systems.
* Use sagas for long-running, multi-service transactions.

### AP-06: Data as a Product

* Treat data domains as products with defined owners, contracts, and quality SLAs.
* Maintain lineage, catalog PII, and enforce retention policies.

### AP-07: Zero-Trust Runtime

* Services authenticate and authorize every request.
* Secrets managed in vaults with rotation; policies enforced at runtime.

### AP-08: Observability by Design

* Implement RED (Rate/Errors/Duration) and USE (Utilization/Saturation/Errors) metrics.
* Trace propagation across services; meaningful health endpoints.
* Alerts tied to user impact, not noise.

### AP-09: Progressive Delivery

* Use feature flags, canary releases, and blue-green deployments.
* Always maintain a proven rollback path.

### AP-10: Multi-Tenancy Strategy

* Choose explicit model (pooled, partitioned, dedicated).
* Enforce isolation, quotas, and noisy-neighbor controls.

### AP-11: Performance Budgets

* Define latency, throughput, and resource budgets.
* Enforce them with CI load/performance testing.
* Cache safely with TTL, invalidation strategies, and stampede protection.

### AP-12: Platform Leverage & Infrastructure as Code

* Prefer paved roads and golden paths.
* Everything version-controlled, reviewed, and reproducible.

### AP-13: Accessibility & UX Non-Functional Requirements

* Enforce accessibility standards (e.g., WCAG compliance).
* Incorporate usability budgets and acceptance criteria.

### AP-14: Compliance-Ready

* Embed audit trails, retention, and policy-as-code.
* Pipelines generate evidence artifacts for governance.

### AP-15: Decommissioning & Sunsets

* Every system has an exit plan.
* Data migration, retention, and contract tombstones are planned up front.

---

## 4) Anti-Patterns (Never Normalize)

* Distributed monoliths with hidden coupling.
* Shared mutable databases across bounded contexts.
* Unbounded fan-out or ungoverned pub/sub topics.
* Retrying non-idempotent operations.
* Secrets embedded in configs or code.
* Dashboards without SLOs or actionable alerts.

---

## 5) Reference Patterns

* **Modular Monolith vs. Microservices** – trade-offs documented.
* **Event-Driven Architectures** – pub/sub, outbox, saga.
* **API Gateway + Service Mesh** – separation of north-south vs east-west.
* **Multi-Tenant SaaS Models** – pooled, partitioned, dedicated.
* **Data Integration** – lakehouse, CDC, streaming ETL.
* **Progressive Delivery** – feature flags, canary, blue-green.

Each pattern includes: context, diagram, trade-offs, risks, and guardrails.

---

## 6) Adoption & Governance

* Architecture decisions captured as ADRs.
* Lightweight RFC process for significant changes.
* Architecture Review Board (ARB-lite) with clear SLAs.
* Exception/waiver process with time-boxed mitigations.
* Encourage *constructive challenge and scrutiny* as cultural norm.

---

## 7) Definition of Done (for a Solution)

* Contracts and schemas are versioned and tested.
* SLOs, SLAs, and error budgets defined.
* Threat model and runbooks completed.
* Load/performance and failover tests green.
* Observability baseline instrumented.
* Rollback plan proven in non-prod.
* ADRs recorded and merged.

---

## 8) Metrics & Continuous Review

* **Leading:** % services with contract tests; % endpoints with timeouts; % adoption of paved-road patterns.
* **Lagging:** Change failure rate, MTTR, error budget burn, cost/unit of value.
* **Cadence:** Monthly architecture health reviews; quarterly pattern refresh; post-incident architectural RCAs.
