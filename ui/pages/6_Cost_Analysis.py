"""Cost analysis page."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from ui import session_state
from ui.components import (
    render_cost_pie_chart,
    render_cost_breakdown_chart,
    render_daily_cost_chart,
    render_labor_cost_breakdown,
    render_transport_cost_by_route,
    render_cost_waterfall,
    render_cost_summary_table,
    render_labor_breakdown_table,
)

# Page config
st.set_page_config(
    page_title="Cost Analysis",
    page_icon="💰",
    layout="wide",
)

# Initialize session state
session_state.initialize_session_state()

st.header("💰 Cost Analysis")

# Check if planning is complete
if not session_state.is_planning_complete():
    st.warning("⚠️ No cost data available. Please run the planning workflow first.")
    if st.button("Go to Planning Workflow", type="primary"):
        st.switch_page("pages/3_Planning_Workflow.py")
    st.stop()

# Get planning results
results = session_state.get_planning_results()
cost_breakdown = results['cost_breakdown']
production_schedule = results['production_schedule']

# Summary metrics
st.subheader("📊 Cost Summary")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Cost", f"${cost_breakdown.total_cost:,.2f}")
    st.metric("Cost Per Unit", f"${cost_breakdown.cost_per_unit_delivered:.2f}")

with col2:
    st.metric("Labor Cost", f"${cost_breakdown.labor.total_cost:,.2f}")
    labor_pct = (cost_breakdown.labor.total_cost / cost_breakdown.total_cost) * 100 if cost_breakdown.total_cost > 0 else 0
    st.caption(f"{labor_pct:.1f}% of total")

with col3:
    st.metric("Production Cost", f"${cost_breakdown.production.total_cost:,.2f}")
    production_pct = (cost_breakdown.production.total_cost / cost_breakdown.total_cost) * 100 if cost_breakdown.total_cost > 0 else 0
    st.caption(f"{production_pct:.1f}% of total")

with col4:
    st.metric("Transport Cost", f"${cost_breakdown.transport.total_cost:,.2f}")
    transport_pct = (cost_breakdown.transport.total_cost / cost_breakdown.total_cost) * 100 if cost_breakdown.total_cost > 0 else 0
    st.caption(f"{transport_pct:.1f}% of total")

# Waste cost (if any)
if cost_breakdown.waste.total_cost > 0:
    st.warning(f"⚠️ **Waste Cost:** ${cost_breakdown.waste.total_cost:,.2f} ({(cost_breakdown.waste.total_cost / cost_breakdown.total_cost) * 100:.1f}% of total)")

st.divider()

# Visualizations
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview",
    "👷 Labor Costs",
    "🏭 Production Costs",
    "🚚 Transport Costs",
    "📋 Detailed Tables"
])

with tab1:
    st.subheader("Cost Overview")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Cost Proportions**")
        fig = render_cost_pie_chart(cost_breakdown, height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Cost Components**")
        fig = render_cost_breakdown_chart(cost_breakdown, height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Waterfall chart
    st.markdown("**Cost Per Unit Breakdown**")
    fig = render_cost_waterfall(cost_breakdown, height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Shows how each cost component contributes to the total cost per unit delivered")

with tab2:
    st.subheader("Labor Cost Analysis")

    # Labor summary
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Fixed Hours", f"{cost_breakdown.labor.fixed_hours:.1f}h")
        st.metric("Fixed Cost", f"${cost_breakdown.labor.fixed_hours_cost:,.2f}")

    with col2:
        st.metric("Overtime Hours", f"{cost_breakdown.labor.overtime_hours:.1f}h")
        st.metric("Overtime Cost", f"${cost_breakdown.labor.overtime_cost:,.2f}")

    with col3:
        st.metric("Non-Fixed Hours", f"{cost_breakdown.labor.non_fixed_hours:.1f}h")
        st.metric("Non-Fixed Cost", f"${cost_breakdown.labor.non_fixed_labor_cost:,.2f}")

    st.divider()

    # Labor breakdown chart
    st.markdown("**Labor Cost Breakdown**")
    fig = render_labor_cost_breakdown(cost_breakdown, height=400)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Daily cost chart
    st.markdown("**Daily Labor Cost**")
    fig = render_daily_cost_chart(cost_breakdown, height=400)
    st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.subheader("Production Cost Analysis")

    # Production summary
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Units", f"{cost_breakdown.production.total_units_produced:,.0f}")
        st.metric("Total Cost", f"${cost_breakdown.production.total_cost:,.2f}")

    with col2:
        st.metric("Cost Per Unit", f"${cost_breakdown.production.average_cost_per_unit:.3f}")
        st.metric("Production Days", len(cost_breakdown.production.cost_by_date))

    with col3:
        st.metric("Production Batches", len(cost_breakdown.production.batch_details))
        if cost_breakdown.production.batch_details:
            products = set(b['product_id'] for b in cost_breakdown.production.batch_details)
            st.metric("Products", len(products))

    st.divider()

    # Production by product
    if cost_breakdown.production.cost_by_product:
        st.markdown("**Production Cost by Product**")

        # Sort by cost
        sorted_products = sorted(
            cost_breakdown.production.cost_by_product.items(),
            key=lambda x: x[1],
            reverse=True
        )

        fig = go.Figure(data=[
            go.Bar(
                x=[p[0] for p in sorted_products],
                y=[p[1] for p in sorted_products],
                marker=dict(color='#4ECDC4'),
                text=[f'${c:,.2f}' for _, c in sorted_products],
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Cost: $%{y:,.2f}<extra></extra>',
            )
        ])

        fig.update_layout(
            title='Production Cost by Product',
            title_x=0.5,
            xaxis_title='Product',
            yaxis_title='Cost ($)',
            height=400,
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("Transport Cost Analysis")

    # Transport summary
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Cost", f"${cost_breakdown.transport.total_cost:,.2f}")
        st.metric("Units Shipped", f"{cost_breakdown.transport.total_units_shipped:,.0f}")

    with col2:
        st.metric("Cost Per Unit", f"${cost_breakdown.transport.average_cost_per_unit:.3f}")
        st.metric("Total Shipments", len(cost_breakdown.transport.shipment_details))

    with col3:
        if cost_breakdown.transport.cost_by_route:
            st.metric("Unique Routes", len(cost_breakdown.transport.cost_by_route))

    st.divider()

    # Transport cost by route
    if cost_breakdown.transport.cost_by_route:
        st.markdown("**Transport Cost by Route**")
        fig = render_transport_cost_by_route(cost_breakdown, height=500)
        st.plotly_chart(fig, use_container_width=True)

    # Transport cost by leg
    if cost_breakdown.transport.cost_by_leg:
        st.divider()
        st.markdown("**Transport Cost by Route Leg**")

        # Sort by cost
        sorted_legs = sorted(
            cost_breakdown.transport.cost_by_leg.items(),
            key=lambda x: x[1],
            reverse=True
        )

        fig = go.Figure(data=[
            go.Bar(
                y=[leg[0] for leg in sorted_legs],
                x=[leg[1] for leg in sorted_legs],
                orientation='h',
                marker=dict(color='#95E1D3'),
                text=[f'${c:,.2f}' for _, c in sorted_legs],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Cost: $%{x:,.2f}<extra></extra>',
            )
        ])

        fig.update_layout(
            title='Transport Cost by Individual Route Leg',
            title_x=0.5,
            xaxis_title='Cost ($)',
            yaxis_title='Route Leg',
            height=400,
            showlegend=False,
        )

        st.plotly_chart(fig, use_container_width=True)

with tab5:
    st.subheader("Detailed Cost Tables")

    # Sub-tabs
    subtab1, subtab2, subtab3 = st.tabs(["Cost Summary", "Labor Breakdown", "Waste Details"])

    with subtab1:
        st.markdown("**Total Cost Breakdown**")
        render_cost_summary_table(cost_breakdown)

    with subtab2:
        st.markdown("**Labor Cost Breakdown**")
        render_labor_breakdown_table(cost_breakdown)

    with subtab3:
        st.markdown("**Waste Cost Details**")

        waste = cost_breakdown.waste

        if waste.total_cost > 0:
            col1, col2 = st.columns(2)

            with col1:
                st.metric("Expired Units", f"{waste.expired_units:,.0f}")
                st.metric("Expired Cost", f"${waste.expired_cost:,.2f}")

            with col2:
                st.metric("Unmet Demand Units", f"{waste.unmet_demand_units:,.0f}")
                st.metric("Unmet Demand Cost", f"${waste.unmet_demand_cost:,.2f}")

            # Waste by location
            if waste.waste_by_location:
                st.divider()
                st.markdown("**Waste by Location**")

                waste_data = [
                    {'Location': loc, 'Cost': f"${cost:,.2f}"}
                    for loc, cost in sorted(waste.waste_by_location.items(), key=lambda x: x[1], reverse=True)
                ]
                df = pd.DataFrame(waste_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No waste costs - all demand met with acceptable shelf life!")

    # Export option
    st.divider()
    if st.button("📥 Export to Excel", type="secondary"):
        st.info("Excel export functionality coming soon!")

# Footer with navigation
st.divider()
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Distribution Plan", use_container_width=True):
        st.switch_page("pages/5_Distribution_Plan.py")

with col2:
    if st.button("Network Analysis →", use_container_width=True):
        st.switch_page("pages/7_Network_Visualization.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
