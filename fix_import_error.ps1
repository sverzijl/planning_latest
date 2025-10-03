# ============================================
# Windows Import Error Fix Script (PowerShell)
# ============================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Planning App - Import Error Fix" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get current directory (should be project root)
$ProjectRoot = Get-Location

Write-Host "[1/6] Checking Git status..." -ForegroundColor Yellow
git log -1 --oneline
$LastCommit = git rev-parse --short HEAD
Write-Host "  Current commit: $LastCommit" -ForegroundColor Gray
Write-Host ""

Write-Host "[2/6] Verifying critical files exist..." -ForegroundColor Yellow
$FilesToCheck = @(
    "ui\components\__init__.py",
    "ui\components\data_tables.py",
    "ui\pages\3_Results.py"
)

foreach ($File in $FilesToCheck) {
    if (Test-Path $File) {
        $FileInfo = Get-Item $File
        Write-Host "  ✓ $File (Modified: $($FileInfo.LastWriteTime))" -ForegroundColor Green
    } else {
        Write-Host "  ✗ MISSING: $File" -ForegroundColor Red
        Write-Host ""
        Write-Host "ERROR: Critical file missing. Run 'git pull origin master' to update." -ForegroundColor Red
        exit 1
    }
}
Write-Host ""

Write-Host "[3/6] Searching for function definition..." -ForegroundColor Yellow
$FunctionFound = Select-String -Path "ui\components\data_tables.py" -Pattern "def render_truck_loadings_table" -Quiet
if ($FunctionFound) {
    $LineNumber = (Select-String -Path "ui\components\data_tables.py" -Pattern "def render_truck_loadings_table").LineNumber
    Write-Host "  ✓ Function found at line $LineNumber in data_tables.py" -ForegroundColor Green
} else {
    Write-Host "  ✗ Function NOT found in data_tables.py" -ForegroundColor Red
    Write-Host "    Run 'git pull origin master' to get latest code" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "[4/6] Clearing Python bytecode cache..." -ForegroundColor Yellow
$CacheDirs = Get-ChildItem -Path . -Recurse -Directory -Filter __pycache__ -ErrorAction SilentlyContinue
$CacheCount = ($CacheDirs | Measure-Object).Count
Write-Host "  Found $CacheCount cache directories" -ForegroundColor Gray

if ($CacheCount -gt 0) {
    $CacheDirs | Remove-Item -Recurse -Force
    Write-Host "  ✓ Deleted $CacheCount __pycache__ directories" -ForegroundColor Green
} else {
    Write-Host "  No cache directories to delete" -ForegroundColor Gray
}

# Also remove .pyc files
$PycFiles = Get-ChildItem -Path . -Recurse -File -Filter *.pyc -ErrorAction SilentlyContinue
$PycCount = ($PycFiles | Measure-Object).Count
if ($PycCount -gt 0) {
    $PycFiles | Remove-Item -Force
    Write-Host "  ✓ Deleted $PycCount .pyc files" -ForegroundColor Green
}
Write-Host ""

Write-Host "[5/6] Clearing Streamlit cache..." -ForegroundColor Yellow
if (Test-Path ".streamlit\cache") {
    Remove-Item -Path ".streamlit\cache" -Recurse -Force
    Write-Host "  ✓ Deleted Streamlit cache" -ForegroundColor Green
} else {
    Write-Host "  No Streamlit cache to delete" -ForegroundColor Gray
}
Write-Host ""

Write-Host "[6/6] Testing imports..." -ForegroundColor Yellow
$TestScript = @"
import sys
sys.path.insert(0, r'$ProjectRoot')

try:
    from ui.components import render_truck_loadings_table
    print('  ✓ Import successful!')
    print('\n✅ ALL IMPORT TESTS PASSED!')
except ImportError as e:
    print(f'  ✗ Import failed: {e}')
    sys.exit(1)
"@

$TestScript | python
$TestExitCode = $LASTEXITCODE

Write-Host ""
if ($TestExitCode -eq 0) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "✅ FIX SUCCESSFUL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Imports are now working correctly." -ForegroundColor Green
    Write-Host "You can now start Streamlit:" -ForegroundColor White
    Write-Host "  streamlit run ui\app.py" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "❌ FIX INCOMPLETE" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Import tests still failing. Try these steps:" -ForegroundColor Yellow
    Write-Host "1. Close all Python/Streamlit processes (Ctrl+C)" -ForegroundColor White
    Write-Host "2. Run: git pull origin master" -ForegroundColor White
    Write-Host "3. Restart your terminal/PowerShell" -ForegroundColor White
    Write-Host "4. Run this script again" -ForegroundColor White
    Write-Host ""
}
