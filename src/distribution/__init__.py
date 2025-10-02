"""Distribution planning module.

This module handles shipment planning and truck loading for the distribution
network, converting production schedules into truck load plans.

Key components:
- ShipmentPlanner: Expands production batches into destination shipments
- TruckLoader: Assigns shipments to truck departures with D-1/D0 logic
"""

from .shipment_planner import ShipmentPlanner
from .truck_loader import TruckLoader, TruckLoad, TruckLoadPlan

__all__ = [
    "ShipmentPlanner",
    "TruckLoader",
    "TruckLoad",
    "TruckLoadPlan",
]
