"""Distribution plan analysis page."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from datetime import datetime
from ui import session_state
from ui.components import (
    render_truck_loading_timeline,
    render_truck_utilization_chart,
    render_shipments_by_destination_chart,
    render_daily_truck_count_chart,
    render_shipments_table,
    render_truck_loads_table,
    render_unassigned_shipments_table,
    render_date_range_filter,
    apply_date_filter,
)
from ui.components.styling import apply_custom_css, section_header

# Page config
st.set_page_config(
    page_title="Distribution Plan",
    page_icon="🚚",
    layout="wide",
)

# Apply custom CSS
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

st.markdown(section_header("Distribution Plan", level=1, icon="🚚"), unsafe_allow_html=True)

# Check if planning is complete
if not session_state.is_planning_complete():
    st.warning("⚠️ No distribution plan available. Please run the planning workflow first.")
    if st.button("Go to Planning Workflow", type="primary"):
        st.switch_page("pages/3_Planning_Workflow.py")
    st.stop()

# Get planning results
results = session_state.get_planning_results()
all_shipments = results['shipments']
truck_plan = results['truck_plan']

# Date Range Filter
st.divider()

# Get date range from shipments (using delivery_date)
if all_shipments:
    # Extract delivery dates from shipments
    delivery_dates = [s.delivery_date for s in all_shipments if hasattr(s, 'delivery_date') and s.delivery_date]

    if delivery_dates:
        min_date = min(delivery_dates)
        max_date = max(delivery_dates)

        # Convert to datetime for filter component
        min_datetime = datetime.combine(min_date, datetime.min.time())
        max_datetime = datetime.combine(max_date, datetime.min.time())

        # Render date filter
        filter_start_date, filter_end_date = render_date_range_filter(
            min_date=min_datetime,
            max_date=max_datetime,
            default_range="2weeks",
            key_prefix="distribution_filter",
            include_url_params=True
        )

        # Filter shipments based on delivery date range
        shipments = [
            s for s in all_shipments
            if hasattr(s, 'delivery_date') and s.delivery_date
            and filter_start_date.date() <= s.delivery_date <= filter_end_date.date()
        ]

        # Filter truck loads based on departure date
        filtered_loads = [
            load for load in truck_plan.loads
            if hasattr(load, 'departure_date') and load.departure_date
            and filter_start_date.date() <= load.departure_date <= filter_end_date.date()
        ]

        # Create filtered truck plan
        from src.production.truck_loader import TruckPlan
        filtered_truck_plan = TruckPlan(
            loads=filtered_loads,
            unassigned_shipments=[s for s in truck_plan.unassigned_shipments
                                 if hasattr(s, 'delivery_date') and s.delivery_date
                                 and filter_start_date.date() <= s.delivery_date <= filter_end_date.date()],
            infeasibilities=truck_plan.infeasibilities,
            total_trucks_used=len(filtered_loads),
            average_utilization=sum(load.utilization for load in filtered_loads) / len(filtered_loads) if filtered_loads else 0,
        )
    else:
        # No delivery dates, use all shipments
        shipments = all_shipments
        filtered_truck_plan = truck_plan
else:
    # No shipments
    shipments = all_shipments
    filtered_truck_plan = truck_plan

st.divider()

# Summary metrics
st.markdown(section_header("Distribution Summary", level=2, icon="📊"), unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Shipments", len(shipments))
    total_units = sum(s.quantity for s in shipments)
    st.metric("Total Units", f"{total_units:,.0f}")

with col2:
    st.metric("Trucks Used", filtered_truck_plan.total_trucks_used)
    st.metric("Avg Utilization", f"{filtered_truck_plan.average_utilization:.1%}")

with col3:
    destinations = len(set(s.destination_id for s in shipments))
    st.metric("Destinations", destinations)
    st.metric("Unassigned", len(filtered_truck_plan.unassigned_shipments))

with col4:
    if truck_plan.is_feasible():
        st.success("✅ Feasible")
    else:
        st.error(f"❌ {len(truck_plan.infeasibilities)} Issues")

    # Show filtered vs total
    if len(shipments) < len(all_shipments):
        st.caption(f"**Filtered:** {len(shipments)} / {len(all_shipments)} shipments")

# Show infeasibilities if any
if not truck_plan.is_feasible():
    st.divider()
    st.error("⚠️ **Truck Loading Infeasibilities:**")
    for infeas in truck_plan.infeasibilities[:10]:  # Show first 10
        st.warning(f"- {infeas}")

    if len(truck_plan.infeasibilities) > 10:
        st.caption(f"... and {len(truck_plan.infeasibilities) - 10} more")

st.divider()

# Visualizations
tab1, tab2, tab3, tab4 = st.tabs([
    "🚛 Truck Loading",
    "📦 Shipments",
    "📊 Analysis",
    "📋 Detailed Tables"
])

with tab1:
    st.markdown(section_header("Truck Loading Timeline", level=3), unsafe_allow_html=True)
    st.markdown("Shows truck departures, destinations, and loading over time")

    fig = render_truck_loading_timeline(filtered_truck_plan, height=600)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Truck utilization
    st.markdown("**Truck Utilization Analysis**")
    fig = render_truck_utilization_chart(filtered_truck_plan, height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Color coding: 🟢 High (≥90%), 🔵 Medium (70-90%), 🟡 Low-Medium (50-70%), 🔴 Low (<50%)")

with tab2:
    st.markdown(section_header("Shipments by Destination", level=3), unsafe_allow_html=True)

    fig = render_shipments_by_destination_chart(filtered_truck_plan, height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Daily truck count
    st.markdown("**Daily Truck Count**")
    fig = render_daily_truck_count_chart(filtered_truck_plan, height=400)
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.markdown(section_header("Distribution Analysis", level=3), unsafe_allow_html=True)

    # Breakdown by departure type
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**By Departure Type**")
        morning_trucks = sum(1 for load in filtered_truck_plan.loads if load.departure_type == 'morning')
        afternoon_trucks = sum(1 for load in filtered_truck_plan.loads if load.departure_type == 'afternoon')

        st.metric("Morning Trucks", morning_trucks)
        st.metric("Afternoon Trucks", afternoon_trucks)

    with col2:
        st.markdown("**By Transport Mode**")
        # Count shipments by transport mode
        ambient_shipments = sum(1 for s in shipments if s.route and s.route.transport_modes and 'ambient' in s.route.transport_modes)
        frozen_shipments = sum(1 for s in shipments if s.route and s.route.transport_modes and 'frozen' in s.route.transport_modes)

        st.metric("Ambient Shipments", ambient_shipments)
        st.metric("Frozen Shipments", frozen_shipments)

    st.divider()

    # Route analysis
    st.markdown("**Route Analysis**")

    # Group shipments by route path
    route_counts = {}
    for s in shipments:
        if s.route:
            route_key = " → ".join(s.route.path)
            if route_key not in route_counts:
                route_counts[route_key] = {'count': 0, 'units': 0}
            route_counts[route_key]['count'] += 1
            route_counts[route_key]['units'] += s.quantity

    # Display top routes
    sorted_routes = sorted(route_counts.items(), key=lambda x: x[1]['units'], reverse=True)

    route_data = []
    for route, stats in sorted_routes[:10]:  # Top 10 routes
        route_data.append({
            'Route': route,
            'Shipments': stats['count'],
            'Total Units': f"{stats['units']:,.0f}"
        })

    if route_data:
        df = pd.DataFrame(route_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Showing top {len(route_data)} routes by volume")

with tab4:
    st.markdown(section_header("Detailed Data Tables", level=3), unsafe_allow_html=True)

    # Sub-tabs for different tables
    subtab1, subtab2, subtab3 = st.tabs(["Shipments", "Truck Loads", "Unassigned"])

    with subtab1:
        st.markdown("**All Shipments**")

        # Filters
        col1, col2 = st.columns(2)

        with col1:
            # Destination filter
            all_destinations = sorted(set(s.destination_id for s in shipments))
            selected_destinations = st.multiselect(
                "Filter by Destination",
                options=all_destinations,
                default=all_destinations,
                key="dest_filter"
            )

        with col2:
            # Product filter
            all_products = sorted(set(s.product_id for s in shipments))
            selected_products = st.multiselect(
                "Filter by Product",
                options=all_products,
                default=all_products,
                key="shipment_product_filter"
            )

        # Filter shipments
        filtered_shipments = [
            s for s in shipments
            if s.destination_id in selected_destinations and s.product_id in selected_products
        ]

        st.caption(f"Showing {len(filtered_shipments)} of {len(shipments)} shipments")
        render_shipments_table(filtered_shipments)

    with subtab2:
        st.markdown("**Truck Loads**")
        render_truck_loads_table(filtered_truck_plan)

    with subtab3:
        st.markdown("**Unassigned Shipments**")
        render_unassigned_shipments_table(filtered_truck_plan)

    # Export option
    st.divider()

    col1, col2 = st.columns([3, 1])

    with col1:
        st.caption("Export shipment plan to Excel with truck loading schedules and manifests")

    with col2:
        if st.button("📥 Export to Excel", type="secondary", use_container_width=True):
            try:
                import tempfile
                import os
                from src.exporters import export_shipment_plan

                # Create temporary file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"shipment_plan_{timestamp}.xlsx"
                temp_dir = tempfile.gettempdir()
                output_path = os.path.join(temp_dir, filename)

                # Export to Excel
                with st.spinner("Generating Excel file..."):
                    export_shipment_plan(
                        shipment_data=all_shipments,
                        truck_plan=truck_plan,
                        output_path=output_path,
                        truck_capacity=14080  # 44 pallets * 320 units
                    )

                # Read file for download
                with open(output_path, 'rb') as f:
                    excel_data = f.read()

                # Provide download button
                st.download_button(
                    label="💾 Download Excel File",
                    data=excel_data,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )

                st.success(f"✅ Excel file generated: {filename}")

            except Exception as e:
                st.error(f"❌ Error exporting to Excel: {str(e)}")
                st.exception(e)

# Footer with navigation
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Production Schedule", use_container_width=True):
        st.switch_page("pages/4_Production_Schedule.py")

with col2:
    if st.button("Cost Analysis →", use_container_width=True):
        st.switch_page("pages/6_Cost_Analysis.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
