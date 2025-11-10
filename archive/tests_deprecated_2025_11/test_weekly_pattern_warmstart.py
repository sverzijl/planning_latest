"""Integration test for weekly pattern warmstart strategy.

Validates the two-phase solve approach:
1. Phase 1: Weekly cycle (no pallets) → fast warmup
2. Phase 2: Full binary (with pallets + warmstart) → optimal solution

Expected performance (6-week):
- Phase 1: ~20-40s
- Phase 2: ~250-300s with warmstart
- Total: ~270-340s vs 400s+ timeout without
"""

import pytest
from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import solve_weekly_pattern_warmstart
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType


def test_weekly_pattern_warmstart_6week():
    """Test weekly pattern warmstart on 6-week horizon."""

    print("\n" + "="*80)
    print("TEST: Weekly Pattern Warmstart (6-week horizon)")
    print("="*80)

    # Load data
    data_dir = Path(__file__).parent.parent / "data" / "examples"
    forecast_file = data_dir / "Gfree Forecast.xlsm"
    network_file = data_dir / "Network_Config.xlsx"

    parser = MultiFileParser(
        forecast_file=str(forecast_file),
        network_file=str(network_file),
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Convert to unified format
    manuf_loc = [loc for loc in locations if loc.type == LocationType.MANUFACTURING][0]
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

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    # 6-week horizon
    start_date = min(e.forecast_date for e in forecast.entries)
    end_date = start_date + timedelta(days=41)

    print(f"Planning horizon: {start_date} to {end_date} (42 days)")

    # Test weekly pattern warmstart
    test_start = time.time()

    result = solve_weekly_pattern_warmstart(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        use_pallet_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        solver_name='appsi_highs',
        time_limit_phase1=120,
        time_limit_phase2=360,
        mip_gap=0.03,
        tee=False,
    )

    test_time = time.time() - test_start

    # Assertions
    print(f"\nValidation:")

    # Should complete
    assert result.solve_time_seconds > 0, "Should have solve time"
    print(f"  ✓ Completed in {result.solve_time_seconds:.1f}s")

    # Should be faster than expected single-phase timeout
    assert result.solve_time_seconds < 400, f"Should be faster than 400s, got {result.solve_time_seconds:.1f}s"
    print(f"  ✓ Faster than single-phase timeout (< 400s)")

    # Should have reasonable cost
    assert result.objective_value > 0, "Should have positive cost"
    assert result.objective_value < 1_000_000, f"Cost ${result.objective_value:,.0f} seems too high"
    print(f"  ✓ Reasonable cost: ${result.objective_value:,.0f}")

    # Should have metadata from two-phase solve
    assert result.metadata is not None, "Should have metadata"
    assert 'weekly_pattern_warmstart' in result.metadata, "Should have weekly pattern flag"
    assert result.metadata['weekly_pattern_warmstart'] is True
    print(f"  ✓ Metadata present with weekly pattern flag")

    # Should have phase breakdown
    assert 'phase1_time' in result.metadata, "Should have Phase 1 time"
    assert 'phase2_time' in result.metadata, "Should have Phase 2 time"
    phase1_time = result.metadata['phase1_time']
    phase2_time = result.metadata['phase2_time']
    print(f"  ✓ Phase breakdown: {phase1_time:.1f}s + {phase2_time:.1f}s = {result.solve_time_seconds:.1f}s")

    # Phase 1 should be fast (< 60s for 6-week)
    assert phase1_time < 60, f"Phase 1 should be < 60s, got {phase1_time:.1f}s"
    print(f"  ✓ Phase 1 fast (< 60s)")

    # Should have weekly pattern in metadata
    assert 'weekly_pattern' in result.metadata, "Should have weekly pattern"
    pattern = result.metadata['weekly_pattern']
    print(f"  ✓ Weekly pattern extracted:")
    for day, products in pattern.items():
        print(f"      {day}: {len(products)} SKUs")

    print("\n✅ ALL ASSERTIONS PASSED")
    print("="*80)


if __name__ == "__main__":
    pytest.main([__file__, '-v', '-s'])
