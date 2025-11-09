"""Baseline test for warmstart enhancements.

Run BEFORE implementing changes to establish baseline performance.

This test captures:
- Phase 1 solve time
- Phase 2 solve time
- Total solve time
- Final cost
- MIP gap
- Solution quality metrics

Results are saved to warmstart_baseline.json for comparison after enhancements.
"""

import pytest
import json
from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


@pytest.fixture
def data_6week():
    """Load real data for 6-week test."""
    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Get manufacturing site
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

    # Convert to unified
    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # Initial inventory
    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    return {
        'nodes': nodes,
        'routes': unified_routes,
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'truck_schedules': unified_truck_schedules,
        'cost_structure': cost_structure,
        'initial_inventory': initial_inventory,
        'inventory_date': inventory_date,
    }


def test_6week_warmstart_baseline(data_6week):
    """Baseline: Current warmstart performance without enhancements.

    This establishes the performance baseline before implementing:
    - Pallet warmstart hints
    - Inventory bound tightening

    Success criteria:
    - Solve completes (may hit timeout)
    - Metrics are captured and saved
    """
    print("\n" + "="*80)
    print("BASELINE TEST - Current Warmstart Performance")
    print("="*80)
    print("\nCapturing metrics BEFORE implementing enhancements...")

    # 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print(f"\nConfiguration:")
    print(f"  Horizon: {start_date} to {end_date} (42 days)")
    print(f"  Solver: APPSI_HIGHS")
    print(f"  Phase 1 timeout: 120s")
    print(f"  Phase 2 timeout: 600s")
    print(f"  MIP gap: 3%")

    # Run current implementation
    start_time = time.time()

    result = solve_weekly_pattern_warmstart(
        nodes=data_6week['nodes'],
        routes=data_6week['routes'],
        forecast=data_6week['forecast'],
        labor_calendar=data_6week['labor_calendar'],
        cost_structure=data_6week['cost_structure'],
        start_date=start_date,
        end_date=end_date,
        truck_schedules=data_6week['truck_schedules'],
        initial_inventory=data_6week['initial_inventory'],
        inventory_snapshot_date=data_6week['inventory_date'],
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=600,
        mip_gap=0.03,
        tee=False,
    )

    total_time = time.time() - start_time

    # Extract metrics
    baseline = {
        'phase1_time': result.metadata.get('phase1_time', 0),
        'phase2_time': result.metadata.get('phase2_time', 0),
        'total_time': total_time,
        'final_cost': result.objective_value if result.success else None,
        'gap': result.gap if result.gap else None,
        'success': result.success,
        'termination': str(result.termination_condition),
        'phase1_cost': result.metadata.get('phase1_cost', 0),
        'timestamp': str(date.today()),
    }

    # Save to file
    baseline_file = Path(__file__).parent.parent / 'warmstart_baseline.json'
    with open(baseline_file, 'w') as f:
        json.dump(baseline, f, indent=2)

    print("\n" + "="*80)
    print("BASELINE METRICS CAPTURED")
    print("="*80)
    print(f"\nPhase 1:")
    print(f"  Time: {baseline['phase1_time']:.1f}s")
    print(f"  Cost: ${baseline['phase1_cost']:,.2f}")

    print(f"\nPhase 2:")
    print(f"  Time: {baseline['phase2_time']:.1f}s")
    print(f"  Cost: ${baseline['final_cost']:,.2f}" if baseline['final_cost'] else "  Cost: N/A (failed)")
    print(f"  Gap: {baseline['gap']*100:.2f}%" if baseline['gap'] else "  Gap: N/A")

    print(f"\nTotal:")
    print(f"  Time: {baseline['total_time']:.1f}s")
    print(f"  Success: {baseline['success']}")
    print(f"  Termination: {baseline['termination']}")

    print(f"\nBaseline saved to: {baseline_file}")
    print("="*80)

    # Test always passes - we just need to capture baseline
    assert True, "Baseline captured successfully"


if __name__ == "__main__":
    # Can run standalone
    pytest.main([__file__, "-v", "-s"])
