"""Weekly Solve workflow page (Phase B).

This page will implement the Weekly workflow for rolling 12-week replanning
with warmstart from previous solves.

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
    page_title="Weekly Solve - GF Bread Optimizer",
    page_icon="🔄",
    layout="wide"
)

apply_custom_css()
session_state.initialize_session_state()

# Main content
st.markdown(section_header("Weekly Solve - Rolling Horizon Replanning", level=1, icon="🔄"), unsafe_allow_html=True)

st.info(
    """
    🚧 **Coming in Phase B**

    The Weekly Solve workflow will provide:
    - **Rolling 12-week horizon** planning with updated forecast
    - **Warmstart from previous solve** for faster optimization
    - **Preview dashboard** showing forecast changes, cost comparison, and constraint violations
    - **Approval workflow** for warmstart usage
    - **Auto-calculated inventory** from previous solve + actuals

    **Timeline:** Phase B implementation (2-3 weeks)
    """
)

st.divider()

st.subheader("Planned Features")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        ### Warmstart Preview
        - Demand delta heatmap (forecast changes)
        - Cost comparison (old vs new)
        - Constraint violation detection
        - Solve age indicator

        ### Workflow Steps
        1. Upload updated forecast
        2. Review current inventory
        3. Preview and approve warmstart
        4. Configure solve
        5. Run optimization
        6. Review results
        7. Export plans
        """
    )

with col2:
    st.markdown(
        """
        ### Smart Features
        - **Alert system** detects large forecast changes
        - **Auto-recommendation** to run Weekly vs Daily
        - **Time-shifting** of previous solution (weeks 2-12 → 1-11)
        - **Validation** ensures warmstart compatibility

        ### Performance
        - Faster solves with warmstart (typically 30-50% reduction)
        - Maintains solution quality
        - Handles forecast changes gracefully
        """
    )

st.divider()

st.subheader("Current Workaround")

st.markdown(
    """
    Until Weekly Solve is implemented in Phase B, you can:

    1. **Use Initial Solve** with updated forecast
       - Go to Initial Solve page
       - Upload new forecast file
       - Run cold start optimization
       - Results will be saved for future warmstart

    2. **Check solve history** to compare with previous weeks
       - Results page will show historical solves (Phase C)
    """
)

if st.button("Go to Initial Solve"):
    st.switch_page("pages/2_Initial_Solve.py")

if st.button("Return to Home"):
    st.switch_page("app.py")
