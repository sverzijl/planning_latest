"""Test script to verify component imports."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Test imports from 3_Results.py
try:
    from ui.components import (
        render_production_gantt,
        render_labor_hours_chart,
        render_daily_production_chart,
        render_capacity_utilization_chart,
        render_production_batches_table,
        render_daily_breakdown_table,
        render_date_range_filter,
        render_truck_loading_timeline,
        render_shipments_by_destination_chart,
        render_truck_utilization_chart,
        render_shipments_table,
        render_truck_loadings_table,
        render_cost_breakdown_chart,
        render_cost_by_category_chart,
        render_daily_cost_chart,
        render_cost_breakdown_table,
    )
    print("✅ All imports successful!")
    print("\nImported functions:")
    print("  - render_production_gantt")
    print("  - render_labor_hours_chart")
    print("  - render_daily_production_chart")
    print("  - render_capacity_utilization_chart")
    print("  - render_production_batches_table")
    print("  - render_daily_breakdown_table")
    print("  - render_date_range_filter")
    print("  - render_truck_loading_timeline")
    print("  - render_shipments_by_destination_chart")
    print("  - render_truck_utilization_chart")
    print("  - render_shipments_table")
    print("  - render_truck_loadings_table ✨ (NEW)")
    print("  - render_cost_breakdown_chart")
    print("  - render_cost_by_category_chart ✨ (NEW)")
    print("  - render_daily_cost_chart")
    print("  - render_cost_breakdown_table ✨ (NEW)")

except ImportError as e:
    print(f"❌ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
