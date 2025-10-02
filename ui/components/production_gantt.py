"""Production schedule visualization components using Plotly."""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime
from src.production.scheduler import ProductionSchedule


def render_production_gantt(production_schedule: ProductionSchedule, height: int = 500):
    """
    Render production schedule as a Gantt chart.

    Args:
        production_schedule: ProductionSchedule instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    batches = production_schedule.production_batches

    if not batches:
        fig = go.Figure()
        fig.add_annotation(
            text="No production batches to display",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Production Schedule (Gantt Chart)',
            title_x=0.5,
            height=height,
        )
        return fig

    # Prepare data for Gantt chart
    df_data = []
    for batch in batches:
        df_data.append({
            'Product': batch.product_id,
            'Start': datetime.combine(batch.production_date, datetime.min.time()),
            'Finish': datetime.combine(batch.production_date, datetime.max.time()),
            'Quantity': batch.quantity,
            'Labor Hours': batch.labor_hours_used,
            'Batch ID': batch.id,
        })

    df = pd.DataFrame(df_data)

    # Create Gantt chart using timeline
    fig = px.timeline(
        df,
        x_start='Start',
        x_end='Finish',
        y='Product',
        color='Product',
        hover_data=['Quantity', 'Labor Hours', 'Batch ID'],
        title='Production Schedule by Product',
    )

    # Update layout
    fig.update_yaxes(categoryorder='category ascending')
    fig.update_layout(
        title_x=0.5,
        xaxis_title='Production Date',
        yaxis_title='Product',
        height=height,
        showlegend=True,
    )

    return fig


def render_labor_hours_chart(production_schedule: ProductionSchedule, height: int = 400):
    """
    Render daily labor hours as a stacked bar chart.

    Args:
        production_schedule: ProductionSchedule instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    daily_labor = production_schedule.daily_labor_hours

    if not daily_labor:
        fig = go.Figure()
        fig.add_annotation(
            text="No labor hours data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Daily Labor Hours',
            title_x=0.5,
            height=height,
        )
        return fig

    # Sort by date
    sorted_dates = sorted(daily_labor.keys())
    dates_str = [str(d) for d in sorted_dates]
    hours = [daily_labor[d] for d in sorted_dates]

    # Get labor calendar to show capacity
    # For now, just show actual hours
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Labor Hours Used',
        x=dates_str,
        y=hours,
        marker=dict(color='#FF6B6B'),
        text=[f'{h:.1f}h' for h in hours],
        textposition='outside',
        hovertemplate='Date: %{x}<br>Hours: %{y:.1f}h<extra></extra>',
    ))

    # Add capacity line if available (12h fixed + 2h OT = 14h max)
    capacity = [14.0] * len(sorted_dates)
    fig.add_trace(go.Scatter(
        name='Max Capacity (14h)',
        x=dates_str,
        y=capacity,
        mode='lines',
        line=dict(color='red', dash='dash', width=2),
        hovertemplate='Max Capacity: %{y:.1f}h<extra></extra>',
    ))

    fig.update_layout(
        title='Daily Labor Hours vs. Capacity',
        title_x=0.5,
        xaxis_title='Date',
        yaxis_title='Hours',
        height=height,
        hovermode='x unified',
    )

    return fig


def render_daily_production_chart(production_schedule: ProductionSchedule, height: int = 400):
    """
    Render daily production quantities by product.

    Args:
        production_schedule: ProductionSchedule instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    batches = production_schedule.production_batches

    if not batches:
        fig = go.Figure()
        fig.add_annotation(
            text="No production data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Daily Production Quantities',
            title_x=0.5,
            height=height,
        )
        return fig

    # Group by date and product
    production_by_date_product = {}
    for batch in batches:
        key = (batch.production_date, batch.product_id)
        if key not in production_by_date_product:
            production_by_date_product[key] = 0
        production_by_date_product[key] += batch.quantity

    # Get all unique dates and products
    all_dates = sorted(set(k[0] for k in production_by_date_product.keys()))
    all_products = sorted(set(k[1] for k in production_by_date_product.keys()))

    # Create traces for each product
    fig = go.Figure()

    for product in all_products:
        quantities = [production_by_date_product.get((d, product), 0) for d in all_dates]
        fig.add_trace(go.Bar(
            name=product,
            x=[str(d) for d in all_dates],
            y=quantities,
            hovertemplate=f'<b>{product}</b><br>Date: %{{x}}<br>Quantity: %{{y:,.0f}} units<extra></extra>',
        ))

    fig.update_layout(
        title='Daily Production Quantities by Product',
        title_x=0.5,
        xaxis_title='Date',
        yaxis_title='Quantity (units)',
        barmode='stack',
        height=height,
        hovermode='x unified',
    )

    return fig


def render_capacity_utilization_chart(production_schedule: ProductionSchedule, height: int = 400):
    """
    Render daily capacity utilization.

    Args:
        production_schedule: ProductionSchedule instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    daily_totals = production_schedule.daily_totals

    if not daily_totals:
        fig = go.Figure()
        fig.add_annotation(
            text="No capacity data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Daily Capacity Utilization',
            title_x=0.5,
            height=height,
        )
        return fig

    # Assume 1400 units/hour * 14 hours = 19,600 max daily capacity
    MAX_DAILY_CAPACITY = 19600

    sorted_dates = sorted(daily_totals.keys())
    dates_str = [str(d) for d in sorted_dates]
    quantities = [daily_totals[d] for d in sorted_dates]
    utilization = [(q / MAX_DAILY_CAPACITY) * 100 for q in quantities]

    fig = go.Figure()

    # Bar chart for quantities
    fig.add_trace(go.Bar(
        name='Production',
        x=dates_str,
        y=quantities,
        yaxis='y',
        marker=dict(color='#4ECDC4'),
        hovertemplate='Date: %{x}<br>Production: %{y:,.0f} units<extra></extra>',
    ))

    # Line chart for utilization percentage
    fig.add_trace(go.Scatter(
        name='Utilization %',
        x=dates_str,
        y=utilization,
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='#FF6B6B', width=3),
        marker=dict(size=8),
        hovertemplate='Date: %{x}<br>Utilization: %{y:.1f}%<extra></extra>',
    ))

    # Add 100% line
    fig.add_trace(go.Scatter(
        name='100% Capacity',
        x=dates_str,
        y=[100] * len(dates_str),
        yaxis='y2',
        mode='lines',
        line=dict(color='red', dash='dash', width=2),
        hovertemplate='100% Capacity<extra></extra>',
    ))

    # Update layout with dual y-axes
    fig.update_layout(
        title='Daily Capacity Utilization',
        title_x=0.5,
        xaxis=dict(title='Date'),
        yaxis=dict(
            title='Production (units)',
            side='left',
        ),
        yaxis2=dict(
            title='Utilization (%)',
            overlaying='y',
            side='right',
            range=[0, 120],  # 0-120% to show over-capacity
        ),
        height=height,
        hovermode='x unified',
    )

    return fig
