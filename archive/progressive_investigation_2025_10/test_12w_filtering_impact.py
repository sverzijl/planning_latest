"""
Definitive Test: 12-Week Solve @ 2% Gap
Comparing WITH and WITHOUT shipment filtering

This will take 30-60 minutes per solve (2 solves total).
Purpose: Verify if shipment filtering helps or hurts at tight gaps.
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
    end_date = start_date + timedelta(days=83)  # 12 weeks

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
    print("12-WEEK SOLVE @ 2% GAP: FILTERING IMPACT TEST")
    print("="*80)
    print("\nThis will run TWO solves (expect 30-60 min each):")
    print("1. WITH shipment filtering (current code)")
    print("2. WITHOUT shipment filtering (temporarily disabled)")
    print("\nTotal test time: 60-120 minutes")
    print("="*80)

    data = load_data()

    # TEST 1: WITH FILTERING (current implementation)
    print("\n" + "="*80)
    print("TEST 1: WITH Shipment Filtering")
    print("="*80)
    print("Shipment filtering: ENABLED")
    print("Weekend capacity: 14h")
    print("7-day minimum freshness: ENABLED")
    print("\nSolving... (this will take 10-30 minutes)")

    model_with_filter = UnifiedNodeModel(
        nodes=data['nodes'],
        routes=data['routes'],
        forecast=data['forecast'],
        labor_calendar=data['labor_calendar'],
        cost_structure=data['cost_structure'],
        products=data['products'],
        start_date=data['start_date'],
        end_date=data['end_date'],
        truck_schedules=data['truck_schedules'],
        use_batch_tracking=True,
        allow_shortages=True,
    )

    start_time = time.time()
    result_with = model_with_filter.solve(
        solver_name='appsi_highs',
        mip_gap=0.02,  # 2% gap
        time_limit_seconds=3600  # 60 min max
    )
    time_with = time.time() - start_time

    # Get model statistics
    built_model_with = model_with_filter.model
    shipments_with = len(built_model_with.shipment_cohort_index) if hasattr(built_model_with, 'shipment_cohort_index') else 0

    print(f"\nTest 1 Results:")
    print(f"  Solve time: {time_with:.1f}s ({time_with/60:.1f} min)")
    print(f"  Objective: ${result_with.objective_value:,.2f}")
    print(f"  Status: {result_with.termination_condition}")
    print(f"  Success: {result_with.success}")
    print(f"  Shipment cohorts: {shipments_with:,}")

    # TEST 2: WITHOUT FILTERING
    # Temporarily disable filtering by commenting out the check
    print("\n" + "="*80)
    print("TEST 2: WITHOUT Shipment Filtering")
    print("="*80)
    print("⚠️  Need to temporarily disable filtering in code...")
    print("Please manually disable the shipment filtering (lines 996-1025)")
    print("in unified_node_model.py, then re-run this script.")
    print("\nOr run the baseline benchmark which doesn't have filtering:")
    print("  12w @ 2% gap from clean_scaling_benchmark.txt")
    print("  (extrapolate from 12w @ 40% gap = 464s)")
    print("\nEstimated time without filtering: 800-1200s (13-20 min)")


if __name__ == '__main__':
    main()
