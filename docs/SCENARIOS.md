# Incident Scenarios & Target Fault Specifications

This document defines the five core incident investigation scenarios supported by Falsify, detailing expected symptoms, competing hypotheses, diagnostic signals, safety gate policies, and verified remediation paths.

---

## 1. Scenario: `bad_deploy`

- **Identifier**: `bad_deploy`
- **Title**: High HTTP 500 error spike on `/checkout` after release `v1.2.4`
- **Target Service**: `falsify-demo-payment`
- **Blast Radius**: Low / Medium
- **Failure Mechanism**: A regression in release `v1.2.4` introduces an unhandled `NullPointerException` during order checkout payload processing.
- **Diagnostic Signal**:
  - `get_deploy_history`: Shows release `v1.2.4` deployed within the last 5 minutes.
  - `get_logs`: Highlights recurring `NullPointerException at PaymentController.java:42`.
- **Competing Hypotheses**:
  1. Faulty release `v1.2.4` (Leading / Supported)
  2. Database connection pool exhaustion (Contradicted by normal DB stats)
  3. External network partition to payment gateway (Contradicted by healthy probe)
- **Safety Decision**: `auto` (High confidence >= 0.80, low blast radius).
- **Remediation Action**: `rollback_deploy(service_name="falsify-demo-payment", target_version="v1.2.3")`.
- **Verification**: `get_metrics` confirms error rate drops back to baseline `< 0.1%`.

---

## 2. Scenario: `db_pool_exhaustion`

- **Identifier**: `db_pool_exhaustion`
- **Title**: High HTTP 503 and latency degradation on checkout flow
- **Target Service**: `falsify-demo-payment` / `falsify-demo-db`
- **Blast Radius**: Medium
- **Failure Mechanism**: Database connection pool capacity is saturated due to connection handle leakage or high concurrent transactions.
- **Diagnostic Signal**:
  - `get_db_stats`: Active connections equal maximum capacity (`100/100`), with waiting threads `> 40`.
  - `get_logs`: Contains `ConnectionPoolTimeoutException: Pool exhausted`.
- **Competing Hypotheses**:
  1. Database connection pool exhaustion (Leading / Supported)
  2. Memory leak in payment service (Contradicted by nominal memory usage)
  3. Upstream gateway timeout (Contradicted by healthy gateway metrics)
- **Safety Decision**: `auto` (High confidence >= 0.80).
- **Remediation Action**: `restart_service(service_name="falsify-demo-payment")` or `scale_service`.
- **Verification**: `get_db_stats` verifies active connections drop to `12/100` and HTTP 503 errors cease.

---

## 3. Scenario: `slow_dependency`

- **Identifier**: `slow_dependency`
- **Title**: P99 latency degradation on gateway `/api/v1/orders`
- **Target Service**: `falsify-demo-inventory` / `falsify-demo-gateway`
- **Blast Radius**: Medium
- **Failure Mechanism**: Downstream inventory service experiences queue bottleneck and latency degradation (`> 2000ms`), cascading back to the gateway.
- **Diagnostic Signal**:
  - `probe_dependency`: Reports HTTP probe latency `2100ms` to `http://inventory-service:8080/health`.
  - `get_metrics`: P99 upstream latency exceeds threshold (`> 1500ms`).
- **Competing Hypotheses**:
  1. Downstream inventory service latency bottleneck (Leading / Supported)
  2. Gateway worker thread starvation (Contradicted by low CPU usage)
  3. Database table lock contention (Contradicted by zero lock waits)
- **Safety Decision**: `auto` / `approve` (Corroborated dependency latency).
- **Remediation Action**: `scale_service(service_name="falsify-demo-inventory", replicas=3)`.
- **Verification**: `probe_dependency` confirms latency drops to nominal `45ms`.

---

## 4. Scenario: `false_alarm`

- **Identifier**: `false_alarm`
- **Title**: Spike in metric alert: gateway error rate reported at 12%
- **Target Service**: `falsify-demo-gateway`
- **Blast Radius**: Low
- **Failure Mechanism**: A transient metric scraper artifact or brief synthetic test probe creates a short alert spike, but actual services are 100% healthy.
- **Diagnostic Signal**:
  - `get_logs`: Confirms 100% HTTP 200 OK responses with zero crash or error logs.
  - `get_metrics`: Current error rate is nominal (`0.01%`).
- **Competing Hypotheses**:
  1. Gateway container failure (Falsified by health logs)
  2. Synthetic test spike / monitoring artifact (Confirmed)
- **Safety Decision**: `escalate` / **NO ACTION**. Safety gate strictly blocks destructive remediations (no restarts or rollbacks).
- **Remediation Action**: None.
- **Verification**: Verified operating in nominal baseline state; incident dismissed safely.

---

## 5. Scenario: `ambiguous`

- **Identifier**: `ambiguous`
- **Title**: Intermittent 502 Bad Gateway and connection drops across multiple endpoints
- **Target Service**: Distributed Mesh (`falsify-demo-gateway`, `payment`, `db`)
- **Blast Radius**: High
- **Failure Mechanism**: Multiple weak and conflicting anomaly signals across DNS, network sockets, and database queries without definitive corroborating evidence.
- **Diagnostic Signal**:
  - `get_logs`: Single isolated DNS warning log (inconclusive).
  - `get_db_stats`: 2 socket read timeouts with nominal `45/100` connections (inconclusive).
- **Competing Hypotheses**:
  1. Service mesh DNS resolution failure (Inconclusive)
  2. Intermittent database socket drops (Inconclusive)
  3. TLS certificate expiration (Inconclusive)
- **Safety Decision**: `escalate`. Confidence (`0.45`) is below approval threshold (`0.60`) and blast radius is high.
- **Remediation Action**: None (Unsafe to act blindly).
- **Verification**: Incident safely escalated to human SRE with structured diagnostic dossier and memory snapshot.
