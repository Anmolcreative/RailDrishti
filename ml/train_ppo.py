"""
RailDrishti — train_ppo.py
Trains PPO agent on RailwayEnv using stable-baselines3.

Install:  pip install stable-baselines3 gymnasium
Run:      python train_ppo.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.callbacks import EvalCallback
from environment.railway_env import RailwayEnv


if __name__ == "__main__":
    print("🚂 RailDrishti — PPO Training")
    print("─" * 40)

    # Create environment
    env = make_vec_env(RailwayEnv, n_envs=4)

    # PPO agent
    model = PPO(
        "MlpPolicy",
        env,
        verbose=1,
        learning_rate=3e-4,
        n_steps=512,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        ent_coef=0.01,
        tensorboard_log="./logs/ppo_raildrishti/",
    )

    print("\n📉 Training for 20,000 timesteps ...")
    model.learn(total_timesteps=20_000)

    os.makedirs("model", exist_ok=True)
    model.save("model/ppo_raildrishti")
    print("\n✅ PPO model saved → model/ppo_raildrishti.zip")

    # Quick eval
    print("\n🔍 Evaluating ...")
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
    print("✅ PPO training complete!")