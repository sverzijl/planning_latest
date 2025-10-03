@echo off
REM ============================================
REM Windows Import Error Fix Script (Batch)
REM ============================================

echo ========================================
echo Planning App - Import Error Fix
echo ========================================
echo.

echo [1/5] Checking Git status...
git log -1 --oneline
echo.

echo [2/5] Verifying critical files...
if exist "ui\components\data_tables.py" (
    echo   ✓ ui\components\data_tables.py exists
) else (
    echo   ✗ ERROR: ui\components\data_tables.py NOT FOUND
    echo   Run: git pull origin master
    pause
    exit /b 1
)
echo.

echo [3/5] Clearing Python bytecode cache...
for /d /r . %%d in (__pycache__) do @if exist "%%d" (
    rd /s /q "%%d" 2>nul
)
del /s /q *.pyc 2>nul
echo   ✓ Cache cleared
echo.

echo [4/5] Clearing Streamlit cache...
if exist ".streamlit\cache" (
    rd /s /q ".streamlit\cache" 2>nul
    echo   ✓ Deleted Streamlit cache
) else (
    echo   No Streamlit cache found
)
echo.

echo [5/5] Testing imports...
python -c "import sys; sys.path.insert(0, '.'); from ui.components import render_truck_loadings_table; print('  ✓ Import successful!')"

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ FIX SUCCESSFUL!
    echo ========================================
    echo.
    echo Imports are now working correctly.
    echo Start Streamlit with:
    echo   streamlit run ui\app.py
    echo.
) else (
    echo.
    echo ========================================
    echo ❌ FIX INCOMPLETE
    echo ========================================
    echo.
    echo Try these steps:
    echo 1. Close all Python/Streamlit processes
    echo 2. Run: git pull origin master
    echo 3. Restart your terminal
    echo 4. Run this script again
    echo.
)

pause
