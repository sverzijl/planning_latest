"""Scenario Management page - save, load, and compare planning scenarios."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from typing import List

from ui import session_state
from ui.components.styling import (
    apply_custom_css,
    section_header,
    status_badge,
    colored_metric,
    info_box,
    create_card,
)
from src.scenario import ScenarioManager, Scenario

# Page config
st.set_page_config(
    page_title="Scenario Management",
    page_icon="💾",
    layout="wide",
)

# Apply custom styling
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

# Initialize scenario manager
if 'scenario_manager' not in st.session_state:
    st.session_state.scenario_manager = ScenarioManager()

scenario_manager = st.session_state.scenario_manager

# Page header
st.markdown(section_header("Scenario Management", level=1, icon="💾"), unsafe_allow_html=True)

st.markdown("""
Save, load, and compare multiple planning scenarios to evaluate "what-if" alternatives.
Compare baseline vs. high-demand scenarios, test different optimization strategies,
or evaluate overtime policies.
""")

st.divider()


# =============================================================================
# Helper Functions
# =============================================================================

def extract_current_scenario_data() -> dict:
    """Extract current session state into scenario-compatible dict."""
    return {
        'forecast_data': st.session_state.get('forecast'),
        'labor_calendar': st.session_state.get('labor_calendar'),
        'truck_schedules': st.session_state.get('truck_schedules'),
        'cost_parameters': st.session_state.get('cost_structure'),
        'locations': st.session_state.get('locations'),
        'routes': st.session_state.get('routes'),
        'manufacturing_site': st.session_state.get('manufacturing_site'),
        'planning_results': st.session_state.get('cost_breakdown'),
        'optimization_results': st.session_state.get('optimization_result'),
    }


def load_scenario_to_session(scenario: Scenario) -> None:
    """Load scenario data into session state."""
    if scenario.forecast_data is not None:
        st.session_state.forecast = scenario.forecast_data
    if scenario.labor_calendar is not None:
        st.session_state.labor_calendar = scenario.labor_calendar
    if scenario.truck_schedules is not None:
        st.session_state.truck_schedules = scenario.truck_schedules
    if scenario.cost_parameters is not None:
        st.session_state.cost_structure = scenario.cost_parameters
    if scenario.locations is not None:
        st.session_state.locations = scenario.locations
    if scenario.routes is not None:
        st.session_state.routes = scenario.routes
    if scenario.manufacturing_site is not None:
        st.session_state.manufacturing_site = scenario.manufacturing_site

    # Load results if present
    if scenario.planning_results is not None:
        st.session_state.cost_breakdown = scenario.planning_results
        st.session_state.planning_complete = True
    if scenario.optimization_results is not None:
        st.session_state.optimization_result = scenario.optimization_results


def create_cost_comparison_chart(scenarios: List[Scenario]) -> go.Figure:
    """Create grouped bar chart comparing costs across scenarios."""
    scenario_names = [s.name for s in scenarios]

    # Prepare data
    labor_costs = [s.labor_cost if s.labor_cost is not None else 0 for s in scenarios]
    production_costs = [s.production_cost if s.production_cost is not None else 0 for s in scenarios]
    transport_costs = [s.transport_cost if s.transport_cost is not None else 0 for s in scenarios]
    waste_costs = [s.waste_cost if s.waste_cost is not None else 0 for s in scenarios]

    # Create stacked bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Labor',
        x=scenario_names,
        y=labor_costs,
        marker_color='#1E88E5',
    ))

    fig.add_trace(go.Bar(
        name='Production',
        x=scenario_names,
        y=production_costs,
        marker_color='#43A047',
    ))

    fig.add_trace(go.Bar(
        name='Transport',
        x=scenario_names,
        y=transport_costs,
        marker_color='#FB8C00',
    ))

    fig.add_trace(go.Bar(
        name='Waste',
        x=scenario_names,
        y=waste_costs,
        marker_color='#E53935',
    ))

    fig.update_layout(
        barmode='stack',
        title='Cost Breakdown by Scenario',
        xaxis_title='Scenario',
        yaxis_title='Cost ($)',
        hovermode='x unified',
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig


def create_metrics_comparison_chart(scenarios: List[Scenario]) -> go.Figure:
    """Create chart comparing key metrics across scenarios."""
    scenario_names = [s.name for s in scenarios]

    # Normalize metrics to 0-100 scale for comparison
    total_costs = [s.total_cost if s.total_cost is not None else 0 for s in scenarios]
    demand_sat = [s.demand_satisfaction_pct if s.demand_satisfaction_pct is not None else 0 for s in scenarios]

    # Normalize total cost (inverse - lower is better)
    max_cost = max(total_costs) if total_costs else 1
    normalized_costs = [100 - (cost / max_cost * 100) if max_cost > 0 else 0 for cost in total_costs]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Cost Efficiency (lower cost = higher score)',
        x=scenario_names,
        y=normalized_costs,
        marker_color='#1E88E5',
    ))

    fig.add_trace(go.Bar(
        name='Demand Satisfaction (%)',
        x=scenario_names,
        y=demand_sat,
        marker_color='#43A047',
    ))

    fig.update_layout(
        barmode='group',
        title='Performance Comparison',
        xaxis_title='Scenario',
        yaxis_title='Score (0-100)',
        hovermode='x unified',
        height=400,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    return fig


# =============================================================================
# Section 1: Save Current Scenario
# =============================================================================

st.markdown(section_header("Save Current Scenario", level=2), unsafe_allow_html=True)

# Check if there's data to save
has_data = session_state.is_data_uploaded()
has_results = session_state.is_planning_complete() or 'optimization_result' in st.session_state

if not has_data:
    st.markdown(
        info_box(
            "No data loaded. Please upload data first before saving scenarios.",
            box_type="warning",
            title="⚠️ No Data"
        ),
        unsafe_allow_html=True
    )
else:
    # Show current state summary
    with st.expander("📊 Current State Summary", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            stats = session_state.get_summary_stats()
            st.metric("Forecast Entries", stats.get('forecast_entries', 0))
            st.metric("Locations", stats.get('locations', 0))

        with col2:
            st.metric("Routes", stats.get('routes', 0))
            st.metric("Planning Days", stats.get('date_range_days', 0))

        with col3:
            if has_results:
                summary = session_state.get_planning_summary()
                total_cost = summary.get('total_cost', 0)
                st.metric("Total Cost", f"${total_cost:,.2f}" if total_cost else "N/A")
                demand_sat = summary.get('demand_satisfaction_pct', 0)
                if demand_sat:
                    st.metric("Demand Satisfaction", f"{demand_sat:.1f}%")
            else:
                st.info("No planning results yet")

    # Save scenario form
    with st.form("save_scenario_form"):
        st.markdown("### Scenario Details")

        name = st.text_input(
            "Scenario Name*",
            placeholder="e.g., Baseline Q1 2025",
            help="Required: A descriptive name for this scenario"
        )

        description = st.text_area(
            "Description",
            placeholder="Optional notes about this scenario, assumptions, or key differences from baseline",
            help="Optional: Detailed description of this scenario"
        )

        tags_input = st.text_input(
            "Tags (comma-separated)",
            placeholder="e.g., baseline, Q1, high-demand, optimization",
            help="Optional: Tags for organizing and filtering scenarios"
        )

        # Determine planning mode
        planning_mode = None
        if 'optimization_result' in st.session_state:
            planning_mode = "optimization"
        elif session_state.is_planning_complete():
            planning_mode = "heuristic"

        if planning_mode:
            st.info(f"✓ Planning mode: **{planning_mode.capitalize()}**")

        col1, col2 = st.columns([1, 3])
        with col1:
            submitted = st.form_submit_button("💾 Save Scenario", use_container_width=True, type="primary")
        with col2:
            if not has_results:
                st.caption("💡 Tip: Run planning workflow or optimization first to save complete results")

        if submitted:
            if not name:
                st.error("❌ Please provide a scenario name")
            else:
                try:
                    # Parse tags
                    tags = [t.strip() for t in tags_input.split(",")] if tags_input else []

                    # Extract current data
                    current_data = extract_current_scenario_data()

                    # Save scenario
                    scenario = scenario_manager.save_scenario(
                        name=name,
                        description=description,
                        planning_mode=planning_mode,
                        tags=tags,
                        **current_data
                    )

                    st.success(f"✅ Scenario '{name}' saved successfully!")
                    st.markdown(
                        info_box(
                            f"**Scenario ID:** {scenario.id}<br>"
                            f"**Created:** {scenario.created_at.strftime('%Y-%m-%d %H:%M:%S')}<br>"
                            f"**Tags:** {', '.join(tags) if tags else 'None'}",
                            box_type="success"
                        ),
                        unsafe_allow_html=True
                    )

                    # Clear form by rerunning
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error saving scenario: {str(e)}")

st.divider()


# =============================================================================
# Section 2: Load Saved Scenario
# =============================================================================

st.markdown(section_header("Load Saved Scenario", level=2), unsafe_allow_html=True)

# List scenarios
scenarios = scenario_manager.list_scenarios()

if not scenarios:
    st.markdown(
        info_box(
            "No saved scenarios yet. Save your current planning state above to create your first scenario.",
            box_type="info",
            title="ℹ️ No Scenarios"
        ),
        unsafe_allow_html=True
    )
else:
    # Filter options
    col1, col2 = st.columns([2, 1])

    with col1:
        # Tag filter
        all_tags = set()
        for s in scenarios:
            all_tags.update(s.tags)
        all_tags = sorted(list(all_tags))

        if all_tags:
            selected_tags = st.multiselect(
                "Filter by Tags",
                options=all_tags,
                default=[],
                help="Filter scenarios by tags"
            )
        else:
            selected_tags = []

    with col2:
        sort_option = st.selectbox(
            "Sort By",
            options=["Created Date (Newest)", "Created Date (Oldest)", "Name (A-Z)", "Total Cost (Low-High)"],
            index=0
        )

    # Apply filters
    filtered_scenarios = scenarios
    if selected_tags:
        filtered_scenarios = scenario_manager.list_scenarios(tags=selected_tags)

    # Apply sorting
    if sort_option == "Created Date (Newest)":
        filtered_scenarios = sorted(filtered_scenarios, key=lambda s: s.created_at, reverse=True)
    elif sort_option == "Created Date (Oldest)":
        filtered_scenarios = sorted(filtered_scenarios, key=lambda s: s.created_at, reverse=False)
    elif sort_option == "Name (A-Z)":
        filtered_scenarios = sorted(filtered_scenarios, key=lambda s: s.name.lower())
    elif sort_option == "Total Cost (Low-High)":
        filtered_scenarios = sorted(
            filtered_scenarios,
            key=lambda s: s.total_cost if s.total_cost is not None else float('inf')
        )

    st.markdown(f"**{len(filtered_scenarios)}** scenario(s) found")

    # Display scenarios as cards
    for scenario in filtered_scenarios:
        with st.expander(
            f"📋 {scenario.name} ({scenario.created_at.strftime('%Y-%m-%d %H:%M')})",
            expanded=False
        ):
            # Scenario details
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Description:** {scenario.description or 'N/A'}")
                st.markdown(f"**Tags:** {', '.join(scenario.tags) if scenario.tags else 'None'}")
                st.markdown(f"**Planning Mode:** {scenario.planning_mode or 'N/A'}")
                st.markdown(f"**Created:** {scenario.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                st.markdown(f"**Modified:** {scenario.modified_at.strftime('%Y-%m-%d %H:%M:%S')}")

            with col2:
                # Metrics
                if scenario.total_cost is not None:
                    st.markdown(
                        colored_metric("Total Cost", f"${scenario.total_cost:,.2f}", "primary"),
                        unsafe_allow_html=True
                    )

                if scenario.demand_satisfaction_pct is not None:
                    st.markdown(
                        colored_metric(
                            "Demand Satisfaction",
                            f"{scenario.demand_satisfaction_pct:.1f}%",
                            "success"
                        ),
                        unsafe_allow_html=True
                    )

            # Cost breakdown
            if any([scenario.labor_cost, scenario.production_cost, scenario.transport_cost, scenario.waste_cost]):
                st.markdown("**Cost Breakdown:**")
                cost_col1, cost_col2, cost_col3, cost_col4 = st.columns(4)

                with cost_col1:
                    if scenario.labor_cost is not None:
                        st.metric("Labor", f"${scenario.labor_cost:,.0f}")
                with cost_col2:
                    if scenario.production_cost is not None:
                        st.metric("Production", f"${scenario.production_cost:,.0f}")
                with cost_col3:
                    if scenario.transport_cost is not None:
                        st.metric("Transport", f"${scenario.transport_cost:,.0f}")
                with cost_col4:
                    if scenario.waste_cost is not None:
                        st.metric("Waste", f"${scenario.waste_cost:,.0f}")

            # Production metrics
            if scenario.total_production_units is not None:
                st.metric("Total Production", f"{scenario.total_production_units:,} units")

            if scenario.planning_time_seconds is not None:
                st.metric("Planning Time", f"{scenario.planning_time_seconds:.2f} seconds")

            # Action buttons
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button("📂 Load", key=f"load_{scenario.id}", use_container_width=True):
                    load_scenario_to_session(scenario)
                    st.success(f"✅ Scenario '{scenario.name}' loaded!")
                    st.rerun()

            with col2:
                if st.button("✏️ Edit", key=f"edit_{scenario.id}", use_container_width=True):
                    st.session_state[f"editing_{scenario.id}"] = True
                    st.rerun()

            with col3:
                # Export button with download
                export_format = st.selectbox(
                    "Format",
                    options=["pickle", "json", "excel"],
                    key=f"export_format_{scenario.id}",
                    label_visibility="collapsed"
                )

                if st.button("📤 Export", key=f"export_{scenario.id}", use_container_width=True):
                    try:
                        extension = {"pickle": "pkl", "json": "json", "excel": "xlsx"}[export_format]
                        filename = f"{scenario.name.replace(' ', '_')}_{scenario.id[:8]}.{extension}"
                        filepath = f"/tmp/{filename}"

                        scenario_manager.export_scenario(scenario.id, filepath, format=export_format)

                        with open(filepath, 'rb') as f:
                            st.download_button(
                                label=f"⬇️ Download {extension.upper()}",
                                data=f,
                                file_name=filename,
                                mime="application/octet-stream",
                                key=f"download_{scenario.id}"
                            )
                    except Exception as e:
                        st.error(f"❌ Export error: {str(e)}")

            with col4:
                if st.button("🗑️ Delete", key=f"delete_{scenario.id}", use_container_width=True, type="secondary"):
                    if st.session_state.get(f"confirm_delete_{scenario.id}", False):
                        scenario_manager.delete_scenario(scenario.id)
                        st.success(f"✅ Scenario '{scenario.name}' deleted")
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_{scenario.id}"] = True
                        st.warning("⚠️ Click again to confirm deletion")

            # Edit form (if editing)
            if st.session_state.get(f"editing_{scenario.id}", False):
                st.markdown("---")
                st.markdown("### Edit Scenario")

                with st.form(f"edit_form_{scenario.id}"):
                    new_name = st.text_input("Name", value=scenario.name)
                    new_description = st.text_area("Description", value=scenario.description or "")
                    new_tags = st.text_input("Tags (comma-separated)", value=", ".join(scenario.tags))

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("💾 Save Changes", use_container_width=True):
                            updated_scenario = scenario_manager.update_scenario(
                                scenario.id,
                                name=new_name,
                                description=new_description,
                                tags=[t.strip() for t in new_tags.split(",") if t.strip()]
                            )
                            st.success("✅ Scenario updated!")
                            st.session_state[f"editing_{scenario.id}"] = False
                            st.rerun()
                    with col2:
                        if st.form_submit_button("❌ Cancel", use_container_width=True):
                            st.session_state[f"editing_{scenario.id}"] = False
                            st.rerun()

st.divider()


# =============================================================================
# Section 3: Compare Scenarios
# =============================================================================

st.markdown(section_header("Compare Scenarios", level=2), unsafe_allow_html=True)

if len(scenarios) < 2:
    st.markdown(
        info_box(
            "You need at least 2 saved scenarios to use the comparison feature. Save more scenarios to enable comparison.",
            box_type="info",
            title="ℹ️ Insufficient Scenarios"
        ),
        unsafe_allow_html=True
    )
else:
    # Scenario selection
    scenario_options = {s.id: f"{s.name} ({s.created_at.strftime('%Y-%m-%d %H:%M')})" for s in scenarios}

    selected_scenario_ids = st.multiselect(
        "Select scenarios to compare (2-4 recommended)",
        options=list(scenario_options.keys()),
        format_func=lambda sid: scenario_options[sid],
        default=list(scenario_options.keys())[:min(2, len(scenarios))],
        max_selections=6
    )

    if len(selected_scenario_ids) < 2:
        st.warning("⚠️ Please select at least 2 scenarios to compare")
    else:
        if st.button("🔍 Compare Selected Scenarios", type="primary"):
            try:
                # Load selected scenarios
                selected_scenarios = [
                    scenario_manager.load_scenario(sid)
                    for sid in selected_scenario_ids
                ]

                # Generate comparison table
                st.markdown("### 📊 Comparison Table")
                comparison_df = scenario_manager.compare_scenarios(selected_scenario_ids)
                st.dataframe(comparison_df, use_container_width=True, hide_index=True)

                # Cost breakdown chart
                st.markdown("### 💰 Cost Breakdown Comparison")
                cost_chart = create_cost_comparison_chart(selected_scenarios)
                st.plotly_chart(cost_chart, use_container_width=True)

                # Metrics comparison chart
                st.markdown("### 📈 Performance Metrics")
                metrics_chart = create_metrics_comparison_chart(selected_scenarios)
                st.plotly_chart(metrics_chart, use_container_width=True)

                # Key differences analysis
                st.markdown("### 🔍 Key Differences")

                baseline = selected_scenarios[0]
                st.markdown(f"**Baseline:** {baseline.name}")

                for i, scenario in enumerate(selected_scenarios[1:], start=1):
                    st.markdown(f"**Comparison {i}:** {scenario.name}")

                    cols = st.columns(4)

                    # Cost difference
                    with cols[0]:
                        if baseline.total_cost is not None and scenario.total_cost is not None:
                            delta = scenario.total_cost - baseline.total_cost
                            pct = (delta / baseline.total_cost * 100) if baseline.total_cost != 0 else 0
                            st.metric(
                                "Cost Difference",
                                f"${abs(delta):,.2f}",
                                delta=f"{pct:+.1f}%",
                                delta_color="inverse"  # Lower cost is better
                            )

                    # Demand satisfaction difference
                    with cols[1]:
                        if (baseline.demand_satisfaction_pct is not None and
                            scenario.demand_satisfaction_pct is not None):
                            delta = scenario.demand_satisfaction_pct - baseline.demand_satisfaction_pct
                            st.metric(
                                "Demand Satisfaction Δ",
                                f"{abs(delta):.1f}%",
                                delta=f"{delta:+.1f}%"
                            )

                    # Production difference
                    with cols[2]:
                        if (baseline.total_production_units is not None and
                            scenario.total_production_units is not None):
                            delta = scenario.total_production_units - baseline.total_production_units
                            pct = (delta / baseline.total_production_units * 100) if baseline.total_production_units != 0 else 0
                            st.metric(
                                "Production Δ",
                                f"{abs(delta):,} units",
                                delta=f"{pct:+.1f}%"
                            )

                    # Time difference
                    with cols[3]:
                        if (baseline.planning_time_seconds is not None and
                            scenario.planning_time_seconds is not None):
                            delta = scenario.planning_time_seconds - baseline.planning_time_seconds
                            st.metric(
                                "Planning Time Δ",
                                f"{abs(delta):.2f}s",
                                delta=f"{delta:+.2f}s",
                                delta_color="inverse"
                            )

                    st.markdown("---")

            except Exception as e:
                st.error(f"❌ Error comparing scenarios: {str(e)}")

st.divider()


# =============================================================================
# Section 4: Import Scenario
# =============================================================================

st.markdown(section_header("Import Scenario", level=2), unsafe_allow_html=True)

with st.expander("📥 Import Scenario from File", expanded=False):
    uploaded_file = st.file_uploader(
        "Upload scenario file",
        type=["pkl", "json"],
        help="Upload a previously exported scenario file"
    )

    if uploaded_file is not None:
        import_format = "pickle" if uploaded_file.name.endswith(".pkl") else "json"

        if st.button("📥 Import Scenario", type="primary"):
            try:
                # Save uploaded file temporarily
                temp_path = f"/tmp/{uploaded_file.name}"
                with open(temp_path, 'wb') as f:
                    f.write(uploaded_file.getbuffer())

                # Import scenario
                imported_scenario = scenario_manager.import_scenario(temp_path, format=import_format)

                st.success(f"✅ Scenario '{imported_scenario.name}' imported successfully!")
                st.markdown(
                    info_box(
                        f"**Scenario ID:** {imported_scenario.id}<br>"
                        f"**Original Name:** {imported_scenario.name}<br>"
                        f"**Imported At:** {imported_scenario.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
                        box_type="success"
                    ),
                    unsafe_allow_html=True
                )

                st.rerun()

            except Exception as e:
                st.error(f"❌ Import error: {str(e)}")

st.divider()


# =============================================================================
# Section 5: Storage Management
# =============================================================================

st.markdown(section_header("Storage Management", level=2), unsafe_allow_html=True)

with st.expander("💾 Storage Information", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        total_scenarios = len(scenarios)
        st.metric("Total Scenarios", total_scenarios)

    with col2:
        storage_size = scenario_manager.get_storage_size()
        storage_mb = storage_size / (1024 * 1024)
        st.metric("Storage Size", f"{storage_mb:.2f} MB")

    with col3:
        avg_size = (storage_size / total_scenarios) if total_scenarios > 0 else 0
        avg_mb = avg_size / (1024 * 1024)
        st.metric("Avg Scenario Size", f"{avg_mb:.2f} MB")

    st.markdown("---")

    # Cleanup orphaned files
    if st.button("🧹 Cleanup Orphaned Files", help="Remove scenario files not in index"):
        removed = scenario_manager.cleanup_orphaned_files()
        if removed > 0:
            st.success(f"✅ Removed {removed} orphaned file(s)")
        else:
            st.info("ℹ️ No orphaned files found")

    # Storage location
    st.markdown(f"**Storage Location:** `{scenario_manager.storage_dir.absolute()}`")

st.divider()


# =============================================================================
# Footer
# =============================================================================

st.markdown("---")
st.markdown(
    info_box(
        """
        <strong>💡 Tips for Effective Scenario Management:</strong><br>
        <ul>
            <li><strong>Use descriptive names:</strong> Include key parameters (e.g., "High Demand +20% with Overtime")</li>
            <li><strong>Tag systematically:</strong> Use tags like "baseline", "approved", "Q1-2025" for easy filtering</li>
            <li><strong>Compare 2-3 scenarios:</strong> Too many scenarios make comparison difficult</li>
            <li><strong>Export critical scenarios:</strong> Backup important scenarios to external storage</li>
            <li><strong>Regular cleanup:</strong> Delete outdated scenarios to save storage space</li>
        </ul>
        """,
        box_type="info",
        title="Best Practices"
    ),
    unsafe_allow_html=True
)
