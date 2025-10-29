"""Adapters to convert optimization results to heuristic-compatible format.

This module provides functions to normalize optimization model outputs
into the same data structures used by heuristic planning, enabling
the Results UI to display both types of results seamlessly.

REFACTORED: Now expects Pydantic-validated OptimizationSolution.
All defensive isinstance() checks removed - data is guaranteed valid.
"""

import logging
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from datetime import date as Date, timedelta
from collections import defaultdict
from pydantic import ValidationError
from src.models.production_schedule import ProductionSchedule
from src.models.production_batch import ProductionBatch
from src.costs.cost_breakdown import (
    TotalCostBreakdown,
    LaborCostBreakdown,
    ProductionCostBreakdown,
    TransportCostBreakdown,
    HoldingCostBreakdown,
    WasteCostBreakdown,
)
from src.models.truck_load import TruckLoadPlan, TruckLoad
from src.models.shipment import Shipment

if TYPE_CHECKING:
    from src.optimization.result_schema import OptimizationSolution

logger = logging.getLogger(__name__)


def adapt_optimization_results(
    model: Any,
    result: dict,
    inventory_snapshot_date: Optional[Date] = None
) -> Optional[Dict[str, Any]]:
    """
    Convert optimization results to heuristic-compatible format.

    IMPORTANT: Expects Pydantic-validated OptimizationSolution from model.get_solution().
    Raises ValidationError if solution doesn't conform to schema.

    Args:
        model: BaseOptimizationModel instance (SlidingWindowModel or UnifiedNodeModel)
        result: Optimization result dictionary from session state (unused, kept for compatibility)
        inventory_snapshot_date: Optional date when initial inventory was loaded

    Returns:
        Dictionary with keys: production_schedule, shipments, truck_plan, cost_breakdown, model_solution
        Returns None if optimization hasn't been solved yet

    Raises:
        ValidationError: If solution violates OptimizationSolution schema
    """
    solution = model.get_solution()  # Returns OptimizationSolution (Pydantic)
    if not solution:
        return None

    # Validate schema compliance (fail-fast)
    from src.optimization.result_schema import OptimizationSolution
    if not isinstance(solution, OptimizationSolution):
        raise ValidationError(
            f"Model returned {type(solution).__name__} instead of OptimizationSolution. "
            "Model must conform to interface specification."
        )

    # Convert production schedule
    production_schedule = _create_production_schedule(
        model,
        solution,
        inventory_snapshot_date
    )

    # Get shipments from unified model
    if hasattr(model, 'extract_shipments'):
        shipments = model.extract_shipments() or []
    else:
        shipments = []
        logger.warning("Model does not have shipment extraction method")

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
        'model_solution': solution,  # Include solution for daily snapshot MODEL MODE
    }


def _create_production_schedule(
    model: Any,
    solution: 'OptimizationSolution',  # Now Pydantic validated
    inventory_snapshot_date: Optional[Date] = None
) -> ProductionSchedule:
    """Convert optimization solution to ProductionSchedule object.

    Args:
        model: BaseOptimizationModel instance
        solution: Pydantic-validated OptimizationSolution
        inventory_snapshot_date: Optional date when initial inventory was loaded

    Returns:
        ProductionSchedule with batches and labor hours
    """

    # Get manufacturing site ID from model
    if hasattr(model, 'manufacturing_nodes') and model.manufacturing_nodes:
        first_mfg_node = list(model.manufacturing_nodes)[0]
        # Extract ID (handle both object and string)
        manufacturing_site_id = first_mfg_node if isinstance(first_mfg_node, str) else first_mfg_node.id
    else:
        manufacturing_site_id = "6122"  # Fallback

    batches = []

    # CREATE BATCHES FROM INITIAL INVENTORY
    if hasattr(model, 'initial_inventory') and model.initial_inventory and inventory_snapshot_date:
        for key, quantity in model.initial_inventory.items():
            if quantity > 0:
                # Parse 4-tuple key: (loc, prod, prod_date, state)
                if len(key) == 4:
                    location_id, product_id, prod_date, state = key
                elif len(key) == 2:
                    # Fallback for 2-tuple
                    location_id, product_id = key
                    prod_date = inventory_snapshot_date
                else:
                    continue  # Skip invalid keys

                # Create virtual batch for initial inventory
                batch = ProductionBatch(
                    id=f"INIT-{location_id}-{product_id}",
                    product_id=product_id,
                    manufacturing_site_id=location_id,
                    production_date=prod_date,
                    quantity=quantity,
                    labor_hours_used=0,  # Initial inventory has no labor cost
                    production_cost=0,  # Initial inventory is sunk cost
                )
                batches.append(batch)

    # Create ProductionBatch objects from Pydantic solution
    # SIMPLIFIED: solution.production_batches is guaranteed to exist (Pydantic validates)
    logger.info(f"Converting {len(solution.production_batches)} Pydantic production batches to ProductionBatch objects")
    for idx, batch_result in enumerate(solution.production_batches):
        batch = ProductionBatch(
            id=f"OPT-BATCH-{idx+1:04d}",
            product_id=batch_result.product,
            manufacturing_site_id=manufacturing_site_id,
            production_date=batch_result.date,
            quantity=batch_result.quantity,
            labor_hours_used=0,  # Will aggregate from daily totals
            production_cost=batch_result.quantity * model.cost_structure.production_cost_per_unit,
        )
        batches.append(batch)

    logger.info(f"Total batches (INIT + OPT): {len(batches)}, INIT batches: {sum(1 for b in batches if b.id.startswith('INIT-'))}")

    # Build daily totals from batches (EXCLUDING initial inventory - not production!)
    daily_totals: Dict[Date, float] = {}
    for batch in batches:
        # Only include actual production batches, not initial inventory
        if not batch.id.startswith('INIT-'):
            daily_totals[batch.production_date] = daily_totals.get(batch.production_date, 0) + batch.quantity

    logger.info(f"Daily totals (production only): {len(daily_totals)} dates, total: {sum(daily_totals.values()):.0f} units")
    if len(daily_totals) == 0 and len(batches) > 0:
        logger.error("CRITICAL: All batches are INIT batches! No actual production extracted from solution.")

    # Get labor hours by date from Pydantic solution
    # SIMPLIFIED: solution.labor_hours_by_date is guaranteed to be Dict[Date, LaborHoursBreakdown]
    daily_labor_hours = solution.labor_hours_by_date

    # Update batch labor hours proportionally
    for batch in batches:
        date_total = daily_totals.get(batch.production_date, 1)
        if date_total > 0:
            proportion = batch.quantity / date_total

            # Extract labor hours from LaborHoursBreakdown
            # NO isinstance() check needed - Pydantic guarantees it's LaborHoursBreakdown
            labor_breakdown = daily_labor_hours.get(batch.production_date)
            if labor_breakdown:
                batch.labor_hours_used = labor_breakdown.used * proportion

    # Determine actual schedule start date
    actual_start_date = (
        inventory_snapshot_date if inventory_snapshot_date
        else min(b.production_date for b in batches) if batches
        else model.start_date
    )

    # Calculate total labor hours
    # SIMPLIFIED: Always LaborHoursBreakdown, just sum .used field
    total_labor_hours = sum(
        labor_breakdown.used
        for labor_breakdown in daily_labor_hours.values()
    )

    # Build ProductionSchedule
    return ProductionSchedule(
        manufacturing_site_id=manufacturing_site_id,  # Use variable determined above
        schedule_start_date=actual_start_date,
        schedule_end_date=model.end_date,
        production_batches=batches,
        daily_totals=daily_totals,
        daily_labor_hours=daily_labor_hours,
        infeasibilities=[],  # Optimal solution is feasible
        total_units=sum(b.quantity for b in batches if not b.id.startswith('INIT-')),  # Exclude initial inventory from production total
        total_labor_hours=total_labor_hours,
    )


def _create_truck_plan_from_optimization(model: Any, shipments: List[Shipment]) -> TruckLoadPlan:
    """Create TruckLoadPlan from optimization results.

    Args:
        model: UnifiedNodeModel instance
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

    # Note: SlidingWindowModel produces aggregate shipments without truck assignments
    # This is expected (model optimizes flows, not truck loading details)
    # Only warn if using cohort model (which should assign trucks)
    if len(unassigned_shipments) > 0 and len(shipments) > 0:
        pct_unassigned = 100 * len(unassigned_shipments) / len(shipments)
        # Suppress warning for aggregate models (100% unassigned is normal)
        if pct_unassigned > 50 and pct_unassigned < 99:
            logger.warning(
                f"{pct_unassigned:.1f}% of shipments are unassigned to trucks. "
                f"This may indicate: (1) model solved without truck_schedules, "
                f"(2) routes don't align with truck destinations, or "
                f"(3) limited route enumeration (max_routes_per_destination too low)"
            )

    # Create TruckLoad objects
    loads: List[TruckLoad] = []

    for (truck_id, departure_date), shipment_list in truck_shipments.items():
        # Find the truck schedule - handle both model types
        truck_schedule = None

        # Get truck schedules list
        if hasattr(model, 'truck_schedules'):
            if hasattr(model.truck_schedules, 'schedules'):
                # Legacy: TruckScheduleCollection
                truck_list = model.truck_schedules.schedules
            elif isinstance(model.truck_schedules, list):
                # Unified: List[UnifiedTruckSchedule]
                truck_list = model.truck_schedules
            else:
                truck_list = []
        else:
            truck_list = []

        for truck in truck_list:
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

        # Get truck name (handle both TruckSchedule and UnifiedTruckSchedule)
        truck_name = truck_schedule.truck_name if hasattr(truck_schedule, 'truck_name') else truck_schedule.id

        truck_load = TruckLoad(
            truck_schedule_id=truck_schedule.id,
            truck_name=truck_name,
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
    """Convert optimization solution dict to TotalCostBreakdown object.

    Builds cost breakdown from solution dict fields for SlidingWindowModel.

    Args:
        model: BaseOptimizationModel instance
        solution: Solution dict from model.get_solution()

    Returns:
        TotalCostBreakdown object
    """
    # For SlidingWindowModel, solution is a dict, not OptimizationSolution
    # Build cost breakdown manually from solution fields
    return _create_cost_breakdown_legacy(model, solution)


def _create_cost_breakdown_legacy(model: Any, solution: dict) -> TotalCostBreakdown:
    """DEPRECATED: Old defensive cost breakdown creation.

    Kept for reference only. New code should use solution.costs directly.
    """
    # This entire function (~100 lines) is replaced by: return solution.costs

    # Extract costs from solution
    labor_cost = solution.get('total_labor_cost', 0)
    production_cost = solution.get('total_production_cost', 0)
    transport_cost = solution.get('total_transport_cost', 0)
    truck_cost = solution.get('total_truck_cost', 0)
    shortage_cost = solution.get('total_shortage_cost', 0)
    freeze_cost = solution.get('total_freeze_cost', 0)  # Freeze/thaw state transition costs
    thaw_cost = solution.get('total_thaw_cost', 0)
    holding_cost = solution.get('total_holding_cost', 0)  # Pallet-based storage costs

    # Use actual total cost from model objective (includes all costs like changeover)
    # Don't calculate from components - some costs (changeover, pallet entry) not broken down
    total_cost = solution.get('total_cost', 0)

    # Get daily labor hours and costs
    labor_hours_by_date = solution.get('labor_hours_by_date', {})
    labor_cost_by_date = solution.get('labor_cost_by_date', {})

    # Convert labor hours to nested format for daily_breakdown
    daily_breakdown_nested: Dict[Date, Dict[str, float]] = {}
    for date_val, total_cost_val in labor_cost_by_date.items():
        labor_hours = labor_hours_by_date.get(date_val, 0)
        # labor_hours is a float from SlidingWindowModel, not an object
        if labor_hours:
            daily_breakdown_nested[date_val] = {
                'total_hours': labor_hours,
                'fixed_hours': 0,  # Not separately tracked
                'overtime_hours': 0,  # Not separately tracked
                'fixed_cost': 0,
                'overtime_cost': 0,
                'non_fixed_cost': 0,
                'total_cost': total_cost_val,
            }

    # Calculate total labor hours (handle both dict and float values)
    total_labor_hours = sum(labor_hours_by_date.values())

    # Build labor cost breakdown
    labor_breakdown = LaborCostBreakdown(
        total_cost=labor_cost,
        fixed_hours_cost=0,
        overtime_cost=0,
        non_fixed_labor_cost=0,
        total_hours=total_labor_hours,
        fixed_hours=0,
        overtime_hours=0,
        non_fixed_hours=0,
        daily_breakdown=daily_breakdown_nested,
    )

    # Build production cost breakdown
    production_by_date_product = solution.get('production_by_date_product', {})

    # Aggregate by date
    cost_by_date: Dict[Date, float] = {}
    total_units = sum(production_by_date_product.values())
    if total_units > 0:
        for key, qty in production_by_date_product.items():
            # Handle both formats: (date, product) or (node, product, date)
            if len(key) == 2:
                date, product = key
            else:  # len(key) == 3
                node, product, date = key

            proportion = qty / total_units
            cost_by_date[date] = cost_by_date.get(date, 0) + (proportion * production_cost)

    # Aggregate by product
    cost_by_product: Dict[str, float] = {}
    if total_units > 0:
        for key, qty in production_by_date_product.items():
            # Handle both formats: (date, product) or (node, product, date)
            if len(key) == 2:
                date, product = key
            else:  # len(key) == 3
                node, product, date = key

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

    # Build holding cost breakdown (pallet-based storage costs)
    holding_breakdown = HoldingCostBreakdown(
        total_cost=holding_cost,
        frozen_cost=frozen_holding_cost,
        ambient_cost=ambient_holding_cost,
        cost_by_location={},  # Could populate from cohort_inventory if needed
        cost_by_product={},  # Could populate from cohort_inventory if needed
        cost_by_date={},  # Could populate from cohort_inventory if needed
    )

    # Build total cost breakdown
    return TotalCostBreakdown(
        total_cost=total_cost,
        labor=labor_breakdown,
        production=production_breakdown,
        transport=transport_breakdown,
        holding=holding_breakdown,
        waste=waste_breakdown,
        cost_per_unit_delivered=total_cost / total_units if total_units > 0 else 0,
    )
