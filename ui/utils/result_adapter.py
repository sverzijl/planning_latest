"""Adapters to convert optimization results to heuristic-compatible format.

This module provides functions to normalize optimization model outputs
into the same data structures used by heuristic planning, enabling
the Results UI to display both types of results seamlessly.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import date as Date, timedelta
from collections import defaultdict
from src.production.scheduler import ProductionSchedule, ProductionBatch
from src.costs.cost_breakdown import (
    TotalCostBreakdown,
    LaborCostBreakdown,
    ProductionCostBreakdown,
    TransportCostBreakdown,
    WasteCostBreakdown,
)
from src.distribution.truck_loader import TruckLoadPlan, TruckLoad
from src.models.shipment import Shipment

logger = logging.getLogger(__name__)


def adapt_optimization_results(
    model: Any,
    result: dict,
    inventory_snapshot_date: Optional[Date] = None
) -> Optional[Dict[str, Any]]:
    """
    Convert optimization results to heuristic-compatible format.

    Args:
        model: IntegratedProductionDistributionModel instance
        result: Optimization result dictionary from session state
        inventory_snapshot_date: Optional date when initial inventory was loaded

    Returns:
        Dictionary with keys: production_schedule, shipments, truck_plan, cost_breakdown
        Returns None if optimization hasn't been solved yet
    """
    solution = model.get_solution()
    if not solution:
        return None

    # Convert production schedule
    production_schedule = _create_production_schedule(
        model,
        solution,
        inventory_snapshot_date
    )

    # Get shipments (model already has this method)
    shipments = model.get_shipment_plan() or []
    logger.info(f"Retrieved {len(shipments)} shipments from optimization model")

    # Create truck plan from optimization results
    truck_plan = _create_truck_plan_from_optimization(model, shipments)
    logger.info(f"Created truck plan with {len(truck_plan.loads)} truck loads and {len(truck_plan.unassigned_shipments)} unassigned shipments")

    # Convert cost breakdown
    cost_breakdown = _create_cost_breakdown(model, solution)

    return {
        'production_schedule': production_schedule,
        'shipments': shipments,
        'truck_plan': truck_plan,
        'cost_breakdown': cost_breakdown,
    }


def _create_production_schedule(
    model: Any,
    solution: dict,
    inventory_snapshot_date: Optional[Date] = None
) -> ProductionSchedule:
    """Convert optimization solution to ProductionSchedule object."""

    batches = []

    # CREATE BATCHES FROM INITIAL INVENTORY
    if hasattr(model, 'initial_inventory') and model.initial_inventory and inventory_snapshot_date:
        for (location_id, product_id), quantity in model.initial_inventory.items():
            if quantity > 0:
                # Create virtual batch for initial inventory
                # Use snapshot_date - 1 so inventory exists on snapshot_date
                batch = ProductionBatch(
                    id=f"INIT-{location_id}-{product_id}",
                    product_id=product_id,
                    manufacturing_site_id=location_id,  # CRITICAL: Use actual location, not just 6122!
                    production_date=inventory_snapshot_date - timedelta(days=1),
                    quantity=quantity,
                    labor_hours_used=0,  # Initial inventory has no labor cost
                    production_cost=0,  # Initial inventory is sunk cost
                )
                batches.append(batch)

    # EXISTING CODE: Create ProductionBatch objects from solution
    for idx, batch_dict in enumerate(solution.get('production_batches', [])):
        batch = ProductionBatch(
            id=f"OPT-BATCH-{idx+1:04d}",
            product_id=batch_dict['product'],
            manufacturing_site_id=model.manufacturing_site.location_id,
            production_date=batch_dict['date'],
            quantity=batch_dict['quantity'],
            labor_hours_used=0,  # Will aggregate from daily totals
            production_cost=batch_dict['quantity'] * model.cost_structure.production_cost_per_unit,
        )
        batches.append(batch)

    # Build daily totals from batches
    daily_totals: Dict[Date, float] = {}
    for batch in batches:
        daily_totals[batch.production_date] = daily_totals.get(batch.production_date, 0) + batch.quantity

    # Get labor hours by date from solution
    daily_labor_hours = solution.get('labor_hours_by_date', {})

    # Update batch labor hours proportionally
    for batch in batches:
        date_total = daily_totals.get(batch.production_date, 1)
        if date_total > 0:
            proportion = batch.quantity / date_total
            batch.labor_hours_used = daily_labor_hours.get(batch.production_date, 0) * proportion

    # Determine actual schedule start date
    if inventory_snapshot_date:
        # Use inventory snapshot date as schedule start
        actual_start_date = inventory_snapshot_date
    elif batches:
        # Use earliest production/batch date if no inventory
        actual_start_date = min(b.production_date for b in batches)
    else:
        # Fallback to model start date
        actual_start_date = model.start_date

    # Build ProductionSchedule
    return ProductionSchedule(
        manufacturing_site_id=model.manufacturing_site.location_id,
        schedule_start_date=actual_start_date,
        schedule_end_date=model.end_date,
        production_batches=batches,
        daily_totals=daily_totals,
        daily_labor_hours=daily_labor_hours,
        infeasibilities=[],  # Optimal solution is feasible
        total_units=sum(b.quantity for b in batches),
        total_labor_hours=sum(daily_labor_hours.values()),
        requirements=None,  # Optimization doesn't track original requirements
    )


def _create_truck_plan_from_optimization(model: Any, shipments: List[Shipment]) -> TruckLoadPlan:
    """Create TruckLoadPlan from optimization results.

    Args:
        model: IntegratedProductionDistributionModel instance
        shipments: List of Shipment objects with assigned_truck_id set

    Returns:
        TruckLoadPlan with actual truck loads from optimization
    """
    # Group shipments by truck and date
    truck_shipments: Dict[tuple, List[Shipment]] = defaultdict(list)
    unassigned_shipments: List[Shipment] = []

    for shipment in shipments:
        if shipment.assigned_truck_id:
            # Use production_date as the truck departure date
            key = (shipment.assigned_truck_id, shipment.production_date)
            truck_shipments[key].append(shipment)
        else:
            unassigned_shipments.append(shipment)

    # Log truck assignment diagnostics
    logger.debug(f"Grouped shipments: {len(truck_shipments)} trucks with assignments, {len(unassigned_shipments)} unassigned")

    if len(unassigned_shipments) > 0 and len(shipments) > 0:
        pct_unassigned = 100 * len(unassigned_shipments) / len(shipments)
        if pct_unassigned > 50:
            logger.warning(
                f"{pct_unassigned:.1f}% of shipments are unassigned to trucks. "
                f"This may indicate: (1) model solved without truck_schedules, "
                f"(2) routes don't align with truck destinations, or "
                f"(3) limited route enumeration (max_routes_per_destination too low)"
            )

    # Create TruckLoad objects
    loads: List[TruckLoad] = []

    for (truck_id, departure_date), shipment_list in truck_shipments.items():
        # Find the truck schedule
        truck_schedule = None
        for truck in model.truck_schedules.schedules if model.truck_schedules else []:
            if truck.id == truck_id:
                truck_schedule = truck
                break

        if not truck_schedule:
            continue

        # Get destination from first shipment's immediate next hop
        destination_id = shipment_list[0].first_leg_destination

        # Calculate totals
        total_units = sum(s.quantity for s in shipment_list)

        # Calculate pallets (accounting for partial pallets)
        units_per_pallet = truck_schedule.units_per_pallet
        total_pallets = 0
        for shipment in shipment_list:
            pallets = (shipment.quantity + units_per_pallet - 1) // units_per_pallet  # Ceiling division
            total_pallets += pallets

        # Calculate utilization
        capacity_pallets = truck_schedule.pallet_capacity
        capacity_utilization = total_pallets / capacity_pallets if capacity_pallets > 0 else 0

        # Create TruckLoad
        # Handle departure_type - might be DepartureType enum or string
        departure_type_str = truck_schedule.departure_type.value if hasattr(truck_schedule.departure_type, 'value') else truck_schedule.departure_type

        truck_load = TruckLoad(
            truck_schedule_id=truck_schedule.id,
            truck_name=truck_schedule.truck_name,
            departure_date=departure_date,
            departure_type=departure_type_str,
            departure_time=truck_schedule.departure_time,
            destination_id=destination_id or "UNKNOWN",
            shipments=shipment_list,
            total_units=total_units,
            total_pallets=total_pallets,
            capacity_units=truck_schedule.capacity,
            capacity_pallets=capacity_pallets,
            capacity_utilization=capacity_utilization,
            is_full=total_pallets >= capacity_pallets,
        )
        loads.append(truck_load)

    # Calculate average utilization
    total_trucks_used = len(loads)
    average_utilization = sum(load.capacity_utilization for load in loads) / total_trucks_used if total_trucks_used > 0 else 0.0

    return TruckLoadPlan(
        loads=loads,
        unassigned_shipments=unassigned_shipments,
        infeasibilities=[],
        total_trucks_used=total_trucks_used,
        total_shipments=len(shipments),
        average_utilization=average_utilization,
    )


def _create_cost_breakdown(model: Any, solution: dict) -> TotalCostBreakdown:
    """Convert optimization cost components to TotalCostBreakdown object."""

    # Extract costs from solution
    labor_cost = solution.get('total_labor_cost', 0)
    production_cost = solution.get('total_production_cost', 0)
    transport_cost = solution.get('total_transport_cost', 0)
    truck_cost = solution.get('total_truck_cost', 0)
    shortage_cost = solution.get('total_shortage_cost', 0)
    total_cost = solution.get('total_cost', 0)

    # Get daily labor hours and costs
    labor_hours_by_date = solution.get('labor_hours_by_date', {})
    labor_cost_by_date = solution.get('labor_cost_by_date', {})

    # Convert flat cost dict to nested format matching LaborCostBreakdown.daily_breakdown type
    # The UI expects Dict[date, Dict[str, float]] but optimization provides Dict[date, float]
    daily_breakdown_nested: Dict[Date, Dict[str, float]] = {}
    for date, total_cost in labor_cost_by_date.items():
        daily_breakdown_nested[date] = {
            'total_hours': labor_hours_by_date.get(date, 0),
            'fixed_hours': 0,  # Not tracked separately in optimization
            'overtime_hours': 0,
            'fixed_cost': 0,
            'overtime_cost': 0,
            'non_fixed_cost': 0,
            'total_cost': total_cost,
        }

    # Build labor cost breakdown
    # Note: Optimization doesn't track fixed vs OT breakdown, so we use totals
    labor_breakdown = LaborCostBreakdown(
        total_cost=labor_cost,
        fixed_hours_cost=0,  # Not tracked separately in optimization
        overtime_cost=0,  # Not tracked separately in optimization
        non_fixed_labor_cost=0,  # Not tracked separately in optimization
        total_hours=sum(labor_hours_by_date.values()),
        fixed_hours=0,
        overtime_hours=0,
        non_fixed_hours=0,
        daily_breakdown=daily_breakdown_nested,  # Use nested dict matching expected structure
    )

    # Build production cost breakdown
    production_by_date_product = solution.get('production_by_date_product', {})

    # Aggregate by date
    cost_by_date: Dict[Date, float] = {}
    total_units = sum(production_by_date_product.values())
    if total_units > 0:
        for (date, product), qty in production_by_date_product.items():
            proportion = qty / total_units
            cost_by_date[date] = cost_by_date.get(date, 0) + (proportion * production_cost)

    # Aggregate by product
    cost_by_product: Dict[str, float] = {}
    if total_units > 0:
        for (date, product), qty in production_by_date_product.items():
            proportion = qty / total_units
            cost_by_product[product] = cost_by_product.get(product, 0) + (proportion * production_cost)

    production_breakdown = ProductionCostBreakdown(
        total_cost=production_cost,
        total_units_produced=total_units,
        average_cost_per_unit=production_cost / total_units if total_units > 0 else 0,
        cost_by_product=cost_by_product,
        cost_by_date=cost_by_date,
        batch_details=[],  # Could populate if needed
    )

    # Build transport cost breakdown
    transport_breakdown = TransportCostBreakdown(
        total_cost=transport_cost + truck_cost,  # Combine transport and truck costs
        total_units_shipped=total_units,  # Approximate
        average_cost_per_unit=(transport_cost + truck_cost) / total_units if total_units > 0 else 0,
        cost_by_route={},  # Could populate from shipments if needed
        cost_by_leg={},
        shipment_details=[],
    )

    # Build waste cost breakdown (shortage cost)
    total_shortage_units = solution.get('total_shortage_units', 0)
    waste_breakdown = WasteCostBreakdown(
        total_cost=shortage_cost,
        expired_units=0,  # Not tracked separately in optimization
        expired_cost=0,
        unmet_demand_units=total_shortage_units,  # Corrected from shortage_units
        unmet_demand_cost=shortage_cost,          # Corrected from shortage_cost
        waste_by_location={},
        waste_by_product={},
        waste_details=[],  # Explicit empty list
    )

    # Build total cost breakdown
    return TotalCostBreakdown(
        total_cost=total_cost,
        labor=labor_breakdown,
        production=production_breakdown,
        transport=transport_breakdown,
        waste=waste_breakdown,
        cost_per_unit_delivered=total_cost / total_units if total_units > 0 else 0,
    )
