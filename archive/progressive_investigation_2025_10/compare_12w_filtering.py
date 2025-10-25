"""
12-Week @ 2% Gap: Shipment Filtering Comparison

Runs TWO complete solves to compare filtering impact:
1. WITH filtering (filter_shipments_by_freshness=True)
2. WITHOUT filtering (filter_shipments_by_freshness=False)

Expected total runtime: 40-120 minutes (20-60 min each)
"""

from datetime import date, timedelta
from pathlib import Path
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from tests.conftest import create_test_products


def load_data():
    """Load 12-week data."""
    parser = MultiFileParser(
        forecast_file=Path('data/examples/Gluten Free Forecast - Latest.xlsm'),
        network_file=Path('data/examples/Network_Config.xlsx')
    )
    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
    manuf_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit
    )

    start_date = min(e.forecast_date for e in forecast.entries)
    end_date = start_date + timedelta(days=83)

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manuf_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_trucks = converter.convert_truck_schedules(truck_schedules_list, manuf_site.id)
    products = create_test_products(sorted(set(e.product_id for e in forecast.entries)))

    return {
        'nodes': nodes, 'routes': unified_routes, 'forecast': forecast,
        'labor_calendar': labor_calendar, 'cost_structure': cost_structure,
        'truck_schedules': unified_trucks, 'products': products,
        'start_date': start_date, 'end_date': end_date,
    }


def main():
    print("="*80)
    print("12-WEEK @ 2% GAP: FILTERING COMPARISON")
    print("="*80)
    print("\nModel improvements active:")
    print("  ✓ Weekend capacity: 14h max")
    print("  ✓ 7-day minimum freshness (demand cohorts)")
    print("  ? Shipment filtering: TESTING")
    print("\nRunning 2 solves to compare...")
    print("="*80)

    data = load_data()

    # TEST 1: WITH FILTERING
    print("\n" + "="*80)
    print("TEST 1: WITH Shipment Filtering")
    print("="*80)
    print("Expected: ~50k shipment cohorts, solve time TBD")
    print("\nSolving 12 weeks @ 2% gap with filtering...")
    print("(This may take 20-60 minutes)")

    model_with = UnifiedNodeModel(
        **data,
        use_batch_tracking=True,
        allow_shortages=True,
        filter_shipments_by_freshness=True,  # ENABLED
    )

    start1 = time.time()
    result_with = model_with.solve(
        solver_name='appsi_highs',
        mip_gap=0.02,
        time_limit_seconds=7200  # 2 hours max (no timeout for proper comparison)
    )
    time_with = time.time() - start1

    shipments_with = len(model_with.model.shipment_cohort_index) if hasattr(model_with.model, 'shipment_cohort_index') else 0

    print(f"\nTest 1 Complete:")
    print(f"  Time: {time_with:.1f}s ({time_with/60:.1f} min)")
    print(f"  Objective: ${result_with.objective_value:,.2f}")
    print(f"  Status: {result_with.termination_condition}")
    print(f"  Shipment cohorts: {shipments_with:,}")

    # TEST 2: WITHOUT FILTERING
    print("\n" + "="*80)
    print("TEST 2: WITHOUT Shipment Filtering")
    print("="*80)
    print("Expected: ~170k shipment cohorts, solve time TBD")
    print("\nSolving 12 weeks @ 2% gap without filtering...")
    print("(This may take 20-60 minutes)")

    model_without = UnifiedNodeModel(
        **data,
        use_batch_tracking=True,
        allow_shortages=True,
        filter_shipments_by_freshness=False,  # DISABLED
    )

    start2 = time.time()
    result_without = model_without.solve(
        solver_name='appsi_highs',
        mip_gap=0.02,
        time_limit_seconds=7200  # 2 hours max
    )
    time_without = time.time() - start2

    shipments_without = len(model_without.model.shipment_cohort_index) if hasattr(model_without.model, 'shipment_cohort_index') else 0

    print(f"\nTest 2 Complete:")
    print(f"  Time: {time_without:.1f}s ({time_without/60:.1f} min)")
    print(f"  Objective: ${result_without.objective_value:,.2f}")
    print(f"  Status: {result_without.termination_condition}")
    print(f"  Shipment cohorts: {shipments_without:,}")

    # COMPARISON
    print("\n" + "="*80)
    print("COMPARISON RESULTS")
    print("="*80)

    print(f"\nShipment cohorts:")
    print(f"  WITH filtering:    {shipments_with:,}")
    print(f"  WITHOUT filtering: {shipments_without:,}")
    reduction = (shipments_without - shipments_with) / shipments_without * 100 if shipments_without > 0 else 0
    print(f"  Reduction: {reduction:.1f}%")

    print(f"\nSolve time:")
    print(f"  WITH filtering:    {time_with:.1f}s ({time_with/60:.1f} min)")
    print(f"  WITHOUT filtering: {time_without:.1f}s ({time_without/60:.1f} min)")

    if time_without > time_with:
        speedup = time_without / time_with
        print(f"  ✓ Filtering is FASTER: {speedup:.2f}× speedup")
    else:
        slowdown = time_with / time_without
        print(f"  ✗ Filtering is SLOWER: {slowdown:.2f}× slowdown")

    print(f"\nObjective quality:")
    print(f"  WITH filtering:    ${result_with.objective_value:,.2f}")
    print(f"  WITHOUT filtering: ${result_without.objective_value:,.2f}")
    obj_diff = abs(result_with.objective_value - result_without.objective_value) / result_without.objective_value * 100
    print(f"  Difference: {obj_diff:.2f}%")

    print("\n" + "="*80)
    print("VERDICT")
    print("="*80)

    if time_without > time_with * 1.1 and obj_diff < 5:
        print("\n✅ KEEP FILTERING: Faster solve with similar solution quality")
    elif time_with > time_without * 1.1:
        print("\n❌ REMOVE FILTERING: Makes problem harder to solve")
    else:
        print("\n⚖️  NEUTRAL: Minimal impact either way")


if __name__ == '__main__':
    main()
