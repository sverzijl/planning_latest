# Diagnostic Steps - Please Run These

## Critical: We Need to Sync

**I'm seeing different results than you**, which means either:
1. You haven't pulled my latest commits (15 total)
2. Or there's a Windows vs Linux difference
3. Or Streamlit cache is showing old results

---

## Step 1: Verify You Have Latest Code

**Run:**
```bash
git pull
git log --oneline -5
```

**Should show:**
```
f301db8 docs: Summary of current UI display issues
ae3a198 docs: Final status and diagnostic tools
de1dad1 fix: Check .stale attribute to avoid uninitialized
7f7ee2b fix: Implement proper piecewise labor cost model
3f57569 fix: Extract manufacturing_site_id correctly
```

**If not matching:** Pull again until you have these commits.

---

## Step 2: Clear ALL Caches

**Stop Streamlit** (Ctrl+C)

**Clear Python cache:**
```bash
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null
```

**Clear Streamlit cache:**
```bash
rm -rf ~/.streamlit/cache 2>/dev/null  # Linux/Mac
# OR
del /S /Q %USERPROFILE%\.streamlit\cache  # Windows
```

**Restart UI:**
```bash
streamlit run ui/app.py
```

---

## Step 3: Fresh Solve with Diagnostics

**In Streamlit UI:**

1. **Go to Settings** → Click "Clear Cache" button (if available)
2. **Go to Initial Solve page**
3. **Configure:**
   - Planning horizon: **4 weeks**
   - Solver: **APPSI HiGHS**
   - MIP gap: **2%**
   - Pallet tracking: **Enabled**

4. **Click "Run Optimization"**

5. **While solving, watch the console output for:**
   ```
   🎯 Building objective...
     Labor cost: Weekday overtime ($660/h) + Weekend ($1320/h), fixed hours FREE
     Changeover cost: $38.40 per start
     Changeover waste: 30 units per start × $1.30/unit = $39.00 per start
   ```

6. **After solve completes, note:**
   - Solve time (should be 5-10 seconds)
   - Total production shown
   - Which products you see

---

## Step 4: Run Python Diagnostic

**Run this in your terminal (not UI):**

```bash
python check_ui_product_display.py
```

**This will show:**
- What products the model actually produced
- What products are in the solution
- What products the UI adapter receives

**Copy the output and send it to me.**

---

## Step 5: Check Specific Files

**Tell me:**

1. **In Production Tab, what EXACT product names do you see?**
   - Copy/paste the exact text
   - Are there multiple products or just one?
   - How many batches shown?

2. **What's the total production quantity shown?**
   - Should be ~300k units for 4 weeks
   - If showing ~26k units, that's the bug

3. **How many hours per day on average?**
   - Should be ~8-10h/day
   - If 1.2h/day, production is way too low

---

## What I'm Suspecting

**Theory 1: Streamlit Cache**
- UI showing old solve results from before my fixes
- Cache not cleared properly
- Solution: Force clear + fresh solve

**Theory 2: JSON Save Broken**
- Solve works in memory but doesn't save correctly
- Explains why JSON shows 0 production
- UI might be loading from broken JSON

**Theory 3: Initial Inventory Bug**
- Initial inventory creating phantom supply
- Model satisfying demand without production
- Need to fix state balance constraint

---

## Immediate Action

**Please do Steps 1-3 above and tell me:**
1. Do you have commit `7f7ee2b` after pulling?
2. After clearing cache and fresh solve, what do you see?
3. Send me output from `python check_ui_product_display.py`

This will help me pinpoint whether it's:
- Code version mismatch
- Cache issue
- Actual model bug

---

**I can't fix it without knowing which version you're running and what a fresh solve shows!**
