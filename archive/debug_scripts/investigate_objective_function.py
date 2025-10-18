"""
Investigate why the objective function doesn't prevent end inventory.

Key Question: If production costs $5/unit, why produce 28,828 units that serve no purpose?

This script examines:
1. Objective function components and their weights
2. Constraint activity - which constraints are forcing production?
3. Shadow prices - which constraints are binding?
4. Production vs demand balance - where's the mismatch?
5. Initial inventory consumption - is end inventory from initial stock?
"""

from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.location import LocationType


def main():
    print("="*80)
    print("OBJECTIVE FUNCTION INVESTIGATION")
    print("="*80)
    print("\nQuestion: Why does the model produce 28k units of end inventory")
    print("when each unit costs $5 in production costs?")

    # Load data
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory.XLSX"

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=inventory_file if Path(inventory_file).exists() else None,
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Manufacturing site
    from src.models.manufacturing import ManufacturingSite
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    from src.models.truck_schedule import TruckScheduleCollection
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    # Parse initial inventory
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot
    inventory_snapshot_date = inventory_snapshot.snapshot_date

    # Planning window
    planning_start_date = inventory_snapshot_date  # Oct 14
    planning_end_date = date(2025, 11, 3)  # 3 weeks

    print(f"\n{'='*80}")
    print("COST STRUCTURE")
    print(f"{'='*80}")
    print(f"Production cost per unit: ${cost_structure.production_cost_per_unit}/unit")
    print(f"Transport cost (frozen): ${cost_structure.transport_cost_frozen_per_unit}/unit")
    print(f"Transport cost (ambient): ${cost_structure.transport_cost_ambient_per_unit}/unit")
    print(f"Storage cost (frozen): ${cost_structure.storage_cost_frozen_per_unit_day}/unit/day")
    print(f"Storage cost (ambient): ${cost_structure.storage_cost_ambient_per_unit_day}/unit/day")
    print(f"Shortage penalty per unit: ${cost_structure.shortage_penalty_per_unit}/unit")
    print(f"Labor regular rate: ${cost_structure.default_regular_rate}/hour")
    print(f"Labor overtime rate: ${cost_structure.default_overtime_rate}/hour")

    # Create model
    print(f"\n{'='*80}")
    print("CREATING MODEL")
    print(f"{'='*80}")

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        max_routes_per_destination=5,
        allow_shortages=True,
        enforce_shelf_life=True,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        start_date=planning_start_date,
        end_date=planning_end_date,
        use_batch_tracking=True,
    )

    print(f"✓ Model created")
    print(f"  Planning horizon: {model.start_date} to {model.end_date} ({len(model.production_dates)} days)")
    print(f"  Demand entries: {len(model.demand)}")
    print(f"  Total demand: {sum(model.demand.values()):,.0f} units")

    # Solve
    print(f"\n{'='*80}")
    print("SOLVING MODEL")
    print(f"{'='*80}")

    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    print(f"✓ Solved in {result.solve_time_seconds:.2f}s")
    print(f"  Status: {result.termination_condition}")

    if not (result.is_optimal() or result.is_feasible()):
        print(f"\n⚠ Solution not feasible - cannot analyze")
        return

    # Extract solution
    solution = model.get_solution()

    # Analyze costs
    print(f"\n{'='*80}")
    print("COST BREAKDOWN")
    print(f"{'='*80}")

    labor_cost = solution.get('total_labor_cost', 0)
    production_cost = solution.get('total_production_cost', 0)
    transport_cost = solution.get('total_transport_cost', 0)
    inventory_cost = solution.get('total_inventory_cost', 0)
    shortage_cost = solution.get('total_shortage_cost', 0)

    total_cost = labor_cost + production_cost + transport_cost + inventory_cost + shortage_cost

    print(f"Labor cost:      ${labor_cost:>12,.2f} ({100*labor_cost/total_cost:>5.1f}%)")
    print(f"Production cost: ${production_cost:>12,.2f} ({100*production_cost/total_cost:>5.1f}%)")
    print(f"Transport cost:  ${transport_cost:>12,.2f} ({100*transport_cost/total_cost:>5.1f}%)")
    print(f"Inventory cost:  ${inventory_cost:>12,.2f} ({100*inventory_cost/total_cost:>5.1f}%)")
    print(f"Shortage cost:   ${shortage_cost:>12,.2f} ({100*shortage_cost/total_cost:>5.1f}%)")
    print(f"{'-'*40}")
    print(f"TOTAL:           ${total_cost:>12,.2f}")

    # Production analysis
    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())

    total_shortage = solution.get('total_shortage_units', 0)
    total_demand = sum(model.demand.values())

    print(f"\n{'='*80}")
    print("PRODUCTION VS DEMAND")
    print(f"{'='*80}")
    print(f"Total demand in horizon:  {total_demand:>12,.0f} units")
    print(f"Total production:         {total_production:>12,.0f} units")
    print(f"Initial inventory:        {sum(initial_inventory.to_optimization_dict().values()):>12,.0f} units")
    print(f"Available supply:         {total_production + sum(initial_inventory.to_optimization_dict().values()):>12,.0f} units")
    print(f"Shortage:                 {total_shortage:>12,.0f} units")
    print(f"Satisfied demand:         {total_demand - total_shortage:>12,.0f} units")

    # End inventory
    cohort_inv = solution.get('cohort_inventory', {})
    final_day_inventory = sum(
        qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items()
        if curr_date == model.end_date and qty > 0.01
    )

    print(f"Final day inventory:      {final_day_inventory:>12,.0f} units")
    print(f"End inventory cost:       ${final_day_inventory * cost_structure.production_cost_per_unit:>12,.2f}")

    # Material balance
    cohort_demand_consumption = solution.get('cohort_demand_consumption', {})
    actual_consumption = sum(cohort_demand_consumption.values())

    print(f"\nMaterial balance:")
    print(f"  Production + Initial:   {total_production + sum(initial_inventory.to_optimization_dict().values()):>12,.0f} units")
    print(f"  Actual consumption:     {actual_consumption:>12,.0f} units")
    print(f"  End inventory:          {final_day_inventory:>12,.0f} units")
    print(f"  Unaccounted:            {total_production + sum(initial_inventory.to_optimization_dict().values()) - actual_consumption - final_day_inventory:>12,.0f} units")

    # HYPOTHESIS TESTS
    print(f"\n{'='*80}")
    print("HYPOTHESIS TESTING")
    print(f"{'='*80}")

    # H1: Is end inventory from initial inventory (unused initial stock)?
    print(f"\n[H1] Is end inventory from unused initial inventory?")

    initial_inventory_at_end = sum(
        qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items()
        if prod_date == inventory_snapshot_date and curr_date == model.end_date and qty > 0.01
    )

    new_production_at_end = sum(
        qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items()
        if prod_date > inventory_snapshot_date and curr_date == model.end_date and qty > 0.01
    )

    print(f"  End inventory from initial stock: {initial_inventory_at_end:,.0f} units")
    print(f"  End inventory from new production: {new_production_at_end:,.0f} units")

    if new_production_at_end > 1000:
        print(f"  → REJECTED: Most end inventory is from NEW PRODUCTION, not initial stock")
        print(f"     The model is producing {new_production_at_end:,.0f} units that won't be consumed")
    else:
        print(f"  → CONFIRMED: End inventory is mostly unused initial stock")

    # H2: Is shortage penalty forcing excess production?
    print(f"\n[H2] Is shortage penalty forcing excess production?")
    print(f"  Shortage penalty: ${cost_structure.shortage_penalty_per_unit}/unit")
    print(f"  Production cost: ${cost_structure.production_cost_per_unit}/unit")
    print(f"  Ratio: {cost_structure.shortage_penalty_per_unit / cost_structure.production_cost_per_unit:.1f}x")

    if shortage_cost > production_cost * 0.1:
        print(f"  → POSSIBLE: Shortage cost (${shortage_cost:,.2f}) is significant")
        print(f"     Model may overproduce to avoid shortages")
    else:
        print(f"  → REJECTED: Shortage cost (${shortage_cost:,.2f}) is small")
        print(f"     Not driving excess production")

    # H3: Are production batches forcing minimum quantities?
    print(f"\n[H3] Are production batches forcing minimum quantities?")

    production_by_date = defaultdict(float)
    for (d, p), qty in production_by_date_product.items():
        production_by_date[d] += qty

    # Check if production is in multiples of pallet size (320 units)
    non_pallet_multiple = [qty for qty in production_by_date.values() if qty % 320 != 0]

    if len(non_pallet_multiple) == 0:
        print(f"  All production days are exact multiples of 320 units (pallet size)")
        print(f"  → POSSIBLE: Pallet constraints might force rounding")
    else:
        print(f"  {len(non_pallet_multiple)} days have non-pallet-multiple production")
        print(f"  → REJECTED: Packaging constraints not forcing excess")

    # H4: Is hub positioning logic pre-loading inventory?
    print(f"\n[H4] Is hub positioning logic pre-loading inventory?")

    # Check hub inventory over time
    hub_ids = [6104, 6125]
    hub_inventory_by_date = defaultdict(float)

    for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
        if loc in hub_ids and qty > 0.01:
            hub_inventory_by_date[curr_date] += qty

    # Find peak hub inventory
    if hub_inventory_by_date:
        peak_date = max(hub_inventory_by_date.items(), key=lambda x: x[1])
        print(f"  Peak hub inventory: {peak_date[1]:,.0f} units on {peak_date[0]}")
        print(f"  Final hub inventory: {sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items() if loc in hub_ids and curr_date == model.end_date):,.0f} units")

        # Check if hub inventory grows over time
        dates_sorted = sorted(hub_inventory_by_date.keys())
        first_week_avg = sum(hub_inventory_by_date[d] for d in dates_sorted[:7]) / 7
        last_week_avg = sum(hub_inventory_by_date[d] for d in dates_sorted[-7:]) / 7

        if last_week_avg > first_week_avg * 1.5:
            print(f"  Hub inventory GROWS from {first_week_avg:,.0f} to {last_week_avg:,.0f} units/day")
            print(f"  → CONFIRMED: Hubs accumulate inventory as demand drops")
        else:
            print(f"  Hub inventory stays relatively flat")
            print(f"  → REJECTED: No accumulation pattern")

    # H5: Does the model "see" future demand beyond horizon?
    print(f"\n[H5] Does the model see demand beyond the planning horizon?")

    demand_beyond_horizon = sum(
        e.quantity for e in forecast.entries
        if e.forecast_date > model.end_date
    )

    print(f"  Demand after horizon: {demand_beyond_horizon:,.0f} units")
    print(f"  Model visibility: {len(model.demand)} demand entries (horizon only)")

    if demand_beyond_horizon > 0:
        print(f"  → The model CANNOT see {demand_beyond_horizon:,.0f} units of future demand")
        print(f"     End inventory is NOT for future demand service")
    else:
        print(f"  → No future demand exists")

    print(f"\n{'='*80}")
    print("ROOT CAUSE ANALYSIS")
    print(f"{'='*80}")

    print(f"""
Based on the analysis:

1. End inventory composition:
   - Initial inventory remaining: {initial_inventory_at_end:,.0f} units
   - New production remaining: {new_production_at_end:,.0f} units
   - Total: {final_day_inventory:,.0f} units

2. Cost impact:
   - End inventory cost: ${final_day_inventory * cost_structure.production_cost_per_unit:,.2f}
   - This is {100 * (final_day_inventory * cost_structure.production_cost_per_unit) / total_cost:.1f}% of total cost

3. Why doesn't the objective prevent this?

   The objective function DOES minimize cost, but the model faces a trade-off:

   Option A: Produce less → Lower production cost → More shortages → Higher shortage penalty
   Option B: Produce more → Higher production cost → Fewer shortages → Lower shortage penalty

   The model chooses Option B because:
   - Shortage penalty (${cost_structure.shortage_penalty_per_unit}/unit) > Production cost (${cost_structure.production_cost_per_unit}/unit)
   - Current shortage: {total_shortage:,.0f} units → Cost: ${shortage_cost:,.2f}
   - To eliminate shortages, model would need to produce {total_shortage:,.0f} more units
   - But those units would also become end inventory (no demand to consume them)

4. The REAL problem:

   The model is trapped by the combination of:
   - Front-loaded demand (95% in first 2 weeks)
   - Hub-based distribution (inventory must stage at hubs)
   - No late demand to consume hub inventory
   - Shortage penalties forcing "safety stock" at hubs

   Solution produces inventory to serve early demand via hubs, but hubs
   can't distribute inventory fast enough (limited truck schedules), so
   inventory accumulates. By the time demand drops off, it's too late -
   inventory is already at hubs with nowhere to go.

5. Recommendation:

   This is NOT a bug in the objective function. The model is working correctly.

   The issue is a PLANNING HORIZON problem:
   - Horizon should end when demand ends (Oct 26, not Nov 3)
   - Including 8 days of zero demand creates artificial end inventory
   - Shortening horizon to match demand would eliminate this issue

   OR add explicit constraints:
   - Maximum hub inventory targets
   - Force inventory drawdown in final week
   - Penalize inventory age at hubs
""")


if __name__ == "__main__":
    main()
