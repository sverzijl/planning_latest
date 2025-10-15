"""Baseline Test 5: State transition verification."""

import pytest
from datetime import timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.models.truck_schedule import TruckScheduleCollection
from src.models.manufacturing import ManufacturingSite
from src.optimization.integrated_model import IntegratedProductionDistributionModel


def test_baseline_state_transitions():
    """Baseline: Verify freeze/thaw state transitions in current model."""

    parser = MultiFileParser(
        forecast_file="data/examples/Gfree Forecast.xlsm",
        network_file="data/examples/Network_Config.xlsx"
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

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

    all_dates = [entry.forecast_date for entry in forecast.entries]
    start_date = min(all_dates)
    end_date = start_date + timedelta(days=13)  # 2 weeks

    model = IntegratedProductionDistributionModel(
        manufacturing_site=manufacturing_site,
        forecast=forecast,
        locations=locations,
        routes=routes,
        start_date=start_date,
        end_date=end_date,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        truck_schedules=truck_schedules,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    result = model.solve(time_limit_seconds=120, mip_gap=0.02)

    assert result.is_optimal() or result.is_feasible()

    solution = model.get_solution()

    # Check for frozen inventory at Lineage (should freeze ambient arrivals)
    cohort_inventory = solution.get('cohort_inventory', {})

    lineage_frozen = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                        if loc == 'Lineage' and state == 'frozen')

    lineage_ambient = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                         if loc == 'Lineage' and state == 'ambient')

    # Check for thawed inventory at 6130 (WA - should thaw frozen arrivals)
    wa_thawed = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                   if loc == '6130' and state == 'thawed')

    wa_frozen = sum(qty for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items()
                   if loc == '6130' and state == 'frozen')

    baseline_metrics = {
        'lineage_frozen': lineage_frozen,
        'lineage_ambient': lineage_ambient,
        'wa_thawed': wa_thawed,
        'wa_frozen': wa_frozen,
    }

    print(f"\n=== BASELINE STATE TRANSITIONS ===")
    print(f"Lineage frozen inventory: {lineage_frozen:,.0f} units")
    print(f"Lineage ambient inventory: {lineage_ambient:,.0f} units")
    print(f"WA (6130) thawed inventory: {wa_thawed:,.0f} units")
    print(f"WA (6130) frozen inventory: {wa_frozen:,.0f} units")
    print(f"==================================\n")

    import json
    with open('test_baseline_state_transitions_metrics.json', 'w') as f:
        json.dump(baseline_metrics, f, indent=2, default=str)

    # Note: May be zero if Lineage/WA routes not used in optimal solution
    # Document for comparison with unified model


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
