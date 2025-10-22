"""Test hybrid integer/continuous pallet formulation.

Revolutionary approach:
- Integer pallet_count for ≤10 pallets (domain {0...10})
- Linear cost for >10 pallets (continuous approximation)

Expected:
- 84% domain reduction (62 → 10)
- Potential 60-90% solve speedup
- NO WARMSTART NEEDED!
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
    print("HYBRID INTEGER/CONTINUOUS PALLET TEST")
    print("="*80)
    print("\nTesting revolutionary hybrid formulation:")
    print("  • Integer pallet_count for cohorts ≤10 pallets (0-10 domain)")
    print("  • Linear cost approximation for cohorts >10 pallets")
    print("  • Expected: 60-90% faster than full integer formulation!")

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
    print(f"  Horizon: 6 weeks (42 days)")
    print(f"  Hybrid threshold: 3,200 units (10 pallets)")
    print(f"  Timeout: 600s (10 minutes)")
    print(f"  MIP gap: 3%")
    print(f"  NO WARMSTART (testing hybrid direct solve)")

    # Build and solve with hybrid formulation
    print("\nBuilding model with hybrid pallet formulation...")

    model = UnifiedNodeModel(
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
        use_hybrid_pallet_formulation=True,  # ← HYBRID ENABLED
        pallet_hybrid_threshold=3200,  # 10 pallets
    )

    print("\nSolving with hybrid formulation (no warmstart)...")
    start_time = time.time()

    result = model.solve(
        solver_name='appsi_highs',
        time_limit_seconds=600,
        mip_gap=0.03,
        use_warmstart=False,
        tee=False,
    )

    solve_time = time.time() - start_time

    print("\n" + "="*80)
    print("HYBRID FORMULATION RESULTS")
    print("="*80)

    print(f"\nSolve Performance:")
    print(f"  Time: {solve_time:.1f}s")
    print(f"  Success: {result.success}")
    print(f"  Termination: {result.termination_condition}")
    print(f"  Cost: ${result.objective_value:,.2f}")
    if result.gap:
        print(f"  Gap: {result.gap*100:.2f}%")

    print(f"\nComparison to Baseline:")
    print(f"  Full integer (no warmstart): 636s, 78% gap, $3.5M")
    print(f"  Hybrid (current):            {solve_time:.1f}s, {result.gap*100:.1f if result.gap else 'N/A'}% gap, ${result.objective_value/1e6:.2f}M")

    if solve_time < 300:
        speedup = 636 / solve_time
        print(f"\n🎉 REVOLUTIONARY: {speedup:.1f}× faster than baseline!")
        print(f"   Domain reduction (62→10) achieved massive speedup!")
    elif solve_time < 500:
        speedup = 636 / solve_time
        print(f"\n✅ SIGNIFICANT IMPROVEMENT: {speedup:.1f}× faster!")
    elif solve_time < 636:
        print(f"\n✓ Improved performance")
    else:
        print(f"\n⚠️  Similar or slower than baseline")

    if solve_time < 600:
        print(f"\n✅ MEETS 10-MINUTE TARGET!")
        print(f"   NO WARMSTART NEEDED!")
        return 0
    else:
        print(f"\n⚠️  Still over 10-minute target by {solve_time-600:.1f}s")
        return 1


if __name__ == "__main__":
    exit(main())
