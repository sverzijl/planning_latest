"""Daily Solve workflow page (Phase B).

This page will implement the Daily workflow for operational replanning with
actuals locking and fixed periods.

Status: Stub implementation for Phase A. Full implementation in Phase B.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from ui import session_state
from ui.components.styling import apply_custom_css, section_header

# Page config
st.set_page_config(
    page_title="Daily Solve - GF Bread Optimizer",
    page_icon="📅",
    layout="wide"
)

apply_custom_css()
session_state.initialize_session_state()

# Main content
st.markdown(section_header("Daily Solve - Operational Replanning", level=1, icon="📅"), unsafe_allow_html=True)

st.info(
    """
    🚧 **Coming in Phase B**

    The Daily Solve workflow will provide:
    - **Actuals entry** for yesterday's production and shipments
    - **Review and lock** workflow for today's plan
    - **4-week free + 8-week fixed** optimization
    - **Variance detection** (plan vs actual with deviation alerts)
    - **Forward plan generation** for next 1-7 days
    - **Multi-format export** (Excel, PDF, interactive dashboard)

    **Timeline:** Phase B implementation (2-3 weeks)
    """
)

st.divider()

st.subheader("Planned Features")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        ### Actuals Management
        - Auto-populate from previous day's plan
        - Manual override for deviations
        - Variance detection (>10% flagged)
        - Plan vs actual comparison table

        ### Review and Lock
        - Separate tab for today's plan review
        - Approve before solve runs
        - Prevents accidental replanning of today

        ### Workflow Steps
        1. Enter yesterday's actuals
        2. Review and lock today's plan
        3. Verify inventory and in-transit stock
        4. Configure free/fixed periods
        5. Run optimization (4 weeks free)
        6. Review variance report
        7. Generate forward plans (1-7 days)
        8. Export to Excel/PDF
        """
    )

with col2:
    st.markdown(
        """
        ### Fixed Periods
        - **Weeks 1-4:** Free to re-optimize
        - **Weeks 5-12:** Hard-fixed from previous solve
        - **Validation:** Error if actuals create infeasibility
        - **Stability:** Long-term plan remains stable

        ### Forward Planning
        - Generate production plans 1-7 days ahead
        - Critical for Friday → Monday planning
        - Manual editing with deviation tracking
        - Dough plan and packing plan export

        ### In-Transit Tracking
        - Auto-populate trucks from previous solve
        - Manual truck additions supported
        - Expected arrival auto-marking
        - Override capabilities for delays
        """
    )

st.divider()

st.subheader("Current Workaround")

st.markdown(
    """
    Until Daily Solve is implemented in Phase B, you can:

    1. **Use Initial Solve** for weekly replanning
       - Adjust planning horizon to 4 weeks for faster solves
       - Manually track actuals in spreadsheet
       - Compare results to identify variances

    2. **Export results** for production planning
       - Use Results page to view production schedule
       - Manually create shop floor instructions
    """
)

if st.button("Go to Initial Solve"):
    st.switch_page("pages/2_Initial_Solve.py")

if st.button("Return to Home"):
    st.switch_page("app.py")
