"""Workflow progress checklist component.

Displays a visual checklist in the sidebar showing workflow execution progress.
Each workflow type has a standardized set of steps that guide the user through
the process.
"""

import streamlit as st
from typing import List, Dict, Optional
from enum import Enum


class ChecklistItem:
    """A single item in the workflow checklist.

    Attributes:
        label: Display text for the step
        status: Current status (pending/in_progress/completed)
        help_text: Optional help text shown on hover
    """

    def __init__(self, label: str, status: str = "pending", help_text: Optional[str] = None):
        self.label = label
        self.status = status  # "pending", "in_progress", "completed"
        self.help_text = help_text


def render_workflow_checklist(
    title: str,
    items: List[ChecklistItem],
    show_in_sidebar: bool = True
) -> None:
    """Render a workflow checklist with visual status indicators.

    Args:
        title: Checklist title (e.g., "Initial Solve Progress")
        items: List of ChecklistItem objects
        show_in_sidebar: Whether to render in sidebar (default: True)

    Example:
        ```python
        items = [
            ChecklistItem("Upload Data", status="completed"),
            ChecklistItem("Configure Solve", status="in_progress"),
            ChecklistItem("Run Optimization", status="pending"),
            ChecklistItem("Review Results", status="pending"),
        ]

        render_workflow_checklist("Initial Solve", items)
        ```
    """
    container = st.sidebar if show_in_sidebar else st

    with container:
        st.markdown(f"### {title}")
        st.markdown("---")

        for i, item in enumerate(items, 1):
            # Choose icon based on status
            if item.status == "completed":
                icon = "✅"
                color = "#28a745"  # Green
            elif item.status == "in_progress":
                icon = "🔄"
                color = "#007bff"  # Blue
            else:  # pending
                icon = "⭕"
                color = "#6c757d"  # Gray

            # Render item
            st.markdown(
                f'<div style="display: flex; align-items: center; margin-bottom: 12px;">'
                f'<span style="font-size: 20px; margin-right: 8px;">{icon}</span>'
                f'<span style="color: {color}; font-weight: {"600" if item.status == "in_progress" else "400"};">'
                f'{i}. {item.label}'
                f'</span>'
                f'</div>',
                unsafe_allow_html=True
            )

            # Show help text if provided
            if item.help_text:
                with st.expander("ℹ️ Help", expanded=False):
                    st.caption(item.help_text)

        st.markdown("---")


def get_initial_workflow_checklist(current_step: int = 0) -> List[ChecklistItem]:
    """Get checklist for Initial workflow.

    Args:
        current_step: Index of current step (0-based)

    Returns:
        List of ChecklistItem objects with appropriate status
    """
    steps = [
        ("Upload Data", "Provide forecast, network config, and initial inventory"),
        ("Configure Solve", "Set planning horizon, time limits, and solver options"),
        ("Run Optimization", "Execute 12-week optimization (cold start)"),
        ("Review Results", "Examine production plan, costs, and feasibility"),
        ("Export Plans", "Download production schedules and reports"),
    ]

    items = []
    for i, (label, help_text) in enumerate(steps):
        if i < current_step:
            status = "completed"
        elif i == current_step:
            status = "in_progress"
        else:
            status = "pending"

        items.append(ChecklistItem(label, status, help_text))

    return items


def get_weekly_workflow_checklist(current_step: int = 0) -> List[ChecklistItem]:
    """Get checklist for Weekly workflow.

    Args:
        current_step: Index of current step (0-based)

    Returns:
        List of ChecklistItem objects with appropriate status
    """
    steps = [
        ("Upload Data", "Upload updated forecast and verify network config"),
        ("Review Inventory", "Verify current inventory (auto-calculated from previous solve)"),
        ("Review Warmstart", "Preview warmstart data and approve/reject"),
        ("Configure Solve", "Set planning horizon and solver options"),
        ("Run Optimization", "Execute 12-week rolling horizon optimization"),
        ("Review Results", "Compare with previous week's plan"),
        ("Export Plans", "Download updated production schedules"),
    ]

    items = []
    for i, (label, help_text) in enumerate(steps):
        if i < current_step:
            status = "completed"
        elif i == current_step:
            status = "in_progress"
        else:
            status = "pending"

        items.append(ChecklistItem(label, status, help_text))

    return items


def get_daily_workflow_checklist(current_step: int = 0) -> List[ChecklistItem]:
    """Get checklist for Daily workflow.

    Args:
        current_step: Index of current step (0-based)

    Returns:
        List of ChecklistItem objects with appropriate status
    """
    steps = [
        ("Enter Actuals", "Enter yesterday's actual production and shipments"),
        ("Review Today", "Review and lock today's production plan"),
        ("Verify Inventory", "Check current inventory and in-transit stock"),
        ("Configure Solve", "Set free/fixed periods and solver options"),
        ("Run Optimization", "Execute 4-week free + 8-week fixed optimization"),
        ("Review Results", "Check variance report and updated plan"),
        ("Generate Plans", "Create production plans for next 1-7 days"),
        ("Export Plans", "Download dough plan, packing plan, and reports"),
    ]

    items = []
    for i, (label, help_text) in enumerate(steps):
        if i < current_step:
            status = "completed"
        elif i == current_step:
            status = "in_progress"
        else:
            status = "pending"

        items.append(ChecklistItem(label, status, help_text))

    return items


def update_checklist_step(workflow_type: str, new_step: int) -> None:
    """Update the current step in session state.

    Args:
        workflow_type: "initial", "weekly", or "daily"
        new_step: New step index (0-based)
    """
    st.session_state[f'{workflow_type}_workflow_step'] = new_step


def get_current_step(workflow_type: str) -> int:
    """Get current step for a workflow from session state.

    Args:
        workflow_type: "initial", "weekly", or "daily"

    Returns:
        Current step index (0-based)
    """
    return st.session_state.get(f'{workflow_type}_workflow_step', 0)
