"""Main Streamlit application for supply chain optimization.

This is the home page. Other pages are in the pages/ directory and will be
automatically discovered by Streamlit's multi-page app feature.
"""

import streamlit as st
from ui import session_state

# Set page configuration
st.set_page_config(
    page_title="GF Bread Supply Chain Optimizer",
    page_icon="🍞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
session_state.initialize_session_state()

# Main title
st.title("🍞 Gluten-Free Bread Supply Chain Optimizer")
st.markdown(
    """
    Integrated production scheduling and distribution planning for gluten-free bread
    from manufacturing through multi-echelon networks to breadroom destinations.
    """
)

st.divider()

# Status section
st.header("📊 Project Status")

col1, col2 = st.columns(2)

with col1:
    st.success("**Phase 1: Foundation ✅ Complete**")
    st.markdown(
        """
        - ✅ Data models (11 core models)
        - ✅ Excel parsers (multi-file support)
        - ✅ Network graph builder
        - ✅ Shelf life tracking engine
        - ✅ 100+ tests passing
        """
    )

    st.divider()

    st.success("**Phase 2: Core Logic ✅ Complete**")
    st.markdown(
        """
        - ✅ Production scheduler with labor optimization
        - ✅ Truck loading with D-1/D0 timing
        - ✅ Cost calculation engine (4 components)
        - ✅ Network analysis and route finding
        - ✅ End-to-end planning workflow
        - ✅ 200 tests passing
        """
    )

with col2:
    st.info("**Phase 3: Optimization 🔄 In Progress**")
    st.markdown(
        """
        **Coming Soon:**
        - Mathematical optimization (Pyomo)
        - Minimize total cost to serve
        - What-if scenario analysis
        - Multi-period rolling horizon
        - Sensitivity analysis
        - Production campaign optimization
        """
    )

st.divider()

# Current session status
st.header("🎯 Quick Start")

# Check data upload status
if session_state.is_data_uploaded():
    st.success("✅ Data Loaded")

    stats = session_state.get_summary_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Locations", stats.get('locations', 0))
        st.metric("Routes", stats.get('routes', 0))
    with col2:
        st.metric("Forecast Entries", stats.get('forecast_entries', 0))
        st.metric("Products", stats.get('products_in_forecast', 0))
    with col3:
        st.metric("Total Demand", f"{stats.get('total_demand', 0):,.0f}")
        st.metric("Planning Days", stats.get('date_range_days', 0))
    with col4:
        st.metric("Labor Days", stats.get('labor_days', 0))
        st.metric("Trucks/Week", stats.get('truck_schedules', 0))

    # Check planning status
    st.divider()

    if session_state.is_planning_complete():
        st.success("✅ Planning Complete")

        summary = session_state.get_planning_summary()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Production Batches", summary.get('production_batches', 0))
            st.metric("Total Units", f"{summary.get('total_units', 0):,.0f}")
        with col2:
            st.metric("Shipments", summary.get('shipments_count', 0))
            st.metric("Trucks Used", summary.get('trucks_used', 0))
        with col3:
            st.metric("Total Cost", f"${summary.get('total_cost', 0):,.2f}")
            st.metric("Cost/Unit", f"${summary.get('cost_per_unit', 0):.2f}")
        with col4:
            if summary.get('production_is_feasible', True) and summary.get('truck_plan_is_feasible', True):
                st.success("✅ Feasible Plan")
            else:
                st.warning("⚠️ Has Infeasibilities")

        # Quick navigation to results
        st.divider()
        st.subheader("📑 View Results")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("📦 Production Schedule", use_container_width=True):
                st.switch_page("pages/4_Production_Schedule.py")
        with col2:
            if st.button("🚚 Distribution Plan", use_container_width=True):
                st.switch_page("pages/5_Distribution_Plan.py")
        with col3:
            if st.button("💰 Cost Analysis", use_container_width=True):
                st.switch_page("pages/6_Cost_Analysis.py")
        with col4:
            if st.button("🔄 Re-run Planning", use_container_width=True):
                st.switch_page("pages/3_Planning_Workflow.py")

    else:
        st.info("ℹ️ Ready to plan. Run the planning workflow to generate production and distribution plans.")

        if st.button("🚀 Run Planning Workflow", type="primary", use_container_width=True):
            st.switch_page("pages/3_Planning_Workflow.py")

else:
    st.warning("⚠️ No data loaded. Upload forecast and network configuration files to get started.")

    if st.button("📤 Upload Data", type="primary", use_container_width=True):
        st.switch_page("pages/1_Upload_Data.py")

    st.divider()

    st.info("""
    **Getting Started:**

    1. **Upload Data** - Provide forecast and network configuration Excel files
    2. **Run Planning Workflow** - Generate production schedule, assign to trucks, calculate costs
    3. **Analyze Results** - Review production, distribution, and cost details
    4. **Optimize** (Phase 3) - Find optimal plans that minimize total cost to serve
    """)

st.divider()

# Business rules reference
st.header("📝 Key Business Rules")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Shelf Life")
    st.metric("Ambient", "17 days")
    st.metric("Frozen", "120 days")
    st.metric("Thawed", "14 days")

with col2:
    st.subheader("Quality Standards")
    st.metric("Min. Acceptable", "7 days")
    st.caption("Breadrooms discard stock with <7 days remaining")
    st.metric("Manufacturing Site", "6122")
    st.caption("Source location for all products")

with col3:
    st.subheader("Production Capacity")
    st.metric("Production Rate", "1,400 units/hour")
    st.metric("Regular Hours", "12h/day (Mon-Fri)")
    st.metric("Max w/ Overtime", "14h/day")
    st.caption("Weekend: 4h minimum payment")

st.divider()

# Network overview
st.header("🌐 Network Overview")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Distribution Network")
    st.markdown("""
    **Structure:** 2-echelon hub-and-spoke + frozen buffer

    - **Manufacturing:** Location 6122 (source)
    - **Regional Hubs:** 6104 (NSW/ACT), 6125 (VIC/TAS/SA)
    - **Frozen Buffer:** Lineage (WA route)
    - **Destinations:** 9 breadrooms across Australia
    - **Routes:** 10 route legs

    **Special:** WA (6130) receives frozen, thaws on-site (shelf life resets to 14 days)
    """)

with col2:
    st.subheader("Truck Schedule")
    st.markdown("""
    **Morning Truck (Daily Mon-Fri):**
    - Mon, Tue, Thu, Fri: 6122 → 6125
    - Wednesday: 6122 → Lineage → 6125
    - Loads D-1 production only

    **Afternoon Truck (Day-Specific):**
    - Monday: 6122 → 6104
    - Tuesday: 6122 → 6110
    - Wednesday: 6122 → 6104
    - Thursday: 6122 → 6110
    - Friday: 6122 → 6110 AND 6122 → 6104 (2 trucks)
    - Loads D-1 or D0 production
    """)

st.divider()

# Footer
st.caption("Built with Streamlit • Powered by Pyomo • Phase 2 Complete ✅")
