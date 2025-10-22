"""Full 6-week test with batch-binary Phase 1.

Tests complete warmstart strategy with:
- Phase 1: Batch-level binaries (discrete cost structure)
- Phase 1: 72s solve time
- Warmstart: 4,515 pallet hints (100% coverage, HIGH QUALITY)
- Phase 2: Full pallet tracking with enhanced warmstart

Expected performance:
- Phase 1: ~72s (validated)
- Phase 2: ~200-400s (improved from 637s baseline)
- Total: ~270-470s (4.5-7.8 min) ✅ UNDER 10-minute target!
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time
import json

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    print("="*80)
    print("6-WEEK BATCH-BINARY PHASE 1 TEST")
    print("="*80)
    print("\nTesting enhanced warmstart with batch-level binaries")

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

    # 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print(f"\nConfiguration:")
    print(f"  Horizon: {(end_date - start_date).days + 1} days")
    print(f"  Phase 1 timeout: 600s (allow time for batch binaries)")
    print(f"  Phase 2 timeout: 600s (10 minutes)")
    print(f"  MIP gap: 3%")
    print(f"  Expected: Phase 1 ~72s, Phase 2 ~200-400s with enhanced warmstart")

    # Run enhanced warmstart
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
        time_limit_phase1=600,
        time_limit_phase2=600,
        mip_gap=0.03,
        tee=False,
    )

    total_time = time.time() - start_time

    # Load baseline for comparison
    try:
        with open('warmstart_baseline.json') as f:
            baseline = json.load(f)
    except:
        baseline = None

    # Extract results
    phase1_time = result.metadata.get('phase1_time', 0)
    phase2_time = result.metadata.get('phase2_time', 0)
    phase1_cost = result.metadata.get('phase1_cost', 0)
    pallet_hints = result.metadata.get('warmstart_pallet_hints', 0)

    print("\n" + "="*80)
    print("BATCH-BINARY RESULTS")
    print("="*80)

    print(f"\nPhase 1:")
    print(f"  Time: {phase1_time:.1f}s")
    print(f"  Cost: ${phase1_cost:,.2f}")
    print(f"  Batch binaries: {result.metadata.get('phase1_batch_binaries', 0):,}")

    print(f"\nPhase 2:")
    print(f"  Time: {phase2_time:.1f}s")
    print(f"  Cost: ${result.objective_value:,.2f}")
    print(f"  Gap: {result.gap*100:.2f}%" if result.gap else "  Gap: N/A")
    print(f"  Pallet hints: {pallet_hints:,}")

    print(f"\nTotal:")
    print(f"  Time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"  Success: {result.success}")

    # Compare to baseline
    if baseline:
        print("\n" + "="*80)
        print("COMPARISON TO BASELINE")
        print("="*80)

        baseline_phase2 = baseline['phase2_time']
        baseline_total = baseline['total_time']

        speedup_phase2 = baseline_phase2 / phase2_time if phase2_time > 0 else 1.0
        speedup_total = baseline_total / total_time if total_time > 0 else 1.0

        print(f"\nBaseline (binary-only warmstart, no batch binaries):")
        print(f"  Phase 2: {baseline_phase2:.1f}s")
        print(f"  Total: {baseline_total:.1f}s")
        print(f"  Gap: {baseline['gap']*100:.1f}%")

        print(f"\nBatch-Binary (current):")
        print(f"  Phase 2: {phase2_time:.1f}s")
        print(f"  Total: {total_time:.1f}s")
        print(f"  Gap: {result.gap*100:.1f}%" if result.gap else "  Gap: N/A")

        print(f"\nImprovement:")
        print(f"  Phase 2 speedup: {speedup_phase2:.2f}×")
        print(f"  Total speedup: {speedup_total:.2f}×")

        time_saved = baseline_total - total_time
        print(f"  Time saved: {time_saved:.1f}s")

        if total_time < 600:
            print(f"\n🎉 SUCCESS: Under 10-minute target!")
            print(f"   Total: {total_time:.1f}s ({total_time/60:.1f} min)")
        elif total_time < baseline_total:
            print(f"\n✅ Improvement: {time_saved:.1f}s faster than baseline")
        else:
            print(f"\n⚠️  Slower than baseline by {-time_saved:.1f}s")

        if result.gap and baseline['gap']:
            gap_improvement = (baseline['gap'] - result.gap) * 100
            print(f"  Gap improvement: {gap_improvement:+.1f} percentage points")

    print("\n" + "="*80)

    return 0 if total_time < 600 else 1


if __name__ == "__main__":
    exit(main())
