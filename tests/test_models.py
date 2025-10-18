"""Tests for data models."""

import pytest
from datetime import date

from src.models import (
    Location,
    LocationType,
    StorageMode,
    Route,
    Product,
    ProductState,
    Forecast,
    ForecastEntry,
    CostStructure,
)


class TestLocation:
    """Tests for Location model."""

    def test_create_location(self):
        """Test creating a basic location."""
        location = Location(
            id="6122",
            name="Manufacturing Site",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH,
        )
        assert location.id == "6122"
        assert location.name == "Manufacturing Site"
        assert location.type == LocationType.MANUFACTURING

    def test_can_store_mode_both(self):
        """Test location with BOTH mode can store any mode."""
        location = Location(
            id="1",
            name="Warehouse",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.BOTH,
        )
        assert location.can_store_mode(StorageMode.FROZEN)
        assert location.can_store_mode(StorageMode.AMBIENT)

    def test_can_store_mode_specific(self):
        """Test location with specific mode."""
        location = Location(
            id="2",
            name="Frozen Storage",
            type=LocationType.STORAGE,
            storage_mode=StorageMode.FROZEN,
        )
        assert location.can_store_mode(StorageMode.FROZEN)
        assert not location.can_store_mode(StorageMode.AMBIENT)


class TestRoute:
    """Tests for Route model."""

    def test_create_route(self):
        """Test creating a basic route."""
        route = Route(
            id="R1",
            origin_id="6122",
            destination_id="BR1",
            transport_mode=StorageMode.FROZEN,
            transit_time_days=2.5,
        )
        assert route.id == "R1"
        assert route.origin_id == "6122"
        assert route.destination_id == "BR1"
        assert route.transit_time_days == 2.5

    def test_route_with_cost(self):
        """Test route with cost information."""
        route = Route(
            id="R2",
            origin_id="A",
            destination_id="B",
            transport_mode=StorageMode.AMBIENT,
            transit_time_days=1.0,
            cost=50.0,
            capacity=1000.0,
        )
        assert route.cost == 50.0
        assert route.capacity == 1000.0


class TestProduct:
    """Tests for Product model."""

    def test_create_product_with_defaults(self):
        """Test creating product with default shelf life values."""
        product = Product(
            id="P1",
            name="Gluten-Free Bread",
            sku="GFB-001",
        )
        assert product.ambient_shelf_life_days == 17.0
        assert product.frozen_shelf_life_days == 120.0
        assert product.thawed_shelf_life_days == 14.0
        assert product.min_acceptable_shelf_life_days == 7.0

    def test_get_shelf_life(self):
        """Test getting shelf life for different states."""
        product = Product(id="P1", name="Test", sku="T1")
        assert product.get_shelf_life(ProductState.AMBIENT) == 17.0
        assert product.get_shelf_life(ProductState.FROZEN) == 120.0
        assert product.get_shelf_life(ProductState.THAWED) == 14.0

    def test_is_acceptable(self):
        """Test checking if product is acceptable."""
        product = Product(id="P1", name="Test", sku="T1")
        assert product.is_acceptable(7.0)  # Exactly at threshold
        assert product.is_acceptable(10.0)  # Above threshold
        assert not product.is_acceptable(6.0)  # Below threshold
        assert not product.is_acceptable(0.0)  # Expired


class TestForecast:
    """Tests for Forecast and ForecastEntry models."""

    def test_create_forecast_entry(self):
        """Test creating a forecast entry."""
        entry = ForecastEntry(
            location_id="BR1",
            product_id="P1",
            forecast_date=date(2025, 10, 15),
            quantity=100.0,
            confidence=0.85,
        )
        assert entry.location_id == "BR1"
        assert entry.quantity == 100.0
        assert entry.confidence == 0.85

    def test_create_forecast(self):
        """Test creating a forecast with entries."""
        entries = [
            ForecastEntry(
                location_id="BR1",
                product_id="P1",
                forecast_date=date(2025, 10, 15),
                quantity=100.0,
            ),
            ForecastEntry(
                location_id="BR2",
                product_id="P1",
                forecast_date=date(2025, 10, 15),
                quantity=150.0,
            ),
        ]
        forecast = Forecast(name="Test Forecast", entries=entries)
        assert forecast.name == "Test Forecast"
        assert len(forecast.entries) == 2

    def test_get_demand(self):
        """Test getting demand for specific location, product, date."""
        entries = [
            ForecastEntry(
                location_id="BR1",
                product_id="P1",
                forecast_date=date(2025, 10, 15),
                quantity=100.0,
            ),
        ]
        forecast = Forecast(name="Test", entries=entries)

        # Should find the entry
        demand = forecast.get_demand("BR1", "P1", date(2025, 10, 15))
        assert demand == 100.0

        # Should return 0 for non-existent entry
        demand = forecast.get_demand("BR2", "P1", date(2025, 10, 15))
        assert demand == 0.0


class TestCostStructureFixedPalletCosts:
    """Tests for CostStructure.get_fixed_pallet_costs() with state-specific support."""

    def test_get_fixed_pallet_costs_state_specific(self):
        """
        Test get_fixed_pallet_costs() with both state-specific fields set.

        When both storage_cost_fixed_per_pallet_frozen and
        storage_cost_fixed_per_pallet_ambient are set, they should be returned
        as the (frozen, ambient) tuple.
        """
        costs = CostStructure(
            storage_cost_fixed_per_pallet_frozen=5.0,
            storage_cost_fixed_per_pallet_ambient=2.0
        )
        frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()

        assert frozen_fixed == 5.0, "Frozen fixed cost should be 5.0"
        assert ambient_fixed == 2.0, "Ambient fixed cost should be 2.0"

    def test_get_fixed_pallet_costs_legacy_only(self):
        """
        Test get_fixed_pallet_costs() with only legacy field set.

        When only storage_cost_fixed_per_pallet is set (legacy behavior),
        it should be applied to both frozen and ambient states.
        """
        costs = CostStructure(
            storage_cost_fixed_per_pallet=3.0
        )
        frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()

        assert frozen_fixed == 3.0, "Frozen fixed cost should be 3.0 (from legacy)"
        assert ambient_fixed == 3.0, "Ambient fixed cost should be 3.0 (from legacy)"

    def test_get_fixed_pallet_costs_defaults(self):
        """
        Test get_fixed_pallet_costs() with no fields set.

        When no fixed pallet cost fields are set, should return (0.0, 0.0).
        """
        costs = CostStructure()
        frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()

        assert frozen_fixed == 0.0, "Frozen fixed cost should default to 0.0"
        assert ambient_fixed == 0.0, "Ambient fixed cost should default to 0.0"

    def test_get_fixed_pallet_costs_mixed_frozen_only(self):
        """
        Test get_fixed_pallet_costs() with only frozen state-specific set.

        When only storage_cost_fixed_per_pallet_frozen is set, it should be
        used for frozen state, while ambient falls back to legacy field.
        """
        costs = CostStructure(
            storage_cost_fixed_per_pallet_frozen=5.0,
            storage_cost_fixed_per_pallet=3.0
        )
        frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()

        assert frozen_fixed == 5.0, "Frozen fixed cost should be 5.0 (state-specific)"
        assert ambient_fixed == 3.0, "Ambient fixed cost should be 3.0 (legacy fallback)"

    def test_get_fixed_pallet_costs_mixed_ambient_only(self):
        """
        Test get_fixed_pallet_costs() with only ambient state-specific set.

        When only storage_cost_fixed_per_pallet_ambient is set, it should be
        used for ambient state, while frozen falls back to legacy field.
        """
        costs = CostStructure(
            storage_cost_fixed_per_pallet_ambient=2.0,
            storage_cost_fixed_per_pallet=3.0
        )
        frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()

        assert frozen_fixed == 3.0, "Frozen fixed cost should be 3.0 (legacy fallback)"
        assert ambient_fixed == 2.0, "Ambient fixed cost should be 2.0 (state-specific)"

    def test_get_fixed_pallet_costs_state_specific_precedence(self):
        """
        Test get_fixed_pallet_costs() precedence: state-specific overrides legacy.

        When both state-specific and legacy fields are set, the state-specific
        fields should take precedence (legacy is ignored).
        """
        costs = CostStructure(
            storage_cost_fixed_per_pallet_frozen=5.0,
            storage_cost_fixed_per_pallet_ambient=2.0,
            storage_cost_fixed_per_pallet=3.0  # This should be ignored
        )
        frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()

        assert frozen_fixed == 5.0, "Frozen fixed cost should be 5.0 (state-specific wins)"
        assert ambient_fixed == 2.0, "Ambient fixed cost should be 2.0 (state-specific wins)"

    def test_get_fixed_pallet_costs_zero_values(self):
        """
        Test get_fixed_pallet_costs() with explicit zero values.

        Explicit zero values should be treated as valid configuration
        (not the same as None/unset).
        """
        costs = CostStructure(
            storage_cost_fixed_per_pallet_frozen=0.0,
            storage_cost_fixed_per_pallet_ambient=0.0
        )
        frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()

        assert frozen_fixed == 0.0, "Frozen fixed cost should be 0.0 (explicit)"
        assert ambient_fixed == 0.0, "Ambient fixed cost should be 0.0 (explicit)"

    def test_get_fixed_pallet_costs_mixed_with_zero(self):
        """
        Test get_fixed_pallet_costs() with one state zero, other state set.

        Zero is a valid cost value (different from None), so it should be used.
        """
        costs = CostStructure(
            storage_cost_fixed_per_pallet_frozen=5.0,
            storage_cost_fixed_per_pallet_ambient=0.0,  # Explicit zero
            storage_cost_fixed_per_pallet=3.0
        )
        frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()

        assert frozen_fixed == 5.0, "Frozen fixed cost should be 5.0"
        assert ambient_fixed == 0.0, "Ambient fixed cost should be 0.0 (explicit, not fallback)"
