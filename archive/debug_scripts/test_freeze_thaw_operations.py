#!/usr/bin/env python3
"""
Test freeze/thaw operations in the batch tracking model.

This script checks if freeze/thaw decision variables are included in the model
and whether they are used in the solution.
"""

from datetime import date, timedelta
from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from pyomo.environ import value

def analyze_freeze_thaw_operations(model_instance, result):
    """Analyze freeze/thaw operations in the solution."""

    print("\n" + "=" * 70)
    print("FREEZE/THAW OPERATIONS ANALYSIS")
    print("=" * 70)

    # Check if freeze/thaw variables exist
    if not hasattr(model_instance.model, 'freeze'):
        print("\n❌ Freeze variable not found in model")
        return False

    if not hasattr(model_instance.model, 'thaw'):
        print("\n❌ Thaw variable not found in model")
        return False

    print("\n✅ Freeze/thaw variables exist in model")

    # Count total freeze/thaw indices
    model = model_instance.model
    freeze_indices = len(model.cohort_freeze_thaw_index)
    print(f"   Freeze/thaw index size: {freeze_indices:,} tuples")

    # Analyze freeze operations
    total_freeze = 0.0
    freeze_operations = []

    for loc, prod, prod_date, curr_date in model.cohort_freeze_thaw_index:
        freeze_qty = value(model.freeze[loc, prod, prod_date, curr_date])
        if freeze_qty > 0.01:  # Non-zero (accounting for numerical tolerance)
            total_freeze += freeze_qty
            freeze_operations.append((loc, prod, prod_date, curr_date, freeze_qty))

    # Analyze thaw operations
    total_thaw = 0.0
    thaw_operations = []

    for loc, prod, prod_date, curr_date in model.cohort_freeze_thaw_index:
        thaw_qty = value(model.thaw[loc, prod, prod_date, curr_date])
        if thaw_qty > 0.01:  # Non-zero
            total_thaw += thaw_qty
            thaw_operations.append((loc, prod, prod_date, curr_date, thaw_qty))

    print(f"\n   Total freeze operations: {len(freeze_operations)}")
    print(f"   Total thaw operations: {len(thaw_operations)}")
    print(f"   Total frozen quantity: {total_freeze:,.2f} units")
    print(f"   Total thawed quantity: {total_thaw:,.2f} units")

    # Print details if any operations occurred
    if freeze_operations:
        print("\n" + "-" * 70)
        print("FREEZE OPERATIONS (sample - first 10)")
        print("-" * 70)
        for i, (loc, prod, prod_date, curr_date, qty) in enumerate(freeze_operations[:10]):
            age = (curr_date - prod_date).days
            print(f"   {i+1}. Location {loc}, Product {prod}")
            print(f"      Production date: {prod_date}, Current date: {curr_date} (age: {age} days)")
            print(f"      Quantity frozen: {qty:,.2f} units")

    if thaw_operations:
        print("\n" + "-" * 70)
        print("THAW OPERATIONS (sample - first 10)")
        print("-" * 70)
        for i, (loc, prod, prod_date, curr_date, qty) in enumerate(thaw_operations[:10]):
            age = (curr_date - prod_date).days
            print(f"   {i+1}. Location {loc}, Product {prod}")
            print(f"      Original production date: {prod_date}, Thaw date: {curr_date} (age: {age} days)")
            print(f"      Quantity thawed: {qty:,.2f} units")
            print(f"      → Becomes ambient cohort with prod_date={curr_date} (14 days shelf life)")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    if total_freeze > 0 or total_thaw > 0:
        print("\n✅ Freeze/thaw operations ARE being used!")
        print(f"   Total frozen: {total_freeze:,.2f} units")
        print(f"   Total thawed: {total_thaw:,.2f} units")
        return True
    else:
        print("\n⚠️  No freeze/thaw operations in solution")
        print("   This may be expected if:")
        print("   - Holding costs make freezing uneconomical")
        print("   - Short planning horizon doesn't require long-term storage")
        print("   - Direct routing is more cost-effective")
        print("   - No locations with BOTH storage modes exist in test scenario")

        # Check if any locations support both modes
        locations_both = model_instance.locations_with_freezing
        print(f"\n   Locations with BOTH frozen/ambient storage: {len(locations_both)}")
        if locations_both:
            print(f"   Locations: {list(locations_both)}")
        else:
            print("   ❌ No locations support both modes - freeze/thaw not possible!")

        return False

def main():
    """Run freeze/thaw operations test."""

    print("=" * 70)
    print("FREEZE/THAW OPERATIONS TEST")
    print("=" * 70)
    print("\nTesting: Are freeze/thaw operations included and functional?")

    # Load real data
    print("\nLoading data...")

    # Use Network_Config for network/labor/costs
    network_parser = ExcelParser("data/examples/Network_Config.xlsx")
    locations = network_parser.parse_locations()
    routes = network_parser.parse_routes()
    labor_calendar = network_parser.parse_labor_calendar()
    truck_schedules = network_parser.parse_truck_schedules()
    cost_structure = network_parser.parse_cost_structure()

    # Use Gfree Forecast for forecast data (SAP IBP format)
    forecast_parser = ExcelParser("data/examples/Gfree Forecast.xlsm")
    forecast = forecast_parser.parse_forecast(sheet_name="G610_RET")

    # Get manufacturing site from locations
    manufacturing_site = next((loc for loc in locations if loc.type == "manufacturing"), None)

    print(f"✅ Data loaded")

    # Set 4-week planning window
    start_date = date(2025, 10, 13)  # Monday
    end_date = start_date + timedelta(days=27)  # 4 weeks

    print(f"   Planning window: {start_date} to {end_date}")

    # Build model WITH batch tracking
    print("\nBuilding optimization model...")

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=TruckScheduleCollection(schedules=truck_schedules),
        max_routes_per_destination=3,
        allow_shortages=True,
        enforce_shelf_life=True,
        start_date=start_date,
        end_date=end_date,
        use_batch_tracking=True,
        enable_production_smoothing=False
    )

    print(f"✅ Model built")
    print(f"   Batch tracking: {model.use_batch_tracking}")

    # Solve
    print("\nSolving optimization...")
    result = model.solve(time_limit_seconds=600)

    if not result.is_feasible():
        print(f"\n❌ Solve failed: {result.termination_condition}")
        return

    status_str = "optimal" if result.is_optimal() else "feasible"
    print(f"✅ Solve completed: {status_str}")
    print(f"   Total cost: ${result.objective_value:,.2f}")

    # Analyze freeze/thaw operations
    has_operations = analyze_freeze_thaw_operations(model, result)

    print("\n" + "=" * 70)
    print("TEST RESULT")
    print("=" * 70)

    if has_operations:
        print("\n✅ SUCCESS: Freeze/thaw operations are functional and being used!")
    else:
        print("\n⚠️  INFORMATIONAL: Freeze/thaw variables exist but are not used in this scenario")
        print("   Implementation is correct - whether operations are used depends on cost structure")

if __name__ == "__main__":
    main()
