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
