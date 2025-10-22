"""Test solving Phase 2 directly without warmstart.

MIP Expert Hypothesis: Warmstart from different objective may be counter-productive.
Test if solving Phase 2 directly (cold start) performs better.

Advantages of no warmstart:
- No Phase 1 overhead (save 72s)
- No solution bias from unit-cost objective
- Solver explores freely based on pallet-cost objective
- Can use full 10-minute budget for Phase 2
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def main():
    print("="*80)
    print("NO WARMSTART TEST - Phase 2 Direct Solve")
    print("="*80)
    print("\nHypothesis: Cold start may outperform warmstart from different objective")
    print("Advantage: No Phase 1 overhead (72s), no solution bias")

    # Load data
    print("\n1. Loading data...")
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
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
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

    # 6-week horizon
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=6*7 - 1)

    print(f"\n2. Configuration:")
    print(f"   Horizon: {start_date} to {end_date} (42 days)")
    print(f"   Solver: APPSI_HIGHS")
    print(f"   Time limit: 600s (10 minutes - full budget for Phase 2)")
    print(f"   MIP gap: 3%")
    print(f"   Warmstart: DISABLED (cold start)")

    # Build Phase 2 model directly (no Phase 1)
    print("\n3. Building Phase 2 model (WITH pallet tracking, NO warmstart)...")

    model = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,  # Original pallet costs
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
    )

    # Solve without warmstart
    print("\n4. Solving (cold start - no warmstart bias)...")
    print("   Solver will explore freely based on pallet-cost objective")

    start_time = time.time()

    result = model.solve(
        solver_name='appsi_highs',
        time_limit_seconds=600,  # Full 10 minutes
        mip_gap=0.03,            # 3% gap
        use_warmstart=False,     # NO WARMSTART
        tee=False,
    )

    solve_time = time.time() - start_time

    # Results
    print("\n" + "="*80)
    print("NO WARMSTART RESULTS")
    print("="*80)

    print(f"\nSolve Time: {solve_time:.1f}s (limit: 600s)")
    print(f"Success: {result.success}")
    print(f"Termination: {result.termination_condition}")
    print(f"Cost: ${result.objective_value:,.2f}")
    if result.gap:
        print(f"Gap: {result.gap*100:.2f}%")

    # Compare to warmstart strategies
    print("\n" + "="*80)
    print("COMPARISON TO WARMSTART STRATEGIES")
    print("="*80)

    print(f"\nBinary-Only Warmstart:")
    print(f"  Phase 1: 72s")
    print(f"  Phase 2: 637s (60% gap, $1.9M)")
    print(f"  Total: 709s")

    print(f"\nNo Warmstart (Current Test):")
    print(f"  Phase 1: 0s (skipped)")
    print(f"  Phase 2: {solve_time:.1f}s ({result.gap*100:.1f}% gap, ${result.objective_value/1e6:.1f}M)")
    print(f"  Total: {solve_time:.1f}s")

    if solve_time < 600:
        print(f"\n✅ SUCCESS: Cold start completed WITHIN 10-minute limit!")
        print(f"   Saved: {709 - solve_time:.1f}s vs binary-only warmstart")
    else:
        print(f"\n⚠️  Cold start timed out at {solve_time:.1f}s")

    # Gap comparison
    binary_only_gap = 0.60  # From previous test
    if result.gap:
        if result.gap < binary_only_gap:
            improvement = (binary_only_gap - result.gap) * 100
            print(f"✅ Gap improved: {result.gap*100:.1f}% vs {binary_only_gap*100:.1f}% (binary-only)")
            print(f"   {improvement:.1f}% gap reduction")
        elif result.gap > binary_only_gap * 1.1:
            print(f"❌ Gap worse: {result.gap*100:.1f}% vs {binary_only_gap*100:.1f}% (binary-only)")
        else:
            print(f"✓ Gap similar: {result.gap*100:.1f}% vs {binary_only_gap*100:.1f}% (binary-only)")

    print("\n" + "="*80)
    print("VERDICT")
    print("="*80)

    if solve_time < 600 and result.gap and result.gap < 0.10:
        print("\n🏆 NO WARMSTART is the winner!")
        print("   Completes within 10-minute target")
        print("   No Phase 1 overhead")
        print("   No solution bias from different objective")
        print("\n   RECOMMENDATION: Use direct Phase 2 solve for 6-week horizons")
    elif solve_time < 709 and result.gap and result.gap <= binary_only_gap:
        print("\n✅ NO WARMSTART performs better than warmstart!")
        print(f"   Faster: {solve_time:.1f}s vs 709s (binary-only)")
        print(f"   Better or similar gap: {result.gap*100:.1f}%")
        print("\n   RECOMMENDATION: Disable warmstart for 6-week horizons")
    else:
        print("\n⚠️  Binary-only warmstart still slightly better")
        print(f"   But close enough to consider both viable")

    print("\n" + "="*80)

    return 0 if solve_time < 600 else 1


if __name__ == "__main__":
    exit(main())
