"""Main Streamlit application for supply chain optimization."""

import streamlit as st
from pathlib import Path
import pandas as pd

# Set page configuration
st.set_page_config(
    page_title="GF Bread Supply Chain Optimizer",
    page_icon="🍞",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    """Main application entry point."""
    st.title("🍞 Gluten-Free Bread Supply Chain Optimizer")
    st.markdown(
        """
        Optimize distribution of gluten-free bread from manufacturing to breadrooms
        through multi-echelon frozen/ambient networks.
        """
    )

    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Go to",
        ["Home", "Upload Data", "Network Visualization", "Route Analysis", "Settings"],
    )

    # Render selected page
    if page == "Home":
        render_home_page()
    elif page == "Upload Data":
        render_upload_page()
    elif page == "Network Visualization":
        render_network_page()
    elif page == "Route Analysis":
        render_route_analysis_page()
    elif page == "Settings":
        render_settings_page()


def render_home_page():
    """Render the home page."""
    st.header("Welcome")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Project Status")
        st.success("**Phase 1: Foundation (Complete)**")
        st.markdown(
            """
            - ✅ Data models created (9 models)
            - ✅ Excel parsers (single & multi-file)
            - ✅ Network configuration file
            - ✅ Two-file upload workflow
            - ✅ 41 tests passing
            """
        )

    with col2:
        st.subheader("🔑 Key Features")
        st.markdown(
            """
            **Current:**
            - Two-file upload (forecast + network config)
            - 11 locations, 10 routes, 11 trucks/week
            - 204-day planning horizon
            - Data validation & consistency checks

            **Coming Soon (Phase 2):**
            - Route feasibility analysis
            - Shelf life tracking
            - Production scheduling
            """
        )

    st.divider()

    st.subheader("📝 Business Rules")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Ambient Shelf Life", "17 days")
        st.metric("Frozen Shelf Life", "120 days")

    with col2:
        st.metric("Thawed Shelf Life", "14 days", delta="After thawing")
        st.metric("Min. Acceptable", "7 days", delta="Breadroom policy")

    with col3:
        st.metric("Manufacturing Site", "6122")
        st.caption("Source location for all products")


def render_upload_page():
    """Render the data upload page."""
    st.header("📤 Upload Data")

    st.markdown(
        """
        Upload TWO separate Excel files:
        1. **Forecast File**: Sales demand by location and date
        2. **Network Configuration File**: Locations, routes, labor, trucks, and costs

        This separation allows you to update forecast data frequently while keeping
        network configuration stable.
        """
    )

    # Two-column layout for file uploads
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1️⃣ Forecast File")
        forecast_file = st.file_uploader(
            "Choose forecast file",
            type=["xlsm", "xlsx"],
            help="Excel file containing Forecast sheet with demand data",
            key="forecast_uploader",
        )
        if forecast_file:
            st.success(f"✅ {forecast_file.name}")

    with col2:
        st.subheader("2️⃣ Network Configuration File")
        network_file = st.file_uploader(
            "Choose network config file",
            type=["xlsm", "xlsx"],
            help="Excel file with Locations, Routes, LaborCalendar, TruckSchedules, and CostParameters sheets",
            key="network_uploader",
        )
        if network_file:
            st.success(f"✅ {network_file.name}")

    # Display file contents if uploaded
    if forecast_file is not None or network_file is not None:
        st.divider()
        st.subheader("📋 File Contents")

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
            if st.button("Parse and Validate Data", type="primary"):
                with st.spinner("Parsing and validating data..."):
                    try:
                        from pathlib import Path
                        import tempfile
                        from src.parsers import MultiFileParser

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

                        # Validate consistency
                        validation_results = parser.validate_consistency(forecast_obj, locations, routes)

                        # Display results
                        st.success("✅ Parsing completed successfully!")

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

                        # Clean up temp files
                        Path(forecast_path).unlink()
                        Path(network_path).unlink()

                    except Exception as e:
                        st.error(f"❌ Error parsing files: {e}")
                        import traceback
                        st.code(traceback.format_exc())

    else:
        st.info("👆 Please upload both files to get started")


def render_network_page():
    """Render the network visualization page."""
    st.header("🌐 Network Visualization")
    st.info("⏳ Network visualization will be available in Phase 2")

    st.markdown(
        """
        **Planned features:**
        - Interactive network graph
        - Location nodes with storage mode indicators
        - Route edges with transit times
        - Path highlighting
        """
    )


def render_route_analysis_page():
    """Render the route analysis page."""
    st.header("📊 Route Analysis")
    st.info("⏳ Route analysis will be available in Phase 2")

    st.markdown(
        """
        **Planned features:**
        - Route enumeration
        - Feasibility checking
        - Shelf life calculations
        - Route recommendations
        """
    )


def render_settings_page():
    """Render the settings page."""
    st.header("⚙️ Settings")

    st.subheader("Product Settings")

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Ambient Shelf Life (days)", value=17, min_value=1, max_value=365)
        st.number_input("Frozen Shelf Life (days)", value=120, min_value=1, max_value=365)

    with col2:
        st.number_input("Thawed Shelf Life (days)", value=14, min_value=1, max_value=365)
        st.number_input("Minimum Acceptable (days)", value=7, min_value=0, max_value=365)

    st.divider()

    st.subheader("Optimization Settings")
    st.info("⏳ Optimization settings will be available in Phase 3")


if __name__ == "__main__":
    main()
