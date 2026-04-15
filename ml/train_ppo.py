"""
RailDrishti — train_ppo.py
Trains PPO agent on RailwayEnv using stable-baselines3.
Install: pip install stable-baselines3 gymnasium
Run: python train_ppo.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import EvalCallback
from environment.railway_env import RailwayEnv


def train_ppo(
    total_timesteps=20_000,
    n_envs=4,
    learning_rate=3e-4,
    batch_size=64,
    n_epochs=10,
    tensorboard_log='./logs/ppo_raildrishti/',
):
    print("RailDrishti PPO Training")
    print("-" * 40)

    env = make_vec_env(RailwayEnv, n_envs=n_envs)
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=learning_rate,
        n_steps=512,
        batch_size=batch_size,
        n_epochs=n_epochs,
        gamma=0.99,
        ent_coef=0.01,
        tensorboard_log=tensorboard_log,
    )

    print(f"\nTraining for {total_timesteps:,} timesteps ...")
    model.learn(total_timesteps=total_timesteps)

    os.makedirs('model', exist_ok=True)
    model_path = 'model/ppo_raildrishti'
    model.save(model_path)
    print(f"\nPPO model saved -> {model_path}.zip")

    print("\nEvaluating ...")
    eval_env = RailwayEnv()
    obs, _ = eval_env.reset()
    total_reward = 0.0
    for step in range(100):
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, done, _, info = eval_env.step(int(action))
        total_reward += reward
        if step % 20 == 0:
            print(f"  Step {step:03d} | Reward: {reward:.3f} | Critical: {info['critical_stations']}")
        if done:
            break

    print(f"\n  100-step total reward: {total_reward:.3f}")
    print("PPO training complete!")


if __name__ == "__main__":
    train_ppo()
