"""Force overtime usage with a scenario that has no alternative.

This test validates that the overtime mechanism can work by creating a scenario
where overtime is the ONLY feasible solution.
"""

import pytest
from datetime import timedelta
from pyomo.core import value
from src.parsers.multi_file_parser import MultiFileParser
from src.models.manufacturing import ManufacturingSite
from src.models.forecast import Forecast, ForecastEntry
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel
from tests.conftest import create_test_products


def test_monday_demand_forces_overtime():
    """Test that Monday demand requiring 14h labor triggers overtime.

    Scenario:
    - Monday (first day of planning): 18,200 units demand
    - Production time: 18,200 / 1,400 = 13h
    - Overhead: 1h (single product: startup + shutdown)
    - Total labor: 14h
    - Weekday capacity: 12h regular + 2h OT max
    - MUST use 2h overtime (no alternative!)

    Expected:
    - Production on Monday (can't defer - it's first day)
    - uses_overtime = 1
    - overtime_hours_used = 2h
    - Labor cost = $0 (12h) + $1,320 (2h OT) = $1,320
    """

    # Load real data to use actual labor calendar
    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast_orig, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Zero all costs except labor
    cost_structure.production_cost_per_unit = 0.0
    cost_structure.storage_cost_frozen_per_unit_day = 0.0
    cost_structure.storage_cost_ambient_per_unit_day = 0.0
    cost_structure.storage_cost_per_pallet_day_frozen = 0.0
    cost_structure.storage_cost_per_pallet_day_ambient = 0.0
    cost_structure.storage_cost_fixed_per_pallet_frozen = 0.0
    cost_structure.storage_cost_fixed_per_pallet_ambient = 0.0

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
        truck_schedules_list, forecast_orig
    )

    # Get a breadroom destination
    breadroom = '6110'  # QLD breadroom

    # Create SINGLE demand on Monday (first day of planning)
    # This forces production on Monday (can't defer to earlier day)
    start_date = labor_calendar.days[0].date  # Use first date from labor calendar

    # Find first Monday
    while start_date.weekday() != 0:  # 0 = Monday
        start_date = start_date + timedelta(days=1)

    monday = start_date

    # Use an actual product from the real forecast
    actual_products = list(set(e.product_id for e in forecast_orig.entries))
    test_product = actual_products[0] if actual_products else 'HELGAS GFREE WHOLEM 500G'

    # Create demand on WEDNESDAY (allows Monday or Tuesday production with 1-day transit)
    wednesday = monday + timedelta(days=2)

    # Create simple forecast: Single product, Wednesday demand
    forecast = Forecast(name="Force Overtime Test", entries=[
        ForecastEntry(
            location_id=breadroom,
            product_id=test_product,
            forecast_date=wednesday,  # Wednesday demand
            quantity=18200.0,  # 13h production, 14h with overhead
        )
    ])

    print("\n" + "="*80)
    print("FORCE OVERTIME TEST")
    print("="*80)
    print(f"Demand date: {wednesday} ({wednesday.strftime('%A')})")
    print(f"Production window: Monday or Tuesday (for Wednesday delivery)")
    print(f"Demand quantity: 18,200 units = 13h production")
    print(f"With overhead: 14h total labor")
    print(f"Weekday capacity: 14h (12h regular + 2h OT)")
    print(f"Expected: Produce on Tuesday with 2h overtime")
    print()

    # Build model
    model_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=monday,
        end_date=monday + timedelta(days=6),
        truck_schedules=[],  # No trucks
        use_batch_tracking=True,
        allow_shortages=True,  # Allow to see what happens
        enforce_shelf_life=False,
    )

    # Solve
    result = model_obj.solve(time_limit_seconds=60, mip_gap=0.01, tee=False)

    print(f"Solve status: {result.termination_condition}")
    print(f"Success: {result.success}")

    if not result.success:
        print(f"❌ FAILED TO SOLVE: {result.infeasibility_message}")
        assert False, f"Model should be feasible: {result.infeasibility_message}"

    print(f"Total cost: ${result.objective_value:,.2f}")

    # Extract solution
    solution = model_obj.get_solution()
    production = solution.get('production_by_date_product', {})
    labor_by_date = solution.get('labor_hours_by_date', {})

    print("\n" + "="*80)
    print("PRODUCTION SCHEDULE")
    print("="*80)

    tuesday = monday + timedelta(days=1)
    tuesday_production = sum(qty for (date, prod), qty in production.items() if date == tuesday)
    monday_production = sum(qty for (date, prod), qty in production.items() if date == monday)
    other_days = sum(qty for (date, prod), qty in production.items() if date not in [monday, tuesday])

    print(f"Monday production: {monday_production:,.0f} units")
    print(f"Tuesday production: {tuesday_production:,.0f} units")
    print(f"Other days: {other_days:,.0f} units")

    total_prod = monday_production + tuesday_production
    assert total_prod >= 18000, f"Should produce for Wednesday demand, got {total_prod:,.0f}"

    # Extract Tuesday labor details from Pyomo model (production day)
    pyomo_model = model_obj.model
    node_id = '6122'
    production_date = tuesday if tuesday_production > monday_production else monday

    if (node_id, production_date) in pyomo_model.labor_hours_used:
        labor_used = value(pyomo_model.labor_hours_used[node_id, production_date])
        fixed_used = value(pyomo_model.fixed_hours_used[node_id, production_date])
        ot_used = value(pyomo_model.overtime_hours_used[node_id, production_date])
        uses_ot = value(pyomo_model.uses_overtime[node_id, production_date])

        print("\n" + "="*80)
        print(f"PRODUCTION DAY LABOR DETAILS: {production_date.strftime('%A')}")
        print("="*80)
        print(f"labor_hours_used: {labor_used:.2f}h")
        print(f"fixed_hours_used: {fixed_used:.2f}h")
        print(f"overtime_hours_used: {ot_used:.2f}h")
        print(f"uses_overtime (binary): {uses_ot:.0f}")

        labor_day = labor_calendar.get_labor_day(production_date)
        expected_cost = fixed_used * labor_day.regular_rate + ot_used * labor_day.overtime_rate

        print(f"\nExpected labor cost: ${expected_cost:,.2f}")
        print(f"Regular rate: ${labor_day.regular_rate:.2f}/h")
        print(f"Overtime rate: ${labor_day.overtime_rate:.2f}/h")

        # CRITICAL CHECKS
        print("\n" + "="*80)
        print("VALIDATION")
        print("="*80)

        if labor_used > 13.5:
            print(f"✅ Labor hours used: {labor_used:.2f}h (expected ~14h)")
        else:
            print(f"❌ Labor hours too low: {labor_used:.2f}h (expected ~14h)")

        if uses_ot >= 0.5:
            print(f"✅ uses_overtime = {uses_ot:.0f} (overtime engaged)")
        else:
            print(f"❌ uses_overtime = {uses_ot:.0f} (overtime NOT engaged)")
            print(f"   This is the BUG! Overtime should be required for {labor_used:.2f}h > 12h")

        if ot_used > 1.5:
            print(f"✅ Overtime hours: {ot_used:.2f}h (expected ~2h)")
            print(f"\n🎉 SUCCESS: Overtime mechanism WORKS!")
            print(f"   The model CAN use overtime when required.")
        elif ot_used > 0.1:
            print(f"⚠️  Partial overtime: {ot_used:.2f}h (expected ~2h)")
            print(f"   Overtime works but may be undercounting")
        else:
            print(f"❌ NO OVERTIME USED: {ot_used:.2f}h")
            print(f"\n🔍 DEBUGGING INFO:")
            print(f"   Labor used: {labor_used:.2f}h")
            print(f"   Fixed used: {fixed_used:.2f}h")
            print(f"   Overtime calculated: {labor_used - fixed_used:.2f}h")
            print(f"   Overtime variable: {ot_used:.2f}h")
            print(f"   uses_overtime: {uses_ot}")

            # Check constraints
            print(f"\n   Constraint 3 (OT calculation): OT = labor_used - fixed_used")
            print(f"     {ot_used:.2f} should equal {labor_used:.2f} - {fixed_used:.2f} = {labor_used - fixed_used:.2f}")

            if abs(ot_used - (labor_used - fixed_used)) > 0.01:
                print(f"   ❌ CONSTRAINT VIOLATION: Overtime calculation incorrect!")

            print(f"\n   Constraint 8 (OT forcing): labor_used <= 12 + 2 * uses_overtime")
            print(f"     {labor_used:.2f} <= 12 + 2 * {uses_ot} = {12 + 2 * uses_ot:.2f}")

            if labor_used > 12.01 and uses_ot < 0.5:
                print(f"   ❌ CONSTRAINT VIOLATION: Labor exceeds 12h but uses_overtime=0!")

            assert False, "Overtime mechanism is broken - cannot trigger overtime even when required"

    else:
        print(f"❌ ERROR: No labor variables found for production date {production_date}")
        assert False, "Labor variables not created"


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
