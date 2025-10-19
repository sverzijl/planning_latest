"""Check if capacity constraints are properly enforced in solved model."""

import sys
from pathlib import Path
from datetime import timedelta
from pyomo.core import value

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel


def check_capacity_constraints():
    """Verify capacity constraints in solved model."""

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

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
    end_date = start_date + timedelta(weeks=1)  # Just 1 week for speed

    print("Building and solving model...")
    model_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model_obj.solve(time_limit_seconds=60, mip_gap=0.01, tee=False)

    if not result.success:
        print(f"Solve failed: {result.infeasibility_message}")
        return

    print(f"Solved: {result.termination_condition}\n")

    # Access the solved Pyomo model
    pyomo_model = model_obj.model

    # Check production capacity constraints
    print("="*80)
    print("CAPACITY CONSTRAINT VERIFICATION")
    print("="*80)

    if not hasattr(pyomo_model, 'production_capacity_con'):
        print("❌ ERROR: production_capacity_con not found in model!")
        return

    print(f"\nTotal capacity constraints: {len(pyomo_model.production_capacity_con)}")

    # Check each constraint
    violations = []

    for (node_id, date) in pyomo_model.production_capacity_con:
        constraint = pyomo_model.production_capacity_con[node_id, date]

        # Get constraint LHS and RHS
        try:
            lhs = value(constraint.body)
            rhs = value(constraint.upper) if constraint.has_ub() else float('inf')

            labor_day = labor_calendar.get_labor_day(date)
            day_name = date.strftime('%A')

            # Check for violations
            if lhs > rhs + 0.01:  # Allow small numerical tolerance
                violations.append((node_id, date, lhs, rhs))
                print(f"\n❌ VIOLATION: {date} ({day_name})")
                print(f"   LHS (used): {lhs:.2f}h")
                print(f"   RHS (limit): {rhs:.2f}h")
                print(f"   Excess: {lhs - rhs:.2f}h")

                # Extract components
                if hasattr(pyomo_model, 'production_day') and (node_id, date) in pyomo_model.production_day:
                    prod_day = value(pyomo_model.production_day[node_id, date])
                    num_products = value(pyomo_model.num_products_produced[node_id, date])

                    print(f"   production_day: {prod_day}")
                    print(f"   num_products: {num_products}")

                    # Calculate overhead
                    startup = 0.5
                    shutdown = 0.5
                    changeover = 1.0
                    overhead = (startup + shutdown - changeover) * prod_day + changeover * num_products

                    # Calculate production time
                    total_units = sum(
                        value(pyomo_model.production[node_id, prod, date])
                        for prod in pyomo_model.products
                        if (node_id, prod, date) in pyomo_model.production
                    )
                    prod_time = total_units / 1400.0

                    print(f"   Production time: {prod_time:.2f}h")
                    print(f"   Overhead time: {overhead:.2f}h")
                    print(f"   Total: {prod_time + overhead:.2f}h")

        except Exception as e:
            print(f"Error checking constraint for {date}: {e}")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    if violations:
        print(f"❌ Found {len(violations)} capacity constraint violations!")
        print("This means the constraint is NOT being properly enforced.")
    else:
        print("✅ All capacity constraints satisfied")


if __name__ == "__main__":
    check_capacity_constraints()
