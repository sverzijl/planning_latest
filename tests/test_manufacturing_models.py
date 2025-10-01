"""Tests for manufacturing-related data models."""

import pytest
from datetime import date, time, datetime

from src.models import (
    ManufacturingSite,
    LocationType,
    StorageMode,
    TruckSchedule,
    DepartureType,
    LaborCalendar,
    LaborDay,
    ProductionBatch,
    ProductState,
    CostStructure,
)


class TestManufacturingSite:
    """Tests for ManufacturingSite model."""

    def test_create_manufacturing_site(self):
        """Test creating a manufacturing site."""
        site = ManufacturingSite(
            id="6122",
            name="Main Manufacturing",
            type=LocationType.MANUFACTURING,
            storage_mode=StorageMode.BOTH,
            production_rate=100.0,
            max_daily_capacity=2000.0,
        )
        assert site.id == "6122"
        assert site.production_rate == 100.0
        assert site.max_daily_capacity == 2000.0

    def test_calculate_labor_hours(self):
        """Test labor hours calculation."""
        site = ManufacturingSite(
            id="M1",
            name="Plant",
            storage_mode=StorageMode.BOTH,
            production_rate=50.0,  # 50 units per hour
            setup_time_hours=2.0,
        )
        # 500 units = 2h setup + 10h production = 12h
        hours = site.calculate_labor_hours(500.0)
        assert hours == 12.0

    def test_calculate_production_units(self):
        """Test production units calculation."""
        site = ManufacturingSite(
            id="M1",
            name="Plant",
            storage_mode=StorageMode.BOTH,
            production_rate=50.0,
            setup_time_hours=2.0,
        )
        # 12h - 2h setup = 10h × 50 units/h = 500 units
        units = site.calculate_production_units(12.0)
        assert units == 500.0

    def test_can_produce_quantity(self):
        """Test capacity checking."""
        site = ManufacturingSite(
            id="M1",
            name="Plant",
            storage_mode=StorageMode.BOTH,
            production_rate=100.0,
            max_daily_capacity=1000.0,
        )
        assert site.can_produce_quantity(800.0)
        assert not site.can_produce_quantity(1200.0)


class TestTruckSchedule:
    """Tests for TruckSchedule model."""

    def test_create_morning_truck(self):
        """Test creating morning truck schedule."""
        truck = TruckSchedule(
            id="T1",
            truck_name="Morning Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            destination_id="BR1",
            capacity=500.0,
        )
        assert truck.is_morning()
        assert not truck.is_afternoon()
        assert truck.is_fixed_route()

    def test_create_flexible_route_truck(self):
        """Test truck with flexible routing."""
        truck = TruckSchedule(
            id="T2",
            truck_name="Afternoon Truck",
            departure_type=DepartureType.AFTERNOON,
            departure_time=time(14, 0),
            destination_id=None,  # Flexible
            capacity=600.0,
        )
        assert not truck.is_fixed_route()

    def test_calculate_cost(self):
        """Test truck cost calculation."""
        truck = TruckSchedule(
            id="T1",
            truck_name="Test Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            capacity=500.0,
            cost_fixed=100.0,
            cost_per_unit=0.5,
        )
        # 200 units: 100 + (200 * 0.5) = 200
        assert truck.calculate_cost(200.0) == 200.0

    def test_calculate_required_pallets(self):
        """Test pallet calculation with ceiling division."""
        truck = TruckSchedule(
            id="T1",
            truck_name="Standard Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            capacity=14080.0,  # 44 pallets
            pallet_capacity=44,
            units_per_pallet=320,
        )
        # Exact pallets
        assert truck.calculate_required_pallets(14080) == 44  # Full truck
        assert truck.calculate_required_pallets(320) == 1  # One pallet
        assert truck.calculate_required_pallets(640) == 2  # Two pallets

        # Partial pallets (rounds up)
        assert truck.calculate_required_pallets(321) == 2  # 1.003 pallets -> 2
        assert truck.calculate_required_pallets(10) == 1  # 0.03 pallets -> 1
        assert truck.calculate_required_pallets(13600) == 43  # 42.5 pallets -> 43

        # Zero
        assert truck.calculate_required_pallets(0) == 0

    def test_calculate_required_pallets_exceeds_capacity(self):
        """Test pallet calculation when exceeding truck capacity."""
        truck = TruckSchedule(
            id="T1",
            truck_name="Standard Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            capacity=14080.0,
            pallet_capacity=44,
            units_per_pallet=320,
        )
        # Exceeds capacity
        with pytest.raises(ValueError, match="exceeds truck capacity"):
            truck.calculate_required_pallets(14400)  # 45 pallets

    def test_calculate_pallet_efficiency(self):
        """Test pallet utilization efficiency calculation."""
        truck = TruckSchedule(
            id="T1",
            truck_name="Standard Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            capacity=14080.0,
            pallet_capacity=44,
            units_per_pallet=320,
        )
        # 100% efficiency
        assert truck.calculate_pallet_efficiency(14080) == 1.0

        # Partial efficiency
        assert truck.calculate_pallet_efficiency(7040) == pytest.approx(0.5)  # 22 pallets
        assert truck.calculate_pallet_efficiency(13600) == pytest.approx(0.977, rel=0.01)  # 43 pallets

        # Low efficiency (1 unit = 1 pallet)
        assert truck.calculate_pallet_efficiency(10) == pytest.approx(0.0227, rel=0.01)  # 1 pallet

    def test_validate_case_quantity(self):
        """Test case quantity validation."""
        truck = TruckSchedule(
            id="T1",
            truck_name="Standard Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            capacity=14080.0,
            units_per_case=10,
        )
        # Valid case quantities
        assert truck.validate_case_quantity(10) is True
        assert truck.validate_case_quantity(100) is True
        assert truck.validate_case_quantity(14080) is True
        assert truck.validate_case_quantity(0) is True

        # Invalid (partial cases)
        assert truck.validate_case_quantity(5) is False
        assert truck.validate_case_quantity(15) is False
        assert truck.validate_case_quantity(105) is False

    def test_round_to_case_quantity(self):
        """Test rounding to valid case quantities."""
        truck = TruckSchedule(
            id="T1",
            truck_name="Standard Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            capacity=14080.0,
            units_per_case=10,
        )
        # Round up
        assert truck.round_to_case_quantity(105, round_up=True) == 110
        assert truck.round_to_case_quantity(101, round_up=True) == 110
        assert truck.round_to_case_quantity(5, round_up=True) == 10

        # Round down
        assert truck.round_to_case_quantity(105, round_up=False) == 100
        assert truck.round_to_case_quantity(109, round_up=False) == 100
        assert truck.round_to_case_quantity(5, round_up=False) == 0

        # Already valid
        assert truck.round_to_case_quantity(100, round_up=True) == 100
        assert truck.round_to_case_quantity(100, round_up=False) == 100

    def test_has_intermediate_stops(self):
        """Test intermediate stops detection."""
        # No stops
        truck1 = TruckSchedule(
            id="T1",
            truck_name="Direct Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            destination_id="6125",
            capacity=14080.0,
        )
        assert not truck1.has_intermediate_stops()

        # With stops
        truck2 = TruckSchedule(
            id="T2",
            truck_name="Wednesday Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            destination_id="6125",
            capacity=14080.0,
            intermediate_stops=["Lineage"],
        )
        assert truck2.has_intermediate_stops()

    def test_is_day_specific(self):
        """Test day-specific schedule detection."""
        from src.models import DayOfWeek

        # Daily schedule
        truck1 = TruckSchedule(
            id="T1",
            truck_name="Daily Truck",
            departure_type=DepartureType.MORNING,
            departure_time=time(8, 0),
            capacity=14080.0,
        )
        assert not truck1.is_day_specific()

        # Day-specific
        truck2 = TruckSchedule(
            id="T2",
            truck_name="Monday Truck",
            departure_type=DepartureType.AFTERNOON,
            departure_time=time(14, 0),
            capacity=14080.0,
            day_of_week=DayOfWeek.MONDAY,
        )
        assert truck2.is_day_specific()


class TestLaborCalendar:
    """Tests for LaborDay and LaborCalendar models."""

    def test_create_fixed_labor_day(self):
        """Test creating a fixed labor day."""
        day = LaborDay(
            date=date(2025, 10, 15),
            fixed_hours=8.0,
            regular_rate=25.0,
            overtime_rate=37.5,
            is_fixed_day=True,
        )
        assert day.fixed_hours == 8.0
        assert day.is_fixed_day

    def test_calculate_cost_within_fixed_hours(self):
        """Test labor cost calculation within fixed hours."""
        day = LaborDay(
            date=date(2025, 10, 15),
            fixed_hours=8.0,
            regular_rate=25.0,
            overtime_rate=37.5,
        )
        # 6 hours at regular rate
        cost = day.calculate_labor_cost(6.0)
        assert cost == 150.0  # 6 * 25

    def test_calculate_cost_with_overtime(self):
        """Test labor cost with overtime."""
        day = LaborDay(
            date=date(2025, 10, 15),
            fixed_hours=8.0,
            regular_rate=25.0,
            overtime_rate=37.5,
        )
        # 10 hours: 8 at regular + 2 at OT
        cost = day.calculate_labor_cost(10.0)
        assert cost == 275.0  # (8 * 25) + (2 * 37.5)

    def test_calculate_cost_non_fixed_day(self):
        """Test labor cost on non-fixed day."""
        day = LaborDay(
            date=date(2025, 10, 16),
            fixed_hours=0.0,
            regular_rate=25.0,
            overtime_rate=37.5,
            non_fixed_rate=40.0,
            minimum_hours=4.0,
            is_fixed_day=False,
        )
        # 6 hours at non-fixed rate
        cost = day.calculate_labor_cost(6.0)
        assert cost == 240.0  # 6 * 40

        # 2 hours but minimum is 4
        cost = day.calculate_labor_cost(2.0)
        assert cost == 160.0  # 4 * 40 (minimum)

    def test_labor_calendar(self):
        """Test LaborCalendar container."""
        days = [
            LaborDay(
                date=date(2025, 10, 15),
                fixed_hours=8.0,
                regular_rate=25.0,
                overtime_rate=37.5,
            ),
            LaborDay(
                date=date(2025, 10, 16),
                fixed_hours=8.0,
                regular_rate=25.0,
                overtime_rate=37.5,
            ),
        ]
        calendar = LaborCalendar(name="Test Calendar", days=days)
        assert len(calendar.days) == 2

        # Get specific day
        day = calendar.get_labor_day(date(2025, 10, 15))
        assert day is not None
        assert day.fixed_hours == 8.0


class TestProductionBatch:
    """Tests for ProductionBatch model."""

    def test_create_production_batch(self):
        """Test creating a production batch."""
        batch = ProductionBatch(
            id="B001",
            product_id="P1",
            manufacturing_site_id="M1",
            production_date=date(2025, 10, 15),
            quantity=500.0,
            initial_state=ProductState.AMBIENT,
        )
        assert batch.id == "B001"
        assert batch.quantity == 500.0
        assert not batch.is_assigned()

    def test_assign_batch_to_truck(self):
        """Test assigning batch to truck."""
        batch = ProductionBatch(
            id="B001",
            product_id="P1",
            manufacturing_site_id="M1",
            production_date=date(2025, 10, 15),
            quantity=500.0,
            assigned_truck_id="T1",
        )
        assert batch.is_assigned()
        assert batch.assigned_truck_id == "T1"

    def test_is_same_day_production(self):
        """Test checking same-day production."""
        batch = ProductionBatch(
            id="B001",
            product_id="P1",
            manufacturing_site_id="M1",
            production_date=date(2025, 10, 15),
            quantity=500.0,
        )
        assert batch.is_same_day_production(date(2025, 10, 15))
        assert not batch.is_same_day_production(date(2025, 10, 16))

    def test_is_previous_day_production(self):
        """Test checking previous-day production."""
        batch = ProductionBatch(
            id="B001",
            product_id="P1",
            manufacturing_site_id="M1",
            production_date=date(2025, 10, 14),
            quantity=500.0,
        )
        assert batch.is_previous_day_production(date(2025, 10, 15))
        assert not batch.is_previous_day_production(date(2025, 10, 14))


class TestCostStructure:
    """Tests for CostStructure model."""

    def test_create_cost_structure(self):
        """Test creating cost structure with defaults."""
        costs = CostStructure()
        assert costs.production_cost_per_unit >= 0
        assert costs.default_regular_rate > 0

    def test_calculate_waste_cost(self):
        """Test waste cost calculation."""
        costs = CostStructure(
            production_cost_per_unit=5.0,
            waste_cost_multiplier=1.5,
        )
        waste_cost = costs.calculate_waste_cost(100.0)
        assert waste_cost == 750.0  # 100 * 5 * 1.5

    def test_calculate_storage_cost(self):
        """Test storage cost calculation."""
        costs = CostStructure(
            storage_cost_frozen_per_unit_day=0.10,
            storage_cost_ambient_per_unit_day=0.05,
        )
        # Frozen: 100 units × 10 days × 0.10 = 100
        frozen_cost = costs.calculate_storage_cost(100.0, 10.0, is_frozen=True)
        assert frozen_cost == 100.0

        # Ambient: 100 units × 10 days × 0.05 = 50
        ambient_cost = costs.calculate_storage_cost(100.0, 10.0, is_frozen=False)
        assert ambient_cost == 50.0

    def test_calculate_transport_cost(self):
        """Test transport cost calculation."""
        costs = CostStructure(
            transport_cost_frozen_per_unit=0.50,
            transport_cost_ambient_per_unit=0.30,
            truck_fixed_cost=100.0,
        )
        # Frozen: 200 units × 0.50 + 100 fixed = 200
        frozen_cost = costs.calculate_transport_cost(200.0, is_frozen=True, include_truck_fixed=True)
        assert frozen_cost == 200.0

        # Without fixed cost
        frozen_cost_var = costs.calculate_transport_cost(200.0, is_frozen=True, include_truck_fixed=False)
        assert frozen_cost_var == 100.0

    def test_calculate_shortage_cost(self):
        """Test shortage penalty calculation."""
        costs = CostStructure(shortage_penalty_per_unit=10.0)
        shortage_cost = costs.calculate_shortage_cost(50.0)
        assert shortage_cost == 500.0  # 50 * 10
