"""Reusable data table components for the planning application."""

import streamlit as st
import pandas as pd
from typing import List
from src.production.scheduler import ProductionSchedule
from src.models.shipment import Shipment
from src.distribution import TruckLoadPlan


def render_production_batches_table(production_schedule: ProductionSchedule, max_rows: int = None):
    """
    Render production batches as a Streamlit dataframe.

    Args:
        production_schedule: ProductionSchedule instance
        max_rows: Maximum number of rows to display (None for all)
    """
    batches = production_schedule.production_batches

    if not batches:
        st.info("No production batches to display")
        return

    # Prepare data
    data = []
    for batch in batches:
        data.append({
            'Batch ID': batch.id,
            'Product': batch.product_id,
            'Production Date': batch.production_date,
            'Quantity (units)': f"{batch.quantity:,.0f}",
            'Labor Hours': f"{batch.labor_hours_used:.1f}",
            'Production Cost': f"${batch.production_cost:,.2f}",
            'State': batch.initial_state,
            'Sequence': batch.sequence_number or '-',
        })

    df = pd.DataFrame(data)

    # Display
    if max_rows:
        st.dataframe(df.head(max_rows), use_container_width=True, hide_index=True)
        if len(df) > max_rows:
            st.caption(f"Showing {max_rows} of {len(df)} batches")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} total batches")


def render_shipments_table(shipments: List[Shipment], max_rows: int = None):
    """
    Render shipments as a Streamlit dataframe.

    Args:
        shipments: List of Shipment instances
        max_rows: Maximum number of rows to display (None for all)
    """
    if not shipments:
        st.info("No shipments to display")
        return

    # Prepare data
    data = []
    for shipment in shipments:
        # Get route path
        route_path = " → ".join(shipment.route.path) if shipment.route else "N/A"

        data.append({
            'Shipment ID': shipment.id,
            'Product': shipment.product_id,
            'Origin': shipment.origin_id,
            'Destination': shipment.destination_id,
            'Route': route_path,
            'Quantity (units)': f"{shipment.quantity:,.0f}",
            'Delivery Date': shipment.delivery_date,
            'Production Date': shipment.production_date or '-',
            'Assigned Truck': shipment.assigned_truck_id or 'Unassigned',
            'Transit Days': shipment.route.total_transit_days if shipment.route else '-',
        })

    df = pd.DataFrame(data)

    # Display
    if max_rows:
        st.dataframe(df.head(max_rows), use_container_width=True, hide_index=True)
        if len(df) > max_rows:
            st.caption(f"Showing {max_rows} of {len(df)} shipments")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} total shipments")


def render_truck_loads_table(truck_plan: TruckLoadPlan, max_rows: int = None):
    """
    Render truck loads as a Streamlit dataframe.

    Args:
        truck_plan: TruckLoadPlan instance
        max_rows: Maximum number of rows to display (None for all)
    """
    loads = truck_plan.loads

    if not loads:
        st.info("No truck loads to display")
        return

    # Prepare data
    data = []
    for load in loads:
        total_units = sum(s.quantity for s in load.shipments)
        total_pallets = total_units / 320  # Assuming 320 units per pallet

        data.append({
            'Truck ID': load.truck_schedule_id,
            'Truck Name': load.truck_name,
            'Departure Date': load.departure_date,
            'Departure Type': load.departure_type,
            'Destination': load.destination_id,
            'Shipments': len(load.shipments),
            'Total Units': f"{total_units:,.0f}",
            'Total Pallets': f"{total_pallets:.1f}",
            'Utilization': f"{load.utilization_pct:.1%}",
            'Is Full': '✓' if load.is_full else '',
        })

    df = pd.DataFrame(data)

    # Display
    if max_rows:
        st.dataframe(df.head(max_rows), use_container_width=True, hide_index=True)
        if len(df) > max_rows:
            st.caption(f"Showing {max_rows} of {len(df)} truck loads")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} total truck loads")


def render_truck_loadings_table(truck_plan: TruckLoadPlan, max_rows: int = None):
    """
    Alias for render_truck_loads_table for backward compatibility.

    Args:
        truck_plan: TruckLoadPlan instance
        max_rows: Maximum number of rows to display (None for all)
    """
    return render_truck_loads_table(truck_plan, max_rows)


def render_unassigned_shipments_table(truck_plan: TruckLoadPlan):
    """
    Render unassigned shipments as a Streamlit dataframe.

    Args:
        truck_plan: TruckLoadPlan instance
    """
    unassigned = truck_plan.unassigned_shipments

    if not unassigned:
        st.success("✅ All shipments assigned to trucks")
        return

    st.warning(f"⚠️ {len(unassigned)} unassigned shipments")

    # Prepare data
    data = []
    for shipment in unassigned:
        route_path = " → ".join(shipment.route.path) if shipment.route else "N/A"

        data.append({
            'Shipment ID': shipment.id,
            'Product': shipment.product_id,
            'Destination': shipment.destination_id,
            'Route': route_path,
            'Quantity (units)': f"{shipment.quantity:,.0f}",
            'Delivery Date': shipment.delivery_date,
            'Production Date': shipment.production_date or '-',
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_cost_summary_table(cost_breakdown):
    """
    Render cost summary as a table.

    Args:
        cost_breakdown: TotalCostBreakdown instance
    """
    data = [
        {'Component': 'Labor', 'Cost': cost_breakdown.labor.total_cost},
        {'Component': 'Production', 'Cost': cost_breakdown.production.total_cost},
        {'Component': 'Transport', 'Cost': cost_breakdown.transport.total_cost},
        {'Component': 'Waste', 'Cost': cost_breakdown.waste.total_cost},
        {'Component': '**TOTAL**', 'Cost': cost_breakdown.total_cost},
    ]

    df = pd.DataFrame(data)
    df['Cost'] = df['Cost'].apply(lambda x: f"${x:,.2f}")

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Cost per unit delivered: ${cost_breakdown.cost_per_unit_delivered:.2f}")


def render_cost_breakdown_table(cost_breakdown):
    """
    Alias for render_cost_summary_table for backward compatibility.

    Args:
        cost_breakdown: TotalCostBreakdown instance
    """
    return render_cost_summary_table(cost_breakdown)


def render_labor_breakdown_table(cost_breakdown):
    """
    Render labor cost breakdown table.

    Args:
        cost_breakdown: TotalCostBreakdown instance
    """
    labor = cost_breakdown.labor

    data = [
        {
            'Category': 'Fixed Hours',
            'Hours': f"{labor.fixed_hours:.1f}",
            'Cost': f"${labor.fixed_hours_cost:,.2f}"
        },
        {
            'Category': 'Overtime',
            'Hours': f"{labor.overtime_hours:.1f}",
            'Cost': f"${labor.overtime_cost:,.2f}"
        },
        {
            'Category': 'Non-Fixed Labor',
            'Hours': f"{labor.non_fixed_hours:.1f}",
            'Cost': f"${labor.non_fixed_labor_cost:,.2f}"
        },
        {
            'Category': '**TOTAL**',
            'Hours': f"**{labor.total_hours:.1f}**",
            'Cost': f"**${labor.total_cost:,.2f}**"
        },
    ]

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_daily_breakdown_table(production_schedule: ProductionSchedule):
    """
    Render daily production and labor summary.

    Args:
        production_schedule: ProductionSchedule instance
    """
    daily_totals = production_schedule.daily_totals
    daily_labor = production_schedule.daily_labor_hours

    if not daily_totals:
        st.info("No daily data available")
        return

    # Get all dates
    all_dates = sorted(set(list(daily_totals.keys()) + list(daily_labor.keys())))

    data = []
    for date in all_dates:
        data.append({
            'Date': date,
            'Production (units)': f"{daily_totals.get(date, 0):,.0f}",
            'Labor Hours': f"{daily_labor.get(date, 0):.1f}",
            'Units/Hour': f"{daily_totals.get(date, 0) / daily_labor.get(date, 1) if daily_labor.get(date, 0) > 0 else 0:.0f}",
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"{len(df)} production days")
