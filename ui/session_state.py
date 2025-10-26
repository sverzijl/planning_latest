"""Session state management for the planning application.

Provides centralized management of Streamlit session state for:
- Parsed data (forecast, locations, routes, etc.)
- Planning objects (graph builder, route finder, scheduler)
- Planning results (production schedule, shipments, truck plan, costs)
- UI state (workflow progress, flags)
"""

import streamlit as st
from typing import Optional, Any
from src.models.forecast import Forecast
from src.models.location import Location
from src.models.route import Route
from src.models.labor_calendar import LaborCalendar
from src.models.truck_schedule import TruckSchedule, TruckScheduleCollection
from src.models.cost_structure import CostStructure
from src.models.manufacturing import ManufacturingSite
from src.network import NetworkGraphBuilder, RouteFinder
from src.models.production_schedule import ProductionSchedule
from src.models.truck_load import TruckLoadPlan
from src.models.shipment import Shipment
from src.costs import CostCalculator
from src.costs.cost_breakdown import TotalCostBreakdown


def initialize_session_state():
    """Initialize all session state variables with defaults."""
    defaults = {
        # Data upload flags
        'data_uploaded': False,
        'planning_complete': False,
        'current_step': 0,

        # Parsed data
        'forecast': None,
        'locations': None,
        'routes': None,
        'labor_calendar': None,
        'truck_schedules': None,
        'cost_structure': None,
        'manufacturing_site': None,
        'initial_inventory': None,
        'product_aliases': None,

        # Optimization results
        'optimization_complete': False,
        'optimization_result': None,
        'optimization_model': None,

        # Metadata
        'forecast_filename': None,
        'network_filename': None,
        'inventory_filename': None,
        'inventory_snapshot_date': None,

        # Workflow state (Phase A - New workflow system)
        'initial_workflow_step': 0,
        'weekly_workflow_step': 0,
        'daily_workflow_step': 0,
        'latest_solve_result': None,
        'latest_solve_path': None,
        'workflow_config': None,
    }

    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def clear_planning_results():
    """Clear planning results (but keep parsed data).

    Note: This is legacy. For new workflow system, use reset_workflow_step() instead.
    """
    st.session_state.planning_complete = False
    st.session_state.current_step = 0
    st.session_state.optimization_complete = False
    st.session_state.optimization_result = None
    st.session_state.optimization_model = None


def clear_all_data():
    """Clear all data and results."""
    st.session_state.data_uploaded = False
    st.session_state.planning_complete = False
    st.session_state.current_step = 0
    st.session_state.forecast = None
    st.session_state.locations = None
    st.session_state.routes = None
    st.session_state.labor_calendar = None
    st.session_state.truck_schedules = None
    st.session_state.cost_structure = None
    st.session_state.manufacturing_site = None
    st.session_state.optimization_complete = False
    st.session_state.optimization_result = None
    st.session_state.optimization_model = None
    st.session_state.forecast_filename = None
    st.session_state.network_filename = None
    st.session_state.initial_inventory = None
    st.session_state.product_aliases = None


# ========== Data Storage Functions ==========

def store_parsed_data(
    forecast: Forecast,
    locations: list[Location],
    routes: list[Route],
    labor_calendar: LaborCalendar,
    truck_schedules: TruckScheduleCollection,
    cost_structure: CostStructure,
    manufacturing_site: ManufacturingSite,
    forecast_filename: str = None,
    network_filename: str = None,
    initial_inventory: Optional[Any] = None,
    product_aliases: Optional[Any] = None,
    products: Optional[Any] = None,
    inventory_filename: str = None,
    inventory_snapshot_date: Optional[Any] = None,
):
    """Store parsed data in session state.

    Note: truck_schedules should be a TruckScheduleCollection, not a list.
    If you have a list from the parser, wrap it:
        TruckScheduleCollection(schedules=truck_schedules_list)
    """
    st.session_state.forecast = forecast
    st.session_state.locations = locations
    st.session_state.routes = routes
    st.session_state.labor_calendar = labor_calendar
    st.session_state.truck_schedules = truck_schedules
    st.session_state.cost_structure = cost_structure
    st.session_state.manufacturing_site = manufacturing_site
    st.session_state.initial_inventory = initial_inventory
    st.session_state.product_aliases = product_aliases
    st.session_state.products = products
    st.session_state.forecast_filename = forecast_filename
    st.session_state.network_filename = network_filename
    st.session_state.inventory_filename = inventory_filename
    st.session_state.inventory_snapshot_date = inventory_snapshot_date
    st.session_state.data_uploaded = True


# Legacy functions - kept for backward compatibility with Results page
# These will be removed when Results page is updated to use workflow results

def store_planning_objects(
    graph_builder: NetworkGraphBuilder,
    route_finder: RouteFinder,
):
    """DEPRECATED: Store planning objects in session state.

    Legacy function from Phase 2 heuristic planning. No longer used by workflow system.
    """
    pass  # No-op


def store_planning_results(
    production_schedule: ProductionSchedule,
    shipments: list[Shipment],
    truck_plan: TruckLoadPlan,
    cost_breakdown: TotalCostBreakdown,
):
    """DEPRECATED: Store planning results in session state.

    Legacy function from Phase 2. Results page may still use this.
    Will be removed when Results page is updated to use WorkflowResult.
    """
    st.session_state.production_schedule = production_schedule
    st.session_state.shipments = shipments
    st.session_state.truck_plan = truck_plan
    st.session_state.cost_breakdown = cost_breakdown
    st.session_state.planning_complete = True


def store_optimization_results(model: Any, result: dict):
    """Store optimization results in session state.

    Args:
        model: The optimization model (IntegratedProductionDistributionModel)
        result: Dictionary containing optimization results
    """
    st.session_state.optimization_model = model
    st.session_state.optimization_result = result
    st.session_state.optimization_complete = True


# ========== Data Retrieval Functions ==========

def get_parsed_data() -> Optional[dict]:
    """Get all parsed data as a dictionary."""
    if not st.session_state.data_uploaded:
        return None

    return {
        'forecast': st.session_state.forecast,
        'locations': st.session_state.locations,
        'routes': st.session_state.routes,
        'labor_calendar': st.session_state.labor_calendar,
        'truck_schedules': st.session_state.truck_schedules,
        'cost_structure': st.session_state.cost_structure,
        'manufacturing_site': st.session_state.manufacturing_site,
        'initial_inventory': st.session_state.initial_inventory,
        'product_aliases': st.session_state.product_aliases,
        'products': st.session_state.get('products'),
    }


def get_initial_inventory_dict() -> dict:
    """Get initial inventory in optimization model format.

    Returns:
        Dictionary mapping (location_id, product_id) to quantity in units.
        Empty dict if no inventory loaded.
    """
    inventory = st.session_state.get('initial_inventory')
    if inventory and hasattr(inventory, 'to_optimization_dict'):
        return inventory.to_optimization_dict()
    return {}


def get_planning_results() -> Optional[dict]:
    """Get all planning results as a dictionary."""
    if not st.session_state.planning_complete:
        return None

    return {
        'production_schedule': st.session_state.production_schedule,
        'shipments': st.session_state.shipments,
        'truck_plan': st.session_state.truck_plan,
        'cost_breakdown': st.session_state.cost_breakdown,
    }


def get_optimization_results() -> Optional[dict]:
    """Get optimization results as a dictionary.

    Returns:
        Dictionary with 'model' and 'result' keys if optimization is complete,
        None otherwise.
    """
    if not st.session_state.get('optimization_complete', False):
        return None

    return {
        'model': st.session_state.optimization_model,
        'result': st.session_state.optimization_result,
    }


# ========== Status Check Functions ==========

def is_data_uploaded() -> bool:
    """Check if data has been uploaded and parsed."""
    return st.session_state.get('data_uploaded', False)


def is_planning_complete() -> bool:
    """Check if planning workflow is complete."""
    return st.session_state.get('planning_complete', False)


def is_optimization_complete() -> bool:
    """Check if optimization is complete.

    Returns:
        True if optimization has been run and results are stored, False otherwise.
    """
    return st.session_state.get('optimization_complete', False)


def get_current_step() -> int:
    """Get current planning workflow step."""
    return st.session_state.get('current_step', 0)


def set_current_step(step: int):
    """Set current planning workflow step."""
    st.session_state.current_step = step


# ========== Helper Functions ==========

def get_summary_stats() -> dict:
    """Get summary statistics from parsed data."""
    if not is_data_uploaded():
        return {}

    stats = {
        'forecast_entries': len(st.session_state.forecast.entries) if st.session_state.forecast else 0,
        'locations': len(st.session_state.locations) if st.session_state.locations else 0,
        'routes': len(st.session_state.routes) if st.session_state.routes else 0,
        'labor_days': len(st.session_state.labor_calendar.days) if st.session_state.labor_calendar else 0,
        'truck_schedules': len(st.session_state.truck_schedules) if st.session_state.truck_schedules else 0,
    }

    if st.session_state.forecast:
        forecast = st.session_state.forecast
        stats['total_demand'] = sum(e.quantity for e in forecast.entries)
        stats['locations_in_forecast'] = len(set(e.location_id for e in forecast.entries))
        stats['products_in_forecast'] = len(set(e.product_id for e in forecast.entries))

        # Date range
        dates = [e.forecast_date for e in forecast.entries]
        if dates:
            stats['date_range_start'] = min(dates)
            stats['date_range_end'] = max(dates)
            stats['date_range_days'] = (max(dates) - min(dates)).days + 1

    return stats


def get_planning_summary() -> dict:
    """Get summary statistics from planning results."""
    if not is_planning_complete():
        return {}

    schedule = st.session_state.production_schedule
    shipments = st.session_state.shipments
    truck_plan = st.session_state.truck_plan
    costs = st.session_state.cost_breakdown

    summary = {}

    if schedule:
        summary['production_batches'] = len(schedule.production_batches)
        summary['total_units'] = schedule.total_units
        summary['total_labor_hours'] = schedule.total_labor_hours
        summary['production_is_feasible'] = schedule.is_feasible()

    if shipments:
        summary['shipments_count'] = len(shipments)
        summary['total_shipment_units'] = sum(s.quantity for s in shipments)

    if truck_plan:
        summary['trucks_used'] = truck_plan.total_trucks_used
        summary['average_utilization'] = truck_plan.average_utilization
        summary['truck_plan_is_feasible'] = truck_plan.is_feasible()
        summary['unassigned_shipments'] = len(truck_plan.unassigned_shipments)

    if costs:
        summary['total_cost'] = costs.total_cost
        summary['cost_per_unit'] = costs.cost_per_unit_delivered
        summary['labor_cost'] = costs.labor.total_cost
        summary['production_cost'] = costs.production.total_cost
        summary['transport_cost'] = costs.transport.total_cost
        summary['waste_cost'] = costs.waste.total_cost

    return summary


def show_data_status_card():
    """Show a status card for data upload state."""
    if is_data_uploaded():
        st.success("✅ Data Uploaded")
        stats = get_summary_stats()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Locations", stats.get('locations', 0))
            st.metric("Routes", stats.get('routes', 0))
        with col2:
            st.metric("Forecast Entries", stats.get('forecast_entries', 0))
            st.metric("Products", stats.get('products_in_forecast', 0))
        with col3:
            st.metric("Labor Days", stats.get('labor_days', 0))
            st.metric("Truck Schedules", stats.get('truck_schedules', 0))
    else:
        st.warning("⚠️ No data uploaded. Please upload forecast and network configuration files.")
        if st.button("Go to Upload Page"):
            st.switch_page("Upload Data")


def show_planning_status_card():
    """Show a status card for planning completion state."""
    if is_planning_complete():
        st.success("✅ Planning Complete")
        summary = get_planning_summary()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Production Batches", summary.get('production_batches', 0))
            st.metric("Total Units", f"{summary.get('total_units', 0):,.0f}")
        with col2:
            st.metric("Shipments", summary.get('shipments_count', 0))
            st.metric("Trucks Used", summary.get('trucks_used', 0))
        with col3:
            st.metric("Total Cost", f"${summary.get('total_cost', 0):,.2f}")
            st.metric("Cost/Unit", f"${summary.get('cost_per_unit', 0):.2f}")
    else:
        st.info("ℹ️ Planning not yet run. Go to Planning Workflow to generate production and distribution plans.")
        if is_data_uploaded() and st.button("Go to Planning Workflow"):
            st.switch_page("Planning Workflow")


# ========== Workflow State Functions (Phase A) ==========

def store_workflow_result(result: Any, file_path: Optional[str] = None):
    """Store workflow solve result in session state.

    Args:
        result: WorkflowResult object from workflow execution
        file_path: Optional path where result was saved
    """
    st.session_state.latest_solve_result = result
    st.session_state.latest_solve_path = file_path


def get_latest_solve_result() -> Optional[Any]:
    """Get the most recent workflow solve result.

    Returns:
        WorkflowResult object or None
    """
    return st.session_state.get('latest_solve_result')


def has_latest_solve() -> bool:
    """Check if a solve result exists in session state.

    Returns:
        True if latest solve result exists, False otherwise
    """
    return st.session_state.get('latest_solve_result') is not None


def get_workflow_step(workflow_type: str) -> int:
    """Get current step for a workflow.

    Args:
        workflow_type: "initial", "weekly", or "daily"

    Returns:
        Current step index (0-based)
    """
    return st.session_state.get(f'{workflow_type}_workflow_step', 0)


def set_workflow_step(workflow_type: str, step: int):
    """Set current step for a workflow.

    Args:
        workflow_type: "initial", "weekly", or "daily"
        step: Step index to set (0-based)
    """
    st.session_state[f'{workflow_type}_workflow_step'] = step


def advance_workflow_step(workflow_type: str):
    """Advance to next step in workflow.

    Args:
        workflow_type: "initial", "weekly", or "daily"
    """
    current = get_workflow_step(workflow_type)
    set_workflow_step(workflow_type, current + 1)


def reset_workflow_step(workflow_type: str):
    """Reset workflow to first step.

    Args:
        workflow_type: "initial", "weekly", or "daily"
    """
    set_workflow_step(workflow_type, 0)
