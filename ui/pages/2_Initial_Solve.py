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
        if st.button("🚀 Run Initial Solve", type="primary", width="stretch"):
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

                    # Also store for Results page compatibility
                    if result.model and result.success:
                        session_state.store_optimization_results(result.model, result.solution)

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

        # Extract and display production data if model available
        if result.model and hasattr(result.model, 'get_solution'):
            solution_dict = result.model.get_solution()

            if solution_dict:
                st.subheader("Production Summary")

                # Production by product
                production_by_product = solution_dict.get('production_by_product', {})
                if production_by_product:
                    st.write("**Total Production by SKU:**")
                    import pandas as pd
                    prod_df = pd.DataFrame([
                        {"Product": prod, "Quantity": qty}
                        for prod, qty in production_by_product.items()
                    ]).sort_values("Quantity", ascending=False)
                    st.dataframe(prod_df, hide_index=True, use_container_width=True)

                st.divider()

                # Production by date
                production_by_date = solution_dict.get('production_by_date', {})
                if production_by_date:
                    st.subheader("Daily Production")
                    import pandas as pd
                    import plotly.express as px

                    daily_df = pd.DataFrame([
                        {"Date": date_val, "Quantity": qty}
                        for date_val, qty in sorted(production_by_date.items())
                    ])

                    if not daily_df.empty:
                        fig = px.bar(
                            daily_df,
                            x="Date",
                            y="Quantity",
                            title="Production by Date",
                            labels={"Quantity": "Units Produced", "Date": "Production Date"}
                        )
                        fig.update_layout(showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)

                st.divider()

                # Cost breakdown
                cost_breakdown = solution_dict.get('cost_breakdown', {})
                # Also check metadata directly (cost_breakdown might not exist)
                if not cost_breakdown and solution_dict:
                    cost_breakdown = solution_dict

                if cost_breakdown:
                    st.subheader("Cost Breakdown (Incremental Costs)")

                    # Primary operational costs (Row 1)
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        labor_cost = cost_breakdown.get('total_labor_cost', 0)
                        st.metric("Labor Cost", f"${labor_cost:,.2f}")
                    with col2:
                        shortage_cost = cost_breakdown.get('total_shortage_cost', 0)
                        st.metric("Shortage Penalty", f"${shortage_cost:,.2f}")
                    with col3:
                        waste_cost = cost_breakdown.get('total_waste_cost', 0)
                        st.metric("Waste Cost", f"${waste_cost:,.2f}")
                    with col4:
                        staleness_cost = cost_breakdown.get('total_staleness_cost', 0)
                        st.metric("Freshness Penalty", f"${staleness_cost:,.2f}")

                    # Secondary costs (Row 2)
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        transport_cost = cost_breakdown.get('total_transport_cost', 0)
                        st.metric("Transport Cost", f"${transport_cost:,.2f}")
                    with col2:
                        storage_cost = cost_breakdown.get('total_holding_cost', 0)
                        st.metric("Storage Cost", f"${storage_cost:,.2f}")
                    with col3:
                        changeover_cost = cost_breakdown.get('total_changeover_cost', 0)
                        st.metric("Changeover Cost", f"${changeover_cost:,.2f}")
                    with col4:
                        total_cost = cost_breakdown.get('total_cost', 0)
                        st.metric("Total Incremental", f"${total_cost:,.2f}")

                    # Show production cost and waste details
                    prod_cost_ref = cost_breakdown.get('total_production_cost_reference', 0)
                    changeover_waste_units = cost_breakdown.get('total_changeover_waste_units', 0)
                    end_inv_units = cost_breakdown.get('end_horizon_inventory_units', 0)

                    if prod_cost_ref > 0 or changeover_waste_units > 0 or end_inv_units > 0:
                        with st.expander("💡 Cost Details"):
                            if prod_cost_ref > 0:
                                st.write(f"**Production cost (reference only):** ${prod_cost_ref:,.2f}")
                                st.caption("Not in objective - pass-through cost, doesn't vary with decisions")

                            if changeover_waste_units > 0:
                                st.write(f"**Changeover waste:** {changeover_waste_units:,.0f} units (${cost_breakdown.get('total_changeover_waste_cost', 0):,.2f})")
                                st.caption("Material lost during SKU transitions - creates batch size economics")

                            if end_inv_units > 0:
                                st.write(f"**End-of-horizon inventory:** {end_inv_units:,.0f} units")
                                st.caption("Unsold inventory at end of planning period - treated as waste")

                st.divider()

                # Link to detailed results
                st.info("📊 For detailed analysis, drill-down views, and exports, visit the **Results** page.")
                if st.button("📈 Go to Detailed Results", type="secondary"):
                    st.switch_page("pages/5_Results.py")

        else:
            # Model not available - show basic info only
            st.subheader("Model Statistics")
            if result.solution:
                st.write(f"**Decision variables:** {result.solution.num_variables:,}")
                st.write(f"**Constraints:** {result.solution.num_constraints:,}")
                st.write(f"**Integer/binary variables:** {result.solution.num_integer_vars:,}")

            st.info(
                "💡 **Tip:** Detailed production schedule and cost analysis available on the **Results** page. "
                "The model data is stored in session state while the app is running."
            )

        st.divider()

        # Metadata
        with st.expander("📋 Solve Metadata"):
            st.json(result.metadata)

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
            if st.button("📊 Export to Excel", width="stretch"):
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
            if st.button("📄 Generate PDF", width="stretch"):
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
            if st.button("📈 Open Dashboard", width="stretch"):
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
