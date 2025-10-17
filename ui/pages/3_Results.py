"""Results - View production schedules, distribution plans, costs, and comparisons.

Consolidates:
- 4_Production_Schedule.py
- 5_Distribution_Plan.py
- 6_Cost_Analysis.py
- 11_Results_Comparison.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from datetime import datetime
import math
from ui import session_state
from ui.utils import adapt_optimization_results, extract_labor_hours
from ui.components.styling import apply_custom_css, section_header, colored_metric, success_badge, error_badge, warning_badge
from ui.components.navigation import render_page_header, check_planning_required
from ui.components import (
    render_production_gantt,
    render_labor_hours_chart,
    render_daily_production_chart,
    render_capacity_utilization_chart,
    render_production_batches_table,
    render_daily_breakdown_table,
    render_date_range_filter,
    render_truck_loading_timeline,
    render_shipments_by_destination_chart,
    render_truck_utilization_chart,
    render_shipments_table,
    render_truck_loads_table,
    render_cost_breakdown_chart,
    render_cost_by_category_chart,
    render_daily_cost_chart,
    render_cost_breakdown_table,
    render_daily_snapshot,
)
from ui.components.production_labeling import render_production_labeling_view

# Page config
st.set_page_config(
    page_title="Results - GF Bread Production",
    page_icon="📈",
    layout="wide",
)

# Apply design system
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

# Page header
render_page_header(
    title="Results",
    icon="📈",
    subtitle="View production schedules, distribution plans, costs, and comparisons"
)

# Check if planning results are available
if not check_planning_required():
    st.stop()

st.divider()

# ===========================
# RESULT SOURCE SELECTION
# ===========================

# Check which results are available
has_heuristic = session_state.is_planning_complete()
has_optimization = session_state.is_optimization_complete()

# Initialize result source in session state if not set
if 'result_source' not in st.session_state:
    # Default to most recently completed
    if has_optimization:
        st.session_state.result_source = 'optimization'
    elif has_heuristic:
        st.session_state.result_source = 'heuristic'
    else:
        st.session_state.result_source = 'heuristic'

# Result source selector if both are available
if has_heuristic and has_optimization:
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 12px 20px; border-radius: 8px; margin-bottom: 16px;">
            <div style="color: white; font-weight: 600; font-size: 14px;">
                📊 SELECT RESULT SOURCE
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        pass

    result_source = st.radio(
        "Choose which results to display:",
        options=['heuristic', 'optimization'],
        format_func=lambda x: "🎯 Heuristic Planning" if x == 'heuristic' else "⚡ Optimized Solution",
        key='result_source',
        horizontal=True,
    )
elif has_optimization:
    st.session_state.result_source = 'optimization'
    result_source = 'optimization'
else:
    st.session_state.result_source = 'heuristic'
    result_source = 'heuristic'

# Display result source indicator
if result_source == 'optimization':
    opt_results = session_state.get_optimization_results()
    result_info = opt_results.get('result', {})
    solver_status = getattr(result_info, 'termination_condition', 'UNKNOWN')
    solve_time = getattr(result_info, 'solve_time_seconds', 0)

    # Determine status color
    if solver_status in ['optimal', 'OPTIMAL']:
        status_color = "#10b981"  # Green
        status_icon = "✅"
        status_text = "OPTIMAL"
    elif solver_status in ['feasible', 'FEASIBLE']:
        status_color = "#f59e0b"  # Yellow
        status_icon = "⚠️"
        status_text = "FEASIBLE"
    else:
        status_color = "#ef4444"  # Red
        status_icon = "❌"
        status_text = "INFEASIBLE"

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {status_color}20 0%, {status_color}10 100%);
                border-left: 4px solid {status_color};
                padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-size: 12px; color: #64748b; font-weight: 500; margin-bottom: 4px;">
                    VIEWING RESULTS FROM
                </div>
                <div style="font-size: 18px; font-weight: 700; color: {status_color};">
                    {status_icon} OPTIMIZATION ({status_text})
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 12px; color: #64748b; font-weight: 500; margin-bottom: 4px;">
                    SOLVE TIME
                </div>
                <div style="font-size: 16px; font-weight: 600; color: #1e293b;">
                    {solve_time:.2f}s
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #3b82f620 0%, #3b82f610 100%);
                border-left: 4px solid #3b82f6;
                padding: 16px 20px; border-radius: 8px; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-size: 12px; color: #64748b; font-weight: 500; margin-bottom: 4px;">
                    VIEWING RESULTS FROM
                </div>
                <div style="font-size: 18px; font-weight: 700; color: #3b82f6;">
                    🎯 HEURISTIC PLANNING
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 12px; color: #64748b; font-weight: 500; margin-bottom: 4px;">
                    METHOD
                </div>
                <div style="font-size: 16px; font-weight: 600; color: #1e293b;">
                    Rule-Based
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Helper function to get current results based on selected source
def get_current_results():
    """Get results based on currently selected source."""
    if st.session_state.result_source == 'optimization':
        opt_results = session_state.get_optimization_results()

        # Get inventory snapshot date from session state
        inventory_snapshot_date = st.session_state.get('inventory_snapshot_date')

        adapted_results = adapt_optimization_results(
            model=opt_results['model'],
            result=opt_results['result'],
            inventory_snapshot_date=inventory_snapshot_date
        )
        if adapted_results is None:
            st.error("❌ Optimization results are not available. The model may not have been solved yet.")
            st.stop()
        return adapted_results
    else:
        return session_state.get_planning_results()

st.divider()

# Create tabs for different result views
tab_overview, tab_production, tab_labeling, tab_distribution, tab_costs, tab_comparison, tab_snapshot = st.tabs([
    "📊 Overview",
    "📦 Production",
    "🏷️ Labeling",
    "🚚 Distribution",
    "💰 Costs",
    "⚖️ Comparison",
    "📸 Daily Snapshot"
])


# ===========================
# TAB 0: OVERVIEW
# ===========================

with tab_overview:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">📊 Results Overview</div>
        <div>Key performance indicators, solver diagnostics, and demand satisfaction metrics.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get current results
    results = get_current_results()
    production_schedule = results['production_schedule']
    shipments = results.get('shipments', [])
    cost_breakdown = results.get('cost_breakdown')

    # Show solver diagnostics if optimization results
    if st.session_state.result_source == 'optimization':
        st.markdown(section_header("Solver Diagnostics", level=3, icon="⚙️"), unsafe_allow_html=True)

        opt_results = session_state.get_optimization_results()
        result_info = opt_results.get('result', {})

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            solver_status = getattr(result_info, 'termination_condition', 'UNKNOWN')
            if solver_status in ['optimal', 'OPTIMAL']:
                st.markdown(success_badge("OPTIMAL"), unsafe_allow_html=True)
            elif solver_status in ['feasible', 'FEASIBLE']:
                st.markdown(warning_badge("FEASIBLE"), unsafe_allow_html=True)
            else:
                st.markdown(error_badge("INFEASIBLE"), unsafe_allow_html=True)
            st.caption("**Solver Status**")

        with col2:
            gap = getattr(result_info, 'gap', 0)
            gap_pct = gap * 100 if gap is not None and not math.isinf(gap) and not math.isnan(gap) else 0
            st.markdown(colored_metric("Gap", f"{gap_pct:.2f}%", "secondary"), unsafe_allow_html=True)

        with col3:
            solve_time = getattr(result_info, 'solve_time_seconds', 0)
            st.markdown(colored_metric("Solve Time", f"{solve_time:.2f}s", "accent"), unsafe_allow_html=True)

        with col4:
            num_vars = getattr(result_info, 'num_variables', 0)
            st.markdown(colored_metric("Variables", f"{num_vars:,}", "primary"), unsafe_allow_html=True)

        with col5:
            num_constraints = getattr(result_info, 'num_constraints', 0)
            st.markdown(colored_metric("Constraints", f"{num_constraints:,}", "primary"), unsafe_allow_html=True)

        st.divider()

    # Key Performance Indicators
    st.markdown(section_header("Key Performance Indicators", level=3, icon="📈"), unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if cost_breakdown:
            st.markdown(colored_metric("Total Cost", f"${cost_breakdown.total_cost:,.2f}", "primary"), unsafe_allow_html=True)
            total_units = sum(s.quantity for s in shipments) if shipments else production_schedule.total_units
            cost_per_unit = cost_breakdown.total_cost / total_units if total_units > 0 else 0
            st.markdown(colored_metric("Cost/Unit", f"${cost_per_unit:.2f}", "primary"), unsafe_allow_html=True)

    with col2:
        st.markdown(colored_metric("Production Days", str(len(production_schedule.daily_totals)), "secondary"), unsafe_allow_html=True)
        st.markdown(colored_metric("Total Units", f"{production_schedule.total_units:,.0f}", "secondary"), unsafe_allow_html=True)

    with col3:
        st.markdown(colored_metric("Labor Hours", f"{production_schedule.total_labor_hours:.1f}h", "accent"), unsafe_allow_html=True)
        avg_daily_hours = production_schedule.total_labor_hours / len(production_schedule.daily_totals) if production_schedule.daily_totals else 0
        st.markdown(colored_metric("Avg Daily Hours", f"{avg_daily_hours:.1f}h", "accent"), unsafe_allow_html=True)

    with col4:
        if shipments:
            destinations = set(s.destination_id for s in shipments)
            st.markdown(colored_metric("Destinations", str(len(destinations)), "success"), unsafe_allow_html=True)
            st.markdown(colored_metric("Shipments", str(len(shipments)), "success"), unsafe_allow_html=True)

    st.divider()

    # Demand Satisfaction (if optimization results with demand info)
    if st.session_state.result_source == 'optimization':
        st.markdown(section_header("Demand Satisfaction", level=3, icon="✅"), unsafe_allow_html=True)

        opt_results = session_state.get_optimization_results()
        model = opt_results.get('model')
        solution = model.get_solution() if model else None

        if solution and 'shortages_by_dest_product_date' in solution:
            total_shortage = solution.get('total_shortage_units', 0)
            shortage_cost = solution.get('total_shortage_cost', 0)

            # Calculate total demand (would need to get from model.demand)
            # For now, show shortage metrics
            col1, col2, col3 = st.columns(3)

            with col1:
                if total_shortage == 0:
                    st.markdown(colored_metric("Fulfillment", "100%", "success"), unsafe_allow_html=True)
                else:
                    # Calculate fulfillment percentage if we have demand info
                    st.markdown(colored_metric("Shortage Units", f"{total_shortage:,.0f}", "warning"), unsafe_allow_html=True)

            with col2:
                st.markdown(colored_metric("Shortage Cost", f"${shortage_cost:,.2f}", "warning"), unsafe_allow_html=True)

            with col3:
                if total_shortage == 0:
                    st.markdown(success_badge("All Demand Met"), unsafe_allow_html=True)
                else:
                    st.markdown(warning_badge("Partial Shortage"), unsafe_allow_html=True)

            # Show shortage details if any
            if total_shortage > 0:
                with st.expander("⚠️ Shortage Details", expanded=False):
                    shortages = solution.get('shortages_by_dest_product_date', {})
                    shortage_data = []
                    for (dest, product, date), qty in shortages.items():
                        if qty > 0:
                            shortage_data.append({
                                'Destination': dest,
                                'Product': product,
                                'Date': date,
                                'Shortage': qty
                            })

                    if shortage_data:
                        df_shortages = pd.DataFrame(shortage_data)
                        st.dataframe(df_shortages, use_container_width=True, hide_index=True)
                    else:
                        st.info("No shortages detected.")
        else:
            st.info("✅ All demand satisfied (no shortage data tracked)")

        st.divider()

    # Cost Breakdown Summary
    if cost_breakdown:
        st.markdown(section_header("Cost Breakdown", level=3, icon="💰"), unsafe_allow_html=True)

        col1, col2 = st.columns([2, 1])

        with col1:
            # Cost breakdown chart
            fig = render_cost_breakdown_chart(cost_breakdown)
            st.plotly_chart(fig, use_container_width=True, key="overview_cost_breakdown")

        with col2:
            st.markdown("#### Cost Components")

            # Labor
            labor_pct = (cost_breakdown.labor.total_cost / cost_breakdown.total_cost * 100) if cost_breakdown.total_cost > 0 else 0
            st.markdown(f"""
            <div style="padding: 8px; margin-bottom: 8px; border-left: 3px solid #3b82f6; background: #3b82f610;">
                <div style="font-size: 12px; color: #64748b;">LABOR</div>
                <div style="font-size: 18px; font-weight: 600;">${cost_breakdown.labor.total_cost:,.2f}</div>
                <div style="font-size: 12px; color: #64748b;">{labor_pct:.1f}% of total</div>
            </div>
            """, unsafe_allow_html=True)

            # Production
            prod_pct = (cost_breakdown.production.total_cost / cost_breakdown.total_cost * 100) if cost_breakdown.total_cost > 0 else 0
            st.markdown(f"""
            <div style="padding: 8px; margin-bottom: 8px; border-left: 3px solid #10b981; background: #10b98110;">
                <div style="font-size: 12px; color: #64748b;">PRODUCTION</div>
                <div style="font-size: 18px; font-weight: 600;">${cost_breakdown.production.total_cost:,.2f}</div>
                <div style="font-size: 12px; color: #64748b;">{prod_pct:.1f}% of total</div>
            </div>
            """, unsafe_allow_html=True)

            # Transport
            transport_pct = (cost_breakdown.transport.total_cost / cost_breakdown.total_cost * 100) if cost_breakdown.total_cost > 0 else 0
            st.markdown(f"""
            <div style="padding: 8px; margin-bottom: 8px; border-left: 3px solid #f59e0b; background: #f59e0b10;">
                <div style="font-size: 12px; color: #64748b;">TRANSPORT</div>
                <div style="font-size: 18px; font-weight: 600;">${cost_breakdown.transport.total_cost:,.2f}</div>
                <div style="font-size: 12px; color: #64748b;">{transport_pct:.1f}% of total</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Quick Insights
    st.markdown(section_header("Quick Insights", level=3, icon="💡"), unsafe_allow_html=True)

    insights = []

    # Production insights
    if production_schedule.daily_labor_hours:
        # Find day with maximum labor hours (handle both dict and numeric formats)
        max_hours_day = max(
            production_schedule.daily_labor_hours.items(),
            key=lambda x: extract_labor_hours(x[1], 0)
        )
        max_hours_value = extract_labor_hours(max_hours_day[1], 0)
        insights.append(f"📅 **Peak production day:** {max_hours_day[0]} with {max_hours_value:.1f} labor hours")

    # Cost insights
    if cost_breakdown:
        dominant_cost = max(
            [('Labor', cost_breakdown.labor.total_cost),
             ('Production', cost_breakdown.production.total_cost),
             ('Transport', cost_breakdown.transport.total_cost)],
            key=lambda x: x[1]
        )
        insights.append(f"💰 **Largest cost driver:** {dominant_cost[0]} (${dominant_cost[1]:,.2f})")

    # Shipment insights
    if shipments:
        avg_shipment_size = sum(s.quantity for s in shipments) / len(shipments)
        insights.append(f"📦 **Average shipment size:** {avg_shipment_size:,.0f} units")

    # Optimization insights
    if st.session_state.result_source == 'optimization' and has_heuristic:
        heuristic_results = session_state.get_planning_results()
        heuristic_cost = heuristic_results['cost_breakdown'].total_cost
        opt_cost = cost_breakdown.total_cost if cost_breakdown else 0
        if heuristic_cost > 0 and opt_cost > 0:
            savings = heuristic_cost - opt_cost
            savings_pct = (savings / heuristic_cost * 100)
            if savings > 0:
                insights.append(f"⚡ **Optimization savings:** ${savings:,.2f} ({savings_pct:.1f}%) vs heuristic")
            elif savings < 0:
                insights.append(f"⚠️ **Heuristic advantage:** ${abs(savings):,.2f} ({abs(savings_pct):.1f}%) lower cost")

    # Display insights
    for insight in insights:
        st.markdown(f"- {insight}")

    if not insights:
        st.info("No insights available yet.")


# ===========================
# TAB 1: PRODUCTION SCHEDULE
# ===========================

with tab_production:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">📦 Production Schedule</div>
        <div>View production batches, labor hours, capacity utilization, and daily breakdowns.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get current results (heuristic or optimization based on selection)
    results = get_current_results()
    production_schedule = results['production_schedule']

    # Date Range Filter
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
        from src.models.production_schedule import ProductionSchedule
        filtered_schedule = ProductionSchedule(
            manufacturing_site_id=production_schedule.manufacturing_site_id,
            schedule_start_date=production_schedule.schedule_start_date,
            schedule_end_date=production_schedule.schedule_end_date,
            production_batches=filtered_batches,
            daily_totals=filtered_daily_totals,
            daily_labor_hours=filtered_daily_labor_hours,
            infeasibilities=production_schedule.infeasibilities,
            total_units=sum(b.quantity for b in filtered_batches),
            total_labor_hours=sum(extract_labor_hours(hrs, 0) for hrs in filtered_daily_labor_hours.values()),
        )
    else:
        # No batches, use original schedule
        filtered_schedule = production_schedule

    st.divider()

    # Summary metrics
    st.markdown(section_header("Schedule Summary", level=3, icon="📊"), unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(colored_metric("Production Batches", str(len(filtered_schedule.production_batches)), "primary"), unsafe_allow_html=True)
        st.markdown(colored_metric("Total Units", f"{filtered_schedule.total_units:,.0f}", "primary"), unsafe_allow_html=True)

    with col2:
        st.markdown(colored_metric("Total Labor Hours", f"{filtered_schedule.total_labor_hours:.1f}h", "secondary"), unsafe_allow_html=True)
        avg_daily_hours = filtered_schedule.total_labor_hours / len(filtered_schedule.daily_totals) if filtered_schedule.daily_totals else 0
        st.markdown(colored_metric("Avg Daily Hours", f"{avg_daily_hours:.1f}h", "secondary"), unsafe_allow_html=True)

    with col3:
        st.markdown(colored_metric("Production Days", str(len(filtered_schedule.daily_totals)), "accent"), unsafe_allow_html=True)
        # Show filtered date range
        if filtered_schedule.production_batches:
            filtered_dates = [b.production_date for b in filtered_schedule.production_batches]
            date_range = f"{min(filtered_dates)} to {max(filtered_dates)}"
        else:
            date_range = "No production"
        st.caption(f"**Date Range:** {date_range}")

    with col4:
        if production_schedule.is_feasible():
            st.markdown(success_badge("Feasible"), unsafe_allow_html=True)
        else:
            st.markdown(error_badge(f"{len(production_schedule.infeasibilities)} Issues"), unsafe_allow_html=True)

        # Show filtered vs total
        if len(filtered_schedule.production_batches) < len(production_schedule.production_batches):
            st.caption(f"**Filtered:** {len(filtered_schedule.production_batches)} / {len(production_schedule.production_batches)} batches")

    # Show infeasibilities if any
    if not production_schedule.is_feasible():
        st.divider()
        with st.expander("⚠️ Production Schedule Infeasibilities", expanded=False):
            for infeas in production_schedule.infeasibilities:
                st.warning(f"- {infeas}")

    st.divider()

    # Visualizations
    viz_tab1, viz_tab2, viz_tab3 = st.tabs(["📊 Charts", "📅 Gantt", "📋 Tables"])

    with viz_tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(section_header("Daily Production", level=4), unsafe_allow_html=True)
            fig = render_daily_production_chart(filtered_schedule)
            st.plotly_chart(fig, use_container_width=True, key="production_daily_production")

        with col2:
            st.markdown(section_header("Labor Hours", level=4), unsafe_allow_html=True)
            fig = render_labor_hours_chart(filtered_schedule)
            st.plotly_chart(fig, use_container_width=True, key="production_labor_hours")

        st.markdown(section_header("Capacity Utilization", level=4), unsafe_allow_html=True)
        fig = render_capacity_utilization_chart(filtered_schedule)
        st.plotly_chart(fig, use_container_width=True, key="production_capacity_utilization")

    with viz_tab2:
        st.markdown(section_header("Production Gantt Chart", level=4), unsafe_allow_html=True)
        fig = render_production_gantt(filtered_schedule)
        st.plotly_chart(fig, use_container_width=True, key="production_gantt")

    with viz_tab3:
        st.markdown(section_header("Production Batches", level=4), unsafe_allow_html=True)
        render_production_batches_table(filtered_schedule)

        st.divider()

        st.markdown(section_header("Daily Breakdown", level=4), unsafe_allow_html=True)
        render_daily_breakdown_table(filtered_schedule)


# ===========================
# TAB 2: PRODUCTION LABELING
# ===========================

with tab_labeling:
    # Check if optimization results are available
    if st.session_state.result_source != 'optimization':
        st.warning("""
        **Production labeling requirements are only available for optimization results.**

        The labeling report analyzes optimization routing decisions to determine which
        quantities need frozen vs. ambient labels based on their destination routes.
        """)

        st.info("Switch to **Optimization** results or run optimization to view labeling requirements.")

        if st.button("⚡ Run Optimization", type="primary", use_container_width=True):
            st.switch_page("pages/2_Planning.py")
    else:
        # Get optimization model and results
        opt_results = session_state.get_optimization_results()
        model = opt_results.get('model')

        if not model:
            st.error("❌ Optimization model not available")
        else:
            # Get solution
            solution = model.get_solution() if hasattr(model, 'get_solution') else None

            if not solution:
                st.error("❌ Optimization solution not available")
            else:
                # Render the production labeling view
                render_production_labeling_view(model, solution)


# ===========================
# TAB 3: DISTRIBUTION PLAN
# ===========================

with tab_distribution:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">🚚 Distribution Plan</div>
        <div>View truck loading schedules, shipments by destination, and utilization.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get current results (heuristic or optimization based on selection)
    results = get_current_results()
    truck_plan = results.get('truck_plan')
    shipments = results.get('shipments', [])

    # Check if we have any distribution data to show
    has_shipments = shipments and len(shipments) > 0
    has_truck_loads = truck_plan and len(truck_plan.loads) > 0

    if not has_shipments:
        st.warning("📦 No distribution plan available - no shipments found in solution")
    else:
        # We have shipments - show distribution data
        # Display informational message if truck assignments are missing
        if not has_truck_loads:
            st.info("📦 **Shipment data available.** Truck assignments not available - model may have been solved without truck schedules or routes don't align with truck destinations.")

        # Summary metrics
        st.markdown(section_header("Distribution Summary", level=3, icon="📊"), unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(colored_metric("Shipments", str(len(shipments)), "primary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Total Units", f"{sum(s.quantity for s in shipments):,.0f}", "primary"), unsafe_allow_html=True)

        with col2:
            trucks_used = len(truck_plan.loads) if truck_plan else 0
            st.markdown(colored_metric("Trucks Used", str(trucks_used), "secondary"), unsafe_allow_html=True)
            avg_load = sum(tl.total_units for tl in truck_plan.loads) / len(truck_plan.loads) if has_truck_loads else 0
            st.markdown(colored_metric("Avg Load", f"{avg_load:,.0f} units", "secondary"), unsafe_allow_html=True)

        with col3:
            destinations = set(s.destination_id for s in shipments)
            st.markdown(colored_metric("Destinations", str(len(destinations)), "accent"), unsafe_allow_html=True)

            # Show unassigned shipment count if relevant
            if truck_plan and len(truck_plan.unassigned_shipments) > 0:
                st.markdown(colored_metric("Unassigned", str(len(truck_plan.unassigned_shipments)), "accent"), unsafe_allow_html=True)

        with col4:
            if truck_plan and truck_plan.is_feasible():
                st.markdown(success_badge("Feasible"), unsafe_allow_html=True)
            elif truck_plan and not truck_plan.is_feasible():
                st.markdown(error_badge(f"{len(truck_plan.infeasibilities)} Issues"), unsafe_allow_html=True)
            else:
                st.markdown(warning_badge("No Truck Data"), unsafe_allow_html=True)

        # Show infeasibilities if any
        if truck_plan and not truck_plan.is_feasible():
            st.divider()
            with st.expander("⚠️ Truck Loading Infeasibilities", expanded=False):
                for infeas in truck_plan.infeasibilities:
                    st.warning(f"- {infeas}")

        st.divider()

        # Visualizations
        dist_tab1, dist_tab2 = st.tabs(["📊 Charts", "📋 Tables"])

        with dist_tab1:
            if has_truck_loads:
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown(section_header("Shipments by Destination", level=4), unsafe_allow_html=True)
                    fig = render_shipments_by_destination_chart(truck_plan)
                    st.plotly_chart(fig, use_container_width=True, key="distribution_shipments_by_dest")

                with col2:
                    st.markdown(section_header("Truck Utilization", level=4), unsafe_allow_html=True)
                    fig = render_truck_utilization_chart(truck_plan)
                    st.plotly_chart(fig, use_container_width=True, key="distribution_truck_utilization")

                st.markdown(section_header("Truck Loading Timeline", level=4), unsafe_allow_html=True)
                fig = render_truck_loading_timeline(truck_plan)
                st.plotly_chart(fig, use_container_width=True, key="distribution_truck_timeline")
            else:
                st.info("📊 Truck loading charts not available - no truck assignments in solution. View shipments in the **Tables** tab below.")

        with dist_tab2:
            st.markdown(section_header("Shipments", level=4), unsafe_allow_html=True)
            render_shipments_table(shipments)

            st.divider()

            st.markdown(section_header("Truck Loadings", level=4), unsafe_allow_html=True)
            if has_truck_loads:
                render_truck_loads_table(truck_plan)
            else:
                st.info("ℹ️ No truck loading data available. Shipments may not be assigned to specific trucks.")


# ===========================
# TAB 4: COST ANALYSIS
# ===========================

with tab_costs:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">💰 Cost Analysis</div>
        <div>View cost breakdown by category, daily costs, and detailed cost components.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get current results (heuristic or optimization based on selection)
    results = get_current_results()
    cost_breakdown = results.get('cost_breakdown')

    if not cost_breakdown:
        st.warning("No cost analysis available")
    else:
        # Summary metrics
        st.markdown(section_header("Cost Summary", level=3, icon="📊"), unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(colored_metric("Total Cost", f"${cost_breakdown.total_cost:,.2f}", "primary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Production", f"${cost_breakdown.production.total_cost:,.2f}", "primary"), unsafe_allow_html=True)

        with col2:
            st.markdown(colored_metric("Labor", f"${cost_breakdown.labor.total_cost:,.2f}", "secondary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Transport", f"${cost_breakdown.transport.total_cost:,.2f}", "secondary"), unsafe_allow_html=True)

        with col3:
            total_units = sum(s.quantity for s in results.get('shipments', []))
            cost_per_unit = cost_breakdown.total_cost / total_units if total_units > 0 else 0
            st.markdown(colored_metric("Cost/Unit", f"${cost_per_unit:.2f}", "accent"), unsafe_allow_html=True)
            st.markdown(colored_metric("Waste", f"${cost_breakdown.waste.total_cost:,.2f}", "accent"), unsafe_allow_html=True)

        with col4:
            # Cost breakdown percentages
            if cost_breakdown.total_cost > 0:
                labor_pct = (cost_breakdown.labor.total_cost / cost_breakdown.total_cost) * 100
                st.caption(f"**Labor:** {labor_pct:.1f}%")
                prod_pct = (cost_breakdown.production.total_cost / cost_breakdown.total_cost) * 100
                st.caption(f"**Production:** {prod_pct:.1f}%")

        st.divider()

        # Visualizations
        cost_tab1, cost_tab2 = st.tabs(["📊 Charts", "📋 Tables"])

        with cost_tab1:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(section_header("Cost Breakdown", level=4), unsafe_allow_html=True)
                fig = render_cost_breakdown_chart(cost_breakdown)
                st.plotly_chart(fig, use_container_width=True, key="costs_cost_breakdown")

            with col2:
                st.markdown(section_header("Cost by Category", level=4), unsafe_allow_html=True)
                fig = render_cost_by_category_chart(cost_breakdown)
                st.plotly_chart(fig, use_container_width=True, key="costs_cost_by_category")

            st.markdown(section_header("Daily Costs", level=4), unsafe_allow_html=True)
            fig = render_daily_cost_chart(cost_breakdown)
            st.plotly_chart(fig, use_container_width=True, key="costs_daily_costs")

        with cost_tab2:
            st.markdown(section_header("Cost Details", level=4), unsafe_allow_html=True)
            render_cost_breakdown_table(cost_breakdown)


# ===========================
# TAB 5: RESULTS COMPARISON
# ===========================

with tab_comparison:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">⚖️ Results Comparison</div>
        <div>Compare heuristic planning results with mathematical optimization.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Check if both heuristic and optimization results are available
    has_heuristic = session_state.is_planning_complete()
    has_optimization = session_state.is_optimization_complete()

    if not has_heuristic and not has_optimization:
        st.info("No results available for comparison. Run planning first.")
    elif not has_optimization:
        st.info("Only heuristic results available. Run **Optimization** to enable comparison.")
        if st.button("⚡ Go to Optimization", type="primary", use_container_width=True):
            st.switch_page("pages/2_Planning.py")
    elif not has_heuristic:
        st.info("Only optimization results available. Run **Heuristic Planning** to enable comparison.")
        if st.button("🎯 Go to Heuristic Planning", type="primary", use_container_width=True):
            st.switch_page("pages/2_Planning.py")
    else:
        # Both available - show comparison
        st.markdown(section_header("Heuristic vs. Optimization", level=3, icon="⚖️"), unsafe_allow_html=True)

        heuristic_results = session_state.get_planning_results()
        opt_results = session_state.get_optimization_results()

        # Get key metrics
        heuristic_cost = heuristic_results['cost_breakdown'].total_cost
        # Use properly calculated total_cost from model solution, not raw solver objective_value
        model_solution = opt_results['model'].get_solution()
        opt_cost = model_solution.get('total_cost', 0) if model_solution else 0

        # Validate opt_cost is finite
        if opt_cost is None or math.isinf(opt_cost) or math.isnan(opt_cost):
            st.error("⚠️ Optimization cost is invalid (infinity or NaN). Cannot compare results. Check cost parameters.")
            opt_cost = 0  # Use 0 as fallback to prevent calculation errors
            cost_savings = 0
            cost_savings_pct = 0
        else:
            cost_savings = heuristic_cost - opt_cost
            cost_savings_pct = (cost_savings / heuristic_cost * 100) if heuristic_cost > 0 else 0

        # High-level comparison
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(section_header("Heuristic", level=4), unsafe_allow_html=True)
            st.markdown(colored_metric("Total Cost", f"${heuristic_cost:,.2f}", "secondary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Production Batches", str(len(heuristic_results['production_schedule'].production_batches)), "secondary"), unsafe_allow_html=True)

        with col2:
            st.markdown(section_header("Optimization", level=4), unsafe_allow_html=True)
            st.markdown(colored_metric("Total Cost", f"${opt_cost:,.2f}", "success"), unsafe_allow_html=True)

            # Use model_solution already obtained above
            if model_solution:
                production_days = len(set(
                    batch['date'] for batch in model_solution.get('production_batches', [])
                )) if 'production_batches' in model_solution else 0
                total_production = sum(
                    batch['quantity'] for batch in model_solution.get('production_batches', [])
                ) if 'production_batches' in model_solution else 0

                # Extract cost components
                opt_production_cost = model_solution.get('total_production_cost', 0)
                opt_labor_cost = model_solution.get('total_labor_cost', 0)
                opt_transport_cost = model_solution.get('total_transport_cost', 0)
                opt_truck_cost = model_solution.get('total_truck_cost', 0)
            else:
                production_days = 0
                total_production = 0
                opt_production_cost = 0
                opt_labor_cost = 0
                opt_transport_cost = 0
                opt_truck_cost = 0

            st.markdown(colored_metric("Production Days", str(production_days), "success"), unsafe_allow_html=True)

        with col3:
            st.markdown(section_header("Savings", level=4), unsafe_allow_html=True)
            delta_color = "success" if cost_savings > 0 else "warning"
            st.markdown(colored_metric("Cost Savings", f"${cost_savings:,.2f}", delta_color), unsafe_allow_html=True)
            st.markdown(colored_metric("Improvement", f"{cost_savings_pct:.1f}%", delta_color), unsafe_allow_html=True)

        st.divider()

        # Detailed comparison table
        st.markdown(section_header("Detailed Comparison", level=4), unsafe_allow_html=True)

        comparison_data = {
            'Metric': [
                'Total Cost',
                'Production Cost',
                'Labor Cost',
                'Transport Cost',
                'Production Days',
                'Total Units',
                'Cost per Unit'
            ],
            'Heuristic': [
                f"${heuristic_cost:,.2f}",
                f"${heuristic_results['cost_breakdown'].production.total_cost:,.2f}",
                f"${heuristic_results['cost_breakdown'].labor.total_cost:,.2f}",
                f"${heuristic_results['cost_breakdown'].transport.total_cost:,.2f}",
                str(len(heuristic_results['production_schedule'].daily_totals)),
                f"{heuristic_results['production_schedule'].total_units:,.0f}",
                f"${heuristic_cost / heuristic_results['production_schedule'].total_units:.2f}" if heuristic_results['production_schedule'].total_units > 0 else "N/A"
            ],
            'Optimization': [
                f"${opt_cost:,.2f}",
                f"${opt_production_cost:,.2f}",
                f"${opt_labor_cost:,.2f}",
                f"${opt_transport_cost:,.2f}",
                str(production_days),
                f"{total_production:,.0f}",
                f"${opt_cost / total_production:.2f}" if total_production > 0 else "N/A"
            ]
        }

        df_comparison = pd.DataFrame(comparison_data)
        st.dataframe(df_comparison, use_container_width=True, hide_index=True)

        st.divider()

        # Insights
        st.markdown(section_header("Insights", level=4, icon="💡"), unsafe_allow_html=True)

        if cost_savings > 0:
            st.success(f"✅ Optimization achieves **${cost_savings:,.2f}** ({cost_savings_pct:.1f}%) cost savings compared to heuristic planning.")
        elif cost_savings < 0:
            st.warning(f"⚠️ Heuristic performs better by **${abs(cost_savings):,.2f}** ({abs(cost_savings_pct):.1f}%). This may indicate optimization model limitations.")
        else:
            st.info("Both methods achieve the same total cost.")

        # Additional insights
        with st.expander("📊 Additional Analysis", expanded=False):
            st.markdown("""
            **Heuristic Planning:**
            - Fast execution (< 1 second)
            - Rule-based logic
            - May not find optimal solution
            - Easy to understand and debug

            **Mathematical Optimization:**
            - Provably optimal (or near-optimal)
            - Considers all constraints simultaneously
            - Longer solve time
            - More complex to configure
            """)


# ===========================
# TAB 6: DAILY SNAPSHOT
# ===========================

with tab_snapshot:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">📸 Daily Inventory Snapshot</div>
        <div>Interactive daily view of inventory at locations, in-transit shipments, manufacturing activity, and demand satisfaction.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get current results (heuristic or optimization based on selection)
    results = get_current_results()

    # Convert locations list to dict {location_id: Location}
    locations_list = st.session_state.get('locations', [])
    locations_dict = {loc.location_id: loc for loc in locations_list} if locations_list else {}

    # Add virtual 6122_Storage location if using optimization results
    # The optimization model uses 6122_Storage as a virtual inventory location
    # that receives production and supplies trucks
    if st.session_state.result_source == 'optimization' and locations_dict:
        from src.models.location import Location, LocationType, StorageMode

        # Find the manufacturing site (6122)
        manufacturing_site = st.session_state.get('manufacturing_site')
        if manufacturing_site:
            # Create virtual 6122_Storage location that mirrors manufacturing site
            virtual_storage = Location(
                id="6122_Storage",
                name="Manufacturing Storage (Virtual)",
                type=LocationType.STORAGE,
                storage_mode=StorageMode.BOTH,  # Supports both frozen and ambient
                capacity=None,  # No capacity limit for virtual location
                latitude=manufacturing_site.latitude if hasattr(manufacturing_site, 'latitude') else None,
                longitude=manufacturing_site.longitude if hasattr(manufacturing_site, 'longitude') else None,
            )
            # Add to locations_dict
            locations_dict["6122_Storage"] = virtual_storage

    # Render the daily snapshot component
    if results and locations_dict:
        render_daily_snapshot(results, locations_dict, key_prefix="results_snapshot")
    else:
        st.warning("⚠️ Unable to display daily snapshot. Missing results or location data.")
        if not results:
            st.info("No planning results available. Run planning first.")
        if not locations_dict:
            st.info("No location data available. Upload data in the Upload page first.")
