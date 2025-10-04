"""Adapters to convert optimization results to heuristic-compatible format.

This module provides functions to normalize optimization model outputs
into the same data structures used by heuristic planning, enabling
the Results UI to display both types of results seamlessly.
"""

from typing import Dict, Any, Optional
from datetime import date as Date
from src.production.scheduler import ProductionSchedule, ProductionBatch
from src.costs.cost_breakdown import (
    TotalCostBreakdown,
    LaborCostBreakdown,
    ProductionCostBreakdown,
    TransportCostBreakdown,
    WasteCostBreakdown,
)
from src.distribution.truck_loader import TruckLoadPlan


def adapt_optimization_results(model: Any, result: dict) -> Optional[Dict[str, Any]]:
    """
    Convert optimization results to heuristic-compatible format.

    Args:
        model: IntegratedProductionDistributionModel instance
        result: Optimization result dictionary from session state

    Returns:
        Dictionary with keys: production_schedule, shipments, truck_plan, cost_breakdown
        Returns None if optimization hasn't been solved yet
    """
    solution = model.get_solution()
    if not solution:
        return None

    # Convert production schedule
    production_schedule = _create_production_schedule(model, solution)

    # Get shipments (model already has this method)
    shipments = model.get_shipment_plan() or []

    # Truck plan may not be available from optimization
    # For now, return a minimal placeholder
    truck_plan = _create_placeholder_truck_plan()

    # Convert cost breakdown
    cost_breakdown = _create_cost_breakdown(model, solution)

    return {
        'production_schedule': production_schedule,
        'shipments': shipments,
        'truck_plan': truck_plan,
        'cost_breakdown': cost_breakdown,
    }


def _create_production_schedule(model: Any, solution: dict) -> ProductionSchedule:
    """Convert optimization solution to ProductionSchedule object."""

    # Create ProductionBatch objects from solution
    batches = []
    for idx, batch_dict in enumerate(solution.get('production_batches', [])):
        batch = ProductionBatch(
            id=f"OPT-BATCH-{idx+1:04d}",
            product_id=batch_dict['product'],
            manufacturing_site_id=model.manufacturing_site.id,
            production_date=batch_dict['date'],
            quantity=batch_dict['quantity'],
            labor_hours_used=0,  # Will aggregate from daily totals
            production_cost=0,  # Can calculate if needed
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

    # Build ProductionSchedule
    return ProductionSchedule(
        manufacturing_site_id=model.manufacturing_site.id,
        schedule_start_date=model.start_date,
        schedule_end_date=model.end_date,
        production_batches=batches,
        daily_totals=daily_totals,
        daily_labor_hours=daily_labor_hours,
        infeasibilities=[],  # Optimal solution is feasible
        total_units=sum(b.quantity for b in batches),
        total_labor_hours=sum(daily_labor_hours.values()),
        requirements=None,  # Optimization doesn't track original requirements
    )


def _create_placeholder_truck_plan() -> TruckLoadPlan:
    """Create a minimal truck plan placeholder for optimization results.

    The optimization model uses route-based distribution, not truck-based.
    This placeholder allows UI components to handle the absence of truck data gracefully.
    """
    return TruckLoadPlan(
        manufacturing_site_id="optimization",
        loads=[],
        total_trucks=0,
        total_units=0,
        total_cost=0,
        infeasibilities=[],
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
        daily_breakdown=labor_cost_by_date,
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
        expired_units=0,  # Not tracked separately
        expired_cost=0,
        shortage_units=total_shortage_units,
        shortage_cost=shortage_cost,
        waste_by_location={},
        waste_by_product={},
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
