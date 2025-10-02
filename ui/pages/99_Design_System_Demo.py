"""Design System Component Showcase

This page demonstrates all available design system components and their usage.
Use this as a reference when building new pages.
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from ui.components.styling import (
    apply_custom_css,
    section_header,
    status_badge,
    colored_metric,
    success_badge,
    warning_badge,
    error_badge,
    info_badge,
    info_box,
    phase_card,
    progress_bar,
    create_card,
    status_icon,
)

# Page config
st.set_page_config(
    page_title="Design System Demo",
    page_icon="🎨",
    layout="wide",
)

# Apply custom CSS
apply_custom_css()

# Page title
st.markdown(section_header("Design System Component Showcase", level=1, icon="🎨"), unsafe_allow_html=True)

st.markdown("""
<div class="body-text">
This page demonstrates all available components from the design system.
Use these examples as reference when building new pages.
</div>
""", unsafe_allow_html=True)

st.divider()

# ===== HEADERS =====
st.markdown(section_header("Headers & Typography", level=2, icon="📝"), unsafe_allow_html=True)

st.markdown(section_header("This is a Level 1 Header (Page Title)", level=1), unsafe_allow_html=True)
st.code('section_header("This is a Level 1 Header (Page Title)", level=1)')

st.markdown(section_header("This is a Level 2 Header (Section)", level=2), unsafe_allow_html=True)
st.code('section_header("This is a Level 2 Header (Section)", level=2)')

st.markdown(section_header("This is a Level 3 Header (Subsection)", level=3), unsafe_allow_html=True)
st.code('section_header("This is a Level 3 Header (Subsection)", level=3)')

st.markdown(section_header("Header with Icon", level=2, icon="🚀"), unsafe_allow_html=True)
st.code('section_header("Header with Icon", level=2, icon="🚀")')

st.divider()

# ===== STATUS BADGES =====
st.markdown(section_header("Status Badges", level=2, icon="🏷️"), unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Success Badge:**", unsafe_allow_html=True)
    st.markdown(success_badge("Data Loaded"), unsafe_allow_html=True)
    st.code('success_badge("Data Loaded")')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Info Badge:**", unsafe_allow_html=True)
    st.markdown(info_badge("Processing"), unsafe_allow_html=True)
    st.code('info_badge("Processing")')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Warning Badge:**", unsafe_allow_html=True)
    st.markdown(warning_badge("Check Required"), unsafe_allow_html=True)
    st.code('warning_badge("Check Required")')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Error Badge:**", unsafe_allow_html=True)
    st.markdown(error_badge("Infeasible"), unsafe_allow_html=True)
    st.code('error_badge("Infeasible")')

with col2:
    st.markdown("**Badge with Count:**", unsafe_allow_html=True)
    st.markdown(warning_badge("Warnings", count=5), unsafe_allow_html=True)
    st.code('warning_badge("Warnings", count=5)')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Custom Badge:**", unsafe_allow_html=True)
    st.markdown(status_badge("neutral", "Custom Status", icon="🔔"), unsafe_allow_html=True)
    st.code('status_badge("neutral", "Custom Status", icon="🔔")')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**All Badge Types:**", unsafe_allow_html=True)
    st.markdown(status_badge("success", "Success"), unsafe_allow_html=True)
    st.markdown(status_badge("info", "Info"), unsafe_allow_html=True)
    st.markdown(status_badge("warning", "Warning"), unsafe_allow_html=True)
    st.markdown(status_badge("error", "Error"), unsafe_allow_html=True)
    st.markdown(status_badge("neutral", "Neutral"), unsafe_allow_html=True)

st.divider()

# ===== COLORED METRICS =====
st.markdown(section_header("Colored Metrics", level=2, icon="📊"), unsafe_allow_html=True)

st.markdown("**Metric Cards with Different Colors:**", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(colored_metric("Primary Metric", "12,345", "primary"), unsafe_allow_html=True)
    st.code('colored_metric("Primary Metric", "12,345", "primary")')

with col2:
    st.markdown(colored_metric("Secondary Metric", "94.2%", "secondary"), unsafe_allow_html=True)
    st.code('colored_metric("Secondary Metric", "94.2%", "secondary")')

with col3:
    st.markdown(colored_metric("Accent Metric", "$45,678", "accent"), unsafe_allow_html=True)
    st.code('colored_metric("Accent Metric", "$45,678", "accent")')

st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(colored_metric("Success Metric", "98.5%", "success"), unsafe_allow_html=True)
    st.code('colored_metric("Success Metric", "98.5%", "success")')

with col2:
    st.markdown(colored_metric("Warning Metric", "75%", "warning"), unsafe_allow_html=True)
    st.code('colored_metric("Warning Metric", "75%", "warning")')

with col3:
    st.markdown(colored_metric("Error Metric", "3", "error"), unsafe_allow_html=True)
    st.code('colored_metric("Error Metric", "3", "error")')

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("**Metrics with Delta:**", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.markdown(
        colored_metric("Efficiency", "94.2%", "success", delta="+2.1%", delta_positive=True),
        unsafe_allow_html=True
    )
    st.code('colored_metric("Efficiency", "94.2%", "success", delta="+2.1%", delta_positive=True)')

with col2:
    st.markdown(
        colored_metric("Cost Overrun", "$1,234", "error", delta="-5.3%", delta_positive=False),
        unsafe_allow_html=True
    )
    st.code('colored_metric("Cost Overrun", "$1,234", "error", delta="-5.3%", delta_positive=False)')

st.divider()

# ===== INFO BOXES =====
st.markdown(section_header("Info Boxes", level=2, icon="💬"), unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        info_box("This is an information message with important details.", "info", "ℹ️ Information"),
        unsafe_allow_html=True
    )
    st.code('info_box("Message text", "info", "ℹ️ Information")')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        info_box("Operation completed successfully!", "success", "✅ Success"),
        unsafe_allow_html=True
    )
    st.code('info_box("Message text", "success", "✅ Success")')

with col2:
    st.markdown(
        info_box("Please review these items before continuing.", "warning", "⚠️ Warning"),
        unsafe_allow_html=True
    )
    st.code('info_box("Message text", "warning", "⚠️ Warning")')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        info_box("An error occurred during processing.", "error", "❌ Error"),
        unsafe_allow_html=True
    )
    st.code('info_box("Message text", "error", "❌ Error")')

st.divider()

# ===== PHASE CARDS =====
st.markdown(section_header("Phase Status Cards", level=2, icon="📋"), unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    items = ["✅ Task 1 complete", "✅ Task 2 complete", "✅ Task 3 complete"]
    st.markdown(phase_card("Complete Phase", items, "complete", "✅"), unsafe_allow_html=True)
    st.code('phase_card("Complete Phase", items, "complete", "✅")')

with col2:
    items = ["✅ Task 1 done", "⚡ Task 2 in progress", "Task 3 pending"]
    st.markdown(phase_card("In Progress Phase", items, "in_progress", "⚡"), unsafe_allow_html=True)
    st.code('phase_card("In Progress Phase", items, "in_progress", "⚡")')

with col3:
    items = ["Task 1", "Task 2", "Task 3"]
    st.markdown(phase_card("Planned Phase", items, "planned", "🔜"), unsafe_allow_html=True)
    st.code('phase_card("Planned Phase", items, "planned", "🔜")')

st.divider()

# ===== PROGRESS BARS =====
st.markdown(section_header("Progress Bars", level=2, icon="📈"), unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Primary Progress (75%):**", unsafe_allow_html=True)
    st.markdown(progress_bar(75, color="primary"), unsafe_allow_html=True)
    st.code('progress_bar(75, color="primary")')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Success Progress (100%):**", unsafe_allow_html=True)
    st.markdown(progress_bar(100, color="success"), unsafe_allow_html=True)
    st.code('progress_bar(100, color="success")')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Warning Progress (85%):**", unsafe_allow_html=True)
    st.markdown(progress_bar(85, color="warning"), unsafe_allow_html=True)
    st.code('progress_bar(85, color="warning")')

with col2:
    st.markdown("**Custom Max Value (8/10):**", unsafe_allow_html=True)
    st.markdown(progress_bar(8, max_value=10, color="secondary"), unsafe_allow_html=True)
    st.code('progress_bar(8, max_value=10, color="secondary")')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Without Label:**", unsafe_allow_html=True)
    st.markdown(progress_bar(45, color="accent", show_label=False), unsafe_allow_html=True)
    st.code('progress_bar(45, color="accent", show_label=False)')

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("**Custom Height:**", unsafe_allow_html=True)
    st.markdown(progress_bar(60, color="error", height="16px"), unsafe_allow_html=True)
    st.code('progress_bar(60, color="error", height="16px")')

st.divider()

# ===== CARDS =====
st.markdown(section_header("Cards", level=2, icon="🗂️"), unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    content = """
    <div class="subsection-header">Card Title</div>
    <div class="body-text">This is a basic card container with standard padding.</div>
    """
    st.markdown(create_card(content), unsafe_allow_html=True)
    st.code('create_card(content)')

with col2:
    content = """
    <div class="subsection-header">Hover Card</div>
    <div class="body-text">This card has a hover effect. Try hovering over it!</div>
    """
    st.markdown(create_card(content, hover=True), unsafe_allow_html=True)
    st.code('create_card(content, hover=True)')

st.divider()

# ===== STATUS ICONS =====
st.markdown(section_header("Status Icons", level=2, icon="⚫"), unsafe_allow_html=True)

st.markdown("**Colored Status Circles:**", unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown(status_icon("success") + " Success status", unsafe_allow_html=True)
    st.markdown(status_icon("info") + " Info status", unsafe_allow_html=True)
    st.markdown(status_icon("warning") + " Warning status", unsafe_allow_html=True)

with col2:
    st.markdown(status_icon("error") + " Error status", unsafe_allow_html=True)
    st.markdown(status_icon("neutral") + " Neutral status", unsafe_allow_html=True)
    st.code('status_icon("success") + " Success status"')

st.divider()

# ===== COLOR PALETTE =====
st.markdown(section_header("Color Palette", level=2, icon="🎨"), unsafe_allow_html=True)

st.markdown("""
<div class="card">
    <div class="subsection-header">Design System Colors</div>
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 16px;">
        <div>
            <div style="background: #1E88E5; height: 60px; border-radius: 8px; margin-bottom: 8px;"></div>
            <div class="body-text"><strong>Primary Blue</strong></div>
            <div class="caption-text">#1E88E5</div>
            <div class="caption-text">Planning, Structure</div>
        </div>
        <div>
            <div style="background: #43A047; height: 60px; border-radius: 8px; margin-bottom: 8px;"></div>
            <div class="body-text"><strong>Secondary Green</strong></div>
            <div class="caption-text">#43A047</div>
            <div class="caption-text">Success, Performance</div>
        </div>
        <div>
            <div style="background: #FB8C00; height: 60px; border-radius: 8px; margin-bottom: 8px;"></div>
            <div class="body-text"><strong>Accent Orange</strong></div>
            <div class="caption-text">#FB8C00</div>
            <div class="caption-text">Costs, Warnings</div>
        </div>
        <div>
            <div style="background: #E53935; height: 60px; border-radius: 8px; margin-bottom: 8px;"></div>
            <div class="body-text"><strong>Error Red</strong></div>
            <div class="caption-text">#E53935</div>
            <div class="caption-text">Errors, Critical</div>
        </div>
        <div>
            <div style="background: #757575; height: 60px; border-radius: 8px; margin-bottom: 8px;"></div>
            <div class="body-text"><strong>Neutral Gray</strong></div>
            <div class="caption-text">#757575</div>
            <div class="caption-text">Secondary Text</div>
        </div>
        <div>
            <div style="background: #FAFAFA; height: 60px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #E0E0E0;"></div>
            <div class="body-text"><strong>Background</strong></div>
            <div class="caption-text">#FAFAFA</div>
            <div class="caption-text">Page Background</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

st.divider()

# ===== USAGE GUIDE =====
st.markdown(section_header("Quick Usage Guide", level=2, icon="📖"), unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
    <div style="font-weight: 600; margin-bottom: 12px;">📋 Getting Started</div>
    <ol style="margin: 0; padding-left: 20px; line-height: 1.8;">
        <li>Import styling functions at the top of your page</li>
        <li>Call <code>apply_custom_css()</code> after <code>st.set_page_config()</code></li>
        <li>Use styled components with <code>st.markdown(..., unsafe_allow_html=True)</code></li>
        <li>Refer to <code>ui/assets/DESIGN_SYSTEM.md</code> for complete documentation</li>
        <li>Check <code>ui/assets/QUICK_REFERENCE.md</code> for fast lookups</li>
    </ol>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

st.code("""
from ui.components.styling import (
    apply_custom_css,
    section_header,
    status_badge,
    colored_metric,
)

# Apply CSS
apply_custom_css()

# Use components
st.markdown(section_header("My Page", level=1, icon="📊"), unsafe_allow_html=True)
st.markdown(success_badge("Data Loaded"), unsafe_allow_html=True)
st.markdown(colored_metric("Total Cost", "$12,345", "primary"), unsafe_allow_html=True)
""", language="python")

st.divider()

# Footer
st.markdown("""
<div class="caption-text" style="text-align: center; margin-top: 32px;">
    Design System v1.0 • Work Package 1.1 • Professional UI/UX
</div>
""", unsafe_allow_html=True)
