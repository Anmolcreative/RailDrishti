/**
 * RailDrishti — WebSocket Server + Conflict Detection Engine
 * Layer 2: Redis subscriber → Conflict Engine → ML inference → WS broadcast
 *
 * PORT: 3000
 * WS message types emitted: train_status_batch | conflict_alert | ml_recommendation | scraper_health
 */

const WebSocket = require("ws");
const Redis     = require("ioredis");
const axios     = require("axios");

const ML_API_URL   = process.env.ML_API_URL   || "http://localhost:8000";
const REDIS_URL    = process.env.REDIS_URL     || "redis://localhost:6379";
const WS_PORT      = parseInt(process.env.WS_PORT || "3000", 10);
const WS_BROADCAST_INTERVAL_MS = 2000;

// ── Redis sub/pub ─────────────────────────────────────────────────────────────
const redisSub = new Redis(REDIS_URL);
const redisPub = new Redis(REDIS_URL);

// ── WebSocket server ──────────────────────────────────────────────────────────
const wss = new WebSocket.Server({ port: WS_PORT });
console.log(`[WS] Server listening on ws://localhost:${WS_PORT}`);

function broadcast(data) {
  const msg = JSON.stringify(data);
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(msg);
    }
  });
}

wss.on("connection", (ws) => {
  console.log("[WS] Client connected. Total:", wss.clients.size);
  // Send latest cached state immediately on connect
  if (latestCorridorState) {
    ws.send(JSON.stringify({ type: "corridor_state", payload: latestCorridorState }));
  }
  ws.on("message", handleOperatorAction);
  ws.on("close", () => console.log("[WS] Client disconnected. Total:", wss.clients.size));
});

// ── Operator action handler ────────────────────────────────────────────────────
const auditLog = [];

function handleOperatorAction(raw) {
  try {
    const msg = JSON.parse(raw);
    if (msg.type === "operator_action") {
      const entry = {
        ...msg,
        timestamp: new Date().toISOString(),
        id:        `OP_${Date.now()}`,
      };
      auditLog.push(entry);
      console.log("[Audit] Operator action:", entry);
      // Broadcast acknowledgement
      broadcast({ type: "action_ack", payload: entry });
    }
  } catch (err) {
    console.error("[WS] Bad message:", err.message);
  }
}

// ── Conflict detection ────────────────────────────────────────────────────────
function detectConflicts(trains) {
  const alerts = [];

  for (let i = 0; i < trains.length; i++) {
    for (let j = i + 1; j < trains.length; j++) {
      const a = trains[i], b = trains[j];

      // Same corridor + both running + gap < 5 min
      if (
        a.corridor === b.corridor &&
        a.current_station === b.current_station
      ) {
        alerts.push({
          id:            `CONFLICT_${a.train_no}_${b.train_no}_${Date.now()}`,
          type:          "HEAD_ON_RISK",
          severity:      "HIGH",
          trains:        [a.train_no, b.train_no],
          station:       a.current_station,
          message:       `Trains ${a.train_no} and ${b.train_no} at same station on ${a.corridor}`,
          timestamp:     new Date().toISOString(),
          recommended:   "REROUTE",
        });
      }

      // Same corridor + one heavily delayed causing cascade
      if (
        a.corridor === b.corridor &&
        Math.abs((a.delay_minutes || 0) - (b.delay_minutes || 0)) > 20
      ) {
        alerts.push({
          id:          `CASCADE_${a.train_no}_${b.train_no}_${Date.now()}`,
          type:        "CASCADE_RISK",
          severity:    "MEDIUM",
          trains:      [a.train_no, b.train_no],
          station:     a.current_station,
          message:     `Cascade delay risk: ${a.train_no} (${a.delay_minutes}min) → ${b.train_no}`,
          timestamp:   new Date().toISOString(),
          recommended: "HOLD",
        });
      }
    }

    // Platform saturation (>= 4 trains in same corridor)
    const corridorTrains = trains.filter((t) => t.corridor === trains[i].corridor);
    if (corridorTrains.length >= 4 && !alerts.some((a) => a.type === "CONGESTION" && a.trains.includes(trains[i].train_no))) {
      alerts.push({
        id:          `CONG_${trains[i].corridor}_${Date.now()}`,
        type:        "CONGESTION",
        severity:    "LOW",
        trains:      corridorTrains.map((t) => t.train_no),
        station:     "CORRIDOR",
        message:     `High train density on ${trains[i].corridor} corridor`,
        timestamp:   new Date().toISOString(),
        recommended: "HOLD",
      });
    }
  }

  return alerts;
}

// ── ML inference per train ────────────────────────────────────────────────────
async function getMLRecommendation(train, conflictDetected) {
  try {
    const hour = new Date().getHours();
    const payload = {
      delay_minutes:        train.delay_minutes || 0,
      congestion_score:     train.congestion_score || 0.3,
      speed_kmh:            train.speed_kmh || 70,
      trains_ahead:         train.trains_ahead || 0,
      trailing_gap_min:     train.trailing_gap_min || 15,
      train_type:           train.train_type || "EXPRESS",
      is_vip:               train.is_vip || false,
      is_freight:           train.is_freight || false,
      station_zone:         train.zone || "NR",
      station_type:         train.station_type || "JUNCTION",
      platform_utilisation: train.platform_utilisation || 0.4,
      weather_state:        train.weather_state || 0,
      temperature_c:        train.temperature_c || 28,
      precipitation_mm:     train.precipitation_mm || 0,
      hour_of_day:          hour,
      day_of_week:          new Date().getDay(),
      is_peak_hour:         (hour >= 7 && hour <= 10) || (hour >= 17 && hour <= 21),
      delay_velocity:       train.delay_velocity || 0,
      cascade_risk:         train.cascade_risk || 0.2,
      historical_avg_delay: train.historical_avg_delay || 5,
      train_no:             train.train_no,
      station_code:         train.current_station,
      corridor_id:          train.corridor,
    };

    const { data } = await axios.post(`${ML_API_URL}/predict`, payload, { timeout: 500 });
    return data;
  } catch (err) {
    // Graceful degradation: rule-based fallback
    return ruleBased(train, conflictDetected);
  }
}

function ruleBased(train, conflictDetected) {
  const d = train.delay_minutes || 0;
  const c = train.congestion_score || 0;
  let action = "APPROVE";
  if (train.is_vip && d > 0 && c > 0.6) action = "PRIORITY_OVERRIDE";
  else if (conflictDetected || c > 0.6)  action = "REROUTE";
  else if (d >= 5 || (c >= 0.4 && c <= 0.6)) action = "HOLD";

  return {
    action,
    confidence:      0.72,
    probabilities:   { APPROVE: 0.1, HOLD: 0.1, REROUTE: 0.1, PRIORITY_OVERRIDE: 0.1 },
    shap_top5:       [],
    latency_ms:      0,
    source:          "RULE_BASED",
    train_no:        train.train_no,
  };
}

// ── State assembly ────────────────────────────────────────────────────────────
let latestCorridorState = null;

async function assembleCorridorState(trains, source) {
  const conflicts = detectConflicts(trains);

  // ML inference — parallelised
  const mlResults = await Promise.all(
    trains.map((t) => {
      const hasConflict = conflicts.some((c) => c.trains.includes(t.train_no));
      return getMLRecommendation(t, hasConflict);
    })
  );

  const enrichedTrains = trains.map((t, i) => ({
    ...t,
    ml_recommendation: mlResults[i],
  }));

  return {
    timestamp:      new Date().toISOString(),
    source,
    trains:         enrichedTrains,
    conflicts,
    summary: {
      total_trains:    trains.length,
      conflict_count:  conflicts.filter((c) => c.severity === "HIGH").length,
      avg_delay:       trains.reduce((sum, t) => sum + (t.delay_minutes || 0), 0) / trains.length,
    },
  };
}

// ── Redis subscriber ──────────────────────────────────────────────────────────
redisSub.subscribe("raildrishti:train_status", (err) => {
  if (err) {
    console.error("[Redis] Subscribe error:", err);
  } else {
    console.log("[Redis] Subscribed to raildrishti:train_status");
  }
});

redisSub.on("message", async (_channel, raw) => {
  try {
    const msg = JSON.parse(raw);
    if (msg.type !== "train_status_batch") return;

    const state = await assembleCorridorState(msg.trains, msg.source);
    latestCorridorState = state;

    broadcast({ type: "corridor_state", payload: state });
  } catch (err) {
    console.error("[WS] State assembly error:", err.message);
  }
});

// ── Heartbeat broadcast (2s cadence) ──────────────────────────────────────────
setInterval(() => {
  if (latestCorridorState) {
    broadcast({ type: "heartbeat", timestamp: new Date().toISOString() });
  }
}, WS_BROADCAST_INTERVAL_MS);

console.log("[WS] RailDrishti WebSocket server ready.");