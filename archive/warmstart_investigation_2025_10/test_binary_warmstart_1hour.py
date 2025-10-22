"""Test binary-only warmstart with 1-hour timeout.

Winner from all warmstart strategies:
- Binary-only warmstart (649 decision hints)
- Best gap: 60% at 10-minute timeout
- Best cost: $1.9M

Test: Give it a full hour to see:
- Final gap achievable
- Final cost achievable
- Whether it reaches 3% gap target
- Actual time needed
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
    print("BINARY-ONLY WARMSTART - 1 HOUR TEST")
    print("="*80)
    print("\nTesting winner strategy with extended time to find achievable gap")

    # Load data
    print("\n1. Loading data...")
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

    print(f"   ✓ Loaded successfully")

    # 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print(f"\n2. Configuration:")
    print(f"   Horizon: {start_date} to {end_date} (42 days)")
    print(f"   Solver: APPSI_HIGHS")
    print(f"   Phase 1 timeout: 120s")
    print(f"   Phase 2 timeout: 3600s (1 HOUR)")
    print(f"   MIP gap: 3%")
    print(f"   Warmstart: Binary-only (decision hints)")

    # Run warmstart solve
    print("\n3. Running two-phase solve with binary-only warmstart...")
    print("   (This will take up to 1 hour)")

    start_time = time.time()

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
        time_limit_phase1=120,
        time_limit_phase2=3600,  # 1 HOUR
        mip_gap=0.03,
        tee=False,
    )

    total_time = time.time() - start_time

    # Results
    print("\n" + "="*80)
    print("1-HOUR TEST RESULTS")
    print("="*80)

    phase1_time = result.metadata.get('phase1_time', 0)
    phase2_time = result.metadata.get('phase2_time', 0)

    print(f"\nPhase 1:")
    print(f"  Time: {phase1_time:.1f}s")
    print(f"  Cost: ${result.metadata.get('phase1_cost', 0):,.2f}")

    print(f"\nPhase 2:")
    print(f"  Time: {phase2_time:.1f}s")
    print(f"  Cost: ${result.objective_value:,.2f}")
    print(f"  Gap: {result.gap*100:.2f}%" if result.gap else "  Gap: N/A")
    print(f"  Termination: {result.termination_condition}")

    print(f"\nTotal:")
    print(f"  Time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"  Success: {result.success}")

    # Analysis
    print("\n" + "="*80)
    print("ANALYSIS")
    print("="*80)

    if result.gap and result.gap <= 0.03:
        print(f"\n✅ REACHED 3% GAP TARGET!")
        print(f"   Actual gap: {result.gap*100:.2f}%")
        print(f"   Time needed: {total_time:.1f}s ({total_time/60:.1f} min)")
    elif result.gap and result.gap <= 0.05:
        print(f"\n✓ Within 5% gap (acceptable)")
        print(f"   Actual gap: {result.gap*100:.2f}%")
        print(f"   Time needed: {total_time:.1f}s ({total_time/60:.1f} min)")
    elif result.gap and result.gap <= 0.10:
        print(f"\n⚠️  Within 10% gap")
        print(f"   Actual gap: {result.gap*100:.2f}%")
        print(f"   Time needed: {total_time:.1f}s ({total_time/60:.1f} min)")
    else:
        print(f"\n❌ Gap still large: {result.gap*100:.1f}%" if result.gap else "\n❌ No gap information")
        print(f"   Time: {total_time:.1f}s ({total_time/60:.1f} min)")

    # Compare to 10-minute result
    print(f"\nComparison to 10-minute timeout:")
    print(f"  10-min: 637s, 60% gap, $1.9M")
    print(f"  1-hour: {phase2_time:.1f}s, {result.gap*100:.1f}% gap, ${result.objective_value/1e6:.1f}M")

    if result.gap:
        gap_improvement = (0.60 - result.gap) * 100
        print(f"  Gap improvement: {gap_improvement:+.1f} percentage points")

        if gap_improvement > 10:
            print(f"\n✅ Significant improvement with more time!")
        elif gap_improvement > 0:
            print(f"\n✓ Modest improvement")
        else:
            print(f"\n⚠️  No improvement (solver plateaued)")

    print("\n" + "="*80)
    print("RECOMMENDATION")
    print("="*80)

    if result.gap and result.gap <= 0.05:
        print(f"\n✅ Binary-only warmstart reaches {result.gap*100:.1f}% gap in {total_time/60:.1f} minutes")
        print(f"   This is acceptable for 6-week planning")
        print(f"   RECOMMEND: Use {int(phase2_time + 60)}s timeout for 6-week horizons")
    elif total_time < 720:  # Less than 12 minutes
        print(f"\n✓ Binary-only warmstart with ~12-minute timeout is practical")
        print(f"   Gap: {result.gap*100:.1f}%, Cost: ${result.objective_value/1e6:.1f}M")
    else:
        print(f"\n⚠️  Problem is very difficult even with 1 hour")
        print(f"   Consider:")
        print(f"   - Relaxing gap tolerance to 5-10%")
        print(f"   - Accepting current 11.8-minute performance")
        print(f"   - Reducing horizon to 4-5 weeks")

    print("\n" + "="*80)

    return 0


if __name__ == "__main__":
    exit(main())
