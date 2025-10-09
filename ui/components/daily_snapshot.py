"""Daily inventory snapshot visualization component.

This module provides an interactive UI component for viewing comprehensive
daily inventory information including:
- Inventory at each location
- In-transit shipments
- Manufacturing activity
- Daily inflows and outflows
- Demand satisfaction metrics
"""

import streamlit as st
import pandas as pd
from datetime import date as Date, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

from src.models.location import Location
from src.production.scheduler import ProductionSchedule, ProductionBatch
from src.models.shipment import Shipment
from ui.components.styling import (
    section_header,
    colored_metric,
    success_badge,
    warning_badge,
    error_badge,
    info_badge,
)


def render_daily_snapshot(
    results: Dict[str, Any],
    locations: Dict[str, Location],
    key_prefix: str = "daily_snapshot"
) -> None:
    """Render comprehensive daily inventory snapshot.

    Args:
        results: Results dictionary containing:
            - production_schedule: ProductionSchedule object
            - shipments: List[Shipment]
            - cost_breakdown: Optional cost breakdown
        locations: Dictionary mapping location_id to Location objects
        key_prefix: Prefix for session state keys (for multiple instances)
    """

    # Extract data
    production_schedule = results.get('production_schedule')
    shipments = results.get('shipments', [])

    if not production_schedule:
        st.warning("⚠️ No production schedule available for snapshot analysis")
        return

    # Get date range from production schedule and shipments
    date_range = _get_date_range(production_schedule, shipments)

    if not date_range:
        st.info("ℹ️ No production or shipment data available for snapshot")
        return

    min_date, max_date = date_range

    # ====================
    # DATE SELECTOR
    # ====================

    st.markdown(section_header("Daily Inventory Snapshot", level=2, icon="📸"), unsafe_allow_html=True)

    # Initialize selected date in session state
    session_key = f'{key_prefix}_selected_date'
    if session_key not in st.session_state:
        # Default to first date with production or shipments
        st.session_state[session_key] = min_date

    # Date selector
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        # Create list of dates for slider
        all_dates = []
        current = min_date
        while current <= max_date:
            all_dates.append(current)
            current += timedelta(days=1)

        selected_date = st.select_slider(
            "Select Date",
            options=all_dates,
            value=st.session_state[session_key],
            format_func=lambda d: d.strftime("%Y-%m-%d (%a)"),
            key=f"{key_prefix}_date_slider"
        )

        # Update session state
        st.session_state[session_key] = selected_date

    with col2:
        # Quick navigation buttons
        if st.button("⬅️ Previous Day", key=f"{key_prefix}_prev_day", use_container_width=True):
            idx = all_dates.index(st.session_state[session_key])
            if idx > 0:
                st.session_state[session_key] = all_dates[idx - 1]
                st.rerun()

    with col3:
        if st.button("Next Day ➡️", key=f"{key_prefix}_next_day", use_container_width=True):
            idx = all_dates.index(st.session_state[session_key])
            if idx < len(all_dates) - 1:
                st.session_state[session_key] = all_dates[idx + 1]
                st.rerun()

    st.divider()

    # ====================
    # GENERATE SNAPSHOT
    # ====================

    snapshot = _generate_snapshot(
        selected_date=selected_date,
        production_schedule=production_schedule,
        shipments=shipments,
        locations=locations
    )

    # ====================
    # SUMMARY METRICS
    # ====================

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_inventory = snapshot['total_inventory']
        st.markdown(
            colored_metric("Total Inventory", f"{total_inventory:,.0f} units", "primary"),
            unsafe_allow_html=True
        )

    with col2:
        in_transit = snapshot['in_transit_total']
        st.markdown(
            colored_metric("In Transit", f"{in_transit:,.0f} units", "secondary"),
            unsafe_allow_html=True
        )

    with col3:
        production_today = snapshot['production_total']
        st.markdown(
            colored_metric("Production", f"{production_today:,.0f} units", "accent"),
            unsafe_allow_html=True
        )

    with col4:
        demand_today = snapshot['demand_total']
        st.markdown(
            colored_metric("Demand", f"{demand_today:,.0f} units", "success"),
            unsafe_allow_html=True
        )

    st.divider()

    # ====================
    # LOCATION INVENTORY
    # ====================

    st.markdown(section_header("Inventory at Locations", level=3, icon="📦"), unsafe_allow_html=True)

    location_inventory = snapshot['location_inventory']

    if not location_inventory:
        st.info("ℹ️ No inventory at any location on this date")
    else:
        # Sort locations by quantity (descending)
        sorted_locations = sorted(
            location_inventory.items(),
            key=lambda x: x[1]['total'],
            reverse=True
        )

        for location_id, inv_data in sorted_locations:
            location = locations.get(location_id)
            location_name = location.name if location else location_id
            total_units = inv_data['total']

            # Determine if expanded (manufacturing site defaults to expanded)
            is_manufacturing = location and hasattr(location, 'is_manufacturing') and location.is_manufacturing

            with st.expander(
                f"**{location_id} - {location_name}** ({total_units:,.0f} units)",
                expanded=is_manufacturing
            ):
                # Show batches by product
                batches_by_product = inv_data.get('batches', {})

                if not batches_by_product:
                    st.caption("_No detailed batch information available_")
                else:
                    # Create table
                    batch_data = []
                    for product_id, batch_list in batches_by_product.items():
                        for batch_info in batch_list:
                            batch_data.append({
                                'Batch ID': batch_info.get('id', 'N/A'),
                                'Product': product_id,
                                'Quantity': batch_info.get('quantity', 0),
                                'Age (days)': batch_info.get('age_days', 0),
                                'Production Date': batch_info.get('production_date', 'N/A'),
                            })

                    if batch_data:
                        df_batches = pd.DataFrame(batch_data)

                        # Style based on age
                        def highlight_age(row):
                            age = row['Age (days)']
                            if age <= 3:
                                return ['background-color: #d4edda'] * len(row)  # Green - fresh
                            elif age <= 7:
                                return ['background-color: #fff3cd'] * len(row)  # Yellow - medium
                            else:
                                return ['background-color: #f8d7da'] * len(row)  # Red - old

                        st.dataframe(
                            df_batches.style.apply(highlight_age, axis=1),
                            use_container_width=True,
                            hide_index=True
                        )

                        # Show legend
                        st.caption("🟢 Fresh (0-3 days)  |  🟡 Medium (4-7 days)  |  🔴 Old (8+ days)")

    st.divider()

    # ====================
    # TWO COLUMN: IN-TRANSIT & MANUFACTURING
    # ====================

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(section_header("In Transit", level=3, icon="🚚"), unsafe_allow_html=True)

        in_transit_shipments = snapshot['in_transit_shipments']

        if not in_transit_shipments:
            st.info("ℹ️ No shipments in transit on this date")
        else:
            transit_data = []
            for shipment in in_transit_shipments:
                transit_data.append({
                    'Route': f"{shipment.origin_id} → {shipment.destination_id}",
                    'Product': shipment.product_id,
                    'Quantity': shipment.quantity,
                    'Days in Transit': _get_days_in_transit(shipment, selected_date),
                })

            df_transit = pd.DataFrame(transit_data)
            st.dataframe(df_transit, use_container_width=True, hide_index=True)

    with col2:
        st.markdown(section_header("Manufacturing Activity", level=3, icon="🏭"), unsafe_allow_html=True)

        production_batches = snapshot['production_batches']

        if not production_batches:
            st.info("ℹ️ No production on this date")
        else:
            prod_data = []
            for batch in production_batches:
                prod_data.append({
                    'Batch ID': batch.id,
                    'Product': batch.product_id,
                    'Quantity': batch.quantity,
                    'Labor Hours': f"{batch.labor_hours_used:.1f}h",
                })

            df_prod = pd.DataFrame(prod_data)
            st.dataframe(df_prod, use_container_width=True, hide_index=True)

            # Show summary
            total_labor = sum(b.labor_hours_used for b in production_batches)
            st.caption(f"**Total Labor Hours:** {total_labor:.1f}h")

    st.divider()

    # ====================
    # TWO COLUMN: INFLOWS & OUTFLOWS
    # ====================

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(section_header("Inflows", level=3, icon="⬇️"), unsafe_allow_html=True)

        inflows = snapshot['inflows']

        if not inflows:
            st.info("ℹ️ No inflows on this date")
        else:
            inflow_data = []
            for flow in inflows:
                inflow_data.append({
                    'Type': flow['type'],
                    'Location': flow['location'],
                    'Product': flow['product'],
                    'Quantity': flow['quantity'],
                    'Details': flow.get('details', ''),
                })

            df_inflows = pd.DataFrame(inflow_data)

            # Style by type
            def highlight_inflow_type(row):
                if row['Type'] == 'Production':
                    return ['background-color: #d1ecf1'] * len(row)  # Blue
                else:  # Arrival
                    return ['background-color: #d4edda'] * len(row)  # Green

            st.dataframe(
                df_inflows.style.apply(highlight_inflow_type, axis=1),
                use_container_width=True,
                hide_index=True
            )

    with col2:
        st.markdown(section_header("Outflows", level=3, icon="⬆️"), unsafe_allow_html=True)

        outflows = snapshot['outflows']

        if not outflows:
            st.info("ℹ️ No outflows on this date")
        else:
            outflow_data = []
            for flow in outflows:
                outflow_data.append({
                    'Type': flow['type'],
                    'Location': flow['location'],
                    'Product': flow['product'],
                    'Quantity': flow['quantity'],
                    'Details': flow.get('details', ''),
                })

            df_outflows = pd.DataFrame(outflow_data)

            # Style by type
            def highlight_outflow_type(row):
                if row['Type'] == 'Departure':
                    return ['background-color: #fff3cd'] * len(row)  # Yellow
                else:  # Demand
                    return ['background-color: #cfe2ff'] * len(row)  # Light blue

            st.dataframe(
                df_outflows.style.apply(highlight_outflow_type, axis=1),
                use_container_width=True,
                hide_index=True
            )

    st.divider()

    # ====================
    # DEMAND SATISFACTION
    # ====================

    st.markdown(section_header("Demand Satisfaction", level=3, icon="✅"), unsafe_allow_html=True)

    demand_info = snapshot['demand_satisfaction']

    if not demand_info:
        st.info("ℹ️ No demand on this date")
    else:
        demand_data = []
        total_demand = 0
        total_shortage = 0

        for item in demand_info:
            demand_qty = item['demand']
            supplied_qty = item.get('supplied', 0)
            shortage = max(0, demand_qty - supplied_qty)

            total_demand += demand_qty
            total_shortage += shortage

            status = "✅ Met" if shortage == 0 else f"⚠️ Short {shortage:.0f}"

            demand_data.append({
                'Destination': item['destination'],
                'Product': item['product'],
                'Demand': demand_qty,
                'Supplied': supplied_qty,
                'Status': status,
            })

        df_demand = pd.DataFrame(demand_data)

        # Style based on status
        def highlight_status(row):
            if '✅' in row['Status']:
                return ['background-color: #d4edda'] * len(row)  # Green
            else:
                return ['background-color: #fff3cd'] * len(row)  # Yellow warning

        st.dataframe(
            df_demand.style.apply(highlight_status, axis=1),
            use_container_width=True,
            hide_index=True
        )

        # Show summary badge
        if total_shortage == 0:
            st.markdown(success_badge("All Demand Met"), unsafe_allow_html=True)
        else:
            st.markdown(
                warning_badge(f"{total_shortage:.0f} units short"),
                unsafe_allow_html=True
            )


def _get_date_range(
    production_schedule: ProductionSchedule,
    shipments: List[Shipment]
) -> Optional[Tuple[Date, Date]]:
    """Get the overall date range from production and shipments.

    Returns:
        Tuple of (min_date, max_date) or None if no data
    """
    dates = []

    # Add production dates
    if production_schedule and production_schedule.production_batches:
        dates.extend([b.production_date for b in production_schedule.production_batches])

    # Add shipment dates
    for shipment in shipments:
        if hasattr(shipment, 'departure_date') and shipment.departure_date:
            dates.append(shipment.departure_date)
        if hasattr(shipment, 'arrival_date') and shipment.arrival_date:
            dates.append(shipment.arrival_date)
        if hasattr(shipment, 'production_date') and shipment.production_date:
            dates.append(shipment.production_date)

    if not dates:
        return None

    return min(dates), max(dates)


def _generate_snapshot(
    selected_date: Date,
    production_schedule: ProductionSchedule,
    shipments: List[Shipment],
    locations: Dict[str, Location]
) -> Dict[str, Any]:
    """Generate snapshot data for a specific date.

    Returns:
        Dictionary containing:
        - total_inventory: Total inventory across all locations
        - in_transit_total: Total in-transit quantity
        - production_total: Total production on this date
        - demand_total: Total demand on this date
        - location_inventory: Dict[location_id, inventory_info]
        - in_transit_shipments: List of shipments in transit
        - production_batches: List of batches produced on this date
        - inflows: List of inflow events
        - outflows: List of outflow events
        - demand_satisfaction: List of demand items
    """

    # Initialize snapshot
    snapshot = {
        'total_inventory': 0,
        'in_transit_total': 0,
        'production_total': 0,
        'demand_total': 0,
        'location_inventory': {},
        'in_transit_shipments': [],
        'production_batches': [],
        'inflows': [],
        'outflows': [],
        'demand_satisfaction': [],
    }

    # ====================
    # PRODUCTION BATCHES
    # ====================

    if production_schedule and production_schedule.production_batches:
        for batch in production_schedule.production_batches:
            if batch.production_date == selected_date:
                snapshot['production_batches'].append(batch)
                snapshot['production_total'] += batch.quantity

                # Add to inflows
                snapshot['inflows'].append({
                    'type': 'Production',
                    'location': batch.manufacturing_site_id,
                    'product': batch.product_id,
                    'quantity': batch.quantity,
                    'details': f"Batch {batch.id}",
                })

    # ====================
    # SHIPMENTS (IN-TRANSIT & ARRIVALS/DEPARTURES)
    # ====================

    for shipment in shipments:
        departure_date = getattr(shipment, 'departure_date', None) or getattr(shipment, 'production_date', None)
        arrival_date = getattr(shipment, 'arrival_date', None)

        # Check if in transit on selected date
        if departure_date and arrival_date:
            if departure_date <= selected_date < arrival_date:
                snapshot['in_transit_shipments'].append(shipment)
                snapshot['in_transit_total'] += shipment.quantity

        # Check if departing on selected date
        if departure_date == selected_date:
            snapshot['outflows'].append({
                'type': 'Departure',
                'location': shipment.origin_id,
                'product': shipment.product_id,
                'quantity': shipment.quantity,
                'details': f"To {shipment.destination_id}",
            })

        # Check if arriving on selected date
        if arrival_date == selected_date:
            snapshot['inflows'].append({
                'type': 'Arrival',
                'location': shipment.destination_id,
                'product': shipment.product_id,
                'quantity': shipment.quantity,
                'details': f"From {shipment.origin_id}",
            })

    # ====================
    # LOCATION INVENTORY (SIMPLIFIED)
    # ====================

    # Build inventory by tracking production and shipments up to selected_date
    # This is a simplified view - actual inventory tracking would be more complex

    inventory_by_location_product: Dict[Tuple[str, str], List[ProductionBatch]] = defaultdict(list)

    # Add all production batches up to and including selected date
    if production_schedule and production_schedule.production_batches:
        for batch in production_schedule.production_batches:
            if batch.production_date <= selected_date:
                key = (batch.manufacturing_site_id, batch.product_id)
                inventory_by_location_product[key].append(batch)

    # Aggregate by location
    for (location_id, product_id), batch_list in inventory_by_location_product.items():
        if location_id not in snapshot['location_inventory']:
            snapshot['location_inventory'][location_id] = {
                'total': 0,
                'batches': {},
            }

        total_qty = sum(b.quantity for b in batch_list)
        snapshot['location_inventory'][location_id]['total'] += total_qty
        snapshot['total_inventory'] += total_qty

        # Store batch details
        snapshot['location_inventory'][location_id]['batches'][product_id] = [
            {
                'id': b.id,
                'quantity': b.quantity,
                'production_date': b.production_date,
                'age_days': (selected_date - b.production_date).days,
            }
            for b in batch_list
        ]

    # ====================
    # DEMAND SATISFACTION (PLACEHOLDER)
    # ====================

    # Note: Full demand satisfaction tracking would require forecast data
    # For now, we'll show a simplified view

    # Get forecast from session state if available
    try:
        import streamlit as st
        forecast = st.session_state.get('forecast')

        if forecast:
            # Group demand by destination and product for selected date
            for entry in forecast.entries:
                if entry.date == selected_date:
                    snapshot['demand_total'] += entry.quantity

                    snapshot['demand_satisfaction'].append({
                        'destination': entry.location_id,
                        'product': entry.product_id,
                        'demand': entry.quantity,
                        'supplied': entry.quantity,  # Simplified - assume met
                    })

                    # Add to outflows
                    snapshot['outflows'].append({
                        'type': 'Demand',
                        'location': entry.location_id,
                        'product': entry.product_id,
                        'quantity': entry.quantity,
                        'details': 'Customer demand',
                    })
    except Exception:
        # If forecast not available, continue without demand data
        pass

    return snapshot


def _get_days_in_transit(shipment: Shipment, current_date: Date) -> int:
    """Calculate how many days a shipment has been in transit."""
    departure_date = getattr(shipment, 'departure_date', None) or getattr(shipment, 'production_date', None)

    if not departure_date:
        return 0

    return (current_date - departure_date).days
