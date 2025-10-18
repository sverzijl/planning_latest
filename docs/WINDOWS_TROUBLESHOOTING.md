# Windows Troubleshooting Guide

## Import Error: cannot import name 'render_truck_loadings_table'

### Quick Fix (90% Success Rate)

**Option 1: PowerShell Script (Recommended)**
```powershell
.\fix_import_error.ps1
```

**Option 2: Batch Script**
```cmd
fix_import_error.bat
```

---

### Manual Fix Instructions

If scripts don't work, follow these steps:

#### Step 1: Clear Python Cache

**PowerShell:**
```powershell
Get-ChildItem -Path . -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Recurse -File -Filter *.pyc | Remove-Item -Force
```

**Command Prompt:**
```cmd
for /d /r . %d in (__pycache__) do @if exist "%d" rd /s /q "%d"
del /s /q *.pyc
```

#### Step 2: Clear Streamlit Cache

```cmd
rd /s /q .streamlit\cache
```

#### Step 3: Restart Streamlit

```cmd
streamlit run ui\app.py
```

---

### Why This Happens

After major refactoring (like the navigation redesign in WP2.3), Python's bytecode cache (`.pyc` files in `__pycache__` directories) may contain outdated compiled modules. This causes import errors even though the source code is correct.

**Solution:** Delete all `__pycache__` directories to force Python to recompile with the current code.

---

### Verification

Test if imports work:

```python
python -c "from ui.components import render_truck_loadings_table; print('✅ Success!')"
```

If you see `✅ Success!`, the fix worked.

---

### Still Not Working?

Try the "nuclear option":

1. **Close all Python/Streamlit processes**
   ```cmd
   taskkill /F /IM python.exe 2>nul
   taskkill /F /IM streamlit.exe 2>nul
   ```

2. **Pull latest code**
   ```cmd
   git pull origin master
   ```

3. **Delete all cache** (run fix script again)

4. **Restart computer** (clears file locks)

5. **Try again**

---

### Common Issues

#### Issue: Permission Denied

**Solution:** Run PowerShell as Administrator
- Right-click PowerShell
- Select "Run as Administrator"
- Navigate to project directory
- Run fix script again

#### Issue: Function Not Found in File

**Solution:** Update code from Git
```cmd
git pull origin master
```

#### Issue: Wrong Python Environment

**Solution:** Verify Python path
```cmd
where python
where streamlit
```

Both should point to your WPy64-31311b1 directory.

---

### Need More Help?

Check the main troubleshooting section in `README.md` or review commit history:
```cmd
git log --oneline -10
```

The import fix was added in commit `50b2cff`.
