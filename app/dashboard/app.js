/**
 * Falsify Live Incident Dashboard Controller
 * Connects to live WebSocket (/ws/events) or provides smooth interactive simulation replay.
 */

class DashboardController {
  constructor() {
    this.currentScenarioKey = "bad_deploy";
    this.currentStepIndex = -1;
    this.isPlaying = false;
    this.playInterval = null;
    this.playbackSpeedMs = 1200; // 1.2s per step in normal speed
    this.isLiveMode = false;
    this.ws = null;

    this.state = {
      incident_id: "inc_sim_001",
      title: "Select a scenario to begin investigation",
      status: "idle",
      blast_radius: "unknown",
      confidence: 0.0,
      decision: "pending",
      hypotheses: [],
      actions_taken: [],
      events: []
    };

    this.initDOM();
    this.bindEvents();
    this.loadScenario("bad_deploy");
  }

  initDOM() {
    this.dom = {
      scenarioSelect: document.getElementById("scenario-select"),
      btnPlay: document.getElementById("btn-play"),
      btnStep: document.getElementById("btn-step"),
      btnReset: document.getElementById("btn-reset"),
      speedSelect: document.getElementById("speed-select"),
      wsToggleBtn: document.getElementById("btn-ws-toggle"),
      liveStatusBadge: document.getElementById("live-status-badge"),
      connectionStatus: document.getElementById("connection-status"),

      // Pipeline Steps
      stepNodes: document.querySelectorAll(".stepper-item"),

      // Incident Details
      incidentTitle: document.getElementById("incident-title"),
      incidentStatusBadge: document.getElementById("incident-status-badge"),
      serviceName: document.getElementById("meta-service"),
      blastRadius: document.getElementById("meta-blast-radius"),
      scenarioDesc: document.getElementById("scenario-desc"),
      expectedOutcome: document.getElementById("expected-outcome"),

      // Confidence
      confidenceValue: document.getElementById("confidence-value"),
      confidenceBarFill: document.getElementById("confidence-bar-fill"),

      // Hypotheses
      hypothesesList: document.getElementById("hypotheses-list"),

      // Diagnostics & Skeptic
      diagnosticsContainer: document.getElementById("diagnostics-container"),
      skepticCard: document.getElementById("skeptic-card"),
      skepticCritique: document.getElementById("skeptic-critique"),

      // Gate & Action
      gateStatusPill: document.getElementById("gate-status-pill"),
      gateReason: document.getElementById("gate-reason"),
      actionCard: document.getElementById("action-card"),
      actionName: document.getElementById("action-name"),
      actionParams: document.getElementById("action-params"),

      // Verification
      verificationCard: document.getElementById("verification-card"),
      verificationFinding: document.getElementById("verification-finding"),

      // Events
      eventsContainer: document.getElementById("events-container"),
      eventCount: document.getElementById("event-count")
    };
  }

  bindEvents() {
    this.dom.scenarioSelect.addEventListener("change", (e) => {
      this.loadScenario(e.target.value);
    });

    this.dom.btnPlay.addEventListener("click", () => this.togglePlay());
    this.dom.btnStep.addEventListener("click", () => this.stepForward());
    this.dom.btnReset.addEventListener("click", () => this.resetScenario());

    this.dom.speedSelect.addEventListener("change", (e) => {
      this.playbackSpeedMs = parseInt(e.target.value, 10);
      if (this.isPlaying) {
        this.pause();
        this.play();
      }
    });

    this.dom.wsToggleBtn.addEventListener("click", () => this.toggleLiveWebSocket());
  }

  loadScenario(key) {
    this.pause();
    this.currentScenarioKey = key;
    const scenario = SCENARIOS[key];
    if (!scenario) return;

    this.currentStepIndex = -1;
    this.state = {
      incident_id: `inc_${key}_${Date.now()}`,
      title: scenario.name,
      status: "idle",
      blast_radius: "unknown",
      confidence: 0.0,
      decision: "pending",
      hypotheses: [],
      actions_taken: [],
      events: []
    };

    this.dom.scenarioDesc.textContent = scenario.description;
    this.dom.expectedOutcome.textContent = scenario.expectedOutcome;
    this.dom.serviceName.textContent = scenario.service;

    this.render();
  }

  togglePlay() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }

  play() {
    const scenario = SCENARIOS[this.currentScenarioKey];
    if (!scenario) return;

    this.isPlaying = true;
    this.dom.btnPlay.innerHTML = `<span>⏸</span> Pause`;
    this.dom.btnPlay.classList.add("active");

    this.playInterval = setInterval(() => {
      if (this.currentStepIndex < scenario.timeline.length - 1) {
        this.stepForward();
      } else {
        this.pause();
      }
    }, this.playbackSpeedMs);
  }

  pause() {
    this.isPlaying = false;
    if (this.playInterval) clearInterval(this.playInterval);
    this.dom.btnPlay.innerHTML = `<span>▶</span> Run Simulation`;
    this.dom.btnPlay.classList.remove("active");
  }

  resetScenario() {
    this.loadScenario(this.currentScenarioKey);
  }

  stepForward() {
    const scenario = SCENARIOS[this.currentScenarioKey];
    if (!scenario) return;

    if (this.currentStepIndex < scenario.timeline.length - 1) {
      this.currentStepIndex += 1;
      const eventItem = scenario.timeline[this.currentStepIndex];
      this.processTimelineEvent(eventItem);
    }
  }

  processTimelineEvent(eventItem) {
    // Record event
    this.state.events.push(eventItem);

    // Apply state mutations
    if (eventItem.stateUpdate) {
      Object.assign(this.state, eventItem.stateUpdate);
    }

    this.render();
  }

  render() {
    const scenario = SCENARIOS[this.currentScenarioKey];
    const currentEvent = this.currentStepIndex >= 0 ? scenario.timeline[this.currentStepIndex] : null;

    // 1. Update Stepper Pipeline
    const activePhaseIndex = this.getPhaseIndex(currentEvent ? currentEvent.phase : "idle");
    this.dom.stepNodes.forEach((node, idx) => {
      node.classList.remove("active", "completed");
      if (idx === activePhaseIndex) {
        node.classList.add("active");
      } else if (idx < activePhaseIndex) {
        node.classList.add("completed");
      }
    });

    // 2. Incident Summary
    this.dom.incidentTitle.textContent = this.state.title || "Ready to Investigate";
    this.dom.blastRadius.textContent = (this.state.blast_radius || "UNKNOWN").toUpperCase();

    // Status Badge
    let statusBadgeText = "IDLE";
    let statusBadgeClass = "badge-info";

    if (this.state.status === "investigating") {
      statusBadgeText = "INVESTIGATING";
      statusBadgeClass = "badge-info";
    } else if (this.state.status === "resolved") {
      statusBadgeText = "RECOVERY VERIFIED";
      statusBadgeClass = "badge-success";
    } else if (this.state.status === "dismissed_false_alarm") {
      statusBadgeText = "FALSE ALARM (NO ACTION)";
      statusBadgeClass = "badge-warning";
    } else if (this.state.status === "escalated" || this.state.decision === "escalate") {
      statusBadgeText = "ESCALATED TO SRE";
      statusBadgeClass = "badge-danger";
    }

    this.dom.incidentStatusBadge.textContent = statusBadgeText;
    this.dom.incidentStatusBadge.className = `card-badge ${statusBadgeClass}`;

    // 3. Confidence Bar
    const confPercent = Math.round((this.state.confidence || 0) * 100);
    this.dom.confidenceValue.textContent = `${(this.state.confidence || 0).toFixed(2)}`;
    this.dom.confidenceBarFill.style.width = `${confPercent}%`;

    // 4. Competing Hypotheses List
    this.renderHypotheses();

    // 5. Diagnostics & Skeptic
    this.renderDiagnostics();
    this.renderSkeptic();

    // 6. Safety Gate & Action
    this.renderGateAndAction();

    // 7. Verification
    this.renderVerification();

    // 8. Event Timeline Log
    this.renderEvents();
  }

  getPhaseIndex(phase) {
    const phases = ["observe", "hypothesize", "experiment", "skeptic", "gate", "action", "verify", "complete"];
    return phases.indexOf(phase);
  }

  renderHypotheses() {
    if (!this.state.hypotheses || this.state.hypotheses.length === 0) {
      this.dom.hypothesesList.innerHTML = `
        <div style="color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 2rem 0;">
          Awaiting triage & hypothesis generation...
        </div>
      `;
      return;
    }

    // Find leader
    const leaderHyp = this.state.hypotheses.find(h => h.status === "alive");

    this.dom.hypothesesList.innerHTML = this.state.hypotheses.map((h, i) => {
      const isLeader = leaderHyp && leaderHyp.id === h.id;
      const statusClass = h.status || "alive";
      
      const evidenceHTML = (h.evidence || []).map(e => `
        <div class="evidence-tag ${e.classification}">
          <span>${e.classification === 'supports' ? '✓' : e.classification === 'contradicts' ? '✗' : '?'}</span>
          <span>${e.source}: ${e.finding}</span>
        </div>
      `).join("");

      return `
        <div class="hypothesis-card ${statusClass} ${isLeader ? 'leader' : ''}">
          <div class="hyp-header">
            <span class="hyp-id">${h.id.toUpperCase()}</span>
            <span class="hyp-status ${statusClass}">${statusClass.toUpperCase()}${isLeader ? ' • LEADER' : ''}</span>
          </div>
          <div class="hyp-claim">${h.claim}</div>
          <div class="hyp-prediction">⚡ Prediction: ${h.prediction}</div>
          ${evidenceHTML ? `<div class="evidence-tags">${evidenceHTML}</div>` : ''}
        </div>
      `;
    }).join("");
  }

  renderDiagnostics() {
    const toolEvents = this.state.events.filter(e => e.type === "tool_called");
    if (toolEvents.length === 0) {
      this.dom.diagnosticsContainer.innerHTML = `
        <div style="color: var(--text-muted); font-size: 0.8rem; padding: 0.5rem 0;">
          No diagnostic tools executed yet.
        </div>
      `;
      return;
    }

    const lastTool = toolEvents[toolEvents.length - 1];
    const p = lastTool.payload;
    this.dom.diagnosticsContainer.innerHTML = `
      <div style="font-family: var(--font-mono); font-size: 0.78rem; background: rgba(0,0,0,0.3); padding: 0.6rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
          <span style="color: var(--accent-cyan); font-weight: 700;">${p.tool}(...)</span>
          <span style="color: var(--accent-emerald); font-weight: 600;">✓ OK (${p.latency_ms.toFixed(1)}ms)</span>
        </div>
        <div style="color: var(--text-muted); font-size: 0.7rem; margin-bottom: 0.3rem;">Params: ${JSON.stringify(p.parameters || {})}</div>
        <div style="color: var(--text-secondary); background: rgba(0,0,0,0.4); padding: 0.4rem; border-radius: 4px; max-height: 80px; overflow-y: auto;">
          ${JSON.stringify(p.data || {}, null, 2)}
        </div>
      </div>
    `;
  }

  renderSkeptic() {
    const skepticEvent = this.state.events.find(e => e.type === "skeptic_note");
    if (skepticEvent) {
      this.dom.skepticCard.style.display = "flex";
      this.dom.skepticCritique.textContent = skepticEvent.payload.critique;
    } else {
      this.dom.skepticCard.style.display = "none";
    }
  }

  renderGateAndAction() {
    const gateEvent = this.state.events.find(e => e.type === "decision_made");
    if (gateEvent) {
      const dec = gateEvent.payload.decision;
      this.dom.gateStatusPill.className = `gate-status-pill ${dec}`;
      this.dom.gateStatusPill.innerHTML = `
        <span>Gate Outcome</span>
        <span>${dec.toUpperCase()}</span>
      `;
      this.dom.gateReason.textContent = gateEvent.payload.reason || "Evaluated confidence and safety policies.";
    } else {
      this.dom.gateStatusPill.className = "gate-status-pill pending";
      this.dom.gateStatusPill.innerHTML = `<span>Gate Outcome</span><span>PENDING</span>`;
      this.dom.gateReason.textContent = "Awaiting skeptic challenge and evidence verification.";
    }

    const actionEvent = this.state.events.find(e => e.type === "action_taken");
    if (actionEvent) {
      this.dom.actionCard.style.display = "flex";
      this.dom.actionName.textContent = actionEvent.payload.action;
      this.dom.actionParams.textContent = JSON.stringify(actionEvent.payload.parameters || {}, null, 2);
    } else {
      this.dom.actionCard.style.display = "none";
    }
  }

  renderVerification() {
    const verifyEvent = this.state.events.find(e => e.type === "recovery_checked");
    if (verifyEvent) {
      this.dom.verificationCard.style.display = "flex";
      const recovered = verifyEvent.payload.recovered;
      this.dom.verificationCard.className = `verification-card ${recovered ? 'success' : 'failed'}`;
      this.dom.verificationFinding.textContent = verifyEvent.payload.finding;
    } else {
      this.dom.verificationCard.style.display = "none";
    }
  }

  renderEvents() {
    this.dom.eventCount.textContent = `${this.state.events.length} Events`;
    this.dom.eventsContainer.innerHTML = this.state.events.map(ev => `
      <div class="event-item">
        <span class="event-time">${new Date(ev.ts * 1000).toLocaleTimeString()}</span>
        <span class="event-type-badge type-${ev.type}">${ev.type}</span>
        <span class="event-summary">${ev.payload.title || ev.payload.summary || ev.payload.critique || ev.payload.finding || ev.payload.reason || JSON.stringify(ev.payload)}</span>
      </div>
    `).reverse().join("");
  }

  toggleLiveWebSocket() {
    if (this.isLiveMode) {
      this.disconnectWebSocket();
    } else {
      this.connectWebSocket();
    }
  }

  connectWebSocket() {
    this.pause();
    this.isLiveMode = true;
    const wsUrl = "ws://localhost:8000/ws/events";

    try {
      this.ws = new WebSocket(wsUrl);
      this.dom.connectionStatus.textContent = "Connecting to WebSocket...";

      this.ws.onopen = () => {
        this.dom.connectionStatus.textContent = "🟢 Live WebSocket Connected (localhost:8000)";
        this.dom.wsToggleBtn.textContent = "Disconnect WS";
        this.dom.wsToggleBtn.classList.add("active");
      };

      this.ws.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data);
          this.processTimelineEvent(data);
        } catch (err) {
          console.error("Malformed WebSocket payload", err);
        }
      };

      this.ws.onerror = (e) => {
        this.dom.connectionStatus.textContent = "⚠️ WS Connection Failed (Backend Offline - Reverting to Simulation)";
        this.disconnectWebSocket();
      };

      this.ws.onclose = () => {
        this.dom.connectionStatus.textContent = "⚪ Replay Simulation Mode";
        this.disconnectWebSocket();
      };
    } catch (e) {
      this.dom.connectionStatus.textContent = "⚠️ WebSocket unavailable";
      this.disconnectWebSocket();
    }
  }

  disconnectWebSocket() {
    this.isLiveMode = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.dom.wsToggleBtn.textContent = "Connect Live WS";
    this.dom.wsToggleBtn.classList.remove("active");
    this.dom.connectionStatus.textContent = "⚪ Simulation / Replay Mode";
  }
}

// Instantiate on load
window.addEventListener("DOMContentLoaded", () => {
  window.dashboard = new DashboardController();
});
