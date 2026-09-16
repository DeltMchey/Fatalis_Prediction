# Project Brief — BlackDragon

## Identity

BlackDragon (黑龙) is an AI-assisted hunting overlay tool for **Monster Hunter World (MHW)**, designed specifically for the endgame boss **Fatalis (黑龙)**.

## Core Purpose

Predict Fatalis's next attack in real-time and display it as a transparent in-game overlay, helping players anticipate and react to the boss's moves.

## What It Does

1. **Reads game memory** — Uses `pymem` to read MonsterHunterWorld.exe process memory directly (not screen capture)
2. **Records combat data** — Writes real-time combat state to CSV files (~10 rows/sec)
3. **Trains an ML model** — XGBoost pipeline (AutoML-selected Run B config, 12 engineered features) predicts next action from current state; one-click retrain in seconds
4. **Predicts in real-time** — Loads the trained model, runs inference every 0.5s, displays Top-3 predictions
5. **Applies game-rule filters** — Post-processing with phase/posture constraints ensures predictions are physically possible
6. **Warns of Nova (飞天火)** — HP-threshold-based alert for the boss's ultimate attack

## Key Metrics

| Metric | Value |
|--------|-------|
| Training samples | 2444 rows / 19 sessions (factory dataset; user recordings merge on retrain) |
| Input features | 6 (distance, angle, posture, prev_action, phase, enrage) → 12 engineered in-pipeline |
| Model | XGBoost pipeline (AutoML Run B: 190 trees, single-threaded inference) |
| Accuracy (holdout) | top1 **32.58%** / top3 raw **66.19%** / **top3 hard-filtered 65.37%** (v1.1: 27.05 / 60.25 / 58.81%) |
| Model file | `fatalis_ai_model.pkl` (~7.5 MB) + immutable `factory_model.pkl` rollback copy |
| Inference rate | Every 0.5s, p95 4.31ms, ~2% CPU |
| Overlay | dearpygui transparent window, 420×350, top-right corner |

## Current Status

BlackDragon v1.2.0 (P6.1 AutoML Model Migration). Production model is an AutoML-selected XGBoost pipeline (FLAML Run B) adopted through a gated benchmark process. One-click training (`python launch.py --pipeline` or Dashboard button) retrains the winning config on the user's merged recordings in seconds, with two-generation backup chains, an immutable factory model, training gates, and per-run logs. Frozen EXE distribution includes `--selftest` diagnostics and the build gates on it. 766 tests, 86% overall coverage. Experiment branch merged to main; push/GitHub Release pending user decision.
