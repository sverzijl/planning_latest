"""Shipment planning from production schedules.

This module converts production batches into shipments for distribution,
expanding aggregated requirements into individual destination shipments.
"""

from typing import List, Dict
import uuid

from src.models.shipment import Shipment
from src.production.scheduler import ProductionSchedule, ProductionRequirement


class ShipmentPlanner:
    """
    Plans shipments from production schedule.

    Takes a ProductionSchedule (which includes both batches and requirements)
    and creates individual Shipment objects for each destination in each requirement.

    The key insight is that ProductionRequirement has demand_details containing:
    (location_id, delivery_date, quantity, route) for each destination served.

    Example:
        schedule = scheduler.schedule_from_forecast(forecast)
        planner = ShipmentPlanner()
        shipments = planner.create_shipments(schedule)
    """

    def create_shipments(
        self,
        schedule: ProductionSchedule
    ) -> List[Shipment]:
        """
        Create shipments from production schedule.

        For each ProductionRequirement in the schedule:
        1. Find the corresponding ProductionBatch
        2. For each demand_detail in the requirement:
           - Create a Shipment linking batch to destination
           - Preserve route and delivery date
           - Set production date from batch

        Args:
            schedule: Production schedule with batches and requirements

        Returns:
            List of shipments, one per demand_detail across all requirements

        Example:
            Requirement: PROD1 on 2025-01-15, 1000 units total
            demand_details:
                - (6103, 2025-01-20, 500, route_via_6125)
                - (6101, 2025-01-20, 500, route_via_6104)

            Creates 2 shipments:
                - 500 units → 6103 via 6125
                - 500 units → 6101 via 6104
        """
        shipments = []

        # Create mapping of (production_date, product_id) → batch
        batch_map: Dict[tuple, List] = {}
        for batch in schedule.production_batches:
            key = (batch.production_date, batch.product_id)
            if key not in batch_map:
                batch_map[key] = []
            batch_map[key].append(batch)

        # Process each requirement
        for requirement in schedule.requirements:
            # Find corresponding batch(es)
            key = (requirement.production_date, requirement.product_id)
            batches = batch_map.get(key, [])

            if not batches:
                # Should not happen if schedule is consistent
                continue

            # For simplicity, use the first batch if multiple exist
            # (In practice, requirement aggregates to one batch per (date, product))
            batch = batches[0]

            # Create shipment for each demand detail
            for location_id, delivery_date, quantity, route in requirement.demand_details:
                shipment = Shipment(
                    id=self._generate_shipment_id(batch.id, location_id),
                    batch_id=batch.id,
                    product_id=batch.product_id,
                    quantity=quantity,
                    origin_id=schedule.manufacturing_site_id,
                    destination_id=location_id,
                    delivery_date=delivery_date,
                    route=route,
                    assigned_truck_id=None,
                    production_date=batch.production_date,
                )
                shipments.append(shipment)

        return shipments

    def _generate_shipment_id(self, batch_id: str, destination_id: str) -> str:
        """
        Generate unique shipment ID.

        Args:
            batch_id: Production batch ID
            destination_id: Destination location ID

        Returns:
            Unique shipment identifier
        """
        # Format: SHIP-{batch_id_suffix}-{destination}-{random}
        batch_suffix = batch_id.split("-")[-1][:8] if "-" in batch_id else batch_id[:8]
        random_suffix = uuid.uuid4().hex[:6]
        return f"SHIP-{batch_suffix}-{destination_id}-{random_suffix}"

    def get_shipments_by_destination(
        self,
        shipments: List[Shipment]
    ) -> Dict[str, List[Shipment]]:
        """
        Group shipments by first leg destination.

        This is useful for truck loading - shipments are assigned to trucks
        based on the first leg destination (hub).

        Args:
            shipments: List of shipments

        Returns:
            Dictionary mapping first_leg_destination → list of shipments

        Example:
            shipments to 6103 (via 6125) → grouped under "6125"
            shipments to 6101 (via 6104) → grouped under "6104"
        """
        grouped: Dict[str, List[Shipment]] = {}

        for shipment in shipments:
            dest = shipment.first_leg_destination
            if dest not in grouped:
                grouped[dest] = []
            grouped[dest].append(shipment)

        return grouped

    def get_shipments_by_production_date(
        self,
        shipments: List[Shipment]
    ) -> Dict:
        """
        Group shipments by production date.

        Args:
            shipments: List of shipments

        Returns:
            Dictionary mapping production_date → list of shipments
        """
        from datetime import date
        grouped: Dict[date, List[Shipment]] = {}

        for shipment in shipments:
            prod_date = shipment.production_date
            if prod_date not in grouped:
                grouped[prod_date] = []
            grouped[prod_date].append(shipment)

        return grouped
