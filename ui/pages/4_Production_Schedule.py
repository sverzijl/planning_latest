"""Production schedule analysis page."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from ui import session_state
from ui.components import (
    render_production_gantt,
    render_labor_hours_chart,
    render_daily_production_chart,
    render_capacity_utilization_chart,
    render_production_batches_table,
    render_daily_breakdown_table,
)

# Page config
st.set_page_config(
    page_title="Production Schedule",
    page_icon="📦",
    layout="wide",
)

# Initialize session state
session_state.initialize_session_state()

st.header("📦 Production Schedule")

# Check if planning is complete
if not session_state.is_planning_complete():
    st.warning("⚠️ No production schedule available. Please run the planning workflow first.")
    if st.button("Go to Planning Workflow", type="primary"):
        st.switch_page("pages/3_Planning_Workflow.py")
    st.stop()

# Get planning results
results = session_state.get_planning_results()
production_schedule = results['production_schedule']

# Summary metrics
st.subheader("📊 Schedule Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Production Batches", len(production_schedule.production_batches))
    st.metric("Total Units", f"{production_schedule.total_units:,.0f}")

with col2:
    st.metric("Total Labor Hours", f"{production_schedule.total_labor_hours:.1f}h")
    avg_daily_hours = production_schedule.total_labor_hours / len(production_schedule.daily_totals) if production_schedule.daily_totals else 0
    st.metric("Avg Daily Hours", f"{avg_daily_hours:.1f}h")

with col3:
    st.metric("Production Days", len(production_schedule.daily_totals))
    date_range = f"{production_schedule.schedule_start_date} to {production_schedule.schedule_end_date}"
    st.caption(f"**Date Range:**\n{date_range}")

with col4:
    if production_schedule.is_feasible():
        st.success("✅ Feasible")
    else:
        st.error(f"❌ {len(production_schedule.infeasibilities)} Issues")

    # Show requirements
    st.metric("Requirements", len(production_schedule.requirements))

# Show infeasibilities if any
if not production_schedule.is_feasible():
    st.divider()
    st.error("⚠️ **Production Schedule Infeasibilities:**")
    for infeas in production_schedule.infeasibilities:
        st.warning(f"- {infeas}")

st.divider()

# Visualizations
tab1, tab2, tab3, tab4 = st.tabs([
    "📅 Gantt Chart",
    "👷 Labor Analysis",
    "📈 Daily Production",
    "📋 Detailed Tables"
])

with tab1:
    st.subheader("Production Schedule (Gantt Chart)")
    st.markdown("Shows production batches by product and date")

    fig = render_production_gantt(production_schedule, height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Each bar represents a production batch. Batches are grouped by product.")

with tab2:
    st.subheader("Labor Hours Analysis")

    # Labor hours chart
    st.markdown("**Daily Labor Hours vs. Capacity**")
    fig = render_labor_hours_chart(production_schedule, height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Capacity utilization
    st.markdown("**Production Capacity Utilization**")
    fig = render_capacity_utilization_chart(production_schedule, height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Maximum capacity: 1,400 units/hour × 14 hours = 19,600 units/day")

with tab3:
    st.subheader("Daily Production Quantities")
    st.markdown("Shows production quantities by product and date")

    fig = render_daily_production_chart(production_schedule, height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Daily breakdown table
    st.markdown("**Daily Summary Table**")
    render_daily_breakdown_table(production_schedule)

with tab4:
    st.subheader("Production Batches")

    # Filters
    col1, col2 = st.columns(2)

    with col1:
        # Product filter
        all_products = sorted(set(b.product_id for b in production_schedule.production_batches))
        selected_products = st.multiselect(
            "Filter by Product",
            options=all_products,
            default=all_products,
            key="product_filter"
        )

    with col2:
        # Date filter
        all_dates = sorted(set(b.production_date for b in production_schedule.production_batches))
        if all_dates:
            date_range_filter = st.date_input(
                "Filter by Date Range",
                value=(min(all_dates), max(all_dates)),
                key="date_range_filter"
            )

    # Filter batches
    filtered_batches = [
        b for b in production_schedule.production_batches
        if b.product_id in selected_products
    ]

    if 'date_range_filter' in locals() and date_range_filter:
        if len(date_range_filter) == 2:
            start_date, end_date = date_range_filter
            filtered_batches = [
                b for b in filtered_batches
                if start_date <= b.production_date <= end_date
            ]

    st.caption(f"Showing {len(filtered_batches)} of {len(production_schedule.production_batches)} batches")

    # Create temporary schedule with filtered batches
    from src.production.scheduler import ProductionSchedule
    filtered_schedule = ProductionSchedule(
        manufacturing_site_id=production_schedule.manufacturing_site_id,
        schedule_start_date=production_schedule.schedule_start_date,
        schedule_end_date=production_schedule.schedule_end_date,
        production_batches=filtered_batches,
        daily_totals=production_schedule.daily_totals,
        daily_labor_hours=production_schedule.daily_labor_hours,
        infeasibilities=production_schedule.infeasibilities,
        total_units=sum(b.quantity for b in filtered_batches),
        total_labor_hours=sum(b.labor_hours_used for b in filtered_batches),
        requirements=production_schedule.requirements,
    )

    render_production_batches_table(filtered_schedule)

    # Export option
    st.divider()
    if st.button("📥 Export to Excel", type="secondary"):
        st.info("Excel export functionality coming soon!")

# Footer with navigation
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Back to Workflow", use_container_width=True):
        st.switch_page("pages/3_Planning_Workflow.py")

with col2:
    if st.button("Distribution Plan →", use_container_width=True):
        st.switch_page("pages/5_Distribution_Plan.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
