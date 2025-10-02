"""Results Comparison page - side-by-side comparison of heuristic vs optimization.

This page enables users to compare the results from two planning approaches:
1. Heuristic Planning (rule-based, fast) - from pages/3_Planning_Workflow.py
2. Mathematical Optimization (optimal, slower) - from pages/10_Optimization.py

The comparison shows:
- Cost metrics with deltas and percentages
- Waterfall chart visualizing cost component differences
- Detailed breakdowns by production, demand satisfaction, labor, and performance
- Actionable insights highlighting savings and trade-offs

Required session state data:
- st.session_state.planning_complete: bool - Heuristic results available
- st.session_state.cost_breakdown: TotalCostBreakdown - Heuristic cost breakdown
- st.session_state.production_schedule: ProductionSchedule - Heuristic production schedule
- st.session_state.optimization_result: OptimizationResult - Optimization results
- st.session_state.optimization_model: Model - Optimization model with solution
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import timedelta
from typing import Optional, Dict, Any, Tuple

from ui import session_state
from ui.components.styling import (
    apply_custom_css,
    section_header,
    colored_metric,
    success_badge,
    error_badge,
    warning_badge,
    info_badge,
    info_box,
    status_badge,
)

# Page config
st.set_page_config(
    page_title="Results Comparison",
    page_icon="⚖️",
    layout="wide",
)

# Apply custom CSS
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()


# ========================================
#  Helper Functions
# ========================================

def format_currency(value: float) -> str:
    """Format value as currency with proper formatting."""
    if value is None or pd.isna(value):
        return "$0.00"
    return f"${value:,.2f}"


def format_number(value: float) -> str:
    """Format number with thousands separator."""
    if value is None or pd.isna(value):
        return "0"
    return f"{value:,.0f}"


def format_percentage(value: float) -> str:
    """Format value as percentage."""
    if value is None or pd.isna(value):
        return "0.0%"
    return f"{value:.1f}%"


def calculate_delta(heuristic_val: float, optimization_val: float) -> Tuple[float, float]:
    """Calculate delta between heuristic and optimization values.

    Returns:
        Tuple of (absolute_delta, percentage_delta)
        Negative delta means optimization is better (lower cost)
    """
    if heuristic_val is None or optimization_val is None:
        return 0.0, 0.0

    absolute_delta = optimization_val - heuristic_val

    if heuristic_val == 0:
        if optimization_val == 0:
            percentage_delta = 0.0
        else:
            percentage_delta = 100.0  # Arbitrary large value
    else:
        percentage_delta = (absolute_delta / abs(heuristic_val)) * 100

    return absolute_delta, percentage_delta


def color_delta(delta: float, inverse: bool = False) -> str:
    """Determine color for delta value.

    Args:
        delta: The delta value
        inverse: If True, positive deltas are bad (for costs). Default True.

    Returns:
        Color name: "success" or "error"
    """
    if not inverse:
        return "success" if delta >= 0 else "error"
    else:
        # For costs: negative delta is good (savings)
        return "success" if delta < 0 else "error"


def create_delta_display(delta_abs: float, delta_pct: float, inverse: bool = True) -> str:
    """Create formatted delta display with sign and percentage.

    Args:
        delta_abs: Absolute delta value
        delta_pct: Percentage delta value
        inverse: If True, negative is good (for costs)
    """
    sign = "+" if delta_abs >= 0 else ""

    if inverse:
        # For costs, show savings as positive
        if delta_abs < 0:
            return f"−${abs(delta_abs):,.2f} (−{abs(delta_pct):.1f}%)"
        else:
            return f"+${delta_abs:,.2f} (+{delta_pct:.1f}%)"
    else:
        return f"{sign}${delta_abs:,.2f} ({sign}{delta_pct:.1f}%)"


def get_heuristic_data() -> Optional[Dict[str, Any]]:
    """Extract heuristic planning results from session state."""
    if not session_state.is_planning_complete():
        return None

    summary = session_state.get_planning_summary()

    return {
        'total_cost': summary.get('total_cost', 0),
        'labor_cost': summary.get('labor_cost', 0),
        'production_cost': summary.get('production_cost', 0),
        'transport_cost': summary.get('transport_cost', 0),
        'waste_cost': summary.get('waste_cost', 0),
        'production_batches': summary.get('production_batches', 0),
        'total_units': summary.get('total_units', 0),
        'total_labor_hours': summary.get('total_labor_hours', 0),
        'demand_satisfaction_pct': 100.0,  # Heuristic aims for 100%
        'execution_time': None,  # Not tracked for heuristic
    }


def get_optimization_data() -> Optional[Dict[str, Any]]:
    """Extract optimization results from session state."""
    if 'optimization_result' not in st.session_state:
        return None

    result = st.session_state['optimization_result']

    if not result.is_feasible():
        return None

    model = st.session_state.get('optimization_model')
    solution = model.get_solution() if model else None

    if not solution:
        return None

    # Calculate demand satisfaction
    demand_total = sum(model.demand.values()) if model else 0
    shortage_total = solution.get('total_shortage_units', 0)
    satisfaction_pct = ((demand_total - shortage_total) / demand_total * 100) if demand_total > 0 else 0

    # Count production batches (days with production)
    production_batches = 0
    if solution.get('production_by_date_product'):
        production_dates = set()
        for (prod_date, product), qty in solution['production_by_date_product'].items():
            if qty > 0:
                production_dates.add(prod_date)
        production_batches = len(production_dates)

    # Calculate total units produced
    total_units = sum(solution['production_by_date_product'].values()) if solution.get('production_by_date_product') else 0

    return {
        'total_cost': result.objective_value,
        'labor_cost': solution['total_labor_cost'],
        'production_cost': solution['total_production_cost'],
        'transport_cost': solution['total_transport_cost'],
        'waste_cost': solution.get('total_shortage_cost', 0),  # Shortage penalty as "waste"
        'production_batches': production_batches,
        'total_units': total_units,
        'total_labor_hours': None,  # Not directly available from optimization
        'demand_satisfaction_pct': satisfaction_pct,
        'execution_time': result.solve_time_seconds,
    }


def create_waterfall_chart(heuristic_costs: Dict[str, float], optimization_costs: Dict[str, float]) -> go.Figure:
    """Create a waterfall chart showing cost component differences.

    Args:
        heuristic_costs: Dict with keys: labor_cost, production_cost, transport_cost, waste_cost
        optimization_costs: Dict with same keys as heuristic_costs

    Returns:
        Plotly Figure object
    """
    components = ['Labor', 'Production', 'Transport', 'Waste']
    cost_keys = ['labor_cost', 'production_cost', 'transport_cost', 'waste_cost']

    # Calculate deltas for each component
    deltas = {}
    for comp, key in zip(components, cost_keys):
        heur_val = heuristic_costs.get(key, 0)
        opt_val = optimization_costs.get(key, 0)
        deltas[comp] = opt_val - heur_val

    # Build waterfall data
    x_labels = ['Heuristic\nTotal'] + components + ['Optimization\nTotal']
    measures = ['absolute'] + ['relative'] * len(components) + ['total']

    # Values for waterfall
    values = [heuristic_costs.get('total_cost', 0)]
    text_labels = [format_currency(heuristic_costs.get('total_cost', 0))]

    for comp in components:
        delta = deltas[comp]
        values.append(delta)
        if delta < 0:
            text_labels.append(f"−${abs(delta):,.0f}")
        else:
            text_labels.append(f"+${delta:,.0f}")

    values.append(optimization_costs.get('total_cost', 0))
    text_labels.append(format_currency(optimization_costs.get('total_cost', 0)))

    # Colors: green for savings, red for increases
    colors = ['#1E88E5']  # Blue for starting total
    for comp in components:
        delta = deltas[comp]
        colors.append('#43A047' if delta < 0 else '#E53935')
    colors.append('#1E88E5')  # Blue for ending total

    fig = go.Figure(go.Waterfall(
        x=x_labels,
        y=values,
        measure=measures,
        text=text_labels,
        textposition='outside',
        connector={'line': {'color': '#757575', 'width': 2}},
        increasing={'marker': {'color': '#E53935'}},
        decreasing={'marker': {'color': '#43A047'}},
        totals={'marker': {'color': '#1E88E5'}},
    ))

    fig.update_layout(
        title='Cost Comparison: Optimization vs Heuristic',
        yaxis_title='Cost ($)',
        height=500,
        showlegend=False,
        font=dict(size=12),
    )

    return fig


# ========================================
#  Page Header
# ========================================

st.markdown(section_header("Results Comparison", level=1, icon="⚖️"), unsafe_allow_html=True)

st.markdown("""
Compare heuristic planning (rule-based) vs mathematical optimization (optimal) results side-by-side.
See cost savings, demand satisfaction improvements, and time-cost tradeoffs.
""")

st.divider()

# ========================================
#  Check Data Availability
# ========================================

heuristic_available = session_state.is_planning_complete()
optimization_available = 'optimization_result' in st.session_state and st.session_state['optimization_result'].is_feasible()

# Status badges
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    if heuristic_available:
        st.markdown(success_badge("Heuristic Results Available"), unsafe_allow_html=True)
    else:
        st.markdown(error_badge("Heuristic Results Missing"), unsafe_allow_html=True)

with col2:
    if optimization_available:
        st.markdown(success_badge("Optimization Results Available"), unsafe_allow_html=True)
    else:
        st.markdown(error_badge("Optimization Results Missing"), unsafe_allow_html=True)

with col3:
    # Quick action buttons
    if not heuristic_available:
        if st.button("▶️ Run Heuristic Planning", key="run_heuristic"):
            st.switch_page("pages/3_Planning_Workflow.py")
    if not optimization_available:
        if st.button("▶️ Run Optimization", key="run_optimization"):
            st.switch_page("pages/10_Optimization.py")

st.divider()

# If both missing, show getting started guide
if not heuristic_available and not optimization_available:
    st.markdown(
        info_box(
            """
            <b>Getting Started:</b><br>
            To compare results, you need to run both planning approaches:<br><br>
            1. <b>Heuristic Planning</b>: Go to Planning Workflow page and click "Run Complete Workflow"<br>
            2. <b>Mathematical Optimization</b>: Go to Optimization page and click "Run Optimization"<br><br>
            Once both are complete, return to this page to see the comparison.
            """,
            box_type="info",
            title="📋 No Results to Compare"
        ),
        unsafe_allow_html=True
    )
    st.stop()

# If only one is missing, show warning
if not heuristic_available:
    st.markdown(
        warning_box(
            """
            <b>Heuristic results not available.</b> Run the Planning Workflow first to establish a baseline for comparison.
            """,
            box_type="warning",
            title="⚠️ Missing Baseline"
        ),
        unsafe_allow_html=True
    )
    st.stop()

if not optimization_available:
    st.markdown(
        info_box(
            """
            <b>Optimization results not available.</b> The heuristic provides a good baseline,
            but optimization may find a better solution. Run optimization to see potential savings.
            """,
            box_type="info",
            title="💡 Optimization Not Run"
        ),
        unsafe_allow_html=True
    )
    st.stop()

# ========================================
#  Load Data
# ========================================

heuristic_data = get_heuristic_data()
optimization_data = get_optimization_data()

if not heuristic_data or not optimization_data:
    st.error("❌ Error loading comparison data. Please ensure both planning approaches have been run successfully.")
    st.stop()

# ========================================
#  Comparison Metrics Section
# ========================================

st.markdown(section_header("Cost Comparison", level=2), unsafe_allow_html=True)

# Calculate overall savings
total_delta_abs, total_delta_pct = calculate_delta(
    heuristic_data['total_cost'],
    optimization_data['total_cost']
)

# Show key insight
if total_delta_abs < 0:
    st.markdown(
        info_box(
            f"""
            <b>Optimization saves ${abs(total_delta_abs):,.2f} ({abs(total_delta_pct):.1f}%) compared to heuristic planning.</b><br>
            Optimization completed in {optimization_data['execution_time']:.1f} seconds.
            """,
            box_type="success",
            title="✅ Cost Savings Achieved"
        ),
        unsafe_allow_html=True
    )
elif total_delta_abs > 0:
    st.markdown(
        warning_box(
            f"""
            <b>Optimization cost is ${total_delta_abs:,.2f} ({total_delta_pct:.1f}%) higher than heuristic.</b><br>
            This may indicate constraints or model configuration differences. Review detailed breakdown below.
            """,
            box_type="warning",
            title="⚠️ Unexpected Result"
        ),
        unsafe_allow_html=True
    )
else:
    st.markdown(
        info_box(
            "<b>Both approaches yield the same total cost.</b><br>The heuristic may already be optimal for this scenario.",
            box_type="info",
            title="ℹ️ Equal Performance"
        ),
        unsafe_allow_html=True
    )

st.markdown("<br>", unsafe_allow_html=True)

# Metrics in 3 columns: Heuristic, Delta, Optimization
col1, col2, col3 = st.columns([2, 1, 2])

with col1:
    st.markdown(section_header("Heuristic (Baseline)", level=3), unsafe_allow_html=True)

    st.markdown(colored_metric(
        "Total Cost",
        format_currency(heuristic_data['total_cost']),
        "accent"
    ), unsafe_allow_html=True)

    metrics_html = '<div style="display: flex; flex-direction: column; gap: 12px;">'
    metrics_html += colored_metric("Labor Cost", format_currency(heuristic_data['labor_cost']), "primary")
    metrics_html += colored_metric("Production Cost", format_currency(heuristic_data['production_cost']), "primary")
    metrics_html += colored_metric("Transport Cost", format_currency(heuristic_data['transport_cost']), "accent")
    metrics_html += colored_metric("Waste Cost", format_currency(heuristic_data['waste_cost']), "error")
    metrics_html += '</div>'
    st.markdown(metrics_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.metric("Production Batches", format_number(heuristic_data['production_batches']))
    st.metric("Demand Satisfaction", format_percentage(heuristic_data['demand_satisfaction_pct']))

with col2:
    st.markdown(section_header("Δ Change", level=3), unsafe_allow_html=True)

    # Total cost delta
    total_delta_abs, total_delta_pct = calculate_delta(heuristic_data['total_cost'], optimization_data['total_cost'])
    delta_color = color_delta(total_delta_abs, inverse=True)

    st.markdown(colored_metric(
        "Total Δ",
        create_delta_display(total_delta_abs, total_delta_pct),
        delta_color
    ), unsafe_allow_html=True)

    # Component deltas
    components = [
        ('labor_cost', "Labor Δ"),
        ('production_cost', "Production Δ"),
        ('transport_cost', "Transport Δ"),
        ('waste_cost', "Waste Δ"),
    ]

    deltas_html = '<div style="display: flex; flex-direction: column; gap: 12px;">'
    for cost_key, label in components:
        delta_abs, delta_pct = calculate_delta(heuristic_data[cost_key], optimization_data[cost_key])
        delta_color = color_delta(delta_abs, inverse=True)
        delta_text = create_delta_display(delta_abs, delta_pct)

        # Simplified display
        if delta_abs < 0:
            badge = success_badge(delta_text)
        elif delta_abs > 0:
            badge = error_badge(delta_text)
        else:
            badge = info_badge("$0 (0%)")

        deltas_html += f'<div style="margin: 8px 0;"><b>{label}:</b><br>{badge}</div>'

    deltas_html += '</div>'
    st.markdown(deltas_html, unsafe_allow_html=True)

with col3:
    st.markdown(section_header("Optimization (Result)", level=3), unsafe_allow_html=True)

    # Determine color based on whether optimization is better
    opt_color = "secondary" if total_delta_abs < 0 else "error"

    st.markdown(colored_metric(
        "Total Cost",
        format_currency(optimization_data['total_cost']),
        opt_color
    ), unsafe_allow_html=True)

    metrics_html = '<div style="display: flex; flex-direction: column; gap: 12px;">'
    metrics_html += colored_metric("Labor Cost", format_currency(optimization_data['labor_cost']), "primary")
    metrics_html += colored_metric("Production Cost", format_currency(optimization_data['production_cost']), "primary")
    metrics_html += colored_metric("Transport Cost", format_currency(optimization_data['transport_cost']), "accent")
    metrics_html += colored_metric("Waste/Shortage", format_currency(optimization_data['waste_cost']), "error")
    metrics_html += '</div>'
    st.markdown(metrics_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.metric("Production Batches", format_number(optimization_data['production_batches']))
    st.metric("Demand Satisfaction", format_percentage(optimization_data['demand_satisfaction_pct']))

st.divider()

# ========================================
#  Waterfall Chart
# ========================================

st.markdown(section_header("Cost Breakdown Waterfall", level=2), unsafe_allow_html=True)

heuristic_costs = {
    'total_cost': heuristic_data['total_cost'],
    'labor_cost': heuristic_data['labor_cost'],
    'production_cost': heuristic_data['production_cost'],
    'transport_cost': heuristic_data['transport_cost'],
    'waste_cost': heuristic_data['waste_cost'],
}

optimization_costs = {
    'total_cost': optimization_data['total_cost'],
    'labor_cost': optimization_data['labor_cost'],
    'production_cost': optimization_data['production_cost'],
    'transport_cost': optimization_data['transport_cost'],
    'waste_cost': optimization_data['waste_cost'],
}

waterfall_fig = create_waterfall_chart(heuristic_costs, optimization_costs)
st.plotly_chart(waterfall_fig, use_container_width=True)

st.divider()

# ========================================
#  Detailed Comparison Tabs
# ========================================

st.markdown(section_header("Detailed Comparison", level=2), unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "💰 Cost Summary",
    "📦 Production Comparison",
    "✅ Demand Satisfaction",
    "👷 Labor Utilization",
    "⏱️ Performance Metrics"
])

with tab1:
    st.markdown("### Cost Component Breakdown")

    # Create comparison table
    cost_components = [
        ("Labor Cost", heuristic_data['labor_cost'], optimization_data['labor_cost']),
        ("Production Cost", heuristic_data['production_cost'], optimization_data['production_cost']),
        ("Transport Cost", heuristic_data['transport_cost'], optimization_data['transport_cost']),
        ("Waste/Shortage Cost", heuristic_data['waste_cost'], optimization_data['waste_cost']),
        ("**Total Cost**", heuristic_data['total_cost'], optimization_data['total_cost']),
    ]

    table_data = []
    for component, heur_val, opt_val in cost_components:
        delta_abs, delta_pct = calculate_delta(heur_val, opt_val)

        table_data.append({
            'Component': component,
            'Heuristic ($)': format_currency(heur_val),
            'Optimization ($)': format_currency(opt_val),
            'Delta ($)': format_currency(delta_abs),
            'Delta (%)': f"{delta_pct:+.1f}%",
        })

    df = pd.DataFrame(table_data)

    # Style the dataframe
    def highlight_delta(row):
        if 'Total' in row['Component']:
            return ['font-weight: bold'] * len(row)

        delta_str = row['Delta (%)']
        if delta_str.startswith('-'):
            return [''] * 3 + ['color: #43A047; font-weight: bold'] * 2
        elif delta_str.startswith('+') and not delta_str.startswith('+0'):
            return [''] * 3 + ['color: #E53935; font-weight: bold'] * 2
        return [''] * len(row)

    st.dataframe(
        df.style.apply(highlight_delta, axis=1),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Cost per unit comparison
    col1, col2, col3 = st.columns(3)
    with col1:
        heur_cpu = heuristic_data['total_cost'] / heuristic_data['total_units'] if heuristic_data['total_units'] > 0 else 0
        st.metric("Heuristic Cost/Unit", format_currency(heur_cpu))
    with col2:
        opt_cpu = optimization_data['total_cost'] / optimization_data['total_units'] if optimization_data['total_units'] > 0 else 0
        st.metric("Optimization Cost/Unit", format_currency(opt_cpu))
    with col3:
        cpu_delta = opt_cpu - heur_cpu
        st.metric("Cost/Unit Savings", format_currency(abs(cpu_delta)), delta=f"{cpu_delta:.2f}", delta_color="inverse")

with tab2:
    st.markdown("### Production Schedule Comparison")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Heuristic Production**")
        st.metric("Production Batches", format_number(heuristic_data['production_batches']))
        st.metric("Total Units", format_number(heuristic_data['total_units']))
        if heuristic_data['total_labor_hours']:
            st.metric("Labor Hours", f"{heuristic_data['total_labor_hours']:.1f}h")

    with col2:
        st.markdown("**Optimization Production**")
        st.metric("Production Batches", format_number(optimization_data['production_batches']))
        st.metric("Total Units", format_number(optimization_data['total_units']))
        if optimization_data['total_labor_hours']:
            st.metric("Labor Hours", f"{optimization_data['total_labor_hours']:.1f}h")

    st.markdown("<br>", unsafe_allow_html=True)

    # Production schedule details
    if 'production_schedule' in st.session_state and st.session_state['production_schedule']:
        with st.expander("View Heuristic Production Schedule"):
            schedule = st.session_state['production_schedule']
            if schedule.production_batches:
                batch_data = []
                for batch in schedule.production_batches[:20]:  # Limit to first 20
                    batch_data.append({
                        'Date': batch.production_date,
                        'Product': batch.product_id,
                        'Quantity': batch.quantity,
                        'Labor Hours': batch.labor_hours_used,
                    })
                st.dataframe(pd.DataFrame(batch_data), use_container_width=True, hide_index=True)

    if 'optimization_model' in st.session_state and st.session_state['optimization_model']:
        with st.expander("View Optimization Production Schedule"):
            model = st.session_state['optimization_model']
            solution = model.get_solution()
            if solution and solution.get('production_by_date_product'):
                prod_data = []
                for (prod_date, product), qty in list(solution['production_by_date_product'].items())[:20]:
                    if qty > 0:
                        prod_data.append({
                            'Date': prod_date,
                            'Product': product,
                            'Quantity': qty,
                        })
                if prod_data:
                    st.dataframe(pd.DataFrame(prod_data), use_container_width=True, hide_index=True)

with tab3:
    st.markdown("### Demand Satisfaction Analysis")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Heuristic Satisfaction",
            format_percentage(heuristic_data['demand_satisfaction_pct']),
        )

    with col2:
        st.metric(
            "Optimization Satisfaction",
            format_percentage(optimization_data['demand_satisfaction_pct']),
        )

    with col3:
        satisfaction_delta = optimization_data['demand_satisfaction_pct'] - heuristic_data['demand_satisfaction_pct']
        st.metric(
            "Satisfaction Change",
            f"{satisfaction_delta:+.1f}%",
            delta=f"{satisfaction_delta:.1f}%",
            delta_color="normal"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Show shortage details if applicable
    if optimization_data['demand_satisfaction_pct'] < 100:
        st.markdown(
            warning_box(
                f"""
                <b>Optimization left {100 - optimization_data['demand_satisfaction_pct']:.1f}% of demand unmet.</b><br>
                This may be due to capacity constraints or shortage penalties being lower than fulfillment costs.
                Check the Optimization page for detailed shortage analysis.
                """,
                box_type="warning",
                title="⚠️ Demand Shortages"
            ),
            unsafe_allow_html=True
        )

with tab4:
    st.markdown("### Labor Utilization")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Heuristic Labor**")
        if heuristic_data['total_labor_hours']:
            st.metric("Total Hours", f"{heuristic_data['total_labor_hours']:.1f}h")
            st.metric("Labor Cost", format_currency(heuristic_data['labor_cost']))
            cost_per_hour = heuristic_data['labor_cost'] / heuristic_data['total_labor_hours']
            st.metric("Cost per Hour", format_currency(cost_per_hour))
        else:
            st.info("Labor hours not available from heuristic results.")

    with col2:
        st.markdown("**Optimization Labor**")
        st.metric("Labor Cost", format_currency(optimization_data['labor_cost']))
        if heuristic_data['total_labor_hours']:
            # Estimate hours if possible
            st.info("Detailed labor hours not directly available from optimization model.")

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        info_box(
            """
            <b>Labor Analysis:</b> The optimization model considers labor costs in its objective function
            but may schedule production differently than the heuristic. Lower labor costs in optimization
            typically result from reduced overtime or more efficient production scheduling.
            """,
            box_type="info"
        ),
        unsafe_allow_html=True
    )

with tab5:
    st.markdown("### Performance Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Heuristic**")
        st.metric("Execution Time", "< 1 second")
        st.metric("Method", "Rule-based")
        st.info("Fast, deterministic results")

    with col2:
        st.markdown("**Optimization**")
        if optimization_data['execution_time']:
            st.metric("Execution Time", f"{optimization_data['execution_time']:.2f}s")

        solver = st.session_state.get('optimization_solver', 'unknown')
        st.metric("Solver", solver.upper())

        result = st.session_state.get('optimization_result')
        if result and result.is_optimal():
            st.success("Provably optimal")
        elif result and result.is_feasible():
            st.warning("Feasible, not proven optimal")

    with col3:
        st.markdown("**Trade-off**")
        if optimization_data['execution_time'] and total_delta_abs < 0:
            savings_per_second = abs(total_delta_abs) / optimization_data['execution_time']
            st.metric("Savings per Second", format_currency(savings_per_second))
            st.success("✅ Good time-cost tradeoff")
        elif total_delta_abs >= 0:
            st.warning("⚠️ No cost improvement")

    st.markdown("<br>", unsafe_allow_html=True)

    # Optimization statistics
    if 'optimization_result' in st.session_state:
        result = st.session_state['optimization_result']

        st.markdown("**Optimization Statistics**")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Variables", format_number(result.num_variables))
        with col2:
            st.metric("Constraints", format_number(result.num_constraints))
        with col3:
            if result.gap is not None:
                st.metric("MIP Gap", f"{result.gap*100:.2f}%")
        with col4:
            st.metric("Integer Vars", format_number(result.num_integer_vars))

st.divider()

# ========================================
#  Export Section (Placeholder)
# ========================================

st.markdown(section_header("Export Results", level=2), unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📊 Export Comparison to Excel", use_container_width=True, disabled=True):
        st.info("Export to Excel functionality will be implemented in WP1.3")

with col2:
    if st.button("📄 Generate PDF Report", use_container_width=True, disabled=True):
        st.info("PDF report generation will be implemented in WP1.3")

with col3:
    if st.button("📋 Copy Summary to Clipboard", use_container_width=True, disabled=True):
        st.info("Clipboard functionality will be implemented in WP1.3")

st.divider()

# ========================================
#  Navigation
# ========================================

st.markdown(section_header("Navigation", level=2), unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Heuristic Planning", use_container_width=True):
        st.switch_page("pages/3_Planning_Workflow.py")

with col2:
    if st.button("← Optimization", use_container_width=True):
        st.switch_page("pages/10_Optimization.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
