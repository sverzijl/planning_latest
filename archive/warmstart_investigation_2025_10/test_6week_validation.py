"""6-Week Warmstart Validation Test

Validates that the fix works for real 6-week solve.

Success criteria:
1. Total time < 600s (10 minutes)
2. Phase 1 time < 120s (2 minutes)
3. Phase 2 benefits from warmstart
4. Solution is feasible
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
    print("6-WEEK WARMSTART VALIDATION TEST")
    print("="*80)
    print("\nValidating fix for Phase 1 pallet variable issue...")

    # Load data
    print("\n1. Loading data files...")
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

    print(f"   ✓ Loaded {len(nodes)} nodes, {len(unified_routes)} routes")
    print(f"   ✓ Forecast: {len(forecast.entries)} entries")
    print(f"   ✓ Inventory date: {inventory_date}")

    # 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)  # 42 days

    print(f"\n2. Solve configuration:")
    print(f"   Horizon: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")
    print(f"   MIP Gap: 3%")
    print(f"   Solver: APPSI_HIGHS")
    print(f"   Phase 1 timeout: 120s")
    print(f"   Phase 2 timeout: 600s (10 min)")
    print(f"   Batch tracking: True")
    print(f"   Allow shortages: True")

    # Track phase statistics
    phase_stats = {'phase1_time': None, 'phase2_time': None}

    def progress_callback(phase, status, elapsed, cost):
        """Capture phase statistics."""
        if status == "complete":
            phase_stats[f'phase{phase}_time'] = elapsed
            phase_stats[f'phase{phase}_cost'] = cost

    # Run warmstart solve
    print("\n3. Running two-phase warmstart solve...")
    print("   (This will show cost conversion and model building output)")
    print()

    start_time = time.time()

    try:
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
            time_limit_phase2=600,
            mip_gap=0.03,
            tee=False,
            progress_callback=progress_callback,
        )

        total_time = time.time() - start_time

        # Validate results
        print("\n" + "="*80)
        print("VALIDATION RESULTS")
        print("="*80)

        success = True

        # 1. Check solve succeeded
        print(f"\n1. Solve Status:")
        print(f"   Success: {result.success}")
        print(f"   Termination: {result.termination_condition}")

        if not result.success:
            print(f"   ❌ FAILED: {result.infeasibility_message}")
            success = False
        else:
            print(f"   ✓ Solve succeeded")

        # 2. Check total time
        print(f"\n2. Total Time:")
        print(f"   Elapsed: {total_time:.1f}s")
        print(f"   Limit: 600s (10 minutes)")

        if total_time >= 600:
            print(f"   ❌ FAILED: Exceeded time limit")
            success = False
        else:
            print(f"   ✓ Under time limit")

        # 3. Check Phase 1 time
        phase1_time = phase_stats.get('phase1_time') or result.metadata.get('phase1_time', 0)
        print(f"\n3. Phase 1 Performance:")
        print(f"   Time: {phase1_time:.1f}s")
        print(f"   Expected: 20-40s (fast warmstart)")

        if phase1_time > 120:
            print(f"   ⚠️  WARNING: Phase 1 slower than expected")
            print(f"   Check if pallet variables were eliminated")
        elif phase1_time > 60:
            print(f"   ⚠️  SLOW: Phase 1 took {phase1_time:.1f}s (expected 20-40s)")
        else:
            print(f"   ✓ Phase 1 is fast")

        # 4. Check Phase 2 time
        phase2_time = phase_stats.get('phase2_time') or result.metadata.get('phase2_time', 0)
        print(f"\n4. Phase 2 Performance:")
        print(f"   Time: {phase2_time:.1f}s")

        if phase1_time > 0 and phase2_time > 0:
            ratio = phase2_time / phase1_time
            print(f"   Ratio: Phase 2 is {ratio:.1f}× slower than Phase 1")

            if ratio < 2:
                print(f"   ⚠️  WARNING: Phase 1 not simplified enough (ratio {ratio:.1f} < 2.0)")
            else:
                print(f"   ✓ Phase 1 is simplified (ratio {ratio:.1f})")

        # 5. Check solution quality
        print(f"\n5. Solution Quality:")
        print(f"   Cost: ${result.objective_value:,.2f}")

        if result.gap:
            print(f"   Gap: {result.gap*100:.2f}%")
            if result.gap > 0.05:
                print(f"   ⚠️  WARNING: Gap {result.gap*100:.1f}% > 5%")
            else:
                print(f"   ✓ Gap acceptable")

        if result.objective_value > 1_000_000:
            print(f"   ⚠️  WARNING: Cost very high (potential shortage penalties)")
        else:
            print(f"   ✓ Cost reasonable")

        # 6. Check cost conversion worked
        phase1_cost = phase_stats.get('phase1_cost') or result.metadata.get('phase1_cost', 0)
        phase2_cost = result.objective_value

        print(f"\n6. Cost Equivalence (Phase 1 vs Phase 2):")
        print(f"   Phase 1 cost: ${phase1_cost:,.2f}")
        print(f"   Phase 2 cost: ${phase2_cost:,.2f}")

        if phase1_cost > 0:
            cost_ratio = phase2_cost / phase1_cost
            cost_diff_pct = abs(phase2_cost - phase1_cost) / phase1_cost * 100

            print(f"   Ratio: {cost_ratio:.2f}×")
            print(f"   Difference: {cost_diff_pct:.1f}%")

            if cost_ratio > 2.0:
                print(f"   ⚠️  WARNING: Phase 2 cost much higher than Phase 1")
                print(f"   May indicate cost conversion issue or shortage penalties")
            elif cost_diff_pct < 10:
                print(f"   ✓ Costs are similar (economic equivalence)")
            else:
                print(f"   ⚠️  Costs differ by {cost_diff_pct:.1f}%")

        # Final verdict
        print("\n" + "="*80)
        if success and total_time < 600 and phase1_time < 120:
            print("✅ VALIDATION PASSED!")
            print("="*80)
            print(f"\nFix is working correctly:")
            print(f"  • Phase 1: {phase1_time:.1f}s (fast warmstart)")
            print(f"  • Phase 2: {phase2_time:.1f}s (with warmstart)")
            print(f"  • Total: {total_time:.1f}s (under 10-minute limit)")
            print(f"  • Solution: Feasible with ${result.objective_value:,.2f} cost")
            return 0
        else:
            print("❌ VALIDATION FAILED!")
            print("="*80)
            print(f"\nIssues detected:")
            if not success:
                print(f"  • Solve failed")
            if total_time >= 600:
                print(f"  • Total time {total_time:.1f}s exceeded limit")
            if phase1_time >= 120:
                print(f"  • Phase 1 time {phase1_time:.1f}s too slow")
            return 1

    except Exception as e:
        total_time = time.time() - start_time
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print(f"\nFailed after {total_time:.1f}s")
        return 1


if __name__ == "__main__":
    exit(main())
