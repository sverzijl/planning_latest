"""
Diagnostic script to test multiple 4-week windows and analyze end inventory patterns.

This script tests the optimization model with different 4-week windows to determine
if the 11k end inventory issue is:
1. Consistent across all windows (systematic issue)
2. Varies by window (demand-pattern-specific)
3. Increases with certain demand characteristics

Tests multiple windows from the forecast data and collects:
- End inventory at each location
- Demand patterns in last 3 days
- Production patterns in last 3 days
- Shipments beyond horizon
- Material balance metrics
"""

from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.location import LocationType


def test_window(
    forecast, locations, routes, labor_calendar, truck_schedules,
    cost_structure, manufacturing_site, start_date, end_date
):
    """Test a single 4-week window and return diagnostics."""

    print(f"\n{'='*80}")
    print(f"TESTING WINDOW: {start_date} to {end_date}")
    print(f"{'='*80}")

    # Create model
    model_start = time.time()

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
        initial_inventory=None,  # Start from zero for clean comparison
        inventory_snapshot_date=None,
        start_date=start_date,
        end_date=end_date,
        use_batch_tracking=True,
    )

    model_build_time = time.time() - model_start
    print(f"✓ Model built in {model_build_time:.2f}s")
    print(f"  Planning horizon: {len(model.production_dates)} days")
    print(f"  Actual dates: {model.start_date} to {model.end_date}")

    # Solve
    solve_start = time.time()

    result = model.solve(
        solver_name='cbc',
        time_limit_seconds=120,
        mip_gap=0.01,
        use_aggressive_heuristics=True,
        tee=False,
    )

    solve_time = time.time() - solve_start

    print(f"✓ Solved in {solve_time:.2f}s")
    print(f"  Status: {result.termination_condition}")

    if not (result.is_optimal() or result.is_feasible()):
        print(f"  ⚠ Solution not feasible - skipping analysis")
        return None

    # Extract solution
    solution = model.get_solution()
    if not solution:
        print(f"  ⚠ No solution available - skipping analysis")
        return None

    # Calculate metrics
    production_by_date_product = solution.get('production_by_date_product', {})
    total_production = sum(production_by_date_product.values())
    total_shortage = solution.get('total_shortage_units', 0)

    # Demand in horizon
    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if model.start_date <= e.forecast_date <= model.end_date
    )

    fill_rate = 100 * (1 - total_shortage / demand_in_horizon) if demand_in_horizon > 0 else 100

    # Final day inventory
    final_day_inventory = 0.0
    final_day_by_location = {}

    if 'cohort_inventory' in solution:
        cohort_inv = solution['cohort_inventory']

        for (loc, prod, prod_date, curr_date, state), qty in cohort_inv.items():
            if curr_date == model.end_date and qty > 0.01:
                final_day_inventory += qty
                if loc not in final_day_by_location:
                    final_day_by_location[loc] = 0.0
                final_day_by_location[loc] += qty

    # Shipments beyond horizon
    shipments = model.get_shipment_plan() or []
    shipments_after_horizon = [s for s in shipments if s.delivery_date > model.end_date]
    total_in_transit_beyond = sum(s.quantity for s in shipments_after_horizon)

    # Demand after horizon
    demand_after_horizon = sum(
        e.quantity for e in forecast.entries
        if e.forecast_date > model.end_date
    )

    # Last 3 days demand in horizon
    last_3_days_start = model.end_date - timedelta(days=2)
    last_3_days_demand = sum(
        e.quantity for e in forecast.entries
        if last_3_days_start <= e.forecast_date <= model.end_date
    )

    # Last 3 days production
    last_3_days_production = sum(
        qty for (d, p), qty in production_by_date_product.items()
        if last_3_days_start <= d <= model.end_date
    )

    # Material balance
    cohort_demand_consumption = solution.get('cohort_demand_consumption', {})
    actual_consumption = sum(cohort_demand_consumption.values())
    total_outflow = actual_consumption + final_day_inventory + total_in_transit_beyond
    material_balance = total_production - total_outflow

    # Print summary
    print(f"\n--- Summary ---")
    print(f"Demand in horizon: {demand_in_horizon:,.0f} units")
    print(f"Total production: {total_production:,.0f} units")
    print(f"Fill rate: {fill_rate:.1f}%")
    print(f"Final day inventory: {final_day_inventory:,.0f} units")
    print(f"In-transit beyond: {total_in_transit_beyond:,.0f} units")
    print(f"Material balance: {material_balance:+,.0f} units")
    print(f"Last 3 days demand: {last_3_days_demand:,.0f} units ({100*last_3_days_demand/demand_in_horizon:.1f}% of total)")
    print(f"Last 3 days production: {last_3_days_production:,.0f} units ({100*last_3_days_production/total_production:.1f}% of total)")

    if final_day_by_location:
        print(f"\nEnd inventory by location:")
        for loc, qty in sorted(final_day_by_location.items(), key=lambda x: x[1], reverse=True):
            if qty > 0.01:
                print(f"  {loc}: {qty:,.0f} units")

    # Return diagnostics dict
    return {
        'start_date': model.start_date,
        'end_date': model.end_date,
        'solve_time': solve_time,
        'status': result.termination_condition,
        'demand_in_horizon': demand_in_horizon,
        'total_production': total_production,
        'total_shortage': total_shortage,
        'fill_rate': fill_rate,
        'final_day_inventory': final_day_inventory,
        'final_day_by_location': final_day_by_location,
        'in_transit_beyond': total_in_transit_beyond,
        'demand_after_horizon': demand_after_horizon,
        'last_3_days_demand': last_3_days_demand,
        'last_3_days_production': last_3_days_production,
        'actual_consumption': actual_consumption,
        'material_balance': material_balance,
    }


def main():
    """Run diagnostic across multiple 4-week windows."""

    print("="*80)
    print("MULTIPLE WINDOW DIAGNOSTIC")
    print("="*80)
    print("\nGoal: Determine if 11k end inventory is systematic or demand-pattern-specific")
    print("Strategy: Test multiple 4-week windows and compare end inventory patterns")

    # Load data files
    data_dir = Path("data/examples")
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    print(f"\nLoading data from:")
    print(f"  Forecast: {forecast_file}")
    print(f"  Network: {network_file}")

    parser = MultiFileParser(
        forecast_file=forecast_file,
        network_file=network_file,
        inventory_file=None,  # No initial inventory for clean comparison
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Create manufacturing site
    from src.models.manufacturing import ManufacturingSite
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found")

    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id,
        name=manuf_loc.name,
        storage_mode=manuf_loc.storage_mode,
        production_rate=manuf_loc.production_rate if hasattr(manuf_loc, 'production_rate') and manuf_loc.production_rate else 1400.0,
        daily_startup_hours=0.5,
        daily_shutdown_hours=0.25,
        default_changeover_hours=0.5,
        production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    # Convert truck schedules
    from src.models.truck_schedule import TruckScheduleCollection
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    print(f"\n✓ Data loaded")
    print(f"  Forecast entries: {len(forecast.entries)}")
    print(f"  Date range: {min(e.forecast_date for e in forecast.entries)} to {max(e.forecast_date for e in forecast.entries)}")
    print(f"  Total demand: {sum(e.quantity for e in forecast.entries):,.0f} units")

    # Define windows to test
    base_date = date(2025, 10, 13)  # Current test baseline

    windows = [
        ("Baseline (Oct 13)", base_date, base_date + timedelta(weeks=4)),
        ("-2 weeks", base_date - timedelta(weeks=2), base_date - timedelta(weeks=2) + timedelta(weeks=4)),
        ("-1 week", base_date - timedelta(weeks=1), base_date - timedelta(weeks=1) + timedelta(weeks=4)),
        ("+1 week", base_date + timedelta(weeks=1), base_date + timedelta(weeks=1) + timedelta(weeks=4)),
        ("+2 weeks", base_date + timedelta(weeks=2), base_date + timedelta(weeks=2) + timedelta(weeks=4)),
    ]

    print(f"\n{'='*80}")
    print("TESTING MULTIPLE WINDOWS")
    print(f"{'='*80}")

    results = []

    for name, start_date, end_date in windows:
        print(f"\n\n{'#'*80}")
        print(f"# WINDOW: {name}")
        print(f"# {start_date} to {end_date}")
        print(f"{'#'*80}")

        try:
            diagnostics = test_window(
                forecast, locations, routes, labor_calendar, truck_schedules,
                cost_structure, manufacturing_site, start_date, end_date
            )

            if diagnostics:
                diagnostics['name'] = name
                results.append(diagnostics)
        except Exception as e:
            print(f"\n⚠ ERROR testing window {name}: {e}")
            import traceback
            traceback.print_exc()

    # Summary comparison
    print(f"\n\n{'='*80}")
    print("COMPARISON ACROSS WINDOWS")
    print(f"{'='*80}")

    if not results:
        print("No successful results to compare")
        return

    print(f"\n{'Window':<20} {'Demand':>12} {'Production':>12} {'End Inv':>12} {'In-Transit':>12} {'Balance':>12}")
    print("-" * 92)

    for r in results:
        print(f"{r['name']:<20} {r['demand_in_horizon']:>12,.0f} {r['total_production']:>12,.0f} {r['final_day_inventory']:>12,.0f} {r['in_transit_beyond']:>12,.0f} {r['material_balance']:>12,.0f}")

    # Analysis
    print(f"\n{'='*80}")
    print("ANALYSIS")
    print(f"{'='*80}")

    end_inventories = [r['final_day_inventory'] for r in results]
    avg_end_inv = sum(end_inventories) / len(end_inventories)
    min_end_inv = min(end_inventories)
    max_end_inv = max(end_inventories)

    print(f"\nEnd Inventory Statistics:")
    print(f"  Average: {avg_end_inv:,.0f} units")
    print(f"  Min: {min_end_inv:,.0f} units")
    print(f"  Max: {max_end_inv:,.0f} units")
    print(f"  Range: {max_end_inv - min_end_inv:,.0f} units")
    print(f"  Std Dev: {(sum((x - avg_end_inv)**2 for x in end_inventories) / len(end_inventories))**0.5:,.0f} units")

    # Check for patterns
    if max_end_inv - min_end_inv < 1000:
        print(f"\n✓ CONSISTENT: End inventory is consistent across windows (< 1k variation)")
        print(f"  → This suggests a SYSTEMATIC issue, not demand-pattern-specific")
    else:
        print(f"\n⚠ VARIABLE: End inventory varies significantly across windows ({max_end_inv - min_end_inv:,.0f} units)")
        print(f"  → This suggests a DEMAND-PATTERN-SPECIFIC issue")

    # Check last 3 days patterns
    print(f"\nLast 3 Days Demand as % of Total:")
    for r in results:
        pct = 100 * r['last_3_days_demand'] / r['demand_in_horizon'] if r['demand_in_horizon'] > 0 else 0
        print(f"  {r['name']:<20}: {pct:>5.1f}%  (demand: {r['last_3_days_demand']:>8,.0f}, end inv: {r['final_day_inventory']:>8,.0f})")

    # Check correlation between late demand and end inventory
    import statistics
    if len(results) >= 3:
        late_demand_pcts = [100 * r['last_3_days_demand'] / r['demand_in_horizon'] for r in results if r['demand_in_horizon'] > 0]
        end_invs = [r['final_day_inventory'] for r in results if r['demand_in_horizon'] > 0]

        if len(late_demand_pcts) == len(end_invs) and len(late_demand_pcts) >= 3:
            # Calculate correlation (simple)
            mean_late = statistics.mean(late_demand_pcts)
            mean_inv = statistics.mean(end_invs)

            numerator = sum((late_demand_pcts[i] - mean_late) * (end_invs[i] - mean_inv) for i in range(len(late_demand_pcts)))
            denom = (sum((x - mean_late)**2 for x in late_demand_pcts) * sum((x - mean_inv)**2 for x in end_invs))**0.5

            if denom > 0:
                correlation = numerator / denom
                print(f"\nCorrelation between late demand % and end inventory: {correlation:.3f}")

                if abs(correlation) > 0.7:
                    if correlation > 0:
                        print(f"  → STRONG POSITIVE correlation: Higher late demand → More end inventory")
                        print(f"     Hypothesis: Model produces for late demand but horizon cuts off before consumption")
                    else:
                        print(f"  → STRONG NEGATIVE correlation: Higher late demand → Less end inventory")
                        print(f"     Unexpected - needs investigation")
                else:
                    print(f"  → WEAK correlation: Late demand doesn't explain end inventory")

    # Final recommendations
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print(f"{'='*80}")

    if max_end_inv > 5000:  # Significant end inventory
        print("\n1. End inventory > 5k detected in at least one window")

        if max_end_inv - min_end_inv < 1000:
            print("   → Consistent across windows → Likely systematic issue")
            print("   → Check: Objective function weighting (end inventory penalty missing?)")
            print("   → Check: Flow conservation constraints at hubs")
            print("   → Check: Planning horizon extension logic")
        else:
            print("   → Varies by window → Likely demand-pattern-specific")
            print("   → Check: Demand clustering in last 3 days")
            print("   → Check: Truck schedule boundary conditions")
            print("   → Check: Product mix effects")

        # Check if it's hub-specific
        hub_inventory_windows = []
        for r in results:
            hub_inv = sum(qty for loc, qty in r['final_day_by_location'].items() if loc in [6104, 6125])
            if hub_inv > 100:
                hub_inventory_windows.append(r['name'])

        if len(hub_inventory_windows) > 0:
            print(f"\n2. Hub inventory detected in: {', '.join(hub_inventory_windows)}")
            print("   → Hub-specific issue (6104, 6125)")
            print("   → Check: Hub dual role (transit + destination)")
            print("   → Check: Spoke deliveries scheduled after horizon")
    else:
        print("\n✓ All windows show < 5k end inventory")
        print("   → Issue may have been resolved or doesn't exist in tested windows")


if __name__ == "__main__":
    main()
