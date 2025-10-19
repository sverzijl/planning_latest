"""Trace why Friday production can't serve Sunday demand.

This script builds a model and inspects the cohort indices to identify
exactly where the Friday→Saturday→Sunday path is blocked.
"""

import sys
from pathlib import Path
from datetime import timedelta, datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel


def trace_cohort_path():
    """Trace cohort path construction to find blocking constraint."""

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Zero all costs except labor
    cost_structure.storage_cost_per_pallet_day_frozen = 0.0
    cost_structure.storage_cost_fixed_per_pallet_frozen = 0.0

    manufacturing_site = None
    for loc in locations:
        if loc.type == 'manufacturing':
            manufacturing_site = ManufacturingSite(
                id=loc.id, name=loc.name, type=loc.type,
                storage_mode=loc.storage_mode, capacity=loc.capacity,
                latitude=loc.latitude, longitude=loc.longitude,
                production_rate=1400.0
            )
            break

    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site, locations, routes,
        truck_schedules_list, forecast
    )

    start_date = min(e.forecast_date for e in forecast.entries)
    end_date = start_date + timedelta(weeks=2)

    print("\n" + "="*80)
    print("COHORT PATH TRACING: Friday→Saturday→Sunday")
    print("="*80)

    # Build model (WITHOUT trucks to isolate the issue)
    model_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=[],  # NO TRUCKS
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=False,  # NO SHELF LIFE
    )

    # Key dates
    friday = datetime(2025, 10, 10).date()
    saturday = datetime(2025, 10, 11).date()
    sunday = datetime(2025, 10, 12).date()
    monday = datetime(2025, 10, 13).date()

    # Get sample products
    products = list(set(e.product_id for e in forecast.entries))[:2]
    breadroom = '6110'  # Sample breadroom
    mfg = '6122'

    print(f"\nDates:")
    print(f"  Friday:   {friday} ({friday.strftime('%A')})")
    print(f"  Saturday: {saturday} ({saturday.strftime('%A')})")
    print(f"  Sunday:   {sunday} ({sunday.strftime('%A')})")
    print(f"  Monday:   {monday} ({monday.strftime('%A')})")

    print(f"\nChecking product: {products[0][:30]}")

    # Check 1: Demand cohort index
    print("\n" + "="*80)
    print("1. DEMAND COHORT INDEX CHECK")
    print("="*80)

    paths_to_check = [
        (friday, saturday, "Friday prod → Saturday demand"),
        (friday, sunday, "Friday prod → Sunday demand"),
        (friday, monday, "Friday prod → Monday demand"),
        (saturday, sunday, "Saturday prod → Sunday demand"),
        (saturday, monday, "Saturday prod → Monday demand"),
    ]

    for prod_date, demand_date, description in paths_to_check:
        key = (breadroom, products[0], prod_date, demand_date)
        exists = key in model_obj.demand_cohort_index_set
        age = (demand_date - prod_date).days

        status = "✅ ALLOWED" if exists else "❌ BLOCKED"
        print(f"  {description}: age={age}d → {status}")

    # Check 2: Shipment cohort index
    print("\n" + "="*80)
    print("2. SHIPMENT COHORT INDEX CHECK")
    print("="*80)

    shipment_paths = [
        (friday, saturday, "Friday ship → Saturday arrival"),
        (friday, sunday, "Friday ship → Sunday arrival"),
        (saturday, sunday, "Saturday ship → Sunday arrival"),
        (saturday, monday, "Saturday ship → Monday arrival"),
    ]

    for depart_date, arrive_date, description in shipment_paths:
        # Find matching shipment cohort
        found = False
        for (o, d, p, pd, dd, s) in model_obj.shipment_cohort_index_set:
            if (o == mfg and d == breadroom and
                p == products[0] and pd == depart_date and dd == arrive_date):
                found = True
                print(f"  {description}: ✅ IN INDEX (state={s})")
                break

        if not found:
            print(f"  {description}: ❌ NOT IN INDEX")

    # Check 3: Inventory cohort index
    print("\n" + "="*80)
    print("3. INVENTORY COHORT INDEX CHECK (at breadroom)")
    print("="*80)

    inventory_paths = [
        (friday, saturday, "Friday prod → Saturday inventory"),
        (friday, sunday, "Friday prod → Sunday inventory"),
        (saturday, sunday, "Saturday prod → Sunday inventory"),
    ]

    for prod_date, inv_date, description in inventory_paths:
        key = (breadroom, products[0], prod_date, inv_date, 'ambient')
        exists = key in model_obj.cohort_index_set

        status = "✅ IN INDEX" if exists else "❌ NOT IN INDEX"
        print(f"  {description}: {status}")

    # Check 4: What does the model's solution actually show?
    print("\n" + "="*80)
    print("4. ACTUAL SOLVER SOLUTION")
    print("="*80)

    result = model_obj.solve(time_limit_seconds=120, mip_gap=0.01, tee=False)

    if result.success:
        print(f"  Status: {result.termination_condition}")
        print(f"  Cost: ${result.objective_value:,.2f}")

        solution = model_obj.get_solution()
        labor_by_date = solution.get('labor_hours_by_date', {})

        print("\n  Labor usage:")
        for date in [friday, saturday, sunday, monday]:
            info = labor_by_date.get(date, {})
            if info:
                used = info.get('used', 0)
                ot = info.get('overtime', 0)
                print(f"    {date} ({date.strftime('%A'):9s}): {used:.2f}h used, {ot:.2f}h OT")
    else:
        print(f"  ❌ Solve failed: {result.infeasibility_message}")

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)

    # Find which path is blocked
    friday_to_sunday_demand = (breadroom, products[0], friday, sunday) in model_obj.demand_cohort_index_set
    friday_to_monday_demand = (breadroom, products[0], friday, monday) in model_obj.demand_cohort_index_set

    if not friday_to_sunday_demand and not friday_to_monday_demand:
        print("❌ BUG FOUND: demand_cohort_index_set excludes Friday production")
        print("   Friday production cannot serve Sunday/Monday demands")
        print("   Location: Cohort index construction (lines ~720-750)")
    elif friday_to_sunday_demand:
        print("✅ Indices allow Friday→Sunday path")
        print("   Bug must be in cohort balance or solver preference")
    else:
        print("ℹ️  Check solver logs and constraint duals for binding constraints")


if __name__ == "__main__":
    trace_cohort_path()
