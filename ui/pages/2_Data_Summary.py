"""Data summary page showing all loaded data."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from ui import session_state

# Page config
st.set_page_config(
    page_title="Data Summary",
    page_icon="📊",
    layout="wide",
)

# Initialize session state
session_state.initialize_session_state()

st.header("📊 Data Summary")

# Check if data uploaded
if not session_state.is_data_uploaded():
    st.warning("⚠️ No data loaded. Please upload files first.")
    if st.button("📤 Go to Upload Page", type="primary"):
        st.switch_page("pages/1_Upload_Data.py")
    st.stop()

# Get data
data = session_state.get_parsed_data()
stats = session_state.get_summary_stats()

# Summary metrics
st.subheader("📈 Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Locations", stats.get('locations', 0))
    st.metric("Routes", stats.get('routes', 0))

with col2:
    st.metric("Forecast Entries", stats.get('forecast_entries', 0))
    st.metric("Products", stats.get('products_in_forecast', 0))

with col3:
    st.metric("Total Demand", f"{stats.get('total_demand', 0):,.0f}")
    date_range_days = stats.get('date_range_days', 0)
    st.metric("Planning Horizon", f"{date_range_days} days")

with col4:
    st.metric("Labor Days", stats.get('labor_days', 0))
    st.metric("Truck Schedules", stats.get('truck_schedules', 0))

# File information
if session_state.st.session_state.get('forecast_filename'):
    st.caption(f"**Forecast File:** {session_state.st.session_state['forecast_filename']}")
if session_state.st.session_state.get('network_filename'):
    st.caption(f"**Network File:** {session_state.st.session_state['network_filename']}")

st.divider()

# Tabbed data views
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Forecast",
    "Locations",
    "Routes",
    "Labor Calendar",
    "Truck Schedules",
    "Cost Parameters"
])

with tab1:
    st.subheader("Forecast Data")

    forecast = data['forecast']

    if forecast and forecast.entries:
        # Summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Entries", len(forecast.entries))
        with col2:
            st.metric("Date Range", f"{stats.get('date_range_start')} to {stats.get('date_range_end')}")
        with col3:
            st.metric("Total Demand", f"{sum(e.quantity for e in forecast.entries):,.0f} units")

        st.divider()

        # Convert to dataframe
        forecast_data = []
        for entry in forecast.entries:
            forecast_data.append({
                'Location': entry.location_id,
                'Product': entry.product_id,
                'Date': entry.forecast_date,
                'Quantity': entry.quantity,
            })

        df = pd.DataFrame(forecast_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} forecast entries")
    else:
        st.info("No forecast data available")

with tab2:
    st.subheader("Locations")

    locations = data['locations']

    if locations:
        loc_data = []
        for loc in locations:
            loc_data.append({
                'ID': loc.id,
                'Name': loc.name,
                'Type': loc.type,
                'Storage Mode': loc.storage_mode,
                'Capacity': loc.capacity or '-',
            })

        df = pd.DataFrame(loc_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} locations")
    else:
        st.info("No location data available")

with tab3:
    st.subheader("Routes")

    routes = data['routes']

    if routes:
        route_data = []
        for route in routes:
            route_data.append({
                'ID': route.id,
                'Origin': route.origin_id,
                'Destination': route.destination_id,
                'Transit Days': route.transit_time_days,
                'Mode': route.transport_mode,
                'Cost/Unit': f"${route.cost:.2f}" if route.cost else '-',
            })

        df = pd.DataFrame(route_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} routes")
    else:
        st.info("No route data available")

with tab4:
    st.subheader("Labor Calendar")

    labor_calendar = data['labor_calendar']

    if labor_calendar and labor_calendar.days:
        labor_data = []
        for day in labor_calendar.days[:100]:  # Show first 100 days
            labor_data.append({
                'Date': day.date,
                'Fixed Hours': day.fixed_hours,
                'Regular Rate': f"${day.regular_rate:.2f}",
                'Overtime Rate': f"${day.overtime_rate:.2f}",
                'Non-Fixed Rate': f"${day.non_fixed_rate:.2f}",
                'Is Fixed Day': '✓' if day.is_fixed_day else '',
            })

        df = pd.DataFrame(labor_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Showing first 100 of {len(labor_calendar.days)} days")
    else:
        st.info("No labor calendar data available")

with tab5:
    st.subheader("Truck Schedules")

    truck_schedules = data['truck_schedules']

    if truck_schedules:
        truck_data = []
        for truck in truck_schedules:
            truck_data.append({
                'ID': truck.id,
                'Name': truck.truck_name,
                'Type': truck.departure_type,
                'Destination': truck.destination_id,
                'Day of Week': truck.day_of_week or 'Daily',
                'Capacity': f"{truck.capacity:,.0f} units",
                'Pallets': truck.pallet_capacity,
            })

        df = pd.DataFrame(truck_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} truck schedules")
    else:
        st.info("No truck schedule data available")

with tab6:
    st.subheader("Cost Parameters")

    cost_structure = data['cost_structure']

    if cost_structure:
        cost_data = [
            {'Parameter': 'Production Cost per Unit', 'Value': f"${cost_structure.production_cost_per_unit:.2f}"},
            {'Parameter': 'Default Regular Rate', 'Value': f"${cost_structure.default_regular_rate:.2f}/hour"},
            {'Parameter': 'Default Overtime Rate', 'Value': f"${cost_structure.default_overtime_rate:.2f}/hour"},
            {'Parameter': 'Default Non-Fixed Rate', 'Value': f"${cost_structure.default_non_fixed_rate:.2f}/hour"},
            {'Parameter': 'Storage Cost (Frozen)', 'Value': f"${cost_structure.storage_cost_frozen_per_unit_day:.3f}/unit/day"},
            {'Parameter': 'Storage Cost (Ambient)', 'Value': f"${cost_structure.storage_cost_ambient_per_unit_day:.3f}/unit/day"},
            {'Parameter': 'Waste Cost Multiplier', 'Value': f"{cost_structure.waste_cost_multiplier}x"},
            {'Parameter': 'Shortage Penalty', 'Value': f"${cost_structure.shortage_penalty_per_unit:.2f}/unit"},
        ]

        df = pd.DataFrame(cost_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No cost parameter data available")

st.divider()

# Navigation buttons
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Back to Upload", use_container_width=True):
        st.switch_page("pages/1_Upload_Data.py")

with col2:
    if st.button("🚀 Run Planning", type="primary", use_container_width=True):
        st.switch_page("pages/3_Planning_Workflow.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
