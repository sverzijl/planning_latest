"""Integration test for truck assignment functionality.

This test verifies the complete end-to-end flow of truck assignments from
optimization model through to UI display:
1. Load real data with truck schedules
2. Build and solve optimization model WITH truck_schedules parameter
3. Verify truck_loads_by_truck_dest_product_date is populated
4. Verify shipments have assigned_truck_id set
5. Verify UI adapter creates proper TruckLoadPlan

This test will fail if truck schedules are not properly enabled.
"""

import pytest
from datetime import date as Date, timedelta
from pathlib import Path

from src.parsers import MultiFileParser
from src.optimization import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.location import LocationType
from src.models.manufacturing import ManufacturingSite
from ui.utils.result_adapter import adapt_optimization_results


class TestTruckAssignmentIntegration:
    """End-to-end integration tests for truck assignment system."""

    @pytest.fixture
    def real_data_paths(self):
        """Paths to real data files for integration testing."""
        base_path = Path(__file__).parent.parent / "data" / "examples"
        return {
            'network': base_path / "Network_Config.xlsx",
            'forecast': base_path / "Gfree Forecast_Converted.xlsx",
        }

    @pytest.fixture
    def parsed_data(self, real_data_paths):
        """Parse real data files."""
        parser = MultiFileParser(
            network_file=str(real_data_paths['network']),
            forecast_file=str(real_data_paths['forecast'])
        )
        # parse_all returns tuple: (forecast, locations, routes, labor, trucks, costs)
        forecast, locations, routes, labor, trucks_list, costs = parser.parse_all()

        # Convert truck_schedules list to TruckScheduleCollection
        truck_schedules = TruckScheduleCollection(schedules=trucks_list)

        # Extract manufacturing site from locations
        manufacturing_site = None
        for loc in locations:
            if loc.type == LocationType.MANUFACTURING:
                manufacturing_site = ManufacturingSite(
                    id=loc.id,
                    name=loc.name,
                    type=loc.type,
                    storage_mode=loc.storage_mode,
                    capacity=loc.capacity,
                    latitude=loc.latitude,
                    longitude=loc.longitude,
                    production_rate=1400.0,
                    labor_calendar=labor,
                    changeover_time_hours=0.5,
                )
                break

        assert manufacturing_site is not None, "Should have manufacturing location"

        # Return as dictionary for easy access
        return {
            'forecast': forecast,
            'locations': locations,
            'routes': routes,
            'labor_calendar': labor,
            'truck_schedules': truck_schedules,
            'cost_structure': costs,
            'manufacturing_site': manufacturing_site,
        }

    def test_data_files_exist(self, real_data_paths):
        """Verify test data files exist."""
        assert real_data_paths['network'].exists(), f"Network config not found: {real_data_paths['network']}"
        assert real_data_paths['forecast'].exists(), f"Forecast not found: {real_data_paths['forecast']}"

    def test_parser_loads_truck_schedules(self, parsed_data):
        """Verify parser successfully loads truck schedules."""
        assert parsed_data is not None, "Parser should return data"
        assert 'truck_schedules' in parsed_data, "Parsed data should include truck_schedules"
        assert parsed_data['truck_schedules'] is not None, "truck_schedules should not be None"
        assert len(parsed_data['truck_schedules'].schedules) > 0, "Should have at least one truck schedule"
        print(f"Loaded {len(parsed_data['truck_schedules'].schedules)} truck schedules")

    def test_truck_assignment_end_to_end(self, parsed_data):
        """Full end-to-end test of truck assignment system.

        This is the critical integration test that verifies:
        1. Binary import works (no NameError)
        2. truck_schedules parameter is accepted
        3. Optimization creates truck variables
        4. Solver assigns products to trucks
        5. Solution extraction populates truck_loads
        6. get_shipment_plan() assigns trucks to shipments
        7. UI adapter creates proper truck plan
        """
        # Use a short planning horizon for faster testing
        # Use dates from the forecast range (June - December 2025)
        # Let model calculate start_date (accounts for D-1 production + transit times)
        end_date = Date(2025, 6, 15)  # 2 weeks from first forecast date

        print(f"\n=== Building Optimization Model ===")
        print(f"Planning horizon end: {end_date} (start will be auto-calculated)")

        # Build model WITH truck_schedules (critical!)
        model = IntegratedProductionDistributionModel(
            forecast=parsed_data['forecast'],
            labor_calendar=parsed_data['labor_calendar'],
            manufacturing_site=parsed_data['manufacturing_site'],
            cost_structure=parsed_data['cost_structure'],
            locations=parsed_data['locations'],
            routes=parsed_data['routes'],
            truck_schedules=parsed_data['truck_schedules'],  # CRITICAL: Must pass truck_schedules!
            end_date=end_date,  # Only specify end, let model calculate required start
            max_routes_per_destination=1,  # Limit to 1 route for simpler model
            allow_shortages=True,  # Allow shortages for feasibility
            enforce_shelf_life=False,  # Disable shelf life filtering to simplify
            validate_feasibility=False,  # Skip validation for faster testing
        )

        print(f"Actual planning horizon: {min(model.production_dates)} to {max(model.production_dates)} ({len(model.production_dates)} days)")

        # Verify truck data was extracted
        assert model.truck_schedules is not None, "Model should have truck_schedules"
        assert len(model.truck_indices) > 0, "Should have truck indices"
        assert len(model.trucks_to_destination) > 0, "Should have trucks_to_destination mapping"
        print(f"Truck indices: {len(model.truck_indices)}")
        print(f"Truck destinations: {list(model.trucks_to_destination.keys())}")

        print(f"\n=== Solving Optimization ===")
        print(f"Routes: {len(model.enumerated_routes)}")
        print(f"Planning days: {len(model.production_dates)}")

        # Solve optimization (use short time limit for testing)
        result = model.solve(
            solver_name='cbc',
            time_limit_seconds=120,
            tee=False,
        )

        # Verify solution was found
        assert result.success, f"Optimization should succeed. Status: {result.termination_condition}"
        assert result.is_optimal() or result.is_feasible(), "Should find optimal or feasible solution"
        print(f"Solver status: {result.termination_condition}")
        print(f"Objective value: ${result.objective_value:,.2f}")

        print(f"\n=== Verifying Truck Loads ===")

        # CRITICAL TEST: Verify truck_loads_by_truck_dest_product_date is populated
        solution = model.get_solution()
        assert solution is not None, "Should have solution"

        truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})
        assert isinstance(truck_loads, dict), "truck_loads should be a dictionary"
        assert len(truck_loads) > 0, "truck_loads should be populated (not empty!)"

        print(f"Truck loads entries: {len(truck_loads)}")
        # Print first few truck load entries for debugging
        for i, (key, quantity) in enumerate(list(truck_loads.items())[:5]):
            truck_idx, dest, prod, date = key
            truck = model.truck_by_index[truck_idx]
            print(f"  Truck {truck.id} to {dest}: {quantity:.1f} units of {prod} on {date}")

        print(f"\n=== Verifying Shipment Assignments ===")

        # CRITICAL TEST: Verify shipments have assigned_truck_id
        shipments = model.get_shipment_plan()
        assert shipments is not None, "Should have shipment plan"
        assert len(shipments) > 0, "Should have shipments"

        # Filter to shipments from manufacturing (those should be assigned to trucks)
        manufacturing_id = model.manufacturing_site.location_id
        manufacturing_shipments = [s for s in shipments if s.origin_id == manufacturing_id]
        assert len(manufacturing_shipments) > 0, "Should have shipments from manufacturing"

        # Check how many are assigned
        assigned_shipments = [s for s in manufacturing_shipments if s.assigned_truck_id is not None]
        unassigned_shipments = [s for s in manufacturing_shipments if s.assigned_truck_id is None]

        print(f"Total shipments: {len(shipments)}")
        print(f"Manufacturing shipments: {len(manufacturing_shipments)}")
        print(f"Assigned to trucks: {len(assigned_shipments)}")
        print(f"Unassigned: {len(unassigned_shipments)}")

        # Print some examples of assigned shipments
        for i, shipment in enumerate(assigned_shipments[:5]):
            print(f"  {shipment.id}: {shipment.quantity:.0f} units of {shipment.product_id} "
                  f"to {shipment.destination_id} on truck {shipment.assigned_truck_id}")

        # CRITICAL ASSERTION: At least some shipments should be assigned
        assert len(assigned_shipments) > 0, \
            "At least some shipments from manufacturing should be assigned to trucks!"

        # Calculate assignment percentage
        assignment_pct = 100 * len(assigned_shipments) / len(manufacturing_shipments)
        print(f"Assignment rate: {assignment_pct:.1f}%")

        # At least SOME shipments should be assigned - this is the critical test
        # Note: assignment % may be low due to:
        # - Routes via hubs that don't match truck destinations
        # - Limited route enumeration (max_routes_per_destination=1)
        # - Multi-hop routes that don't perfectly align with truck schedules
        # The key is that the system WORKS and assigns what it can
        assert assignment_pct > 5, \
            f"At least some shipments should be assigned (got {assignment_pct:.1f}%). " \
            f"If 0%, truck assignment system is broken."

        print(f"\n=== Verifying UI Adapter ===")

        # CRITICAL TEST: Verify UI adapter creates proper truck plan
        adapted_results = adapt_optimization_results(model, result)
        assert adapted_results is not None, "Adapted results should exist"
        assert 'truck_plan' in adapted_results, "Should have truck_plan"

        truck_plan = adapted_results['truck_plan']
        assert truck_plan is not None, "Truck plan should not be None"
        assert len(truck_plan.loads) > 0, "Truck plan should have loads (not empty!)"
        assert truck_plan.total_trucks_used > 0, "Should show trucks used"

        print(f"Truck loads in UI plan: {len(truck_plan.loads)}")
        print(f"Total trucks used: {truck_plan.total_trucks_used}")
        print(f"Average utilization: {truck_plan.average_utilization:.1%}")

        # Print some truck load details
        for i, load in enumerate(truck_plan.loads[:5]):
            print(f"  {load.truck_name} on {load.departure_date}: "
                  f"{len(load.shipments)} shipments, {load.total_units:.0f} units, "
                  f"{load.capacity_utilization:.1%} utilization")

        print(f"\n=== TEST PASSED ===")
        print("Truck assignment system is working end-to-end!")

    def test_model_without_truck_schedules_still_works(self, parsed_data):
        """Verify model still works when truck_schedules is None (backward compatibility)."""
        start_date = Date(2025, 6, 2)  # First date in forecast
        end_date = start_date + timedelta(days=3)

        # Build model WITHOUT truck_schedules
        model = IntegratedProductionDistributionModel(
            forecast=parsed_data['forecast'],
            labor_calendar=parsed_data['labor_calendar'],
            manufacturing_site=parsed_data['manufacturing_site'],
            cost_structure=parsed_data['cost_structure'],
            locations=parsed_data['locations'],
            routes=parsed_data['routes'],
            truck_schedules=None,  # Explicitly None
            start_date=start_date,
            end_date=end_date,
            max_routes_per_destination=2,
            allow_shortages=True,
            validate_feasibility=False,
        )

        # Should still solve successfully (just without truck constraints)
        result = model.solve(solver_name='cbc', time_limit_seconds=60, tee=False)
        assert result.success, "Should solve even without truck schedules"

        # But truck loads should be empty
        solution = model.get_solution()
        truck_loads = solution.get('truck_loads_by_truck_dest_product_date', {})
        assert len(truck_loads) == 0, "Should have no truck loads when truck_schedules=None"

        # And shipments should be unassigned
        shipments = model.get_shipment_plan()
        if shipments:
            assigned = [s for s in shipments if s.assigned_truck_id is not None]
            assert len(assigned) == 0, "Should have no assigned trucks when truck_schedules=None"
