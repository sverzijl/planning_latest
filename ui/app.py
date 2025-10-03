"""Main Streamlit application for supply chain optimization.

This is the home page. Other pages are in the pages/ directory and will be
automatically discovered by Streamlit's multi-page app feature.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from ui import session_state
from ui.components.styling import (
    apply_custom_css,
    section_header,
    phase_card,
    status_badge,
    colored_metric,
    success_badge,
    info_badge,
)

# Set page configuration
st.set_page_config(
    page_title="GF Bread Supply Chain Optimizer",
    page_icon="🍞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply custom CSS
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

# Main title
st.markdown(section_header("Gluten-Free Bread Supply Chain Optimizer", level=1, icon="🍞"), unsafe_allow_html=True)
st.markdown(
    """
    <div class="body-text" style="margin-bottom: 24px;">
    Integrated production scheduling and distribution planning for gluten-free bread
    from manufacturing through multi-echelon networks to breadroom destinations.
    </div>
    """,
    unsafe_allow_html=True
)

st.divider()

# Status section
st.markdown(section_header("Project Status", level=2, icon="📊"), unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    phase1_items = [
        "✅ Data models (11 core models)",
        "✅ Excel parsers (multi-file support)",
        "✅ Network graph builder",
        "✅ Shelf life tracking engine",
        "✅ 100+ tests passing"
    ]
    st.markdown(phase_card("Phase 1: Foundation", phase1_items, "complete", "✅"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    phase2_items = [
        "✅ Production scheduler with labor optimization",
        "✅ Truck loading with D-1/D0 timing",
        "✅ Cost calculation engine (4 components)",
        "✅ Network analysis and route finding",
        "✅ End-to-end planning workflow",
        "✅ 200 tests passing"
    ]
    st.markdown(phase_card("Phase 2: Core Logic", phase2_items, "complete", "✅"), unsafe_allow_html=True)

with col2:
    phase3_items = [
        "✅ Mathematical optimization (Pyomo)",
        "✅ Minimize total cost to serve",
        "✅ Shortage penalties (soft constraints)",
        "✅ Shelf life enforcement",
        "✅ Multi-solver support (CBC, GLPK, Gurobi, CPLEX)",
        "✅ Demand satisfaction diagnostics",
        "✅ Cross-platform compatibility"
    ]
    st.markdown(phase_card("Phase 3: Optimization", phase3_items, "complete", "⚡"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    phase4_items = [
        "Rolling horizon planning",
        "Stochastic demand scenarios",
        "Integer pallet optimization",
        "Flexible truck routing",
        "What-if scenario comparison"
    ]
    st.markdown(phase_card("Phase 4: Advanced Features", phase4_items, "planned", "🔜"), unsafe_allow_html=True)

st.divider()

# Current session status
st.markdown(section_header("Quick Start", level=2, icon="🎯"), unsafe_allow_html=True)

# Check data upload status
if session_state.is_data_uploaded():
    st.markdown(success_badge("Data Loaded"), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    stats = session_state.get_summary_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            colored_metric("Locations", str(stats.get('locations', 0)), "primary"),
            unsafe_allow_html=True
        )
        st.markdown(
            colored_metric("Routes", str(stats.get('routes', 0)), "primary"),
            unsafe_allow_html=True
        )
    with col2:
        st.markdown(
            colored_metric("Forecast Entries", f"{stats.get('forecast_entries', 0):,}", "secondary"),
            unsafe_allow_html=True
        )
        st.markdown(
            colored_metric("Products", str(stats.get('products_in_forecast', 0)), "secondary"),
            unsafe_allow_html=True
        )
    with col3:
        st.markdown(
            colored_metric("Total Demand", f"{stats.get('total_demand', 0):,.0f}", "accent"),
            unsafe_allow_html=True
        )
        st.markdown(
            colored_metric("Planning Days", str(stats.get('date_range_days', 0)), "accent"),
            unsafe_allow_html=True
        )
    with col4:
        st.markdown(
            colored_metric("Labor Days", str(stats.get('labor_days', 0)), "success"),
            unsafe_allow_html=True
        )
        st.markdown(
            colored_metric("Trucks/Week", str(stats.get('truck_schedules', 0)), "success"),
            unsafe_allow_html=True
        )

    # Check planning status
    st.divider()

    if session_state.is_planning_complete():
        st.markdown(success_badge("Planning Complete"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        summary = session_state.get_planning_summary()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(
                colored_metric("Production Batches", str(summary.get('production_batches', 0)), "primary"),
                unsafe_allow_html=True
            )
            st.markdown(
                colored_metric("Total Units", f"{summary.get('total_units', 0):,.0f}", "primary"),
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                colored_metric("Shipments", str(summary.get('shipments_count', 0)), "secondary"),
                unsafe_allow_html=True
            )
            st.markdown(
                colored_metric("Trucks Used", str(summary.get('trucks_used', 0)), "secondary"),
                unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                colored_metric("Total Cost", f"${summary.get('total_cost', 0):,.2f}", "accent"),
                unsafe_allow_html=True
            )
            st.markdown(
                colored_metric("Cost/Unit", f"${summary.get('cost_per_unit', 0):.2f}", "accent"),
                unsafe_allow_html=True
            )
        with col4:
            if summary.get('production_is_feasible', True) and summary.get('truck_plan_is_feasible', True):
                st.markdown(success_badge("Feasible Plan"), unsafe_allow_html=True)
            else:
                st.markdown(
                    status_badge("warning", "Has Infeasibilities", icon="⚠️"),
                    unsafe_allow_html=True
                )

        # Quick navigation to results
        st.divider()
        st.markdown(section_header("View Results", level=3, icon="📑"), unsafe_allow_html=True)

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            if st.button("📦 Production Schedule", use_container_width=True):
                st.switch_page("pages/3_Results.py")
        with col2:
            if st.button("🚚 Distribution Plan", use_container_width=True):
                st.switch_page("pages/3_Results.py")
        with col3:
            if st.button("💰 Cost Analysis", use_container_width=True):
                st.switch_page("pages/3_Results.py")
        with col4:
            if st.button("⚡ Optimization", use_container_width=True):
                st.switch_page("pages/2_Planning.py")
        with col5:
            if st.button("🔄 Re-run Planning", use_container_width=True):
                st.switch_page("pages/2_Planning.py")

    else:
        st.markdown(info_badge("Ready to plan"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="body-text">
        Run the planning workflow to generate production and distribution plans.
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 Run Planning Workflow (Heuristic)", type="primary", use_container_width=True):
                st.switch_page("pages/2_Planning.py")
        with col2:
            if st.button("⚡ Run Optimization (Optimal)", type="primary", use_container_width=True):
                st.switch_page("pages/2_Planning.py")

else:
    st.markdown(
        status_badge("warning", "No data loaded", icon="⚠️"),
        unsafe_allow_html=True
    )
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""
    <div class="body-text">
    Upload forecast and network configuration files to get started.
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("📤 Upload Data", type="primary", use_container_width=True):
        st.switch_page("pages/1_Data.py")

    st.divider()

    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 12px;">🚀 Getting Started</div>
        <ol style="margin: 0; padding-left: 20px;">
            <li><strong>Upload Data</strong> - Provide forecast and network configuration Excel files</li>
            <li><strong>Run Planning Workflow</strong> - Generate production schedule, assign to trucks, calculate costs</li>
            <li><strong>Analyze Results</strong> - Review production, distribution, and cost details</li>
            <li><strong>Optimize</strong> (Phase 3) - Find optimal plans that minimize total cost to serve</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Quick Navigation section
st.markdown(section_header("Quick Navigation", level=2, icon="🧭"), unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="card card-hover">
        <div style="font-size: 32px; margin-bottom: 8px;">📁</div>
        <div style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">Data Management</div>
        <div class="caption-text">Upload files, view data summaries, and edit forecasts</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Go to Data Management", use_container_width=True, key="nav_data"):
        st.switch_page("pages/1_Data.py")

with col2:
    st.markdown("""
    <div class="card card-hover">
        <div style="font-size: 32px; margin-bottom: 8px;">📋</div>
        <div style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">Planning</div>
        <div class="caption-text">Run heuristic planning, optimization, or manage scenarios</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Go to Planning", use_container_width=True, key="nav_planning"):
        st.switch_page("pages/2_Planning.py")

with col3:
    st.markdown("""
    <div class="card card-hover">
        <div style="font-size: 32px; margin-bottom: 8px;">📈</div>
        <div style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">Results</div>
        <div class="caption-text">View production, distribution, costs, and comparisons</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Go to Results", use_container_width=True, key="nav_results"):
        st.switch_page("pages/3_Results.py")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="card card-hover">
        <div style="font-size: 32px; margin-bottom: 8px;">🗺️</div>
        <div style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">Network Analysis</div>
        <div class="caption-text">Visualize network graph and analyze routes</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Go to Network Analysis", use_container_width=True, key="nav_network"):
        st.switch_page("pages/4_Network.py")

with col2:
    st.markdown("""
    <div class="card card-hover">
        <div style="font-size: 32px; margin-bottom: 8px;">⚙️</div>
        <div style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">Settings</div>
        <div class="caption-text">Configure application preferences</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Go to Settings", use_container_width=True, key="nav_settings"):
        st.switch_page("pages/5_Settings.py")

with col3:
    # Empty placeholder for symmetry
    pass

st.divider()

# Business rules reference
st.markdown(section_header("Key Business Rules", level=2, icon="📝"), unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(section_header("Shelf Life", level=3), unsafe_allow_html=True)
    st.markdown(colored_metric("Ambient", "17 days", "primary"), unsafe_allow_html=True)
    st.markdown(colored_metric("Frozen", "120 days", "secondary"), unsafe_allow_html=True)
    st.markdown(colored_metric("Thawed", "14 days", "accent"), unsafe_allow_html=True)

with col2:
    st.markdown(section_header("Quality Standards", level=3), unsafe_allow_html=True)
    st.markdown(colored_metric("Min. Acceptable", "7 days", "warning"), unsafe_allow_html=True)
    st.markdown('<p class="caption-text">Breadrooms discard stock with <7 days remaining</p>', unsafe_allow_html=True)
    st.markdown(colored_metric("Manufacturing Site", "6122", "primary"), unsafe_allow_html=True)
    st.markdown('<p class="caption-text">Source location for all products</p>', unsafe_allow_html=True)

with col3:
    st.markdown(section_header("Production Capacity", level=3), unsafe_allow_html=True)
    st.markdown(colored_metric("Production Rate", "1,400 units/hour", "success"), unsafe_allow_html=True)
    st.markdown(colored_metric("Regular Hours", "12h/day (Mon-Fri)", "success"), unsafe_allow_html=True)
    st.markdown(colored_metric("Max w/ Overtime", "14h/day", "success"), unsafe_allow_html=True)
    st.markdown('<p class="caption-text">Weekend: 4h minimum payment</p>', unsafe_allow_html=True)

st.divider()

# Network overview
st.markdown(section_header("Network Overview", level=2, icon="🌐"), unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown(section_header("Distribution Network", level=3), unsafe_allow_html=True)
    st.markdown("""
    <div class="card">
        <div class="body-text">
            <strong>Structure:</strong> 2-echelon hub-and-spoke + frozen buffer
        </div>
        <ul style="margin-top: 12px; line-height: 1.8;">
            <li><strong>Manufacturing:</strong> Location 6122 (source)</li>
            <li><strong>Regional Hubs:</strong> 6104 (NSW/ACT), 6125 (VIC/TAS/SA)</li>
            <li><strong>Frozen Buffer:</strong> Lineage (WA route)</li>
            <li><strong>Destinations:</strong> 9 breadrooms across Australia</li>
            <li><strong>Routes:</strong> 10 route legs</li>
        </ul>
        <div class="warning-box" style="margin-top: 12px;">
            <strong>Special:</strong> WA (6130) receives frozen, thaws on-site (shelf life resets to 14 days)
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(section_header("Truck Schedule", level=3), unsafe_allow_html=True)
    st.markdown("""
    <div class="card">
        <div class="body-text" style="font-weight: 600; margin-bottom: 8px;">
            Morning Truck (Daily Mon-Fri):
        </div>
        <ul style="line-height: 1.8;">
            <li>Mon, Tue, Thu, Fri: 6122 → 6125</li>
            <li>Wednesday: 6122 → Lineage → 6125</li>
            <li>Loads D-1 production only</li>
        </ul>
        <div class="body-text" style="font-weight: 600; margin-top: 16px; margin-bottom: 8px;">
            Afternoon Truck (Day-Specific):
        </div>
        <ul style="line-height: 1.8;">
            <li>Monday: 6122 → 6104</li>
            <li>Tuesday: 6122 → 6110</li>
            <li>Wednesday: 6122 → 6104</li>
            <li>Thursday: 6122 → 6110</li>
            <li>Friday: 6122 → 6110 AND 6122 → 6104 (2 trucks)</li>
            <li>Loads D-1 or D0 production</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# Footer
st.caption("Built with Streamlit • Powered by Pyomo • Phase 3 Complete ✅ • Optimization Ready ⚡")
