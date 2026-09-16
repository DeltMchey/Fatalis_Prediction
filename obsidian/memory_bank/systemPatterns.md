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
    CSV files → data_cleaner.py (merge semantics) → ML_Ready_Dataset.csv
              → src/model/production_backend.py (Run B XGBoost)
              → fatalis_ai_model.pkl → joblib.load
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

### 5. Two-Generation Backup Chain + Factory Model (两代备份链 + 出厂模型回滚层, v1.2.0)

**Pattern**: All destructive writes (model AND dataset) go through `promote_with_backup()` in `src/core/backup_chain.py`: write to `.tmp` → atomic replace → rotate the target into a two-generation chain.

```
promote_with_backup(tmp, target, generations=2)
  → target            (new content, atomically promoted)
  → target.bak        (previous version)
  → target.bak2       (version before that)
  → same-sha skip: if tmp sha == target sha, rotation is skipped entirely

Rollback ladder (user view):
  factory_model.pkl   (immutable shipped copy, never touched by training)
  → fatalis_ai_model.pkl.bak  → .bak2
  dataset: same chain, or delete + rebuild byte-identically from 19 shipped raw CSVs
```

**Why**: The v3 preview incident (recording 1 fight silently replaced the shipped 19-session dataset with a 164-row single session) exposed silent data loss. Same-sha skip matters because Run B is deterministic — retraining unchanged data produces a bit-identical model and must not consume the backup. The factory copy deliberately avoids the `.bak` name: `.bak` is the first runtime generation and would be pushed forward on the first retrain; "factory" and "previous version" cannot share one slot.

### 6. Dataset Merge Semantics (数据集合并语义, v1.2.0)

**Pattern**: When rebuilding `ML_Ready_Dataset.csv`, `data_cleaner.py` keeps rows whose `source_session` is NOT among the on-disk CSVs, then re-extracts and appends sessions that ARE present.

```
rebuild:
  keep   = old_df[~old_df.source_session.isin(on_disk_sessions)]   # history preserved
  output = keep + re-extract(on_disk_sessions)
  guarantee: all CSVs present → output byte-identical to factory dataset
  legacy format (no source_session column) → no merge, warn, stays in backup chain
```

**Why**: Users record new fights incrementally; a full-replace cleaner would discard every shipped session not currently on disk. Merge semantics make "record one fight → one-click retrain" safe by construction, with the byte-identical guarantee acting as the regression anchor.

### 7. Selftest Build Gate (--selftest 构建门禁, v1.2.0)

**Pattern**: Both frozen EXEs expose `--selftest`: resolve paths → load the real model → run one predict → exit 0/1. `scripts/build_exe.ps1` step 7 runs both EXEs and fails the build on any non-zero exit; Overlay runs with CWD=TEMP to cover the frozen-path/CWD scenario.

```
BlackDragon.exe --selftest        (CWD = project root)  → exit 0
BlackDragonOverlay.exe --selftest (CWD = TEMP)          → exit 0
implementation trap: PowerShell & exe does not wait for GUI-subsystem
processes → $LASTEXITCODE is stale → must use Start-Process -Wait -PassThru
```

**Why**: The old "alive for 10s" smoke test could never observe model-load failures — the load happens after game attach and failures were silently swallowed. Selftest exercises the exact frozen import chain (incl. dynamically-referenced `sklearn.pipeline` inside the pickle) in the real EXE process.

### 8. Deterministic Training Backend (确定性训练后端, v1.2.0)

**Pattern**: `src/model/production_backend.py` mirrors the FLAML winner's (Run B) training semantics bit-for-bit in first-class code: stratified split (random_state=42) → FeatureBuilder fit on train_80 only (leak red line) → rare-class auto_augment mirror (<20-sample classes row-copied, 1949→2175) → shuffle(random_state=1) → XGBClassifier(RUNB_BEST_CONFIG, n_jobs=1, no random_state) → LabelDecodedEstimator → sklearn Pipeline → `.tmp` + promote_with_backup.

```
--pipeline = data_cleaner (merge semantics) → production_backend (Run B retrain)
--train    = legacy train_lgbm (LightGBM), kept for backward compatibility
observability: data summary line (📊 sessions/rows/classes vs previous),
⚠ destructive-change warnings (only warn, never block), tee to train_*.log (keep 10)
```

**Why**: One-click training must reproduce the adopted model exactly (missing the augment/shuffle mirror shifts top3 by +0.6pp). Encapsulating the pipeline inside the sklearn Pipeline (6 raw features in, 12 columns internally) keeps `ActionPredictor.predict`'s 6-arg contract unchanged for Dashboard/Overlay.

## Data Flow Pattern

```
[Recording]  0.1s per row → fatalis_combat_data_*.csv
                              (8 columns: timestamp, hp%, phase, enrage, distance, angle, posture, action_id)

[Cleaning]   Per-frame CSV → ACTION_MAPPING → Posture FSM → Transition extraction
                              + merge semantics (keep sessions not on disk, v1.2.0)
                              Output: ML_Ready_Dataset.csv
                              (8 columns: distance, angle, posture, prev_action, phase, enrage,
                               next_action, source_session)

[Training]   ML_Ready_Dataset.csv → production_backend.py (Run B XGBoost, 12 columns via
              FeatureBuilder, deterministic) → .pkl + backup chain + sidecar
              legacy: train_lgbm.py (LightGBM, 6 features) via --train

[Pipeline]   `launch.py --pipeline` = data_cleaner (merge) → production_backend (一键流程)
              Unknown actions (not in ACTION_DB) filtered with warning at both stages

[Inference]  Live memory → 6 features → Pipeline.predict_proba (12 columns internally)
              → filter → Top-3 → overlay
```

## Process / Thread Model

```
Process 1: Dashboard (launch.py / BlackDragon.exe)
  ├─ Main thread: dearpygui render loop (Dashboard.run) — status/log/training refresh
  ├─ GameService daemon: 2s poll game process → attach/detach P4 modules
  ├─ CombatRecorder daemon: 0.1s record frames → CSV (when attached)
  ├─ (subprocess) BlackDragonOverlay.exe
  └─ (subprocess) BlackDragon.exe --pipeline  ← one-click clean+train (v1.2: data_cleaner
                                                 merge → production_backend Run B retrain)

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
