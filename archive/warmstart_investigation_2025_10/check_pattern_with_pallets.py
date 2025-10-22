#!/usr/bin/env python3
"""Check Pattern with REAL Pallet Integers in Phase 1

Tests if Phase 1 pattern changes when using ACTUAL pallet integers
(not converted unit costs or SOS2 approximation).

Question: Does real pallet cost make pattern more selective?
"""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    print("="*80)
    print("PATTERN COMPARISON: Phase 1 WITH vs WITHOUT Pallet Integers")
    print("="*80)

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure_base = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure_base.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    # 4-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=4*7 - 1)

    # Configure with staleness
    cost_structure = cost_structure_base.model_copy()
    cost_structure.freshness_incentive_weight = 0.05

    # TEST 1: Phase 1 WITH pallet conversion (default - uses SOS2/unit costs)
    print("\n" + "="*80)
    print("TEST 1: Phase 1 Normal (Converted/SOS2 Pallet Costs)")
    print("="*80)

    result_normal = solve_weekly_pattern_warmstart(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=300,
        mip_gap=0.03,
        tee=False,
        disable_pallet_conversion_for_diagnostic=False,  # Normal mode
    )

    print(f"\nPattern found (normal Phase 1): All products = {result_normal.production_schedule is not None}")

    # TEST 2: Phase 1 WITH actual pallet integers (diagnostic mode)
    print("\n" + "="*80)
    print("TEST 2: Phase 1 Diagnostic (REAL Pallet Integer Costs)")
    print("="*80)

    result_diagnostic = solve_weekly_pattern_warmstart(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=300,
        mip_gap=0.03,
        tee=False,
        disable_pallet_conversion_for_diagnostic=True,  # Use REAL pallets!
    )

    print(f"\nPattern found (diagnostic Phase 1): All products = {result_diagnostic.production_schedule is not None}")

    print("\n" + "="*80)
    print("VERDICT")
    print("="*80)
    print("\nIf patterns differ → Cost conversion changes optimal pattern")
    print("If patterns same → Something else is wrong")

    return 0


if __name__ == "__main__":
    exit(main())
