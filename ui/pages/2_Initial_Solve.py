"""Initial Solve workflow page.

This page implements the Initial workflow for establishing the first 12-week
production plan. It's used for:
- First-time planning when starting the system
- Major replanning events (network changes, large forecast revisions)
- Establishing baseline for subsequent Weekly/Daily solves

Workflow Steps:
1. Upload/Verify Data
2. Configure Solve
3. Run Optimization
4. Review Results
5. Export Plans
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from datetime import datetime

from ui import session_state
from ui.components.styling import apply_custom_css, section_header, colored_metric
from ui.components.workflow_checklist import (
    render_workflow_checklist,
    get_initial_workflow_checklist,
)

from src.workflows import InitialWorkflow, WorkflowConfig, WorkflowType
from src.persistence import SolveRepository
from src.models.truck_schedule import TruckScheduleCollection

# Page config
st.set_page_config(
    page_title="Initial Solve - GF Bread Optimizer",
    page_icon="🚀",
    layout="wide"
)

apply_custom_css()
session_state.initialize_session_state()

# Get current workflow step
current_step = session_state.get_workflow_step("initial")

# Render checklist in sidebar
checklist_items = get_initial_workflow_checklist(current_step)
render_workflow_checklist("Initial Solve Progress", checklist_items)

# Main content
st.markdown(section_header("Initial Solve - 12 Week Planning", level=1, icon="🚀"), unsafe_allow_html=True)

st.markdown(
    """
    <div class="body-text" style="margin-bottom: 24px;">
    Create your first optimized production plan covering 12 weeks. This cold-start
    solve establishes the baseline for future Weekly and Daily replanning.
    </div>
    """,
    unsafe_allow_html=True
)

# Create tabs for workflow sections
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📁 Data",
    "⚙️ Configure",
    "▶️ Solve",
    "📊 Results",
    "📥 Export"
])

# ========== TAB 1: DATA ==========
with tab1:
    st.markdown(section_header("Step 1: Verify Data", level=2, icon="📁"), unsafe_allow_html=True)

    if session_state.is_data_uploaded():
        st.success("✅ Data uploaded and ready")

        stats = session_state.get_summary_stats()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(colored_metric("Locations", str(stats.get('locations', 0)), "primary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Routes", str(stats.get('routes', 0)), "primary"), unsafe_allow_html=True)
        with col2:
            st.markdown(colored_metric("Products", str(stats.get('products_in_forecast', 0)), "secondary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Forecast Entries", f"{stats.get('forecast_entries', 0):,}", "secondary"), unsafe_allow_html=True)
        with col3:
            st.markdown(colored_metric("Total Demand", f"{stats.get('total_demand', 0):,.0f}", "accent"), unsafe_allow_html=True)
            st.markdown(colored_metric("Planning Days", str(stats.get('date_range_days', 0)), "accent"), unsafe_allow_html=True)
        with col4:
            st.markdown(colored_metric("Labor Days", str(stats.get('labor_days', 0)), "success"), unsafe_allow_html=True)
            st.markdown(colored_metric("Truck Schedules", str(stats.get('truck_schedules', 0)), "success"), unsafe_allow_html=True)

        st.divider()

        # Data files info
        st.subheader("Loaded Files")
        if st.session_state.get('forecast_filename'):
            st.markdown(f"**Forecast:** {st.session_state.forecast_filename}")
        if st.session_state.get('network_filename'):
            st.markdown(f"**Network:** {st.session_state.network_filename}")
        if st.session_state.get('inventory_filename'):
            st.markdown(f"**Inventory:** {st.session_state.inventory_filename}")
            if st.session_state.get('inventory_snapshot_date'):
                st.caption(f"Snapshot Date: {st.session_state.inventory_snapshot_date}")

        if st.button("✅ Data Verified - Proceed to Configure", type="primary"):
            session_state.set_workflow_step("initial", 1)
            st.rerun()

    else:
        st.warning("⚠️ No data uploaded. Please upload forecast and network configuration files first.")
        if st.button("Go to Data Upload Page"):
            st.switch_page("pages/1_Data.py")

# ========== TAB 2: CONFIGURE ==========
with tab2:
    st.markdown(section_header("Step 2: Configure Solve", level=2, icon="⚙️"), unsafe_allow_html=True)

    if not session_state.is_data_uploaded():
        st.error("❌ Please upload data first (Step 1)")
    else:
        st.markdown("**Configure optimization parameters for the initial 12-week planning solve.**")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Planning Horizon")
            horizon_weeks = st.number_input(
                "Planning Horizon (weeks)",
                min_value=1,
                max_value=52,
                value=12,
                help="Number of weeks to plan ahead. Default: 12 weeks"
            )

            st.subheader("Solver Settings")
            solver_name = st.selectbox(
                "Solver",
                options=["appsi_highs", "cbc", "glpk"],
                index=0,
                help="Optimization solver. APPSI HiGHS recommended for binary variables."
            )

            time_limit = st.number_input(
                "Time Limit (seconds)",
                min_value=60,
                max_value=7200,
                value=1800,
                step=60,
                help="Maximum solve time. 0 = no limit. Recommended: 30 minutes (1800s) for 12 weeks."
            )

            mip_gap = st.number_input(
                "MIP Gap Tolerance",
                min_value=0.0001,
                max_value=0.1,
                value=0.01,
                step=0.001,
                format="%.4f",
                help="Solution quality tolerance. 0.01 = 1% gap (good balance). Lower = better solution but longer solve time."
            )

        with col2:
            st.subheader("Model Options")

            allow_shortages = st.checkbox(
                "Allow Demand Shortages",
                value=False,
                help="If enabled, optimizer can leave demand unmet (with high penalty cost). Useful for testing infeasible scenarios."
            )

            track_batches = st.checkbox(
                "Track Production Batches",
                value=True,
                help="Track individual production batches for shelf life management. Recommended: enabled."
            )

            use_pallet_costs = st.checkbox(
                "Use Pallet-Based Storage Costs",
                value=True,
                help="Use integer pallet variables for accurate storage costs (partial pallets occupy full pallet space). Slower but more accurate."
            )

            st.info(
                "💡 **Tip:** For faster initial testing, try 4-week horizon with 5-minute time limit. "
                "For production use, stick with 12 weeks and 30 minutes."
            )

        st.divider()

        # Save config to session state
        config_dict = {
            "workflow_type": "initial",
            "planning_horizon_weeks": horizon_weeks,
            "solve_time_limit": time_limit if time_limit > 0 else None,
            "mip_gap_tolerance": mip_gap,
            "solver_name": solver_name,
            "allow_shortages": allow_shortages,
            "track_batches": track_batches,
            "use_pallet_costs": use_pallet_costs,
        }

        st.session_state.workflow_config = config_dict

        if st.button("✅ Configuration Complete - Ready to Solve", type="primary"):
            session_state.set_workflow_step("initial", 2)
            st.rerun()

# ========== TAB 3: SOLVE ==========
with tab3:
    st.markdown(section_header("Step 3: Run Optimization", level=2, icon="▶️"), unsafe_allow_html=True)

    if not session_state.is_data_uploaded():
        st.error("❌ Please upload data first (Tab 1)")
    elif not st.session_state.get('workflow_config'):
        st.error("❌ Please configure solve parameters first (Tab 2)")
    else:
        # Show config summary
        config = st.session_state.workflow_config

        st.subheader("Solve Configuration Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Planning Horizon", f"{config['planning_horizon_weeks']} weeks")
            st.metric("Solver", config['solver_name'].upper())
        with col2:
            time_limit_str = f"{config['solve_time_limit']}s" if config['solve_time_limit'] else "No limit"
            st.metric("Time Limit", time_limit_str)
            st.metric("MIP Gap", f"{config['mip_gap_tolerance']*100:.2f}%")
        with col3:
            st.metric("Allow Shortages", "Yes" if config['allow_shortages'] else "No")
            st.metric("Track Batches", "Yes" if config['track_batches'] else "No")

        st.divider()

        # Run solve button
        if st.button("🚀 Run Initial Solve", type="primary", use_container_width=True):
            with st.spinner("Building optimization model..."):
                try:
                    # Create workflow config
                    workflow_config = WorkflowConfig(
                        workflow_type=WorkflowType.INITIAL,
                        planning_horizon_weeks=config['planning_horizon_weeks'],
                        solve_time_limit=config['solve_time_limit'],
                        mip_gap_tolerance=config['mip_gap_tolerance'],
                        solver_name=config['solver_name'],
                        allow_shortages=config['allow_shortages'],
                        track_batches=config['track_batches'],
                        use_pallet_costs=config['use_pallet_costs'],
                    )

                    # Get truck schedules (handle both list and TruckScheduleCollection)
                    truck_schedules = st.session_state.truck_schedules
                    if isinstance(truck_schedules, list):
                        truck_schedules = TruckScheduleCollection(schedules=truck_schedules)

                    # Get products list
                    products = st.session_state.get('products', [])

                    # Create workflow
                    workflow = InitialWorkflow(
                        config=workflow_config,
                        locations=st.session_state.locations,
                        routes=st.session_state.routes,
                        products=products,
                        forecast=st.session_state.forecast,  # Pass Forecast object
                        labor_calendar=st.session_state.labor_calendar,
                        truck_schedules=truck_schedules,
                        cost_structure=st.session_state.cost_structure,
                        initial_inventory=st.session_state.initial_inventory,
                    )

                    # Execute workflow
                    st.info("⏳ Executing workflow... This may take several minutes.")

                    # Create progress placeholder
                    progress_container = st.empty()

                    with progress_container.container():
                        st.write("**Workflow Progress:**")
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        # Simulate progress updates (in reality, workflow runs in background)
                        import time

                        status_text.text("Preparing input data...")
                        progress_bar.progress(10)
                        time.sleep(0.5)

                        status_text.text("Building optimization model...")
                        progress_bar.progress(20)
                        time.sleep(0.5)

                        status_text.text("Solving optimization problem...")
                        progress_bar.progress(30)

                        # Execute workflow
                        result = workflow.execute()

                        progress_bar.progress(90)
                        status_text.text("Saving results...")
                        time.sleep(0.3)

                        progress_bar.progress(100)
                        status_text.text("Complete!")

                    # Save result to repository
                    repo = SolveRepository()
                    file_path = repo.save(result)

                    # Store in session state
                    session_state.store_workflow_result(result, str(file_path))

                    # Clear progress, show result
                    progress_container.empty()

                    if result.success:
                        st.success(f"✅ Solve completed successfully!")
                        st.markdown(f"**Saved to:** `{file_path}`")

                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Objective Value", f"${result.objective_value:,.2f}")
                        with col2:
                            st.metric("Solve Time", f"{result.solve_time_seconds:.1f}s")
                        with col3:
                            gap_pct = result.mip_gap * 100 if result.mip_gap else 0
                            st.metric("MIP Gap", f"{gap_pct:.2f}%")
                        with col4:
                            st.metric("Solver Status", result.solver_status or "N/A")

                        session_state.set_workflow_step("initial", 3)

                        st.info("👉 Proceed to **Results** tab to review the optimized plan.")

                    else:
                        st.error(f"❌ Solve failed: {result.error_message}")
                        st.warning("Check your data and configuration, then try again.")

                except Exception as e:
                    st.error(f"❌ Error during solve: {str(e)}")
                    import traceback
                    with st.expander("Show Error Details"):
                        st.code(traceback.format_exc())

# ========== TAB 4: RESULTS ==========
with tab4:
    st.markdown(section_header("Step 4: Review Results", level=2, icon="📊"), unsafe_allow_html=True)

    result = session_state.get_latest_solve_result()

    if result is None:
        st.info("ℹ️ No solve results available yet. Run optimization in the **Solve** tab.")

    elif not result.success:
        st.error(f"❌ Last solve failed: {result.error_message}")

    else:
        st.success("✅ Optimization completed successfully")

        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(
                colored_metric("Total Cost", f"${result.objective_value:,.2f}", "primary"),
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                colored_metric("Solve Time", f"{result.solve_time_seconds:.1f}s", "secondary"),
                unsafe_allow_html=True
            )
        with col3:
            gap_pct = result.mip_gap * 100 if result.mip_gap else 0
            st.markdown(
                colored_metric("MIP Gap", f"{gap_pct:.2f}%", "accent"),
                unsafe_allow_html=True
            )
        with col4:
            st.markdown(
                colored_metric("Solver Status", result.solver_status or "N/A", "success"),
                unsafe_allow_html=True
            )

        st.divider()

        # Metadata
        with st.expander("📋 Solve Metadata"):
            st.json(result.metadata)

        # Solution preview (if available)
        if result.solution:
            st.subheader("Solution Preview")
            st.info("🚧 Detailed solution visualization coming in Phase B/C")

            # Show model statistics
            st.write(f"**Decision variables:** {result.solution.num_variables}")
            st.write(f"**Constraints:** {result.solution.num_constraints}")
            st.write(f"**Integer/binary variables:** {result.solution.num_integer_vars}")

        st.divider()

        if st.button("✅ Results Reviewed - Proceed to Export", type="primary"):
            session_state.set_workflow_step("initial", 4)
            st.rerun()

# ========== TAB 5: EXPORT ==========
with tab5:
    st.markdown(section_header("Step 5: Export Plans", level=2, icon="📥"), unsafe_allow_html=True)

    result = session_state.get_latest_solve_result()

    if result is None or not result.success:
        st.info("ℹ️ No successful solve results available for export.")

    else:
        st.markdown("**Export production plans and reports in various formats.**")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.subheader("Excel Export")
            st.markdown(
                """
                - Production schedule
                - Labor allocation
                - Truck loading plan
                - Cost breakdown
                """
            )
            if st.button("📊 Export to Excel", use_container_width=True):
                st.info("🚧 Excel export coming in Phase C")

        with col2:
            st.subheader("PDF Report")
            st.markdown(
                """
                - Production summary
                - Shop floor instructions
                - Daily production plan
                - Print-ready format
                """
            )
            if st.button("📄 Generate PDF", use_container_width=True):
                st.info("🚧 PDF export coming in Phase C")

        with col3:
            st.subheader("Interactive Dashboard")
            st.markdown(
                """
                - Drill-down analysis
                - Date/SKU filters
                - Editable plans
                - Deviation tracking
                """
            )
            if st.button("📈 Open Dashboard", use_container_width=True):
                st.info("🚧 Interactive dashboard coming in Phase C")

        st.divider()

        # Save location info
        if st.session_state.get('latest_solve_path'):
            st.subheader("Solve File Location")
            st.code(st.session_state.latest_solve_path)
            st.caption("This file will be used as warmstart for future Weekly solves.")

        st.divider()

        # Workflow complete
        st.success("🎉 Initial Solve workflow complete!")
        st.markdown(
            """
            **Next Steps:**
            - Run Weekly solves for routine replanning (coming in Phase B)
            - Run Daily solves for operational adjustments (coming in Phase B)
            - View detailed results in the Results page
            """
        )

        if st.button("🏠 Return to Home"):
            st.switch_page("app.py")
