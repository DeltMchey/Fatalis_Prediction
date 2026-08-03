# Archive

Deprecated or replaced files preserved for reference.

## Legacy code

- `mod.py` — Original simpler overlay (no AI prediction, no combat recording). Replaced by `ai_engine.py`.
- `enrage.py` — Standalone research tool for enrage struct memory scanning. Superseded by
  `src/core/memory_reader.py` (`read_enrage_state`) + `src/core/state_tracker.py`
  (`update_enrage`). Retained for historical reference only — not part of the runtime,
  not covered by tests.

## Legacy reports

- `legacy_reports/` — Closure reports and execution plans from completed phases
  (P2, P3). Historical documentation only; the authoritative project context lives in
  `obsidian/memory_bank/`.
