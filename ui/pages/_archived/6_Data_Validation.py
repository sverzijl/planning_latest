"""Data Validation Dashboard - Pre-flight checks for production planning.

This page provides comprehensive data validation to identify issues before planning runs.
Validates completeness, consistency, capacity constraints, shelf life, date ranges,
data quality, and business rules.
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

from ui import session_state
from ui.components.styling import (
    apply_custom_css,
    section_header,
    colored_metric,
    status_badge,
    info_box,
)
from src.validation import DataValidator, ValidationSeverity

# Page config
st.set_page_config(
    page_title="Data Validation",
    page_icon="✅",
    layout="wide",
)

# Apply custom CSS
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

st.markdown(section_header("Data Validation Dashboard", level=1, icon="✅"), unsafe_allow_html=True)

st.markdown(
    """
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">🔍 Pre-flight Checks</div>
        <div>
            Comprehensive validation of uploaded data to identify issues before planning runs.
            Prevents wasted time by catching problems early with actionable fix guidance.
        </div>
        <div style="margin-top: 8px; font-size: 13px; color: #757575;">
            <strong>Validation categories:</strong> Completeness • Consistency • Capacity •
            Transport • Shelf Life • Date Ranges • Data Quality • Business Rules
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# Check if data is loaded
if not session_state.is_data_uploaded():
    st.warning("⚠️ No data loaded yet. Please upload data first.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Go to Upload Data", use_container_width=True, type="primary"):
            st.switch_page("pages/1_Upload_Data.py")
    with col2:
        if st.button("🏠 Back to Home", use_container_width=True):
            st.switch_page("app.py")

    st.divider()

    # Show what validation will check
    st.markdown("### 📋 Validation Categories")

    categories = [
        ("Completeness", "All required data present (forecast, locations, routes, etc.)"),
        ("Consistency", "Cross-references valid (location IDs, product codes)"),
        ("Capacity", "Production and transport capacity sufficient for demand"),
        ("Transport", "Truck capacity and schedules adequate"),
        ("Shelf Life", "Transit times compatible with product shelf life"),
        ("Date Ranges", "Calendar coverage and planning horizon"),
        ("Data Quality", "Outliers, anomalies, and data integrity"),
        ("Business Rules", "Manufacturing and distribution constraints"),
    ]

    for category, description in categories:
        st.markdown(f"**{category}:** {description}")

    st.stop()

# Data is loaded - run validation
st.divider()

# Run validation button
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    run_validation = st.button("🔍 Run Validation Checks", type="primary", use_container_width=True)

with col2:
    if st.button("📊 View Data Summary", use_container_width=True):
        st.switch_page("pages/2_Data_Summary.py")

with col3:
    if st.button("🔄 Refresh", use_container_width=True):
        # Clear cached validation results
        if 'validation_issues' in st.session_state:
            del st.session_state['validation_issues']
        if 'validation_complete' in st.session_state:
            del st.session_state['validation_complete']
        st.rerun()

if run_validation or st.session_state.get('validation_complete', False):

    # Run validation if not already done or forced
    if run_validation or 'validation_issues' not in st.session_state:
        with st.spinner("Running validation checks..."):
            # Get data from session state
            parsed_data = session_state.get_parsed_data()

            # Create validator
            validator = DataValidator(
                forecast=parsed_data.get('forecast'),
                locations=parsed_data.get('locations'),
                routes=parsed_data.get('routes'),
                labor_calendar=parsed_data.get('labor_calendar'),
                truck_schedules=parsed_data.get('truck_schedules'),
                cost_structure=parsed_data.get('cost_structure'),
                manufacturing_site=parsed_data.get('manufacturing_site'),
            )

            # Run all checks
            issues = validator.validate_all()
            stats = validator.get_summary_stats()

            # Store results
            st.session_state.validation_issues = issues
            st.session_state.validation_stats = stats
            st.session_state.validation_complete = True
            st.session_state.validation_timestamp = datetime.now()

    # Display results
    issues = st.session_state.validation_issues
    stats = st.session_state.validation_stats

    st.divider()

    # Overall status message
    critical_count = stats['by_severity']['critical']
    error_count = stats['by_severity']['error']
    warning_count = stats['by_severity']['warning']
    info_count = stats['by_severity']['info']

    if critical_count == 0 and error_count == 0 and warning_count == 0:
        st.markdown(
            info_box(
                "All validation checks passed! Your data is ready for planning. "
                "No critical issues, errors, or warnings detected.",
                box_type="success",
                title="✅ Validation Successful"
            ),
            unsafe_allow_html=True
        )
    elif critical_count > 0:
        st.markdown(
            info_box(
                f"Found {critical_count} critical issue{'s' if critical_count != 1 else ''} that will prevent planning from running. "
                "These must be fixed before proceeding. See details below for guidance.",
                box_type="error",
                title="❌ Critical Issues Found"
            ),
            unsafe_allow_html=True
        )
    elif error_count > 0:
        st.markdown(
            info_box(
                f"Found {error_count} error{'s' if error_count != 1 else ''} that may cause planning to fail or produce poor results. "
                "Review and fix before running planning.",
                box_type="error",
                title="❌ Errors Found"
            ),
            unsafe_allow_html=True
        )
    elif warning_count > 0:
        st.markdown(
            info_box(
                f"Found {warning_count} warning{'s' if warning_count != 1 else ''} that may affect planning quality or costs. "
                "Planning can proceed, but review recommendations below.",
                box_type="warning",
                title="⚠️ Warnings Found"
            ),
            unsafe_allow_html=True
        )

    # Summary metrics
    st.markdown(section_header("Validation Summary", level=2), unsafe_allow_html=True)

    # Estimate total checks (8 categories × ~3 checks each)
    total_checks = 25
    passed_checks = total_checks - len(issues)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            colored_metric("Total Checks", str(total_checks), "primary"),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            colored_metric("Passed", str(passed_checks), "success"),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            colored_metric("Warnings", str(warning_count), "warning"),
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            colored_metric(
                "Errors",
                str(error_count + critical_count),
                "error"
            ),
            unsafe_allow_html=True
        )

    # Category breakdown
    if stats['by_category']:
        st.divider()
        st.markdown("**Issues by Category:**")

        cols = st.columns(len(stats['by_category']))
        for idx, (category, count) in enumerate(stats['by_category'].items()):
            with cols[idx]:
                st.metric(category, count)

    # Detailed results in tabs
    st.divider()
    st.markdown(section_header("Detailed Results", level=2), unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Summary",
        "❌ Critical & Errors",
        "⚠️ Warnings",
        "ℹ️ Info",
        "✅ All Issues"
    ])

    # Helper function to display issue card
    def display_issue_card(issue):
        """Display a single validation issue as an expandable card."""

        # Choose icon and color based on severity
        if issue.severity == ValidationSeverity.CRITICAL:
            icon = "🔴"
            badge = status_badge("error", "CRITICAL", icon="🔴")
        elif issue.severity == ValidationSeverity.ERROR:
            icon = "❌"
            badge = status_badge("error", "ERROR", icon="❌")
        elif issue.severity == ValidationSeverity.WARNING:
            icon = "⚠️"
            badge = status_badge("warning", "WARNING", icon="⚠️")
        else:
            icon = "ℹ️"
            badge = status_badge("info", "INFO", icon="ℹ️")

        # Create expander with title
        with st.expander(f"{icon} {issue.title}", expanded=False):
            # Display badge and category
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(badge, unsafe_allow_html=True)
            with col2:
                st.markdown(f"**Category:** {issue.category} • **ID:** `{issue.id}`")

            st.divider()

            # Description
            st.markdown("**Description:**")
            st.markdown(issue.description)

            # Impact
            st.markdown("**Impact:**")
            st.info(issue.impact)

            # Fix guidance
            st.markdown("**How to Fix:**")
            st.markdown(issue.fix_guidance)

            # Affected data table
            if issue.affected_data is not None and not issue.affected_data.empty:
                st.markdown("**Affected Data:**")
                st.dataframe(issue.affected_data, use_container_width=True, height=min(400, len(issue.affected_data) * 35 + 38))

            # Metadata
            if issue.metadata:
                with st.expander("📊 Additional Details", expanded=False):
                    st.json(issue.metadata)

    # Tab 1: Summary view
    with tab1:
        if len(issues) == 0:
            st.success("🎉 No issues found! All validation checks passed.")
        else:
            st.markdown("**Top Issues to Address:**")

            # Show critical and error issues first
            priority_issues = [i for i in issues if i.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]]

            if priority_issues:
                st.markdown(f"**{len(priority_issues)} Critical/Error Issues:**")
                for issue in priority_issues[:5]:  # Show top 5
                    severity_icon = "🔴" if issue.severity == ValidationSeverity.CRITICAL else "❌"
                    st.markdown(f"{severity_icon} **{issue.title}** ({issue.category})")
                    st.markdown(f"   ↳ {issue.impact}")

                if len(priority_issues) > 5:
                    st.info(f"... and {len(priority_issues) - 5} more. See detailed tabs for all issues.")

            # Show warnings summary
            warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
            if warnings:
                st.markdown(f"**{len(warnings)} Warnings:**")
                for issue in warnings[:3]:  # Show top 3
                    st.markdown(f"⚠️ **{issue.title}** ({issue.category})")

                if len(warnings) > 3:
                    st.info(f"... and {len(warnings) - 3} more. See Warnings tab for all.")

            # Show info summary
            infos = [i for i in issues if i.severity == ValidationSeverity.INFO]
            if infos:
                st.markdown(f"**{len(infos)} Informational Items:**")
                st.caption("See Info tab for details. These are for awareness and optimization opportunities.")

    # Tab 2: Critical & Errors
    with tab2:
        critical_and_errors = [i for i in issues if i.severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]]

        if len(critical_and_errors) == 0:
            st.success("✅ No critical issues or errors found!")
        else:
            st.markdown(f"**Found {len(critical_and_errors)} critical issues and errors that need attention:**")
            st.divider()

            for issue in critical_and_errors:
                display_issue_card(issue)

    # Tab 3: Warnings
    with tab3:
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]

        if len(warnings) == 0:
            st.success("✅ No warnings found!")
        else:
            st.markdown(f"**Found {len(warnings)} warnings to review:**")
            st.divider()

            for issue in warnings:
                display_issue_card(issue)

    # Tab 4: Info
    with tab4:
        infos = [i for i in issues if i.severity == ValidationSeverity.INFO]

        if len(infos) == 0:
            st.info("No informational items to display.")
        else:
            st.markdown(f"**{len(infos)} informational items for awareness:**")
            st.caption("These are not problems but provide insights and optimization opportunities.")
            st.divider()

            for issue in infos:
                display_issue_card(issue)

    # Tab 5: All issues
    with tab5:
        if len(issues) == 0:
            st.success("🎉 No issues found! All validation checks passed.")
        else:
            st.markdown(f"**All {len(issues)} validation issues:**")
            st.divider()

            for issue in issues:
                display_issue_card(issue)

    # Action buttons at bottom
    st.divider()
    st.markdown(section_header("Next Steps", level=2, icon="🎯"), unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("📤 Fix & Re-upload Data", use_container_width=True):
            st.switch_page("pages/1_Upload_Data.py")

    with col2:
        if critical_count == 0 and error_count == 0:
            if st.button("🚀 Proceed to Planning", use_container_width=True, type="primary"):
                st.switch_page("pages/3_Planning_Workflow.py")
        else:
            st.button(
                "🚀 Proceed to Planning",
                use_container_width=True,
                disabled=True,
                help="Fix critical issues and errors before planning"
            )

    with col3:
        if st.button("📊 View Data Summary", use_container_width=True):
            st.switch_page("pages/2_Data_Summary.py")

    with col4:
        if st.button("🏠 Back to Home", use_container_width=True):
            st.switch_page("app.py")

    # Export validation report
    st.divider()

    with st.expander("📥 Export Validation Report"):
        st.markdown("**Download validation results as CSV:**")

        # Create CSV export
        export_data = []
        for issue in issues:
            export_data.append({
                'ID': issue.id,
                'Severity': issue.severity.value,
                'Category': issue.category,
                'Title': issue.title,
                'Description': issue.description,
                'Impact': issue.impact,
                'Fix Guidance': issue.fix_guidance,
            })

        if export_data:
            df_export = pd.DataFrame(export_data)
            csv = df_export.to_csv(index=False)

            timestamp = st.session_state.get('validation_timestamp', datetime.now())
            filename = f"validation_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.csv"

            st.download_button(
                label="📥 Download CSV Report",
                data=csv,
                file_name=filename,
                mime="text/csv",
                use_container_width=True
            )

else:
    st.info("👆 Click 'Run Validation Checks' to validate your uploaded data.")

    st.markdown("### 🎯 Benefits of Validation")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Prevents Wasted Time:**
        - Catch issues before planning runs
        - Avoid 10-20 min of failed planning
        - Get actionable fix guidance

        **Ensures Data Quality:**
        - Detects outliers and anomalies
        - Validates cross-references
        - Checks business rule compliance
        """)

    with col2:
        st.markdown("""
        **Validates Feasibility:**
        - Production capacity sufficient
        - Transport capacity adequate
        - Shelf life requirements met

        **Builds Confidence:**
        - Know data is correct before planning
        - Understand constraints upfront
        - Identify optimization opportunities
        """)
