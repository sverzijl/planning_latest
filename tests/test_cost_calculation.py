"""Tests for cost calculation module.

Tests all cost calculators:
- LaborCostCalculator
- ProductionCostCalculator
- TransportCostCalculator
- WasteCostCalculator
- CostCalculator (aggregator)
"""

import pytest
from datetime import date, timedelta
from typing import List

from src.models.cost_structure import CostStructure
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.forecast import Forecast, ForecastEntry
from src.models.shipment import Shipment
from src.models.product import Product
from src.network import RoutePath, RouteLeg
from src.production.scheduler import (
    ProductionSchedule,
    ProductionBatch,
    ProductionRequirement,
)
from src.costs import (
    LaborCostCalculator,
    ProductionCostCalculator,
    TransportCostCalculator,
    WasteCostCalculator,
    CostCalculator,
)


# Test fixtures

@pytest.fixture
def cost_structure():
    """Standard cost structure for testing."""
    return CostStructure(
        production_cost_per_unit=0.80,
        shortage_penalty_per_unit=1.50,
        waste_cost_multiplier=1.5,
    )


@pytest.fixture
def labor_calendar():
    """Labor calendar with weekday and weekend days."""
    days = [
        # Monday Jan 6, 2025 - weekday (fixed labor day)
        LaborDay(
            date=date(2025, 1, 6),
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0,
            non_fixed_rate=100.0,
            minimum_hours=0.0,
            is_fixed_day=True,
        ),
        # Tuesday Jan 7 - weekday (fixed labor day)
        LaborDay(
            date=date(2025, 1, 7),
            fixed_hours=12.0,
            regular_rate=50.0,
            overtime_rate=75.0,
            non_fixed_rate=100.0,
            minimum_hours=0.0,
            is_fixed_day=True,
        ),
        # Saturday Jan 11 - weekend (non-fixed labor day)
        LaborDay(
            date=date(2025, 1, 11),
            fixed_hours=0.0,
            regular_rate=50.0,
            overtime_rate=75.0,
            non_fixed_rate=100.0,
            minimum_hours=4.0,
            is_fixed_day=False,
        ),
    ]
    return LaborCalendar(name="Test Calendar", days=days)


@pytest.fixture
def production_schedule():
    """Production schedule with 2 batches."""
    batches = [
        ProductionBatch(
            id="BATCH-001",
            product_id="PROD1",
            manufacturing_site_id="6122",
            quantity=5600.0,  # 4 hours at 1400 units/hour
            production_date=date(2025, 1, 6),  # Monday
        ),
        ProductionBatch(
            id="BATCH-002",
            product_id="PROD2",
            manufacturing_site_id="6122",
            quantity=16800.0,  # 12 hours at 1400 units/hour
            production_date=date(2025, 1, 7),  # Tuesday
        ),
    ]
    requirements = [
        ProductionRequirement(
            product_id="PROD1",
            production_date=date(2025, 1, 6),
            total_quantity=5600.0,
            demand_details=[],
        ),
        ProductionRequirement(
            product_id="PROD2",
            production_date=date(2025, 1, 7),
            total_quantity=16800.0,
            demand_details=[],
        ),
    ]
    return ProductionSchedule(
        manufacturing_site_id="6122",
        production_batches=batches,
        requirements=requirements,
        total_units=22400.0,
        schedule_start_date=date(2025, 1, 6),
        schedule_end_date=date(2025, 1, 7),
        daily_totals={},
        daily_labor_hours={},
        infeasibilities=[],
        total_labor_hours=0.0,
    )


def create_simple_route(origin: str, destination: str, cost_per_unit: float = 0.50):
    """Helper to create a simple route for testing."""
    return RoutePath(
        path=[origin, destination],
        total_transit_days=2,
        total_cost=cost_per_unit,
        transport_modes=["ambient"],
        route_legs=[
            RouteLeg(
                from_location_id=origin,
                to_location_id=destination,
                transit_days=2,
                transport_mode="ambient",
            )
        ],
        intermediate_stops=[],
    )


@pytest.fixture
def shipments():
    """List of shipments for testing."""
    route_6103 = create_simple_route("6122", "6103", cost_per_unit=0.50)
    route_6101 = create_simple_route("6122", "6101", cost_per_unit=0.60)

    return [
        Shipment(
            id="SHIP-001",
            batch_id="BATCH-001",
            product_id="PROD1",
            quantity=3000.0,
            origin_id="6122",
            destination_id="6103",
            delivery_date=date(2025, 1, 10),
            route=route_6103,
            production_date=date(2025, 1, 6),
        ),
        Shipment(
            id="SHIP-002",
            batch_id="BATCH-001",
            product_id="PROD1",
            quantity=2600.0,
            origin_id="6122",
            destination_id="6101",
            delivery_date=date(2025, 1, 10),
            route=route_6101,
            production_date=date(2025, 1, 6),
        ),
    ]


@pytest.fixture
def forecast():
    """Demand forecast for testing."""
    entries = [
        ForecastEntry(
            location_id="6103",
            product_id="PROD1",
            forecast_date=date(2025, 1, 10),
            quantity=3000.0,
        ),
        ForecastEntry(
            location_id="6101",
            product_id="PROD1",
            forecast_date=date(2025, 1, 10),
            quantity=3000.0,  # Demand higher than shipped (2600)
        ),
    ]
    return Forecast(name="Test Forecast", entries=entries)


# LaborCostCalculator Tests

class TestLaborCostCalculator:
    """Tests for LaborCostCalculator."""

    def test_fixed_hours_only(self, cost_structure, labor_calendar, production_schedule):
        """Test labor cost with only fixed hours (no overtime)."""
        # Modify schedule to use only 4 hours (within fixed 12h)
        production_schedule.production_batches[0].quantity = 5600.0  # 4 hours
        production_schedule.production_batches[1].quantity = 5600.0  # 4 hours

        calculator = LaborCostCalculator(labor_calendar)
        breakdown = calculator.calculate_labor_cost(production_schedule)

        # 4 hours on Monday + 4 hours on Tuesday = 8 fixed hours
        assert breakdown.total_hours == 8.0
        assert breakdown.fixed_hours == 8.0
        assert breakdown.overtime_hours == 0.0
        assert breakdown.non_fixed_hours == 0.0

        # Cost: 8 hours × $50/hour = $400
        assert breakdown.fixed_hours_cost == 400.0
        assert breakdown.overtime_cost == 0.0
        assert breakdown.non_fixed_labor_cost == 0.0
        assert breakdown.total_cost == 400.0

    def test_fixed_hours_plus_overtime(self, cost_structure, labor_calendar):
        """Test labor cost with fixed hours + overtime."""
        # 13 hours on Monday: 12 fixed + 1 overtime
        batches = [
            ProductionBatch(
                id="BATCH-001",
                product_id="PROD1",
                manufacturing_site_id="6122",
                quantity=18200.0,  # 13 hours at 1400 units/hour
                production_date=date(2025, 1, 6),  # Monday
            )
        ]
        requirements = [
            ProductionRequirement(
                product_id="PROD1",
                production_date=date(2025, 1, 6),
                total_quantity=18200.0,
                demand_details=[],
            )
        ]
        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            requirements=requirements,
            total_units=18200.0,
            schedule_start_date=date(2025, 1, 6),
            schedule_end_date=date(2025, 1, 6),
            daily_totals={},
            daily_labor_hours={},
            infeasibilities=[],
            total_labor_hours=0.0,
        )

        calculator = LaborCostCalculator(labor_calendar)
        breakdown = calculator.calculate_labor_cost(schedule)

        assert breakdown.total_hours == 13.0
        assert breakdown.fixed_hours == 12.0
        assert breakdown.overtime_hours == 1.0

        # Cost: 12h × $50 + 1h × $75 = $600 + $75 = $675
        assert breakdown.fixed_hours_cost == 600.0
        assert breakdown.overtime_cost == 75.0
        assert breakdown.total_cost == 675.0

    def test_non_fixed_labor_day(self, cost_structure, labor_calendar):
        """Test labor cost on non-fixed labor day (weekend)."""
        # 3 hours on Saturday (minimum 4h payment)
        batches = [
            ProductionBatch(
                id="BATCH-001",
                product_id="PROD1",
                manufacturing_site_id="6122",
                quantity=4200.0,  # 3 hours at 1400 units/hour
                production_date=date(2025, 1, 11),  # Saturday
            )
        ]
        requirements = [
            ProductionRequirement(
                product_id="PROD1",
                production_date=date(2025, 1, 11),
                total_quantity=4200.0,
                demand_details=[],
            )
        ]
        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            requirements=requirements,
            total_units=4200.0,
            schedule_start_date=date(2025, 1, 11),
            schedule_end_date=date(2025, 1, 11),
            daily_totals={},
            daily_labor_hours={},
            infeasibilities=[],
            total_labor_hours=0.0,
        )

        calculator = LaborCostCalculator(labor_calendar)
        breakdown = calculator.calculate_labor_cost(schedule)

        # 3 hours needed, but pay minimum 4 hours
        assert breakdown.total_hours == 4.0
        assert breakdown.fixed_hours == 0.0
        assert breakdown.overtime_hours == 0.0
        assert breakdown.non_fixed_hours == 4.0

        # Cost: 4h × $100 = $400
        assert breakdown.non_fixed_labor_cost == 400.0
        assert breakdown.total_cost == 400.0

    def test_daily_labor_cost(self, cost_structure, labor_calendar):
        """Test single-day labor cost calculation."""
        calculator = LaborCostCalculator(labor_calendar)

        # Monday, 13 hours (12 fixed + 1 OT)
        result = calculator.calculate_daily_labor_cost(
            prod_date=date(2025, 1, 6),
            quantity=18200.0
        )

        assert result["hours_needed"] == 13.0
        assert result["hours_paid"] == 13.0
        assert result["fixed_cost"] == 600.0
        assert result["overtime_cost"] == 75.0
        assert result["total_cost"] == 675.0


# ProductionCostCalculator Tests

class TestProductionCostCalculator:
    """Tests for ProductionCostCalculator."""

    def test_production_cost_calculation(self, cost_structure, production_schedule):
        """Test production cost calculation."""
        calculator = ProductionCostCalculator(cost_structure)
        breakdown = calculator.calculate_production_cost(production_schedule)

        # 5600 + 16800 = 22400 units
        assert breakdown.total_units_produced == 22400.0

        # Cost: 22400 × $0.80 = $17,920
        assert breakdown.total_cost == 17920.0
        assert breakdown.average_cost_per_unit == 0.80

    def test_cost_by_product(self, cost_structure, production_schedule):
        """Test cost breakdown by product."""
        calculator = ProductionCostCalculator(cost_structure)
        breakdown = calculator.calculate_production_cost(production_schedule)

        # PROD1: 5600 × $0.80 = $4,480
        assert breakdown.cost_by_product["PROD1"] == 4480.0

        # PROD2: 16800 × $0.80 = $13,440
        assert breakdown.cost_by_product["PROD2"] == 13440.0

    def test_batch_cost(self, cost_structure, production_schedule):
        """Test single batch cost calculation."""
        calculator = ProductionCostCalculator(cost_structure)

        batch = production_schedule.production_batches[0]
        cost = calculator.calculate_batch_cost(batch)

        # 5600 × $0.80 = $4,480
        assert cost == 4480.0


# TransportCostCalculator Tests

class TestTransportCostCalculator:
    """Tests for TransportCostCalculator."""

    def test_transport_cost_calculation(self, shipments):
        """Test transport cost calculation."""
        calculator = TransportCostCalculator()
        breakdown = calculator.calculate_transport_cost(shipments)

        # SHIP-001: 3000 × $0.50 = $1,500
        # SHIP-002: 2600 × $0.60 = $1,560
        # Total: $3,060
        assert breakdown.total_cost == 3060.0
        assert breakdown.total_units_shipped == 5600.0
        assert breakdown.average_cost_per_unit == pytest.approx(0.5464, rel=1e-4)

    def test_cost_by_route(self, shipments):
        """Test cost breakdown by route."""
        calculator = TransportCostCalculator()
        breakdown = calculator.calculate_transport_cost(shipments)

        # Route 6122 → 6103: $1,500
        assert breakdown.cost_by_route["6122 → 6103"] == 1500.0

        # Route 6122 → 6101: $1,560
        assert breakdown.cost_by_route["6122 → 6101"] == 1560.0

    def test_shipment_cost(self, shipments):
        """Test single shipment cost calculation."""
        calculator = TransportCostCalculator()

        cost = calculator.calculate_shipment_cost(shipments[0])
        # 3000 × $0.50 = $1,500
        assert cost == 1500.0


# WasteCostCalculator Tests

class TestWasteCostCalculator:
    """Tests for WasteCostCalculator."""

    def test_unmet_demand_cost(self, cost_structure, forecast, shipments):
        """Test unmet demand cost calculation."""
        calculator = WasteCostCalculator(cost_structure)
        breakdown = calculator.calculate_waste_cost(
            forecast=forecast,
            shipments=shipments
        )

        # Location 6101: demand 3000, shipped 2600, unmet 400
        # Cost: 400 × $1.50 = $600
        assert breakdown.unmet_demand_units == 400.0
        assert breakdown.unmet_demand_cost == 600.0
        assert breakdown.total_cost == 600.0

    def test_expired_units_cost(self, cost_structure, forecast, shipments):
        """Test expired inventory cost calculation."""
        calculator = WasteCostCalculator(cost_structure)

        # 100 units expired at location 6103
        expired_units = {"6103": 100.0}

        breakdown = calculator.calculate_waste_cost(
            forecast=forecast,
            shipments=shipments,
            expired_units=expired_units
        )

        # Expired cost: 100 × ($0.80 production × 1.5 multiplier) = $120
        assert breakdown.expired_units == 100.0
        assert breakdown.expired_cost == pytest.approx(120.0, rel=1e-9)

        # Total: $120 expired + $600 unmet = $720
        assert breakdown.total_cost == pytest.approx(720.0, rel=1e-9)

    def test_waste_by_location(self, cost_structure, forecast, shipments):
        """Test waste breakdown by location."""
        calculator = WasteCostCalculator(cost_structure)

        expired_units = {"6103": 100.0}
        breakdown = calculator.calculate_waste_cost(
            forecast=forecast,
            shipments=shipments,
            expired_units=expired_units
        )

        # 6103: $120 expired
        assert breakdown.waste_by_location["6103"] == pytest.approx(120.0, rel=1e-9)

        # 6101: $600 unmet demand
        assert breakdown.waste_by_location["6101"] == 600.0


# CostCalculator Tests

class TestCostCalculator:
    """Tests for CostCalculator (aggregator)."""

    def test_total_cost_calculation(
        self,
        cost_structure,
        labor_calendar,
        production_schedule,
        shipments,
        forecast
    ):
        """Test total cost to serve calculation."""
        calculator = CostCalculator(cost_structure, labor_calendar)

        total = calculator.calculate_total_cost(
            production_schedule=production_schedule,
            shipments=shipments,
            forecast=forecast
        )

        # Labor: $200 + $600 = $800 (4h + 12h fixed at $50/h)
        # Production: 22400 × $0.80 = $17,920
        # Transport: $3,060
        # Waste: $600 (unmet demand)
        # Total: $22,380

        assert total.labor.total_cost == 800.0
        assert total.production.total_cost == 17920.0
        assert total.transport.total_cost == 3060.0
        assert total.waste.total_cost == 600.0
        assert total.total_cost == 22380.0

    def test_cost_per_unit_delivered(
        self,
        cost_structure,
        labor_calendar,
        production_schedule,
        shipments,
        forecast
    ):
        """Test cost per unit delivered calculation."""
        calculator = CostCalculator(cost_structure, labor_calendar)

        total = calculator.calculate_total_cost(
            production_schedule=production_schedule,
            shipments=shipments,
            forecast=forecast
        )

        # Total cost: $22,380
        # Units delivered: 5,600
        # Cost per unit: ~$3.996
        expected = 22380.0 / 5600.0
        assert total.cost_per_unit_delivered == pytest.approx(expected, rel=1e-4)

    def test_cost_proportions(
        self,
        cost_structure,
        labor_calendar,
        production_schedule,
        shipments,
        forecast
    ):
        """Test cost component proportions."""
        calculator = CostCalculator(cost_structure, labor_calendar)

        total = calculator.calculate_total_cost(
            production_schedule=production_schedule,
            shipments=shipments,
            forecast=forecast
        )

        proportions = total.get_cost_proportions()

        # Labor: $800 / $22,380 ≈ 3.6%
        assert proportions["labor"] == pytest.approx(800.0 / 22380.0, rel=1e-4)

        # Production: $17,920 / $22,380 ≈ 80.1%
        assert proportions["production"] == pytest.approx(17920.0 / 22380.0, rel=1e-4)

        # Transport: $3,060 / $22,380 ≈ 13.7%
        assert proportions["transport"] == pytest.approx(3060.0 / 22380.0, rel=1e-4)

        # Waste: $600 / $22,380 ≈ 2.7%
        assert proportions["waste"] == pytest.approx(600.0 / 22380.0, rel=1e-4)

        # Sum to 1.0
        assert sum(proportions.values()) == pytest.approx(1.0, rel=1e-10)

    def test_individual_cost_methods(
        self,
        cost_structure,
        labor_calendar,
        production_schedule,
        shipments,
        forecast
    ):
        """Test individual cost calculation methods."""
        calculator = CostCalculator(cost_structure, labor_calendar)

        labor = calculator.calculate_labor_cost(production_schedule)
        assert labor.total_cost == 800.0

        production = calculator.calculate_production_cost(production_schedule)
        assert production.total_cost == 17920.0

        transport = calculator.calculate_transport_cost(shipments)
        assert transport.total_cost == 3060.0

        waste = calculator.calculate_waste_cost(forecast, shipments)
        assert waste.total_cost == 600.0
