"""Discover Daily Snapshot issues through comprehensive validation.

This script runs the EXACT same code as the UI and validates all aspects
of the Daily Snapshot to discover any issues.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results
from src.analysis.daily_snapshot import DailySnapshotGenerator
from src.ui_interface.snapshot_validator import DailySnapshotValidator
from datetime import timedelta

# Load data (EXACT UI workflow)
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

# Solve (EXACT UI configuration)
model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=True,
    use_truck_pallet_tracking=True
)

print("Solving model...")
result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02, tee=False)

# Adapt results (EXACT UI code path)
adapted = adapt_optimization_results(
    model=model,
    result={'result': result},
    inventory_snapshot_date=inventory.snapshot_date
)

prod_schedule = adapted['production_schedule']
shipments = adapted['shipments']
solution = model.get_solution()

# Generate Daily Snapshot (EXACT UI code)
locations_dict = {loc.id: loc for loc in locations}
generator = DailySnapshotGenerator(
    production_schedule=prod_schedule,
    shipments=shipments,
    locations_dict=locations_dict,
    forecast=forecast,
    model_solution=solution
)

print(f"\n{'=' * 80}")
print("VALIDATING DAILY SNAPSHOTS FOR ALL DATES")
print(f"{'=' * 80}")

# Validate snapshots for multiple days
all_errors = []
dates_to_check = [start + timedelta(days=i) for i in range(7)]  # First week

for day_offset, check_date in enumerate(dates_to_check):
    snapshot = generator._generate_single_snapshot(check_date)

    # Create validator
    validator = DailySnapshotValidator(
        snapshot=snapshot,
        forecast=forecast,
        locations_dict=locations_dict,
        products=products
    )

    # Run validation
    errors = validator.validate_comprehensive(strict=False)

    if errors:
        all_errors.extend([f"Day {day_offset} ({check_date}): {e}" for e in errors])
        print(f"\n❌ Day {day_offset} ({check_date}): {len(errors)} errors")
        for error in errors[:3]:  # Show first 3
            print(f"  - {error}")
        if len(errors) > 3:
            print(f"  ... and {len(errors) - 3} more")
    else:
        print(f"✅ Day {day_offset} ({check_date}): All validations passed")

    # Print diagnostic report
    if errors:
        print(validator.generate_diagnostic_report())

print(f"\n{'=' * 80}")
print(f"VALIDATION SUMMARY")
print(f"{'=' * 80}")

if not all_errors:
    print("\n✅ ALL SNAPSHOTS VALID - No issues discovered")
else:
    print(f"\n❌ DISCOVERED {len(all_errors)} ISSUES:")
    for error in all_errors[:10]:
        print(f"  - {error}")
    if len(all_errors) > 10:
        print(f"  ... and {len(all_errors) - 10} more")

print(f"\n{'=' * 80}")

# Additional detailed checks for first day with errors
if all_errors:
    print("\nDETAILED ANALYSIS OF FIRST DAY WITH ERRORS:")
    for check_date in dates_to_check:
        snapshot = generator._generate_single_snapshot(check_date)
        validator = DailySnapshotValidator(snapshot, forecast, locations_dict, products)
        errors = validator.validate_comprehensive(strict=False)

        if errors:
            print(f"\nDay: {check_date}")

            # Show inventory details
            print(f"\nInventory records: {len(snapshot.inventory)}")
            for inv in snapshot.inventory[:5]:
                print(f"  {inv.location_id}: {inv.product_id[:30]:30s} = {inv.total_quantity:8.0f} units")

            # Show flows
            print(f"\nInflows: {len(snapshot.inflows)}")
            unknown_inflows = [f for f in snapshot.inflows if f.product_id == 'UNKNOWN']
            if unknown_inflows:
                print(f"  ⚠️ {len(unknown_inflows)} UNKNOWN product inflows:")
                for flow in unknown_inflows[:3]:
                    print(f"    {flow.flow_type} at {flow.location_id}: {flow.quantity:.0f} units")

            # Show production
            print(f"\nProduction activity: {len(snapshot.production_activity)}")
            for batch in snapshot.production_activity:
                print(f"  {batch.product_id[:30]:30s} = {batch.quantity:8.0f} units")

            break  # Only show first day with errors

print("\nValidation complete. Check output above for discovered issues.")
