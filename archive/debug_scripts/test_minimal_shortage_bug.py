"""
Minimal test case to reproduce the shortage bug.

Setup:
- 1 product
- 2 locations (manufacturing site 6122 + destination 6110)
- 5 days planning horizon
- Demand: 1000 units/day (5000 total)
- Production capacity: 500 units/day (2500 total - INSUFFICIENT)
- No initial inventory
- Direct route with 1 day transit

Expected Result: 2500 units shortage (50% of demand unmet)
Actual Result (BUG): 0 shortage reported
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.models import (
    Location, Route, Product, Forecast, ForecastEntry,
    ManufacturingSite, LaborCalendar, LaborDay, CostStructure
)
from src.models.truck_schedule import TruckSchedule, TruckScheduleCollection
from src.optimization import IntegratedProductionDistributionModel
from pyomo.environ import value

print("=" * 80)
print("MINIMAL TEST CASE: Shortage Bug Reproduction")
print("=" * 80)

# Setup dates
start_date = datetime(2025, 6, 1)
dates = [start_date + timedelta(days=i) for i in range(5)]

# 1 product
product = Product(id="PROD1", name="Test Product", sku="SKU001")

# 2 locations
manufacturing = Location(
    location_id="6122",
    name="Manufacturing Site",
    location_type="manufacturing"
)

destination = Location(
    location_id="6110",
    name="Destination",
    location_type="breadroom"
)

# Direct route: 6122 -> 6110 (1 day transit, ambient)
route = Route(
    route_id="R1",
    origin_id="6122",
    destination_id="6110",
    intermediate_stop_id=None,
    origin_to_intermediate_days=0,
    intermediate_to_destination_days=0,
    total_transit_days=1,
    transport_mode_origin_to_intermediate=None,
    transport_mode_intermediate_to_destination=None,
    transport_mode_direct="ambient",
    cost_per_unit=1.0
)

# Manufacturing site with limited capacity
mfg_site = ManufacturingSite(
    location_id="6122",
    storage_location_id="6122_Storage",
    storage_mode="ambient",
    units_per_hour=500,  # LIMITED: only 500 UPH instead of 1400
    cost_per_unit=5.0
)

# Labor calendar: 5 weekdays with 12h fixed hours
labor_days = []
for i, date in enumerate(dates):
    labor_days.append(LaborDay(
        date=date,
        fixed_hours=12.0,  # 12h * 500 UPH = 6000 units capacity
        overtime_hours_allowed=0.0,  # NO overtime allowed
        cost_per_hour_regular=100.0,
        cost_per_hour_overtime=150.0,
        minimum_hours_if_used=0.0,
        is_fixed_labor_day=True
    ))

labor_calendar = LaborCalendar(labor_days=labor_days)

# Truck schedule: 1 truck per day
truck_schedules = []
for date in dates:
    truck_schedules.append(TruckSchedule(
        truck_id=f"T{date.strftime('%Y%m%d')}",
        departure_date=date,
        destination_id="6110",
        time_of_day="afternoon",
        capacity_units=14080
    ))

truck_collection = TruckScheduleCollection(schedules=truck_schedules)

# Demand: 1000 units/day for 5 days = 5000 total
# Production capacity: 500 UPH * 12h * 5 days = 30,000 units (wait, that's too much!)
# Let me recalculate: We want INSUFFICIENT capacity
# Demand: 1000 units/day * 5 days = 5000 units
# Let's make capacity: 500 units/day * 5 days = 2500 units (50% shortage expected)

# Actually, let's use 1 hour fixed labor instead:
labor_days = []
for i, date in enumerate(dates):
    labor_days.append(LaborDay(
        date=date,
        fixed_hours=1.0,  # Only 1h * 500 UPH = 500 units/day capacity
        overtime_hours_allowed=0.0,
        cost_per_hour_regular=100.0,
        cost_per_hour_overtime=150.0,
        minimum_hours_if_used=0.0,
        is_fixed_labor_day=True
    ))

labor_calendar = LaborCalendar(labor_days=labor_days)

forecast_entries = []
for date in dates:
    forecast_entries.append(ForecastEntry(
        location_id="6110",
        product_id="PROD1",
        date=date,
        quantity=1000.0  # 1000 units/day demand
    ))

forecast = Forecast(
    entries=forecast_entries,
    start_date=start_date,
    end_date=dates[-1],
    products=[product]
)

# Cost structure
costs = CostStructure(
    labor_cost_per_hour_regular=100.0,
    labor_cost_per_hour_overtime=150.0,
    production_cost_per_unit=5.0,
    transport_cost_per_unit_km=0.01,
    inventory_holding_cost_per_unit_day_ambient=0.02,
    inventory_holding_cost_per_unit_day_frozen=0.05,
    waste_cost_per_unit=20.0,
    shortage_penalty_per_unit=10.0  # $10/unit shortage penalty
)

print("\n📊 Test Setup:")
print(f"  Planning horizon: {len(dates)} days ({start_date.strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')})")
print(f"  Product: {product.id}")
print(f"  Manufacturing site: {manufacturing.location_id}")
print(f"  Destination: {destination.location_id}")
print(f"  Route: {route.route_id} ({route.origin_id} -> {route.destination_id}, {route.total_transit_days} day transit)")
print(f"\n  Production capacity: {mfg_site.units_per_hour} UPH * 1h/day * {len(dates)} days = {mfg_site.units_per_hour * 1 * len(dates):,.0f} units")
print(f"  Total demand: 1000 units/day * {len(dates)} days = {1000 * len(dates):,.0f} units")
print(f"  Expected shortage: {1000 * len(dates) - mfg_site.units_per_hour * 1 * len(dates):,.0f} units ({(1000 * len(dates) - mfg_site.units_per_hour * 1 * len(dates)) / (1000 * len(dates)) * 100:.0f}% of demand)")
print(f"  Shortage penalty: ${costs.shortage_penalty_per_unit}/unit")

print("\n🔧 Building model with allow_shortages=True...")
model = IntegratedProductionDistributionModel(
    forecast=forecast,
    labor_calendar=labor_calendar,
    manufacturing_site=mfg_site,
    cost_structure=costs,
    locations=[manufacturing, destination],
    routes=[route],
    truck_schedules=truck_collection,
    max_routes_per_destination=1,
    allow_shortages=True,  # Allow shortages
    enforce_shelf_life=False,  # Disable shelf life for simplicity
    initial_inventory={}  # No initial inventory
)

print("\n⚙️ Solving...")
result = model.solve(
    solver_name='cbc',
    time_limit_seconds=60,
    mip_gap=0.01,
    use_aggressive_heuristics=False,
    tee=False
)

print(f"\n{'=' * 80}")
print("RESULTS")
print("=" * 80)

if not result.success:
    print(f"\n❌ SOLVE FAILED: {result.status}")
    sys.exit(1)

print(f"\n✅ Solved in {result.solve_time_seconds:.1f}s")
print(f"   Objective: ${result.objective_value:,.2f}")

pyomo_model = model.model

# Calculate totals
total_production = sum(
    value(pyomo_model.production[d, p])
    for d in pyomo_model.dates
    for p in pyomo_model.products
)

total_demand = sum(qty for (dest, prod, d), qty in model.demand.items())

total_shortage = 0
if hasattr(pyomo_model, 'shortage'):
    for (dest, prod, d) in pyomo_model.shortage:
        total_shortage += value(pyomo_model.shortage[dest, prod, d])

total_shipments = sum(
    value(pyomo_model.shipment_leg[(o, dest), p, d])
    for (o, dest) in pyomo_model.legs
    for p in pyomo_model.products
    for d in pyomo_model.dates
)

print(f"\n📈 Summary:")
print(f"  Total production:  {total_production:>10,.0f} units")
print(f"  Total demand:      {total_demand:>10,.0f} units")
print(f"  Total shipments:   {total_shipments:>10,.0f} units")
print(f"  Total shortage:    {total_shortage:>10,.0f} units")
print(f"  Supply deficit:    {total_demand - total_production:>10,.0f} units")

print(f"\n{'=' * 80}")
print("BUG VERIFICATION")
print("=" * 80)

expected_shortage = total_demand - total_production

if abs(total_shortage - expected_shortage) < 1.0:
    print(f"\n✅ CORRECT: Shortage = {total_shortage:,.0f} matches deficit = {expected_shortage:,.0f}")
else:
    print(f"\n🚨 BUG REPRODUCED!")
    print(f"   Expected shortage: {expected_shortage:>10,.0f} units (demand - production)")
    print(f"   Actual shortage:   {total_shortage:>10,.0f} units")
    print(f"   Discrepancy:       {expected_shortage - total_shortage:>10,.0f} units")
    print(f"\n   ROOT CAUSE: Missing constraint 'shortage ≤ demand'")
    print(f"   The solver sets shortage=0 to minimize penalty cost, even with insufficient supply")

# Show daily breakdown
print(f"\n📅 Daily Breakdown:")
print(f"{'Date':<12} {'Production':>12} {'Demand':>12} {'Shortage':>12} {'Should Be':>12}")
print("-" * 64)

for d in sorted(pyomo_model.dates):
    prod_qty = sum(value(pyomo_model.production[d, p]) for p in pyomo_model.products)
    demand_qty = sum(model.demand.get((dest, p, d), 0) for dest, p in
                     [(dest, p) for dest in [destination.location_id] for p in pyomo_model.products])
    shortage_qty = sum(
        value(pyomo_model.shortage[destination.location_id, p, d])
        if (destination.location_id, p, d) in model.demand else 0
        for p in pyomo_model.products
    )
    should_be = max(0, demand_qty - prod_qty)

    print(f"{d.strftime('%Y-%m-%d'):<12} {prod_qty:>12,.0f} {demand_qty:>12,.0f} {shortage_qty:>12,.0f} {should_be:>12,.0f}")

print(f"\n{'=' * 80}")
