# Results Comparison Page

**File:** `ui/pages/11_Results_Comparison.py`
**Page Title:** Results Comparison ⚖️
**Status:** ✅ Complete (WP1.2)

## Overview

The Results Comparison page enables side-by-side comparison of two planning approaches:

1. **Heuristic Planning** (Rule-based, fast) - from `pages/3_Planning_Workflow.py`
2. **Mathematical Optimization** (Optimal, slower) - from `pages/10_Optimization.py`

The page provides comprehensive cost analysis, visual comparisons, and actionable insights to help users understand the value of optimization versus heuristic planning.

## Key Features

### 1. Status Badges and Quick Actions
- Visual indicators showing which results are available
- Quick action buttons to run missing analyses
- Clear getting-started guidance when results are missing

### 2. Cost Comparison Metrics
- **Side-by-side layout** with three columns:
  - **Heuristic (Baseline)**: All cost metrics from rule-based planning
  - **Δ Change**: Delta calculations showing savings or increases
  - **Optimization (Result)**: All cost metrics from mathematical optimization

- **Cost components tracked:**
  - Total Cost (primary metric)
  - Labor Cost
  - Production Cost
  - Transport Cost
  - Waste/Shortage Cost

- **Additional metrics:**
  - Production batches count
  - Demand satisfaction percentage
  - Total units produced
  - Labor hours utilized

### 3. Waterfall Chart Visualization
- Interactive Plotly waterfall chart showing:
  - Starting point: Heuristic total cost
  - Component-by-component changes (Labor, Production, Transport, Waste)
  - Ending point: Optimization total cost
- Color-coded bars:
  - 🟢 Green: Savings (cost reduction)
  - 🔴 Red: Increases (cost addition)
  - 🔵 Blue: Total values

### 4. Actionable Insights
Auto-generated insight boxes showing:
- **Cost savings achieved**: "Optimization saves $X (Y%)"
- **Time-cost tradeoff**: "Optimization takes X seconds but saves $Y"
- **Unexpected results warning**: When optimization costs more than heuristic
- **Equal performance notification**: When both approaches yield same cost

### 5. Detailed Comparison Tabs

#### Tab 1: Cost Summary
- Comprehensive cost breakdown table
- All components with heuristic vs optimization values
- Delta calculations in both $ and %
- Color-coded rows (green for savings, red for increases)
- Cost per unit comparison

#### Tab 2: Production Comparison
- Production batches and total units side-by-side
- Labor hours comparison (when available)
- Expandable production schedule details
- First 20 batches from each approach

#### Tab 3: Demand Satisfaction
- Satisfaction percentage comparison
- Shortage analysis (when applicable)
- Warning boxes for unmet demand
- Satisfaction change metric

#### Tab 4: Labor Utilization
- Labor hours and costs comparison
- Cost per hour calculation
- Efficiency analysis
- Info boxes explaining labor differences

#### Tab 5: Performance Metrics
- Execution time comparison
- Solver information and optimality status
- Time-cost tradeoff analysis
- Optimization statistics (variables, constraints, MIP gap)

### 6. Export Options (Placeholder for WP1.3)
- Export comparison to Excel
- Generate PDF report
- Copy summary to clipboard

### 7. Navigation
- Quick links back to:
  - Heuristic Planning page
  - Optimization page
  - Home page

## Usage Instructions

### Prerequisites
Both planning approaches must be run before comparison:

1. **Run Heuristic Planning:**
   - Navigate to "Planning Workflow" page (page 3)
   - Click "Run Complete Workflow"
   - Wait for completion

2. **Run Mathematical Optimization:**
   - Navigate to "Optimization" page (page 10)
   - Configure solver and settings
   - Click "Run Optimization"
   - Wait for completion

### Accessing the Comparison
Once both are complete:
1. Navigate to "Results Comparison" page (page 11)
2. The page will automatically load and display comparison

### Interpreting Results

**Cost Savings (Green):**
- Negative delta values indicate optimization saves money
- Look for large savings in specific components (e.g., labor, transport)

**Cost Increases (Red):**
- Positive delta values indicate optimization costs more
- May indicate model constraints or configuration differences
- Review detailed tabs to understand why

**Equal Performance:**
- Heuristic may already be optimal for the scenario
- Check if demand is low or constraints are loose

**Time-Cost Tradeoff:**
- Compare execution time vs savings achieved
- "Savings per second" metric shows efficiency of optimization

## Session State Dependencies

The page reads from these session state variables:

### Heuristic Results
- `st.session_state.planning_complete`: bool
- `st.session_state.production_schedule`: ProductionSchedule
- `st.session_state.cost_breakdown`: TotalCostBreakdown
- `st.session_state.shipments`: list[Shipment]
- `st.session_state.truck_plan`: TruckLoadPlan

### Optimization Results
- `st.session_state.optimization_result`: OptimizationResult
- `st.session_state.optimization_model`: IntegratedProductionDistributionModel
- `st.session_state.optimization_solver`: str (solver name)

## Helper Functions

The page includes several utility functions:

### Formatting
- `format_currency(value)` - Format as $X,XXX.XX
- `format_number(value)` - Format as X,XXX
- `format_percentage(value)` - Format as XX.X%

### Calculations
- `calculate_delta(heuristic_val, optimization_val)` - Returns (abs_delta, pct_delta)
- `color_delta(delta, inverse=True)` - Returns "success" or "error"
- `create_delta_display(delta_abs, delta_pct)` - Formatted string with sign

### Data Extraction
- `get_heuristic_data()` - Extract metrics from heuristic session state
- `get_optimization_data()` - Extract metrics from optimization session state

### Visualization
- `create_waterfall_chart(heuristic_costs, optimization_costs)` - Plotly waterfall figure

## Design System Integration

The page uses the custom design system defined in `ui/assets/styles.css`:

### Components Used
- `apply_custom_css()` - Load CSS styles
- `section_header()` - Page and section headers
- `colored_metric()` - Colored metric cards
- `success_badge()`, `error_badge()`, `warning_badge()`, `info_badge()` - Status badges
- `info_box()` - Info/success/warning/error boxes

### Color Palette
- **Primary Blue** (#1E88E5): Labor costs, primary metrics
- **Secondary Green** (#43A047): Savings, success states
- **Accent Orange** (#FB8C00): Transport costs, neutral metrics
- **Error Red** (#E53935): Waste costs, cost increases
- **Success Green** (#43A047): Cost savings, positive deltas

## Error Handling

The page gracefully handles:

1. **Missing heuristic results**
   - Shows warning badge
   - Displays getting-started guide
   - Provides button to run heuristic planning

2. **Missing optimization results**
   - Shows warning badge
   - Displays info box encouraging optimization
   - Provides button to run optimization

3. **Both missing**
   - Shows comprehensive getting-started guide
   - Links to both planning pages

4. **Infeasible optimization**
   - Filters out infeasible solutions
   - Shows error message if optimization failed

5. **Data loading errors**
   - Catches exceptions in data extraction
   - Shows error message with context

## Testing

Unit tests for helper functions are available in:
- `tests/test_results_comparison.py`

Run tests:
```bash
python3 tests/test_results_comparison.py
```

## Future Enhancements (WP1.3+)

Planned features:
1. **Export to Excel**: Complete comparison data in structured Excel file
2. **PDF Report Generation**: Professional PDF report with charts and tables
3. **Clipboard Support**: Copy summary text to clipboard
4. **Production Schedule Charts**: Gantt charts comparing production timing
5. **Labor Hour Visualization**: Daily labor usage comparison charts
6. **Route Comparison**: Network flow comparison showing routing differences
7. **Sensitivity Analysis**: "What-if" scenarios showing cost sensitivity

## Troubleshooting

### "No results to compare" message
- Ensure you've run both heuristic and optimization
- Check that optimization result is feasible (not infeasible)
- Verify session state has not been cleared

### Delta calculations showing 0%
- Check that baseline (heuristic) costs are non-zero
- Division by zero protection returns 0% when baseline is 0

### Optimization costs higher than heuristic
- Review model constraints and parameters
- Check if shortage penalties are being applied
- Verify solver found optimal solution (not just feasible)
- Compare demand satisfaction percentages

### Missing labor hours in optimization
- Labor hours are not directly tracked in optimization model
- Only labor costs are available from optimization
- This is expected behavior

## Related Pages

- **3_Planning_Workflow.py**: Generates heuristic results
- **10_Optimization.py**: Generates optimization results
- **6_Cost_Analysis.py**: Detailed cost breakdown (heuristic only)
- **4_Production_Schedule.py**: Production details (heuristic only)

## Code Structure

```
11_Results_Comparison.py
├── Imports and Setup
├── Helper Functions (formatting, calculations, data extraction)
├── Page Header
├── Status Check and Quick Actions
├── Cost Comparison Metrics (3-column layout)
├── Waterfall Chart Visualization
├── Detailed Comparison Tabs
│   ├── Cost Summary
│   ├── Production Comparison
│   ├── Demand Satisfaction
│   ├── Labor Utilization
│   └── Performance Metrics
├── Export Section (placeholder)
└── Navigation
```

## Maintenance Notes

- Keep helper functions in sync with session state structure changes
- Update cost component list if new cost types are added
- Ensure color coding remains consistent with design system
- Test with edge cases (zero costs, equal results, large deltas)
- Update documentation when new features are added

---

**Created:** 2025-10-02
**Work Package:** WP1.2 - Results Comparison Page
**Status:** ✅ Complete
**Next Steps:** WP1.3 - Export functionality implementation
