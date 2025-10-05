"""Planning - Run heuristic planning, mathematical optimization, or manage scenarios.

Consolidates:
- 3_Planning_Workflow.py (Heuristic)
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
    subtitle="Run heuristic planning, mathematical optimization, or manage scenarios"
)

# Check if data is loaded
if not check_data_required():
    st.stop()

st.divider()

# Create tabs for planning options
tab_heuristic, tab_optimization, tab_scenarios = st.tabs(["🎯 Heuristic", "⚡ Optimization", "📊 Scenarios"])


# ===========================
# TAB 1: HEURISTIC PLANNING
# ===========================

with tab_heuristic:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">🎯 Heuristic Planning Workflow</div>
        <div>Fast rule-based planning that generates production schedules, assigns shipments, and calculates costs.</div>
        <div style="margin-top: 8px; font-size: 13px; color: #757575;">
            This workflow executes 5 steps: Build network → Schedule production → Create shipments → Assign trucks → Calculate costs
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Show data summary
    with st.expander("📊 Loaded Data Summary", expanded=False):
        stats = session_state.get_summary_stats()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(colored_metric("Locations", str(stats.get('locations', 0)), "primary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Routes", str(stats.get('routes', 0)), "primary"), unsafe_allow_html=True)
        with col2:
            st.markdown(colored_metric("Forecast Entries", f"{stats.get('forecast_entries', 0):,}", "secondary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Products", str(stats.get('products_in_forecast', 0)), "secondary"), unsafe_allow_html=True)
        with col3:
            st.markdown(colored_metric("Total Demand", f"{stats.get('total_demand', 0):,.0f}", "accent"), unsafe_allow_html=True)
            st.markdown(colored_metric("Planning Days", str(stats.get('date_range_days', 0)), "accent"), unsafe_allow_html=True)
        with col4:
            st.markdown(colored_metric("Labor Days", str(stats.get('labor_days', 0)), "success"), unsafe_allow_html=True)
            st.markdown(colored_metric("Trucks/Week", str(stats.get('truck_schedules', 0)), "success"), unsafe_allow_html=True)

    st.divider()

    # Run workflow button
    st.markdown(section_header("Run Planning", level=3, icon="🚀"), unsafe_allow_html=True)

    if st.button("🚀 Execute Complete Workflow", type="primary", use_container_width=True, key="run_heuristic"):
        try:
            with st.spinner("Running planning workflow..."):
                from src.network import NetworkGraphBuilder, RouteFinder
                from src.production.scheduler import ProductionScheduler
                from src.distribution import ShipmentPlanner, TruckLoader
                from src.costs import CostCalculator

                # Get parsed data
                data = session_state.get_parsed_data()

                # Step 1: Build network graph
                st.info("Step 1/5: Building network graph...")
                graph_builder = NetworkGraphBuilder(
                    data['locations'],
                    data['routes']
                )
                graph = graph_builder.build_graph()
                route_finder = RouteFinder(graph_builder)

                # Step 2: Generate production schedule
                st.info("Step 2/5: Generating production schedule...")
                scheduler = ProductionScheduler(
                    manufacturing_site=data['manufacturing_site'],
                    labor_calendar=data['labor_calendar'],
                    graph_builder=graph_builder,
                )

                production_schedule = scheduler.schedule_from_forecast(
                    forecast=data['forecast']
                )

                # Check for infeasibilities
                if not production_schedule.is_feasible():
                    st.warning(f"⚠️ Production schedule has {len(production_schedule.infeasibilities)} infeasibilities")
                    for infeas in production_schedule.infeasibilities[:5]:  # Show first 5
                        st.warning(f"- {infeas}")

                # Step 3: Create shipments
                st.info("Step 3/5: Creating shipments...")
                shipment_planner = ShipmentPlanner()
                shipments = shipment_planner.create_shipments(production_schedule)

                # Step 4: Assign to trucks
                st.info("Step 4/5: Assigning shipments to trucks...")

                # Determine date range from production schedule
                if production_schedule.production_batches:
                    start_date = production_schedule.schedule_start_date
                    end_date = production_schedule.schedule_end_date
                    # Extend end date to cover delivery window
                    end_date = end_date + timedelta(days=7)
                else:
                    start_date = date.today()
                    end_date = date.today() + timedelta(days=30)

                truck_loader = TruckLoader(data['truck_schedules'])
                truck_plan = truck_loader.assign_shipments_to_trucks(
                    shipments=shipments,
                    start_date=start_date,
                    end_date=end_date,
                )

                # Check for truck loading infeasibilities
                if not truck_plan.is_feasible():
                    st.warning(f"⚠️ Truck loading has {len(truck_plan.infeasibilities)} infeasibilities")
                    for infeas in truck_plan.infeasibilities[:5]:  # Show first 5
                        st.warning(f"- {infeas}")

                # Step 5: Calculate costs
                st.info("Step 5/5: Calculating costs...")
                cost_calculator = CostCalculator(
                    data['cost_structure'],
                    data['labor_calendar']
                )

                cost_breakdown = cost_calculator.calculate_total_cost(
                    production_schedule=production_schedule,
                    shipments=shipments,
                    forecast=data['forecast'],
                )

                # Store results
                session_state.store_planning_objects(
                    graph_builder=graph_builder,
                    route_finder=route_finder,
                    scheduler=scheduler,
                )

                session_state.store_planning_results(
                    production_schedule=production_schedule,
                    shipments=shipments,
                    truck_plan=truck_plan,
                    cost_breakdown=cost_breakdown,
                )

                st.success("✅ Planning workflow completed successfully!")
                st.rerun()

        except Exception as e:
            st.error(f"❌ Error during planning workflow: {e}")
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())

    # Show results if available
    if session_state.is_planning_complete():
        st.divider()
        st.markdown(section_header("Planning Results", level=3, icon="📊"), unsafe_allow_html=True)

        summary = session_state.get_planning_summary()

        # High-level metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(colored_metric("Production Batches", str(summary.get('production_batches', 0)), "primary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Total Units", f"{summary.get('total_units', 0):,.0f}", "primary"), unsafe_allow_html=True)

        with col2:
            st.markdown(colored_metric("Shipments", str(summary.get('shipments_count', 0)), "secondary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Trucks Used", str(summary.get('trucks_used', 0)), "secondary"), unsafe_allow_html=True)

        with col3:
            st.markdown(colored_metric("Total Cost", f"${summary.get('total_cost', 0):,.2f}", "accent"), unsafe_allow_html=True)
            st.markdown(colored_metric("Cost/Unit", f"${summary.get('cost_per_unit', 0):.2f}", "accent"), unsafe_allow_html=True)

        with col4:
            if summary.get('production_is_feasible', True) and summary.get('truck_plan_is_feasible', True):
                st.markdown(success_badge("Feasible Plan"), unsafe_allow_html=True)
            else:
                st.markdown(warning_badge("Has Infeasibilities"), unsafe_allow_html=True)

        st.divider()

        # Navigation to results
        st.markdown("**View Detailed Results:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("📦 Production Schedule", use_container_width=True, key="nav_prod"):
                st.switch_page("pages/3_Results.py")
        with col2:
            if st.button("🚚 Distribution Plan", use_container_width=True, key="nav_dist"):
                st.switch_page("pages/3_Results.py")
        with col3:
            if st.button("💰 Cost Analysis", use_container_width=True, key="nav_cost"):
                st.switch_page("pages/3_Results.py")


# ===========================
# TAB 2: OPTIMIZATION
# ===========================

with tab_optimization:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">⚡ Mathematical Optimization</div>
        <div>Find the <strong>minimum cost</strong> production and distribution plan using mathematical optimization.</div>
        <div style="margin-top: 8px; font-size: 13px; color: #757575;">
            Uses Pyomo with solvers like CBC, GLPK, Gurobi, or CPLEX to find provably optimal solutions.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Solver Configuration
    st.markdown(section_header("Solver Configuration", level=3, icon="🔧"), unsafe_allow_html=True)

    from src.optimization.solver_config import SolverConfig

    # Detect available solvers
    solver_config = SolverConfig()
    available_solvers = solver_config.get_available_solvers()

    if not available_solvers:
        st.error("❌ No optimization solver found!")
        st.markdown("""
        **Installation Instructions:**

        **Linux/macOS:**
        ```bash
        conda install -c conda-forge coincbc
        ```

        **Windows:**
        1. Download CBC from: https://ampl.com/products/solvers/open-source/
        2. Extract `cbc.exe` to your PATH or venv/Scripts folder
        3. Restart your terminal

        **Alternative: GLPK**
        ```bash
        conda install -c conda-forge glpk
        ```

        See `docs/SOLVER_INSTALLATION.md` for complete instructions.
        """)
        st.stop()

    # Display available solvers
    col1, col2 = st.columns([2, 1])

    with col1:
        st.success(f"✓ Found {len(available_solvers)} solver(s): {', '.join([s.upper() for s in available_solvers])}")

        # Solver selection
        solver_names_display = {
            'cbc': 'CBC (Open Source - Recommended)',
            'asl:cbc': 'ASL:CBC (AMPL Interface)',
            'glpk': 'GLPK (Open Source)',
            'gurobi': 'Gurobi (Commercial)',
            'cplex': 'CPLEX (Commercial)',
        }

        solver_options = [s for s in available_solvers if s in solver_names_display]
        selected_solver = st.selectbox(
            "Select Solver",
            options=solver_options,
            format_func=lambda x: solver_names_display.get(x, x.upper()),
            index=0 if solver_options else None,
            key="opt_solver_select"
        )

    with col2:
        if st.button("Test Solver", use_container_width=True, key="test_solver_btn"):
            with st.spinner(f"Testing {selected_solver.upper()}..."):
                success = solver_config.test_solver(selected_solver, verbose=False)
                if success:
                    st.success(f"✓ {selected_solver.upper()} works!")
                else:
                    st.error(f"✗ {selected_solver.upper()} test failed")

    st.divider()

    # Optimization Settings
    st.markdown(section_header("Optimization Settings", level=3, icon="⚙️"), unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        time_limit = st.slider(
            "Time Limit (seconds)",
            min_value=30,
            max_value=600,
            value=300,
            step=30,
            help="Maximum time solver will run before stopping",
            key="opt_time_limit"
        )

        mip_gap = st.slider(
            "MIP Gap Tolerance (%)",
            min_value=0.0,
            max_value=10.0,
            value=1.0,
            step=0.5,
            help="Accept solutions within this % of optimal (0% = prove optimality)",
            key="opt_mip_gap"
        )

    with col2:
        allow_shortages = st.checkbox(
            "Allow Demand Shortages",
            value=False,
            help="If checked, model can leave demand unmet with penalty cost",
            key="opt_allow_shortages"
        )

        enforce_shelf_life = st.checkbox(
            "Enforce Shelf Life Constraints",
            value=True,
            help="Filter routes exceeding 10-day product age limit",
            key="opt_enforce_shelf"
        )

        max_routes = st.number_input(
            "Max Routes per Destination",
            min_value=1,
            max_value=10,
            value=5,
            help="Number of alternative routes to consider",
            key="opt_max_routes"
        )

    with col3:
        show_solver_output = st.checkbox(
            "Show Solver Output",
            value=False,
            help="Display detailed solver log during optimization",
            key="opt_show_output"
        )

    st.divider()

    # Run Optimization
    st.markdown(section_header("Run Optimization", level=3, icon="🚀"), unsafe_allow_html=True)

    if st.button("⚡ Solve Optimization Model", type="primary", use_container_width=True, key="run_optimization"):
        try:
            with st.spinner("Building optimization model..."):
                from src.optimization import IntegratedProductionDistributionModel

                # Get parsed data
                data = session_state.get_parsed_data()

                # Create optimization model
                model = IntegratedProductionDistributionModel(
                    forecast=data['forecast'],
                    labor_calendar=data['labor_calendar'],
                    manufacturing_site=data['manufacturing_site'],
                    cost_structure=data['cost_structure'],
                    locations=data['locations'],
                    routes=data['routes'],
                    truck_schedules=data['truck_schedules'],
                    max_routes_per_destination=max_routes,
                    allow_shortages=allow_shortages,
                    enforce_shelf_life=enforce_shelf_life,
                )

                st.info(f"Model: {len(model.enumerated_routes)} routes, {len(model.production_dates)} days")

            with st.spinner(f"Solving with {selected_solver.upper()}... (max {time_limit}s)"):
                # Solve
                result = model.solve(
                    solver_name=selected_solver,
                    time_limit_seconds=time_limit,
                    mip_gap=mip_gap / 100.0,  # Convert % to fraction
                    tee=show_solver_output,
                )

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
                        model=model,
                        result=result
                    )

                    st.divider()
                    st.info("✅ Optimization complete! View results in the **Results** page.")

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
                    st.warning(f"⚠️ Solver returned status: {result.termination_condition}")

        except Exception as e:
            st.error(f"❌ Error during optimization: {e}")
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())


# ===========================
# TAB 3: SCENARIO MANAGEMENT
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
