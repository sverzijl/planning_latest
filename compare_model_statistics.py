"""Compare model statistics for 14-day vs 21-day windows to understand scaling."""

import sys
sys.path.insert(0, '/home/sverzijl/planning_latest')

from datetime import date
from pyomo.environ import Var
from src.parsers import ExcelParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast
from src.optimization import IntegratedProductionDistributionModel

print("=" * 80)
print("MODEL STATISTICS COMPARISON: 14-DAY vs 21-DAY WINDOWS")
print("=" * 80)

# Load data
print("\nLoading data...")
network_parser = ExcelParser('data/examples/Network_Config.xlsx')
forecast_parser = ExcelParser('data/examples/Gfree Forecast_Converted.xlsx')

locations = network_parser.parse_locations()
routes = network_parser.parse_routes()
labor_calendar = network_parser.parse_labor_calendar()
truck_schedules = TruckScheduleCollection(schedules=network_parser.parse_truck_schedules())
cost_structure = network_parser.parse_cost_structure()
manufacturing_site = next((loc for loc in locations if loc.type == 'manufacturing'), None)
full_forecast = forecast_parser.parse_forecast()

# Test with first 3 weeks of data
start_date = date(2025, 6, 2)
forecast_entries = [e for e in full_forecast.entries if e.forecast_date >= start_date]

def get_model_stats(window_days, description):
    """Build model and extract statistics without solving."""
    end_date = start_date + __import__('datetime').timedelta(days=window_days - 1)

    # Filter forecast to window
    window_forecast_entries = [
        e for e in forecast_entries
        if start_date <= e.forecast_date <= end_date
    ]

    window_forecast = Forecast(
        name=f"test_{window_days}d",
        entries=window_forecast_entries,
        creation_date=full_forecast.creation_date
    )

    print(f"\n{'=' * 80}")
    print(f"{description}: {window_days}-DAY WINDOW")
    print(f"{'=' * 80}")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Demand entries: {len(window_forecast.entries)}")
    print(f"Total demand: {sum(e.quantity for e in window_forecast.entries):,.0f} units")

    # Build model
    print(f"\nBuilding model...")
    model = IntegratedProductionDistributionModel(
        forecast=window_forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        max_routes_per_destination=5,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Build the Pyomo model
    pyomo_model = model.build_model()

    # Extract statistics
    num_vars = pyomo_model.nvariables()
    num_constraints = pyomo_model.nconstraints()

    # Count binary/integer vs continuous
    binary_vars = 0
    integer_vars = 0
    continuous_vars = 0

    for var in pyomo_model.component_data_objects(Var):
        if var.is_binary():
            binary_vars += 1
        elif var.is_integer():
            integer_vars += 1
        else:
            continuous_vars += 1

    print(f"\nModel Statistics:")
    print(f"  Total variables: {num_vars:,}")
    print(f"    - Continuous: {continuous_vars:,}")
    print(f"    - Integer: {integer_vars:,}")
    print(f"    - Binary: {binary_vars:,}")
    print(f"  Total constraints: {num_constraints:,}")

    # Count specific variable types
    production_vars = len([v for v in pyomo_model.production])
    shipment_vars = len([v for v in pyomo_model.shipment])

    print(f"\nKey Variables:")
    print(f"  Production variables: {production_vars:,}")
    print(f"  Shipment variables: {shipment_vars:,}")

    if hasattr(pyomo_model, 'inventory'):
        inventory_vars = len([v for v in pyomo_model.inventory])
        print(f"  Inventory variables: {inventory_vars:,}")

    if hasattr(pyomo_model, 'labor_hours'):
        labor_vars = len([v for v in pyomo_model.labor_hours])
        print(f"  Labor hours variables: {labor_vars:,}")

    return {
        'days': window_days,
        'total_vars': num_vars,
        'continuous_vars': continuous_vars,
        'integer_vars': integer_vars,
        'binary_vars': binary_vars,
        'constraints': num_constraints,
        'production_vars': production_vars,
        'shipment_vars': shipment_vars,
    }

# Build and compare models
stats_14 = get_model_stats(14, "MODEL A")
stats_21 = get_model_stats(21, "MODEL B")

# Comparison
print(f"\n{'=' * 80}")
print("SCALING ANALYSIS")
print(f"{'=' * 80}")

print(f"\n{'Metric':<30} {'14-day':<15} {'21-day':<15} {'Ratio':<10} {'Expected':<10}")
print("-" * 80)

metrics = [
    ('Total variables', 'total_vars', 1.5),
    ('  Continuous', 'continuous_vars', 1.5),
    ('  Integer', 'integer_vars', 1.5),
    ('  Binary', 'binary_vars', 1.5),
    ('Total constraints', 'constraints', 1.5),
    ('Production variables', 'production_vars', 1.5),
    ('Shipment variables', 'shipment_vars', 1.5),
]

for label, key, expected_ratio in metrics:
    val_14 = stats_14[key]
    val_21 = stats_21[key]
    actual_ratio = val_21 / val_14 if val_14 > 0 else 0

    status = "✓" if abs(actual_ratio - expected_ratio) < 0.5 else "⚠"

    print(f"{label:<30} {val_14:<15,} {val_21:<15,} {actual_ratio:<10.2f} {expected_ratio:<10.1f} {status}")

print(f"\n{'=' * 80}")
print("FINDINGS")
print(f"{'=' * 80}")

total_ratio = stats_21['total_vars'] / stats_14['total_vars']
shipment_ratio = stats_21['shipment_vars'] / stats_14['shipment_vars']

if total_ratio > 2.0:
    print(f"\n❌ EXPONENTIAL SCALING: Variables grow {total_ratio:.1f}x (expected 1.5x)")
    print(f"   This explains the timeout - model complexity explodes!")
elif total_ratio > 1.8:
    print(f"\n⚠ SUPER-LINEAR SCALING: Variables grow {total_ratio:.1f}x (expected 1.5x)")
    print(f"   Slightly higher than linear - may cause solver issues")
else:
    print(f"\n✓ LINEAR SCALING: Variables grow {total_ratio:.1f}x (expected 1.5x)")
    print(f"   Model size scales as expected - bottleneck is elsewhere")

if shipment_ratio > total_ratio + 0.3:
    print(f"\n🔍 SHIPMENT VARIABLE EXPLOSION: Shipment vars grow {shipment_ratio:.1f}x")
    print(f"   Route enumeration may be the bottleneck!")

print(f"\n{'=' * 80}")
