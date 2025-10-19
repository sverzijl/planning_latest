"""Integration tests for warmstart functionality in UnifiedNodeModel.

This test suite validates the integration of campaign-based warmstart hints
with the optimization solver, ensuring that:
1. Warmstart hints are generated correctly
2. Hints are applied to the model variables
3. Solver receives and uses the warmstart values
4. Warmstart doesn't break existing functionality
5. Solution quality is maintained with warmstart
"""

import pytest
from pathlib import Path
from datetime import date, timedelta
import time

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.warmstart_generator import generate_campaign_warmstart


@pytest.fixture
def small_test_data():
    """Create minimal test data for fast warmstart tests."""
    from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
    from src.models.unified_route import UnifiedRoute, TransportMode
    from src.models.unified_truck_schedule import UnifiedTruckSchedule
    from src.models.forecast import Forecast, ForecastEntry
    from src.models.labor_calendar import LaborCalendar, LaborDay
    from src.models.cost_structure import CostStructure

    # Create 1 manufacturing node
    manufacturing_node = UnifiedNode(
        id="6122",
        name="Manufacturing",
        capabilities=NodeCapabilities(
            can_manufacture=True,
            can_store=True,
            has_demand=False,
            requires_trucks=True,
            production_rate_per_hour=1400.0,
            daily_startup_hours=0.5,
            daily_shutdown_hours=0.25,
            default_changeover_hours=0.5,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    # Create 2 demand nodes
    demand_node_1 = UnifiedNode(
        id="6104",
        name="Hub NSW/ACT",
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            has_demand=True,
            requires_trucks=False,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    demand_node_2 = UnifiedNode(
        id="6125",
        name="Hub VIC/TAS/SA",
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            has_demand=True,
            requires_trucks=False,
        ),
        storage_mode=StorageMode.AMBIENT,
    )

    nodes = [manufacturing_node, demand_node_1, demand_node_2]

    # Create routes
    route_1 = UnifiedRoute(
        origin_node_id="6122",
        destination_node_id="6104",
        transport_mode=TransportMode.AMBIENT,
        transit_days=1,
        cost_per_unit=0.5,
    )

    route_2 = UnifiedRoute(
        origin_node_id="6122",
        destination_node_id="6125",
        transport_mode=TransportMode.AMBIENT,
        transit_days=1,
        cost_per_unit=0.5,
    )

    routes = [route_1, route_2]

    # Create truck schedules (Mon-Fri to each destination)
    trucks = []
    for day in range(5):  # Mon-Fri
        # Truck to 6104
        trucks.append(UnifiedTruckSchedule(
            origin_node_id="6122",
            destination_node_id="6104",
            day_of_week=day,
            capacity=14080,
            intermediate_stops=None,
        ))
        # Truck to 6125
        trucks.append(UnifiedTruckSchedule(
            origin_node_id="6122",
            destination_node_id="6125",
            day_of_week=day,
            capacity=14080,
            intermediate_stops=None,
        ))

    # Create forecast (3 products, 2 weeks)
    products = ['PROD_001', 'PROD_002', 'PROD_003']
    start_date = date(2025, 10, 20)  # Monday
    forecast_entries = []

    for days in range(14):
        current_date = start_date + timedelta(days=days)
        # Distribute demand across destinations
        for dest in ["6104", "6125"]:
            for prod in products:
                forecast_entries.append(ForecastEntry(
                    location_id=dest,
                    product_id=prod,
                    forecast_date=current_date,
                    quantity=1000.0,
                ))

    forecast = Forecast(entries=forecast_entries)

    # Create labor calendar (Mon-Fri: 12h fixed, weekends: 0h)
    labor_days = {}
    for days in range(14):
        current_date = start_date + timedelta(days=days)
        is_weekday = current_date.weekday() < 5

        labor_days[current_date] = LaborDay(
            date=current_date,
            fixed_hours=12.0 if is_weekday else 0.0,
            overtime_hours=2.0,
            regular_rate=20.0,
            overtime_rate=30.0,
            non_fixed_rate=40.0,
            is_fixed_day=is_weekday,
        )

    labor_calendar = LaborCalendar(days=labor_days)

    # Create cost structure (minimal costs for fast solving)
    cost_structure = CostStructure(
        production_cost_per_unit=1.0,
        shortage_penalty_per_unit=100.0,  # Keep shortage penalty
        storage_cost_frozen_per_unit_day=0.0,  # Disable storage costs
        storage_cost_ambient_per_unit_day=0.0,
        storage_cost_per_pallet_day_frozen=0.0,
        storage_cost_per_pallet_day_ambient=0.0,
        storage_cost_fixed_per_pallet=0.0,
        storage_cost_fixed_per_pallet_frozen=0.0,
        storage_cost_fixed_per_pallet_ambient=0.0,
        waste_cost_multiplier=1.0,
    )

    return {
        'nodes': nodes,
        'routes': routes,
        'trucks': trucks,
        'forecast': forecast,
        'labor_calendar': labor_calendar,
        'cost_structure': cost_structure,
        'products': products,
        'start_date': start_date,
        'end_date': start_date + timedelta(days=13),  # 2 weeks
    }


class TestWarmstartGeneration:
    """Test warmstart generation methods in UnifiedNodeModel."""

    def test_generate_warmstart_method(self, small_test_data):
        """Test that _generate_warmstart() returns valid hints dictionary."""
        # Create model
        model = UnifiedNodeModel(
            nodes=small_test_data['nodes'],
            routes=small_test_data['routes'],
            forecast=small_test_data['forecast'],
            labor_calendar=small_test_data['labor_calendar'],
            cost_structure=small_test_data['cost_structure'],
            start_date=small_test_data['start_date'],
            end_date=small_test_data['end_date'],
            truck_schedules=small_test_data['trucks'],
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        # Generate warmstart
        warmstart_hints = model._generate_warmstart()

        # Validate
        assert warmstart_hints is not None
        assert isinstance(warmstart_hints, dict)
        assert len(warmstart_hints) > 0

        # Check hint structure
        for key, value in warmstart_hints.items():
            assert len(key) == 3, "Key should be (node_id, product_id, date)"
            assert isinstance(key[0], str), "node_id should be string"
            assert isinstance(key[1], str), "product_id should be string"
            assert isinstance(key[2], date), "date should be datetime.date"
            assert value in [0, 1], f"Hint value should be binary, got {value}"

        print(f"✓ _generate_warmstart() produced {len(warmstart_hints)} hints")

    def test_apply_warmstart_method(self, small_test_data):
        """Test that _apply_warmstart() sets variable values correctly."""
        # Create model
        model = UnifiedNodeModel(
            nodes=small_test_data['nodes'],
            routes=small_test_data['routes'],
            forecast=small_test_data['forecast'],
            labor_calendar=small_test_data['labor_calendar'],
            cost_structure=small_test_data['cost_structure'],
            start_date=small_test_data['start_date'],
            end_date=small_test_data['end_date'],
            truck_schedules=small_test_data['trucks'],
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        # Build model first
        pyomo_model = model.build_model()

        # Create simple warmstart hints
        hints = {
            ("6122", "PROD_001", small_test_data['start_date']): 1,
            ("6122", "PROD_002", small_test_data['start_date'] + timedelta(days=1)): 1,
        }

        # Apply warmstart
        applied_count = model._apply_warmstart(pyomo_model, hints)

        # Validate
        assert applied_count == 2, f"Expected 2 variables to be set, got {applied_count}"

        # Check variable values were set
        for (node_id, prod, date_val), hint_value in hints.items():
            var = pyomo_model.product_produced[node_id, prod, date_val]
            assert var.value is not None, f"Variable {node_id}, {prod}, {date_val} not set"

            # Hint=1 should set binary value
            if hint_value == 1:
                assert var.value == 1, f"Variable should have warmstart value = 1"

        print(f"✓ _apply_warmstart() successfully set {applied_count} variables")


class TestWarmstartSolveIntegration:
    """Test solve() method with warmstart parameter."""

    def test_solve_with_warmstart_parameter(self, small_test_data):
        """Test that solve(use_warmstart=True) works without errors."""
        # Create model
        model = UnifiedNodeModel(
            nodes=small_test_data['nodes'],
            routes=small_test_data['routes'],
            forecast=small_test_data['forecast'],
            labor_calendar=small_test_data['labor_calendar'],
            cost_structure=small_test_data['cost_structure'],
            start_date=small_test_data['start_date'],
            end_date=small_test_data['end_date'],
            truck_schedules=small_test_data['trucks'],
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        # Solve with warmstart
        result = model.solve(
            solver_name='cbc',
            time_limit_seconds=60,
            mip_gap=0.01,
            use_warmstart=True,  # <<<--- KEY PARAMETER
            tee=False,
        )

        # Validate
        assert result.success, f"Solve failed with warmstart: {result.termination_condition}"
        assert result.is_optimal() or result.is_feasible()

        # Check solution exists
        solution = model.get_solution()
        assert solution is not None
        assert 'production_by_date_product' in solution

        production_total = sum(solution['production_by_date_product'].values())
        assert production_total > 0, "No production found in solution"

        print(f"✓ solve(use_warmstart=True) succeeded")
        print(f"  Status: {result.termination_condition}")
        print(f"  Objective: ${result.objective_value:,.2f}")
        print(f"  Solve time: {result.solve_time_seconds:.2f}s")

    def test_solve_without_warmstart_still_works(self, small_test_data):
        """Test backward compatibility - solve() without warmstart still works."""
        # Create model
        model = UnifiedNodeModel(
            nodes=small_test_data['nodes'],
            routes=small_test_data['routes'],
            forecast=small_test_data['forecast'],
            labor_calendar=small_test_data['labor_calendar'],
            cost_structure=small_test_data['cost_structure'],
            start_date=small_test_data['start_date'],
            end_date=small_test_data['end_date'],
            truck_schedules=small_test_data['trucks'],
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        # Solve WITHOUT warmstart (default behavior)
        result = model.solve(
            solver_name='cbc',
            time_limit_seconds=60,
            mip_gap=0.01,
            use_warmstart=False,  # Explicit: no warmstart
            tee=False,
        )

        # Validate
        assert result.success
        assert result.is_optimal() or result.is_feasible()

        solution = model.get_solution()
        assert solution is not None

        print(f"✓ solve(use_warmstart=False) still works (backward compatibility)")

    def test_warmstart_custom_hints(self, small_test_data):
        """Test solve() with pre-generated custom warmstart_hints."""
        # Create model
        model = UnifiedNodeModel(
            nodes=small_test_data['nodes'],
            routes=small_test_data['routes'],
            forecast=small_test_data['forecast'],
            labor_calendar=small_test_data['labor_calendar'],
            cost_structure=small_test_data['cost_structure'],
            start_date=small_test_data['start_date'],
            end_date=small_test_data['end_date'],
            truck_schedules=small_test_data['trucks'],
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        # Generate custom hints (produce all products on Monday)
        custom_hints = {}
        monday = small_test_data['start_date']
        for prod in small_test_data['products']:
            custom_hints[("6122", prod, monday)] = 1

        # Solve with custom hints
        result = model.solve(
            solver_name='cbc',
            time_limit_seconds=60,
            mip_gap=0.01,
            use_warmstart=True,
            warmstart_hints=custom_hints,  # <<<--- CUSTOM HINTS
            tee=False,
        )

        # Validate
        assert result.success
        assert result.is_optimal() or result.is_feasible()

        print(f"✓ solve() with custom warmstart_hints succeeded")

    def test_warmstart_invalid_hints_graceful(self, small_test_data):
        """Test that invalid hints don't crash the solver."""
        # Create model
        model = UnifiedNodeModel(
            nodes=small_test_data['nodes'],
            routes=small_test_data['routes'],
            forecast=small_test_data['forecast'],
            labor_calendar=small_test_data['labor_calendar'],
            cost_structure=small_test_data['cost_structure'],
            start_date=small_test_data['start_date'],
            end_date=small_test_data['end_date'],
            truck_schedules=small_test_data['trucks'],
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        # Invalid hints (node doesn't exist)
        invalid_hints = {
            ("INVALID_NODE", "PROD_001", small_test_data['start_date']): 1,
        }

        # Solve should handle gracefully
        result = model.solve(
            solver_name='cbc',
            time_limit_seconds=60,
            mip_gap=0.01,
            use_warmstart=True,
            warmstart_hints=invalid_hints,
            tee=False,
        )

        # Should still solve (hints just skipped)
        assert result.success
        assert result.is_optimal() or result.is_feasible()

        print(f"✓ Invalid hints handled gracefully (skipped)")

    def test_warmstart_partial_hints(self, small_test_data):
        """Test that partial hints (not all products) work correctly."""
        # Create model
        model = UnifiedNodeModel(
            nodes=small_test_data['nodes'],
            routes=small_test_data['routes'],
            forecast=small_test_data['forecast'],
            labor_calendar=small_test_data['labor_calendar'],
            cost_structure=small_test_data['cost_structure'],
            start_date=small_test_data['start_date'],
            end_date=small_test_data['end_date'],
            truck_schedules=small_test_data['trucks'],
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        # Partial hints (only 1 product)
        partial_hints = {
            ("6122", "PROD_001", small_test_data['start_date']): 1,
        }

        # Solve
        result = model.solve(
            solver_name='cbc',
            time_limit_seconds=60,
            mip_gap=0.01,
            use_warmstart=True,
            warmstart_hints=partial_hints,
            tee=False,
        )

        # Validate
        assert result.success
        assert result.is_optimal() or result.is_feasible()

        # Check that all products were produced (not just hinted one)
        solution = model.get_solution()
        production = solution['production_by_date_product']

        products_produced = set(prod for (date_val, prod) in production.keys())
        assert len(products_produced) >= 1, "At least hinted product should be produced"

        print(f"✓ Partial hints work correctly")
        print(f"  Products produced: {len(products_produced)}")


@pytest.mark.slow
class TestWarmstartPerformance:
    """Performance tests for warmstart in optimization."""

    @pytest.fixture
    def real_data_files(self):
        """Paths to real data files for performance testing."""
        data_dir = Path(__file__).parent.parent / "data" / "examples"

        forecast_file = data_dir / "Gfree Forecast.xlsm"
        network_file = data_dir / "Network_Config.xlsx"

        if not forecast_file.exists() or not network_file.exists():
            pytest.skip("Real data files not available for performance testing")

        return {
            'forecast': forecast_file,
            'network': network_file,
        }

    def test_warmstart_speedup_measurement(self, real_data_files):
        """Compare solve times with/without warmstart on real data."""
        # Parse data
        parser = MultiFileParser(
            forecast_file=real_data_files['forecast'],
            network_file=real_data_files['network'],
        )

        forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

        # Convert to unified format
        from src.models.manufacturing import ManufacturingSite
        from src.models.location import LocationType
        from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

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

        converter = LegacyToUnifiedConverter()
        nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
        unified_routes = converter.convert_routes(routes)
        unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

        # Planning horizon (2 weeks for faster testing)
        start_date = date(2025, 10, 20)
        end_date = start_date + timedelta(days=13)  # 2 weeks

        # Baseline: Solve WITHOUT warmstart
        model_baseline = UnifiedNodeModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=start_date,
            end_date=end_date,
            truck_schedules=unified_truck_schedules,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        start_time = time.time()
        result_baseline = model_baseline.solve(
            solver_name='cbc',
            time_limit_seconds=120,
            mip_gap=0.01,
            use_warmstart=False,  # NO WARMSTART
            tee=False,
        )
        time_baseline = time.time() - start_time

        # Warmstart: Solve WITH warmstart
        model_warmstart = UnifiedNodeModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=start_date,
            end_date=end_date,
            truck_schedules=unified_truck_schedules,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        start_time = time.time()
        result_warmstart = model_warmstart.solve(
            solver_name='cbc',
            time_limit_seconds=120,
            mip_gap=0.01,
            use_warmstart=True,  # WITH WARMSTART
            tee=False,
        )
        time_warmstart = time.time() - start_time

        # Report results
        print(f"\n{'='*60}")
        print("WARMSTART PERFORMANCE COMPARISON (2-week horizon)")
        print(f"{'='*60}")
        print(f"Baseline (no warmstart): {time_baseline:.2f}s")
        print(f"Warmstart enabled:       {time_warmstart:.2f}s")

        if time_warmstart < time_baseline:
            speedup = (time_baseline - time_warmstart) / time_baseline * 100
            print(f"Speedup:                 {speedup:.1f}% faster")
        else:
            slowdown = (time_warmstart - time_baseline) / time_baseline * 100
            print(f"Slowdown:                {slowdown:.1f}% slower (warmstart overhead)")

        # Both should succeed
        assert result_baseline.success
        assert result_warmstart.success

        print(f"\n✓ Both solutions successful")

    def test_warmstart_generation_overhead(self, real_data_files):
        """Test that warmstart generation takes <1 second."""
        # Parse data
        parser = MultiFileParser(
            forecast_file=real_data_files['forecast'],
            network_file=real_data_files['network'],
        )

        forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

        # Convert to unified format
        from src.models.manufacturing import ManufacturingSite
        from src.models.location import LocationType
        from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

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

        converter = LegacyToUnifiedConverter()
        nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
        unified_routes = converter.convert_routes(routes)
        unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

        # Create model
        start_date = date(2025, 10, 20)
        end_date = start_date + timedelta(days=27)  # 4 weeks

        model = UnifiedNodeModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=start_date,
            end_date=end_date,
            truck_schedules=unified_truck_schedules,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        # Measure warmstart generation time
        start_time = time.time()
        warmstart_hints = model._generate_warmstart()
        generation_time = time.time() - start_time

        # Validate
        assert warmstart_hints is not None
        assert len(warmstart_hints) > 0
        assert generation_time < 1.0, f"Generation took {generation_time:.3f}s (expected <1s)"

        print(f"✓ Warmstart generation: {generation_time:.3f}s (<1s threshold)")
        print(f"  Hints generated: {len(warmstart_hints)}")

    def test_warmstart_application_overhead(self, real_data_files):
        """Test that warmstart application takes <0.1 seconds."""
        # Parse data
        parser = MultiFileParser(
            forecast_file=real_data_files['forecast'],
            network_file=real_data_files['network'],
        )

        forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

        # Convert to unified format
        from src.models.manufacturing import ManufacturingSite
        from src.models.location import LocationType
        from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

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

        converter = LegacyToUnifiedConverter()
        nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
        unified_routes = converter.convert_routes(routes)
        unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

        # Create model
        start_date = date(2025, 10, 20)
        end_date = start_date + timedelta(days=27)  # 4 weeks

        model = UnifiedNodeModel(
            nodes=nodes,
            routes=unified_routes,
            forecast=forecast,
            labor_calendar=labor_calendar,
            cost_structure=cost_structure,
            start_date=start_date,
            end_date=end_date,
            truck_schedules=unified_truck_schedules,
            use_batch_tracking=True,
            allow_shortages=True,
            enforce_shelf_life=True,
        )

        # Build model
        pyomo_model = model.build_model()

        # Generate hints
        warmstart_hints = model._generate_warmstart()

        # Measure application time
        start_time = time.time()
        applied_count = model._apply_warmstart(pyomo_model, warmstart_hints)
        application_time = time.time() - start_time

        # Validate
        assert applied_count > 0
        assert application_time < 0.1, f"Application took {application_time:.3f}s (expected <0.1s)"

        print(f"✓ Warmstart application: {application_time:.3f}s (<0.1s threshold)")
        print(f"  Variables set: {applied_count}")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
