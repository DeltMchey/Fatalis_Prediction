# Memory Offsets Guide

> How to update BlackDragon when Monster Hunter World receives a game patch.

## Overview

All memory offsets are defined in **one file**: `src/config/offsets.py`. When the game updates, you only need to modify that file — no source code changes required.

## Offset Categories

### 1. Base Addresses

These are the module-relative starting points for three critical entities:

```python
PLAYER_BASE  = 0x050139A0   # Start of player data chain
MONSTER_BASE = 0x051238C8   # Start of monster list
ZONE_BASE    = 0x0500ECA0   # Start of zone data
```

**How to find them after an update:**
- Use Cheat Engine to scan for known values near these addresses
- The player base leads to player coordinates (floating-point XYZ)
- The monster base leads to the monster entity list (typically 10 slots)
- The zone base leads to a zone ID integer (417 = Fatalis arena)

### 2. Monster Entity Chain

```python
MONSTER_LIST_FIRST    = 0x698   # First offset to monster list
MONSTER_LIST_STRIDE   = 0x8     # Byte stride between monster slots
MONSTER_LIST_NEXT     = 0x138   # Dereference offset to next pointer
MONSTER_LIST_TERMINAL = 0       # Terminal offset (zero means "stop here")
```

Path: `[MONSTER_BASE] → +0x698 → [i * 0x8] → +0x138 → [0]`

### 3. Monster Data Offsets

Once you have a monster pointer, these offsets give you its properties:

| Offset | Type | Meaning |
|--------|------|---------|
| `MONSTER_HP_BASE` (0x7670) | ptr | Pointer to HP structure |
| `HP_MAX` (0x60) | float | Maximum HP (from HP pointer) |
| `HP_CURRENT` (0x64) | float | Current HP (from HP pointer) |
| `MONSTER_COORDS` (0x160) | float×3 | World position (X, Y, Z) |
| `MONSTER_QUAT` (0x170) | float×4 | Rotation quaternion |
| `MONSTER_ACTION_ID` (0x6278) | int32 | Current animation/action ID |

### 4. Enrage Structure

Found via reverse engineering with `enrage.py`:

```python
ENRAGE_STRUCT = 0x1BE30   # Base offset to enrage data
ENRAGE_TIMER  = 0x24      # Current enrage timer (float, counts down)
ENRAGE_MAX    = 0x28      # Max enrage duration (float, constant)
```

Detection logic: the monster is enraged when `0 < ENRAGE_TIMER < ENRAGE_MAX`.

### 5. Player Data Chain

```python
PLAYER_CHAIN_1 = 0x50
PLAYER_CHAIN_2 = 0xC0
PLAYER_COORDS  = 0x670   # Player position (float×3)
```

Path: `[PLAYER_BASE] → +0x50 → +0xC0 → +0x670`

### 6. Zone Detection

```python
ZONE_OFFSET = 0xAED0   # Offset to zone ID integer
ZONE_FATALIS = 417     # Fatalis arena (虚黑城)
```

### 7. Combat Parameters

```python
MONSTER_MAX_SLOTS = 10     # Game spawns at most 10 large monsters
MONSTER_MIN_HP   = 500.0   # Used to identify Fatalis among monster slots
```

## Update Procedure

1. **Launch the game** and enter the Fatalis quest (zone 417)
2. **Use Cheat Engine** to locate the new base addresses
3. **Update `src/config/offsets.py`** with the new values
4. **Verify**: `python ai_engine.py` should display correct monster data
5. **If action IDs changed**: also update `src/config/actions.py`

## Tools

- `enrage.py` — Live memory scanner for discovering enrage struct layout
- Cheat Engine ([cheatengine.org](https://www.cheatengine.org/)) — General-purpose memory scanner

## Notes

- Offsets are specific to the **PC (Steam) version** of Monster Hunter World
- Major game updates (e.g., Iceborne expansion) may require full re-discovery
- Minor patches typically only shift base addresses; internal offsets often stay the same
- If the model's Top-3 accuracy drops significantly after an update, verify the action ID mapping in `actions.py`
