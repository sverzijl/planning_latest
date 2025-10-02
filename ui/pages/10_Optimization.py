"""Optimization page - mathematical optimization for cost minimization."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from datetime import timedelta
from ui import session_state
from src.optimization import IntegratedProductionDistributionModel
from src.optimization.solver_config import SolverConfig

# Page config
st.set_page_config(
    page_title="Optimization",
    page_icon="⚡",
    layout="wide",
)

# Initialize session state
session_state.initialize_session_state()

st.header("⚡ Mathematical Optimization")

st.markdown("""
Use mathematical optimization to find the **minimum cost** production and distribution plan.
This uses Pyomo with solvers like CBC, GLPK, Gurobi, or CPLEX to find provably optimal solutions.
""")

# Check prerequisites
if not session_state.is_data_uploaded():
    st.warning("⚠️ No data uploaded. Please upload forecast and network configuration files first.")
    if st.button("Go to Upload Page", type="primary"):
        st.switch_page("pages/1_Upload_Data.py")
    st.stop()

st.divider()

# Section 1: Solver Configuration
st.subheader("🔧 Solver Configuration")

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
    )

with col2:
    if st.button("Test Solver", use_container_width=True):
        with st.spinner(f"Testing {selected_solver.upper()}..."):
            success = solver_config.test_solver(selected_solver, verbose=False)
            if success:
                st.success(f"✓ {selected_solver.upper()} works!")
            else:
                st.error(f"✗ {selected_solver.upper()} test failed")

st.divider()

# Section 2: Optimization Settings
st.subheader("⚙️ Optimization Settings")

col1, col2, col3 = st.columns(3)

with col1:
    time_limit = st.slider(
        "Time Limit (seconds)",
        min_value=30,
        max_value=600,
        value=300,
        step=30,
        help="Maximum time solver will run before stopping"
    )

    mip_gap = st.slider(
        "MIP Gap Tolerance (%)",
        min_value=0.0,
        max_value=10.0,
        value=1.0,
        step=0.5,
        help="Accept solutions within this % of optimal (0% = prove optimality)"
    )

with col2:
    allow_shortages = st.checkbox(
        "Allow Demand Shortages",
        value=False,
        help="If checked, model can leave demand unmet with penalty cost"
    )

    enforce_shelf_life = st.checkbox(
        "Enforce Shelf Life Constraints",
        value=True,
        help="Filter routes exceeding 10-day product age limit"
    )

    max_routes = st.number_input(
        "Max Routes per Destination",
        min_value=1,
        max_value=10,
        value=5,
        help="Number of alternative routes to consider"
    )

with col3:
    show_solver_output = st.checkbox(
        "Show Solver Output",
        value=False,
        help="Display detailed solver log during optimization"
    )

st.divider()

# Section 3: Run Optimization
st.subheader("🚀 Run Optimization")

def run_optimization():
    """Execute optimization and store results."""
    try:
        with st.spinner("Building optimization model..."):
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
                mip_gap=mip_gap / 100.0,  # Convert % to decimal
                tee=show_solver_output,
            )

        # Store results in session state
        st.session_state['optimization_result'] = result
        st.session_state['optimization_model'] = model
        st.session_state['optimization_solver'] = selected_solver

        return result, model

    except Exception as e:
        st.error(f"❌ Optimization failed: {e}")
        import traceback
        with st.expander("Error Details"):
            st.code(traceback.format_exc())
        return None, None

# Run button
if st.button("▶️ Run Optimization", type="primary", use_container_width=True):
    result, model = run_optimization()
    if result:
        st.rerun()

# Section 4: Results Display
if 'optimization_result' in st.session_state:
    result = st.session_state['optimization_result']
    model = st.session_state['optimization_model']
    solver = st.session_state.get('optimization_solver', 'unknown')

    st.divider()
    st.subheader("📊 Optimization Results")

    # Status
    if result.is_optimal():
        st.success(f"✅ **Optimal solution found!** (solved with {solver.upper()} in {result.solve_time_seconds:.2f}s)")
    elif result.is_feasible():
        st.warning(f"⚠️ **Feasible solution found** (not proven optimal, gap: {result.gap*100:.1f}%)")
    else:
        st.error(f"❌ **No solution found** - Status: {result.termination_condition}")
        if result.infeasibility_message:
            st.error(result.infeasibility_message)

    if result.is_feasible():
        # Metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Cost", f"${result.objective_value:,.2f}")
            st.metric("Solve Time", f"{result.solve_time_seconds:.2f}s")

        with col2:
            st.metric("Variables", f"{result.num_variables:,}")
            st.metric("Constraints", f"{result.num_constraints:,}")

        with col3:
            if result.gap is not None:
                st.metric("MIP Gap", f"{result.gap*100:.2f}%")
            st.metric("Integer Vars", f"{result.num_integer_vars:,}")

        with col4:
            solution = model.get_solution()
            if solution:
                demand_total = sum(model.demand.values())
                shortage_total = solution.get('total_shortage_units', 0)
                satisfaction_pct = ((demand_total - shortage_total) / demand_total * 100) if demand_total > 0 else 0
                st.metric("Demand Satisfied", f"{satisfaction_pct:.1f}%")
                if shortage_total > 0:
                    st.metric("Shortage Units", f"{shortage_total:,.0f}")

        # Cost breakdown
        st.divider()
        st.subheader("💰 Cost Breakdown")

        solution = model.get_solution()
        if solution:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Labor Cost", f"${solution['total_labor_cost']:,.2f}")
            with col2:
                st.metric("Production Cost", f"${solution['total_production_cost']:,.2f}")
            with col3:
                st.metric("Transport Cost", f"${solution['total_transport_cost']:,.2f}")
            with col4:
                if solution.get('total_shortage_cost', 0) > 0:
                    st.metric("Shortage Penalty", f"${solution['total_shortage_cost']:,.2f}")

            # Cost chart
            import plotly.graph_objects as go

            costs = {
                'Labor': solution['total_labor_cost'],
                'Production': solution['total_production_cost'],
                'Transport': solution['total_transport_cost'],
            }
            if solution.get('total_shortage_cost', 0) > 0:
                costs['Shortage'] = solution['total_shortage_cost']

            fig = go.Figure(data=[
                go.Bar(
                    x=list(costs.keys()),
                    y=list(costs.values()),
                    text=[f"${v:,.0f}" for v in costs.values()],
                    textposition='auto',
                )
            ])
            fig.update_layout(
                title="Cost Components",
                xaxis_title="Component",
                yaxis_title="Cost ($)",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

        # Solution summary
        st.divider()
        st.subheader("📋 Solution Summary")

        with st.expander("View Detailed Solution", expanded=False):
            model.print_solution_summary()
            st.write("")
            model.print_demand_diagnostics()

        # Production schedule
        if solution and solution.get('production_by_date_product'):
            st.divider()
            st.subheader("📦 Production Schedule")

            import pandas as pd

            prod_data = []
            for (prod_date, product), qty in solution['production_by_date_product'].items():
                prod_data.append({
                    'Date': prod_date,
                    'Product': product,
                    'Quantity': qty,
                })

            if prod_data:
                df = pd.DataFrame(prod_data)
                df = df.sort_values(['Date', 'Product'])
                st.dataframe(df, use_container_width=True, hide_index=True)

        # Shipment plan
        shipments = model.get_shipment_plan()
        if shipments:
            st.divider()
            st.subheader("🚚 Shipment Plan")
            st.write(f"Total shipments: {len(shipments)}")

            with st.expander("View All Shipments", expanded=False):
                for i, ship in enumerate(shipments[:50], 1):
                    st.text(f"{i}. {ship}")
                if len(shipments) > 50:
                    st.text(f"... and {len(shipments) - 50} more shipments")

    # Clear results button
    st.divider()
    if st.button("🔄 Clear Results and Run Again"):
        if 'optimization_result' in st.session_state:
            del st.session_state['optimization_result']
        if 'optimization_model' in st.session_state:
            del st.session_state['optimization_model']
        st.rerun()

# Navigation
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Planning Workflow", use_container_width=True):
        st.switch_page("pages/3_Planning_Workflow.py")

with col2:
    if st.button("Cost Analysis →", use_container_width=True):
        st.switch_page("pages/6_Cost_Analysis.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
