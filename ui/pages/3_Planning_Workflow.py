"""Planning workflow page - orchestrates the complete planning process."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from datetime import date, timedelta
from ui import session_state
from src.network import NetworkGraphBuilder, RouteFinder
from src.production.scheduler import ProductionScheduler
from src.distribution import ShipmentPlanner, TruckLoader
from src.costs import CostCalculator

# Page config
st.set_page_config(
    page_title="Planning Workflow",
    page_icon="🚀",
    layout="wide",
)

# Initialize session state
session_state.initialize_session_state()

st.header("🚀 Planning Workflow")

st.markdown("""
This workflow executes the complete planning process from forecast to costs.
Each step builds on the previous one to create an integrated production and distribution plan.
""")

# Check prerequisites
if not session_state.is_data_uploaded():
    st.warning("⚠️ No data uploaded. Please upload forecast and network configuration files first.")
    if st.button("Go to Upload Page", type="primary"):
        st.switch_page("pages/1_Upload_Data.py")
    st.stop()

# Show data summary
with st.expander("📊 Loaded Data Summary", expanded=False):
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
        st.metric("Truck Schedules", stats.get('truck_schedules', 0))

st.divider()

# Workflow execution section
st.subheader("📋 Workflow Steps")

# Create columns for workflow steps
col1, col2 = st.columns([3, 1])


def run_complete_workflow():
    """Execute the complete planning workflow."""
    try:
        with st.spinner("Running planning workflow..."):
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

            session_state.set_current_step(1)

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

            session_state.set_current_step(2)

            # Check for infeasibilities
            if not production_schedule.is_feasible():
                st.warning(f"⚠️ Production schedule has {len(production_schedule.infeasibilities)} infeasibilities")
                for infeas in production_schedule.infeasibilities[:5]:  # Show first 5
                    st.warning(f"- {infeas}")

            # Step 3: Create shipments
            st.info("Step 3/5: Creating shipments...")
            shipment_planner = ShipmentPlanner()
            shipments = shipment_planner.create_shipments(production_schedule)

            session_state.set_current_step(3)

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

            session_state.set_current_step(4)

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

            session_state.set_current_step(5)

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


def show_workflow_results():
    """Display workflow results summary."""
    st.subheader("📊 Planning Results")

    summary = session_state.get_planning_summary()

    # High-level metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Production Batches",
            summary.get('production_batches', 0)
        )
        st.metric(
            "Total Units",
            f"{summary.get('total_units', 0):,.0f}"
        )

    with col2:
        st.metric(
            "Labor Hours",
            f"{summary.get('total_labor_hours', 0):.1f}h"
        )
        st.metric(
            "Shipments",
            summary.get('shipments_count', 0)
        )

    with col3:
        st.metric(
            "Trucks Used",
            summary.get('trucks_used', 0)
        )
        st.metric(
            "Avg Utilization",
            f"{summary.get('average_utilization', 0):.1%}"
        )

    with col4:
        st.metric(
            "Total Cost",
            f"${summary.get('total_cost', 0):,.2f}"
        )
        st.metric(
            "Cost/Unit",
            f"${summary.get('cost_per_unit', 0):.2f}"
        )

    # Feasibility status
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if summary.get('production_is_feasible', True):
            st.success("✅ Production schedule is feasible")
        else:
            st.error("❌ Production schedule has infeasibilities")

    with col2:
        if summary.get('truck_plan_is_feasible', True):
            st.success("✅ Truck loading is feasible")
        else:
            st.error(f"❌ Truck loading has {summary.get('unassigned_shipments', 0)} unassigned shipments")

    # Cost breakdown
    st.divider()
    st.subheader("💰 Cost Breakdown")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Labor Cost", f"${summary.get('labor_cost', 0):,.2f}")
    with col2:
        st.metric("Production Cost", f"${summary.get('production_cost', 0):,.2f}")
    with col3:
        st.metric("Transport Cost", f"${summary.get('transport_cost', 0):,.2f}")
    with col4:
        st.metric("Waste Cost", f"${summary.get('waste_cost', 0):,.2f}")

    # Links to detailed pages
    st.divider()
    st.subheader("📑 View Detailed Analysis")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📦 Production Schedule", use_container_width=True):
            st.switch_page("pages/4_Production_Schedule.py")

    with col2:
        if st.button("🚚 Distribution Plan", use_container_width=True):
            st.switch_page("pages/5_Distribution_Plan.py")

    with col3:
        if st.button("💰 Cost Analysis", use_container_width=True):
            st.switch_page("pages/6_Cost_Analysis.py")


# Main workflow UI
with col1:
    # Step progress indicator
    steps = [
        "Build Network Graph",
        "Generate Production Schedule",
        "Create Shipments",
        "Assign to Trucks",
        "Calculate Costs"
    ]

    current_step = session_state.get_current_step()

    for i, step in enumerate(steps):
        if i < current_step:
            st.success(f"✅ Step {i+1}: {step}")
        elif i == current_step:
            st.info(f"⏳ Step {i+1}: {step}")
        else:
            st.text(f"⏸️ Step {i+1}: {step}")

with col2:
    # Run/Clear buttons
    if st.button("▶️ Run Complete Workflow", type="primary", use_container_width=True):
        run_complete_workflow()

    if session_state.is_planning_complete():
        if st.button("🔄 Clear Results", use_container_width=True):
            session_state.clear_planning_results()
            st.rerun()

st.divider()

# Show results if planning is complete
if session_state.is_planning_complete():
    show_workflow_results()

# Navigation
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Data Summary", use_container_width=True):
        st.switch_page("pages/2_Data_Summary.py")

with col2:
    if st.button("Production Schedule →", use_container_width=True):
        st.switch_page("pages/4_Production_Schedule.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
