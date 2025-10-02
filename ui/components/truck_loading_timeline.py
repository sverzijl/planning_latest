"""Truck loading and distribution visualization components using Plotly."""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, time
from src.distribution import TruckLoadPlan


def render_truck_loading_timeline(truck_plan: TruckLoadPlan, height: int = 600):
    """
    Render truck loading timeline as a Gantt chart.

    Args:
        truck_plan: TruckLoadPlan instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    loads = truck_plan.loads

    if not loads:
        fig = go.Figure()
        fig.add_annotation(
            text="No truck loads to display",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Truck Loading Timeline',
            title_x=0.5,
            height=height,
        )
        return fig

    # Prepare data for Gantt chart
    df_data = []
    for load in loads:
        # Create a label combining truck name and destination
        truck_label = f"{load.truck_name} → {load.destination_id}"

        # Start time is departure time, end time is end of day (for visualization)
        start_datetime = datetime.combine(load.departure_date, load.departure_time or time(8, 0))
        end_datetime = datetime.combine(load.departure_date, time(23, 59))

        total_units = sum(s.quantity for s in load.shipments)
        total_pallets = sum(s.quantity / 320 for s in load.shipments)  # Assuming 320 units/pallet

        df_data.append({
            'Truck': truck_label,
            'Start': start_datetime,
            'Finish': end_datetime,
            'Departure Type': load.departure_type,
            'Units': total_units,
            'Pallets': total_pallets,
            'Utilization': load.utilization_pct,
            'Shipments': len(load.shipments),
        })

    df = pd.DataFrame(df_data)

    # Create color mapping for departure type
    color_map = {
        'morning': '#4ECDC4',
        'afternoon': '#FF6B6B',
    }

    fig = px.timeline(
        df,
        x_start='Start',
        x_end='Finish',
        y='Truck',
        color='Departure Type',
        color_discrete_map=color_map,
        hover_data=['Units', 'Pallets', 'Utilization', 'Shipments'],
        title='Truck Loading Timeline',
    )

    # Update layout
    fig.update_yaxes(categoryorder='category ascending')
    fig.update_layout(
        title_x=0.5,
        xaxis_title='Departure Date',
        yaxis_title='Truck (Destination)',
        height=height,
        showlegend=True,
    )

    return fig


def render_truck_utilization_chart(truck_plan: TruckLoadPlan, height: int = 400):
    """
    Render truck utilization as a horizontal bar chart.

    Args:
        truck_plan: TruckLoadPlan instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    loads = truck_plan.loads

    if not loads:
        fig = go.Figure()
        fig.add_annotation(
            text="No truck utilization data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Truck Utilization',
            title_x=0.5,
            height=height,
        )
        return fig

    # Sort by utilization (descending)
    sorted_loads = sorted(loads, key=lambda l: l.utilization_pct, reverse=True)

    truck_labels = [f"{l.truck_name} ({l.departure_date})" for l in sorted_loads]
    utilizations = [l.utilization_pct * 100 for l in sorted_loads]
    total_units = [sum(s.quantity for s in l.shipments) for l in sorted_loads]

    # Color bars based on utilization level
    colors = []
    for util in utilizations:
        if util >= 90:
            colors.append('#95E1D3')  # High utilization - green
        elif util >= 70:
            colors.append('#4ECDC4')  # Medium utilization - cyan
        elif util >= 50:
            colors.append('#FFE66D')  # Low-medium utilization - yellow
        else:
            colors.append('#FF6B6B')  # Low utilization - red

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=truck_labels,
        x=utilizations,
        orientation='h',
        marker=dict(color=colors),
        text=[f'{u:.1f}%' for u in utilizations],
        textposition='outside',
        customdata=total_units,
        hovertemplate='<b>%{y}</b><br>Utilization: %{x:.1f}%<br>Units: %{customdata:,.0f}<extra></extra>',
    ))

    # Add 100% line
    fig.add_vline(x=100, line_dash="dash", line_color="red", annotation_text="100%")

    fig.update_layout(
        title=f'Truck Utilization (Average: {truck_plan.average_utilization:.1%})',
        title_x=0.5,
        xaxis_title='Utilization (%)',
        yaxis_title='Truck (Date)',
        height=height,
        showlegend=False,
        xaxis=dict(range=[0, max(utilizations) * 1.1]),  # Add 10% margin
    )

    return fig


def render_shipments_by_destination_chart(truck_plan: TruckLoadPlan, height: int = 400):
    """
    Render shipments grouped by destination.

    Args:
        truck_plan: TruckLoadPlan instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    loads = truck_plan.loads

    if not loads:
        fig = go.Figure()
        fig.add_annotation(
            text="No shipment data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Shipments by Destination',
            title_x=0.5,
            height=height,
        )
        return fig

    # Group by destination
    by_destination = {}
    for load in loads:
        dest = load.destination_id
        if dest not in by_destination:
            by_destination[dest] = {'units': 0, 'shipments': 0, 'trucks': 0}

        by_destination[dest]['units'] += sum(s.quantity for s in load.shipments)
        by_destination[dest]['shipments'] += len(load.shipments)
        by_destination[dest]['trucks'] += 1

    # Sort by units (descending)
    sorted_destinations = sorted(by_destination.items(), key=lambda x: x[1]['units'], reverse=True)

    destinations = [d[0] for d in sorted_destinations]
    units = [d[1]['units'] for d in sorted_destinations]
    shipments = [d[1]['shipments'] for d in sorted_destinations]
    trucks = [d[1]['trucks'] for d in sorted_destinations]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=destinations,
        y=units,
        marker=dict(color='#4ECDC4'),
        text=[f'{u:,.0f}' for u in units],
        textposition='outside',
        customdata=list(zip(shipments, trucks)),
        hovertemplate='<b>%{x}</b><br>Units: %{y:,.0f}<br>Shipments: %{customdata[0]}<br>Trucks: %{customdata[1]}<extra></extra>',
    ))

    fig.update_layout(
        title='Total Units by Destination',
        title_x=0.5,
        xaxis_title='Destination',
        yaxis_title='Units',
        height=height,
        showlegend=False,
    )

    return fig


def render_daily_truck_count_chart(truck_plan: TruckLoadPlan, height: int = 400):
    """
    Render daily truck count.

    Args:
        truck_plan: TruckLoadPlan instance
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    loads = truck_plan.loads

    if not loads:
        fig = go.Figure()
        fig.add_annotation(
            text="No daily truck data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(
            title='Daily Truck Count',
            title_x=0.5,
            height=height,
        )
        return fig

    # Group by date and departure type
    by_date = {}
    for load in loads:
        date_key = str(load.departure_date)
        if date_key not in by_date:
            by_date[date_key] = {'morning': 0, 'afternoon': 0}

        dep_type = load.departure_type
        if dep_type in by_date[date_key]:
            by_date[date_key][dep_type] += 1

    # Sort by date
    sorted_dates = sorted(by_date.keys())

    morning_counts = [by_date[d]['morning'] for d in sorted_dates]
    afternoon_counts = [by_date[d]['afternoon'] for d in sorted_dates]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Morning',
        x=sorted_dates,
        y=morning_counts,
        marker=dict(color='#4ECDC4'),
        hovertemplate='Date: %{x}<br>Morning Trucks: %{y}<extra></extra>',
    ))

    fig.add_trace(go.Bar(
        name='Afternoon',
        x=sorted_dates,
        y=afternoon_counts,
        marker=dict(color='#FF6B6B'),
        hovertemplate='Date: %{x}<br>Afternoon Trucks: %{y}<extra></extra>',
    ))

    fig.update_layout(
        title='Daily Truck Count by Departure Type',
        title_x=0.5,
        xaxis_title='Date',
        yaxis_title='Number of Trucks',
        barmode='stack',
        height=height,
        hovermode='x unified',
    )

    return fig
