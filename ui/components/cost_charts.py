"""Cost visualization components using Plotly."""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from src.costs.cost_breakdown import TotalCostBreakdown


def render_cost_pie_chart(cost_breakdown: TotalCostBreakdown, height: int = 400):
    """
    Render cost proportions as a pie chart.

    Args:
        cost_breakdown: TotalCostBreakdown instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    proportions = cost_breakdown.get_cost_proportions()

    labels = ['Labor', 'Production', 'Transport', 'Waste']
    values = [
        cost_breakdown.labor.total,
        cost_breakdown.production.total,
        cost_breakdown.transport.total,
        cost_breakdown.waste.total,
    ]
    colors = ['#FF6B6B', '#4ECDC4', '#95E1D3', '#FFE66D']

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors),
        hovertemplate='<b>%{label}</b><br>Cost: $%{value:,.2f}<br>Proportion: %{percent}<extra></extra>',
        textposition='auto',
        textinfo='label+percent',
    )])

    fig.update_layout(
        title='Cost Breakdown by Component',
        title_x=0.5,
        height=height,
        showlegend=True,
    )

    return fig


def render_cost_breakdown_chart(cost_breakdown: TotalCostBreakdown, height: int = 400):
    """
    Render cost components as a horizontal bar chart.

    Args:
        cost_breakdown: TotalCostBreakdown instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    components = ['Labor', 'Production', 'Transport', 'Waste']
    costs = [
        cost_breakdown.labor.total,
        cost_breakdown.production.total,
        cost_breakdown.transport.total,
        cost_breakdown.waste.total,
    ]
    colors = ['#FF6B6B', '#4ECDC4', '#95E1D3', '#FFE66D']

    fig = go.Figure(data=[
        go.Bar(
            y=components,
            x=costs,
            orientation='h',
            marker=dict(color=colors),
            text=[f'${c:,.2f}' for c in costs],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Cost: $%{x:,.2f}<extra></extra>',
        )
    ])

    fig.update_layout(
        title='Cost Components',
        title_x=0.5,
        xaxis_title='Cost ($)',
        yaxis_title='Component',
        height=height,
        showlegend=False,
    )

    return fig


def render_cost_by_category_chart(cost_breakdown: TotalCostBreakdown, height: int = 400):
    """
    Alias for render_cost_pie_chart for backward compatibility.
    Renders cost breakdown by category as a pie chart.

    Args:
        cost_breakdown: TotalCostBreakdown instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    return render_cost_pie_chart(cost_breakdown, height)


def render_daily_cost_chart(cost_breakdown: TotalCostBreakdown, height: int = 400):
    """
    Render daily cost breakdown as a stacked bar chart.

    Args:
        cost_breakdown: TotalCostBreakdown instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    # Extract daily labor costs
    labor_daily = cost_breakdown.labor.daily_breakdown

    if not labor_daily:
        # Return empty figure
        fig = go.Figure()
        fig.add_annotation(
            text="No daily cost data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Daily Cost Breakdown',
            title_x=0.5,
            height=height,
        )
        return fig

    # Extract daily production costs
    production_daily = cost_breakdown.production.cost_by_date

    # Get all dates
    all_dates = sorted(set(list(labor_daily.keys()) + list(production_daily.keys())))

    # Prepare data
    dates_str = [str(d) for d in all_dates]
    labor_costs = [labor_daily.get(d, {}).get('total_cost', 0) for d in all_dates]
    production_costs = [production_daily.get(d, 0) for d in all_dates]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Labor',
        x=dates_str,
        y=labor_costs,
        marker=dict(color='#FF6B6B'),
        hovertemplate='Date: %{x}<br>Labor Cost: $%{y:,.2f}<extra></extra>',
    ))

    fig.add_trace(go.Bar(
        name='Production',
        x=dates_str,
        y=production_costs,
        marker=dict(color='#4ECDC4'),
        hovertemplate='Date: %{x}<br>Production Cost: $%{y:,.2f}<extra></extra>',
    ))

    fig.update_layout(
        title='Daily Cost Breakdown',
        title_x=0.5,
        xaxis_title='Date',
        yaxis_title='Cost ($)',
        barmode='stack',
        height=height,
        hovermode='x unified',
    )

    return fig


def render_labor_cost_breakdown(cost_breakdown: TotalCostBreakdown, height: int = 400):
    """
    Render labor cost breakdown (fixed/overtime/non-fixed).

    Args:
        cost_breakdown: TotalCostBreakdown instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    labor = cost_breakdown.labor

    categories = ['Fixed Hours', 'Overtime', 'Non-Fixed Labor']
    costs = [
        labor.fixed_hours_cost,
        labor.overtime_cost,
        labor.non_fixed_labor_cost,
    ]
    hours = [
        labor.fixed_hours,
        labor.overtime_hours,
        labor.non_fixed_hours,
    ]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Cost',
        x=categories,
        y=costs,
        marker=dict(color='#FF6B6B'),
        text=[f'${c:,.2f}' for c in costs],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Cost: $%{y:,.2f}<extra></extra>',
    ))

    fig.update_layout(
        title=f'Labor Cost Breakdown (Total: {labor.total_hours:.1f} hours)',
        title_x=0.5,
        yaxis_title='Cost ($)',
        height=height,
        showlegend=False,
    )

    return fig


def render_transport_cost_by_route(cost_breakdown: TotalCostBreakdown, height: int = 500):
    """
    Render transport cost by route.

    Args:
        cost_breakdown: TotalCostBreakdown instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    transport = cost_breakdown.transport
    cost_by_route = transport.cost_by_route

    if not cost_by_route:
        fig = go.Figure()
        fig.add_annotation(
            text="No route cost data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Transport Cost by Route',
            title_x=0.5,
            height=height,
        )
        return fig

    # Sort by cost (descending)
    sorted_routes = sorted(cost_by_route.items(), key=lambda x: x[1], reverse=True)
    routes = [r[0] for r in sorted_routes]
    costs = [r[1] for r in sorted_routes]

    fig = go.Figure(data=[
        go.Bar(
            y=routes,
            x=costs,
            orientation='h',
            marker=dict(color='#95E1D3'),
            text=[f'${c:,.2f}' for c in costs],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Cost: $%{x:,.2f}<extra></extra>',
        )
    ])

    fig.update_layout(
        title='Transport Cost by Route',
        title_x=0.5,
        xaxis_title='Cost ($)',
        yaxis_title='Route',
        height=height,
        showlegend=False,
    )

    return fig


def render_cost_waterfall(cost_breakdown: TotalCostBreakdown, height: int = 400):
    """
    Render cost per unit waterfall chart.

    Args:
        cost_breakdown: TotalCostBreakdown instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    labor = cost_breakdown.labor
    production = cost_breakdown.production
    transport = cost_breakdown.transport
    waste = cost_breakdown.waste

    total_units = production.total_units_produced
    if total_units == 0:
        total_units = 1  # Avoid division by zero

    # Calculate per-unit costs
    labor_per_unit = labor.total / total_units
    production_per_unit = production.total / total_units
    transport_per_unit = transport.total / total_units
    waste_per_unit = waste.total / total_units

    fig = go.Figure(go.Waterfall(
        name='Cost Components',
        orientation='v',
        measure=['relative', 'relative', 'relative', 'relative', 'total'],
        x=['Labor', 'Production', 'Transport', 'Waste', 'Total'],
        y=[labor_per_unit, production_per_unit, transport_per_unit, waste_per_unit, 0],
        text=[f'${v:.3f}' for v in [labor_per_unit, production_per_unit, transport_per_unit, waste_per_unit, cost_breakdown.cost_per_unit_delivered]],
        textposition='outside',
        connector={'line': {'color': 'rgb(63, 63, 63)'}},
    ))

    fig.update_layout(
        title=f'Cost Per Unit Breakdown (Total: ${cost_breakdown.cost_per_unit_delivered:.2f}/unit)',
        title_x=0.5,
        yaxis_title='Cost Per Unit ($)',
        height=height,
        showlegend=False,
    )

    return fig
