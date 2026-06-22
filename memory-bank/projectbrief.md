# Project Brief — BlackDragon

## Identity

BlackDragon (黑龙) is an AI-assisted hunting overlay tool for **Monster Hunter World (MHW)**, designed specifically for the endgame boss **Fatalis (黑龙)**.

## Core Purpose

Predict Fatalis's next attack in real-time and display it as a transparent in-game overlay, helping players anticipate and react to the boss's moves.

## What It Does

1. **Reads game memory** — Uses `pymem` to read MonsterHunterWorld.exe process memory directly (not screen capture)
2. **Records combat data** — Writes real-time combat state to CSV files (~10 rows/sec)
3. **Trains an ML model** — LightGBM multiclass classifier predicts next action from current state
4. **Predicts in real-time** — Loads the trained model, runs inference every 0.5s, displays Top-3 predictions
5. **Applies game-rule filters** — Post-processing with phase/posture constraints ensures predictions are physically possible
6. **Warns of Nova (飞天火)** — HP-threshold-based alert for the boss's ultimate attack

## Key Metrics

| Metric | Value |
|--------|-------|
| Training samples | Thousands (17 recorded hunts) |
| Features | 6 (distance, angle, posture, prev_action, phase, enrage) |
| Model | LightGBM multiclass, ~40-60 action classes |
| Model file | `fatalis_ai_model.pkl` (~18 MB) |
| Inference rate | Every 0.5s, < 5ms per prediction |
| Overlay | dearpygui transparent window, 420×350, top-right corner |

## Current Status

Pre-refactoring monolithic script. All logic in `ai_engine.py` (328 lines). Phase P1 — Project Standardization — is active.
