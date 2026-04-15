# RailDrishti — Product Requirements Document

**v2.0 — April 2026** | Anu + Anmol

| Live Corridors | Stations | ML Model | Target Latency |
|---|---|---|---|
| 3 | 100+ | LightGBM | < 2s |

---

## 1. Executive Summary

RailDrishti ("Railway Vision") is an intelligent, real-time railway traffic management dashboard built for Indian Railways. It combines a dark-mode, HUD-style React frontend with a LightGBM-powered ML intelligence layer to deliver `APPROVE / HOLD / REROUTE / PRIORITY-OVERRIDE` recommendations to operators across live and simulated corridors.

The platform is developed by a two-person team: Anu (frontend + system architecture) and Anmol (ML engineering + data pipeline). The v2.0 PRD supersedes the original design document and incorporates updated decisions on real-time data ingestion, ML feature engineering, and deployment architecture.

> **KEY DECISION — Real-Time Data:** RailDrishti will use a hybrid strategy:
> - **Primary:** National Train Enquiry System (NTES) scraper + RailAPI.in for live train positions
> - **Secondary:** OpenRailwayMap (SPARQL) for static infrastructure, OpenWeatherMap for weather features
> - **Future:** Official IR NTES API access (when credentials are secured)

---

## 2. Problem Statement

Indian Railways operates ~13,000 passenger trains daily across 68,000 km of track, managed by human operators using legacy systems. Key pain points:

- No real-time conflict detection — operators discover multi-train corridor congestion reactively
- Manual delay propagation — cascading delays are calculated ad hoc, not predicted
- No ML-assisted decision support — APPROVE / HOLD / REROUTE calls are entirely human-driven
- Data silos — timetable, GPS, weather, and priority data live in disconnected systems
- No unified visualization layer — there is no national-level interactive station drill-down view

RailDrishti addresses all five pain points in a single dashboard built for demonstration, research, and production pathfinding.

---

## 3. Product Vision & Scope

### 3.1 Vision

A military-grade, real-time situational awareness platform for Indian Railways that empowers operators with ML-generated recommendations, conflict alerts, and full corridor drill-down — all within a 2-second data refresh loop.

### 3.2 In-Scope (v1.0 / v2.0)

- National SVG map with clickable station markers and drill-down cards
- 3 live corridors: BPL→ET, NDLS→MGS, HWH→DHN
- 22 named + 100 simulated stations from GeoJSON coordinates
- Train action cards with `APPROVE / OVERRIDE / HOLD / REROUTE` buttons
- ML intelligence panel: LightGBM multiclass classifier for action recommendations
- Conflict alert system with severity scoring
- NTES scraper for live train position ingestion
- WebSocket/MQTT live data feed with 2-second refresh
- Simulated fallback mode (Gaussian noise σ=2min on delays)

### 3.3 Out-of-Scope (v1.0)

- Official IR ATMS / FOIS integration (pending credential approval)
- Mobile native app (React Native port planned for v3)
- End-to-end train control actuation (display-only system)

---

## 4. Real-Time Data Strategy

| Approach | Data Quality | Effort | Verdict |
|---|---|---|---|
| Official IR NTES API | Excellent — authoritative | High — requires MoR approval | FUTURE |
| NTES Web Scraper | Good — same source as public | Medium — fragile to HTML changes | PRIMARY v1.0 |
| RailAPI.in / third-party | Good — aggregated real data | Low — REST JSON, free tier | PRIMARY v1.0 |
| Simulated (Gaussian σ=2min) | Synthetic — for demos | None — already built | FALLBACK |

### 4.1 NTES Scraper

Node.js/Puppeteer scraper targeting `enquiry.indianrail.gov.in`:

- Queries the NTES 'Train Running Status' endpoint for each active train in the 3 live corridors
- Parses departure/arrival times, current station, and delay minutes from the HTML response
- Normalizes data into RailDrishti's internal `TrainStatus` schema
- Publishes updates via WebSocket to the React frontend every 30 seconds
- Falls back to RailAPI.in JSON if NTES returns errors or is throttled

> **Scraper Resilience Strategy:**
> - CSS selector config externalized to `ntes_selectors.json` — survives HTML redesigns
> - Retry logic: 3 attempts with exponential backoff before RailAPI.in fallback
> - Health endpoint `/api/scraper/health` exposes last-success timestamp and source (NTES | RailAPI | Simulated)
> - Rate limit: max 1 req/5s per train to stay within NTES fair-use thresholds

### 4.2 RailAPI.in — Supplementary REST Layer

- Base URL: `https://railapi.in/api/v2/`
- Key endpoint: `GET /trains/{train_number}/live` — returns lat/lng, delay_mins, last_station
- Free tier: 1,000 req/day — sufficient for 3-corridor demo
- Authentication: `X-API-Key` header

### 4.3 Static Infrastructure Data

- OpenRailwayMap (SPARQL / Overpass API) — station coordinates, track topology, zone boundaries
- `raildishti_stations.json` — curated file of 22 named + 100 simulated stations (built)
- IR Zone CSV (public) — for zone color-coding on the national map

### 4.4 Weather & External Features

- OpenWeatherMap API (free tier) — temperature, precipitation, fog score per station
- Queried every 10 minutes; weather state rotates in simulated mode to cover all conditions
- Used as ML feature input (see Section 6)

---

## 5. Frontend Architecture

### 5.1 Tech Stack

| Component | Choice |
|---|---|
| Framework | React 18 (Vite build) |
| Styling | Tailwind CSS + custom CSS variables for HUD dark theme |
| Font | Share Tech Mono (monospace HUD aesthetic) |
| Map | Custom SVG India map with D3-powered coordinate projection |
| State | Zustand global store + React Query for API polling |
| Real-time | WebSocket (ws library, Node server) — 2-second update interval |

### 5.2 Component Hierarchy

- `RailDrishti.jsx` — root app shell, theme provider, WebSocket context
- `NationalMap.jsx` — SVG India map, zone overlays, station marker layer
- `StationMarker.jsx` — clickable SVG circle, color by alert status
- `CorridorPanel.jsx` — right sidebar listing active corridors + train cards
- `TrainCard.jsx` — APPROVE / HOLD / REROUTE / PRIORITY-OVERRIDE action buttons
- `MLIntelligencePanel.jsx` — live corridor feed, confidence bars, decision log
- `ConflictAlert.jsx` — severity badge, affected trains, recommended action
- `ScraperHealth.jsx` — status indicator: NTES | RailAPI | Simulated

### 5.3 Design System

| Token | Value | Usage |
|---|---|---|
| `--bg-primary` | `#0A0F1E` | App background |
| `--bg-surface` | `#111827` | Panel backgrounds |
| `--accent-blue` | `#3B82F6` | APPROVE state, primary CTA |
| `--accent-amber` | `#F59E0B` | HOLD state, warnings |
| `--accent-red` | `#EF4444` | REROUTE / conflict alerts |
| `--accent-green` | `#10B981` | On-time / normal status |
| `--font-hud` | `Share Tech Mono` | All HUD labels and data values |

---

## 6. ML Intelligence Layer

### 6.1 Model Selection — LightGBM Multiclass Classifier

LightGBM selected over Random Forest, XGBoost, and neural approaches because:

- Native support for categorical features (`train_type`, `zone`, `weather_state`) without one-hot encoding
- Leaf-wise tree growth outperforms XGBoost on tabular railway delay data
- Training time < 30s on 100k rows — enables rapid experimentation
- Built-in feature importance (SHAP-compatible) for explainability in the dashboard
- sklearn-compatible API — easy pipeline integration with pandas feature engineering

### 6.2 Target Variable — 4-Class Action

| Class | Action | Trigger Condition |
|---|---|---|
| 0 | APPROVE | Delay < 5 min, congestion < 0.4, no conflicts |
| 1 | HOLD | Delay 5–15 min OR congestion 0.4–0.6 |
| 2 | REROUTE | Conflict detected OR congestion > 0.6 |
| 3 | PRIORITY-OVERRIDE | Rajdhani/VIP train + any delay + congestion > 0.6 |

### 6.3 Feature Engineering

All features computed per `(train, station, timestamp)` triple:

| Feature | Type | Source |
|---|---|---|
| `delay_minutes` | Numeric | NTES scraper / RailAPI |
| `corridor_congestion_score` | Numeric [0,1] | Computed: active trains / corridor capacity |
| `trains_ahead_count` | Integer | Live corridor feed |
| `speed_deviation_pct` | Numeric | GPS vs timetable speed |
| `train_type` | Categorical | IR timetable CSV |
| `zone_id` | Categorical | IR Zone CSV |
| `weather_state` | Categorical | OpenWeatherMap API |
| `hour_of_day` | Cyclic (sin/cos) | Timestamp derived |
| `day_of_week` | Cyclic (sin/cos) | Timestamp derived |
| `is_vip_train` | Boolean | Priority classification list |
| `historical_avg_delay_min` | Numeric | Historical delay dataset |
| `conflict_flag` | Boolean | Conflict detection engine (real-time) |

> **Data Dependencies (Blockers for full ML training):**
> 1. Official IR Timetable CSV — for `train_type`, scheduled times, stop sequences
> 2. Historical Delay Dataset (2+ years) — for `historical_avg_delay_min` and label generation
> 3. GPS Sensor Credentials — for `speed_deviation_pct` (live)
> 4. Priority Classification List — for `is_vip_train` (Rajdhani, Shatabdi, VIP specials)
>
> Interim: synthetic generation with domain-calibrated distributions covers all features until real data arrives.

### 6.4 Model Training Pipeline

- Data ingestion: NTES scraper → pandas DataFrame → `feature_engineering.py`
- Label generation: rule-based heuristic on delay + congestion (bootstraps training set)
- Train/val/test split: 70/15/15, stratified by action class
- Hyperparameter tuning: Optuna (100 trials, 5-fold CV on train set)
- Evaluation: macro F1, confusion matrix, per-class precision/recall
- SHAP explainability: top-5 features per prediction displayed in `MLIntelligencePanel`
- Export: `model.pkl` + `feature_names.json` → loaded by FastAPI inference server

### 6.5 Inference Server

- Framework: FastAPI (Python) — lightweight, async
- Endpoint: `POST /predict` — accepts `TrainFeatureVector` JSON, returns `{ action, confidence, shap_top5 }`
- Latency target: < 50ms p99 (LightGBM inference is CPU-bound, < 5ms typical)
- Deployment: Docker container, runs alongside Node WebSocket server
- Frontend polling: every 2 seconds via WebSocket message type `ml_recommendation`

---

## 7. Implementation Roadmap — 8 Phases

| # | Phase | Deliverables | Owner |
|---|---|---|---|
| 1 | Data Foundations | Stations JSON, GeoJSON parse, corridor definitions, simulated delay baseline | Both (done) |
| 2 | Frontend Shell | React app, SVG national map, dark HUD theme, Share Tech Mono, Tailwind tokens | Anu (done) |
| 3 | NTES Scraper | Puppeteer scraper, RailAPI.in fallback, WebSocket publisher, health endpoint | Anu + Anmol |
| 4 | Conflict Engine | Rule-based conflict detection, severity scoring, alert card component | Anu |
| 5 | ML Data Prep | Feature engineering pipeline, synthetic label generation, train/val/test split | Anmol |
| 6 | LightGBM Training | Optuna tuning, SHAP explainability, model.pkl export, offline evaluation report | Anmol |
| 7 | FastAPI Server | POST /predict endpoint, Docker container, WebSocket integration, confidence bars in UI | Both |
| 8 | Real Data & Hardening | Swap synthetic for real IR data, retrain, A/B vs simulated in ML comparison panel, load test | Anmol (data) + Anu (UI) |

---

## 8. API Integration Reference

### 8.1 NTES Scraper (Internal)

- Target: `https://enquiry.indianrail.gov.in/mntes/`
- Method: Puppeteer headless browser
- Output schema: `{ train_no, train_name, current_station, delay_min, last_updated }`
- Config file: `ntes_selectors.json`
- Error handling: 3 retries → RailAPI fallback → simulated fallback

### 8.2 RailAPI.in

- Docs: `https://railapi.in/docs`
- Auth: `X-API-Key` (free tier, 1k req/day)
- Key endpoint: `GET /api/v2/trains/{train_no}/live`
- Response: `{ lat, lng, delay_mins, last_station_code, next_station_code, speed_kmh }`

### 8.3 OpenWeatherMap

- Docs: `https://openweathermap.org/api/one-call-3`
- Auth: `APPID` query param (free tier — 1k calls/day)
- Endpoint: `GET /data/3.0/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly`
- ML feature mapping: `Clear=0, Clouds=1, Rain=2, Fog=3, Thunderstorm=4`

### 8.4 OpenRailwayMap / Overpass API

- Used for: static track topology, station node positions
- Already partially consumed — `raildishti_stations.json` built from GeoJSON export
- Future: query Overpass for signal positions and junction topology

### 8.5 FastAPI ML Inference (Internal)

- Endpoint: `POST http://localhost:8000/predict`
- Request: `{ delay_minutes, congestion_score, train_type, weather_state, ... }`
- Response: `{ action: 'APPROVE'|'HOLD'|'REROUTE'|'PRIORITY_OVERRIDE', confidence: 0.0–1.0, shap_top5: [...] }`
- WebSocket event: `ml_recommendation` — emitted by Node server after calling `/predict`

---

## 9. System Architecture Overview

```
LAYER 1 — Data Ingestion
  NTES Scraper (Puppeteer) + RailAPI.in REST + OpenWeatherMap REST
  → normalizes to TrainStatus schema → pushes to Redis pub/sub

LAYER 2 — Intelligence Engine (Node.js backend)
  Redis subscriber → Conflict Detection Engine → calls FastAPI /predict per train
  → assembles CorridorState object → WebSocket broadcast to all connected clients

LAYER 3 — ML Inference (FastAPI + LightGBM)
  POST /predict → feature vector → model.pkl → { action, confidence, shap_top5 }
  → returned synchronously to Node backend within 50ms

LAYER 4 — React Frontend
  WebSocket client → Zustand store → NationalMap + CorridorPanel + MLIntelligencePanel
  → operator APPROVE/OVERRIDE/HOLD/REROUTE → POST /api/operator-action → audit log
```

### 9.1 Data Flow Timing

- Scraper poll interval: 30s (NTES fair-use) / 10s (RailAPI free tier)
- Conflict detection: runs on every new `TrainStatus` event, no additional delay
- ML inference: < 50ms per train, parallelized across corridor trains
- WebSocket broadcast: 2-second cadence to frontend (batched updates)
- Weather refresh: every 10 minutes

### 9.2 Simulated Mode

- Activates automatically when both NTES and RailAPI are unavailable
- Delay model: Gaussian noise N(0, σ=2min) applied to timetable baseline
- Weather state: rotates Clear → Clouds → Rain → Fog every 10 minutes
- Congestion: sinusoidal function peaking at 08:00 and 18:00
- UI indicator: orange `SIMULATED` badge in `ScraperHealth` component

---

## 10. Non-Functional Requirements

| Category | Requirement | Target |
|---|---|---|
| Performance | WebSocket update latency | < 2 seconds end-to-end |
| Performance | ML inference p99 | < 50ms per train |
| Performance | Map render (100+ stations) | < 500ms initial paint |
| Reliability | Scraper uptime | 99% with simulated fallback |
| Reliability | FastAPI server uptime | 99.5% (Docker restart policy) |
| Accuracy | ML macro F1 (synthetic data) | > 0.82 on validation set |
| Accuracy | ML macro F1 (real IR data) | > 0.75 target |
| Usability | Operator action response | < 3 clicks from alert to action |
| Security | API keys | Server-side only — never exposed to frontend |

---

## 11. Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| NTES blocks scraper IP | HIGH | RailAPI.in fallback + simulated mode; rotate scraper user-agent |
| NTES HTML redesign breaks selectors | MED | Externalized selector config; integration test on CI against saved HTML snapshot |
| Data dependencies delayed | HIGH | Synthetic data generation covers all features; retrain on real data later |
| LightGBM accuracy below target on real data | MED | Label smoothing + class weights for imbalanced action classes; fallback to rule-based engine |
| WebSocket connection drops | LOW | Auto-reconnect with exponential backoff in frontend WebSocket hook |
| RailAPI.in free tier exhausted | LOW | Monitor usage; 3 corridors x 30s poll = ~2,880 req/day — upgrade if needed |

---

## 12. Open Questions

1. Can we secure official NTES API credentials via Ministry of Railways channels? Timeline?
2. Should operator APPROVE/OVERRIDE actions be persisted to a database, or logged to a flat file for v1?
3. Do we need user authentication for the dashboard, or is it internal-only for demo purposes?
4. Should the ML comparison panel (ML decision vs actual IR outcome) be built for v1.0 or deferred to v2.0?
5. What is the demo environment — localhost, Vercel frontend + Railway.app backend, or a single VPS?
6. Should SHAP explanations be computed server-side (adds ~10ms) or pre-computed per class as lookup tables?

---

## 13. Appendix — File Inventory

| File | Owner | Description |
|---|---|---|
| `raildish.jsx` | Anu | v1 national map + corridor panel |
| `raildish-v2.jsx` | Anu | v2 with drill-down, train cards, delay/speed panels |
| `raildish-ml.jsx` | Anu | ML intelligence panel, 8-phase roadmap view, comparison panel |
| `raildishti_stations.json` | Both | 22 named + 100 simulated stations, 3 corridor definitions |
| `ntes_scraper.js` | Anmol | Puppeteer NTES scraper (Phase 3 — to build) |
| `feature_engineering.py` | Anmol | Pandas pipeline for ML features (Phase 5 — to build) |
| `train_model.py` | Anmol | LightGBM + Optuna training script (Phase 6 — to build) |
| `inference_server.py` | Anmol | FastAPI /predict endpoint (Phase 7 — to build) |

---

*Document prepared by Anu | ML architecture by Anmol | April 2026*