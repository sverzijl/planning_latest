"""Data upload page for forecast and network configuration files."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import tempfile
from ui import session_state
from ui.components.styling import (
    apply_custom_css,
    section_header,
    success_badge,
    info_badge,
)

# Page config
st.set_page_config(
    page_title="Upload Data",
    page_icon="📤",
    layout="wide",
)

# Apply custom CSS
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

st.markdown(section_header("Upload Data", level=1, icon="📤"), unsafe_allow_html=True)

st.markdown(
    """
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">📋 Required Files</div>
        <div>Upload TWO separate Excel files:</div>
        <ol style="margin-top: 8px; padding-left: 20px;">
            <li><strong>Forecast File:</strong> Sales demand by location and date</li>
            <li><strong>Network Configuration File:</strong> Locations, routes, labor, trucks, and costs</li>
        </ol>
        <div style="margin-top: 12px; font-size: 13px; color: #757575;">
            This separation allows you to update forecast data frequently while keeping network configuration stable.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Two-column layout for file uploads
col1, col2 = st.columns(2)

with col1:
    st.markdown(section_header("1️⃣ Forecast File", level=3), unsafe_allow_html=True)
    forecast_file = st.file_uploader(
        "Choose forecast file",
        type=["xlsm", "xlsx"],
        help="Excel file containing Forecast sheet with demand data",
        key="forecast_uploader",
    )
    if forecast_file:
        st.markdown(success_badge(forecast_file.name), unsafe_allow_html=True)

with col2:
    st.markdown(section_header("2️⃣ Network Configuration File", level=3), unsafe_allow_html=True)
    network_file = st.file_uploader(
        "Choose network config file",
        type=["xlsm", "xlsx"],
        help="Excel file with Locations, Routes, LaborCalendar, TruckSchedules, and CostParameters sheets",
        key="network_uploader",
    )
    if network_file:
        st.markdown(success_badge(network_file.name), unsafe_allow_html=True)

# Display file contents if uploaded
if forecast_file is not None or network_file is not None:
    st.divider()
    st.markdown(section_header("File Contents Preview", level=2, icon="📋"), unsafe_allow_html=True)

    # Create tabs based on what's uploaded
    if forecast_file and network_file:
        tabs = st.tabs(["Forecast", "Locations", "Routes", "LaborCalendar", "TruckSchedules", "CostParameters"])
    elif forecast_file:
        tabs = st.tabs(["Forecast"])
    else:
        tabs = st.tabs(["Locations", "Routes", "LaborCalendar", "TruckSchedules", "CostParameters"])

    tab_idx = 0

    # Forecast tab
    if forecast_file:
        with tabs[tab_idx]:
            try:
                df_forecast = pd.read_excel(forecast_file, sheet_name="Forecast", engine="openpyxl")
                st.dataframe(df_forecast.head(100), use_container_width=True)
                st.caption(f"📊 {len(df_forecast)} forecast entries (showing first 100)")
            except Exception as e:
                st.error(f"Error reading Forecast sheet: {e}")
                st.info("If you have a SAP IBP file, use the SAP IBP converter (coming soon)")
        tab_idx += 1

    # Network config tabs
    if network_file:
        # Locations
        with tabs[tab_idx]:
            try:
                df_locations = pd.read_excel(network_file, sheet_name="Locations", engine="openpyxl")
                st.dataframe(df_locations, use_container_width=True)
                st.caption(f"📍 {len(df_locations)} locations")
            except Exception as e:
                st.error(f"Error reading Locations sheet: {e}")
        tab_idx += 1

        # Routes
        with tabs[tab_idx]:
            try:
                df_routes = pd.read_excel(network_file, sheet_name="Routes", engine="openpyxl")
                st.dataframe(df_routes, use_container_width=True)
                st.caption(f"🛣️ {len(df_routes)} routes")
            except Exception as e:
                st.error(f"Error reading Routes sheet: {e}")
        tab_idx += 1

        # LaborCalendar
        with tabs[tab_idx]:
            try:
                df_labor = pd.read_excel(network_file, sheet_name="LaborCalendar", engine="openpyxl")
                st.dataframe(df_labor.head(30), use_container_width=True)
                st.caption(f"📅 {len(df_labor)} days (showing first 30)")
            except Exception as e:
                st.error(f"Error reading LaborCalendar sheet: {e}")
        tab_idx += 1

        # TruckSchedules
        with tabs[tab_idx]:
            try:
                df_trucks = pd.read_excel(network_file, sheet_name="TruckSchedules", engine="openpyxl")
                st.dataframe(df_trucks, use_container_width=True)
                st.caption(f"🚚 {len(df_trucks)} truck schedules")
            except Exception as e:
                st.error(f"Error reading TruckSchedules sheet: {e}")
        tab_idx += 1

        # CostParameters
        with tabs[tab_idx]:
            try:
                df_costs = pd.read_excel(network_file, sheet_name="CostParameters", engine="openpyxl")
                st.dataframe(df_costs, use_container_width=True)
                st.caption(f"💰 {len(df_costs)} cost parameters")
            except Exception as e:
                st.error(f"Error reading CostParameters sheet: {e}")

    # Parse and validate button
    if forecast_file and network_file:
        st.divider()
        if st.button("✅ Parse and Validate Data", type="primary", use_container_width=True):
            with st.spinner("Parsing and validating data..."):
                try:
                    from src.parsers import MultiFileParser
                    from src.models.location import LocationType

                    # Save uploaded files to temp locations
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f_forecast:
                        f_forecast.write(forecast_file.getvalue())
                        forecast_path = f_forecast.name

                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f_network:
                        f_network.write(network_file.getvalue())
                        network_path = f_network.name

                    # Parse files
                    parser = MultiFileParser(
                        forecast_file=forecast_path,
                        network_file=network_path
                    )

                    forecast_obj, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

                    # Find manufacturing site
                    manufacturing_site = None
                    for loc in locations:
                        if loc.type == LocationType.MANUFACTURING:
                            # Convert Location to ManufacturingSite
                            from src.models.manufacturing import ManufacturingSite
                            manufacturing_site = ManufacturingSite(
                                id=loc.id,
                                name=loc.name,
                                type=loc.type,
                                storage_mode=loc.storage_mode,
                                capacity=loc.capacity,
                                latitude=loc.latitude,
                                longitude=loc.longitude,
                                production_rate=1400.0,  # Default
                                labor_calendar=labor_calendar,
                                changeover_time_hours=0.5,  # Default
                            )
                            break

                    if manufacturing_site is None:
                        st.error("❌ No manufacturing location found in network configuration")
                    else:
                        # Validate consistency
                        validation_results = parser.validate_consistency(forecast_obj, locations, routes)

                        # Store in session state
                        session_state.store_parsed_data(
                            forecast=forecast_obj,
                            locations=locations,
                            routes=routes,
                            labor_calendar=labor_calendar,
                            truck_schedules=truck_schedules,
                            cost_structure=cost_structure,
                            manufacturing_site=manufacturing_site,
                            forecast_filename=forecast_file.name,
                            network_filename=network_file.name,
                        )

                        # Clear any previous planning results
                        session_state.clear_planning_results()

                        # Display results
                        st.success("✅ Parsing completed successfully!")
                        st.success("✅ Data stored in session state")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Forecast Entries", len(forecast_obj.entries))
                            st.metric("Locations", len(locations))
                        with col2:
                            st.metric("Routes", len(routes))
                            st.metric("Labor Days", len(labor_calendar.days))
                        with col3:
                            st.metric("Truck Schedules", len(truck_schedules))

                        # Show validation warnings
                        if validation_results["warnings"]:
                            st.warning("⚠️ Validation Warnings:")
                            for warning in validation_results["warnings"]:
                                st.write(f"- {warning}")
                        else:
                            st.success("✅ All validation checks passed!")

                        # Next step buttons
                        st.divider()
                        st.subheader("🎯 Next Steps")

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if st.button("📊 View Data Summary", use_container_width=True):
                                st.switch_page("pages/2_Data_Summary.py")
                        with col2:
                            if st.button("🚀 Run Planning Workflow", type="primary", use_container_width=True):
                                st.switch_page("pages/3_Planning_Workflow.py")
                        with col3:
                            if st.button("🏠 Back to Home", use_container_width=True):
                                st.switch_page("app.py")

                    # Clean up temp files
                    Path(forecast_path).unlink()
                    Path(network_path).unlink()

                except Exception as e:
                    st.error(f"❌ Error parsing files: {e}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())

else:
    st.info("👆 Please upload both files to get started")

    st.divider()

    st.markdown("""
    ### 📄 Required File Formats

    **Forecast File** should contain a sheet named "Forecast" with columns:
    - `location_id`: Destination location ID
    - `product_id`: Product identifier
    - `date`: Forecast date (YYYY-MM-DD)
    - `quantity`: Forecasted demand (units)

    **Network Configuration File** should contain 5 sheets:
    - `Locations`: Location definitions (id, name, type, storage_mode)
    - `Routes`: Routes between locations (origin_id, destination_id, transit_time_days, cost)
    - `LaborCalendar`: Daily labor availability (date, fixed_hours, rates)
    - `TruckSchedules`: Truck departure schedules (truck_name, departure_type, destination_id, day_of_week)
    - `CostParameters`: Cost structure (production_cost_per_unit, labor rates, storage costs, waste multiplier)

    See `data/examples/EXCEL_TEMPLATE_SPEC.md` for complete specification.
    """)
