# Quick Start Demo - Phase A Workflow System

## 🚀 Running Your First Initial Solve

This guide walks you through the complete Initial Solve workflow in 5 minutes.

### Prerequisites

1. **Solver installed** (APPSI HiGHS recommended):
   ```bash
   pip install highspy
   ```

2. **Data files ready:**
   - Forecast file (e.g., `Gluten Free Forecast.xlsm`)
   - Network config file (e.g., `Network_Config.xlsx`)
   - Initial inventory file (optional, e.g., from SAP MB52)

### Step-by-Step Demo

#### 1. Start the Application

```bash
cd /home/sverzijl/planning_latest
source venv/bin/activate
streamlit run ui/app.py
```

The app will open in your browser at `http://localhost:8501`

#### 2. Upload Data

**Option A: If data already uploaded**
- You should see "✅ Data Loaded" on the home page
- Skip to Step 3

**Option B: Upload data now**
1. Click **"Go to Data Upload Page"** or navigate to **"Data"** in sidebar
2. Upload your forecast Excel file
3. Upload your network configuration Excel file
4. (Optional) Upload initial inventory file
5. Wait for parsing to complete (~10-30 seconds)
6. You should see success message with data summary

#### 3. Navigate to Initial Solve

From the home page, click **"▶️ Run Initial Solve"** in the "Production Planning Workflows" section.

You'll see the Initial Solve page with:
- Progress checklist in the sidebar (5 steps)
- Five tabs: Data, Configure, Solve, Results, Export

#### 4. Verify Data (Tab 1)

The **Data** tab shows a summary of your uploaded data:
- Locations, routes, products counts
- Total demand and planning days
- Labor days and truck schedules
- Loaded file names

**Action:** Click **"✅ Data Verified - Proceed to Configure"**

The checklist will update (✅ for step 1, 🔄 for step 2).

#### 5. Configure Solve (Tab 2)

The **Configure** tab lets you set optimization parameters:

**Quick Test Setup (4-week, 5-minute solve):**
- Planning Horizon: **4 weeks**
- Solver: **appsi_highs**
- Time Limit: **300 seconds** (5 minutes)
- MIP Gap: **0.01** (1%)
- Check: **Track Production Batches**
- Check: **Use Pallet-Based Storage Costs**

**Production Setup (12-week, 30-minute solve):**
- Planning Horizon: **12 weeks**
- Time Limit: **1800 seconds** (30 minutes)
- MIP Gap: **0.01**
- Keep other defaults

**Action:** Click **"✅ Configuration Complete - Ready to Solve"**

#### 6. Run Optimization (Tab 3)

The **Solve** tab shows your configuration summary and the solve button.

**Action:** Click **"🚀 Run Initial Solve"**

You'll see:
1. "Building optimization model..." message
2. Progress bar with status updates:
   - Preparing input data... (10%)
   - Building optimization model... (20%)
   - Solving optimization problem... (30-90%)
   - Saving results... (90-100%)
3. Completion message with results

**Expected Solve Times:**
- 4-week horizon: 2-5 minutes (good for testing)
- 8-week horizon: 5-15 minutes
- 12-week horizon: 10-30 minutes

**During Solve:**
- Don't close browser
- Don't refresh page
- Don't click other buttons
- Wait for completion

#### 7. Review Results (Tab 4)

After successful solve, you'll see:

**Summary Metrics (4 columns):**
- **Total Cost:** Objective value (e.g., $125,430.50)
- **Solve Time:** Actual solve duration (e.g., 234.5s)
- **MIP Gap:** Final solution quality (e.g., 0.82%)
- **Solver Status:** "ok" or "optimal"

**Additional Information:**
- Metadata (expand to see planning dates, input counts, etc.)
- Solution preview (number of variables)

**Action:** Click **"✅ Results Reviewed - Proceed to Export"**

#### 8. Export Plans (Tab 5)

The **Export** tab shows:
- Placeholder buttons for Excel, PDF, Dashboard (coming in Phase C)
- Solve file location (for warmstart in future Weekly solves)

**File Location Example:**
```
/home/sverzijl/planning_latest/solves/2025/wk43/initial_20251026_0645.json
```

This file will be automatically used for warmstart when you run Weekly Solve (Phase B).

**Action:** Click **"🏠 Return to Home"** to go back to the home page

#### 9. View Results on Home Page

Back on the home page, scroll to the "Production Planning Workflows" section.

You should now see **"Last Solve Status"** metrics:
- **Last Solve Type:** Initial
- **Objective Value:** $125,430.50
- **Solve Time:** 234.5s
- **Status:** ✅ Success

---

## 🎯 Quick Test Script (4-Week Solve)

For rapid testing, use these settings:

```
Planning Horizon: 4 weeks
Solver: appsi_highs
Time Limit: 300s (5 min)
MIP Gap: 0.01 (1%)
Allow Shortages: ✓ (unchecked = more realistic)
Track Batches: ✓ (checked = recommended)
Use Pallet Costs: ✓ (checked = more accurate)
```

**Expected result:** Solve completes in 2-5 minutes with feasible solution.

---

## 🐛 Troubleshooting

### Problem: "Solver not found" error

**Solution:**
```bash
pip install highspy  # For APPSI HiGHS (recommended)
# OR
sudo apt-get install coinor-cbc  # For CBC
```

### Problem: Solve times out after 30 minutes

**Solutions:**
1. **Reduce horizon:** Try 4 weeks instead of 12
2. **Increase MIP gap:** Try 0.02 (2%) instead of 0.01
3. **Increase time limit:** Try 3600s (1 hour) for large problems
4. **Disable pallet costs:** Uncheck "Use Pallet-Based Storage Costs" (faster but less accurate)

### Problem: "No data uploaded" message

**Solution:**
1. Go to **"Data"** page in sidebar
2. Upload forecast and network files
3. Wait for parsing to complete
4. Return to Initial Solve page

### Problem: Solve fails with "infeasible" status

**Possible causes:**
1. **Insufficient capacity:** Production capacity < demand
2. **Truck capacity issues:** Not enough trucks or truck capacity
3. **Shelf life violations:** Products expire before reaching destination

**Solutions:**
1. Enable **"Allow Shortages"** to see where capacity is insufficient
2. Check your input data:
   - Labor calendar has enough working days
   - Truck schedules cover all required routes
   - Shelf life parameters are realistic
3. Reduce planning horizon to test smaller problem first

### Problem: Page doesn't update after clicking button

**Solution:**
- This is expected - Streamlit reruns automatically
- If page truly stuck, refresh browser (you may lose progress in current step)
- For solve execution, wait for progress bar to complete (don't refresh!)

---

## 📊 Expected Results for Sample Data

### Using `Gluten Free Forecast.xlsm` and `Network_Config.xlsx`:

**4-Week Horizon:**
- Solve Time: 2-5 minutes
- Total Cost: ~$40,000-$60,000 (varies by forecast period)
- MIP Gap: <1%
- Status: Optimal or Feasible

**12-Week Horizon:**
- Solve Time: 10-30 minutes
- Total Cost: ~$120,000-$180,000
- MIP Gap: <1%
- Status: Optimal or Feasible

**Solution Characteristics:**
- Production occurs on weekdays (leveraging fixed labor hours)
- Overtime used sparingly (high cost)
- Weekend production only if necessary (4-hour minimum payment)
- Trucks loaded efficiently (near capacity utilization)
- Minimal inventory held (storage costs drive optimization)

---

## 🎉 Success Checklist

After completing the demo, you should have:

- [x] Successfully uploaded data
- [x] Configured and run an Initial Solve
- [x] Reviewed results showing total cost and solve time
- [x] Seen solve file saved to `solves/YYYY/wkNN/` directory
- [x] Understand the 5-step workflow (Data → Configure → Solve → Results → Export)

---

## 🔜 What's Next?

### Explore Features:
1. **Try different configurations:**
   - Vary planning horizon (4, 8, 12 weeks)
   - Test with/without pallet costs
   - Enable/disable shortages to see impact

2. **View Results Page:**
   - Navigate to **"Results"** in sidebar
   - Explore production schedule
   - Review cost breakdown
   - Analyze daily snapshots (if implemented)

3. **Network Visualization:**
   - Navigate to **"Network"** in sidebar
   - View network graph
   - Understand route topology

### Coming in Phase B:
- **Weekly Solve:** Rolling horizon with warmstart
- **Daily Solve:** Actuals entry and fixed periods
- **Variance Reports:** Plan vs actual comparison
- **Forward Plans:** 1-7 day production schedules

---

## 📞 Need Help?

### Common Questions:

**Q: Can I run multiple solves?**
A: Yes! Each solve is saved separately. Session state holds only the latest.

**Q: Where are solve files stored?**
A: In `solves/YYYY/wkNN/TYPE_YYYYMMDD_HHMM.json` relative to project root.

**Q: Can I compare different solves?**
A: Not yet - comparison tools coming in Phase C.

**Q: What if I want to change the forecast?**
A: Re-upload on Data page, then run a new Initial Solve.

**Q: How do I use the saved solve for warmstart?**
A: Weekly Solve (Phase B) will automatically load the latest solve for warmstart.

---

**Happy Planning! 🚀**

*For technical details, see `PHASE_A_COMPLETION_SUMMARY.md`*
*For architecture details, see `CLAUDE.md`*
