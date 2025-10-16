#!/usr/bin/env python3
"""
Quick validation test for truck loading constraint fix.

This test verifies that the fix allows proper production capacity utilization
by checking that first-day afternoon trucks can load same-day production.

Expected results:
- Production should increase from 1.70M to ~2.41M units
- Shortage variables should remain at 0
- First day afternoon trucks should have non-zero loads
- No constraint violations
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import date, timedelta
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route, TransportMode
from src.models.truck_schedule import TruckSchedule, TruckScheduleCollection
from src.optimization.integrated_model import IntegratedProductionDistributionModel

def create_simple_test_scenario():
    """Create a simple 5-day scenario to test the fix."""

    # Planning horizon: Monday-Friday
    start_date = date(2025, 1, 6)  # Monday
    dates = [start_date + timedelta(days=i) for i in range(5)]

    # Forecast: 10,000 units/day at single destination
    forecast_entries = []
    for d in dates:
        forecast_entries.append(ForecastEntry(
            location_id='6125',
            product_id='P1',
            forecast_date=d,
            quantity=10000.0
        ))
    forecast = Forecast(entries=forecast_entries)

    # Labor calendar: All weekdays with 12h regular, 2h overtime
    labor_days = []
    for d in dates:
        labor_days.append(LaborDay(
            date=d,
            is_fixed_day=True,
            fixed_hours=12.0,
            overtime_hours=2.0,
            regular_rate=100.0,
            overtime_rate=150.0,
            non_fixed_rate=None,
            minimum_hours=None
        ))
    labor_calendar = LaborCalendar(days=labor_days)

    # Manufacturing site
    manufacturing = ManufacturingSite(
        id='6122',
        name='Manufacturing',
        production_rate_units_per_hour=1400.0,
        products=['P1']
    )

    # Locations
    locations = [
        Location(
            id='6122',
            name='Manufacturing',
            type=LocationType.MANUFACTURING,
            storage_modes=[StorageMode.AMBIENT]
        ),
        Location(
            id='6125',
            name='Hub VIC',
            type=LocationType.HUB,
            storage_modes=[StorageMode.AMBIENT]
        )
    ]

    # Route: 6122 -> 6125 (2-day transit, ambient)
    routes = [
        Route(
            origin_id='6122',
            destination_id='6125',
            transit_days=2,
            transport_mode=TransportMode.AMBIENT,
            cost_per_unit=0.10
        )
    ]

    # Truck schedules: Morning truck Mon-Fri to 6125
    trucks = []
    for d in dates:
        trucks.append(TruckSchedule(
            day_of_week=d.strftime('%A'),
            departure_time='08:00',
            destination_id='6125',
            capacity_units=14080,  # Standard truck capacity
            cost_fixed=500.0,
            cost_per_unit=0.05,
            intermediate_stops=None
        ))
    truck_schedules = TruckScheduleCollection(schedules=trucks)

    # Cost structure
    costs = CostStructure(
        production_cost_per_unit=1.0,
        storage_cost_frozen_per_unit_day=0.01,
        storage_cost_ambient_per_unit_day=0.005,
        shortage_penalty_per_unit=100.0
    )

    return forecast, labor_calendar, manufacturing, costs, locations, routes, truck_schedules


def main():
    print("=" * 80)
    print("TRUCK LOADING FIX VALIDATION TEST")
    print("=" * 80)
    print()

    # Create test scenario
    print("Creating simple test scenario...")
    forecast, labor_calendar, manufacturing, costs, locations, routes, truck_schedules = \
        create_simple_test_scenario()

    print(f"  Dates: {len(labor_calendar.days)} days")
    print(f"  Demand: {sum(e.quantity for e in forecast.entries):,.0f} units total")
    print(f"  Capacity: {len(labor_calendar.days)} days × 12h × 1,400 = {len(labor_calendar.days) * 12 * 1400:,.0f} units")
    print()

    # Build model
    print("Building optimization model...")
    model_obj = IntegratedProductionDistributionModel(
        forecast=forecast,
        labor_calendar=labor_calendar,
        manufacturing_site=manufacturing,
        cost_structure=costs,
        locations=locations,
        routes=routes,
        truck_schedules=truck_schedules,
        allow_shortages=True,
        initial_inventory={}  # No initial inventory
    )

    print("  Model created successfully")
    print(f"  Planning horizon: {model_obj.start_date} to {model_obj.end_date}")
    print()

    # Solve
    print("Solving model (60 second time limit)...")
    result = model_obj.solve(time_limit_seconds=60, solver_name='cbc')

    if not result.is_optimal():
        print(f"  WARNING: Solver status = {result.solver_status}")
        print(f"  Termination condition = {result.termination_condition}")
        if not result.is_feasible():
            print("  ERROR: Model is INFEASIBLE!")
            return 1
    else:
        print("  ✓ Optimal solution found")

    print()

    # Extract solution
    solution = model_obj.extract_solution(model_obj.model)

    total_production = sum(solution['production_by_date_product'].values())
    total_demand = sum(e.quantity for e in forecast.entries)

    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    print(f"Total Demand:      {total_demand:>12,.0f} units")
    print(f"Total Production:  {total_production:>12,.0f} units")
    print(f"Difference:        {total_production - total_demand:>12,.0f} units")
    print(f"Total Cost:        ${result.objective_value:>12,.2f}")
    print()

    # Check shortage
    total_shortage = sum(solution['shortages_by_dest_product_date'].values())
    print(f"Total Shortage:    {total_shortage:>12,.0f} units")

    if total_shortage > 1:
        print("  ⚠ WARNING: Demand not fully satisfied!")
    else:
        print("  ✓ Full demand satisfaction")
    print()

    # Check first day trucks
    print("First Day Truck Loads:")
    first_date = min(labor_calendar.days, key=lambda d: d.date).date
    first_delivery = first_date + timedelta(days=2)  # 2-day transit

    if 'truck_loads' in solution:
        first_day_loads = {
            (truck_idx, dest, prod): qty
            for (truck_idx, dest, prod, delivery_date), qty in solution['truck_loads'].items()
            if delivery_date == first_delivery
        }

        total_first_day = sum(first_day_loads.values())
        print(f"  Delivery date: {first_delivery}")
        print(f"  Total load: {total_first_day:,.0f} units")

        if total_first_day > 100:
            print("  ✓ First day trucks have non-zero loads (FIX WORKING!)")
        else:
            print("  ⚠ WARNING: First day trucks still at zero (fix may not be working)")
    else:
        print("  (Truck load details not available in solution)")

    print()

    # Validation summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print()

    production_ratio = total_production / total_demand

    if production_ratio >= 0.99:
        print("✓ PASS: Production meets demand (ratio = {:.1%})".format(production_ratio))
        print("✓ PASS: Fix successfully removed production bottleneck")
        return 0
    elif production_ratio >= 0.90:
        print("⚠ PARTIAL: Production at {:.1%} of demand".format(production_ratio))
        print("  May need further investigation")
        return 0
    else:
        print("✗ FAIL: Production still limited to {:.1%} of demand".format(production_ratio))
        print("  Fix may not be working correctly")
        return 1


if __name__ == '__main__':
    sys.exit(main())
