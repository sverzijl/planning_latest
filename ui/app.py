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

# Workflow Selection (Phase A)
st.markdown(section_header("Production Planning Workflows", level=2, icon="🎯"), unsafe_allow_html=True)

st.markdown(
    """
    <div class="body-text" style="margin-bottom: 16px;">
    Choose the appropriate workflow for your planning needs. Each workflow is optimized for
    different operational cadences and planning horizons.
    </div>
    """,
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="card card-hover" style="min-height: 280px;">
        <div style="font-size: 32px; margin-bottom: 8px;">🚀</div>
        <div style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">Initial Solve</div>
        <div class="caption-text" style="margin-bottom: 12px;">
            First-time planning or major replanning. Creates baseline 12-week production plan
            with cold start optimization.
        </div>
        <div style="font-size: 12px; color: #6c757d; margin-top: 8px;">
            <strong>Use when:</strong><br>
            • Starting fresh<br>
            • Network changes<br>
            • Major forecast revisions
        </div>
        <div style="margin-top: 12px;">
            <span style="background-color: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px;">
                ✅ AVAILABLE
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("▶️ Run Initial Solve", use_container_width=True, type="primary"):
        st.switch_page("pages/2_Initial_Solve.py")

with col2:
    st.markdown("""
    <div class="card card-hover" style="min-height: 280px;">
        <div style="font-size: 32px; margin-bottom: 8px;">🔄</div>
        <div style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">Weekly Solve</div>
        <div class="caption-text" style="margin-bottom: 12px;">
            Weekly replanning with updated forecast. Uses warmstart from previous solve
            for faster optimization. Rolling 12-week horizon.
        </div>
        <div style="font-size: 12px; color: #6c757d; margin-top: 8px;">
            <strong>Use when:</strong><br>
            • Weekly forecast updates<br>
            • Rolling forward 1 week<br>
            • Routine replanning
        </div>
        <div style="margin-top: 12px;">
            <span style="background-color: #ffc107; color: #000; padding: 4px 8px; border-radius: 4px; font-size: 11px;">
                🚧 PHASE B
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("▶️ Run Weekly Solve", use_container_width=True):
        st.switch_page("pages/3_Weekly_Solve.py")

with col3:
    st.markdown("""
    <div class="card card-hover" style="min-height: 280px;">
        <div style="font-size: 32px; margin-bottom: 8px;">📅</div>
        <div style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">Daily Solve</div>
        <div class="caption-text" style="margin-bottom: 12px;">
            Operational replanning with actuals. Locks yesterday/today, optimizes next
            4 weeks, fixes remaining 8 weeks for stability.
        </div>
        <div style="font-size: 12px; color: #6c757d; margin-top: 8px;">
            <strong>Use when:</strong><br>
            • Daily operations<br>
            • Actuals vs plan tracking<br>
            • Short-term adjustments
        </div>
        <div style="margin-top: 12px;">
            <span style="background-color: #ffc107; color: #000; padding: 4px 8px; border-radius: 4px; font-size: 11px;">
                🚧 PHASE B
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("▶️ Run Daily Solve", use_container_width=True):
        st.switch_page("pages/4_Daily_Solve.py")

# Show last solve status if available
if session_state.has_latest_solve():
    st.divider()
    result = session_state.get_latest_solve_result()
    if result:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Last Solve Type", result.workflow_type.value.title())
        with col2:
            st.metric("Objective Value", f"${result.objective_value:,.2f}" if result.objective_value else "N/A")
        with col3:
            st.metric("Solve Time", f"{result.solve_time_seconds:.1f}s" if result.solve_time_seconds else "N/A")
        with col4:
            status = "✅ Success" if result.success else "❌ Failed"
            st.metric("Status", status)

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
st.caption("Built with Streamlit • Powered by Pyomo • Phase A Workflow System ✅ • Production Ready 🚀")
