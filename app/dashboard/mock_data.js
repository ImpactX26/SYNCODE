/**
 * Falsify Demo Scenarios & Timeline Fixtures
 * 5 Standard Scenarios matching docs/CONTRACTS.md event schema.
 */

const SCENARIOS = {
  bad_deploy: {
    id: "bad_deploy",
    name: "Scenario 1: Bad Deployment (Memory Leak)",
    badge: "RECOVERY VERIFIED",
    badgeType: "success",
    description: "Release v2.4.1 introduced an unclosed database connection leak causing memory exhaustion on payment-service.",
    service: "falsify-demo-payment",
    expectedOutcome: "Diagnose release regression, verify with deploy history & metrics, auto-rollback to v2.4.0, verify recovery.",
    timeline: [
      {
        step: 1,
        phase: "observe",
        phaseName: "1. Incident Detection",
        type: "incident_opened",
        ts: 1728390001.100,
        payload: {
          title: "Memory leak & latency spike on /checkout endpoint",
          problem_area: "payment-service",
          blast_radius: "low",
          summary: "Alert triggered: payment-service container memory RSS > 92% and p99 latency elevated to 2400ms.",
          is_real_incident: true,
          severity: "HIGH"
        },
        stateUpdate: {
          title: "Memory leak & latency spike on /checkout endpoint",
          blast_radius: "low",
          confidence: 0.15,
          decision: "pending",
          status: "investigating"
        }
      },
      {
        step: 2,
        phase: "hypothesize",
        phaseName: "2. Competing Hypotheses",
        type: "hypotheses_proposed",
        ts: 1728390001.800,
        payload: {
          count: 3,
          hypotheses: [
            {
              id: "hyp_01",
              claim: "Faulty deployment v2.4.1 introduced resource leak in connection handler",
              prediction: "Deploy history shows release v2.4.1 deployed within the last 15 minutes",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_02",
              claim: "Sudden incoming traffic flood from marketing campaign",
              prediction: "Traffic metrics show request rate > 5000 RPS on gateway",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_03",
              claim: "Underlying container host memory degradation",
              prediction: "Host swap utilization > 80% across all co-located containers",
              status: "alive",
              evidence: []
            }
          ],
          confidence: 0.20
        },
        stateUpdate: {
          confidence: 0.20,
          hypotheses: [
            {
              id: "hyp_01",
              claim: "Faulty deployment v2.4.1 introduced resource leak in connection handler",
              prediction: "Deploy history shows release v2.4.1 deployed within the last 15 minutes",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_02",
              claim: "Sudden incoming traffic flood from marketing campaign",
              prediction: "Traffic metrics show request rate > 5000 RPS on gateway",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_03",
              claim: "Underlying container host memory degradation",
              prediction: "Host swap utilization > 80% across all co-located containers",
              status: "alive",
              evidence: []
            }
          ]
        }
      },
      {
        step: 3,
        phase: "experiment",
        phaseName: "3. Experiment Execution",
        type: "tool_called",
        ts: 1728390002.400,
        payload: {
          tool: "get_deploy_history",
          ok: true,
          latency_ms: 18.4,
          source: "deploy_stub",
          parameters: { service_name: "falsify-demo-payment", limit: 3 },
          data: {
            service: "falsify-demo-payment",
            deployments: [
              { version: "v2.4.1", deployed_at: "12 mins ago", author: "ci-bot", status: "active" },
              { version: "v2.4.0", deployed_at: "3 days ago", author: "release-team", status: "stable" }
            ]
          }
        }
      },
      {
        step: 4,
        phase: "experiment",
        phaseName: "3. Evidence Classification",
        type: "hypothesis_updated",
        ts: 1728390002.900,
        payload: {
          hypothesis_id: "hyp_01",
          claim: "Faulty deployment v2.4.1 introduced resource leak in connection handler",
          status: "alive",
          evidence_id: "ev_01",
          classification: "supports",
          finding: "Release v2.4.1 was deployed 12 minutes ago, matching the exact onset timestamp of memory growth.",
          confidence_after: 0.60
        },
        stateUpdate: {
          confidence: 0.60,
          hypothesesIndex: {
            hyp_01: {
              status: "alive",
              evidence: [
                {
                  id: "ev_01",
                  source: "get_deploy_history",
                  classification: "supports",
                  finding: "Release v2.4.1 deployed 12 mins ago correlates with incident onset."
                }
              ]
            }
          }
        }
      },
      {
        step: 5,
        phase: "experiment",
        phaseName: "3. Falsification Test",
        type: "tool_called",
        ts: 1728390003.300,
        payload: {
          tool: "get_metrics",
          ok: true,
          latency_ms: 22.1,
          source: "metrics_stub",
          parameters: { service_name: "falsify-demo-gateway", metric_name: "request_rate" },
          data: {
            service: "falsify-demo-gateway",
            metric: "request_rate",
            current_value: "135 rps",
            baseline: "140 rps"
          }
        }
      },
      {
        step: 6,
        phase: "experiment",
        phaseName: "3. Rival Hypothesis Falsified",
        type: "hypothesis_updated",
        ts: 1728390003.800,
        payload: {
          hypothesis_id: "hyp_02",
          claim: "Sudden incoming traffic flood from marketing campaign",
          status: "falsified",
          evidence_id: "ev_02",
          classification: "contradicts",
          finding: "Gateway request rate is steady at 135 RPS (baseline 140 RPS). Rival traffic hypothesis falsified.",
          confidence_after: 0.75
        },
        stateUpdate: {
          confidence: 0.75,
          hypothesesIndex: {
            hyp_02: {
              status: "falsified",
              evidence: [
                {
                  id: "ev_02",
                  source: "get_metrics",
                  classification: "contradicts",
                  finding: "Request rate 135 RPS is normal; contradicts traffic flood."
                }
              ]
            }
          }
        }
      },
      {
        step: 7,
        phase: "skeptic",
        phaseName: "4. Skeptic Challenge",
        type: "skeptic_note",
        ts: 1728390004.200,
        payload: {
          critique: "Hypothesis 1 is corroborated by deployment timestamps and memory slope. Rival traffic spike is falsified. Independent metrics and deploy logs align. Validated for auto-remediation.",
          challenged: false,
          suggested_status: "alive",
          confidence_after: 0.88
        },
        stateUpdate: {
          confidence: 0.88
        }
      },
      {
        step: 8,
        phase: "gate",
        phaseName: "5. Safety Decision Gate",
        type: "decision_made",
        ts: 1728390004.600,
        payload: {
          decision: "auto",
          confidence: 0.88,
          blast_radius: "low",
          reason: "Confidence 0.88 >= 0.80 auto threshold. Low blast radius. Allow-listed action 'rollback_deploy' approved for demo container."
        },
        stateUpdate: {
          decision: "auto"
        }
      },
      {
        step: 9,
        phase: "action",
        phaseName: "6. Remediation Action",
        type: "action_taken",
        ts: 1728390005.100,
        payload: {
          action: "rollback_deploy",
          ok: true,
          parameters: { service_name: "falsify-demo-payment", target_version: "v2.4.0" },
          latency_ms: 180.5,
          result: { service: "falsify-demo-payment", action: "rollback", status: "completed", target_version: "v2.4.0" }
        },
        stateUpdate: {
          actions_taken: [
            {
              action: "rollback_deploy",
              target: "falsify-demo-payment",
              target_version: "v2.4.0",
              status: "completed"
            }
          ]
        }
      },
      {
        step: 10,
        phase: "verify",
        phaseName: "7. Recovery Verification",
        type: "recovery_checked",
        ts: 1728390005.800,
        payload: {
          recovered: true,
          finding: "Probe to /health returned HTTP 200 in 6ms. Memory RSS stabilized from 94% down to 32%. No packet drops.",
          action: "rollback_deploy"
        },
        stateUpdate: {
          status: "resolved"
        }
      },
      {
        step: 11,
        phase: "complete",
        phaseName: "8. Incident Closed",
        type: "incident_closed",
        ts: 1728390006.100,
        payload: {
          status: "resolved",
          resolution: "Rollback to v2.4.0 successful. Memory leak cleared.",
          actions_count: 1,
          total_investigation_time_sec: 4.9
        }
      }
    ]
  },

  db_pool_exhaustion: {
    id: "db_pool_exhaustion",
    name: "Scenario 2: Database Pool Exhaustion",
    badge: "RECOVERY VERIFIED",
    badgeType: "success",
    description: "Database connection pool saturated (100/100 connections) causing cascading HTTP 500 errors across payment services.",
    service: "falsify-demo-db",
    expectedOutcome: "Diagnose pool saturation, verify via get_db_stats & logs, auto-restart database container, verify active connections normalized.",
    timeline: [
      {
        step: 1,
        phase: "observe",
        phaseName: "1. Incident Detection",
        type: "incident_opened",
        ts: 1728390100.100,
        payload: {
          title: "HTTP 500 error spike (42%) and database connection acquisition timeout",
          problem_area: "database-cluster",
          blast_radius: "medium",
          summary: "Alert: ConnectionTimeoutException on falsify-demo-db. 148 requests failed in last 60s.",
          is_real_incident: true,
          severity: "CRITICAL"
        },
        stateUpdate: {
          title: "HTTP 500 error spike & DB connection timeout",
          blast_radius: "medium",
          confidence: 0.10,
          decision: "pending",
          status: "investigating"
        }
      },
      {
        step: 2,
        phase: "hypothesize",
        phaseName: "2. Competing Hypotheses",
        type: "hypotheses_proposed",
        ts: 1728390100.800,
        payload: {
          count: 3,
          hypotheses: [
            {
              id: "hyp_01",
              claim: "Database connection pool exhausted due to leaked client sessions",
              prediction: "get_db_stats shows active_connections == max_connections (100/100)",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_02",
              claim: "Database container crash / port 5432 unreachable",
              prediction: "Network probe to database healthcheck fails with ConnectionRefused",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_03",
              claim: "Table deadlock locking write transactions",
              prediction: "Deadlock count > 0 in database diagnostics",
              status: "alive",
              evidence: []
            }
          ],
          confidence: 0.20
        },
        stateUpdate: {
          confidence: 0.20
        }
      },
      {
        step: 3,
        phase: "experiment",
        phaseName: "3. Diagnostic Probe",
        type: "tool_called",
        ts: 1728390101.400,
        payload: {
          tool: "get_db_stats",
          ok: true,
          latency_ms: 12.0,
          source: "db_stub",
          parameters: { db_identifier: "falsify-demo-db" },
          data: {
            db_identifier: "falsify-demo-db",
            active_connections: 100,
            max_connections: 100,
            waiting_threads: 52,
            deadlocks: 0
          }
        }
      },
      {
        step: 4,
        phase: "experiment",
        phaseName: "3. Evidence Classification",
        type: "hypothesis_updated",
        ts: 1728390101.900,
        payload: {
          hypothesis_id: "hyp_01",
          claim: "Database connection pool exhausted",
          status: "alive",
          evidence_id: "ev_01",
          classification: "supports",
          finding: "active_connections is at 100% capacity (100/100) with 52 threads blocked waiting for connection.",
          confidence_after: 0.65
        },
        stateUpdate: {
          confidence: 0.65
        }
      },
      {
        step: 5,
        phase: "experiment",
        phaseName: "3. Falsifying Deadlock Hypothesis",
        type: "hypothesis_updated",
        ts: 1728390102.300,
        payload: {
          hypothesis_id: "hyp_03",
          claim: "Table deadlock locking write transactions",
          status: "falsified",
          evidence_id: "ev_02",
          classification: "contradicts",
          finding: "Deadlocks metric is 0; deadlocks hypothesis is falsified.",
          confidence_after: 0.78
        },
        stateUpdate: {
          confidence: 0.78
        }
      },
      {
        step: 6,
        phase: "skeptic",
        phaseName: "4. Skeptic Challenge",
        type: "skeptic_note",
        ts: 1728390102.700,
        payload: {
          critique: "Pool capacity is 100% saturated. Deadlock hypothesis falsified. Restarting the demo database resets connection pool cleanly.",
          challenged: false,
          suggested_status: "alive",
          confidence_after: 0.86
        },
        stateUpdate: {
          confidence: 0.86
        }
      },
      {
        step: 7,
        phase: "gate",
        phaseName: "5. Safety Decision Gate",
        type: "decision_made",
        ts: 1728390103.100,
        payload: {
          decision: "auto",
          confidence: 0.86,
          blast_radius: "medium",
          reason: "Confidence 0.86 >= 0.80 auto threshold. Allow-listed action 'restart_service' approved for demo container."
        },
        stateUpdate: {
          decision: "auto"
        }
      },
      {
        step: 8,
        phase: "action",
        phaseName: "6. Remediation Action",
        type: "action_taken",
        ts: 1728390103.600,
        payload: {
          action: "restart_service",
          ok: true,
          parameters: { service_name: "falsify-demo-db" },
          latency_ms: 320.0,
          result: { service: "falsify-demo-db", action: "restart", status: "completed" }
        },
        stateUpdate: {
          actions_taken: [{ action: "restart_service", target: "falsify-demo-db", status: "completed" }]
        }
      },
      {
        step: 9,
        phase: "verify",
        phaseName: "7. Recovery Verification",
        type: "recovery_checked",
        ts: 1728390104.200,
        payload: {
          recovered: true,
          finding: "get_db_stats confirmed active_connections dropped from 100 to 4. Waiting threads = 0. Error rate = 0%.",
          action: "restart_service"
        },
        stateUpdate: {
          status: "resolved"
        }
      },
      {
        step: 10,
        phase: "complete",
        phaseName: "8. Incident Closed",
        type: "incident_closed",
        ts: 1728390104.500,
        payload: {
          status: "resolved",
          resolution: "Database restarted. Connection pool refreshed and stabilized.",
          actions_count: 1,
          total_investigation_time_sec: 4.4
        }
      }
    ]
  },

  slow_dependency: {
    id: "slow_dependency",
    name: "Scenario 3: Slow External Dependency",
    badge: "RECOVERY VERIFIED",
    badgeType: "success",
    description: "Upstream third-party payment gateway latency spike causing worker thread pool starvation on orders service.",
    service: "falsify-demo-orders",
    expectedOutcome: "Diagnose upstream latency, verify via probe & metrics, auto-scale worker replicas to prevent thread starvation, verify throughput.",
    timeline: [
      {
        step: 1,
        phase: "observe",
        phaseName: "1. Incident Detection",
        type: "incident_opened",
        ts: 1728390200.100,
        payload: {
          title: "Order processing latency degraded (p99 > 4200ms)",
          problem_area: "order-pipeline",
          blast_radius: "medium",
          summary: "Alert: orders service response time breached SLA threshold (> 2000ms).",
          is_real_incident: true,
          severity: "MEDIUM"
        },
        stateUpdate: {
          title: "Order processing latency degraded (p99 > 4200ms)",
          blast_radius: "medium",
          confidence: 0.15,
          decision: "pending",
          status: "investigating"
        }
      },
      {
        step: 2,
        phase: "hypothesize",
        phaseName: "2. Competing Hypotheses",
        type: "hypotheses_proposed",
        ts: 1728390200.700,
        payload: {
          count: 3,
          hypotheses: [
            {
              id: "hyp_01",
              claim: "External payment gateway latency degradation causing worker backpressure",
              prediction: "Network probe to external gateway endpoint reports latency > 4000ms",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_02",
              claim: "CPU saturation on order-service container",
              prediction: "CPU usage metric > 90% on order worker",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_03",
              claim: "Disk I/O lock on audit logs volume",
              prediction: "I/O write latency > 500ms",
              status: "alive",
              evidence: []
            }
          ],
          confidence: 0.20
        },
        stateUpdate: {
          confidence: 0.20
        }
      },
      {
        step: 3,
        phase: "experiment",
        phaseName: "3. Dependency Probe",
        type: "tool_called",
        ts: 1728390201.300,
        payload: {
          tool: "probe_dependency",
          ok: true,
          latency_ms: 4120.0,
          source: "network_stub",
          parameters: { target_url: "http://localhost:8000/gateway/probe", timeout_sec: 5.0 },
          data: { target_url: "http://localhost:8000/gateway/probe", latency_ms: 4120, status_code: 504 }
        }
      },
      {
        step: 4,
        phase: "experiment",
        phaseName: "3. Evidence Classification",
        type: "hypothesis_updated",
        ts: 1728390201.800,
        payload: {
          hypothesis_id: "hyp_01",
          claim: "External payment gateway latency degradation",
          status: "alive",
          evidence_id: "ev_01",
          classification: "supports",
          finding: "External gateway probe returned 4120ms latency and 504 Gateway Timeout.",
          confidence_after: 0.70
        },
        stateUpdate: {
          confidence: 0.70
        }
      },
      {
        step: 5,
        phase: "experiment",
        phaseName: "3. CPU Falsification Probe",
        type: "tool_called",
        ts: 1728390202.200,
        payload: {
          tool: "get_metrics",
          ok: true,
          latency_ms: 15.0,
          source: "metrics_stub",
          parameters: { service_name: "falsify-demo-orders", metric_name: "cpu_percent" },
          data: { service: "falsify-demo-orders", metric: "cpu_percent", current_value: "14%" }
        }
      },
      {
        step: 6,
        phase: "experiment",
        phaseName: "3. CPU Hypothesis Falsified",
        type: "hypothesis_updated",
        ts: 1728390202.600,
        payload: {
          hypothesis_id: "hyp_02",
          claim: "CPU saturation on order-service container",
          status: "falsified",
          evidence_id: "ev_02",
          classification: "contradicts",
          finding: "CPU usage is 14% (normal). CPU saturation hypothesis falsified.",
          confidence_after: 0.82
        },
        stateUpdate: {
          confidence: 0.82
        }
      },
      {
        step: 7,
        phase: "skeptic",
        phaseName: "4. Skeptic Review",
        type: "skeptic_note",
        ts: 1728390203.000,
        payload: {
          critique: "Root cause is upstream external gateway latency. Scaling order worker replicas provides concurrent thread headroom to maintain order throughput.",
          challenged: false,
          suggested_status: "alive",
          confidence_after: 0.85
        },
        stateUpdate: {
          confidence: 0.85
        }
      },
      {
        step: 8,
        phase: "gate",
        phaseName: "5. Safety Decision Gate",
        type: "decision_made",
        ts: 1728390203.400,
        payload: {
          decision: "auto",
          confidence: 0.85,
          blast_radius: "medium",
          reason: "Confidence 0.85 >= 0.80. Allow-listed action 'scale_service' approved for demo container."
        },
        stateUpdate: {
          decision: "auto"
        }
      },
      {
        step: 9,
        phase: "action",
        phaseName: "6. Remediation Action",
        type: "action_taken",
        ts: 1728390203.900,
        payload: {
          action: "scale_service",
          ok: true,
          parameters: { service_name: "falsify-demo-orders", replicas: 3 },
          latency_ms: 140.0,
          result: { service: "falsify-demo-orders", action: "scale", replicas: 3 }
        },
        stateUpdate: {
          actions_taken: [{ action: "scale_service", target: "falsify-demo-orders", replicas: 3 }]
        }
      },
      {
        step: 10,
        phase: "verify",
        phaseName: "7. Recovery Verification",
        type: "recovery_checked",
        ts: 1728390204.500,
        payload: {
          recovered: true,
          finding: "Order queue depth normalized. 3 replica workers processing requests concurrently without thread saturation.",
          action: "scale_service"
        },
        stateUpdate: {
          status: "resolved"
        }
      },
      {
        step: 11,
        phase: "complete",
        phaseName: "8. Incident Closed",
        type: "incident_closed",
        ts: 1728390204.800,
        payload: {
          status: "resolved",
          resolution: "Service scaled to 3 replicas. Throughput restored.",
          actions_count: 1,
          total_investigation_time_sec: 4.7
        }
      }
    ]
  },

  false_alarm: {
    id: "false_alarm",
    name: "Scenario 4: False Alarm (Routine Backup)",
    badge: "NO ACTION TAKEN",
    badgeType: "warning",
    description: "Single transient latency spike during scheduled nightly database backup cron. Falsify tests and confirms NO action required.",
    service: "falsify-demo-gateway",
    expectedOutcome: "Detect anomaly, hypothesize failure vs false alarm, probe telemetry, falsify failure claims, Safety Gate enforces NO ACTION.",
    timeline: [
      {
        step: 1,
        phase: "observe",
        phaseName: "1. Incident Detection",
        type: "incident_opened",
        ts: 1728390300.100,
        payload: {
          title: "Single probe timeout alert on gateway during scheduled maintenance window",
          problem_area: "gateway",
          blast_radius: "low",
          summary: "Alert: 1 synthetic probe timed out at 03:00:05 AM. Investigating whether this is a real failure or routine artifact.",
          is_real_incident: false,
          severity: "LOW"
        },
        stateUpdate: {
          title: "Single probe timeout alert on gateway (03:00 AM)",
          blast_radius: "low",
          confidence: 0.10,
          decision: "pending",
          status: "investigating"
        }
      },
      {
        step: 2,
        phase: "hypothesize",
        phaseName: "2. Competing Hypotheses",
        type: "hypotheses_proposed",
        ts: 1728390300.700,
        payload: {
          count: 2,
          hypotheses: [
            {
              id: "hyp_01",
              claim: "Real service degradation and gateway process hang",
              prediction: "Recent error logs show 502/504 errors and crash traces",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_02",
              claim: "False alarm / transient artifact from scheduled backup cron",
              prediction: "Recent logs show cron job execution with 0 error lines; subsequent health check returns 200 OK",
              status: "alive",
              evidence: []
            }
          ],
          confidence: 0.20
        },
        stateUpdate: {
          confidence: 0.20
        }
      },
      {
        step: 3,
        phase: "experiment",
        phaseName: "3. Log Audit Experiment",
        type: "tool_called",
        ts: 1728390301.200,
        payload: {
          tool: "get_logs",
          ok: true,
          latency_ms: 14.0,
          source: "logs_stub",
          parameters: { service_name: "falsify-demo-gateway", lines: 50 },
          data: {
            service: "falsify-demo-gateway",
            lines: [
              "03:00:00 [CRON] Starting scheduled snapshot backup",
              "03:00:04 [CRON] Snapshot snapshot_20261008 completed (4.2s)",
              "03:00:06 [HTTP] GET /health 200 OK - 2ms"
            ]
          }
        }
      },
      {
        step: 4,
        phase: "experiment",
        phaseName: "3. Falsifying Degradation Hypothesis",
        type: "hypothesis_updated",
        ts: 1728390301.700,
        payload: {
          hypothesis_id: "hyp_01",
          claim: "Real service degradation and gateway process hang",
          status: "falsified",
          evidence_id: "ev_01",
          classification: "contradicts",
          finding: "Log audit showed 0 errors. Single spike was routine snapshot cron (4.2s). Degradation claim falsified.",
          confidence_after: 0.10
        },
        stateUpdate: {
          confidence: 0.00
        }
      },
      {
        step: 5,
        phase: "skeptic",
        phaseName: "4. Skeptic Intervention",
        type: "skeptic_note",
        ts: 1728390302.100,
        payload: {
          critique: "FALSE ALARM CONFIRMED: Gateway logs and healthchecks confirm service is 100% operational. Zero degradation. DO NOT RESTART OR ROLLBACK.",
          challenged: true,
          suggested_status: "falsified",
          confidence_after: 0.00
        },
        stateUpdate: {
          confidence: 0.00
        }
      },
      {
        step: 6,
        phase: "gate",
        phaseName: "5. Safety Decision Gate (NO ACTION)",
        type: "decision_made",
        ts: 1728390302.500,
        payload: {
          decision: "escalate",
          confidence: 0.00,
          blast_radius: "low",
          reason: "FALSE ALARM DETECTED: Zero failure evidence. Safety gate strictly enforces NO REMEDIATION ACTION."
        },
        stateUpdate: {
          decision: "escalate"
        }
      },
      {
        step: 7,
        phase: "verify",
        phaseName: "7. Baseline Verification",
        type: "recovery_checked",
        ts: 1728390302.900,
        payload: {
          recovered: true,
          finding: "Cluster verified operating in nominal baseline state. No destructive remediation was performed.",
          action: "none"
        },
        stateUpdate: {
          status: "dismissed_false_alarm"
        }
      },
      {
        step: 8,
        phase: "complete",
        phaseName: "8. Incident Closed",
        type: "incident_closed",
        ts: 1728390303.200,
        payload: {
          status: "resolved",
          resolution: "False alarm identified & safely dismissed. Zero unnecessary restarts performed.",
          actions_count: 0,
          total_investigation_time_sec: 3.1
        }
      }
    ]
  },

  ambiguous: {
    id: "ambiguous",
    name: "Scenario 5: Ambiguous / Inconclusive Diagnosis",
    badge: "SAFE ESCALATION",
    badgeType: "danger",
    description: "Conflicting multi-signal alerts across network and database with inconclusive evidence. Falsify safely ESCALATES without blind guesswork.",
    service: "multiple (gateway / payment / db)",
    expectedOutcome: "Detect competing unresolved root causes, identify weak inconclusive signals, Safety Gate detects ambiguity & escalates to human SRE.",
    timeline: [
      {
        step: 1,
        phase: "observe",
        phaseName: "1. Incident Detection",
        type: "incident_opened",
        ts: 1728390400.100,
        payload: {
          title: "Intermittent 502 Bad Gateway and connection drops across multiple endpoints",
          problem_area: "distributed-mesh",
          blast_radius: "high",
          summary: "Alert: Distributed failure symptoms across gateway, payment, and database.",
          is_real_incident: true,
          severity: "HIGH"
        },
        stateUpdate: {
          title: "Intermittent 502 Bad Gateway across multiple services",
          blast_radius: "high",
          confidence: 0.10,
          decision: "pending",
          status: "investigating"
        }
      },
      {
        step: 2,
        phase: "hypothesize",
        phaseName: "2. Competing Hypotheses",
        type: "hypotheses_proposed",
        ts: 1728390400.700,
        payload: {
          count: 3,
          hypotheses: [
            {
              id: "hyp_01",
              claim: "Service mesh DNS resolution failure",
              prediction: "Gateway logs show DNS timeout errors",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_02",
              claim: "Intermittent database socket drops",
              prediction: "Database stats show socket EOF errors",
              status: "alive",
              evidence: []
            },
            {
              id: "hyp_03",
              claim: "TLS certificate expiration on internal ingress proxy",
              prediction: "SSL handshake error in probe",
              status: "alive",
              evidence: []
            }
          ],
          confidence: 0.20
        },
        stateUpdate: {
          confidence: 0.20
        }
      },
      {
        step: 3,
        phase: "experiment",
        phaseName: "3. DNS Diagnostic Probe",
        type: "tool_called",
        ts: 1728390401.300,
        payload: {
          tool: "get_logs",
          ok: true,
          latency_ms: 18.0,
          source: "logs_stub",
          parameters: { service_name: "falsify-demo-gateway", pattern: "DNS" },
          data: {
            service: "falsify-demo-gateway",
            lines: ["04:12:01 [WARN] DNS lookup payment.internal took 42ms (weak anomaly)"]
          }
        }
      },
      {
        step: 4,
        phase: "experiment",
        phaseName: "3. Weak Evidence Recorded",
        type: "hypothesis_updated",
        ts: 1728390401.800,
        payload: {
          hypothesis_id: "hyp_01",
          claim: "Service mesh DNS resolution failure",
          status: "alive",
          evidence_id: "ev_01",
          classification: "inconclusive",
          finding: "Single DNS warning line observed; insufficient to conclude mesh DNS outage.",
          confidence_after: 0.40
        },
        stateUpdate: {
          confidence: 0.40
        }
      },
      {
        step: 5,
        phase: "experiment",
        phaseName: "3. DB Socket Diagnostic",
        type: "tool_called",
        ts: 1728390402.200,
        payload: {
          tool: "get_db_stats",
          ok: true,
          latency_ms: 22.0,
          source: "db_stub",
          parameters: { db_identifier: "falsify-demo-db" },
          data: { active_connections: 45, max_connections: 100, warnings: "socket_read_timeout_count: 2" }
        }
      },
      {
        step: 6,
        phase: "experiment",
        phaseName: "3. Inconclusive DB Evidence",
        type: "hypothesis_updated",
        ts: 1728390402.700,
        payload: {
          hypothesis_id: "hyp_02",
          claim: "Intermittent database socket drops",
          status: "alive",
          evidence_id: "ev_02",
          classification: "inconclusive",
          finding: "2 socket timeouts observed; connections normal at 45/100. Inconclusive signal.",
          confidence_after: 0.45
        },
        stateUpdate: {
          confidence: 0.45
        }
      },
      {
        step: 7,
        phase: "skeptic",
        phaseName: "4. Skeptic Critical Warning",
        type: "skeptic_note",
        ts: 1728390403.100,
        payload: {
          critique: "HIGH RISK AMBIGUITY: Multiple competing hypotheses (DNS vs DB Socket) have weak, inconclusive signals. No hypothesis is definitively proven or falsified. Blind remediation could worsen cluster stability.",
          challenged: true,
          suggested_status: "uncertain",
          confidence_after: 0.45
        },
        stateUpdate: {
          confidence: 0.45
        }
      },
      {
        step: 8,
        phase: "gate",
        phaseName: "5. Safety Decision Gate (ESCALATE)",
        type: "decision_made",
        ts: 1728390403.600,
        payload: {
          decision: "escalate",
          confidence: 0.45,
          blast_radius: "high",
          reason: "AMBIGUITY DETECTED: Confidence 0.45 < 0.60 approval threshold. High blast radius. Unsafe to act automatically. Escalating to human SRE."
        },
        stateUpdate: {
          decision: "escalate"
        }
      },
      {
        step: 9,
        phase: "complete",
        phaseName: "8. Human SRE Escalation Dossier",
        type: "incident_closed",
        ts: 1728390404.000,
        payload: {
          status: "escalated",
          resolution: "Escalated to On-Call Human SRE. Full diagnostic dossier, competing hypotheses, and inconclusive logs preserved in SQLite memory.",
          actions_count: 0,
          total_investigation_time_sec: 3.9
        }
      }
    ]
  }
};
