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
from src.analysis.daily_snapshot import DailySnapshotGenerator
from ui.components.styling import (
    section_header,
    colored_metric,
    success_badge,
    warning_badge,
    error_badge,
    info_badge,
)


def _get_freshness_status(remaining_days: int) -> Tuple[str, str]:
    """
    Get freshness status emoji and label based on remaining shelf life.

    Args:
        remaining_days: Days of shelf life remaining

    Returns:
        Tuple of (emoji, status_text)
    """
    if remaining_days >= 10:
        return ("🟢", "Fresh")
    elif remaining_days >= 5:
        return ("🟡", "Aging")
    elif remaining_days >= 0:
        return ("🔴", "Near Expiry")
    else:
        return ("⚫", "Expired")


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
        locations=locations,
        results=results
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
        st.info("ℹ️ No locations found in network")
    else:
        # Calculate summary metrics
        locations_with_inventory = sum(1 for inv in location_inventory.values() if inv['total'] > 0)
        locations_empty = len(location_inventory) - locations_with_inventory

        # Display summary metrics in compact format
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Total Locations:** {len(location_inventory)}")
        with col2:
            st.markdown(f"**With Inventory:** {locations_with_inventory}")
        with col3:
            st.markdown(f"**Empty:** {locations_empty}")

        st.markdown("---")

        # Add sorting and filtering controls
        col1, col2 = st.columns([2, 1])

        with col1:
            sort_option = st.radio(
                "Sort by:",
                options=["Inventory Level (High to Low)", "Inventory Level (Low to High)", "Location ID", "Location Name"],
                horizontal=True,
                key=f"{key_prefix}_sort_option"
            )

        with col2:
            filter_option = st.selectbox(
                "Filter:",
                options=["Show All", "Only With Inventory", "Only Empty"],
                key=f"{key_prefix}_filter_option"
            )

        # Apply filtering
        filtered_locations = location_inventory.items()
        if filter_option == "Only With Inventory":
            filtered_locations = [(loc_id, inv) for loc_id, inv in filtered_locations if inv['total'] > 0]
        elif filter_option == "Only Empty":
            filtered_locations = [(loc_id, inv) for loc_id, inv in filtered_locations if inv['total'] == 0]

        # Apply sorting
        if sort_option == "Inventory Level (High to Low)":
            sorted_locations = sorted(filtered_locations, key=lambda x: x[1]['total'], reverse=True)
        elif sort_option == "Inventory Level (Low to High)":
            sorted_locations = sorted(filtered_locations, key=lambda x: x[1]['total'], reverse=False)
        elif sort_option == "Location ID":
            sorted_locations = sorted(filtered_locations, key=lambda x: x[0])
        else:  # Location Name
            sorted_locations = sorted(
                filtered_locations,
                key=lambda x: locations.get(x[0]).name if locations.get(x[0]) else x[0]
            )

        if not sorted_locations:
            st.info(f"ℹ️ No locations match the filter: {filter_option}")
        else:
            # Display locations
            for location_id, inv_data in sorted_locations:
                location = locations.get(location_id)
                location_name = location.name if location else location_id
                total_units = inv_data['total']

                # Visual indicator based on inventory level
                if total_units == 0:
                    icon = "📭"
                    status_text = "Empty"
                    status_color = "secondary"
                elif total_units < 1000:
                    icon = "📦"
                    status_text = f"{total_units:,.0f} units (Low)"
                    status_color = "warning"
                else:
                    icon = "📦"
                    status_text = f"{total_units:,.0f} units"
                    status_color = "primary"

                # Determine if expanded (manufacturing site defaults to expanded)
                is_manufacturing = location and hasattr(location, 'is_manufacturing') and location.is_manufacturing

                with st.expander(
                    f"{icon} **{location_id} - {location_name}** ({status_text})",
                    expanded=is_manufacturing
                ):
                    # Show zero inventory message
                    if total_units == 0:
                        st.caption("📭 No inventory at this location on this date")
                    else:
                        # Show batches by product
                        batches_by_product = inv_data.get('batches', {})

                        if not batches_by_product:
                            st.caption("_No detailed batch information available_")
                        else:
                            # Create enhanced table with shelf life tracking
                            batch_data = []
                            for product_id, batch_list in batches_by_product.items():
                                for batch_info in batch_list:
                                    age_days = batch_info.get('age_days', 0)

                                    # Calculate shelf life remaining
                                    # Ambient shelf life: 17 days
                                    # TODO: Get actual shelf life from product model
                                    shelf_life_days = 17
                                    remaining_days = shelf_life_days - age_days

                                    # Determine freshness status
                                    emoji, status = _get_freshness_status(remaining_days)

                                    batch_data.append({
                                        'Batch ID': batch_info.get('id', 'N/A'),
                                        'Product': product_id,
                                        'Quantity': f"{batch_info.get('quantity', 0):,.0f}",
                                        'Production Date': batch_info.get('production_date', 'N/A'),
                                        'Age (days)': age_days,
                                        'Shelf Life Left': f"{remaining_days}d",
                                        'Status': f"{emoji} {status}",
                                        '_remaining': remaining_days,  # Hidden column for styling
                                    })

                            if batch_data:
                                df_batches = pd.DataFrame(batch_data)

                                # Style based on shelf life remaining
                                def highlight_shelf_life(row):
                                    remaining = row['_remaining']
                                    if remaining >= 10:
                                        return ['background-color: #d4edda'] * len(row)  # Green - fresh
                                    elif remaining >= 5:
                                        return ['background-color: #fff3cd'] * len(row)  # Yellow - aging
                                    elif remaining >= 0:
                                        return ['background-color: #f8d7da'] * len(row)  # Red - near expiry
                                    else:
                                        return ['background-color: #dc3545; color: white'] * len(row)  # Dark red - expired

                                # Apply styling to dataframe (needs _remaining column)
                                # Then hide the _remaining column from display using column_config
                                st.dataframe(
                                    df_batches.style.apply(highlight_shelf_life, axis=1),
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        '_remaining': None  # Hide this column from display
                                    }
                                )

                                # Show enhanced legend
                                st.caption("🟢 Fresh (10+ days)  |  🟡 Aging (5-9 days)  |  🔴 Near Expiry (<5 days)  |  ⚫ Expired")

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
                    'Route': f"{shipment['origin_id']} → {shipment['destination_id']}",
                    'Product': shipment['product_id'],
                    'Quantity': shipment['quantity'],
                    'Days in Transit': shipment['days_in_transit'],
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
                    'Batch ID': batch['batch_id'],
                    'Product': batch['product_id'],
                    'Quantity': batch['quantity'],
                })

            df_prod = pd.DataFrame(prod_data)
            st.dataframe(df_prod, use_container_width=True, hide_index=True)

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
    # BATCH TRACEABILITY (if batch tracking is enabled)
    # ====================

    # Check if batch tracking is enabled in results
    use_batch_tracking = results.get('use_batch_tracking', False)

    if use_batch_tracking and production_schedule and production_schedule.production_batches:
        st.markdown(section_header("Batch Traceability", level=3, icon="🔍"), unsafe_allow_html=True)

        with st.expander("🔍 Trace Individual Batches", expanded=False):
            # Get all batches from production schedule
            all_batches = production_schedule.production_batches

            if not all_batches:
                st.info("ℹ️ No batches available for tracing")
            else:
                # Create batch selection options
                batch_options = [
                    f"{batch.id} - {batch.product_id} ({batch.production_date}) - {batch.quantity:,.0f} units"
                    for batch in all_batches
                ]
                batch_ids = [batch.id for batch in all_batches]

                # Batch selector
                selected_idx = st.selectbox(
                    "Select batch to trace:",
                    range(len(batch_options)),
                    format_func=lambda i: batch_options[i],
                    key=f"{key_prefix}_batch_selector"
                )

                if selected_idx is not None:
                    selected_batch_id = batch_ids[selected_idx]
                    selected_batch = all_batches[selected_idx]

                    # Display batch traceability
                    _display_batch_traceability(
                        batch=selected_batch,
                        batch_id=selected_batch_id,
                        shipments=shipments,
                        results=results,
                        locations=locations,
                        key_prefix=key_prefix
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


def _display_batch_traceability(
    batch: ProductionBatch,
    batch_id: str,
    shipments: List[Shipment],
    results: Dict[str, Any],
    locations: Dict[str, Location],
    key_prefix: str
) -> None:
    """
    Display detailed traceability information for a specific batch.

    Shows the complete journey of the batch from production through
    the supply chain network to final delivery.

    Args:
        batch: ProductionBatch object
        batch_id: Batch identifier
        shipments: List of all shipments
        results: Results dictionary
        locations: Dictionary of locations
        key_prefix: Session state key prefix
    """
    st.markdown("---")
    st.subheader(f"Batch Journey: {batch_id}")

    # ====================
    # PRODUCTION INFO
    # ====================

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(f"**Production Date:** {batch.production_date}")
        location_name = locations.get(batch.manufacturing_site_id).name if locations.get(batch.manufacturing_site_id) else batch.manufacturing_site_id
        st.markdown(f"**Manufactured at:** {location_name} ({batch.manufacturing_site_id})")

    with col2:
        st.markdown(f"**Product:** {batch.product_id}")
        st.markdown(f"**Quantity:** {batch.quantity:,.0f} units")

    with col3:
        st.markdown(f"**Initial State:** {batch.initial_state}")
        if batch.assigned_truck_id:
            st.markdown(f"**Assigned Truck:** {batch.assigned_truck_id}")

    st.markdown("---")

    # ====================
    # SHIPMENT HISTORY
    # ====================

    st.markdown("### 📦 Shipment History")

    # Find all shipments for this batch
    batch_shipments = [s for s in shipments if s.batch_id == batch_id]

    if not batch_shipments:
        st.info("ℹ️ No shipments found for this batch (may still be at manufacturing site)")
    else:
        # Sort by delivery date
        batch_shipments = sorted(batch_shipments, key=lambda s: s.delivery_date)

        shipment_data = []
        for shipment in batch_shipments:
            # Get origin and destination names
            origin_name = locations.get(shipment.origin_id).name if locations.get(shipment.origin_id) else shipment.origin_id
            dest_name = locations.get(shipment.destination_id).name if locations.get(shipment.destination_id) else shipment.destination_id

            # Build route path string
            route_path = " → ".join([leg.from_location_id for leg in shipment.route.route_legs])
            route_path += f" → {shipment.destination_id}"

            shipment_data.append({
                'Shipment ID': shipment.id,
                'Route': f"{origin_name} → {dest_name}",
                'Full Path': route_path,
                'Quantity': f"{shipment.quantity:,.0f}",
                'Delivery Date': shipment.delivery_date,
                'Transit Days': shipment.total_transit_days,
                'Transport Mode': shipment.transport_mode,
            })

        df_shipments = pd.DataFrame(shipment_data)
        st.dataframe(df_shipments, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ====================
    # CURRENT LOCATIONS (from cohort inventory if available)
    # ====================

    st.markdown("### 📍 Current Locations")

    cohort_inventory = results.get('cohort_inventory', {})

    if cohort_inventory:
        # Find where this batch currently is
        # cohort_inventory format: {(loc, prod, prod_date, curr_date, state): qty}
        current_locations = {}

        for (loc, prod, prod_date, curr_date, state), qty in cohort_inventory.items():
            if prod == batch.product_id and prod_date == batch.production_date and qty > 0.01:
                if loc not in current_locations:
                    current_locations[loc] = {'total': 0.0, 'by_state': {}}
                current_locations[loc]['total'] += qty
                if state not in current_locations[loc]['by_state']:
                    current_locations[loc]['by_state'][state] = 0.0
                current_locations[loc]['by_state'][state] += qty

        if current_locations:
            location_data = []
            for loc_id, inv_info in current_locations.items():
                loc_name = locations.get(loc_id).name if locations.get(loc_id) else loc_id
                states = ", ".join([f"{state}: {qty:,.0f}" for state, qty in inv_info['by_state'].items()])

                location_data.append({
                    'Location': f"{loc_name} ({loc_id})",
                    'Total Quantity': f"{inv_info['total']:,.0f} units",
                    'State Breakdown': states,
                })

            df_locations = pd.DataFrame(location_data)
            st.dataframe(df_locations, use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ Batch has been fully consumed (no remaining inventory)")
    else:
        st.info("ℹ️ Cohort inventory data not available (run optimization with use_batch_tracking=True)")

    st.markdown("---")

    # ====================
    # TIMELINE VISUALIZATION
    # ====================

    st.markdown("### 📅 Timeline")

    if batch_shipments:
        # Create simple timeline
        timeline_events = []

        # Production event
        timeline_events.append({
            'Date': batch.production_date,
            'Event': 'Production',
            'Location': batch.manufacturing_site_id,
            'Quantity': f"{batch.quantity:,.0f}",
            'Details': f"Manufactured at {batch.manufacturing_site_id}"
        })

        # Shipment events
        for shipment in batch_shipments:
            # Departure
            departure_date = shipment.delivery_date - timedelta(days=shipment.total_transit_days)
            timeline_events.append({
                'Date': departure_date,
                'Event': 'Departure',
                'Location': shipment.origin_id,
                'Quantity': f"{shipment.quantity:,.0f}",
                'Details': f"Departed {shipment.origin_id} → {shipment.destination_id}"
            })

            # Delivery
            timeline_events.append({
                'Date': shipment.delivery_date,
                'Event': 'Delivery',
                'Location': shipment.destination_id,
                'Quantity': f"{shipment.quantity:,.0f}",
                'Details': f"Arrived at {shipment.destination_id}"
            })

        # Sort by date
        timeline_events = sorted(timeline_events, key=lambda e: e['Date'])

        df_timeline = pd.DataFrame(timeline_events)

        # Style timeline
        def highlight_event(row):
            event = row['Event']
            if event == 'Production':
                return ['background-color: #d1ecf1'] * len(row)  # Blue
            elif event == 'Departure':
                return ['background-color: #fff3cd'] * len(row)  # Yellow
            else:  # Delivery
                return ['background-color: #d4edda'] * len(row)  # Green

        st.dataframe(
            df_timeline.style.apply(highlight_event, axis=1),
            use_container_width=True,
            hide_index=True
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

    # Get planning start date if available
    planning_start = None
    if hasattr(production_schedule, 'schedule_start_date') and production_schedule.schedule_start_date:
        planning_start = production_schedule.schedule_start_date

    # Add production dates (only if on or after planning start)
    if production_schedule and production_schedule.production_batches:
        for batch in production_schedule.production_batches:
            if planning_start is None or batch.production_date >= planning_start:
                dates.append(batch.production_date)

    # Add shipment dates
    for shipment in shipments:
        if hasattr(shipment, 'departure_date') and shipment.departure_date:
            if planning_start is None or shipment.departure_date >= planning_start:
                dates.append(shipment.departure_date)
        if hasattr(shipment, 'arrival_date') and shipment.arrival_date:
            if planning_start is None or shipment.arrival_date >= planning_start:
                dates.append(shipment.arrival_date)
        if hasattr(shipment, 'production_date') and shipment.production_date:
            if planning_start is None or shipment.production_date >= planning_start:
                dates.append(shipment.production_date)
        if hasattr(shipment, 'delivery_date') and shipment.delivery_date:
            if planning_start is None or shipment.delivery_date >= planning_start:
                dates.append(shipment.delivery_date)

    if not dates:
        return None

    return min(dates), max(dates)


def _generate_snapshot(
    selected_date: Date,
    production_schedule: ProductionSchedule,
    shipments: List[Shipment],
    locations: Dict[str, Location],
    results: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate snapshot data for a specific date using the backend generator.

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

    # Get forecast from session state
    forecast = None
    try:
        import streamlit as st
        forecast = st.session_state.get('forecast')
    except Exception:
        pass

    # If no forecast, create empty one
    if not forecast:
        from src.models.forecast import Forecast
        forecast = Forecast(name="Empty", entries=[])

    # Get model solution from results (if available)
    # This enables MODEL MODE for accurate inventory tracking with initial inventory
    model_solution = None
    if 'model_solution' in results:
        model_solution = results['model_solution']

    # Create backend snapshot generator
    generator = DailySnapshotGenerator(
        production_schedule=production_schedule,
        shipments=shipments,
        locations_dict=locations,
        forecast=forecast,
        model_solution=model_solution  # Pass model solution to enable MODEL MODE
    )

    # Generate backend snapshot
    backend_snapshot = generator._generate_single_snapshot(selected_date)

    # Convert backend dataclasses to UI-friendly dict format
    snapshot = {
        'date': backend_snapshot.date,
        'total_inventory': backend_snapshot.total_system_inventory,
        'in_transit_total': backend_snapshot.total_in_transit,
        'production_total': sum(b.quantity for b in backend_snapshot.production_activity),
        'demand_total': sum(d.demand_quantity for d in backend_snapshot.demand_satisfied),
        'location_inventory': {},
        'in_transit_shipments': [],
        'production_batches': [],
        'inflows': [],
        'outflows': [],
        'demand_satisfaction': [],
    }

    # Convert location inventory
    for location_id, loc_inv in backend_snapshot.location_inventory.items():
        # Group batches by product
        batches_by_product = defaultdict(list)
        for batch in loc_inv.batches:
            batches_by_product[batch.product_id].append({
                'id': batch.batch_id,
                'quantity': batch.quantity,
                'production_date': batch.production_date,
                'age_days': batch.age_days,
            })

        snapshot['location_inventory'][location_id] = {
            'location_name': loc_inv.location_name,
            'total': loc_inv.total_quantity,
            'by_product': dict(loc_inv.by_product),
            'batches': dict(batches_by_product),
        }

    # Convert in-transit shipments
    for transit in backend_snapshot.in_transit:
        snapshot['in_transit_shipments'].append({
            'origin_id': transit.origin_id,
            'destination_id': transit.destination_id,
            'product_id': transit.product_id,
            'quantity': transit.quantity,
            'days_in_transit': transit.days_in_transit,
        })

    # Convert production batches
    for batch in backend_snapshot.production_activity:
        snapshot['production_batches'].append({
            'batch_id': batch.batch_id,
            'product_id': batch.product_id,
            'quantity': batch.quantity,
        })

    # Convert inflows (production and arrivals)
    for flow in backend_snapshot.inflows:
        flow_type_map = {
            'production': 'Production',
            'arrival': 'Arrival'
        }
        details = ''
        if flow.counterparty:
            details = f"From {flow.counterparty}"
        elif flow.batch_id:
            details = f"Batch {flow.batch_id}"

        snapshot['inflows'].append({
            'type': flow_type_map.get(flow.flow_type, flow.flow_type.title()),
            'location': flow.location_id,
            'product': flow.product_id,
            'quantity': flow.quantity,
            'details': details,
        })

    # Convert outflows (departures and demand)
    for flow in backend_snapshot.outflows:
        flow_type_map = {
            'departure': 'Departure',
            'demand': 'Demand'
        }
        details = ''
        if flow.counterparty:
            details = f"To {flow.counterparty}"
        else:
            details = 'Customer demand'

        snapshot['outflows'].append({
            'type': flow_type_map.get(flow.flow_type, flow.flow_type.title()),
            'location': flow.location_id,
            'product': flow.product_id,
            'quantity': flow.quantity,
            'details': details,
        })

    # Convert demand satisfaction
    for demand_record in backend_snapshot.demand_satisfied:
        snapshot['demand_satisfaction'].append({
            'destination': demand_record.destination_id,
            'product': demand_record.product_id,
            'demand': demand_record.demand_quantity,
            'supplied': demand_record.supplied_quantity,
            'status': '✅ Met' if demand_record.is_satisfied else f"⚠️ Short {demand_record.shortage_quantity:.0f}",
        })

    return snapshot


def _get_days_in_transit(shipment: Any, current_date: Date) -> int:
    """Calculate how many days a shipment has been in transit.

    Args:
        shipment: Shipment object or dict-like object with departure_date
        current_date: Current date for calculation

    Returns:
        Number of days in transit
    """
    # Handle both real Shipment objects and dict/SimpleNamespace objects
    departure_date = None

    if hasattr(shipment, 'departure_date'):
        departure_date = shipment.departure_date
    elif hasattr(shipment, 'production_date'):
        departure_date = shipment.production_date
    elif isinstance(shipment, dict) and 'departure_date' in shipment:
        departure_date = shipment['departure_date']
    elif isinstance(shipment, dict) and 'production_date' in shipment:
        departure_date = shipment['production_date']

    if not departure_date:
        return 0

    return (current_date - departure_date).days
