"""Pytest configuration and shared fixtures."""

import pytest
from datetime import date

from src.models import (
    Location,
    LocationType,
    StorageMode,
    Route,
    Product,
    Forecast,
    ForecastEntry,
)
from tests.fixtures.solver_mocks import create_mock_solver_config


@pytest.fixture
def manufacturing_location():
    """Fixture for manufacturing location."""
    return Location(
        id="6122",
        name="Manufacturing Site",
        type=LocationType.MANUFACTURING,
        storage_mode=StorageMode.BOTH,
    )


@pytest.fixture
def frozen_storage_location():
    """Fixture for frozen storage location."""
    return Location(
        id="FS1",
        name="Frozen Storage 1",
        type=LocationType.STORAGE,
        storage_mode=StorageMode.FROZEN,
    )


@pytest.fixture
def breadroom_location():
    """Fixture for breadroom location."""
    return Location(
        id="BR1",
        name="Breadroom 1",
        type=LocationType.BREADROOM,
        storage_mode=StorageMode.AMBIENT,
    )


@pytest.fixture
def frozen_route(manufacturing_location, frozen_storage_location):
    """Fixture for frozen transport route."""
    return Route(
        id="R1",
        origin_id=manufacturing_location.id,
        destination_id=frozen_storage_location.id,
        transport_mode=StorageMode.FROZEN,
        transit_time_days=2.0,
    )


@pytest.fixture
def ambient_route(frozen_storage_location, breadroom_location):
    """Fixture for ambient transport route."""
    return Route(
        id="R2",
        origin_id=frozen_storage_location.id,
        destination_id=breadroom_location.id,
        transport_mode=StorageMode.AMBIENT,
        transit_time_days=1.0,
    )


@pytest.fixture
def gf_bread_product():
    """Fixture for gluten-free bread product."""
    return Product(
        id="P1",
        name="Gluten-Free Bread",
        sku="GFB-001",
    )


@pytest.fixture
def sample_forecast():
    """Fixture for sample forecast."""
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
    return Forecast(name="Sample Forecast", entries=entries)


@pytest.fixture
def mock_solver_config():
    """
    Fixture for mock solver configuration.

    Provides a mock SolverConfig that bypasses actual solver installation
    and testing. Useful for optimization model tests that don't need
    actual solver execution.

    Returns:
        Mock SolverConfig object with create_solver() method
    """
    return create_mock_solver_config()
