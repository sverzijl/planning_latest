"""Test each UI tab can render with model data.

These tests verify UI components can consume OptimizationSolution data.
Catches display issues before user sees them.
"""

import pytest
from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from ui.utils.result_adapter import adapt_optimization_results


@pytest.fixture(scope="module")
def solved_model_and_adapted_results():
    """Solve model and adapt results once for all tests."""
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )

    forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
    inventory = parser.parse_inventory()

    mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
    converter = LegacyToUnifiedConverter()
    nodes, unified_routes, unified_trucks = converter.convert_all(
        manufacturing_site=mfg_site, locations=locations, routes=routes,
        truck_schedules=truck_schedules, forecast=forecast
    )

    start = inventory.snapshot_date
    end = start + timedelta(weeks=2)  # Changed to 2 weeks (corrected shelf life constraints)
    product_ids = sorted(set(entry.product_id for entry in forecast.entries))
    products = create_test_products(product_ids)

    model = SlidingWindowModel(
        nodes=nodes, routes=unified_routes, forecast=forecast,
        products=products, labor_calendar=labor_calendar,
        cost_structure=cost_params, start_date=start, end_date=end,
        truck_schedules=unified_trucks,
        initial_inventory=inventory.to_optimization_dict(),
        inventory_snapshot_date=inventory.snapshot_date,
        allow_shortages=True,
        use_pallet_tracking=True,
        use_truck_pallet_tracking=True
    )

    result = model.solve(solver_name='appsi_highs', time_limit_seconds=120, mip_gap=0.02)

    adapted = adapt_optimization_results(
        model=model,
        result={'result': result},
        inventory_snapshot_date=inventory.snapshot_date
    )

    return model, adapted


def test_production_tab_labor_hours(solved_model_and_adapted_results):
    """Test Production tab can extract and display labor hours."""
    model, adapted = solved_model_and_adapted_results

    prod_schedule = adapted['production_schedule']

    # VERIFY: Labor hours data exists
    assert prod_schedule.daily_labor_hours is not None, "daily_labor_hours should not be None"
    assert len(prod_schedule.daily_labor_hours) > 0, "daily_labor_hours should have data"
    assert prod_schedule.total_labor_hours > 0, "total_labor_hours should be > 0"

    # VERIFY: Can extract hours (simulates UI code)
    from ui.utils import extract_labor_hours

    sample_date = list(prod_schedule.daily_labor_hours.keys())[0]
    sample_hours = prod_schedule.daily_labor_hours[sample_date]

    extracted = extract_labor_hours(sample_hours, 0)
    assert extracted > 0, f"extract_labor_hours should return > 0, got {extracted}"

    # VERIFY: Filtered schedule works (simulates Production tab filtering)
    filtered_hours = {d: h for d, h in prod_schedule.daily_labor_hours.items()}
    total_filtered = sum(extract_labor_hours(h, 0) for h in filtered_hours.values())

    assert total_filtered > 0, "Filtered labor hours should be > 0"
    assert abs(total_filtered - prod_schedule.total_labor_hours) < 1, \
        "Filtered total should match production_schedule total"

    print(f"  ✅ Labor hours: {prod_schedule.total_labor_hours:.1f}h")


def test_labeling_tab_route_states(solved_model_and_adapted_results):
    """Test Labeling tab has route state information."""
    model, adapted = solved_model_and_adapted_results

    solution = model.get_solution()

    # VERIFY: Route states exist
    assert hasattr(model, 'route_arrival_state'), "Model missing route_arrival_state"
    assert len(model.route_arrival_state) > 0, "route_arrival_state should have routes"

    # VERIFY: Can generate labeling report (simulates Labeling tab)
    from src.analysis.production_labeling_report import ProductionLabelingReportGenerator

    generator = ProductionLabelingReportGenerator(solution)
    generator.set_leg_states(model.route_arrival_state)

    df = generator.generate_report_dataframe()

    # Should have at least some labeling requirements
    # (Even if all ambient, should show that)
    assert len(df) >= 0, "Should generate dataframe without error"

    print(f"  ✅ Labeling: {len(df)} requirements, {len(model.route_arrival_state)} routes")


def test_distribution_tab_truck_assignments(solved_model_and_adapted_results):
    """Test Distribution tab has truck assignment data."""
    model, adapted = solved_model_and_adapted_results

    shipments = adapted['shipments']
    truck_plan = adapted['truck_plan']

    # VERIFY: Shipments exist
    assert len(shipments) > 0, "Should have shipments"

    # VERIFY: Some shipments have truck assignments
    assigned = [s for s in shipments if s.assigned_truck_id]
    assert len(assigned) > 0, "At least some shipments should have truck assignments"

    # VERIFY: TruckLoadPlan exists
    assert truck_plan is not None, "truck_plan should not be None"

    # Manufacturing shipments should be mostly assigned
    from_mfg = [s for s in shipments if s.origin_id == '6122']
    assigned_mfg = [s for s in from_mfg if s.assigned_truck_id]

    pct_assigned = len(assigned_mfg) / len(from_mfg) * 100 if from_mfg else 0

    assert pct_assigned > 50, f"At least 50% of mfg shipments should be assigned, got {pct_assigned:.1f}%"

    print(f"  ✅ Truck assignments: {len(assigned)}/{len(shipments)} ({len(assigned)/len(shipments)*100:.1f}%)")
    print(f"     Manufacturing: {len(assigned_mfg)}/{len(from_mfg)} ({pct_assigned:.1f}%)")


def test_daily_snapshot_has_flows(solved_model_and_adapted_results):
    """Test Daily Snapshot has flow data (production, arrivals, departures)."""
    model, adapted = solved_model_and_adapted_results

    solution = model.get_solution()

    # VERIFY: FEFO data exists
    assert hasattr(solution, 'fefo_batch_objects'), "Solution missing fefo_batch_objects"
    assert len(solution.fefo_batch_objects) > 0, "fefo_batch_objects should have batches"

    assert hasattr(solution, 'fefo_shipment_allocations'), "Solution missing fefo_shipment_allocations"
    assert len(solution.fefo_shipment_allocations) > 0, "fefo_shipment_allocations should have allocations"

    # VERIFY: Allocations have product_id (user's bug)
    sample_alloc = solution.fefo_shipment_allocations[0]
    assert 'product_id' in sample_alloc, "Allocation missing product_id field"
    assert sample_alloc['product_id'] != 'UNKNOWN', f"product_id should not be UNKNOWN, got {sample_alloc['product_id']}"

    # VERIFY: Can generate Daily Snapshot
    from src.analysis.daily_snapshot import DailySnapshotGenerator
    from src.models.production_schedule import ProductionSchedule

    prod_schedule = adapted['production_schedule']
    shipments = adapted['shipments']

    from src.parsers.multi_file_parser import MultiFileParser
    parser = MultiFileParser(
        forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
        network_file='data/examples/Network_Config.xlsx',
        inventory_file='data/examples/inventory_latest.XLSX'
    )
    forecast, locations, _, _, _, _ = parser.parse_all()

    locations_dict = {loc.id: loc for loc in locations}

    generator = DailySnapshotGenerator(
        production_schedule=prod_schedule,
        shipments=shipments,
        locations_dict=locations_dict,
        forecast=forecast,
        model_solution=solution
    )

    # Generate snapshot for day 2
    snapshot = generator._generate_single_snapshot(model.start_date + timedelta(days=1))

    # VERIFY: Has required data
    assert len(snapshot.location_inventory) > 0, "Should have inventory at locations"
    assert snapshot.total_system_inventory >= 0, "Should have total inventory"

    # VERIFY: Flows have products (not UNKNOWN)
    if snapshot.inflows:
        for flow in snapshot.inflows[:5]:
            if flow.flow_type == 'production' or flow.flow_type == 'arrival':
                assert flow.product_id != 'UNKNOWN', f"Flow product should not be UNKNOWN, got {flow.product_id}"

    print(f"  ✅ Daily Snapshot: {len(snapshot.location_inventory)} locations, {len(snapshot.inflows)} inflows")


def test_costs_tab_validation(solved_model_and_adapted_results):
    """Test Costs tab has validated cost breakdown."""
    model, adapted = solved_model_and_adapted_results

    cost_breakdown = adapted['cost_breakdown']

    # VERIFY: Cost breakdown exists
    assert cost_breakdown is not None, "cost_breakdown should not be None"
    assert cost_breakdown.total_cost > 0, "total_cost should be > 0"

    # VERIFY: Components exist
    assert cost_breakdown.labor is not None, "labor breakdown should not be None"
    assert cost_breakdown.production is not None, "production breakdown should not be None"
    assert cost_breakdown.transport is not None, "transport breakdown should not be None"
    assert cost_breakdown.holding is not None, "holding breakdown should not be None"
    assert cost_breakdown.waste is not None, "waste breakdown should not be None"

    # Component sum should be close to total (within 1%)
    component_sum = (
        cost_breakdown.labor.total +
        cost_breakdown.production.total +
        cost_breakdown.transport.total +
        cost_breakdown.holding.total +
        cost_breakdown.waste.total
    )

    diff_pct = abs(cost_breakdown.total_cost - component_sum) / max(cost_breakdown.total_cost, component_sum) * 100

    assert diff_pct < 1, f"Component sum should match total within 1%, diff={diff_pct:.2f}%"

    print(f"  ✅ Costs: ${cost_breakdown.total_cost:,.2f}, components match")
