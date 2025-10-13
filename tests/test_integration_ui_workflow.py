"""Integration test matching UI workflow with real data files.

⚠️  CRITICAL REGRESSION TEST - REQUIRED VALIDATION GATE ⚠️

This test MUST pass before committing any changes to optimization model or solver code.
It serves as the primary regression test ensuring UI workflow compatibility and performance.

PURPOSE:
--------
Validates the complete optimization workflow using real production data files:
- GFree Forecast.xlsm (SAP IBP export with 17,760 forecast entries)
- Network_Config.xlsx (11 locations, 10 routes, 585 labor days)
- inventory.xlsx (optional initial inventory snapshot)

This test exactly mirrors the UI Planning Tab workflow with typical user settings,
ensuring that code changes don't break the user experience or degrade performance.

TEST CONFIGURATION:
------------------
Settings match UI Planning Tab defaults:
- Allow Demand Shortages: True (soft constraints for flexibility)
- Enforce Shelf Life Constraints: True (filters routes > 10 days transit)
- Enable Batch Tracking: True (age-cohort inventory tracking)
- MIP Gap Tolerance: 1% (acceptable optimality gap)
- Planning Horizon: 4 weeks from inventory snapshot date
- Inventory snapshot date: 2025-10-13 (or earliest forecast date if no inventory)
- Solver: CBC (open source, cross-platform)
- Time Limit: 120 seconds

PERFORMANCE REQUIREMENTS:
------------------------
- ✓ Solve time: < 30 seconds (typically 15-20s)
- ✓ Solution status: OPTIMAL or FEASIBLE
- ✓ Fill rate: ≥ 95% demand satisfaction
- ✓ MIP gap: < 1%
- ✓ No infeasibilities

WHEN TO RUN:
-----------
Run this test before committing changes to:
- src/optimization/ (model formulation, constraints, objective)
- Solver parameters or performance optimizations
- Decision variables or constraint logic
- Route enumeration or network algorithms
- Batch tracking or age-cohort inventory code

HOW TO RUN:
----------
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v

For detailed output with print statements:
venv/bin/python -m pytest tests/test_integration_ui_workflow.py -v -s

IF TEST FAILS:
-------------
1. Check solve time - performance regression if >30s
2. Check fill rate - constraint conflict if <95%
3. Check solution status - infeasibility if not OPTIMAL/FEASIBLE
4. Review test output for specific errors
5. Compare with previous successful runs
6. DO NOT commit until test passes

This test is your safety net - it catches regressions before they reach production!
"""

import pytest
from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel


@pytest.fixture
def data_files():
    """Paths to real data files."""
    data_dir = Path(__file__).parent.parent / "data" / "examples"

    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"
    inventory_file = data_dir / "inventory.xlsx"

    # Verify required files exist
    assert forecast_file.exists(), f"Forecast file not found: {forecast_file}"
    assert network_file.exists(), f"Network file not found: {network_file}"

    # Inventory file is optional
    files = {
        'forecast': forecast_file,
        'network': network_file,
    }

    if inventory_file.exists():
        files['inventory'] = inventory_file
    else:
        files['inventory'] = None

    return files


@pytest.fixture
def parsed_data(data_files):
    """Parse all data files (matches UI data upload)."""
    # Use MultiFileParser (matches UI workflow)
    parser = MultiFileParser(
        forecast_file=data_files['forecast'],
        network_file=data_files['network'],
        inventory_file=data_files['inventory'],  # Can be None
    )

    # Parse all data
    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site from locations (should be the one with type='manufacturing')
    from src.models.manufacturing import ManufacturingSite
    from src.models.location import LocationType
    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    if not manufacturing_locations:
        raise ValueError("No manufacturing site found in locations")

    manuf_loc = manufacturing_locations[0]

    # Create ManufacturingSite from the manufacturing location
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

    # Parse initial inventory (if file provided)
    initial_inventory = None
    inventory_snapshot_date = None
    product_aliases = None

    if data_files['inventory'] is not None:
        # Parse inventory snapshot
        inventory_snapshot = parser.parse_inventory(snapshot_date=None)  # Will use date from file
        initial_inventory = inventory_snapshot
        inventory_snapshot_date = inventory_snapshot.snapshot_date
        product_aliases = parser._product_alias_resolver  # Get the alias resolver if available

    # Convert truck schedules list to TruckScheduleCollection
    from src.models.truck_schedule import TruckScheduleCollection
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

    return {
        'forecast': forecast,
        'locations': locations,
        'routes': routes,
        'labor_calendar': labor_calendar,
        'truck_schedules': truck_schedules,
        'cost_structure': cost_structure,
        'manufacturing_site': manufacturing_site,
        'initial_inventory': initial_inventory,
        'inventory_snapshot_date': inventory_snapshot_date,
        'product_aliases': product_aliases,
    }


def test_ui_workflow_4_weeks_with_initial_inventory(parsed_data):
    """
    Integration test matching UI workflow with 4-week horizon and initial inventory.

    This test validates:
    1. Data loading and parsing (forecast, network, inventory)
    2. Model creation with UI-matching parameters
    3. Fast solve time (<30 seconds with 1% gap tolerance)
    4. Feasible solution with demand satisfaction
    5. Initial inventory properly incorporated
    """

    # Extract parsed data
    forecast = parsed_data['forecast']
    locations = parsed_data['locations']
    routes = parsed_data['routes']
    labor_calendar = parsed_data['labor_calendar']
    truck_schedules = parsed_data['truck_schedules']
    cost_structure = parsed_data['cost_structure']
    manufacturing_site = parsed_data['manufacturing_site']
    initial_inventory = parsed_data['initial_inventory']
    inventory_snapshot_date = parsed_data['inventory_snapshot_date']

    # Validate or set inventory snapshot date
    if inventory_snapshot_date is not None:
        print(f"\n✓ Inventory snapshot date: {inventory_snapshot_date}")
        assert inventory_snapshot_date == date(2025, 10, 13), \
            f"Expected inventory snapshot date 2025-10-13, got {inventory_snapshot_date}"
    else:
        # No inventory file - use earliest forecast date as planning start
        inventory_snapshot_date = min(e.forecast_date for e in forecast.entries)
        print(f"\n⚠ No inventory file - using earliest forecast date as planning start: {inventory_snapshot_date}")

    # Print data summary
    print("\n" + "="*80)
    print("DATA SUMMARY")
    print("="*80)
    print(f"Forecast entries: {len(forecast.entries)}")
    print(f"Date range: {min(e.forecast_date for e in forecast.entries)} to {max(e.forecast_date for e in forecast.entries)}")
    print(f"Total demand: {sum(e.quantity for e in forecast.entries):,.0f} units")
    print(f"Locations: {len(locations)}")
    print(f"Routes: {len(routes)}")
    print(f"Labor days: {len(labor_calendar.days)}")
    print(f"Truck schedules: {len(truck_schedules.schedules)}")

    if initial_inventory:
        total_init_inventory = sum(initial_inventory.to_optimization_dict().values())
        print(f"Initial inventory: {total_init_inventory:,.0f} units at {inventory_snapshot_date}")

    # Calculate 4-week planning horizon from inventory snapshot date
    planning_start_date = inventory_snapshot_date
    planning_end_date = planning_start_date + timedelta(weeks=4)

    print(f"\nPlanning horizon: {planning_start_date} to {planning_end_date} (4 weeks)")

    # UI SETTINGS (matching Planning Tab)
    settings = {
        'allow_shortages': True,              # ✓ Allow Demand Shortages
        'enforce_shelf_life': True,           # ✓ Enforce Shelf Life Constraints
        'use_batch_tracking': True,           # ✓ Enable Batch Tracking
        'max_routes_per_destination': 5,      # Default
        'mip_gap': 0.01,                      # 1% MIP Gap Tolerance
        'time_limit_seconds': 120,            # 2 minutes (expect <30s)
        'solver_name': 'cbc',                 # Default solver
        'start_date': planning_start_date,    # Planning horizon start
        'end_date': planning_end_date,        # Planning horizon end (4 weeks)
    }

    print("\n" + "="*80)
    print("OPTIMIZATION SETTINGS")
    print("="*80)
    for key, value in settings.items():
        print(f"{key}: {value}")

    # Create optimization model (matches UI Planning Tab)
    print("\n" + "="*80)
    print("MODEL CREATION")
    print("="*80)

    model_start = time.time()

    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing_site,
        cost_structure=cost_structure,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        max_routes_per_destination=settings['max_routes_per_destination'],
        allow_shortages=settings['allow_shortages'],
        enforce_shelf_life=settings['enforce_shelf_life'],
        initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
        inventory_snapshot_date=inventory_snapshot_date,
        start_date=settings['start_date'],
        end_date=settings['end_date'],
        use_batch_tracking=settings['use_batch_tracking'],
    )

    model_build_time = time.time() - model_start

    # Model statistics
    horizon_days = len(model.production_dates)
    horizon_weeks = horizon_days / 7.0

    print(f"✓ Model built in {model_build_time:.2f}s")
    print(f"  Routes enumerated: {len(model.enumerated_routes)}")
    print(f"  Planning horizon: {horizon_days} days ({horizon_weeks:.1f} weeks)")
    print(f"  Date range: {model.start_date} to {model.end_date}")
    print(f"  Batch tracking: {'ENABLED' if settings['use_batch_tracking'] else 'DISABLED'}")

    # Validate planning horizon
    assert model.start_date == planning_start_date, \
        f"Model start date {model.start_date} doesn't match expected {planning_start_date}"
    assert model.end_date == planning_end_date, \
        f"Model end date {model.end_date} doesn't match expected {planning_end_date}"

    # Solve optimization (matches UI "Solve Optimization Model" button)
    print("\n" + "="*80)
    print("SOLVING OPTIMIZATION")
    print("="*80)

    solve_start = time.time()

    result = model.solve(
        solver_name=settings['solver_name'],
        time_limit_seconds=settings['time_limit_seconds'],
        mip_gap=settings['mip_gap'],
        use_aggressive_heuristics=True,  # Enable CBC performance features
        tee=False,  # Don't show solver output in test
    )

    solve_time = time.time() - solve_start

    print(f"✓ Solved in {solve_time:.2f}s")

    # ASSERT: Fast solve time (<30 seconds as expected)
    assert solve_time < 30, \
        f"Solve time {solve_time:.2f}s exceeds expected <30s threshold"

    # ASSERT: Solution is optimal or feasible
    assert result.is_optimal() or result.is_feasible(), \
        f"Solution not optimal/feasible: {result.termination_condition}"

    # Print solution summary
    print("\n" + "="*80)
    print("SOLUTION SUMMARY")
    print("="*80)
    print(f"Status: {result.termination_condition}")
    print(f"Objective value: ${result.objective_value:,.2f}")
    print(f"Solve time: {result.solve_time_seconds:.2f}s")
    if result.gap is not None:
        print(f"Gap: {result.gap * 100:.2f}%")

    # Extract solution details
    solution = model.get_solution()
    assert solution is not None, "Solution should not be None"

    # Cost breakdown
    print("\n" + "="*80)
    print("COST BREAKDOWN")
    print("="*80)
    print(f"Labor cost:     ${solution.get('total_labor_cost', 0):>12,.2f}")
    print(f"Production cost: ${solution.get('total_production_cost', 0):>12,.2f}")
    print(f"Transport cost: ${solution.get('total_transport_cost', 0):>12,.2f}")
    print(f"Inventory cost: ${solution.get('total_inventory_cost', 0):>12,.2f}")
    print(f"Shortage cost:  ${solution.get('total_shortage_cost', 0):>12,.2f}")
    print(f"{'-'*40}")
    print(f"TOTAL:          ${solution.get('total_labor_cost', 0) + solution.get('total_production_cost', 0) + solution.get('total_transport_cost', 0) + solution.get('total_inventory_cost', 0) + solution.get('total_shortage_cost', 0):>12,.2f}")

    # Production summary
    total_production = solution.get('total_production_quantity', 0)
    num_batches = len(solution.get('production_batches', []))
    total_labor_hours = sum(solution.get('labor_hours_by_date', {}).values())

    print("\n" + "="*80)
    print("PRODUCTION SUMMARY")
    print("="*80)
    print(f"Total production: {total_production:,.0f} units")
    print(f"Production batches: {num_batches}")
    print(f"Total labor hours: {total_labor_hours:.1f}h")
    if num_batches > 0:
        print(f"Average batch size: {total_production / num_batches:,.0f} units")

    # Shipment summary
    shipments = model.get_shipment_plan()
    if shipments:
        print("\n" + "="*80)
        print("DISTRIBUTION SUMMARY")
        print("="*80)
        print(f"Shipments created: {len(shipments)}")
        print(f"Total shipped: {sum(s.quantity for s in shipments):,.0f} units")

        # Count unique destinations
        destinations = set(s.destination_id for s in shipments)
        print(f"Destinations served: {len(destinations)}")

    # Demand satisfaction
    total_shortage_units = solution.get('total_shortage_units', 0)
    total_demand = sum(e.quantity for e in forecast.entries)

    # Filter demand to planning horizon
    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if planning_start_date <= e.forecast_date <= planning_end_date
    )

    fill_rate = 100 * (1 - total_shortage_units / demand_in_horizon) if demand_in_horizon > 0 else 100

    print("\n" + "="*80)
    print("DEMAND SATISFACTION")
    print("="*80)
    print(f"Total demand (forecast): {total_demand:,.0f} units")
    print(f"Demand in horizon: {demand_in_horizon:,.0f} units")
    print(f"Shortage: {total_shortage_units:,.0f} units")
    print(f"Fill rate: {fill_rate:.1f}%")

    # ASSERT: Reasonable fill rate (should be very high with 4-week horizon and initial inventory)
    assert fill_rate >= 95.0, \
        f"Fill rate {fill_rate:.1f}% is below expected 95% threshold"

    # Validate initial inventory was used
    if initial_inventory:
        print("\n" + "="*80)
        print("INITIAL INVENTORY VALIDATION")
        print("="*80)

        # Check cohort inventory includes initial inventory dates
        if 'cohort_inventory' in solution:
            cohort_inv = solution['cohort_inventory']

            # Extract production dates from cohort keys: (loc, prod, prod_date, curr_date, state)
            prod_dates_in_cohorts = set()
            for key in cohort_inv.keys():
                if len(key) >= 3:
                    prod_date = key[2]
                    prod_dates_in_cohorts.add(prod_date)

            # Check if inventory snapshot date appears as production date (initial inventory)
            has_initial_inventory_cohorts = inventory_snapshot_date in prod_dates_in_cohorts

            print(f"Inventory snapshot date in cohorts: {has_initial_inventory_cohorts}")
            print(f"Production dates in cohorts: {len(prod_dates_in_cohorts)}")
            print(f"Date range: {min(prod_dates_in_cohorts)} to {max(prod_dates_in_cohorts)}")

            # ASSERT: Initial inventory cohorts should exist
            assert has_initial_inventory_cohorts, \
                "Initial inventory cohorts not found in solution"
        else:
            print("⚠ Cohort inventory not available in solution (batch tracking may be disabled)")

    # Performance summary
    print("\n" + "="*80)
    print("PERFORMANCE SUMMARY")
    print("="*80)
    print(f"Model build time: {model_build_time:.2f}s")
    print(f"Solve time: {solve_time:.2f}s")
    print(f"Total time: {model_build_time + solve_time:.2f}s")
    print(f"Status: {'✓ PASSED' if solve_time < 30 else '✗ SLOW'}")

    # Final assertions
    assert result.is_optimal() or result.is_feasible(), \
        f"Solution not optimal/feasible: {result.termination_condition}"
    assert solve_time < 30, \
        f"Solve time {solve_time:.2f}s exceeds 30s threshold"
    assert fill_rate >= 95.0, \
        f"Fill rate {fill_rate:.1f}% is below 95% threshold"
   # Check either total_production or production_by_date_product has values
    production_by_date_product = solution.get('production_by_date_product', {})
    has_production = total_production > 0 or len(production_by_date_product) > 0
    assert has_production, \
        f"No production found: total_production={total_production}, batches={num_batches}, production_by_date_product entries={len(production_by_date_product)}"
    assert num_batches > 0, \
        f"Expected production batches but got {num_batches}"

    print("\n" + "="*80)
    print("TEST PASSED ✓")
    print("="*80)


def test_ui_workflow_without_initial_inventory(parsed_data):
    """
    Test 4-week optimization WITHOUT initial inventory (pure forecast-driven).

    This validates model behavior when starting from zero inventory,
    requiring all demand to be satisfied from new production.
    """

    # Extract parsed data (excluding initial inventory)
    forecast = parsed_data['forecast']
    locations = parsed_data['locations']
    routes = parsed_data['routes']
    labor_calendar = parsed_data['labor_calendar']
    truck_schedules = parsed_data['truck_schedules']
    cost_structure = parsed_data['cost_structure']
    manufacturing_site = parsed_data['manufacturing_site']

    # Use earliest forecast date as planning start
    planning_start_date = min(e.forecast_date for e in forecast.entries)
    planning_end_date = planning_start_date + timedelta(weeks=4)

    print("\n" + "="*80)
    print("TEST: 4-WEEK HORIZON WITHOUT INITIAL INVENTORY")
    print("="*80)
    print(f"Planning horizon: {planning_start_date} to {planning_end_date}")

    # Create model WITHOUT initial inventory
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
        initial_inventory=None,  # NO INITIAL INVENTORY
        inventory_snapshot_date=None,
        start_date=None,  # Auto-calculate from forecast
        end_date=planning_end_date,
        use_batch_tracking=True,
    )

    model_build_time = time.time() - model_start

    print(f"✓ Model built in {model_build_time:.2f}s")
    print(f"  Routes enumerated: {len(model.enumerated_routes)}")
    print(f"  Planning horizon: {len(model.production_dates)} days")

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
    print(f"  Objective: ${result.objective_value:,.2f}")

    # ASSERT: Should still solve quickly
    assert solve_time < 60, f"Solve time {solve_time:.2f}s exceeds 60s threshold"
    assert result.is_optimal() or result.is_feasible()

    # Extract solution
    solution = model.get_solution()
    assert solution is not None

    total_production = solution.get('total_production_quantity', 0)
    total_shortage = solution.get('total_shortage_units', 0)

    # Filter demand to planning horizon
    demand_in_horizon = sum(
        e.quantity for e in forecast.entries
        if model.start_date <= e.forecast_date <= model.end_date
    )

    fill_rate = 100 * (1 - total_shortage / demand_in_horizon) if demand_in_horizon > 0 else 100

    print(f"\nDemand in horizon: {demand_in_horizon:,.0f} units")
    print(f"Total production: {total_production:,.0f} units")
    print(f"Shortage: {total_shortage:,.0f} units")
    print(f"Fill rate: {fill_rate:.1f}%")

    # ASSERT: Should produce enough to meet most demand
    assert total_production > 0
    assert fill_rate >= 85.0, f"Fill rate {fill_rate:.1f}% below 85% threshold"

    print("\nTEST PASSED ✓")


if __name__ == "__main__":
    # Allow running test directly for debugging
    pytest.main([__file__, "-v", "-s"])
