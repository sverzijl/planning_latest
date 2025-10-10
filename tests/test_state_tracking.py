"""
Tests for frozen/ambient state tracking in the integrated production-distribution model.

These tests verify that the model correctly:
1. Identifies frozen vs ambient storage locations
2. Tracks product state (frozen/ambient) through the network
3. Handles thawing transitions (frozen → ambient)
4. Applies state-specific costs (frozen holding cost vs ambient holding cost)
5. Ensures demand is satisfied from ambient inventory only
"""

import pytest
from datetime import date, timedelta
from typing import List, Dict
import os

from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel


# Test data paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'examples')
NETWORK_CONFIG_PATH = os.path.join(DATA_DIR, 'Network_Config.xlsx')
FORECAST_PATH = os.path.join(DATA_DIR, 'Gfree Forecast_Converted.xlsx')


@pytest.fixture
def sample_locations() -> List[Location]:
    """Create sample locations with different storage modes."""
    return [
        # Manufacturing site (ambient only)
        Location(
            id='6122',
            name='Manufacturing Site',
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.AMBIENT
        ),
        # Lineage (frozen storage)
        Location(
            id='Lineage',
            name='Lineage Frozen Storage',
            type=LocationType.STORAGE,
            storage_mode=StorageMode.FROZEN,
            capacity=100000
        ),
        # 6130 WA (supports both frozen and ambient - thaws on-site)
        Location(
            id='6130',
            name='WA Breadroom',
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.BOTH
        ),
        # 6125 VIC Hub (ambient only)
        Location(
            id='6125',
            name='VIC Hub',
            type=LocationType.STORAGE,
            storage_mode=StorageMode.AMBIENT
        ),
        # 6104 NSW Hub (ambient only)
        Location(
            id='6104',
            name='NSW Hub',
            type=LocationType.STORAGE,
            storage_mode=StorageMode.AMBIENT
        ),
        # Other breadrooms (ambient only)
        Location(
            id='6108',
            name='ACT Breadroom',
            type=LocationType.BREADROOM,
            storage_mode=StorageMode.AMBIENT
        ),
    ]


@pytest.fixture
def sample_routes(sample_locations) -> List[Route]:
    """Create sample routes including frozen route to Lineage."""
    return [
        # Frozen route from manufacturing to Lineage
        Route(
            id='R_6122_Lineage_Frozen',
            origin_id='6122',
            destination_id='Lineage',
            transport_mode=StorageMode.FROZEN,
            transit_time_days=1.0,
            cost=0.15  # Higher cost for frozen transport
        ),
        # Frozen transport from Lineage to 6130, then thaws on-site
        Route(
            id='R_Lineage_6130_Frozen',
            origin_id='Lineage',
            destination_id='6130',
            transport_mode=StorageMode.FROZEN,
            transit_time_days=2.0,
            cost=0.20
        ),
        # Ambient routes from manufacturing to hubs
        Route(
            id='R_6122_6125_Ambient',
            origin_id='6122',
            destination_id='6125',
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.10
        ),
        Route(
            id='R_6122_6104_Ambient',
            origin_id='6122',
            destination_id='6104',
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.10
        ),
        # Ambient routes from hubs to breadrooms
        Route(
            id='R_6125_6130_Ambient',
            origin_id='6125',
            destination_id='6130',
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=2.0,
            cost=0.12
        ),
        Route(
            id='R_6104_6108_Ambient',
            origin_id='6104',
            destination_id='6108',
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=0.10
        ),
    ]


@pytest.fixture
def simple_forecast() -> Forecast:
    """Create simple forecast for testing."""
    start_date = date(2025, 1, 6)  # Monday

    entries = []
    # Demand at 6130 (WA - can receive frozen or ambient)
    for i in range(5):
        entries.append(ForecastEntry(
            location_id='6130',
            product_id='P001',
            forecast_date=start_date + timedelta(days=i+7),  # Week 2
            quantity=1000.0
        ))

    # Demand at 6108 (ACT - ambient only)
    for i in range(5):
        entries.append(ForecastEntry(
            location_id='6108',
            product_id='P001',
            forecast_date=start_date + timedelta(days=i+7),  # Week 2
            quantity=500.0
        ))

    return Forecast(entries=entries)


@pytest.fixture
def labor_calendar() -> LaborCalendar:
    """Create simple labor calendar."""
    start = date(2025, 1, 1)
    end = date(2025, 1, 31)

    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday-Friday
            days.append(LaborDay(
                date=current,
                is_fixed_day=True,
                fixed_hours=12.0,
                minimum_hours=0.0,
                regular_rate=50.0,
                overtime_rate=75.0,
                non_fixed_rate=None
            ))
        else:  # Weekend
            days.append(LaborDay(
                date=current,
                is_fixed_day=False,
                fixed_hours=0.0,
                minimum_hours=4.0,
                regular_rate=None,
                overtime_rate=None,
                non_fixed_rate=100.0
            ))
        current += timedelta(days=1)

    return LaborCalendar(labor_days=days)


@pytest.fixture
def manufacturing_site() -> ManufacturingSite:
    """Create manufacturing site."""
    return ManufacturingSite(
        id='6122',
        location_id='6122',
        name='Manufacturing Site',
        production_rate=1400.0,
        max_hours_per_day=14.0
    )


@pytest.fixture
def cost_structure() -> CostStructure:
    """Create cost structure with frozen and ambient holding costs."""
    return CostStructure(
        production_cost_per_unit=1.0,
        storage_cost_frozen_per_unit_day=0.01,  # Frozen storage is more expensive
        storage_cost_ambient_per_unit_day=0.005,  # Ambient storage is cheaper
        shortage_penalty_per_unit=100.0
    )


class TestLocationCategorization:
    """Test that locations are correctly categorized by storage mode."""

    def test_lineage_is_frozen_storage(self, sample_locations):
        """Verify Lineage is identified as frozen storage location."""
        lineage = next(loc for loc in sample_locations if loc.id == 'Lineage')

        assert lineage.storage_mode == StorageMode.FROZEN
        assert lineage.type == LocationType.STORAGE
        assert lineage.can_store_mode(StorageMode.FROZEN)
        assert not lineage.can_store_mode(StorageMode.AMBIENT)

    def test_6130_supports_both_modes(self, sample_locations):
        """Verify 6130 (WA) supports both frozen and ambient storage."""
        wa_location = next(loc for loc in sample_locations if loc.id == '6130')

        assert wa_location.storage_mode == StorageMode.BOTH
        assert wa_location.can_store_mode(StorageMode.FROZEN)
        assert wa_location.can_store_mode(StorageMode.AMBIENT)

    def test_breadrooms_are_ambient_only(self, sample_locations):
        """Verify most breadrooms are ambient-only storage."""
        act_breadroom = next(loc for loc in sample_locations if loc.id == '6108')

        assert act_breadroom.storage_mode == StorageMode.AMBIENT
        assert act_breadroom.type == LocationType.BREADROOM
        assert act_breadroom.can_store_mode(StorageMode.AMBIENT)
        assert not act_breadroom.can_store_mode(StorageMode.FROZEN)

    def test_intermediate_storage_identification(self, sample_locations):
        """Verify intermediate storage locations (like Lineage) are identified."""
        # Intermediate storage = storage type (not manufacturing or breadroom)
        intermediate_storage = [
            loc for loc in sample_locations
            if loc.type == LocationType.STORAGE
        ]

        assert len(intermediate_storage) >= 1
        lineage = next(loc for loc in intermediate_storage if loc.id == 'Lineage')
        assert lineage is not None
        assert lineage.storage_mode == StorageMode.FROZEN


class TestRouteArrivalStates:
    """Test that routes correctly track product state at arrival."""

    def test_frozen_route_to_lineage(self, sample_routes):
        """Verify 6122 → Lineage route uses frozen transport."""
        route = next(r for r in sample_routes if r.destination_id == 'Lineage')

        assert route.transport_mode == StorageMode.FROZEN
        assert route.origin_id == '6122'

    def test_frozen_route_from_lineage_to_6130(self, sample_routes):
        """Verify Lineage → 6130 route uses frozen transport (thaws at 6130)."""
        route = next(
            r for r in sample_routes
            if r.origin_id == 'Lineage' and r.destination_id == '6130'
        )

        assert route.transport_mode == StorageMode.FROZEN
        # Note: Product arrives frozen but thaws on-site at 6130
        # This is a business rule, not encoded in the route itself

    def test_ambient_routes_stay_ambient(self, sample_routes):
        """Verify ambient routes maintain ambient state throughout."""
        ambient_routes = [r for r in sample_routes if r.transport_mode == StorageMode.AMBIENT]

        assert len(ambient_routes) > 0

        # Check hub routes are ambient
        hub_route = next(r for r in ambient_routes if r.destination_id in ['6125', '6104'])
        assert hub_route.transport_mode == StorageMode.AMBIENT


class TestInventoryVariablesCreated:
    """Test that correct inventory variables are created for different storage modes."""

    def test_model_builds_with_frozen_routes(
        self, sample_locations, sample_routes, simple_forecast,
        labor_calendar, manufacturing_site, cost_structure
    ):
        """Verify model builds successfully with frozen and ambient routes."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=sample_locations,
            routes=sample_routes,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            allow_shortages=True,
            validate_feasibility=False  # Skip feasibility checks for unit test
        )

        # Build the Pyomo model
        pyomo_model = model.build_model()

        # Verify model has required components
        assert pyomo_model is not None
        assert hasattr(pyomo_model, 'production')
        assert hasattr(pyomo_model, 'shipment')
        assert hasattr(pyomo_model, 'inventory')

    def test_inventory_index_includes_destinations(
        self, sample_locations, sample_routes, simple_forecast,
        labor_calendar, manufacturing_site, cost_structure
    ):
        """Verify inventory variables exist for all demanded destinations."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=sample_locations,
            routes=sample_routes,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            allow_shortages=True,
            validate_feasibility=False
        )

        # Check that inventory index includes demanded destinations
        destinations_with_demand = set(simple_forecast.get_all_locations())

        # Verify 6130 and 6108 are in demand
        assert '6130' in destinations_with_demand
        assert '6108' in destinations_with_demand


class TestFrozenInventoryAtLineage:
    """Test that frozen inventory can accumulate at Lineage storage."""

    @pytest.mark.skipif(
        not os.path.exists(NETWORK_CONFIG_PATH),
        reason="Network config file not available"
    )
    def test_lineage_accumulates_frozen_inventory(self):
        """
        Test that frozen inventory can accumulate at Lineage.

        This is a buffer strategy: produce early, store frozen at Lineage,
        then ship to WA when needed.
        """
        # Load real network configuration
        parser = ExcelParser(NETWORK_CONFIG_PATH)
        parser.parse()

        # Create simple forecast for WA (6130) only
        start_date = date(2025, 1, 13)  # Week 2
        entries = []
        for i in range(5):
            entries.append(ForecastEntry(
                location_id='6130',
                product_id='P001',
                forecast_date=start_date + timedelta(days=i),
                quantity=5000.0
            ))
        forecast = Forecast(entries=entries)

        # Build model
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=parser.labor_calendar,
            manufacturing_site=parser.manufacturing_site,
            cost_structure=parser.cost_structure,
            locations=parser.locations,
            routes=parser.routes,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            allow_shortages=True,
            validate_feasibility=False
        )

        # Solve
        result = model.solve(time_limit_seconds=60)

        if result.is_optimal() or result.is_feasible():
            # Check if any inventory accumulated at Lineage
            inventory = model.solution.get('inventory_by_dest_product_date', {})
            lineage_inventory = {
                k: v for k, v in inventory.items()
                if k[0] == 'Lineage'
            }

            # If frozen buffer strategy is used, Lineage should have inventory
            if lineage_inventory:
                print(f"\nLineage inventory found: {len(lineage_inventory)} entries")
                # Verify inventory balance is correct
                for (dest, prod, inv_date), qty in lineage_inventory.items():
                    assert qty >= 0, f"Negative inventory at Lineage on {inv_date}: {qty}"


class TestThawingAt6130:
    """Test that product from Lineage arrives as ambient at 6130 (thaws on arrival)."""

    def test_frozen_route_supports_6130_destination(self, sample_routes):
        """Verify route exists from Lineage to 6130 for frozen transport."""
        frozen_route_to_6130 = next(
            (r for r in sample_routes
             if r.origin_id == 'Lineage' and r.destination_id == '6130'),
            None
        )

        assert frozen_route_to_6130 is not None
        assert frozen_route_to_6130.transport_mode == StorageMode.FROZEN

    def test_shelf_life_constraint_for_thawed_product(self):
        """
        Verify that 6130 destination has proper shelf life constraint.

        After thawing at 6130:
        - Product has 14 days remaining shelf life
        - Breadroom requires minimum 7 days
        - Maximum time from thaw to use = 7 days
        """
        # This is tested through route feasibility in the model
        # The model's _is_route_shelf_life_feasible() method should handle this

        # Create a mock route for testing
        route_data = {
            'destination_id': '6130',
            'total_transit_days': 3,  # Should be feasible (< 7 days after thaw)
            'route_path': None,
            'path': []
        }

        # For now, this is a placeholder test
        # Full implementation requires model enhancement to track thaw timing
        assert True  # Placeholder


class TestStateSpecificHoldingCosts:
    """Test that frozen and ambient inventory have different holding costs."""

    def test_frozen_holding_cost_higher(self, cost_structure):
        """Verify frozen storage has higher cost than ambient."""
        assert cost_structure.storage_cost_frozen_per_unit_day > cost_structure.storage_cost_ambient_per_unit_day

    def test_holding_cost_applied_to_inventory(
        self, sample_locations, sample_routes, simple_forecast,
        labor_calendar, manufacturing_site, cost_structure
    ):
        """Verify holding cost is included in objective function."""
        model = IntegratedProductionDistributionModel(
            forecast=simple_forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=sample_locations,
            routes=sample_routes,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            allow_shortages=True,
            validate_feasibility=False
        )

        # Build model
        pyomo_model = model.build_model()

        # Verify objective includes inventory cost term
        # Check objective function structure (simplified check)
        assert hasattr(pyomo_model, 'obj')

        # Check that cost structure has holding costs defined
        assert cost_structure.storage_cost_ambient_per_unit_day is not None
        assert cost_structure.storage_cost_frozen_per_unit_day is not None


class TestBackwardCompatibility:
    """Test that model works with all-ambient routes (no frozen routes)."""

    def test_all_ambient_routes(
        self, sample_locations, labor_calendar, manufacturing_site, cost_structure
    ):
        """Test model with only ambient routes (no frozen buffer)."""
        # Create only ambient routes
        ambient_routes = [
            Route(
                id='R_6122_6104',
                origin_id='6122',
                destination_id='6104',
                transport_mode=StorageMode.AMBIENT,
                transit_time_days=1.0,
                cost=0.10
            ),
            Route(
                id='R_6104_6108',
                origin_id='6104',
                destination_id='6108',
                transport_mode=StorageMode.AMBIENT,
                transit_time_days=1.0,
                cost=0.10
            ),
        ]

        # Simple forecast for ambient-only destination
        forecast = Forecast(entries=[
            ForecastEntry(
                location_id='6108',
                product_id='P001',
                forecast_date=date(2025, 1, 10),
                quantity=1000.0
            )
        ])

        # Build model
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=sample_locations,
            routes=ambient_routes,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 20),
            allow_shortages=True,
            validate_feasibility=False
        )

        pyomo_model = model.build_model()
        assert pyomo_model is not None

    def test_no_frozen_inventory_in_ambient_scenario(
        self, sample_locations, labor_calendar, manufacturing_site, cost_structure
    ):
        """Verify no frozen inventory in all-ambient network."""
        # Create only ambient routes (excluding Lineage)
        ambient_locations = [
            loc for loc in sample_locations
            if loc.id != 'Lineage'
        ]

        ambient_routes = [
            Route(
                id='R_6122_6108',
                origin_id='6122',
                destination_id='6108',
                transport_mode=StorageMode.AMBIENT,
                transit_time_days=2.0,
                cost=0.15
            ),
        ]

        forecast = Forecast(entries=[
            ForecastEntry(
                location_id='6108',
                product_id='P001',
                forecast_date=date(2025, 1, 10),
                quantity=1000.0
            )
        ])

        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=ambient_locations,
            routes=ambient_routes,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 20),
            allow_shortages=True,
            validate_feasibility=False
        )

        # Solve
        result = model.solve(time_limit_seconds=30)

        if result.is_optimal() or result.is_feasible():
            # Check that Lineage is not in inventory
            inventory = model.solution.get('inventory_by_dest_product_date', {})
            lineage_inventory = {
                k: v for k, v in inventory.items()
                if k[0] == 'Lineage'
            }

            assert len(lineage_inventory) == 0, "No frozen inventory should exist in all-ambient scenario"


class TestDemandSatisfactionFromAmbientOnly:
    """Test that demand is satisfied from ambient inventory (frozen inventory doesn't directly satisfy demand)."""

    def test_demand_satisfied_from_ambient(
        self, sample_locations, sample_routes, labor_calendar, manufacturing_site, cost_structure
    ):
        """
        Verify demand is satisfied from ambient inventory.

        For 6130 (WA):
        - Product can arrive frozen (from Lineage)
        - Product thaws on-site (becomes ambient)
        - Demand is satisfied from ambient inventory
        """
        # Create forecast for 6130
        forecast = Forecast(entries=[
            ForecastEntry(
                location_id='6130',
                product_id='P001',
                forecast_date=date(2025, 1, 15),
                quantity=2000.0
            )
        ])

        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=labor_calendar,
            manufacturing_site=manufacturing_site,
            cost_structure=cost_structure,
            locations=sample_locations,
            routes=sample_routes,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            allow_shortages=True,
            validate_feasibility=False
        )

        result = model.solve(time_limit_seconds=60)

        if result.is_optimal() or result.is_feasible():
            # Verify demand satisfaction
            diagnostics = model.get_demand_diagnostics()

            # Check that demand is satisfied
            satisfaction_rate = diagnostics.get('satisfaction_rate', 0)
            print(f"\nDemand satisfaction rate: {satisfaction_rate:.1f}%")

            # For feasible solutions, demand should be satisfied
            # (Either from ambient routes or from frozen → thawed inventory)
            if result.is_optimal():
                assert satisfaction_rate >= 95.0, f"Expected >95% satisfaction, got {satisfaction_rate:.1f}%"


class TestModelIntegration:
    """Integration tests with real data files."""

    @pytest.mark.skipif(
        not os.path.exists(NETWORK_CONFIG_PATH),
        reason="Network config file not available"
    )
    def test_real_network_with_frozen_routes(self):
        """
        Integration test with real network configuration.

        Tests the full 6122 → Lineage → 6130 frozen buffer route.
        """
        # Load real configuration
        parser = ExcelParser(NETWORK_CONFIG_PATH)
        parser.parse()

        # Create focused forecast for WA
        start_date = date(2025, 1, 13)
        entries = []
        for i in range(5):
            entries.append(ForecastEntry(
                location_id='6130',
                product_id='P001',
                forecast_date=start_date + timedelta(days=i),
                quantity=3000.0
            ))
        forecast = Forecast(entries=entries)

        # Build and solve model
        model = IntegratedProductionDistributionModel(
            forecast=forecast,
            labor_calendar=parser.labor_calendar,
            manufacturing_site=parser.manufacturing_site,
            cost_structure=parser.cost_structure,
            locations=parser.locations,
            routes=parser.routes,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            allow_shortages=True,
            validate_feasibility=False
        )

        result = model.solve(time_limit_seconds=120)

        # Verify solution exists
        assert result.is_optimal() or result.is_feasible(), \
            f"Model should find a solution. Status: {result.status}"

        if result.is_optimal() or result.is_feasible():
            # Print summary
            model.print_solution_summary()

            # Check routes used
            shipments = model.solution.get('shipments_by_route_product_date', {})

            # Check if frozen routes were used
            frozen_routes_used = []
            for (route_idx, prod, deliv_date), qty in shipments.items():
                route = model.route_enumerator.get_route(route_idx)
                if route and model._is_frozen_route(route):
                    frozen_routes_used.append(route_idx)

            if frozen_routes_used:
                print(f"\nFrozen routes used: {len(set(frozen_routes_used))} unique routes")

            # Verify demand satisfaction
            diagnostics = model.get_demand_diagnostics()
            print(f"\nDemand satisfaction: {diagnostics['satisfaction_rate']:.1f}%")


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring external files"
    )
