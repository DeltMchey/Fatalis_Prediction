# -*- mode: python ; coding: utf-8 -*-
"""
BlackDragonOverlay.spec — Overlay EXE build specification (PyInstaller).

Build: pyinstaller build/BlackDragonOverlay.spec --clean
Output: dist/BlackDragonOverlay/BlackDragonOverlay.exe

Entry: overlay.py (Overlay process — transparent game overlay)
  Spawned by: BlackDragon.exe (Dashboard) via subprocess
  开发模式: python overlay.py
  冻结模式: BlackDragonOverlay.exe（由 BlackDragon.exe 启动）

Excludes Dashboard-specific modules (src/dashboard, src/app/controller,
src/app/game_service, src/bootstrap) to reduce bundle size.
"""

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent if 'SPECPATH' in dir() else Path('.')

# ---- Bundled data resources ----
datas = [
    # AI model (17.6 MB) — used by ActionPredictor at runtime
    (str(PROJECT_ROOT / 'models' / 'fatalis_ai_model.pkl'), 'models'),
]

# ---- Native binaries ----
binaries = []

# ---- Hidden imports ----
# Overlay process: core + model + data + ui (no dashboard/bootstrap)
hiddenimports = [
    # DearPyGui
    'dearpygui._dearpygui',
    # LightGBM
    'lightgbm', 'lightgbm.basic', 'lightgbm.callback', 'lightgbm.sklearn',
    # scikit-learn edge cases
    'sklearn.utils._typedefs', 'sklearn.utils._vector_sentinel',
    # pandas internals
    'pandas._libs.tslibs',
    # Project packages (Overlay process)
    'src.core.state_tracker', 'src.core.memory_reader',
    'src.model.predictor', 'src.data.recorder',
    'src.ui.overlay', 'src.ui.fonts',
    'src.app.config',
    'src.config.actions', 'src.config.offsets',
    'src.logging_config',
]

# ---- Exclude Dashboard-only modules (size reduction) ----
excludes = [
    'src.dashboard',
    'src.bootstrap',
    'src.app.controller',
    'src.app.game_service',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_gtk3agg',
]

a = Analysis(
    [str(PROJECT_ROOT / 'overlay.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BlackDragonOverlay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX disabled — DPG/GLFW DLL may break under compression
    console=False,      # Windowed app — DPG creates its own window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='BlackDragonOverlay',
)
