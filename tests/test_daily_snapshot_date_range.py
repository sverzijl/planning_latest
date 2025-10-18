"""Tests for daily snapshot date range capping fix.

Tests that _get_date_range() properly caps dates at the planning horizon boundaries
to ensure the snapshot slider only shows dates within the optimization model's
planning period.
"""

import pytest
from datetime import date, timedelta
from typing import List

from src.models.production_schedule import ProductionSchedule
from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment
from src.shelf_life.tracker import RouteLeg
from src.network.route_finder import RoutePath
from ui.components.daily_snapshot import _get_date_range


class TestDailySnapshotDateRange:
    """Test suite for date range capping in daily snapshot."""

    def test_dates_within_planning_horizon(self):
        """Test that dates within the planning horizon are included."""
        # Setup
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 7)

        # Create production schedule with dates inside horizon
        batches = [
            ProductionBatch(
                id="BATCH-001",
                product_id="P1",
                manufacturing_site_id="6122",
                production_date=date(2025, 10, 3),
                quantity=1000,
            ),
            ProductionBatch(
                id="BATCH-002",
                product_id="P1",
                manufacturing_site_id="6122",
                production_date=date(2025, 10, 5),
                quantity=2000,
            ),
        ]

        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            schedule_start_date=start_date,
            schedule_end_date=end_date,
            daily_totals={},
            daily_labor_hours={},
        )

        # Execute
        result = _get_date_range(schedule, [])

        # Verify
        assert result is not None
        min_date, max_date = result
        assert min_date == date(2025, 10, 3)  # First production date
        assert max_date == date(2025, 10, 5)  # Last production date

    def test_dates_beyond_schedule_end_excluded(self):
        """Test that dates beyond schedule_end_date are excluded."""
        # Setup
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 7)

        # Create shipments with delivery dates OUTSIDE the planning horizon
        route_path = RoutePath(
            path=["6122", "6125"],
            total_transit_days=2,
            total_cost=10.0,
            transport_modes=["ambient"],
            route_legs=[
                RouteLeg(
                    from_location_id="6122",
                    to_location_id="6125",
                    transport_mode="ambient",
                    transit_days=2
                )
            ],
            intermediate_stops=[]
        )

        shipments = [
            Shipment(
                id="SHIP-001",
                batch_id="BATCH-001",
                product_id="P1",
                quantity=500,
                origin_id="6122",
                destination_id="6125",
                delivery_date=date(2025, 10, 10),  # AFTER end_date (10/7)
                route=route_path,
                production_date=date(2025, 10, 3),
            ),
        ]

        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=[],
            schedule_start_date=start_date,
            schedule_end_date=end_date,
            daily_totals={},
            daily_labor_hours={},
        )

        # Execute
        result = _get_date_range(schedule, shipments)

        # Verify - date beyond end_date should be excluded
        assert result is None  # No valid dates within horizon

    def test_dates_before_schedule_start_excluded(self):
        """Test that dates before schedule_start_date are excluded."""
        # Setup
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 7)

        # Create production batch with date BEFORE planning horizon
        batches = [
            ProductionBatch(
                id="BATCH-000",
                product_id="P1",
                manufacturing_site_id="6122",
                production_date=date(2025, 9, 28),  # BEFORE start_date (10/1)
                quantity=1000,
            ),
        ]

        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            schedule_start_date=start_date,
            schedule_end_date=end_date,
            daily_totals={},
            daily_labor_hours={},
        )

        # Execute
        result = _get_date_range(schedule, [])

        # Verify - date before start_date should be excluded
        assert result is None  # No valid dates within horizon

    def test_shipment_dates_outside_horizon_excluded(self):
        """Test that shipment dates outside planning horizon are excluded."""
        # Setup
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 7)

        route_path = RoutePath(
            path=["6122", "6125"],
            total_transit_days=1,
            total_cost=10.0,
            transport_modes=["ambient"],
            route_legs=[
                RouteLeg(
                    from_location_id="6122",
                    to_location_id="6125",
                    transport_mode="ambient",
                    transit_days=1
                )
            ],
            intermediate_stops=[]
        )

        shipments = [
            # Shipment with departure_date before horizon
            Shipment(
                id="SHIP-001",
                batch_id="BATCH-001",
                product_id="P1",
                quantity=500,
                origin_id="6122",
                destination_id="6125",
                delivery_date=date(2025, 9, 30),  # Before start_date
                route=route_path,
                production_date=date(2025, 9, 29),
            ),
            # Shipment with delivery_date after horizon
            Shipment(
                id="SHIP-002",
                batch_id="BATCH-002",
                product_id="P1",
                quantity=500,
                origin_id="6122",
                destination_id="6125",
                delivery_date=date(2025, 10, 15),  # After end_date
                route=route_path,
                production_date=date(2025, 10, 14),
            ),
        ]

        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=[],
            schedule_start_date=start_date,
            schedule_end_date=end_date,
            daily_totals={},
            daily_labor_hours={},
        )

        # Execute
        result = _get_date_range(schedule, shipments)

        # Verify - all shipment dates are outside horizon
        assert result is None

    def test_graceful_handling_when_schedule_end_date_none(self):
        """Test graceful handling when schedule_end_date is None."""
        # Setup - schedule without end_date
        batches = [
            ProductionBatch(
                id="BATCH-001",
                product_id="P1",
                manufacturing_site_id="6122",
                production_date=date(2025, 10, 3),
                quantity=1000,
            ),
        ]

        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            schedule_start_date=date(2025, 10, 1),
            schedule_end_date=None,  # No end date
            daily_totals={},
            daily_labor_hours={},
        )

        # Execute
        result = _get_date_range(schedule, [])

        # Verify - should still work, not capping max date
        assert result is not None
        min_date, max_date = result
        assert min_date == date(2025, 10, 3)
        assert max_date == date(2025, 10, 3)

    def test_mixed_dates_some_inside_some_outside_horizon(self):
        """Test date range with mixed dates (some inside, some outside horizon)."""
        # Setup
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 7)

        batches = [
            ProductionBatch(
                id="BATCH-001",
                product_id="P1",
                manufacturing_site_id="6122",
                production_date=date(2025, 10, 3),  # Inside horizon
                quantity=1000,
            ),
            ProductionBatch(
                id="BATCH-002",
                product_id="P1",
                manufacturing_site_id="6122",
                production_date=date(2025, 10, 10),  # Outside horizon (after end)
                quantity=2000,
            ),
        ]

        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=batches,
            schedule_start_date=start_date,
            schedule_end_date=end_date,
            daily_totals={},
            daily_labor_hours={},
        )

        # Execute
        result = _get_date_range(schedule, [])

        # Verify - only dates within horizon should be included
        assert result is not None
        min_date, max_date = result
        assert min_date == date(2025, 10, 3)
        assert max_date == date(2025, 10, 3)  # Second batch excluded

    def test_empty_schedule_returns_none(self):
        """Test that empty schedule returns None."""
        # Setup
        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=[],
            schedule_start_date=date(2025, 10, 1),
            schedule_end_date=date(2025, 10, 7),
            daily_totals={},
            daily_labor_hours={},
        )

        # Execute
        result = _get_date_range(schedule, [])

        # Verify
        assert result is None

    def test_all_shipment_date_fields_respected(self):
        """Test that departure_date, arrival_date, and production_date are all capped."""
        # Setup
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 7)

        route_path = RoutePath(
            path=["6122", "6125"],
            total_transit_days=2,
            total_cost=10.0,
            transport_modes=["ambient"],
            route_legs=[
                RouteLeg(
                    from_location_id="6122",
                    to_location_id="6125",
                    transport_mode="ambient",
                    transit_days=2
                )
            ],
            intermediate_stops=[]
        )

        # Create shipment with all dates within horizon
        shipments = [
            Shipment(
                id="SHIP-001",
                batch_id="BATCH-001",
                product_id="P1",
                quantity=500,
                origin_id="6122",
                destination_id="6125",
                delivery_date=date(2025, 10, 5),  # Within horizon
                route=route_path,
                production_date=date(2025, 10, 3),  # Within horizon
            ),
        ]

        schedule = ProductionSchedule(
            manufacturing_site_id="6122",
            production_batches=[],
            schedule_start_date=start_date,
            schedule_end_date=end_date,
            daily_totals={},
            daily_labor_hours={},
        )

        # Execute
        result = _get_date_range(schedule, shipments)

        # Verify - shipment dates within horizon should be included
        assert result is not None
        min_date, max_date = result
        assert min_date == date(2025, 10, 3)  # production_date
        assert max_date == date(2025, 10, 5)  # delivery_date
