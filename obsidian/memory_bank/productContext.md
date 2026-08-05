# Product Context — BlackDragon

## Why This Exists

Fatalis (黑龙) is widely regarded as the hardest boss in Monster Hunter World. The fight has:
- 3 phases with different move sets
- Complex posture system (standing/prone/flying)
- An enrage mechanic that changes behavior
- A devastating ultimate attack (Nova/飞天火) at specific HP thresholds

Players struggle to learn the boss's patterns because:
- Same animation frames can lead to different follow-ups depending on context
- Phase transitions change the available move pool
- Posture changes invalidate some predictions

This tool helps by predicting the most likely next attack using ML trained on real fight data.

## Who It's For

Monster Hunter World players fighting Fatalis on PC. Requires the game to be running (`MonsterHunterWorld.exe`).

## How It Works (User Perspective)

### Source / Development Mode

1. Launch the game, enter the Fatalis quest (zone 417 = 虚黑城)
2. Run `python launch.py` — Dashboard control center appears
3. Dashboard auto-spawns `python overlay.py` (or `BlackDragonOverlay.exe` in frozen mode)
4. A transparent overlay appears in the top-right corner showing:
   - Current action name
   - Phase (P1/P2/P3) and enrage status
   - Distance, angle, HP percentage
   - Nova warning (red) when HP crosses a threshold
   - AI Top-3 predictions (green) for the next attack
5. To train/retrain the model from recorded data:
   ```
   python launch.py --pipeline    # 一键数据清洗 + 模型训练（v1.1）
   ```
   Or via the Dashboard: click 「模型训练」 button in the Training tab.

### Windows EXE Distribution

1. Download `BlackDragon-v1.1.0-windows.zip`
2. Extract to any folder
3. Double-click `BlackDragon.exe` — Dashboard appears, Overlay auto-starts
4. No Python environment required — everything bundled

## Constraints

- **Windows only** — depends on Win32 API (ctypes) for overlay transparency and mouse passthrough
- **Game version dependent** — memory offsets are specific to a particular MHW build
- **Chinese font required** — uses `msyh.ttc` (Microsoft YaHei) for Chinese character rendering
- **Must run alongside the game** — reads live process memory, no offline mode

## Known Limitations

- No multi-monster support (hardcoded to find monster with HP > 500 in first 10 slots)
- No multi-player party size tracking
- No weapon-type-specific predictions
- Current model is a single LightGBM classifier (no ensemble)
- No model version management (single hardcoded filename)
- Unknown actions (not in `ACTION_DB`) are filtered during pipeline execution with a warning — legitimate new actions must be added to `src/config/actions.py`
