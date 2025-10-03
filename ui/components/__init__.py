"""Reusable UI components for the planning application."""

from .network_graph import render_network_graph, render_connectivity_matrix
from .cost_charts import (
    render_cost_pie_chart,
    render_cost_breakdown_chart,
    render_cost_by_category_chart,
    render_daily_cost_chart,
    render_labor_cost_breakdown,
    render_transport_cost_by_route,
    render_cost_waterfall,
)
from .production_gantt import (
    render_production_gantt,
    render_labor_hours_chart,
    render_daily_production_chart,
    render_capacity_utilization_chart,
)
from .truck_loading_timeline import (
    render_truck_loading_timeline,
    render_truck_utilization_chart,
    render_shipments_by_destination_chart,
    render_daily_truck_count_chart,
)
from .data_tables import (
    render_production_batches_table,
    render_shipments_table,
    render_truck_loads_table,
    render_truck_loadings_table,
    render_unassigned_shipments_table,
    render_cost_summary_table,
    render_cost_breakdown_table,
    render_labor_breakdown_table,
    render_daily_breakdown_table,
)
from .date_filter import (
    render_date_range_filter,
    apply_date_filter,
    get_quick_range_dates,
    calculate_date_stats,
    sync_url_params,
)

__all__ = [
    # Network visualization
    'render_network_graph',
    'render_connectivity_matrix',
    # Cost charts
    'render_cost_pie_chart',
    'render_cost_breakdown_chart',
    'render_cost_by_category_chart',
    'render_daily_cost_chart',
    'render_labor_cost_breakdown',
    'render_transport_cost_by_route',
    'render_cost_waterfall',
    # Production charts
    'render_production_gantt',
    'render_labor_hours_chart',
    'render_daily_production_chart',
    'render_capacity_utilization_chart',
    # Truck loading charts
    'render_truck_loading_timeline',
    'render_truck_utilization_chart',
    'render_shipments_by_destination_chart',
    'render_daily_truck_count_chart',
    # Data tables
    'render_production_batches_table',
    'render_shipments_table',
    'render_truck_loads_table',
    'render_truck_loadings_table',
    'render_unassigned_shipments_table',
    'render_cost_summary_table',
    'render_cost_breakdown_table',
    'render_labor_breakdown_table',
    'render_daily_breakdown_table',
    # Date filter
    'render_date_range_filter',
    'apply_date_filter',
    'get_quick_range_dates',
    'calculate_date_stats',
    'sync_url_params',
]
