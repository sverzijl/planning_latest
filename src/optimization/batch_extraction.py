"""Batch-level solution extraction for cohort-tracking models.

This module provides helper methods to extract batch-level data from
Pyomo models that use age-cohort inventory tracking.
"""

from typing import Dict, List, Tuple, Optional, Any
from datetime import date as Date, timedelta
from pyomo.environ import ConcreteModel, value

from src.models.production_batch import ProductionBatch
from src.models.shipment import Shipment
from src.models.product import ProductState


def extract_cohort_inventory(
    model: ConcreteModel,
    use_batch_tracking: bool
) -> Dict[Tuple[str, str, Date, Date, str], float]:
    """
    Extract cohort-level inventory from solved model.

    Args:
        model: Solved Pyomo model with cohort tracking variables
        use_batch_tracking: Whether batch tracking is enabled

    Returns:
        Dict mapping (location, product, production_date, current_date, state) -> quantity
    """
    cohort_inventory = {}

    if not use_batch_tracking:
        return cohort_inventory  # Empty for legacy model

    # Extract frozen cohorts
    for (loc, prod, prod_date, curr_date) in model.cohort_frozen_index:
        qty = value(model.inventory_frozen_cohort[loc, prod, prod_date, curr_date])
        if qty > 0.01:  # Filter out numerical noise
            cohort_inventory[(loc, prod, prod_date, curr_date, 'frozen')] = qty

    # Extract ambient cohorts
    for (loc, prod, prod_date, curr_date) in model.cohort_ambient_index:
        qty = value(model.inventory_ambient_cohort[loc, prod, prod_date, curr_date])
        if qty > 0.01:
            cohort_inventory[(loc, prod, prod_date, curr_date, 'ambient')] = qty

    return cohort_inventory


def create_production_batches(
    model: ConcreteModel,
    manufacturing_site_id: str,
    production_cost_per_unit: float,
    labor_hours_by_date: Dict[Date, float]
) -> Tuple[List[ProductionBatch], Dict[Tuple[Date, str], str]]:
    """
    Create ProductionBatch objects from solved production variables.

    Each production[date, product] becomes a unique batch with traceability.

    Args:
        model: Solved Pyomo model
        manufacturing_site_id: Manufacturing site location ID
        production_cost_per_unit: Production cost per unit
        labor_hours_by_date: Labor hours used per date

    Returns:
        Tuple of (batch_list, batch_id_map)
        - batch_list: List of ProductionBatch objects
        - batch_id_map: Dict mapping (production_date, product_id) -> batch_id
    """
    batches = []
    batch_id_map = {}
    batch_id_counter = 1

    for (prod_date, product_id) in model.production.keys():
        qty = value(model.production[prod_date, product_id])

        if qty > 0.01:  # Significant production
            # Generate unique batch ID (deterministic)
            batch_id = f"BATCH-{prod_date.strftime('%Y%m%d')}-{product_id}-{batch_id_counter:04d}"
            batch_id_map[(prod_date, product_id)] = batch_id

            # Pro-rate labor hours across products produced on same day
            labor_hours = labor_hours_by_date.get(prod_date, 0.0)
            production_on_date = [
                value(model.production[d, p])
                for (d, p) in model.production.keys()
                if d == prod_date and value(model.production[d, p]) > 0.01
            ]
            num_products = len(production_on_date)
            labor_hours_allocated = labor_hours / num_products if num_products > 0 else 0.0

            # Calculate production cost
            production_cost = qty * production_cost_per_unit

            # Create batch object
            batch = ProductionBatch(
                id=batch_id,
                product_id=product_id,
                manufacturing_site_id=manufacturing_site_id,
                production_date=prod_date,
                quantity=qty,
                initial_state=ProductState.AMBIENT,  # Always starts ambient
                labor_hours_used=labor_hours_allocated,
                production_cost=production_cost
            )

            batches.append(batch)
            batch_id_counter += 1

    return batches, batch_id_map


def extract_batch_shipments(
    model: ConcreteModel,
    use_batch_tracking: bool,
    batch_id_map: Dict[Tuple[Date, str], str],
    leg_transit_days: Dict[Tuple[str, str], int],
    manufacturing_site_id: str
) -> List[Shipment]:
    """
    Extract shipments with batch-level detail.

    Each shipment_leg_cohort becomes a Shipment object linked to a specific batch.

    Args:
        model: Solved Pyomo model
        use_batch_tracking: Whether batch tracking is enabled
        batch_id_map: Mapping of (production_date, product_id) -> batch_id
        leg_transit_days: Transit days for each leg
        manufacturing_site_id: Manufacturing site location ID

    Returns:
        List of Shipment objects with batch linkage
    """
    from src.shelf_life.tracker import RouteLeg
    from src.network.route_finder import RoutePath

    shipments = []
    shipment_id_counter = 1

    if use_batch_tracking:
        # Extract from cohort shipment variables
        for (leg, product_id, prod_date, delivery_date) in model.cohort_shipment_index:
            qty = value(model.shipment_leg_cohort[leg, product_id, prod_date, delivery_date])

            if qty > 0.01:
                origin, dest = leg

                # Find corresponding batch
                batch_id = batch_id_map.get((prod_date, product_id))
                if not batch_id:
                    # Shouldn't happen - batch not found
                    batch_id = f"BATCH-UNKNOWN-{prod_date.strftime('%Y%m%d')}-{product_id}"

                # Generate shipment ID (deterministic)
                shipment_id = f"SHIP-{delivery_date.strftime('%Y%m%d')}-{origin}-{dest}-{shipment_id_counter:05d}"

                # Create single-leg route
                transit_days = leg_transit_days.get(leg, 0)
                leg_obj = RouteLeg(
                    from_location_id=origin,
                    to_location_id=dest,
                    transport_mode='ambient',  # Simplified - could track mode
                    transit_days=transit_days
                )
                single_leg_route = RoutePath(
                    path=[origin, dest],
                    total_transit_days=transit_days,
                    total_cost=0.0,
                    transport_modes=['ambient'],
                    route_legs=[leg_obj],
                    intermediate_stops=[]
                )

                # Create shipment
                shipment = Shipment(
                    id=shipment_id,
                    batch_id=batch_id,
                    product_id=product_id,
                    quantity=qty,
                    origin_id=origin,
                    destination_id=dest,
                    delivery_date=delivery_date,
                    route=single_leg_route,
                    production_date=prod_date  # Key: links to batch
                )

                shipments.append(shipment)
                shipment_id_counter += 1
    else:
        # Legacy: Extract from aggregated shipment_leg variables (no batch detail)
        for (leg, product_id, delivery_date) in [(l, p, d) for l in model.legs for p in model.products for d in model.dates]:
            qty = value(model.shipment_leg[leg, product_id, delivery_date])

            if qty > 0.01:
                origin, dest = leg
                transit_days = leg_transit_days.get(leg, 0)
                departure_date = delivery_date - timedelta(days=transit_days)

                # Try to find matching batch
                batch_id = batch_id_map.get((departure_date, product_id))
                if not batch_id:
                    batch_id = f"BATCH-UNKNOWN"

                # Generate shipment ID
                shipment_id = f"SHIP-{shipment_id_counter:05d}"

                # Create single-leg route
                from src.shelf_life.tracker import RouteLeg
                from src.network.route_finder import RoutePath

                leg_obj = RouteLeg(
                    from_location_id=origin,
                    to_location_id=dest,
                    transport_mode='ambient',
                    transit_days=transit_days
                )
                single_leg_route = RoutePath(
                    path=[origin, dest],
                    total_transit_days=transit_days,
                    total_cost=0.0,
                    transport_modes=['ambient'],
                    route_legs=[leg_obj],
                    intermediate_stops=[]
                )

                # Create shipment
                shipment = Shipment(
                    id=shipment_id,
                    batch_id=batch_id,
                    product_id=product_id,
                    quantity=qty,
                    origin_id=origin,
                    destination_id=dest,
                    delivery_date=delivery_date,
                    route=single_leg_route,
                    production_date=departure_date
                )

                shipments.append(shipment)
                shipment_id_counter += 1

    return shipments


def extract_demand_from_cohort(
    model: ConcreteModel,
    use_batch_tracking: bool
) -> Dict[Tuple[str, str, Date, Date], float]:
    """
    Extract demand satisfaction by cohort.

    Args:
        model: Solved Pyomo model
        use_batch_tracking: Whether batch tracking is enabled

    Returns:
        Dict mapping (location, product, production_date, current_date) -> quantity satisfied
    """
    demand_from_cohort = {}

    if not use_batch_tracking:
        return demand_from_cohort

    for (loc, prod, prod_date, curr_date) in model.cohort_demand_index:
        qty = value(model.demand_from_cohort[loc, prod, prod_date, curr_date])
        if qty > 0.01:
            demand_from_cohort[(loc, prod, prod_date, curr_date)] = qty

    return demand_from_cohort
