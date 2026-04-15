"""
RailDrishti — train_pipeline.py
End-to-end ML pipeline for RailGNN and PPO training using synthetic delay data.
Run: python train_pipeline.py
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from train_gnn import train_gnn
from train_ppo import train_ppo
from train_model import train_model


def main():
    print("RailDrishti ML pipeline")
    print("-" * 50)

    train_gnn(
        epochs=25,
        samples=6000,
        lr=1e-3,
        hidden_dim=64,
        report_every=5,
    )

    train_model()

    train_ppo(
        total_timesteps=30_000,
        n_envs=4,
        learning_rate=3e-4,
        batch_size=64,
        n_epochs=10,
    )


if __name__ == "__main__":
    main()
