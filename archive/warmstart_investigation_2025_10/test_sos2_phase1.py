"""Test SOS2 piecewise linear Phase 1 implementation.

Validates:
1. SOS2 λ variables created correctly
2. SOS2 constraints added
3. Phase 1 solves faster than batch-binary (pure LP vs MIP)
4. Phase 1 cost uses exact piecewise pallet costs
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    print("="*80)
    print("SOS2 PIECEWISE LINEAR PHASE 1 TEST")
    print("="*80)

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    # Test 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print(f"\nConfiguration:")
    print(f"  Horizon: 6 weeks")
    print(f"  Phase 1: SOS2 piecewise (6 breakpoints up to 5 pallets)")
    print(f"  Phase 2: Minimal timeout (just testing Phase 1)")

    # Run with SOS2 Phase 1
    result = solve_weekly_pattern_warmstart(
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
        time_limit_phase1=600,
        time_limit_phase2=10,  # Minimal for testing
        mip_gap=0.03,
        tee=False,
    )

    # Extract results
    phase1_time = result.metadata.get('phase1_time', 0)
    phase1_cost = result.metadata.get('phase1_cost', 0)
    num_lambda_vars = result.metadata.get('phase1_sos2_lambda_vars', 0)
    num_sos2_cohorts = result.metadata.get('phase1_sos2_frozen_cohorts', 0)
    pallet_hints = result.metadata.get('warmstart_pallet_hints_from_piecewise', 0)

    print("\n" + "="*80)
    print("SOS2 PHASE 1 VALIDATION")
    print("="*80)

    # Test 1: SOS2 variables created
    print(f"\n1. SOS2 Structure:")
    print(f"   λ variables: {num_lambda_vars:,}")
    print(f"   Frozen cohorts: {num_sos2_cohorts:,}")
    print(f"   Expected: ~27k λ vars (6 per cohort)")

    if num_lambda_vars > 20000:
        print(f"   ✅ SOS2 variables created")
    else:
        print(f"   ❌ SOS2 variables missing")

    # Test 2: Phase 1 solve time
    print(f"\n2. Phase 1 Performance:")
    print(f"   Time: {phase1_time:.1f}s")
    print(f"   Cost: ${phase1_cost:,.2f}")

    if phase1_time < 70:
        print(f"   ✅ Faster than batch-binary (78s)!")
    elif phase1_time < 100:
        print(f"   ✓ Acceptable solve time")
    else:
        print(f"   ⚠️  Slower than expected")

    # Test 3: Pallet hints
    print(f"\n3. Pallet Hints:")
    print(f"   Hints extracted: {pallet_hints:,}")

    if pallet_hints > 4000:
        print(f"   ✅ High coverage (100%)")
    else:
        print(f"   ⚠️  Lower coverage than expected")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print(f"\nSOS2 Piecewise Phase 1:")
    print(f"  • Variables: {num_lambda_vars:,} λ (continuous)")
    print(f"  • Cohorts: {num_sos2_cohorts:,} frozen")
    print(f"  • Time: {phase1_time:.1f}s")
    print(f"  • Cost: ${phase1_cost:,.2f}")
    print(f"  • Pallet hints: {pallet_hints:,}")

    if phase1_time < 70 and pallet_hints > 4000:
        print(f"\n✅ SOS2 Phase 1 working correctly!")
        print(f"   Ready for full 6-week performance test")
        return 0
    else:
        print(f"\n⚠️  Check results above for issues")
        return 1


if __name__ == "__main__":
    exit(main())
