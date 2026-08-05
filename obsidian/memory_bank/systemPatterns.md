# System Patterns — BlackDragon

## Architecture Pattern

**Dual-Process Architecture** (P5.3, ADR-P5.2) + pipeline data flow with file-system coupling between offline stages.

```
┌──────────────────────────────────────────────────────────────┐
│ Process 1: python launch.py / BlackDragon.exe (Dashboard)    │
│   └─ DPG event loop (Dashboard.run)                          │
│       └─ GameService daemon → attach P4 modules              │
│       └─ spawns Process 2 via subprocess                     │
└───────────────────────────┬──────────────────────────────────┘
                            │ subprocess.Popen
┌───────────────────────────▼──────────────────────────────────┐
│ Process 2: python overlay.py / BlackDragonOverlay.exe        │
│   └─ DPG event loop (OverlayUI.run) — independent context    │
│       └─ MemoryReader → StateTracker → Predictor → Overlay   │
└───────────────────────────┬──────────────────────────────────┘
                            │ (offline, via filesystem)
                            ▼
    CSV files → data_cleaner.py → ML_Ready_Dataset.csv
              → train_lgbm.py → fatalis_ai_model.pkl → joblib.load
```

## Core Design Patterns

### 1. Action Aliasing (动作合并映射)

**Pattern**: Many-to-one mapping from animation frame IDs to base action IDs.

```
Raw action_id (per-frame) → ACTION_MAPPING → Base action_id (semantic)
38, 39, 40 → 37 (龙车/Dragon Charge)
54, 55, 56, 57 → 53 (连咬/Bite Combo)
```

**Why**: The game engine exposes per-animation-frame IDs. Without aliasing, the model would learn "fake transitions" within the same attack. Found in `ai_engine.py:48-60` and `data_cleaner.py:15-45` (duplicated — known tech debt).

### 2. Posture State Machine (姿态状态机)

**Pattern**: Finite state machine tracking monster posture across action transitions.

```
States: {0=Prone(趴下), 1=Standing(站立), 2=Flying(飞行), 3=Downed(倒地), 4=Scripted(演出)}
Initial: 1 (Standing)
Transitions: Triggered by specific action IDs
```

**Why**: Posture gates which attacks are physically possible. The model output is filtered by posture before display.

### 3. Two-Layer Prediction (双层预测)

**Pattern**: ML probability distribution → game-rule hard filter → renormalization → Top-3.

```
Step 1: model.predict_proba(features)  →  P[all_actions]
Step 2: Phase filter (P1-only → 0 in P2/P3, etc.)
Step 3: Posture filter (prone-only → 0 when standing, etc.)
Step 4: Renormalize (P /= sum(P))
Step 5: Top-3 (argsort, prob > 3%)
```

**Why**: Pure ML can output physically impossible predictions. The hard filter guarantees legitimacy. This is the project's key innovation.

### 4. Hardware-Level Enrage Detection (物理级发怒检测)

**Pattern**: Read the engine's internal enrage timer directly from `monster + 0x1BE30`.

```
enrage_timer = read_float(monster + 0x1BE30 + 0x24)
enrage_max   = read_float(monster + 0x1BE30 + 0x28)
is_enraged   = 0 < enrage_timer < enrage_max
```

**Why**: Replaces the old soft-timer approach (roar action → +180s) with frame-precise detection. Discovered via `enrage.py` memory scanner.

## Data Flow Pattern

```
[Recording]  0.1s per row → fatalis_combat_data_*.csv
                              (8 columns: timestamp, hp%, phase, enrage, distance, angle, posture, action_id)

[Cleaning]   Per-frame CSV → ACTION_MAPPING → Posture FSM → Transition extraction
                              Output: ML_Ready_Dataset.csv
                              (7 columns: distance, angle, posture, prev_action, phase, enrage → next_action)

[Training]   ML_Ready_Dataset.csv → LightGBM (6 features, multiclass) → .pkl model

[Pipeline]   `launch.py --pipeline` = Cleaning → Training (一键流程)
              Unknown actions (not in ACTION_DB) filtered with warning at both stages

[Inference]  Live memory → 6 features → predict_proba() → filter → Top-3 → overlay
```

## Process / Thread Model

```
Process 1: Dashboard (launch.py / BlackDragon.exe)
  ├─ Main thread: dearpygui render loop (Dashboard.run) — status/log/training refresh
  ├─ GameService daemon: 2s poll game process → attach/detach P4 modules
  ├─ CombatRecorder daemon: 0.1s record frames → CSV (when attached)
  ├─ (subprocess) BlackDragonOverlay.exe
  └─ (subprocess) BlackDragon.exe --pipeline  ← v1.1: one-click clean+train (button triggered)

Process 2: Overlay (overlay.py / BlackDragonOverlay.exe)
  ├─ Main thread: dearpygui render loop (OverlayUI.run) — update_logic every frame
  │    └─ read memory → state update → AI prediction (every 0.5s) → render overlay
  └─ CombatRecorder daemon: 0.1s record frames → CSV

Shared state (per-process, no cross-process IPC):
  - state_tracker.is_recording (independent per process)
  - action_buffer deque + lock (within process, recorder → UI)
  - config: each process loads blackdragon_config.json independently
  - CSV: each process writes independent files to data/
```

**Why dual-process**: DPG 2.x / GLFW requires window creation on the main thread only; one process cannot host two DPG contexts. Process isolation (ADR-P5.2) gives each its own DPG context + main thread.

## Key Constants

| Constant | Value | Meaning |
|----------|-------|---------|
| Zone ID | 417 | Fatalis arena (虚黑城) |
| Nova thresholds | 78%, 50%, 41%, 26%, 6% | HP% for Nova warnings |
| Phase thresholds | >78%=P1, 50-78%=P2, <50%=P3 | Fight phase by HP |
| Monster min HP | 500 | Used to identify monster entity |
| Max monster slots | 10 | Searched to find Fatalis instance |
| Action buffer size | 100 | Rolling window of recent actions |
| Inference interval | 0.5s | Time between AI predictions |
| Recording interval | 0.1s | Time between CSV rows |
