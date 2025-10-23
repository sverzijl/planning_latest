"""Planning - Run mathematical optimization or manage scenarios.

Consolidates:
- 10_Optimization.py (Mathematical Optimization)
- 13_Scenario_Management.py (Scenarios)
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from datetime import date, timedelta
import math
from ui import session_state
from ui.components.styling import apply_custom_css, section_header, colored_metric, success_badge, warning_badge, info_badge
from ui.components.navigation import render_page_header, check_data_required

# Page config
st.set_page_config(
    page_title="Planning - GF Bread Production",
    page_icon="📋",
    layout="wide",
)

# Apply design system
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

# Initialize scenario manager
if 'scenario_manager' not in st.session_state:
    from src.scenario import ScenarioManager
    st.session_state.scenario_manager = ScenarioManager()

# Page header
render_page_header(
    title="Planning",
    icon="📋",
    subtitle="Run mathematical optimization or manage scenarios"
)

# Check if data is loaded
if not check_data_required():
    st.stop()

st.divider()

# Create tabs for planning options
tab_optimization, tab_scenarios = st.tabs(["⚡ Optimization", "📊 Scenarios"])


# ===========================
# TAB 1: OPTIMIZATION
# ===========================

with tab_optimization:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">⚡ Mathematical Optimization</div>
        <div>Find the <strong>minimum cost</strong> production and distribution plan using mathematical optimization.</div>
        <div style="margin-top: 8px; font-size: 13px; color: #757575;">
            Uses Pyomo with solvers like HiGHS, CBC, GLPK, Gurobi, or CPLEX to find provably optimal solutions.
        </div>
        <div style="margin-top: 8px; font-size: 13px; color: #2e7d32; font-weight: 500;">
            ✓ Solves 4-week horizon in ~96s with HiGHS (2.4× faster than CBC)
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Solver Configuration
    st.markdown(section_header("Solver Configuration", level=3, icon="🔧"), unsafe_allow_html=True)

    from src.optimization.solver_config import SolverConfig

    # Use APPSI HiGHS only (optimal choice for binary MIP with warmstart support)
    selected_solver = 'appsi_highs'

    # Verify APPSI HiGHS is available
    solver_config = SolverConfig()
    available_solvers = solver_config.get_available_solvers()

    if 'appsi_highs' not in available_solvers:
        st.error("❌ APPSI HiGHS solver not found!")
        st.markdown("""
        **Installation Required:**

        ```bash
        # Install HiGHS solver
        pip install highspy
        ```

        **Why APPSI HiGHS?**
        - Fastest open-source solver for binary MIP problems
        - 2.4× faster than CBC on typical 4-week problems
        - Supports warmstart (for 6+ week horizons)
        - Persistent solver interface for efficiency

        See `docs/SOLVER_INSTALLATION.md` for details.
        """)
        st.stop()

    # Display solver info
    st.success("✓ Using **APPSI HiGHS** - High-performance MIP solver with warmstart support")
    st.caption("Optimal choice for binary SKU selection and pallet tracking problems")

    st.divider()

    # Optimization Settings
    st.markdown(section_header("Optimization Settings", level=3, icon="⚙️"), unsafe_allow_html=True)

    # Always use Unified Node Model
    st.info("🎯 Using **Unified Node Model** - clean node-based architecture with no virtual locations, generalized truck constraints, and proper weekend enforcement")

    col1, col2, col3 = st.columns(3)

    with col1:
        time_limit = st.slider(
            "Time Limit (seconds)",
            min_value=30,
            max_value=600,
            value=180,
            step=30,
            help="Maximum time solver will run before stopping (default: 180s = 3 minutes)",
            key="opt_time_limit"
        )

        mip_gap = st.slider(
            "MIP Gap Tolerance (%)",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.5,
            help="Accept solutions within this % of optimal (0% = prove optimality, recommended)",
            key="opt_mip_gap"
        )

        # Planning Horizon Start Date Override
        override_start_date = st.checkbox(
            "Override Planning Start Date",
            value=False,
            help="Override the auto-calculated planning start date (normally based on inventory snapshot date and transit times)",
            key="opt_override_start"
        )

        planning_start_date = None
        if override_start_date:
            # Get inventory snapshot date as default if available
            default_start = st.session_state.get('inventory_snapshot_date')
            if default_start is None:
                # Fall back to earliest forecast date
                data = session_state.get_parsed_data()
                if data and data.get('forecast') and data['forecast'].entries:
                    default_start = min(e.forecast_date for e in data['forecast'].entries)
                else:
                    default_start = date.today()

            planning_start_date = st.date_input(
                "Planning Start Date",
                value=default_start,
                help="Set custom planning horizon start date (must be on/before inventory snapshot date)",
                key="opt_planning_start_date"
            )

    with col2:
        allow_shortages = st.checkbox(
            "Allow Demand Shortages",
            value=True,
            help="If checked, model can leave demand unmet with penalty cost (recommended for flexibility)",
            key="opt_allow_shortages"
        )

        enforce_shelf_life = st.checkbox(
            "Enforce Shelf Life Constraints",
            value=True,
            help="Filter routes exceeding 10-day product age limit (recommended)",
            key="opt_enforce_shelf"
        )

        max_routes = st.number_input(
            "Max Routes per Destination",
            min_value=1,
            max_value=10,
            value=5,
            help="Number of alternative routes to consider (recommended: 5)",
            key="opt_max_routes"
        )

    with col3:
        show_solver_output = st.checkbox(
            "Show Solver Output",
            value=False,
            help="Display detailed solver log during optimization",
            key="opt_show_output"
        )

        use_batch_tracking = st.checkbox(
            "Enable Batch Tracking",
            value=True,
            help="Track inventory by production batch with age-cohort variables. Enables FIFO enforcement and shelf life optimization during solving. REQUIRED for Daily Inventory Snapshot to extract exact inventory from model solution. May increase solve time by 2-3×.",
            key="opt_batch_tracking"
        )

    st.divider()

    # Planning Horizon Control
    st.markdown(section_header("Planning Horizon", level=3, icon="📅"), unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])

    with col1:
        planning_horizon_mode = st.radio(
            "Planning horizon mode:",
            options=["Auto (from forecast)", "Custom (weeks)"],
            index=0,
            help="Auto mode calculates horizon from forecast range. Custom mode lets you specify weeks to plan ahead.",
            key="planning_horizon_mode"
        )

    with col2:
        planning_horizon_weeks = None
        custom_end_date = None

        if planning_horizon_mode == "Custom (weeks)":
            planning_horizon_weeks = st.number_input(
                "Planning horizon (weeks):",
                min_value=4,
                max_value=104,
                value=26,  # Default 6 months
                step=1,
                help="Number of weeks to plan ahead. Minimum 4 weeks, maximum 104 weeks (2 years).",
                key="planning_horizon_weeks"
            )

            # Calculate and display the end date
            data = session_state.get_parsed_data()
            if data and data.get('forecast') and data['forecast'].entries:
                forecast_start = min(e.forecast_date for e in data['forecast'].entries)
                custom_end_date = forecast_start + timedelta(days=planning_horizon_weeks * 7)
                st.info(f"📅 Planning horizon: {planning_horizon_weeks} weeks (ending {custom_end_date.strftime('%Y-%m-%d')})")

                # Check if labor calendar covers the planning horizon
                if data.get('labor_calendar') and data['labor_calendar'].days:
                    labor_end = max(day.date for day in data['labor_calendar'].days)
                    if custom_end_date > labor_end:
                        st.warning(
                            f"⚠️ Planning horizon ({custom_end_date.strftime('%Y-%m-%d')}) extends beyond labor calendar coverage ({labor_end.strftime('%Y-%m-%d')}). "
                            f"Extended dates will issue warnings but optimization will proceed."
                        )
                else:
                    st.warning("⚠️ Labor calendar data not available. Cannot validate planning horizon coverage.")

    st.divider()

    # Run Optimization
    st.markdown(section_header("Run Optimization", level=3, icon="🚀"), unsafe_allow_html=True)

    st.markdown("""
    <div style="background-color: #f5f5f5; padding: 12px; border-radius: 4px; margin-bottom: 16px;">
        <div style="font-size: 13px; color: #424242;">
            <strong>Monolithic Optimization:</strong> Solves the entire planning horizon (all weeks) in a single optimization run.
            This ensures global optimality and coherent decisions across the full horizon. HiGHS solver provides excellent
            performance for MIP problems with binary variables (2.4× faster than CBC for 4-week horizon).
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("⚡ Solve Optimization Model", type="primary", use_container_width=True, key="run_optimization"):
        try:
            with st.spinner("Building optimization model..."):
                # Get parsed data
                data = session_state.get_parsed_data()

                # Get initial inventory from session state
                initial_inventory = session_state.get_initial_inventory_dict()

                # Get inventory snapshot date from session state (if initial inventory was loaded)
                inventory_snapshot_date = st.session_state.get('inventory_snapshot_date')

                # Use Unified Node Model
                from src.optimization.unified_node_model import UnifiedNodeModel
                from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

                # Convert data to unified format
                converter = LegacyToUnifiedConverter()
                nodes, unified_routes, unified_trucks = converter.convert_all(
                    manufacturing_site=data['manufacturing_site'],
                    locations=data['locations'],
                    routes=data['routes'],
                    truck_schedules=data['truck_schedules'].schedules if hasattr(data['truck_schedules'], 'schedules') else data['truck_schedules'],
                    forecast=data['forecast']
                )

                # Calculate planning dates
                if planning_start_date:
                    start_date = planning_start_date
                else:
                    # Auto: use earliest forecast date
                    start_date = min(e.forecast_date for e in data['forecast'].entries)

                if custom_end_date:
                    end_date = custom_end_date
                else:
                    # Auto: use latest forecast date
                    end_date = max(e.forecast_date for e in data['forecast'].entries)

                model = UnifiedNodeModel(
                    nodes=nodes,
                    routes=unified_routes,
                    forecast=data['forecast'],
                    labor_calendar=data['labor_calendar'],
                    cost_structure=data['cost_structure'],
                    start_date=start_date,
                    end_date=end_date,
                    truck_schedules=unified_trucks,
                    initial_inventory=initial_inventory,
                    inventory_snapshot_date=inventory_snapshot_date,
                    use_batch_tracking=use_batch_tracking,
                    allow_shortages=allow_shortages,
                    enforce_shelf_life=enforce_shelf_life,
                    products=data.get('products'),
                )

                # Calculate planning horizon info
                horizon_days = len(model.production_dates)
                horizon_weeks = horizon_days / 7.0

                # Show model info with batch tracking status
                batch_status = " | 🔬 Age-cohort batch tracking ENABLED" if use_batch_tracking else ""

                # Get route count (legacy has enumerated_routes, unified has routes)
                if hasattr(model, 'enumerated_routes'):
                    route_count = len(model.enumerated_routes)
                elif hasattr(model, 'routes'):
                    route_count = len(model.routes)
                else:
                    route_count = 0

                st.info(f"📊 Model built: {route_count} routes, {horizon_days} days ({horizon_weeks:.1f} weeks){batch_status}")
                st.caption(f"Planning horizon: {model.start_date} to {model.end_date}")

                if use_batch_tracking:
                    st.info("🔬 Batch tracking enabled: Inventory tracked by production date with FIFO enforcement and shelf life optimization during solving. Daily Inventory Snapshot will extract exact inventory from model solution. Solve time may be 2-3× longer.")
                else:
                    st.warning("⚠️ Batch tracking disabled: Daily Inventory Snapshot will reconstruct inventory from shipments (less accurate for initial inventory scenarios). Enable batch tracking for exact model results.")

            # Single-phase solve with APPSI HiGHS
            with st.spinner(f"Solving with APPSI HiGHS... (max {time_limit}s)"):
                result = model.solve(
                    solver_name=selected_solver,
                    time_limit_seconds=time_limit,
                    mip_gap=mip_gap / 100.0,  # Convert % to fraction
                    use_aggressive_heuristics=True,  # Enable performance features
                    tee=show_solver_output,
                )

            # Extract model object
            result_model = model

            # Display results
            if result.is_optimal() or result.is_feasible():
                status_str = "optimal" if result.is_optimal() else "feasible"
                st.success(f"✅ Optimization {status_str}!")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Status", status_str.title())
                with col2:
                    # Validate objective value is finite before displaying
                    if result.objective_value is None:
                        cost_display = "$0.00"
                    elif math.isinf(result.objective_value):
                        cost_display = "Invalid (∞)"
                        st.warning("⚠️ Objective value is infinite. Check cost parameters.")
                    elif math.isnan(result.objective_value):
                        cost_display = "Invalid (NaN)"
                        st.warning("⚠️ Objective value is NaN. Check cost parameters.")
                    else:
                        cost_display = f"${result.objective_value:,.2f}"
                    st.metric("Total Cost", cost_display)
                with col3:
                    st.metric("Solve Time", f"{result.solve_time_seconds or 0:.1f}s")
                with col4:
                    # Validate gap is finite before displaying
                    if result.gap is None:
                        pass  # Don't show gap metric
                    elif math.isnan(result.gap) or math.isinf(result.gap):
                        st.metric("Gap", "N/A")
                    else:
                        st.metric("Gap", f"{result.gap * 100:.2f}%")

                # Store optimization results
                session_state.store_optimization_results(
                    model=result_model,
                    result=result
                )

                # Display cost breakdown if available
                st.divider()
                st.markdown(section_header("Cost Breakdown", level=4, icon="💰"), unsafe_allow_html=True)

                if hasattr(result, 'solution') and result.solution:
                    sol = result.solution
                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        labor_cost = sol.get('total_labor_cost', 0)
                        st.markdown(colored_metric("Labor", f"${labor_cost:,.0f}", "primary"), unsafe_allow_html=True)

                    with col2:
                        prod_cost = sol.get('total_production_cost', 0)
                        st.markdown(colored_metric("Production", f"${prod_cost:,.0f}", "secondary"), unsafe_allow_html=True)

                    with col3:
                        transport_cost = sol.get('total_transport_cost', 0)
                        st.markdown(colored_metric("Transport", f"${transport_cost:,.0f}", "accent"), unsafe_allow_html=True)

                    with col4:
                        inventory_cost = sol.get('total_inventory_cost', 0)
                        st.markdown(colored_metric("Inventory", f"${inventory_cost:,.0f}", "success"), unsafe_allow_html=True)

                    with col5:
                        shortage_cost = sol.get('total_shortage_cost', 0)
                        shortage_units = sol.get('total_shortage_units', 0)
                        if shortage_units > 0:
                            st.markdown(colored_metric("Shortage", f"${shortage_cost:,.0f}", "warning"), unsafe_allow_html=True)
                            st.caption(f"{shortage_units:,.0f} units unmet")
                        else:
                            st.markdown(success_badge("100% Demand Satisfied"), unsafe_allow_html=True)

                    # Production summary
                    st.divider()
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        total_production = sol.get('total_production_quantity', 0)
                        st.markdown(colored_metric("Total Production", f"{total_production:,.0f} units", "primary"), unsafe_allow_html=True)
                    with col2:
                        num_batches = len(sol.get('production_batches', []))
                        st.markdown(colored_metric("Production Batches", str(num_batches), "secondary"), unsafe_allow_html=True)
                    with col3:
                        total_mixes = sol.get('total_mixes', 0)
                        st.markdown(colored_metric("Total Mixes", str(total_mixes), "accent"), unsafe_allow_html=True)
                    with col4:
                        num_shipments = sum(len(v) for v in sol.get('shipments_by_route_product_date', {}).values())
                        st.markdown(colored_metric("Shipments", str(num_shipments), "success"), unsafe_allow_html=True)
                    with col5:
                        # Changeover statistics (new with start tracking formulation)
                        total_changeovers = sol.get('total_changeovers', 0)
                        if total_changeovers > 0:
                            st.markdown(colored_metric("Product Changeovers", str(total_changeovers), "warning"), unsafe_allow_html=True)
                            changeover_cost = sol.get('total_changeover_cost', 0)
                            if changeover_cost > 0:
                                st.caption(f"Cost: ${changeover_cost:,.0f}")
                        else:
                            st.markdown(colored_metric("Product Changeovers", "0", "success"), unsafe_allow_html=True)

                    # Mix production schedule table (if mix-based production is enabled)
                    if 'mix_counts' in sol and sol['mix_counts']:
                        st.divider()
                        st.subheader("🔢 Mix Production Schedule")

                        import pandas as pd

                        mix_data = []
                        for (node_id, prod_id, date_val), data in sol['mix_counts'].items():
                            mix_data.append({
                                'Date': date_val.strftime('%Y-%m-%d'),
                                'Product': prod_id,
                                'Mixes': data['mix_count'],
                                'Units/Mix': data['units_per_mix'],
                                'Total Units': data['units']
                            })

                        mix_df = pd.DataFrame(mix_data)
                        mix_df = mix_df.sort_values(['Date', 'Product'])

                        st.dataframe(mix_df, use_container_width=True, hide_index=True)
                        st.caption(f"📊 Total: {len(mix_df)} production runs")

                st.divider()
                st.info("✅ Optimization complete! View detailed results in the **Results** page.")

                if st.button("📈 View Results", type="primary", use_container_width=True, key="view_opt_results"):
                    st.switch_page("pages/3_Results.py")

            elif result.is_infeasible():
                st.error("❌ Problem is infeasible - no solution exists that satisfies all constraints")

                # Show diagnostics
                if result.infeasibility_message:
                    st.warning("**Diagnostics:**")
                    st.write(result.infeasibility_message)

                st.info("💡 Try enabling 'Allow Demand Shortages' to find a feasible solution")

            else:
                st.warning(f"⚠️ Solver returned unexpected status")

                with st.expander("🔍 Solver Diagnostics", expanded=True):
                    st.write("**Termination Condition:**", result.termination_condition)
                    st.write("**Solver Status:**", result.solver_status)
                    st.write("**Success Flag:**", result.success)
                    st.write("**Objective Value:**", result.objective_value)

                    if result.infeasibility_message:
                        st.warning(f"**Message:** {result.infeasibility_message}")

                    # Check if this is actually optimal but flagged wrong
                    from pyomo.opt import TerminationCondition
                    if result.termination_condition == TerminationCondition.optimal:
                        st.info("""
                        **Termination condition is OPTIMAL** but success flag is False.
                        This may be due to:
                        1. Solution load failure
                        2. Solver status != ok
                        3. Objective value extraction issue

                        Check if results are still stored in session state despite this warning.
                        """)

                        # Try to view results anyway
                        if st.button("🔍 Try Viewing Results Anyway", type="secondary"):
                            st.switch_page("pages/3_Results.py")

        except Exception as e:
            st.error(f"❌ Error during optimization: {e}")
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())


# ===========================
# TAB 2: SCENARIO MANAGEMENT
# ===========================

with tab_scenarios:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">📊 Scenario Management</div>
        <div>Save, load, and compare different planning scenarios.</div>
        <div style="margin-top: 8px; font-size: 13px; color: #757575;">
            Compare heuristic vs. optimization results or test different configurations.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    scenario_manager = st.session_state.scenario_manager

    # Section 1: Save Current Scenario
    st.markdown(section_header("Save Current Scenario", level=3, icon="💾"), unsafe_allow_html=True)

    if session_state.is_planning_complete() or session_state.is_optimization_complete():
        col1, col2 = st.columns([3, 1])

        with col1:
            scenario_name = st.text_input(
                "Scenario Name",
                placeholder="e.g., Baseline Plan Q1 2025",
                key="scenario_name_input"
            )

            scenario_description = st.text_area(
                "Description (optional)",
                placeholder="Brief description of this scenario...",
                key="scenario_desc_input",
                height=80
            )

        with col2:
            scenario_type = "optimization" if session_state.is_optimization_complete() else "heuristic"
            st.info(f"**Type:** {scenario_type.title()}")

        if st.button("💾 Save Scenario", type="primary", use_container_width=True, key="save_scenario_btn"):
            if not scenario_name:
                st.error("Please provide a scenario name")
            else:
                # Get current data and results
                data = session_state.get_parsed_data()

                if session_state.is_optimization_complete():
                    opt_data = session_state.get_optimization_results()
                    scenario_data = {
                        'type': 'optimization',
                        'data': data,
                        'optimization_result': opt_data['result'],
                        'model': opt_data['model'],
                    }
                else:
                    planning_data = session_state.get_planning_results()
                    scenario_data = {
                        'type': 'heuristic',
                        'data': data,
                        'planning_results': planning_data,
                    }

                # Save scenario
                scenario_manager.save_scenario(
                    name=scenario_name,
                    description=scenario_description,
                    scenario_data=scenario_data
                )

                st.success(f"✅ Scenario '{scenario_name}' saved!")
                st.rerun()
    else:
        st.info("ℹ️ Run planning or optimization first to save a scenario")

    st.divider()

    # Section 2: Load Scenario
    st.markdown(section_header("Saved Scenarios", level=3, icon="📂"), unsafe_allow_html=True)

    scenarios = scenario_manager.list_scenarios()

    if scenarios:
        st.caption(f"{len(scenarios)} saved scenario(s)")

        for scenario in scenarios:
            with st.expander(f"📊 {scenario['name']}", expanded=False):
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.write(f"**Type:** {scenario['type'].title()}")
                    if scenario.get('description'):
                        st.write(f"**Description:** {scenario['description']}")
                    st.caption(f"Saved: {scenario['timestamp']}")

                with col2:
                    if st.button("📥 Load", key=f"load_{scenario['name']}", use_container_width=True):
                        loaded_data = scenario_manager.load_scenario(scenario['name'])
                        st.success(f"✅ Loaded scenario '{scenario['name']}'")
                        # TODO: Implement loading logic to restore session state

                with col3:
                    if st.button("🗑️ Delete", key=f"delete_{scenario['name']}", use_container_width=True):
                        scenario_manager.delete_scenario(scenario['name'])
                        st.success(f"Deleted scenario '{scenario['name']}'")
                        st.rerun()
    else:
        st.info("No saved scenarios yet. Save your planning results to create scenarios!")

    st.divider()

    # Section 3: Compare Scenarios
    st.markdown(section_header("Compare Scenarios", level=3, icon="⚖️"), unsafe_allow_html=True)

    if len(scenarios) >= 2:
        col1, col2 = st.columns(2)

        with col1:
            scenario_1 = st.selectbox(
                "Scenario 1",
                options=[s['name'] for s in scenarios],
                key="compare_scenario_1"
            )

        with col2:
            scenario_2 = st.selectbox(
                "Scenario 2",
                options=[s['name'] for s in scenarios if s['name'] != scenario_1],
                key="compare_scenario_2"
            )

        if st.button("⚖️ Compare Scenarios", type="primary", use_container_width=True, key="compare_btn"):
            st.info("Comparison functionality coming soon!")
            # TODO: Implement scenario comparison logic
    else:
        st.info("Save at least 2 scenarios to enable comparison")
