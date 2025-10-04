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
)

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

# Create tabs for different result views
tab_production, tab_distribution, tab_costs, tab_comparison = st.tabs([
    "📦 Production",
    "🚚 Distribution",
    "💰 Costs",
    "⚖️ Comparison"
])


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

    # Get planning results
    results = session_state.get_planning_results()
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
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown(section_header("Labor Hours", level=4), unsafe_allow_html=True)
            fig = render_labor_hours_chart(filtered_schedule)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown(section_header("Capacity Utilization", level=4), unsafe_allow_html=True)
        fig = render_capacity_utilization_chart(filtered_schedule)
        st.plotly_chart(fig, use_container_width=True)

    with viz_tab2:
        st.markdown(section_header("Production Gantt Chart", level=4), unsafe_allow_html=True)
        fig = render_production_gantt(filtered_schedule)
        st.plotly_chart(fig, use_container_width=True)

    with viz_tab3:
        st.markdown(section_header("Production Batches", level=4), unsafe_allow_html=True)
        render_production_batches_table(filtered_schedule)

        st.divider()

        st.markdown(section_header("Daily Breakdown", level=4), unsafe_allow_html=True)
        render_daily_breakdown_table(filtered_schedule)


# ===========================
# TAB 2: DISTRIBUTION PLAN
# ===========================

with tab_distribution:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">🚚 Distribution Plan</div>
        <div>View truck loading schedules, shipments by destination, and utilization.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get planning results
    results = session_state.get_planning_results()
    truck_plan = results.get('truck_plan')
    shipments = results.get('shipments', [])

    if not truck_plan or not shipments:
        st.warning("No distribution plan available")
    else:
        # Summary metrics
        st.markdown(section_header("Distribution Summary", level=3, icon="📊"), unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown(colored_metric("Shipments", str(len(shipments)), "primary"), unsafe_allow_html=True)
            st.markdown(colored_metric("Total Units", f"{sum(s.quantity for s in shipments):,.0f}", "primary"), unsafe_allow_html=True)

        with col2:
            st.markdown(colored_metric("Trucks Used", str(len(truck_plan.loads)), "secondary"), unsafe_allow_html=True)
            avg_load = sum(tl.total_units for tl in truck_plan.loads) / len(truck_plan.loads) if truck_plan.loads else 0
            st.markdown(colored_metric("Avg Load", f"{avg_load:,.0f} units", "secondary"), unsafe_allow_html=True)

        with col3:
            destinations = set(s.destination_id for s in shipments)
            st.markdown(colored_metric("Destinations", str(len(destinations)), "accent"), unsafe_allow_html=True)

        with col4:
            if truck_plan.is_feasible():
                st.markdown(success_badge("Feasible"), unsafe_allow_html=True)
            else:
                st.markdown(error_badge(f"{len(truck_plan.infeasibilities)} Issues"), unsafe_allow_html=True)

        # Show infeasibilities if any
        if not truck_plan.is_feasible():
            st.divider()
            with st.expander("⚠️ Truck Loading Infeasibilities", expanded=False):
                for infeas in truck_plan.infeasibilities:
                    st.warning(f"- {infeas}")

        st.divider()

        # Visualizations
        dist_tab1, dist_tab2 = st.tabs(["📊 Charts", "📋 Tables"])

        with dist_tab1:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(section_header("Shipments by Destination", level=4), unsafe_allow_html=True)
                fig = render_shipments_by_destination_chart(truck_plan)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown(section_header("Truck Utilization", level=4), unsafe_allow_html=True)
                fig = render_truck_utilization_chart(truck_plan)
                st.plotly_chart(fig, use_container_width=True)

            st.markdown(section_header("Truck Loading Timeline", level=4), unsafe_allow_html=True)
            fig = render_truck_loading_timeline(truck_plan)
            st.plotly_chart(fig, use_container_width=True)

        with dist_tab2:
            st.markdown(section_header("Shipments", level=4), unsafe_allow_html=True)
            render_shipments_table(shipments)

            st.divider()

            st.markdown(section_header("Truck Loadings", level=4), unsafe_allow_html=True)
            render_truck_loads_table(truck_plan)


# ===========================
# TAB 3: COST ANALYSIS
# ===========================

with tab_costs:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">💰 Cost Analysis</div>
        <div>View cost breakdown by category, daily costs, and detailed cost components.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get planning results
    results = session_state.get_planning_results()
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
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown(section_header("Cost by Category", level=4), unsafe_allow_html=True)
                fig = render_cost_by_category_chart(cost_breakdown)
                st.plotly_chart(fig, use_container_width=True)

            st.markdown(section_header("Daily Costs", level=4), unsafe_allow_html=True)
            fig = render_daily_cost_chart(cost_breakdown)
            st.plotly_chart(fig, use_container_width=True)

        with cost_tab2:
            st.markdown(section_header("Cost Details", level=4), unsafe_allow_html=True)
            render_cost_breakdown_table(cost_breakdown)


# ===========================
# TAB 4: RESULTS COMPARISON
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
        opt_cost = opt_results['result'].get('objective_value', 0)

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
            opt_solution = opt_results['model'].get_solution_summary()
            st.markdown(colored_metric("Production Days", str(opt_solution.get('production_days', 0)), "success"), unsafe_allow_html=True)

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
                "N/A",  # Not readily available from optimization model
                "N/A",
                "N/A",
                str(opt_solution.get('production_days', 0)),
                f"{opt_solution.get('total_production', 0):,.0f}",
                f"${opt_cost / opt_solution.get('total_production', 1):.2f}" if opt_solution.get('total_production', 0) > 0 else "N/A"
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
