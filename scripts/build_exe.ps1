# =============================================================================
# build_exe.ps1 — Build BlackDragon EXEs with PyInstaller
#
# Usage:
#   .\scripts\build_exe.ps1                # Build both EXEs + merge
#   .\scripts\build_exe.ps1 -Clean         # Clean build artifacts first
#   .\scripts\build_exe.ps1 -SkipTests     # Skip pytest verification
#
# Output:
#   dist/BlackDragon/
#   ├── BlackDragon.exe                   (Dashboard)
#   ├── BlackDragonOverlay.exe            (Overlay — merged from separate build)
#   ├── models/                           (bundled AI model)
#   └── ...                               (dependencies)
#
# Requirements:
#   pip install pyinstaller (in venv)
#   Uses: python -m PyInstaller (venv-safe, not global pyinstaller)
# =============================================================================

param(
    [switch]$Clean,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

# Prefer the project venv python if present; fall back to PATH python.
# Bare `python` on Windows may resolve to the Store stub (no site-packages).
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
    Write-Host "  venv python not found — using PATH python" -ForegroundColor Yellow
} else {
    Write-Host "  Using venv python: $Python" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 0. Preconditions
# ---------------------------------------------------------------------------
Write-Host "[1/6] Verifying PyInstaller in venv..." -ForegroundColor Cyan
try {
    & $Python -m PyInstaller --version 2>&1 | Out-Null
} catch {
    Write-Error "PyInstaller not installed. Run: pip install pyinstaller"
    exit 1
}

# ---------------------------------------------------------------------------
# 1. Verify tests pass (unless skipped)
# ---------------------------------------------------------------------------
if (-not $SkipTests) {
    Write-Host "[2/6] Running test suite..." -ForegroundColor Cyan
    $env:MPLBACKEND = "Agg"
    & $Python -m pytest tests/ -q
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Tests failed — aborting build."
        exit 1
    }
} else {
    Write-Host "[2/6] Skipping tests (-SkipTests)" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 2. Clean previous build (if requested)
# ---------------------------------------------------------------------------
if ($Clean) {
    Write-Host "[3/6] Cleaning previous build artifacts..." -ForegroundColor Cyan
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build/BlackDragon
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build/BlackDragonOverlay
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist/BlackDragon
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue dist/BlackDragonOverlay
} else {
    Write-Host "[3/6] Keeping previous build artifacts (use -Clean to clean)" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 3. Build Dashboard EXE (BlackDragon.exe)
# ---------------------------------------------------------------------------
Write-Host "[4/6] Building BlackDragon.exe (Dashboard)..." -ForegroundColor Cyan
# PyInstaller writes INFO to stderr; PowerShell 5.1 treats stderr as error
# under $ErrorActionPreference=Stop. Temporarily relax for the native call.
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Python -m PyInstaller build/BlackDragon.spec --noconfirm 2>$null
$ErrorActionPreference = $prevEAP
if ($LASTEXITCODE -ne 0) {
    Write-Error "Dashboard EXE build failed."
    exit 1
}

# ---------------------------------------------------------------------------
# 4. Build Overlay EXE (BlackDragonOverlay.exe)
# ---------------------------------------------------------------------------
Write-Host "[5/6] Building BlackDragonOverlay.exe (Overlay)..." -ForegroundColor Cyan
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $Python -m PyInstaller build/BlackDragonOverlay.spec --noconfirm 2>$null
$ErrorActionPreference = $prevEAP
if ($LASTEXITCODE -ne 0) {
    Write-Error "Overlay EXE build failed."
    exit 1
}

# ---------------------------------------------------------------------------
# 5. Merge: copy Overlay exe into Dashboard dist (same directory)
# ---------------------------------------------------------------------------
Write-Host "[6/6] Merging EXEs into dist/BlackDragon/..." -ForegroundColor Cyan
$OverlaySrc = Join-Path $ProjectRoot "dist/BlackDragonOverlay/BlackDragonOverlay.exe"
$OverlayDst = Join-Path $ProjectRoot "dist/BlackDragon/BlackDragonOverlay.exe"
if (Test-Path $OverlaySrc) {
    Copy-Item $OverlaySrc $OverlayDst -Force
    Write-Host "  Copied BlackDragonOverlay.exe → dist/BlackDragon/"
} else {
    Write-Error "Overlay exe not found at $OverlaySrc"
    exit 1
}

# ---------------------------------------------------------------------------
# 5b. Copy bundled training dataset to exe-adjacent data/ directory.
# PyInstaller collects datas into _internal/data/; train_fatalis_ai() reads
# "data/ML_Ready_Dataset.csv" relative to CWD (which is the exe dir in frozen
# mode via the cwd fix). So surface it next to the exe.
# ---------------------------------------------------------------------------
$DataSrc = Join-Path $ProjectRoot "dist/BlackDragon/_internal/data/ML_Ready_Dataset.csv"
$DataDst = Join-Path $ProjectRoot "dist/BlackDragon/data/ML_Ready_Dataset.csv"
if (Test-Path $DataSrc) {
    New-Item -ItemType Directory -Force -Path (Split-Path $DataDst) | Out-Null
    Copy-Item $DataSrc $DataDst -Force
    Write-Host "  Copied ML_Ready_Dataset.csv → dist/BlackDragon/data/"
} else {
    Write-Host "  WARNING: bundled dataset not found at $DataSrc" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 5c. Copy bundled runtime model to exe-adjacent models/ directory.
# PyInstaller collects datas into _internal/models/; runtime code reads
# "models/fatalis_ai_model.pkl" relative to CWD (which is the exe dir).
# Surface it next to the exe so both Dashboard and Overlay can load it.
# ---------------------------------------------------------------------------
Write-Host "Surfacing runtime model..."
$ModelSrc = Join-Path $ProjectRoot "dist/BlackDragon/_internal/models/fatalis_ai_model.pkl"
$ModelDst = Join-Path $ProjectRoot "dist/BlackDragon/models/fatalis_ai_model.pkl"
if (Test-Path $ModelSrc) {
    New-Item -ItemType Directory -Force -Path (Split-Path $ModelDst) | Out-Null
    Copy-Item $ModelSrc $ModelDst -Force
    Write-Host "Model copied to dist/BlackDragon/models"
} else {
    Write-Host "  WARNING: bundled model not found at $ModelSrc" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 6. Summary
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "  dist/BlackDragon/BlackDragon.exe"
Write-Host "  dist/BlackDragon/BlackDragonOverlay.exe  (merged)"
Write-Host "  dist/BlackDragon/data/ML_Ready_Dataset.csv"
Write-Host "  dist/BlackDragon/models/fatalis_ai_model.pkl"
Write-Host ""
Write-Host "Both EXEs now in same directory — controller.start_overlay()"
Write-Host "can find BlackDragonOverlay.exe next to sys.executable."
Write-Host "Training dataset + runtime model surfaced next to exe."
Write-Host ""
Write-Host "Release package: copy dist/BlackDragon/ + models/ + config/"
