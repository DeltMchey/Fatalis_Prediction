# -*- mode: python ; coding: utf-8 -*-
"""
BlackDragon.spec — Dashboard EXE build specification (PyInstaller).

Build: pyinstaller build/BlackDragon.spec --clean
Output: dist/BlackDragon/BlackDragon.exe

Entry: launch.py (Dashboard control center)
  开发模式: python launch.py          → spawn `python overlay.py`
  冻结模式: BlackDragon.exe           → spawn `BlackDragonOverlay.exe`
  （controller.start_overlay 通过 sys.frozen 检测运行模式）
"""

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent if 'SPECPATH' in dir() else Path('.')

# ---- Bundled data resources ----
datas = [
    # AI model (17.6 MB) — used by ActionPredictor at runtime
    (str(PROJECT_ROOT / 'models' / 'fatalis_ai_model.pkl'), 'models'),
    # Training dataset (85.8 KB) — used by train_fatalis_ai() via --train mode
    (str(PROJECT_ROOT / 'data' / 'ML_Ready_Dataset.csv'), 'data'),
]

# ---- Native binaries ----
binaries = []

# ---- Hidden imports ----
# DearPyGui: DPG 2.x dynamically loads its C-extension backend
# LightGBM: native lib_lightgbm.dll — must be collected explicitly
# sklearn/pandas: C-extension edge cases
hiddenimports = [
    # DearPyGui
    'dearpygui._dearpygui',
    # LightGBM
    'lightgbm', 'lightgbm.basic', 'lightgbm.callback', 'lightgbm.sklearn',
    # scikit-learn edge cases
    'sklearn.utils._typedefs', 'sklearn.utils._vector_sentinel',
    # pandas internals
    'pandas._libs.tslibs',
    # pymem — lazily imported in game_service._try_attach(); not detected by AST
    'pymem', 'pymem.process',
    # Project packages (Dashboard process)
    'src.core.state_tracker', 'src.core.memory_reader',
    'src.model.predictor', 'src.data.recorder',
    'src.ui.fonts',
    'src.app.config', 'src.app.controller', 'src.app.game_service',
    'src.dashboard.main_window', 'src.dashboard.status_bar',
    'src.dashboard.log_view', 'src.dashboard.training_panel',
    'src.bootstrap.checker',
    'src.config.actions', 'src.config.offsets',
    'src.logging_config',
]

# ---- Exclude unused heavy modules to reduce size ----
excludes = [
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_gtk3agg',
]

a = Analysis(
    [str(PROJECT_ROOT / 'launch.py')],
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
    name='BlackDragon',
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
    name='BlackDragon',
)
