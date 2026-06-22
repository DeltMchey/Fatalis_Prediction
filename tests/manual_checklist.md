# Manual Verification Checklist

Run these checks after any change that touches core paths or dependencies.

## Import Check

- [ ] `python -c "import dearpygui, pymem, lightgbm, sklearn, pandas, numpy, matplotlib, joblib; print('OK')"`
- [ ] `python -c "import ast; ast.parse(open('ai_engine.py').read()); print('Syntax OK')"`
- [ ] `python -c "import ast; ast.parse(open('data_cleaner.py').read()); print('Syntax OK')"`
- [ ] `python -c "import ast; ast.parse(open('train_lgbm.py').read()); print('Syntax OK')"`

## Data Pipeline

- [ ] `python data_cleaner.py` completes without error
- [ ] `data/ML_Ready_Dataset.csv` exists and is non-empty
- [ ] `python train_lgbm.py` completes without error
- [ ] `models/fatalis_ai_model.pkl` exists (~18 MB)
- [ ] `models/feature_importance.png` exists

## Main Program (without game)

- [ ] `python ai_engine.py` prints "未找到游戏进程" (game not found) — not a crash

## Main Program (with game running)

- [ ] `python ai_engine.py` launches transparent overlay
- [ ] Overlay shows: action name, phase, enrage, distance, angle, HP%, AI Top-3
- [ ] Nova warning triggers at correct HP thresholds
- [ ] Combat data CSV is written to `data/` directory

## Git Hygiene

- [ ] `git status` shows only source files and docs (no .venv, no .csv, no .pkl)
- [ ] `.gitignore` excludes data/*.csv and models/*.pkl

## Notes

- Items requiring the game running can be skipped during CI or offline development
- For automated testing, see P3 (Test Safety Net) on the roadmap
