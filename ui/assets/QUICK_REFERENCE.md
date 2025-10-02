# Design System Quick Reference

## Setup (Every Page)

```python
from ui.components.styling import (
    apply_custom_css,
    section_header,
    status_badge,
    colored_metric,
    success_badge,
    warning_badge,
)

# After st.set_page_config()
apply_custom_css()
```

## Common Patterns

### Headers
```python
# Page title (level 1)
st.markdown(section_header("Page Title", level=1, icon="📊"), unsafe_allow_html=True)

# Section (level 2)
st.markdown(section_header("Section Title", level=2), unsafe_allow_html=True)

# Subsection (level 3)
st.markdown(section_header("Subsection", level=3), unsafe_allow_html=True)
```

### Status Badges
```python
# Success
st.markdown(success_badge("Data Loaded"), unsafe_allow_html=True)

# Warning
st.markdown(warning_badge("Check Required", count=5), unsafe_allow_html=True)

# Error
st.markdown(error_badge("Infeasible", count=3), unsafe_allow_html=True)

# Info
st.markdown(info_badge("Processing"), unsafe_allow_html=True)

# Custom
st.markdown(status_badge("info", "Custom Status", icon="🔔"), unsafe_allow_html=True)
```

### Metrics
```python
# Single metric
st.markdown(
    colored_metric("Total Cost", "$12,345", "primary"),
    unsafe_allow_html=True
)

# Metric with delta
st.markdown(
    colored_metric("Efficiency", "94.2%", "success", delta="+2.1%"),
    unsafe_allow_html=True
)

# Row of metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(colored_metric("Metric 1", "100", "primary"), unsafe_allow_html=True)
with col2:
    st.markdown(colored_metric("Metric 2", "200", "secondary"), unsafe_allow_html=True)
with col3:
    st.markdown(colored_metric("Metric 3", "300", "accent"), unsafe_allow_html=True)
```

### Info Boxes
```python
st.markdown("""
<div class="info-box">
    <strong>Note:</strong> This is important information.
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="success-box">
    <strong>Success:</strong> Operation completed.
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="warning-box">
    <strong>Warning:</strong> Check this before proceeding.
</div>
""", unsafe_allow_html=True)
```

### Phase Cards
```python
items = ["✅ Item 1", "✅ Item 2", "Item 3"]
st.markdown(
    phase_card("Phase 1: Title", items, status="complete", icon="✅"),
    unsafe_allow_html=True
)
```

## Color Guide

| Use Case | Color | Example |
|----------|-------|---------|
| Production metrics | `primary` | Production batches, units |
| Performance metrics | `secondary` | Efficiency, quality |
| Cost metrics | `accent` | Total cost, cost per unit |
| Success states | `success` | Feasible, complete |
| Warnings | `warning` | Capacity limits, checks needed |
| Errors | `error` | Infeasible, failures |

## Spacing

```python
# Add vertical space
st.markdown("<br>", unsafe_allow_html=True)

# Divider between sections
st.divider()

# Use columns for horizontal layout
col1, col2, col3 = st.columns(3)
```

## HTML Classes

```html
<!-- Typography -->
<div class="page-title">Title</div>
<div class="section-header">Header</div>
<div class="body-text">Text</div>
<div class="caption-text">Caption</div>

<!-- Colors -->
<span class="text-primary">Blue text</span>
<span class="text-success">Green text</span>
<span class="text-warning">Orange text</span>
<span class="text-error">Red text</span>

<!-- Boxes -->
<div class="info-box">Info</div>
<div class="success-box">Success</div>
<div class="warning-box">Warning</div>
<div class="error-box">Error</div>

<!-- Card -->
<div class="card">Content</div>
```
