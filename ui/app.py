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
        st.info("**Phase 1: Foundation (In Progress)**")
        st.markdown(
            """
            - ✅ Data models created
            - ✅ Excel parser implemented
            - ✅ Basic UI framework
            - ⏳ Network modeling
            - ⏳ Shelf life engine
            """
        )

    with col2:
        st.subheader("🔑 Key Features")
        st.markdown(
            """
            **Current:**
            - Upload Excel forecasts (.xlsm)
            - View locations and routes
            - Basic data validation

            **Coming Soon:**
            - Route feasibility analysis
            - Shelf life tracking
            - Optimization recommendations
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
        Upload an Excel file (.xlsm or .xlsx) containing forecast data, locations, and routes.

        **Required sheets:**
        - `Forecast`: Sales forecast by location and date
        - `Locations`: Location definitions with storage capabilities
        - `Routes`: Transport routes with transit times
        """
    )

    uploaded_file = st.file_uploader(
        "Choose an Excel file",
        type=["xlsm", "xlsx"],
        help="Upload a file with Forecast, Locations, and Routes sheets",
    )

    if uploaded_file is not None:
        try:
            # Show file info
            st.success(f"✅ File uploaded: {uploaded_file.name}")

            # Read and display sheets
            st.subheader("File Contents")

            # Use tabs for different sheets
            tabs = st.tabs(["Forecast", "Locations", "Routes"])

            with tabs[0]:
                try:
                    df_forecast = pd.read_excel(uploaded_file, sheet_name="Forecast", engine="openpyxl")
                    st.dataframe(df_forecast, use_container_width=True)
                    st.caption(f"📊 {len(df_forecast)} forecast entries")
                except Exception as e:
                    st.error(f"Error reading Forecast sheet: {e}")

            with tabs[1]:
                try:
                    df_locations = pd.read_excel(uploaded_file, sheet_name="Locations", engine="openpyxl")
                    st.dataframe(df_locations, use_container_width=True)
                    st.caption(f"📍 {len(df_locations)} locations")
                except Exception as e:
                    st.error(f"Error reading Locations sheet: {e}")

            with tabs[2]:
                try:
                    df_routes = pd.read_excel(uploaded_file, sheet_name="Routes", engine="openpyxl")
                    st.dataframe(df_routes, use_container_width=True)
                    st.caption(f"🛣️ {len(df_routes)} routes")
                except Exception as e:
                    st.error(f"Error reading Routes sheet: {e}")

            # Parse button (placeholder for future functionality)
            if st.button("Parse and Validate Data", type="primary"):
                with st.spinner("Parsing data..."):
                    st.info("⏳ Full parsing functionality coming in next phase")

        except Exception as e:
            st.error(f"Error processing file: {e}")

    else:
        st.info("👆 Please upload an Excel file to get started")


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
