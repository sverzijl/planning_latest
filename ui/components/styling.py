"""Styling helper functions for the Streamlit application.

This module provides utility functions to apply the custom design system
defined in ui/assets/styles.css. It includes functions for:
- Loading and injecting custom CSS
- Creating status badges
- Generating colored metric cards
- Styling section headers
- Creating info boxes

Usage:
    import streamlit as st
    from ui.components.styling import apply_custom_css, status_badge, colored_metric

    # Apply CSS at the start of your page
    apply_custom_css()

    # Use helper functions to create styled components
    st.markdown(status_badge("success", "Data Loaded"), unsafe_allow_html=True)
    st.markdown(colored_metric("Total Cost", "$12,345.67", "primary"), unsafe_allow_html=True)
"""

from pathlib import Path
from typing import Literal, Optional
import streamlit as st

# Type definitions for component variants
StatusType = Literal["success", "info", "warning", "error", "neutral"]
ColorType = Literal["primary", "secondary", "accent", "success", "warning", "error"]
HeaderLevel = Literal[1, 2, 3]


def apply_custom_css() -> None:
    """Load and inject custom CSS from ui/assets/styles.css into the Streamlit app.

    This function should be called once at the start of each page to apply
    the custom design system styles.

    Example:
        >>> apply_custom_css()
    """
    css_file = Path(__file__).parent.parent / "assets" / "styles.css"

    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"⚠️ CSS file not found at {css_file}")


def status_badge(
    status: StatusType,
    label: str,
    count: Optional[int] = None,
    icon: Optional[str] = None
) -> str:
    """Generate a styled status badge HTML component.

    Args:
        status: Badge variant - "success", "info", "warning", "error", or "neutral"
        label: Text to display in the badge
        count: Optional count to display in a pill (e.g., number of errors)
        icon: Optional emoji or icon to display before the label

    Returns:
        HTML string for the status badge

    Example:
        >>> st.markdown(status_badge("success", "Data Loaded", icon="✅"), unsafe_allow_html=True)
        >>> st.markdown(status_badge("error", "Infeasible", count=3, icon="❌"), unsafe_allow_html=True)
    """
    icon_html = f"{icon} " if icon else ""
    count_html = f'<span class="badge-count">{count}</span>' if count is not None else ""

    return f'''
    <div class="status-badge status-badge-{status}">
        {icon_html}{label}{count_html}
    </div>
    '''


def colored_metric(
    label: str,
    value: str,
    color: ColorType = "primary",
    delta: Optional[str] = None,
    delta_positive: bool = True
) -> str:
    """Generate a colored metric card HTML component.

    Args:
        label: Metric label (e.g., "Total Cost")
        value: Metric value (e.g., "$12,345.67")
        color: Border color - "primary", "secondary", "accent", "success", "warning", "error"
        delta: Optional delta/change value to display (e.g., "+5.2%")
        delta_positive: Whether delta is positive (green) or negative (red)

    Returns:
        HTML string for the colored metric card

    Example:
        >>> st.markdown(colored_metric("Total Cost", "$12,345", "primary"), unsafe_allow_html=True)
        >>> st.markdown(colored_metric("Efficiency", "94.2%", "success", "+2.1%"), unsafe_allow_html=True)
    """
    delta_class = "metric-delta-positive" if delta_positive else "metric-delta-negative"
    delta_html = f'<div class="{delta_class}">{delta}</div>' if delta else ""

    return f'''
    <div class="metric-card metric-card-{color}">
        <div class="metric-label">{label}</div>
        <div class="metric-value-large">{value}</div>
        {delta_html}
    </div>
    '''


def section_header(
    text: str,
    level: HeaderLevel = 1,
    icon: Optional[str] = None
) -> str:
    """Generate a styled section header HTML component.

    Args:
        text: Header text
        level: Header level - 1 (page title), 2 (section), 3 (subsection)
        icon: Optional emoji or icon to display before the text

    Returns:
        HTML string for the styled header

    Example:
        >>> st.markdown(section_header("Production Schedule", level=1, icon="📦"), unsafe_allow_html=True)
        >>> st.markdown(section_header("Daily Breakdown", level=2), unsafe_allow_html=True)
    """
    class_map = {
        1: "page-title",
        2: "section-header",
        3: "subsection-header"
    }

    icon_html = f"{icon} " if icon else ""
    css_class = class_map.get(level, "section-header")

    return f'<div class="{css_class}">{icon_html}{text}</div>'


def info_box(
    content: str,
    box_type: StatusType = "info",
    title: Optional[str] = None
) -> str:
    """Generate a styled info box HTML component.

    Args:
        content: Main content text (supports HTML)
        box_type: Box variant - "success", "info", "warning", "error"
        title: Optional title to display above content

    Returns:
        HTML string for the info box

    Example:
        >>> st.markdown(info_box("Planning complete!", "success", "✅ Success"), unsafe_allow_html=True)
        >>> st.markdown(info_box("Check data quality", "warning", "⚠️ Warning"), unsafe_allow_html=True)
    """
    # Map status type to box class
    box_class_map = {
        "success": "success-box",
        "info": "info-box",
        "warning": "warning-box",
        "error": "error-box",
        "neutral": "info-box"
    }

    box_class = box_class_map.get(box_type, "info-box")
    title_html = f'<div style="font-weight: 600; margin-bottom: 8px;">{title}</div>' if title else ""

    return f'''
    <div class="{box_class}">
        {title_html}
        <div>{content}</div>
    </div>
    '''


def phase_card(
    title: str,
    items: list[str],
    status: Literal["complete", "in_progress", "planned"] = "planned",
    icon: Optional[str] = None
) -> str:
    """Generate a styled phase status card HTML component.

    Args:
        title: Phase title (e.g., "Phase 1: Foundation")
        items: List of items/features in this phase
        status: Phase status - "complete", "in_progress", or "planned"
        icon: Optional emoji or icon for the phase

    Returns:
        HTML string for the phase card

    Example:
        >>> items = ["✅ Data models", "✅ Excel parsers", "✅ Tests passing"]
        >>> st.markdown(phase_card("Phase 1: Foundation", items, "complete", "✅"), unsafe_allow_html=True)
    """
    icon_html = f"{icon} " if icon else ""
    items_html = "\n".join([f"<li>{item}</li>" for item in items])

    return f'''
    <div class="phase-card phase-card-{status}">
        <div class="phase-title">{icon_html}{title}</div>
        <ul class="phase-checklist">
            {items_html}
        </ul>
    </div>
    '''


def metric_row(metrics: list[dict]) -> str:
    """Generate a row of metric cards with consistent styling.

    Args:
        metrics: List of metric dictionaries with keys:
            - label: Metric label
            - value: Metric value
            - color: Optional color (default "primary")
            - delta: Optional delta value
            - delta_positive: Optional delta direction (default True)

    Returns:
        HTML string for a row of metrics

    Example:
        >>> metrics = [
        ...     {"label": "Total Cost", "value": "$12,345", "color": "primary"},
        ...     {"label": "Efficiency", "value": "94.2%", "color": "success", "delta": "+2.1%"}
        ... ]
        >>> st.markdown(metric_row(metrics), unsafe_allow_html=True)
    """
    metric_cards = []
    for m in metrics:
        card = colored_metric(
            label=m["label"],
            value=m["value"],
            color=m.get("color", "primary"),
            delta=m.get("delta"),
            delta_positive=m.get("delta_positive", True)
        )
        metric_cards.append(card)

    # Create a flex container
    cards_html = "\n".join(metric_cards)
    return f'''
    <div style="display: flex; gap: 16px; margin: 16px 0;">
        {cards_html}
    </div>
    '''


def create_card(
    content: str,
    hover: bool = False,
    padding: str = "lg"
) -> str:
    """Generate a styled card container HTML component.

    Args:
        content: HTML content to wrap in the card
        hover: Whether to apply hover effect (lift on hover)
        padding: Padding size - "sm", "md", or "lg"

    Returns:
        HTML string for the card

    Example:
        >>> content = "<h3>Title</h3><p>Content goes here</p>"
        >>> st.markdown(create_card(content, hover=True), unsafe_allow_html=True)
    """
    hover_class = " card-hover" if hover else ""
    padding_map = {"sm": "8px", "md": "16px", "lg": "24px"}
    padding_value = padding_map.get(padding, "16px")

    return f'''
    <div class="card{hover_class}" style="padding: {padding_value};">
        {content}
    </div>
    '''


def status_icon(status: StatusType, size: str = "16px") -> str:
    """Generate a status icon (colored circle).

    Args:
        status: Status variant - "success", "info", "warning", "error", "neutral"
        size: Icon size (CSS size value)

    Returns:
        HTML string for the status icon

    Example:
        >>> st.markdown(status_icon("success") + " Operation successful", unsafe_allow_html=True)
    """
    color_map = {
        "success": "#43A047",
        "info": "#1E88E5",
        "warning": "#FB8C00",
        "error": "#E53935",
        "neutral": "#757575"
    }

    color = color_map.get(status, "#757575")

    return f'''
    <span style="
        display: inline-block;
        width: {size};
        height: {size};
        background-color: {color};
        border-radius: 50%;
        margin-right: 6px;
        vertical-align: middle;
    "></span>
    '''


def progress_bar(
    value: float,
    max_value: float = 100.0,
    color: ColorType = "primary",
    height: str = "8px",
    show_label: bool = True
) -> str:
    """Generate a styled progress bar HTML component.

    Args:
        value: Current progress value
        max_value: Maximum value (default 100.0 for percentages)
        color: Bar color - "primary", "secondary", "accent", "success", "warning", "error"
        height: Bar height (CSS size value)
        show_label: Whether to show percentage label

    Returns:
        HTML string for the progress bar

    Example:
        >>> st.markdown(progress_bar(75, color="success"), unsafe_allow_html=True)
        >>> st.markdown(progress_bar(3, max_value=10, color="warning", show_label=True), unsafe_allow_html=True)
    """
    color_map = {
        "primary": "#1E88E5",
        "secondary": "#43A047",
        "accent": "#FB8C00",
        "success": "#43A047",
        "warning": "#FB8C00",
        "error": "#E53935"
    }

    bar_color = color_map.get(color, "#1E88E5")
    percentage = (value / max_value) * 100 if max_value > 0 else 0
    percentage = min(100, max(0, percentage))  # Clamp to 0-100

    label_html = f'<div style="font-size: 12px; color: #757575; margin-top: 4px;">{percentage:.1f}%</div>' if show_label else ""

    return f'''
    <div style="width: 100%;">
        <div style="
            width: 100%;
            height: {height};
            background-color: #E0E0E0;
            border-radius: 4px;
            overflow: hidden;
        ">
            <div style="
                width: {percentage}%;
                height: 100%;
                background-color: {bar_color};
                transition: width 0.3s ease;
            "></div>
        </div>
        {label_html}
    </div>
    '''


# Convenience functions for common use cases

def success_badge(label: str, count: Optional[int] = None) -> str:
    """Shortcut for creating a success status badge."""
    return status_badge("success", label, count, icon="✅")


def warning_badge(label: str, count: Optional[int] = None) -> str:
    """Shortcut for creating a warning status badge."""
    return status_badge("warning", label, count, icon="⚠️")


def error_badge(label: str, count: Optional[int] = None) -> str:
    """Shortcut for creating an error status badge."""
    return status_badge("error", label, count, icon="❌")


def info_badge(label: str, count: Optional[int] = None) -> str:
    """Shortcut for creating an info status badge."""
    return status_badge("info", label, count, icon="ℹ️")
