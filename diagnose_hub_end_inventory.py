"""Diagnose why hubs 6104 and 6125 have inventory at end of horizon.

User observation from UI:
- Final day inventory appears at hubs 6104 and 6125
- Not just a test calculation issue - real in the model

Hypotheses:
1. Hubs receive more than they ship to spoke destinations
2. Hub demand is satisfied but spoke demand creates stranded inventory
3. Missing constraint linking hub inflows to outflows
4. Shipments to spokes are undercounted

This investigates hub material flows specifically.
"""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from src.models.truck_schedule import TruckScheduleCollection
from src.models.forecast import Forecast, ForecastEntry
from src.optimization import IntegratedProductionDistributionModel

# Parse real network
parser = MultiFileParser(
    forecast_file='data/examples/Gfree Forecast.xlsm',
    network_file='data/examples/Network_Config.xlsx',
)

forecast, locations, routes, labor, trucks_list, costs = parser.parse_all()

manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=costs.production_cost_per_unit,
)

trucks = TruckScheduleCollection(schedules=trucks_list)

# Simple 1-week test with hub routing
start_date = date(2025, 10, 13)
end_date = start_date + timedelta(days=6)

print("="*80)
print("HUB END INVENTORY DIAGNOSTIC")
print("="*80)
print()

# Check which locations are hubs
print("Hub identification:")
hubs = [loc for loc in locations if loc.id in ['6104', '6125']]
for hub in hubs:
    print(f"  {hub.id} ({hub.name})")
    # Find routes TO this hub
    routes_to_hub = [r for r in routes if r.destination_id == hub.id]
    print(f"    Inbound: {[r.origin_id for r in routes_to_hub]}")
    # Find routes FROM this hub
    routes_from_hub = [r for r in routes if r.origin_id == hub.id]
    print(f"    Outbound: {[r.destination_id for r in routes_from_hub]}")

print()

# Test scenario: Demand ONLY at spoke destinations (not at hubs themselves)
# This tests if hubs accumulate "pass-through" inventory

# Get spoke destinations for each hub
hub_6104_spokes = ['6105', '6103']  # NSW/ACT spokes
hub_6125_spokes = ['6123', '6134', '6120']  # VIC/TAS/SA spokes

# Create forecast with demand at SPOKES only (no hub demand)
forecast_entries = []
product_id = "HELGAS GFREE WHOLEM 500G"

for day_offset in range(3, 7):  # Days 3-6 (allow 2-day transit via hub)
    # Demand at 6104 spokes
    for spoke in hub_6104_spokes:
        forecast_entries.append(
            ForecastEntry(
                location_id=spoke,
                product_id=product_id,
                forecast_date=start_date + timedelta(days=day_offset),
                quantity=100.0,
            )
        )
    # Demand at 6125 spokes
    for spoke in hub_6125_spokes:
        forecast_entries.append(
            ForecastEntry(
                location_id=spoke,
                product_id=product_id,
                forecast_date=start_date + timedelta(days=day_offset),
                quantity=100.0,
            )
        )

forecast_spokes = Forecast(name="Spokes only", entries=forecast_entries)

total_demand = sum(e.quantity for e in forecast_entries)

print(f"Test scenario:")
print(f"  Demand: {total_demand:,.0f} units at SPOKE destinations only")
print(f"  Hub 6104 spokes: {hub_6104_spokes}")
print(f"  Hub 6125 spokes: {hub_6125_spokes}")
print(f"  NO demand at hubs themselves (pure pass-through)")
print()

# Create and solve model
model = IntegratedProductionDistributionModel(
    forecast=forecast_spokes, labor_calendar=labor, manufacturing_site=manufacturing_site,
    cost_structure=costs, locations=locations, routes=routes,
    truck_schedules=trucks, start_date=start_date, end_date=end_date,
    allow_shortages=True, enforce_shelf_life=True, use_batch_tracking=True,
    initial_inventory=None,
)

print("Solving...")
result = model.solve(solver_name='cbc', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"✓ Solved in {result.solve_time_seconds:.2f}s")
print()

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()

    cohort_inv = solution.get('cohort_inventory', {})
    production = sum(solution.get('production_by_date_product', {}).values())
    consumption = sum(solution.get('cohort_demand_consumption', {}).values())

    # Check hub inventory on final day
    print("="*80)
    print("HUB INVENTORY ON FINAL DAY")
    print("="*80)

    hub_6104_final = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if loc == '6104' and cd == end_date)
    hub_6125_final = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if loc == '6125' and cd == end_date)

    print(f"Hub 6104 final inventory: {hub_6104_final:,.0f} units")
    print(f"Hub 6125 final inventory: {hub_6125_final:,.0f} units")
    print(f"Total hub inventory: {hub_6104_final + hub_6125_final:,.0f} units")
    print()

    if hub_6104_final > 10 or hub_6125_final > 10:
        print("❌ Hubs have end inventory despite only spoke demand!")
        print("   Inventory 'stuck' at hubs not shipping to spokes")
        print()

        # Check flows through hubs
        print("Analyzing hub flows:")
        shipments_by_leg = solution.get('shipments_by_leg_product_date', {})

        # Arrivals at 6104
        arrivals_6104 = sum(
            qty for (leg, prod, dd), qty in shipments_by_leg.items()
            if leg[1] == '6104'
        )

        # Departures from 6104
        departures_6104 = sum(
            qty for (leg, prod, dd), qty in shipments_by_leg.items()
            if leg[0] == '6104'
        )

        # Demand at 6104 itself
        demand_6104 = sum(
            e.quantity for e in forecast_entries
            if e.location_id == '6104'
        )

        print(f"\n  Hub 6104 flows:")
        print(f"    Arrivals (from 6122): {arrivals_6104:,.0f}")
        print(f"    Departures (to spokes): {departures_6104:,.0f}")
        print(f"    Demand at hub: {demand_6104:,.0f}")
        print(f"    Expected balance: arrivals = departures + demand + final_inv")
        print(f"    Actual: {arrivals_6104:,.0f} = {departures_6104:,.0f} + {demand_6104:,.0f} + {hub_6104_final:,.0f}")
        print(f"    Check: {arrivals_6104:,.0f} vs {departures_6104 + demand_6104 + hub_6104_final:,.0f}")

        balance_6104 = arrivals_6104 - (departures_6104 + demand_6104 + hub_6104_final)

        if abs(balance_6104) > 10:
            print(f"    ❌ Imbalance: {balance_6104:+,.0f} units")
        else:
            print(f"    ✓ Balance OK (within rounding)")
            print(f"    → Hub inventory is EXPECTED (routing artifacts)")
    else:
        print("✓ No significant hub end inventory")
        print("  Hubs properly route all inventory to spokes")

    # Overall material balance
    first_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == start_date)
    last_day = sum(qty for (loc, prod, pd, cd, state), qty in cohort_inv.items() if cd == end_date)

    supply = first_day + production
    usage = consumption + last_day
    balance = supply - usage

    print()
    print("="*80)
    print("OVERALL MATERIAL BALANCE")
    print("="*80)
    print(f"Supply: {first_day:,.0f} (day 1) + {production:,.0f} (prod) = {supply:,.0f}")
    print(f"Usage: {consumption:,.0f} (demand) + {last_day:,.0f} (final) = {usage:,.0f}")
    print(f"Balance: {balance:+,.0f}")

    if abs(balance) <= 10:
        print("\n✓ Material balance OK")
    else:
        print(f"\n❌ Material balance issue: {balance:+,.0f} units")
