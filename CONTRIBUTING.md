# Contributing to BlackDragon

Thank you for your interest in contributing! BlackDragon is an AI-assisted hunting overlay for Monster Hunter World.

## Project Overview

BlackDragon uses **dual-process architecture** (P5.3):
- **Dashboard Process** (`launch.py`) — control center UI
- **Overlay Process** (`overlay.py`) — transparent in-game prediction window

Full architecture documentation: [`obsidian/Architecture/System_Architecture.md`](obsidian/Architecture/System_Architecture.md)

## Development Environment

### Requirements

- **Windows** (required — pymem and dearpygui are Windows-only)
- **Python 3.11+**
- **Monster Hunter World** (for runtime testing only — tests run without the game)

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd BlackDragon

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run tests to verify setup
MPLBACKEND=Agg pytest tests/ -q
```

Note: Use `MPLBACKEND=Agg` to avoid matplotlib backend issues on some Windows configurations.

## Testing

All contributions MUST pass the full test suite:

```bash
# Run all tests
MPLBACKEND=Agg pytest tests/ -q

# Run specific test file
MPLBACKEND=Agg pytest tests/test_state_tracker.py -q

# Run with coverage
MPLBACKEND=Agg pytest tests/ -q --cov=src --cov=overlay --cov=launch --cov-report=term
```

Target: 541 tests, 94% overall coverage.

### Test Categories

| Category | Files | What They Test |
|----------|-------|---------------|
| Core Logic | `test_math_logic.py`, `test_phase_filter.py`, `test_nova.py` | Pure mathematical functions |
| P4 Modules | `test_state_tracker.py`, `test_memory_reader.py`, `test_predictor.py`, `test_recorder.py`, `test_overlay.py` | Extracted module APIs |
| P5 Modules | `test_app_config.py`, `test_app_controller.py`, `test_game_service.py`, `test_dashboard.py`, `test_bootstrap_checker.py` | Dashboard/Controller |
| Entry Points | `test_launch.py`, `test_overlay_entry.py`, `test_main_integration.py` | Composition roots |
| Integration | `test_data_cleaner.py`, `test_data_upgrade.py`, `test_train_lgbm.py` | Data pipeline |

## Submitting Issues

Before submitting an issue:

1. Check the [existing issues](issues) to avoid duplicates
2. Use the issue template if available
3. For bugs, include:
   - Python version (`python --version`)
   - Dependencies output (`pip freeze`)
   - Steps to reproduce
   - Expected vs actual behavior
4. For feature requests, describe the use case and expected behavior

## Pull Request Process

1. **Fork** the repository and create a feature branch
2. **Write tests** for new functionality
3. **Ensure all tests pass** (`MPLBACKEND=Agg pytest tests/ -q`)
4. **Update documentation** if needed (obsidian/ docs)
5. **Submit PR** with a clear description of changes

### PR Guidelines

- Keep PRs focused — one feature or fix per PR
- Reference related issues in the description (`Fixes #123`)
- Avoid modifying P4 core modules (`src/core/`, `src/model/`, `src/data/`) unless necessary
- Do not modify legacy files in `archive/` or `obsidian/docs/legacy/` without discussion

## Architecture Constraints

BlackDragon has strict architectural boundaries:

| Layer | Directory | Modification Policy |
|-------|-----------|-------------------|
| **P4 Core** | `src/core/`, `src/model/`, `src/data/` | Frozen — must maintain backward compatibility |
| **P5 UI** | `src/app/`, `src/dashboard/`, `src/bootstrap/` | Open to enhancements |
| **Config** | `src/config/` | Source of truth — changes cascade to all modules |
| **Legacy** | `main.py`, `ai_engine.py` | Reference only — new features target `launch.py` / `overlay.py` |
| **Documentation** | `obsidian/` | Knowledge base v1.0 structure (see `obsidian/docs/legacy/README.md`) |

## Code Style

- Follow existing patterns in the codebase
- Use type hints where practical
- Keep functions under 40 lines where possible
- Use `logging` module for all output (not `print`)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
