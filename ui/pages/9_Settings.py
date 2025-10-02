"""Settings page for application configuration."""

import streamlit as st
from ui import session_state

# Page config
st.set_page_config(
    page_title="Settings",
    page_icon="⚙️",
    layout="wide",
)

# Initialize session state
session_state.initialize_session_state()

st.header("⚙️ Settings")

st.markdown("""
Configure application settings, display preferences, and data management options.
""")

st.divider()

# Product settings
st.subheader("📦 Product Settings")

col1, col2 = st.columns(2)

with col1:
    ambient_shelf_life = st.number_input(
        "Ambient Shelf Life (days)",
        value=17,
        min_value=1,
        max_value=365,
        help="Number of days products remain fresh in ambient storage"
    )
    frozen_shelf_life = st.number_input(
        "Frozen Shelf Life (days)",
        value=120,
        min_value=1,
        max_value=365,
        help="Number of days products remain fresh in frozen storage"
    )

with col2:
    thawed_shelf_life = st.number_input(
        "Thawed Shelf Life (days)",
        value=14,
        min_value=1,
        max_value=365,
        help="Number of days after thawing (e.g., at WA breadroom 6130)"
    )
    min_acceptable_shelf_life = st.number_input(
        "Minimum Acceptable (days)",
        value=7,
        min_value=0,
        max_value=365,
        help="Minimum shelf life required for breadroom acceptance"
    )

st.caption("Note: These settings are for reference only. Actual values are defined in the Product data model.")

st.divider()

# Display preferences
st.subheader("🎨 Display Preferences")

col1, col2 = st.columns(2)

with col1:
    chart_height = st.slider(
        "Default Chart Height (px)",
        min_value=300,
        max_value=800,
        value=400,
        step=50,
        help="Default height for charts and visualizations"
    )

    table_rows = st.slider(
        "Table Rows to Display",
        min_value=10,
        max_value=100,
        value=50,
        step=10,
        help="Number of rows to show in data tables before pagination"
    )

with col2:
    chart_theme = st.selectbox(
        "Chart Color Theme",
        options=["Default", "Pastel", "Bold", "Grayscale"],
        help="Color scheme for charts and graphs"
    )

    number_format = st.selectbox(
        "Number Format",
        options=["1,234.56", "1234.56", "1.234,56"],
        help="How to display numbers throughout the application"
    )

st.caption("Note: Display preferences are not yet fully implemented. Coming in future updates.")

st.divider()

# Optimization settings (Phase 3)
st.subheader("🔧 Optimization Settings")

st.info("⏳ Mathematical optimization features will be available in Phase 3")

col1, col2 = st.columns(2)

with col1:
    solver = st.selectbox(
        "Solver",
        options=["CBC (Open Source)", "Gurobi (Commercial)", "CPLEX (Commercial)"],
        help="Mathematical programming solver to use for optimization"
    )

    time_limit = st.number_input(
        "Time Limit (seconds)",
        value=300,
        min_value=10,
        max_value=3600,
        step=30,
        help="Maximum time allowed for solver to find solution"
    )

with col2:
    mip_gap = st.number_input(
        "MIP Gap Tolerance (%)",
        value=1.0,
        min_value=0.0,
        max_value=10.0,
        step=0.1,
        help="Acceptable optimality gap (0% = optimal, higher = faster but less optimal)"
    )

    parallel_threads = st.number_input(
        "Parallel Threads",
        value=4,
        min_value=1,
        max_value=16,
        step=1,
        help="Number of CPU threads to use for parallel solving"
    )

st.caption("Optimization settings will be used when Phase 3 optimization features are implemented.")

st.divider()

# Data management
st.subheader("💾 Data Management")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Current Session Data:**")

    if session_state.is_data_uploaded():
        st.success("✅ Data loaded")
        if st.button("🗑️ Clear All Data", type="secondary", use_container_width=True):
            if st.confirm("Are you sure you want to clear all data? This cannot be undone."):
                session_state.clear_all_data()
                st.success("All data cleared!")
                st.rerun()
    else:
        st.info("No data currently loaded")

with col2:
    st.markdown("**Planning Results:**")

    if session_state.is_planning_complete():
        st.success("✅ Planning results available")
        if st.button("🔄 Clear Planning Results", type="secondary", use_container_width=True):
            session_state.clear_planning_results()
            st.success("Planning results cleared!")
            st.rerun()
    else:
        st.info("No planning results")

st.divider()

# Session info
st.subheader("📊 Session Information")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Data Status:**")
    if session_state.is_data_uploaded():
        stats = session_state.get_summary_stats()
        st.write(f"- Locations: {stats.get('locations', 0)}")
        st.write(f"- Routes: {stats.get('routes', 0)}")
        st.write(f"- Forecast: {stats.get('forecast_entries', 0)} entries")
    else:
        st.write("- No data loaded")

with col2:
    st.markdown("**Planning Status:**")
    if session_state.is_planning_complete():
        summary = session_state.get_planning_summary()
        st.write(f"- Batches: {summary.get('production_batches', 0)}")
        st.write(f"- Shipments: {summary.get('shipments_count', 0)}")
        st.write(f"- Trucks: {summary.get('trucks_used', 0)}")
    else:
        st.write("- No planning results")

with col3:
    st.markdown("**System Info:**")
    st.write("- Streamlit Version: 1.28+")
    st.write("- Phase: 2 Complete")
    st.write("- Tests: 200 passing")

st.divider()

# Footer with navigation
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Route Analysis", use_container_width=True):
        st.switch_page("pages/8_Route_Analysis.py")

with col2:
    if st.button("📤 Upload Data", use_container_width=True):
        st.switch_page("pages/1_Upload_Data.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
