"""
reward_calculator.py — Reward shaping for rail delay management RL.
Combines time-saved, cascade prevention, and safety penalties.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import numpy as np

from ml.config import (
    REWARD_TIME_SAVED_PER_MIN,
    REWARD_CASCADE_PREVENTED,
    REWARD_ON_TIME_BONUS,
    PENALTY_CANCELLED_TRAIN,
    PENALTY_SAFETY_VIOLATION,
)

logger = logging.getLogger(__name__)


@dataclass
class RewardComponents:
    """Breakdown of reward for interpretability."""
    time_saved_reward: float = 0.0
    cascade_prevented_reward: float = 0.0
    on_time_bonus: float = 0.0
    intervention_cost: float = 0.0
    cancelled_train_penalty: float = 0.0
    safety_penalty: float = 0.0
    total: float = 0.0

    def compute_total(self):
        self.total = (
            self.time_saved_reward
            + self.cascade_prevented_reward
            + self.on_time_bonus
            + self.intervention_cost
            + self.cancelled_train_penalty
            + self.safety_penalty
        )
        return self.total

    def to_dict(self) -> dict:
        return {
            "time_saved": round(self.time_saved_reward, 3),
            "cascade_prevented": round(self.cascade_prevented_reward, 3),
            "on_time_bonus": round(self.on_time_bonus, 3),
            "intervention_cost": round(self.intervention_cost, 3),
            "cancelled_penalty": round(self.cancelled_train_penalty, 3),
            "safety_penalty": round(self.safety_penalty, 3),
            "total": round(self.total, 3),
        }


class RewardCalculator:
    """
    Computes shaped reward for each environment step.
    Reward = time saved + cascade prevention - intervention cost - penalties.
    """

    # Intervention costs (encourage minimal interventions)
    INTERVENTION_COSTS = {
        "hold": 0.0,
        "speed_up": -0.5,
        "priority_path": -1.0,
        "reschedule": -1.5,
        "notify_crew": -0.3,
        "reroute": -3.0,
        "cancel_halt": -2.0,
        "extend_platform": -1.0,
    }

    def __init__(self):
        self._prev_delays: Dict[str, float] = {}
        self._prev_cascade_stations: Set[str] = set()
        self._step_rewards: List[float] = []
        self._episode_reward: float = 0.0

    def compute(
        self,
        prev_delays: Dict[str, float],
        curr_delays: Dict[str, float],
        action_taken: str,
        action_station: str,
        prev_cascade: Set[str],
        curr_cascade: Set[str],
        cancelled_trains: Optional[List[str]] = None,
        safety_violations: int = 0,
    ) -> RewardComponents:
        """
        Compute reward for one step.

        Args:
            prev_delays: delays before action
            curr_delays: delays after action
            action_taken: action name from PPOTrainer.ACTION_NAMES
            action_station: station where action was applied
            prev_cascade: cascading stations before action
            curr_cascade: cascading stations after action
            cancelled_trains: list of cancelled train IDs (penalty)
            safety_violations: number of safety constraint breaches
        """
        rc = RewardComponents()

        # 1. Time-saved reward: sum of delay reduction across all stations
        total_delay_reduction = 0.0
        on_time_count = 0
        for stn, prev_d in prev_delays.items():
            curr_d = curr_delays.get(stn, prev_d)
            reduction = prev_d - curr_d
            total_delay_reduction += max(0.0, reduction)
            if prev_d > 0 and curr_d <= 0:
                on_time_count += 1

        rc.time_saved_reward = total_delay_reduction * REWARD_TIME_SAVED_PER_MIN

        # 2. Cascade prevention reward
        cascades_prevented = len(prev_cascade - curr_cascade)
        rc.cascade_prevented_reward = cascades_prevented * REWARD_CASCADE_PREVENTED

        # 3. On-time bonus (trains returning to schedule)
        rc.on_time_bonus = on_time_count * REWARD_ON_TIME_BONUS

        # 4. Intervention cost
        rc.intervention_cost = self.INTERVENTION_COSTS.get(action_taken, -1.0)

        # 5. Cancelled train penalty
        n_cancelled = len(cancelled_trains) if cancelled_trains else 0
        rc.cancelled_train_penalty = n_cancelled * PENALTY_CANCELLED_TRAIN

        # 6. Safety violation penalty
        rc.safety_penalty = safety_violations * PENALTY_SAFETY_VIOLATION

        rc.compute_total()

        self._step_rewards.append(rc.total)
        self._episode_reward += rc.total

        return rc

    def compute_from_states(
        self,
        prev_state,   # SyntheticDelayState
        curr_state,   # SyntheticDelayState
        action_name: str,
        action_station: str,
    ) -> RewardComponents:
        """
        Convenience: compute reward from two SyntheticDelayState objects.
        """
        prev_cascade = {
            e.station_code for e in prev_state.delay_events if e.cause == "cascade"
        }
        curr_cascade = {
            e.station_code for e in curr_state.delay_events if e.cause == "cascade"
        }
        return self.compute(
            prev_delays=prev_state.station_delays,
            curr_delays=curr_state.station_delays,
            action_taken=action_name,
            action_station=action_station,
            prev_cascade=prev_cascade,
            curr_cascade=curr_cascade,
        )

    def episode_return(self) -> float:
        return self._episode_reward

    def reset(self):
        """Reset for new episode."""
        self._prev_delays.clear()
        self._prev_cascade_stations.clear()
        self._step_rewards.clear()
        self._episode_reward = 0.0

    @property
    def step_history(self) -> List[float]:
        return list(self._step_rewards)

    @property
    def mean_step_reward(self) -> float:
        return float(np.mean(self._step_rewards)) if self._step_rewards else 0.0