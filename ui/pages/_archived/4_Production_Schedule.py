"""Production schedule analysis page."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from datetime import datetime
from ui import session_state
from ui.components import (
    render_production_gantt,
    render_labor_hours_chart,
    render_daily_production_chart,
    render_capacity_utilization_chart,
    render_production_batches_table,
    render_daily_breakdown_table,
    render_date_range_filter,
    apply_date_filter,
)
from ui.components.styling import apply_custom_css, section_header

# Page config
st.set_page_config(
    page_title="Production Schedule",
    page_icon="📦",
    layout="wide",
)

# Apply custom CSS
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

st.markdown(section_header("Production Schedule", level=1, icon="📦"), unsafe_allow_html=True)

# Check if planning is complete
if not session_state.is_planning_complete():
    st.warning("⚠️ No production schedule available. Please run the planning workflow first.")
    if st.button("Go to Planning Workflow", type="primary"):
        st.switch_page("pages/3_Planning_Workflow.py")
    st.stop()

# Get planning results
results = session_state.get_planning_results()
production_schedule = results['production_schedule']

# Date Range Filter
st.divider()

# Get date range from production schedule
if production_schedule.production_batches:
    all_batch_dates = [b.production_date for b in production_schedule.production_batches]
    min_date = min(all_batch_dates)
    max_date = max(all_batch_dates)

    # Convert to datetime for filter component
    min_datetime = datetime.combine(min_date, datetime.min.time())
    max_datetime = datetime.combine(max_date, datetime.min.time())

    # Render date filter
    filter_start_date, filter_end_date = render_date_range_filter(
        min_date=min_datetime,
        max_date=max_datetime,
        default_range="2weeks",
        key_prefix="production_schedule_filter",
        include_url_params=True
    )

    # Filter production batches based on date range
    filtered_batches = [
        b for b in production_schedule.production_batches
        if filter_start_date.date() <= b.production_date <= filter_end_date.date()
    ]

    # Filter daily totals and labor hours
    filtered_daily_totals = {
        d: qty for d, qty in production_schedule.daily_totals.items()
        if filter_start_date.date() <= d <= filter_end_date.date()
    }

    filtered_daily_labor_hours = {
        d: hrs for d, hrs in production_schedule.daily_labor_hours.items()
        if filter_start_date.date() <= d <= filter_end_date.date()
    }

    # Create filtered production schedule
    from src.production.scheduler import ProductionSchedule
    filtered_schedule = ProductionSchedule(
        manufacturing_site_id=production_schedule.manufacturing_site_id,
        schedule_start_date=production_schedule.schedule_start_date,
        schedule_end_date=production_schedule.schedule_end_date,
        production_batches=filtered_batches,
        daily_totals=filtered_daily_totals,
        daily_labor_hours=filtered_daily_labor_hours,
        infeasibilities=production_schedule.infeasibilities,
        total_units=sum(b.quantity for b in filtered_batches),
        total_labor_hours=sum(filtered_daily_labor_hours.values()),
        requirements=production_schedule.requirements,
    )
else:
    # No batches, use original schedule
    filtered_schedule = production_schedule

st.divider()

# Summary metrics
st.markdown(section_header("Schedule Summary", level=2, icon="📊"), unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Production Batches", len(filtered_schedule.production_batches))
    st.metric("Total Units", f"{filtered_schedule.total_units:,.0f}")

with col2:
    st.metric("Total Labor Hours", f"{filtered_schedule.total_labor_hours:.1f}h")
    avg_daily_hours = filtered_schedule.total_labor_hours / len(filtered_schedule.daily_totals) if filtered_schedule.daily_totals else 0
    st.metric("Avg Daily Hours", f"{avg_daily_hours:.1f}h")

with col3:
    st.metric("Production Days", len(filtered_schedule.daily_totals))
    # Show filtered date range
    if filtered_schedule.production_batches:
        filtered_dates = [b.production_date for b in filtered_schedule.production_batches]
        date_range = f"{min(filtered_dates)} to {max(filtered_dates)}"
    else:
        date_range = "No production"
    st.caption(f"**Date Range:**\n{date_range}")

with col4:
    if production_schedule.is_feasible():
        st.success("✅ Feasible")
    else:
        st.error(f"❌ {len(production_schedule.infeasibilities)} Issues")

    # Show filtered vs total
    if len(filtered_schedule.production_batches) < len(production_schedule.production_batches):
        st.caption(f"**Filtered:** {len(filtered_schedule.production_batches)} / {len(production_schedule.production_batches)} batches")

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
    st.markdown(section_header("Production Schedule (Gantt Chart)", level=3), unsafe_allow_html=True)
    st.markdown("Shows production batches by product and date")

    fig = render_production_gantt(filtered_schedule, height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Each bar represents a production batch. Batches are grouped by product.")

with tab2:
    st.markdown(section_header("Labor Hours Analysis", level=3), unsafe_allow_html=True)

    # Labor hours chart
    st.markdown("**Daily Labor Hours vs. Capacity**")
    fig = render_labor_hours_chart(filtered_schedule, height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Capacity utilization
    st.markdown("**Production Capacity Utilization**")
    fig = render_capacity_utilization_chart(filtered_schedule, height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Maximum capacity: 1,400 units/hour × 14 hours = 19,600 units/day")

with tab3:
    st.markdown(section_header("Daily Production Quantities", level=3), unsafe_allow_html=True)
    st.markdown("Shows production quantities by product and date")

    fig = render_daily_production_chart(filtered_schedule, height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Daily breakdown table
    st.markdown("**Daily Summary Table**")
    render_daily_breakdown_table(filtered_schedule)

with tab4:
    st.markdown(section_header("Production Batches", level=3), unsafe_allow_html=True)

    # Additional product filter for the table
    col1, col2 = st.columns(2)

    with col1:
        # Product filter
        all_products = sorted(set(b.product_id for b in filtered_schedule.production_batches))
        if all_products:
            selected_products = st.multiselect(
                "Filter by Product",
                options=all_products,
                default=all_products,
                key="product_filter_table"
            )
        else:
            selected_products = []

    # Filter batches by product
    table_filtered_batches = [
        b for b in filtered_schedule.production_batches
        if b.product_id in selected_products
    ]

    st.caption(f"Showing {len(table_filtered_batches)} of {len(production_schedule.production_batches)} batches")

    # Create schedule for table with product filter applied
    from src.production.scheduler import ProductionSchedule
    table_schedule = ProductionSchedule(
        manufacturing_site_id=filtered_schedule.manufacturing_site_id,
        schedule_start_date=filtered_schedule.schedule_start_date,
        schedule_end_date=filtered_schedule.schedule_end_date,
        production_batches=table_filtered_batches,
        daily_totals=filtered_schedule.daily_totals,
        daily_labor_hours=filtered_schedule.daily_labor_hours,
        infeasibilities=filtered_schedule.infeasibilities,
        total_units=sum(b.quantity for b in table_filtered_batches),
        total_labor_hours=sum(b.labor_hours_used for b in table_filtered_batches),
        requirements=filtered_schedule.requirements,
    )

    render_production_batches_table(table_schedule)

    # Export option
    st.divider()

    col1, col2 = st.columns([3, 1])

    with col1:
        st.caption("Export production schedule to Excel with formatted tables and charts")

    with col2:
        if st.button("📥 Export to Excel", type="secondary", use_container_width=True):
            try:
                import tempfile
                import os
                from datetime import datetime
                from src.exporters import export_production_schedule

                # Create temporary file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"production_schedule_{timestamp}.xlsx"
                temp_dir = tempfile.gettempdir()
                output_path = os.path.join(temp_dir, filename)

                # Get cost breakdown if available
                cost_breakdown = results.get('cost_breakdown', None)

                # Export to Excel
                with st.spinner("Generating Excel file..."):
                    export_production_schedule(
                        production_schedule=production_schedule,
                        labor_data=None,  # Could pass labor DataFrame if available
                        output_path=output_path,
                        cost_breakdown=cost_breakdown
                    )

                # Read file for download
                with open(output_path, 'rb') as f:
                    excel_data = f.read()

                # Provide download button
                st.download_button(
                    label="💾 Download Excel File",
                    data=excel_data,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )

                st.success(f"✅ Excel file generated: {filename}")

            except Exception as e:
                st.error(f"❌ Error exporting to Excel: {str(e)}")
                st.exception(e)

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
