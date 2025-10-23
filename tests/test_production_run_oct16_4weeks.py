"""Reproduction Test: User's Exact Production Run

Reproduces the exact scenario user ran to investigate reported issues:

SCENARIO:
- Forecast: Gluten Free Forecast - Latest.xlsm
- Network: Network_Config.xlsx
- Inventory: inventory_latest.XLSX
- Start: October 23, 2025
- Horizon: 4 weeks (28 days)
- MIP Gap: 2%
- Allow shortages: True
- Batch tracking: True

ISSUES TO INVESTIGATE:
1. Status mismatch: Planning shows "feasible", Results shows "INFEASIBLE"
2. Oct 26 (Sunday) has 0.4h production (should be 0h or ≥4h)
3. Nov 4 (public holiday?) has similar 4h minimum violation
4. Truck assignments missing (shows "Unassigned")

This test GATHERS EVIDENCE without proposing fixes yet.
"""

import pytest
from datetime import date
from pathlib import Path
from pyomo.environ import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.location import LocationType


def test_exact_user_scenario_oct16_4weeks():
    """Reproduce exact user scenario and gather diagnostic evidence."""

    print("\n" + "="*80)
    print("REPRODUCTION TEST: User's Oct 16 4-Week Production Run")
    print("="*80)

    # Load exact files user used
    data_dir = Path(__file__).parent.parent / "data" / "examples"

    parser = MultiFileParser(
        forecast_file=str(data_dir / "Gluten Free Forecast - Latest.xlsm"),
        network_file=str(data_dir / "Network_Config.xlsx"),
        inventory_file=str(data_dir / "inventory_latest.XLSX"),
    )

    forecast, locations, routes, labor_calendar, trucks_list, costs = parser.parse_all()

    # Get manufacturing site
    manufacturing_site = next((loc for loc in locations if loc.type == LocationType.MANUFACTURING), None)
    assert manufacturing_site is not None, "No manufacturing site found"

    # Convert to unified
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(trucks_list, manufacturing_site.id)

    # Parse inventory using parser method (like working test does)
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)  # Will use date from file
    initial_inventory = inventory_snapshot
    inventory_snapshot_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    # Exact user settings
    start_date = date(2025, 10, 23)
    end_date = date(2025, 11, 19)  # 4 weeks = 28 days

    print(f"\nScenario Setup:")
    print(f"  Start: {start_date}")
    print(f"  End: {end_date}")
    print(f"  Horizon: {(end_date - start_date).days + 1} days")
    print(f"  MIP Gap: 2%")
    print(f"  Allow shortages: True")
    print(f"  Batch tracking: True")

    # Build model with exact user settings
    model_wrapper = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=costs,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_trucks,
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        force_all_skus_daily=False,
    )

    # Solve with exact user settings
    result = model_wrapper.solve(
        solver_name='appsi_highs',
        time_limit_seconds=600,  # 10 minutes
        mip_gap=0.02,  # 2%
        tee=False,
    )

    print(f"\n" + "="*80)
    print("SOLVE RESULTS")
    print("="*80)
    print(f"  Termination: {result.termination_condition}")
    print(f"  Success flag: {result.success}")
    print(f"  is_optimal(): {result.is_optimal()}")
    print(f"  is_feasible(): {result.is_feasible()}")
    print(f"  Objective: ${result.objective_value:,.2f}" if result.objective_value else "  Objective: None")
    print(f"  Solve time: {result.solve_time_seconds:.1f}s")
    print(f"  MIP Gap: {result.gap * 100:.4f}%" if result.gap else "  MIP Gap: N/A (optimal or gap not reported)")

    # ISSUE #1: Check status mismatch
    print(f"\n" + "="*80)
    print("ISSUE #1: Status Mismatch Investigation")
    print("="*80)
    print(f"  Planning would show: {'feasible' if result.is_feasible() else 'FAILED'}")
    print(f"  Results page logic needs investigation")

    # Verify solve succeeded
    from pyomo.contrib.appsi.base import TerminationCondition as AppsiTC
    solver_succeeded = result.termination_condition == AppsiTC.optimal
    if not (solver_succeeded or result.is_optimal() or result.is_feasible()):
        print(f"  ⚠️ SOLVE FAILED - Cannot investigate further issues")
        return

    print(f"  ✓ Solve succeeded - can investigate other issues")

    pyomo_model = model_wrapper.model
    manufacturing_node = '6122'

    # ISSUE #2 & #3: Investigate non-production day labor violations
    print(f"\n" + "="*80)
    print("ISSUE #2 & #3: Non-Production Day 4-Hour Minimum Investigation")
    print("="*80)

    # Check specific dates mentioned by user
    investigation_dates = [
        (date(2025, 10, 26), "Sunday Oct 26"),
        (date(2025, 11, 4), "Tuesday Nov 4 (possible holiday)"),
    ]

    for date_val, label in investigation_dates:
        if date_val not in pyomo_model.dates:
            print(f"\n{label}: NOT in planning horizon")
            continue

        print(f"\n{label}:")

        # Get labor day info
        labor_day = labor_calendar.get_labor_day(date_val)
        if labor_day:
            print(f"  LaborCalendar data:")
            print(f"    is_fixed_day: {labor_day.is_fixed_day}")
            print(f"    fixed_hours: {labor_day.fixed_hours}")
            print(f"    minimum_hours: {labor_day.minimum_hours}")
            print(f"    regular_rate: ${labor_day.regular_rate}/h")
            print(f"    non_fixed_rate: ${labor_day.non_fixed_rate}/h")
        else:
            print(f"  ⚠️ No LaborCalendar entry for this date")

        # Check if labor variables exist
        if (manufacturing_node, date_val) not in pyomo_model.labor_hours_used:
            print(f"  No labor variables for this date")
            continue

        # Extract labor hours
        try:
            hours_used = value(pyomo_model.labor_hours_used[manufacturing_node, date_val])
            hours_paid = value(pyomo_model.labor_hours_paid[manufacturing_node, date_val])

            print(f"  Model solution:")
            print(f"    labor_hours_used: {hours_used:.4f}h")
            print(f"    labor_hours_paid: {hours_paid:.4f}h")

            # Check production
            total_production = sum(
                value(pyomo_model.production[manufacturing_node, prod, date_val])
                for prod in pyomo_model.products
                if (manufacturing_node, prod, date_val) in pyomo_model.production
            )
            print(f"    total_production: {total_production:,.1f} units")

            # Calculate production time and overhead separately to verify 4h minimum logic
            production_rate = 1400.0  # units/hour
            production_time_calc = total_production / production_rate if total_production > 0 else 0.0

            # Estimate overhead (startup + shutdown + changeov ers)
            startup_hours = 0.5
            shutdown_hours = 0.5
            changeover_hours = 1.0

            # Count how many products are running
            products_running = sum(
                1 for prod in pyomo_model.products
                if (manufacturing_node, prod, date_val) in pyomo_model.product_produced
                and value(pyomo_model.product_produced[manufacturing_node, prod, date_val]) > 0.5
            )

            overhead_calc = 0.0
            if products_running > 0:
                overhead_calc = startup_hours + shutdown_hours + (changeover_hours * products_running)

            total_hours_calc = production_time_calc + overhead_calc

            print(f"    Calculated breakdown:")
            print(f"      Production time: {production_time_calc:.4f}h ({total_production:,.0f} units / {production_rate} per hour)")
            print(f"      Overhead time: {overhead_calc:.4f}h ({products_running} SKUs × {changeover_hours}h + startup/shutdown)")
            print(f"      Total needed: {total_hours_calc:.4f}h")
            print(f"      4h minimum check: max({total_hours_calc:.4f}h, 4.0h) = {max(total_hours_calc, 4.0):.4f}h")

            # Check production_day variable value (the key to Big-M constraint)
            if (manufacturing_node, date_val) in pyomo_model.production_day:
                production_day_val = value(pyomo_model.production_day[manufacturing_node, date_val])
                print(f"    production_day variable: {production_day_val:.4f}")
            else:
                print(f"    production_day variable: NOT FOUND")

            # CRITICAL CHECK: 4-hour minimum violation
            if labor_day and not labor_day.is_fixed_day:
                minimum_required = labor_day.minimum_hours
                if hours_used > 0.01:  # If any production
                    if hours_paid < minimum_required - 0.01:
                        print(f"  ❌ VIOLATION: paid={hours_paid:.4f}h < minimum={minimum_required}h")
                        print(f"     This is the bug! Production happened but 4h minimum not enforced.")
                        if (manufacturing_node, date_val) in pyomo_model.production_day:
                            prod_day = value(pyomo_model.production_day[manufacturing_node, date_val])
                            print(f"     production_day={prod_day:.4f} (should be 1.0 when producing)")
                            print(f"     Constraint: paid >= {minimum_required} * {prod_day:.4f} = {minimum_required * prod_day:.4f}")
                            if prod_day < 0.5:
                                print(f"     ⚠️ ROOT CAUSE: production_day=0 even though production is happening!")
                                print(f"        This allows paid={hours_paid:.4f}h instead of forcing paid≥4.0h")
                    elif hours_paid < hours_used - 0.01:
                        print(f"  ❌ VIOLATION: paid={hours_paid:.4f}h < used={hours_used:.4f}h")
                    else:
                        print(f"  ✓ OK: paid={hours_paid:.4f}h >= max(used, minimum)")
                else:
                    print(f"  ✓ No production on non-production day")

        except (ValueError, KeyError, AttributeError) as e:
            print(f"  ⚠️ Could not extract labor values: {e}")

    # ISSUE #4: Investigate truck assignments
    print(f"\n" + "="*80)
    print("ISSUE #4: Truck Assignment Investigation")
    print("="*80)

    # Check if truck variables exist in model
    if hasattr(pyomo_model, 'truck_load'):
        print(f"  ✓ truck_load variables exist in model: {len(pyomo_model.truck_load)}")

        # Extract some truck assignments
        truck_assignments = []
        for idx in list(pyomo_model.truck_load)[:10]:  # Sample first 10
            try:
                load_qty = value(pyomo_model.truck_load[idx])
                if load_qty > 0.01:
                    truck_assignments.append((idx, load_qty))
            except:
                pass

        if truck_assignments:
            print(f"  ✓ Found {len(truck_assignments)} truck assignments with qty > 0")
            print(f"  Sample: {truck_assignments[0]}")
        else:
            print(f"  ⚠️ No truck assignments found in solution")

    else:
        print(f"  ⚠️ truck_load variables don't exist in model")

    # Check if truck assignments in solution dict
    if 'truck_assignments' in result.metadata:
        print(f"  ✓ truck_assignments in result.metadata")
        print(f"    Count: {len(result.metadata['truck_assignments'])}")
    else:
        print(f"  ❌ truck_assignments NOT in result.metadata")
        print(f"     This is why UI shows 'Unassigned'")

    print(f"\n" + "="*80)
    print("EVIDENCE GATHERING COMPLETE")
    print("="*80)
    print("\nNext step: Analyze evidence to identify root causes")
    print("Then: Form hypotheses and test them")
    print("Finally: Implement fixes for root causes only")


if __name__ == "__main__":
    test_exact_user_scenario_oct16_4weeks()
