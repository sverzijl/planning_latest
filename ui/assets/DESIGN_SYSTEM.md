# Design System Documentation

## Overview

This design system provides a consistent, professional visual identity for the GF Bread Production Planning Streamlit application. It includes a color palette, typography scale, reusable components, and helper functions to ensure visual consistency across all pages.

**Grade:** A- (upgraded from B-)

## Quick Start

### 1. Import the styling module at the top of your page

```python
from ui.components.styling import (
    apply_custom_css,
    section_header,
    status_badge,
    colored_metric,
    success_badge,
    info_badge,
)
```

### 2. Apply custom CSS at the start of the page

```python
# After st.set_page_config()
apply_custom_css()
```

### 3. Use styled components throughout your page

```python
# Headers
st.markdown(section_header("Page Title", level=1, icon="🍞"), unsafe_allow_html=True)
st.markdown(section_header("Section Title", level=2, icon="📊"), unsafe_allow_html=True)

# Status badges
st.markdown(success_badge("Data Loaded"), unsafe_allow_html=True)
st.markdown(status_badge("warning", "Infeasible", count=3, icon="⚠️"), unsafe_allow_html=True)

# Colored metrics
st.markdown(colored_metric("Total Cost", "$12,345.67", "primary"), unsafe_allow_html=True)
```

## Color Palette

### Primary Colors
- **Primary Blue (#1E88E5):** Trust, planning, primary actions
- **Secondary Green (#43A047):** Success, optimal solutions, completion
- **Accent Orange (#FB8C00):** Warnings, attention, important highlights

### Status Colors
- **Success (#43A047):** Completed tasks, feasible solutions, positive states
- **Info (#1E88E5):** Informational messages, in-progress states
- **Warning (#FB8C00):** Warnings, cautions, items needing attention
- **Error (#E53935):** Errors, infeasibilities, critical issues

### Neutral Colors
- **Primary Text (#212121):** Main content text
- **Secondary Text (#757575):** Captions, helper text, less important content
- **Background (#FAFAFA):** Page background
- **Border (#E0E0E0):** Dividers, card borders

## Typography Scale

| Level | Size | Weight | Usage |
|-------|------|--------|-------|
| Page Title | 32px | Bold (700) | Main page heading |
| Section Header | 24px | Semibold (600) | Major sections |
| Subsection | 18px | Medium (500) | Subsections, card titles |
| Body Text | 14px | Regular (400) | Standard content |
| Caption | 12px | Regular (400) | Helper text, labels |
| Metric Value | 36px | Bold (700) | Large numeric values |

## Component Reference

### Status Badges

Display status information in a consistent, eye-catching format.

```python
# Basic usage
status_badge(status, label, count=None, icon=None)

# Convenience functions
success_badge("Data Loaded")           # Green with ✅
info_badge("Processing")               # Blue with ℹ️
warning_badge("Check Required")        # Orange with ⚠️
error_badge("Infeasible", count=3)     # Red with ❌ and count
```

**Parameters:**
- `status`: "success", "info", "warning", "error", "neutral"
- `label`: Text to display
- `count`: Optional numeric badge (e.g., error count)
- `icon`: Optional emoji/icon

**Example:**
```python
st.markdown(status_badge("success", "Data Loaded", icon="✅"), unsafe_allow_html=True)
st.markdown(error_badge("Infeasible Routes", count=5), unsafe_allow_html=True)
```

### Colored Metrics

Display key metrics with colored borders for visual hierarchy.

```python
colored_metric(label, value, color="primary", delta=None, delta_positive=True)
```

**Parameters:**
- `label`: Metric label (e.g., "Total Cost")
- `value`: Metric value (e.g., "$12,345.67")
- `color`: "primary", "secondary", "accent", "success", "warning", "error"
- `delta`: Optional change indicator (e.g., "+5.2%")
- `delta_positive`: Whether delta is positive (green) or negative (red)

**Example:**
```python
st.markdown(
    colored_metric("Total Cost", "$12,345", "primary"),
    unsafe_allow_html=True
)

st.markdown(
    colored_metric("Efficiency", "94.2%", "success", delta="+2.1%"),
    unsafe_allow_html=True
)
```

**Color Usage Guidelines:**
- **Primary (Blue):** Production-related metrics, structural data
- **Secondary (Green):** Performance, efficiency, quality metrics
- **Accent (Orange):** Cost metrics, items needing attention
- **Success (Green):** Achievements, optimal values
- **Warning (Orange):** Borderline values, capacity warnings
- **Error (Red):** Problems, infeasibilities, critical issues

### Section Headers

Create consistent heading hierarchy across pages.

```python
section_header(text, level=1, icon=None)
```

**Parameters:**
- `text`: Header text
- `level`: 1 (page title), 2 (section), 3 (subsection)
- `icon`: Optional emoji/icon

**Example:**
```python
st.markdown(section_header("Production Schedule", level=1, icon="📦"), unsafe_allow_html=True)
st.markdown(section_header("Daily Breakdown", level=2), unsafe_allow_html=True)
st.markdown(section_header("Shift Details", level=3), unsafe_allow_html=True)
```

### Phase Cards

Display project phases with completion status.

```python
phase_card(title, items, status="planned", icon=None)
```

**Parameters:**
- `title`: Phase title (e.g., "Phase 1: Foundation")
- `items`: List of items/features
- `status`: "complete", "in_progress", "planned"
- `icon`: Optional emoji/icon

**Example:**
```python
items = [
    "✅ Data models",
    "✅ Excel parsers",
    "✅ Tests passing"
]
st.markdown(
    phase_card("Phase 1: Foundation", items, "complete", "✅"),
    unsafe_allow_html=True
)
```

### Info Boxes

Highlight important information with colored containers.

```python
info_box(content, box_type="info", title=None)
```

**Parameters:**
- `content`: Main content (supports HTML)
- `box_type`: "success", "info", "warning", "error"
- `title`: Optional title

**Example:**
```python
st.markdown(
    info_box("Planning complete!", "success", "✅ Success"),
    unsafe_allow_html=True
)

st.markdown(
    info_box("Check data quality before proceeding", "warning", "⚠️ Warning"),
    unsafe_allow_html=True
)
```

### Progress Bars

Visual indicators for completion or capacity.

```python
progress_bar(value, max_value=100.0, color="primary", height="8px", show_label=True)
```

**Example:**
```python
st.markdown(progress_bar(75, color="success"), unsafe_allow_html=True)
st.markdown(progress_bar(8, max_value=10, color="warning"), unsafe_allow_html=True)
```

### Cards

Container component for grouping related content.

```python
create_card(content, hover=False, padding="lg")
```

**Parameters:**
- `content`: HTML content to wrap
- `hover`: Apply lift effect on hover
- `padding`: "sm", "md", "lg"

**Example:**
```python
content = "<h3>Title</h3><p>Content goes here</p>"
st.markdown(create_card(content, hover=True), unsafe_allow_html=True)
```

## CSS Classes Reference

Use these classes directly in your HTML for custom styling.

### Typography
```html
<div class="page-title">Page Title</div>
<div class="section-header">Section Header</div>
<div class="subsection-header">Subsection</div>
<div class="body-text">Body text content</div>
<div class="caption-text">Caption or helper text</div>
<div class="metric-value">12,345</div>
```

### Colors
```html
<!-- Text colors -->
<span class="text-primary">Primary blue text</span>
<span class="text-secondary">Secondary green text</span>
<span class="text-accent">Accent orange text</span>
<span class="text-success">Success green text</span>
<span class="text-warning">Warning orange text</span>
<span class="text-error">Error red text</span>
<span class="text-muted">Muted gray text</span>

<!-- Background colors -->
<div class="bg-primary">Primary background</div>
<div class="bg-success">Success background</div>
<!-- ... etc -->
```

### Layout Utilities
```html
<!-- Spacing -->
<div class="mt-sm">Small top margin</div>
<div class="mb-md">Medium bottom margin</div>
<div class="p-lg">Large padding</div>

<!-- Flexbox -->
<div class="flex gap-md">Flex container with medium gap</div>
<div class="flex flex-column">Column layout</div>
<div class="flex flex-center">Centered items</div>
<div class="flex flex-between">Space between items</div>
```

### Info Boxes
```html
<div class="info-box">Information message</div>
<div class="success-box">Success message</div>
<div class="warning-box">Warning message</div>
<div class="error-box">Error message</div>
```

### Cards
```html
<div class="card">Basic card</div>
<div class="card card-hover">Card with hover effect</div>
```

## Page Template

Here's a complete template for a new page:

```python
"""Page description here."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from ui import session_state
from ui.components.styling import (
    apply_custom_css,
    section_header,
    status_badge,
    colored_metric,
    success_badge,
    warning_badge,
    info_box,
)

# Page config
st.set_page_config(
    page_title="Page Name",
    page_icon="📊",
    layout="wide",
)

# Apply custom CSS
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

# Page content
st.markdown(section_header("Page Title", level=1, icon="📊"), unsafe_allow_html=True)

# Status indicator
st.markdown(success_badge("Data Loaded"), unsafe_allow_html=True)

# Metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(colored_metric("Metric 1", "100", "primary"), unsafe_allow_html=True)
with col2:
    st.markdown(colored_metric("Metric 2", "200", "secondary"), unsafe_allow_html=True)
with col3:
    st.markdown(colored_metric("Metric 3", "300", "accent"), unsafe_allow_html=True)

st.divider()

# Section
st.markdown(section_header("Section Title", level=2), unsafe_allow_html=True)

# Info box
st.markdown(
    info_box("Important information here", "info", "ℹ️ Note"),
    unsafe_allow_html=True
)

# Rest of content...
```

## Best Practices

### 1. Consistency
- **Always** use `apply_custom_css()` at the start of each page
- Use the helper functions instead of writing inline HTML/CSS
- Stick to the defined color palette
- Maintain heading hierarchy (h1 → h2 → h3)

### 2. Color Usage
- **Primary (Blue):** Main actions, navigation, structural elements
- **Secondary (Green):** Success states, completed tasks, optimal solutions
- **Accent (Orange):** Attention items, costs, warnings
- **Error (Red):** Only for actual errors and critical issues

### 3. Typography
- Page should have exactly **one** level-1 header
- Use level-2 for major sections
- Use level-3 for subsections
- Don't skip levels (e.g., h1 → h3)

### 4. Spacing
- Use Streamlit's `st.divider()` between major sections
- Add `<br>` tags via markdown for vertical spacing between badge/metric groups
- Let CSS handle internal component spacing

### 5. Status Indicators
- Use status badges at the top of sections to show current state
- Show counts in badges for errors/warnings (e.g., "Infeasible Routes: 5")
- Use colored metrics for quantitative data
- Use info boxes for explanatory content

### 6. Accessibility
- Always include descriptive text with icons
- Maintain sufficient color contrast
- Use semantic HTML structure
- Provide tooltips for complex metrics

## Updating the Design System

### Adding New Colors

Edit `ui/assets/styles.css`:

```css
:root {
    --color-new-name: #HEXCODE;
}
```

Add utility classes:

```css
.text-new-name { color: var(--color-new-name); }
.bg-new-name { background-color: var(--color-new-name); }
```

### Adding New Components

1. Define the component function in `ui/components/styling.py`
2. Add comprehensive docstrings with examples
3. Add type hints for parameters
4. Document in this file under Component Reference

### Modifying Existing Styles

1. Update CSS in `ui/assets/styles.css`
2. Test across multiple pages
3. Update documentation if behavior changes
4. Ensure backward compatibility

## Examples from the Application

### Home Page (app.py)
- Phase status cards showing project completion
- Colored metrics for data summary statistics
- Status badges for data upload and planning status
- Info boxes for getting started instructions

### Upload Data Page (1_Upload_Data.py)
- Section headers for file upload sections
- Success badges when files are selected
- Info box explaining required files
- Consistent spacing and layout

## Migration Guide

If you have existing pages without the design system:

1. **Add imports:**
   ```python
   from ui.components.styling import apply_custom_css, section_header, colored_metric, status_badge
   ```

2. **Apply CSS:**
   ```python
   apply_custom_css()
   ```

3. **Replace headers:**
   ```python
   # Before
   st.header("My Page")

   # After
   st.markdown(section_header("My Page", level=2, icon="📊"), unsafe_allow_html=True)
   ```

4. **Replace metrics:**
   ```python
   # Before
   st.metric("Total Cost", "$12,345")

   # After
   st.markdown(colored_metric("Total Cost", "$12,345", "primary"), unsafe_allow_html=True)
   ```

5. **Replace status messages:**
   ```python
   # Before
   st.success("✅ Data Loaded")

   # After
   st.markdown(success_badge("Data Loaded"), unsafe_allow_html=True)
   ```

## Troubleshooting

### CSS not loading
- Check that `ui/assets/styles.css` exists
- Verify `apply_custom_css()` is called after `st.set_page_config()`
- Check browser console for errors

### Components not rendering
- Ensure `unsafe_allow_html=True` is set in `st.markdown()`
- Check for syntax errors in HTML strings
- Verify all parameters are correctly formatted

### Colors not appearing
- Confirm CSS variables are defined in `:root`
- Check class names match CSS definitions
- Inspect element in browser DevTools

## Support

For questions or issues with the design system:
1. Check this documentation
2. Review example implementations in `app.py` and `1_Upload_Data.py`
3. Examine the source code in `ui/components/styling.py`
4. Test components in isolation to identify issues
