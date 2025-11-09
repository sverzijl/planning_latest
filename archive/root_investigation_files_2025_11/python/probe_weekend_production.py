#!/usr/bin/env python3
"""
CONSTRAINT PROBING: Weekend Production Investigation

User observation: Some days run production on weekends.

TECHNIQUE: Force weekend production to zero and observe cost impact.

If cost increases are RATIONAL:
  - Higher labor cost on weekends justified
  - Truck schedules require weekend production
  - Demand timing forces weekend work
  → Weekend production is CORRECT optimization

If cost increases are IRRATIONAL:
  - Costs increase but shouldn't
  - Cheaper alternatives ignored
  - Economic logic violated
  → BUG in formulation

This is the "game changer" technique from disposal bug investigation.
"""

from datetime import datetime, timedelta, date
from pyomo.environ import Constraint
from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType

print("="*100)
print("CONSTRAINT PROBING: Weekend Production Investigation")
print("="*100)

# Load data
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(location_id=e.node_id, product_id=e.product_id,
                 forecast_date=e.demand_date, quantity=e.quantity)
    for e in validated.demand_entries
]
forecast = Forecast(name="Test", entries=forecast_entries)

parser = MultiFileParser(
    'data/examples/Gluten Free Forecast - Latest.xlsm',
    'data/examples/Network_Config.xlsx',
    'data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)
products_dict = {p.id: p for p in validated.products}

start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=27)).date()

cost_structure.waste_cost_multiplier = 10.0

print(f"\nPlanning horizon: {start} to {end}")
print(f"waste_multiplier: {cost_structure.waste_cost_multiplier}")
print()

# ============================================================================
# BASELINE: Solve WITHOUT constraint (allows weekend production)
# ============================================================================

print("="*100)
print("BASELINE SOLVE (Weekend production ALLOWED)")
print("="*100)

model_builder_baseline = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

result_baseline = model_builder_baseline.solve(
    solver_name='appsi_highs',
    time_limit_seconds=120,
    mip_gap=0.01
)

if not result_baseline.success:
    print(f"❌ Baseline solve failed: {result_baseline.termination_condition}")
    exit(1)

print(f"\n✅ Baseline solved")
print(f"  Objective: ${result_baseline.objective_value:,.0f}")

# Extract weekend production from baseline
model_baseline = model_builder_baseline.model
weekend_production = {}
total_weekend_units = 0

if hasattr(model_baseline, 'production'):
    from pyomo.environ import value
    for (node, prod, t) in model_baseline.production:
        if t.weekday() in [5, 6]:  # Saturday=5, Sunday=6
            qty = value(model_baseline.production[node, prod, t])
            if qty > 0.01:
                total_weekend_units += qty
                day_name = 'Saturday' if t.weekday() == 5 else 'Sunday'
                weekend_production[(node, prod, t)] = (qty, day_name)

print(f"\nWeekend production in baseline:")
print(f"  Total: {total_weekend_units:,.0f} units on weekends")
print(f"  Number of weekend production events: {len(weekend_production)}")

if weekend_production:
    print(f"\n  Weekend production details (first 10):")
    for i, ((node, prod, t), (qty, day_name)) in enumerate(list(weekend_production.items())[:10]):
        print(f"    {t} ({day_name}): {qty:,.0f} units of {prod[:30]}")

# ============================================================================
# PROBE: Force weekend production to ZERO
# ============================================================================

print("\n" + "="*100)
print("PROBE SOLVE (Weekend production FORCED TO ZERO)")
print("="*100)

model_builder_probe = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

# Build model
model_probe = model_builder_probe.build_model()

# Add probe constraint: No weekend production
print("\nAdding probe constraint: production[weekend] = 0")

weekend_dates = [d for d in model_probe.dates if d.weekday() in [5, 6]]
print(f"  Constraining {len(weekend_dates)} weekend dates")

if hasattr(model_probe, 'production'):
    weekend_prod_constraints = []
    for (node, prod, t) in model_probe.production:
        if t.weekday() in [5, 6]:
            weekend_prod_constraints.append((node, prod, t))

    # Add constraint
    def no_weekend_production_rule(model, node, prod, t):
        return model.production[node, prod, t] == 0

    model_probe.no_weekend_prod_con = Constraint(
        weekend_prod_constraints,
        rule=no_weekend_production_rule,
        doc="PROBE: Force weekend production to zero"
    )

    print(f"  Constraints added: {len(weekend_prod_constraints)}")

# Solve with probe constraint
from pyomo.environ import value
from pyomo.contrib.appsi.solvers.highs import Highs

print("\nSolving probe model...")
solver = Highs()
solver.config.time_limit = 120
solver.config.mip_gap = 0.01

solver_result = solver.solve(model_probe)

# Check result
from pyomo.contrib.appsi.base import TerminationCondition as AppsiTermCond

success = solver_result.termination_condition == AppsiTermCond.optimal

from src.optimization.base_model import OptimizationResult
result_probe = OptimizationResult(
    success=success,
    objective_value=value(model_probe.obj) if success else None,
    termination_condition=solver_result.termination_condition
)

if not result_probe.success:
    print(f"\n❌ INFEASIBLE with no weekend production!")
    print(f"   Termination: {result_probe.termination_condition}")
    print()
    print("DIAGNOSIS: Weekend production is REQUIRED for feasibility")
    print("  Reasons could be:")
    print("    - Weekday capacity insufficient for demand")
    print("    - Truck schedules need Monday delivery (requires Sunday production)")
    print("    - Demand timing forces weekend work")
    print()
    print("✅ Weekend production is CORRECT (not a bug)")
    exit(0)

print(f"\n✅ Probe solved (feasible without weekend production)")
print(f"  Objective: ${result_probe.objective_value:,.0f}")

# ============================================================================
# ANALYSIS: Compare cost breakdown
# ============================================================================

print("\n" + "="*100)
print("COST COMPARISON ANALYSIS")
print("="*100)

cost_increase = result_probe.objective_value - result_baseline.objective_value

print(f"\nObjective:")
print(f"  Baseline (with weekend):    ${result_baseline.objective_value:>12,.0f}")
print(f"  Probe (no weekend):         ${result_probe.objective_value:>12,.0f}")
print(f"  Increase:                   ${cost_increase:>12,.0f} ({cost_increase/result_baseline.objective_value*100:>5.1f}%)")
print()

# Extract production totals
from pyomo.environ import value

baseline_prod = sum(
    value(model_baseline.production[n, p, t])
    for (n, p, t) in model_baseline.production
)

probe_prod = sum(
    value(model_probe.production[n, p, t])
    for (n, p, t) in model_probe.production
)

baseline_shortage = sum(
    value(model_baseline.shortage[n, p, t])
    for (n, p, t) in model_baseline.shortage
    if value(model_baseline.shortage[n, p, t]) > 0.01
)

probe_shortage = sum(
    value(model_probe.shortage[n, p, t])
    for (n, p, t) in model_probe.shortage
    if value(model_probe.shortage[n, p, t]) > 0.01
)

print(f"Production:")
print(f"  Baseline: {baseline_prod:>12,.0f} units")
print(f"  Probe:    {probe_prod:>12,.0f} units")
print(f"  Change:   {probe_prod - baseline_prod:>12,.0f} units")
print()

print(f"Shortage:")
print(f"  Baseline: {baseline_shortage:>12,.0f} units")
print(f"  Probe:    {probe_shortage:>12,.0f} units")
print(f"  Change:   {probe_shortage - baseline_shortage:>12,.0f} units (${(probe_shortage - baseline_shortage) * 10:,.0f})")
print()

# ============================================================================
# ECONOMIC RATIONALITY CHECK
# ============================================================================

print("="*100)
print("ECONOMIC RATIONALITY CHECK")
print("="*100)

weekend_labor_rate = 1320.0  # $/hour (from labor calendar, weekend premium rate)
weekday_ot_rate = 660.0      # $/hour (weekday overtime)
production_rate = 1400.0     # units/hour

weekend_units_lost = total_weekend_units
shortage_units_gained = probe_shortage - baseline_shortage

print(f"\nWeekend production lost: {weekend_units_lost:,.0f} units")
print(f"  Hours saved: {weekend_units_lost / production_rate:.1f} hours")
print(f"  Weekend labor saved: ${weekend_units_lost / production_rate * weekend_labor_rate:,.0f}")
print()

print(f"Shortage increase: {shortage_units_gained:,.0f} units")
print(f"  Shortage cost increase: ${shortage_units_gained * 10:,.0f}")
print()

# Expected cost change
weekend_hours_saved = weekend_units_lost / production_rate
weekend_labor_saved = weekend_hours_saved * weekend_labor_rate
shortage_cost_increase = shortage_units_gained * 10

expected_change = shortage_cost_increase - weekend_labor_saved
actual_change = cost_increase

print("Expected cost change:")
print(f"  Shortage penalty:  +${shortage_cost_increase:,.0f}")
print(f"  Labor saved:       -${weekend_labor_saved:,.0f}")
print(f"  Net expected:       ${expected_change:,.0f}")
print()

print(f"Actual cost change:   ${actual_change:,.0f}")
print(f"Difference:           ${actual_change - expected_change:,.0f}")
print()

# Evaluate rationality
tolerance = 50000  # $50k tolerance for other costs

if abs(actual_change - expected_change) < tolerance:
    print("="*100)
    print("✅ ECONOMICALLY RATIONAL")
    print("="*100)
    print("\nWeekend production is correct optimization:")
    print(f"  - Avoiding weekend saves ${weekend_labor_saved:,.0f} in labor")
    print(f"  - But costs ${shortage_cost_increase:,.0f} in shortages")
    print(f"  - Net impact: ${actual_change:,.0f}")
    print()
    print("Model correctly chooses weekend production when labor cost < shortage cost.")
    print("This is EXPECTED behavior, not a bug.")
else:
    print("="*100)
    print("❌ ECONOMICALLY IRRATIONAL")
    print("="*100)
    print(f"\nCost increase doesn't match expected:")
    print(f"  Expected: ${expected_change:,.0f}")
    print(f"  Actual:   ${actual_change:,.0f}")
    print(f"  Mystery:  ${actual_change - expected_change:,.0f}")
    print()
    print("→ This signals a FORMULATION BUG")
    print("→ Need to investigate what's causing the mystery cost")
    print()
    print("Possible causes:")
    print("  - Hidden holding costs (inventory accumulation)")
    print("  - Production capacity constraints forcing expensive alternatives")
    print("  - Truck scheduling conflicts")
    print("  - Mix/batch size constraints")
