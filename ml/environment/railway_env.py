"""
RailDrishti — railway_env.py
Gymnasium RL environment using stations_100.json as the network state.
State  : [congestion, trains_norm] per station → shape (N*2,)
Action : 0=maintain | 1=slow_down | 2=hold (applied to highest-congestion station)
Reward : 1 - mean_congestion  (higher = better)
"""

import json
import os
import numpy as np
import gymnasium as gym


class RailwayEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(self, data_path=None):
        super().__init__()

        # Load stations
        if data_path is None:
            data_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "stations_100.json"
            )
        with open(data_path) as f:
            raw = json.load(f)

        stations = raw.get("stations_100", [])
        self.num_stations = len(stations)
        self.station_names = [s["name"] for s in stations]

        # Base congestion levels from data
        self._base_congestion = np.array(
            [float(s.get("congestion", 0.5)) for s in stations], dtype=np.float32
        )
        self._base_trains = np.array(
            [float(s.get("trains", 50)) / 400.0 for s in stations], dtype=np.float32
        )

        # Spaces
        obs_size = self.num_stations * 2   # [congestion, trains_norm] per station
        self.observation_space = gym.spaces.Box(
            low=0.0, high=1.0, shape=(obs_size,), dtype=np.float32
        )
        # 3 discrete actions
        self.action_space = gym.spaces.Discrete(3)

        self.state = None
        self.step_count = 0
        self.max_steps = 200

    # ── Gym interface ──────────────────────────────────────────────────────────
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        # Small random perturbation around base values
        noise = np.random.uniform(-0.05, 0.05, self.num_stations).astype(np.float32)
        congestion = np.clip(self._base_congestion + noise, 0.0, 1.0)
        trains     = np.clip(self._base_trains + noise * 0.5, 0.0, 1.0)

        self.state = np.concatenate([congestion, trains]).astype(np.float32)
        self.step_count = 0
        return self.state, {}

    def step(self, action):
        self.step_count += 1

        congestion = self.state[: self.num_stations].copy()
        trains     = self.state[self.num_stations :].copy()

        # Apply action to the most congested station
        target = int(np.argmax(congestion))

        if action == 0:    # maintain — slight natural drift
            delta = 0.0
        elif action == 1:  # slow_down — reduce congestion at target
            delta = -0.08
        elif action == 2:  # hold — reduce more aggressively
            delta = -0.12

        congestion[target] = float(np.clip(congestion[target] + delta, 0.0, 1.0))

        # Natural drift: all stations move slightly
        drift = np.random.uniform(-0.02, 0.03, self.num_stations).astype(np.float32)
        congestion = np.clip(congestion + drift, 0.0, 1.0).astype(np.float32)
        trains     = np.clip(trains + np.random.uniform(-0.01, 0.01, self.num_stations), 0.0, 1.0).astype(np.float32)

        self.state = np.concatenate([congestion, trains]).astype(np.float32)

        # Reward: lower mean congestion = better
        reward = float(1.0 - np.mean(congestion))

        terminated = self.step_count >= self.max_steps
        truncated  = False
        info = {
            "mean_congestion": float(np.mean(congestion)),
            "critical_stations": int(np.sum(congestion > 0.75)),
            "action_target": self.station_names[target],
        }
        return self.state, reward, terminated, truncated, info

    def render(self):
        congestion = self.state[: self.num_stations]
        critical = np.where(congestion > 0.75)[0]
        print(f"Step {self.step_count:03d} | Mean congestion: {np.mean(congestion):.3f}"
              f" | Critical: {len(critical)} stations")


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    env = RailwayEnv()
    obs, _ = env.reset()
    print(f"✅ RailwayEnv ready | Obs shape: {obs.shape} | Actions: {env.action_space.n}")
    print(f"   Stations: {env.num_stations}")

    total_reward = 0.0
    for _ in range(10):
        action = env.action_space.sample()
        obs, reward, done, _, info = env.step(action)
        total_reward += reward
        env.render()
        if done:
            break

    print(f"\n10-step total reward: {total_reward:.3f}")