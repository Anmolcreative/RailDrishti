# RailDrishti 

> One delayed train becomes six. RailDrishti stops the chain before it starts.

[![Hackfest 2026](https://img.shields.io/badge/Hackfest-2026-green?style=for-the-badge)](https://nmamit.nitte.edu.in)
[![Track](https://img.shields.io/badge/Track-Logistics-blue?style=for-the-badge)]()
[![Team](https://img.shields.io/badge/Team-404_FOCACCIA-orange?style=for-the-badge)]()

---

## The Problem

India loses ₹22,000 crore annually from train delays. It's not a hardware problem — it's a reaction-time problem. Human controllers can't process conflicts across hundreds of trains fast enough. One late train cascades into six.

RailDrishti predicts the conflict before it happens and resolves it in 200ms.

---

## What It Does

- Predicts conflicts 5 minutes ahead using a Graph Neural Network that models the rail network in real time
- Issues speed advisories and hold decisions via a Reinforcement Learning agent (PPO) in under 200ms
- Cuts fixed 3-min headways down to 90-sec intervals, tuned per train type and speed
- Gives controllers a live dashboard with one-click accept/override on every conflict alert
- Runs entirely on existing infrastructure — no new hardware, pure software overlay on CTC systems

---

## Architecture

```
LAYER 1 — DATA INGESTION
Axle counters + GPS on locomotives → Apache Kafka (event streaming)
→ InfluxDB (time-series storage) + Weather API

LAYER 2 — AI ENGINE
A. Conflict Detector  — calculates ETA per block, flags headway violations with severity score
B. GNN State Model    — nodes = stations, edges = sections, learns congestion propagation
C. RL Scheduler (PPO) — state: positions + delays | action: speed advisory or hold
                        reward: throughput gained minus delay caused

LAYER 3 — CONTROLLER DASHBOARD
React.js + Mapbox GL live map via WebSocket
D3.js throughput charts with live section KPIs
Conflict alert cards with Accept / Modify / Override
Speed advisory panel per train with estimated delay impact
```

---

## Tech Stack

| Layer | Technologies |
|---|---|
| ML / AI | PyTorch, PyTorch Geometric (GNN), Stable-Baselines3 (PPO), ONNX |
| Backend | FastAPI, Apache Kafka, InfluxDB, Redis |
| Frontend | React.js, Mapbox GL, D3.js, WebSocket |
| Simulation | SimPy, Google OR-Tools |
| Deployment | Docker, Kubernetes |

---

## Expected Impact

| Metric | Before | After | Change |
|---|---|---|---|
| Section throughput | 10 trains/hr | 15–17 trains/hr | +50–70% |
| Average train delay | 45 min | 18 min | -60% |
| Conflict events/day | 120+ | 20–30 | -75% |
| New hardware needed | — | None | zero capex |

---

## Why No New Hardware

Axle counters, CTC panels, and GPS are already deployed across Indian Railways. RailDrishti sits on top of existing infrastructure — no civil work, no signal changes, no procurement cycle.

---

## Roadmap

- Aligns with National Rail Plan 2030 and Mission Raftaar
- Future integration with Kavach anti-collision system
- Pilot target: Bhopal–Itarsi section (highest freight-passenger conflict density)

---

## Team

404 FOCACCIA — Hackfest 2026, NMAMIT Nitte, Logistics Track
