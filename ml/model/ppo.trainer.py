"""
ppo_trainer.py — PPO trainer for rail delay management RL agent.
1M timestep training with TensorBoard logging, checkpoint saving,
and integration with the GNN feature extractor.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from ml.config import (
    PPO_LR, PPO_GAMMA, PPO_EPS_CLIP, PPO_EPOCHS, PPO_BATCH_SIZE,
    PPO_TOTAL_TIMESTEPS, PPO_ROLLOUT_STEPS, PPO_VALUE_COEF,
    PPO_ENTROPY_COEF, PPO_MAX_GRAD_NORM, PPO_GAE_LAMBDA,
    OBS_FEATURE_DIM, MODEL_DIR, TENSORBOARD_DIR,
)

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.distributions import Categorical
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    logger.error("PyTorch required for PPO training")

try:
    from torch.utils.tensorboard import SummaryWriter
    HAS_TB = True
except ImportError:
    HAS_TB = False
    logger.warning("TensorBoard not available — logging to console only")


# ---------------------------------------------------------------------------
# Rollout buffer
# ---------------------------------------------------------------------------

@dataclass
class RolloutBuffer:
    """Stores experience tuples for PPO update."""
    obs: List[np.ndarray] = field(default_factory=list)
    actions: List[int] = field(default_factory=list)
    log_probs: List[float] = field(default_factory=list)
    rewards: List[float] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    dones: List[bool] = field(default_factory=list)
    # Computed after rollout
    advantages: Optional[np.ndarray] = None
    returns: Optional[np.ndarray] = None

    def clear(self):
        self.obs.clear()
        self.actions.clear()
        self.log_probs.clear()
        self.rewards.clear()
        self.values.clear()
        self.dones.clear()
        self.advantages = None
        self.returns = None

    def __len__(self) -> int:
        return len(self.rewards)


# ---------------------------------------------------------------------------
# Actor-Critic network
# ---------------------------------------------------------------------------

if HAS_TORCH:

    class ActorCritic(nn.Module):
        """
        Shared backbone + separate actor/critic heads.
        Input: flattened graph observation (N × 48 → flattened + aggregated)
        """

        def __init__(self, obs_dim: int, n_actions: int, hidden: int = 256):
            super().__init__()
            # Shared feature extractor
            self.backbone = nn.Sequential(
                nn.Linear(obs_dim, hidden),
                nn.LayerNorm(hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden),
                nn.LayerNorm(hidden),
                nn.ReLU(),
            )
            # Actor head
            self.actor = nn.Sequential(
                nn.Linear(hidden, 128),
                nn.ReLU(),
                nn.Linear(128, n_actions),
            )
            # Critic head
            self.critic = nn.Sequential(
                nn.Linear(hidden, 128),
                nn.ReLU(),
                nn.Linear(128, 1),
            )
            self._init_weights()

        def _init_weights(self):
            for module in self.modules():
                if isinstance(module, nn.Linear):
                    nn.init.orthogonal_(module.weight, gain=np.sqrt(2))
                    nn.init.zeros_(module.bias)

        def forward(self, x: "torch.Tensor") -> Tuple["torch.Tensor", "torch.Tensor"]:
            shared = self.backbone(x)
            return self.actor(shared), self.critic(shared)

        def get_action(self, x: "torch.Tensor") -> Tuple["torch.Tensor", "torch.Tensor", "torch.Tensor"]:
            logits, value = self.forward(x)
            dist = Categorical(logits=logits)
            action = dist.sample()
            log_prob = dist.log_prob(action)
            return action, log_prob, value.squeeze(-1)

        def evaluate(
            self, x: "torch.Tensor", actions: "torch.Tensor"
        ) -> Tuple["torch.Tensor", "torch.Tensor", "torch.Tensor"]:
            logits, value = self.forward(x)
            dist = Categorical(logits=logits)
            log_probs = dist.log_prob(actions)
            entropy = dist.entropy()
            return log_probs, value.squeeze(-1), entropy


# ---------------------------------------------------------------------------
# PPO Trainer
# ---------------------------------------------------------------------------

class PPOTrainer:
    """
    Proximal Policy Optimization trainer for rail delay management.
    Trains for PPO_TOTAL_TIMESTEPS (1M) steps with TensorBoard logging.
    """

    # Action space: per-corridor/station operational commands
    ACTION_NAMES = [
        "hold",           # 0: no intervention
        "speed_up",       # 1: allow faster running on clear sections
        "priority_path",  # 2: give priority path at junction
        "reschedule",     # 3: reschedule crossing/halt
        "notify_crew",    # 4: alert crew for compensation
        "reroute",        # 5: reroute via alternate line
        "cancel_halt",    # 6: cancel scheduled halt
        "extend_platform",# 7: extend platform dwell for connection
    ]
    N_ACTIONS = len(ACTION_NAMES)

    def __init__(
        self,
        obs_dim: Optional[int] = None,
        gnn_output_dim: Optional[int] = None,
        device_str: str = "auto",
    ):
        if not HAS_TORCH:
            raise RuntimeError("PyTorch is required for PPO training")

        # Observation: GNN graph embedding (output_dim) + aggregated delay stats
        from ml.config import GNN_OUTPUT_DIM
        self._obs_dim = obs_dim or (GNN_OUTPUT_DIM + 10)  # embedding + 10 delay stats
        self._device = self._get_device(device_str)

        self._model = ActorCritic(self._obs_dim, self.N_ACTIONS).to(self._device)
        self._optimizer = torch.optim.Adam(self._model.parameters(), lr=PPO_LR, eps=1e-5)
        self._buffer = RolloutBuffer()
        self._writer = SummaryWriter(TENSORBOARD_DIR) if HAS_TB else None

        # Training state
        self._total_steps = 0
        self._episode_count = 0
        self._episode_rewards: List[float] = []
        self._current_ep_reward = 0.0

        # Checkpointing
        self._ckpt_dir = Path(MODEL_DIR)
        self._ckpt_dir.mkdir(parents=True, exist_ok=True)
        self._best_reward = float("-inf")

        logger.info(
            f"PPO Trainer initialized — obs_dim={self._obs_dim}, "
            f"n_actions={self.N_ACTIONS}, device={self._device}"
        )

    @staticmethod
    def _get_device(device_str: str) -> "torch.device":
        if device_str == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device_str)

    # ------------------------------------------------------------------
    # Main training loop
    # ------------------------------------------------------------------

    def train(self, env, total_timesteps: int = PPO_TOTAL_TIMESTEPS) -> Dict:
        """
        Train for total_timesteps using PPO.

        Args:
            env: Gymnasium-compatible environment (RailEnvironment)
            total_timesteps: Training budget (default 1M)

        Returns:
            Training history dict
        """
        history = {
            "rewards": [], "policy_loss": [], "value_loss": [],
            "entropy": [], "approx_kl": [], "explained_var": [],
        }

        logger.info(f"Starting PPO training for {total_timesteps:,} timesteps")
        t_start = time.time()

        obs, _ = env.reset()
        obs_t = self._to_tensor(self._process_obs(obs))

        while self._total_steps < total_timesteps:
            # Collect rollout
            self._buffer.clear()
            for _ in range(PPO_ROLLOUT_STEPS):
                with torch.no_grad():
                    action, log_prob, value = self._model.get_action(obs_t)

                next_obs, reward, terminated, truncated, info = env.step(action.item())
                done = terminated or truncated

                self._buffer.obs.append(self._process_obs(obs))
                self._buffer.actions.append(action.item())
                self._buffer.log_probs.append(log_prob.item())
                self._buffer.rewards.append(float(reward))
                self._buffer.values.append(value.item())
                self._buffer.dones.append(done)

                self._current_ep_reward += float(reward)
                self._total_steps += 1

                if done:
                    self._episode_count += 1
                    self._episode_rewards.append(self._current_ep_reward)
                    if self._writer:
                        self._writer.add_scalar("train/ep_reward", self._current_ep_reward, self._total_steps)
                        self._writer.add_scalar("train/ep_count", self._episode_count, self._total_steps)
                    self._current_ep_reward = 0.0
                    obs, _ = env.reset()
                    obs_t = self._to_tensor(self._process_obs(obs))
                else:
                    obs = next_obs
                    obs_t = self._to_tensor(self._process_obs(obs))

                if self._total_steps >= total_timesteps:
                    break

            # Compute advantages
            with torch.no_grad():
                _, last_value = self._model.forward(obs_t)
                last_value = last_value.squeeze(-1).item()

            self._compute_gae(last_value)

            # PPO update
            update_stats = self._ppo_update()
            for k, v in update_stats.items():
                history[k].append(v)

            # Logging
            if self._total_steps % 10_000 == 0:
                mean_reward = np.mean(self._episode_rewards[-20:]) if self._episode_rewards else 0
                elapsed = time.time() - t_start
                fps = self._total_steps / max(elapsed, 1)
                logger.info(
                    f"Step {self._total_steps:,}/{total_timesteps:,} | "
                    f"Episodes: {self._episode_count} | "
                    f"Mean reward: {mean_reward:.2f} | "
                    f"FPS: {fps:.0f}"
                )
                if self._writer:
                    self._writer.add_scalar("train/mean_reward_20ep", mean_reward, self._total_steps)
                    self._writer.add_scalar("train/fps", fps, self._total_steps)
                    for k, v in update_stats.items():
                        self._writer.add_scalar(f"train/{k}", v, self._total_steps)

            # Checkpoint if improved
            if self._episode_rewards:
                recent_reward = np.mean(self._episode_rewards[-10:])
                if recent_reward > self._best_reward:
                    self._best_reward = recent_reward
                    self._save_checkpoint("best")

            # Regular checkpoint every 100k steps
            if self._total_steps % 100_000 == 0:
                self._save_checkpoint(f"step_{self._total_steps}")

        # Final checkpoint
        self._save_checkpoint("final")
        if self._writer:
            self._writer.flush()
            self._writer.close()

        elapsed = time.time() - t_start
        logger.info(
            f"Training complete — {self._total_steps:,} steps in {elapsed:.0f}s | "
            f"Best reward: {self._best_reward:.2f}"
        )
        return history

    def _compute_gae(self, last_value: float):
        """Compute Generalized Advantage Estimation."""
        T = len(self._buffer.rewards)
        advantages = np.zeros(T, dtype=np.float32)
        gae = 0.0

        for t in reversed(range(T)):
            next_value = last_value if t == T - 1 else self._buffer.values[t + 1]
            next_done = self._buffer.dones[t + 1] if t < T - 1 else True
            delta = (
                self._buffer.rewards[t]
                + PPO_GAMMA * next_value * (1 - int(next_done))
                - self._buffer.values[t]
            )
            gae = delta + PPO_GAMMA * PPO_GAE_LAMBDA * (1 - int(next_done)) * gae
            advantages[t] = gae

        self._buffer.advantages = advantages
        self._buffer.returns = advantages + np.array(self._buffer.values, dtype=np.float32)

    def _ppo_update(self) -> Dict[str, float]:
        """Run PPO clipped objective update for PPO_EPOCHS epochs."""
        T = len(self._buffer.rewards)
        obs_arr = np.stack(self._buffer.obs)
        act_arr = np.array(self._buffer.actions)
        old_lp_arr = np.array(self._buffer.log_probs)
        adv_arr = self._buffer.advantages
        ret_arr = self._buffer.returns

        # Normalize advantages
        adv_arr = (adv_arr - adv_arr.mean()) / (adv_arr.std() + 1e-8)

        obs_t = torch.tensor(obs_arr, dtype=torch.float32, device=self._device)
        act_t = torch.tensor(act_arr, dtype=torch.long, device=self._device)
        old_lp_t = torch.tensor(old_lp_arr, dtype=torch.float32, device=self._device)
        adv_t = torch.tensor(adv_arr, dtype=torch.float32, device=self._device)
        ret_t = torch.tensor(ret_arr, dtype=torch.float32, device=self._device)

        stats = {"policy_loss": 0., "value_loss": 0., "entropy": 0., "approx_kl": 0.}

        for _ in range(PPO_EPOCHS):
            indices = np.random.permutation(T)
            for start in range(0, T, PPO_BATCH_SIZE):
                idx = torch.tensor(
                    indices[start: start + PPO_BATCH_SIZE], device=self._device
                )
                log_probs, values, entropy = self._model.evaluate(obs_t[idx], act_t[idx])

                ratio = torch.exp(log_probs - old_lp_t[idx])
                adv_b = adv_t[idx]

                # Clipped policy loss
                p_loss = -torch.min(
                    ratio * adv_b,
                    torch.clamp(ratio, 1 - PPO_EPS_CLIP, 1 + PPO_EPS_CLIP) * adv_b,
                ).mean()

                # Value loss
                v_loss = F.mse_loss(values, ret_t[idx])

                # Total loss
                loss = p_loss + PPO_VALUE_COEF * v_loss - PPO_ENTROPY_COEF * entropy.mean()

                self._optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(self._model.parameters(), PPO_MAX_GRAD_NORM)
                self._optimizer.step()

                with torch.no_grad():
                    approx_kl = ((old_lp_t[idx] - log_probs).mean()).item()

                stats["policy_loss"] += p_loss.item()
                stats["value_loss"] += v_loss.item()
                stats["entropy"] += entropy.mean().item()
                stats["approx_kl"] += approx_kl

        n_updates = PPO_EPOCHS * max(1, T // PPO_BATCH_SIZE)
        return {k: v / n_updates for k, v in stats.items()}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _process_obs(self, obs) -> np.ndarray:
        """
        Convert environment observation to flat PPO input vector.
        obs may be a dict with 'node_features' and 'graph_embedding'.
        """
        if isinstance(obs, dict):
            parts = []
            if "graph_embedding" in obs:
                parts.append(obs["graph_embedding"].flatten())
            if "delay_stats" in obs:
                parts.append(obs["delay_stats"].flatten())
            if parts:
                vec = np.concatenate(parts).astype(np.float32)
                if len(vec) < self._obs_dim:
                    vec = np.pad(vec, (0, self._obs_dim - len(vec)))
                return vec[:self._obs_dim]
        if isinstance(obs, np.ndarray):
            flat = obs.flatten().astype(np.float32)
            if len(flat) < self._obs_dim:
                flat = np.pad(flat, (0, self._obs_dim - len(flat)))
            return flat[:self._obs_dim]
        return np.zeros(self._obs_dim, dtype=np.float32)

    def _to_tensor(self, arr: np.ndarray) -> "torch.Tensor":
        return torch.tensor(arr, dtype=torch.float32, device=self._device).unsqueeze(0)

    def _save_checkpoint(self, tag: str):
        path = self._ckpt_dir / f"ppo_{tag}.pt"
        torch.save({
            "model_state": self._model.state_dict(),
            "optimizer_state": self._optimizer.state_dict(),
            "total_steps": self._total_steps,
            "episode_count": self._episode_count,
            "best_reward": self._best_reward,
            "obs_dim": self._obs_dim,
            "n_actions": self.N_ACTIONS,
        }, path)
        logger.debug(f"Checkpoint saved: {path}")

    def load_checkpoint(self, path: str) -> "PPOTrainer":
        ckpt = torch.load(path, map_location=self._device)
        self._model.load_state_dict(ckpt["model_state"])
        self._optimizer.load_state_dict(ckpt["optimizer_state"])
        self._total_steps = ckpt.get("total_steps", 0)
        self._episode_count = ckpt.get("episode_count", 0)
        self._best_reward = ckpt.get("best_reward", float("-inf"))
        logger.info(f"Checkpoint loaded: {path} (step {self._total_steps:,})")
        return self

    def get_action(self, obs) -> int:
        """Inference-time action selection (greedy)."""
        if not HAS_TORCH:
            return 0
        self._model.eval()
        with torch.no_grad():
            obs_t = self._to_tensor(self._process_obs(obs))
            logits, _ = self._model.forward(obs_t)
            return int(logits.argmax(dim=-1).item())

    @property
    def action_names(self) -> List[str]:
        return self.ACTION_NAMES

    @property
    def stats(self) -> dict:
        return {
            "total_steps": self._total_steps,
            "episode_count": self._episode_count,
            "best_reward": round(self._best_reward, 2),
            "obs_dim": self._obs_dim,
            "n_actions": self.N_ACTIONS,
        }