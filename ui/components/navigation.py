"""Navigation components for breadcrumbs and page navigation."""

import streamlit as st


def render_breadcrumbs(current_page: str, current_tab: str = None):
    """Render breadcrumb navigation.

    Args:
        current_page: The current page name (e.g., "Data Management")
        current_tab: Optional current tab name (e.g., "Upload")
    """
    breadcrumbs = ["🏠 Home"]

    if current_page:
        breadcrumbs.append(f"/ {current_page}")

    if current_tab:
        breadcrumbs.append(f"/ {current_tab}")

    st.markdown(
        f"<div class='breadcrumb'>{' '.join(breadcrumbs)}</div>",
        unsafe_allow_html=True
    )


def render_quick_nav_card(icon: str, title: str, description: str, page_path: str, key: str = None):
    """Render a quick navigation card button.

    Args:
        icon: Emoji icon for the card
        title: Card title
        description: Brief description of the page
        page_path: Path to navigate to (e.g., "pages/1_Data.py")
        key: Optional unique key for the button
    """
    button_key = key or f"nav_{title.lower().replace(' ', '_')}"

    if st.button(f"{icon} {title}", use_container_width=True, key=button_key):
        st.switch_page(page_path)
    st.caption(description)


def check_data_required(redirect_to_upload: bool = True) -> bool:
    """Check if data is uploaded and optionally redirect to upload page.

    Args:
        redirect_to_upload: If True, show warning and redirect button when no data

    Returns:
        True if data is uploaded, False otherwise
    """
    from ui import session_state

    if not session_state.is_data_uploaded():
        if redirect_to_upload:
            st.warning("⚠️ No data loaded. Please upload data first.")
            if st.button("📤 Go to Data Upload", type="primary"):
                st.switch_page("pages/1_Data.py")
        return False
    return True


def check_planning_required(redirect_to_planning: bool = True) -> bool:
    """Check if planning has been run and optionally redirect to planning page.

    Args:
        redirect_to_planning: If True, show warning and redirect button when no planning

    Returns:
        True if planning is complete, False otherwise
    """
    from ui import session_state

    if not session_state.is_planning_complete() and not session_state.is_optimization_complete():
        if redirect_to_planning:
            st.info("ℹ️ No planning results available. Please run planning first.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🎯 Run Heuristic Planning", type="primary", use_container_width=True):
                    st.switch_page("pages/2_Planning.py")
            with col2:
                if st.button("⚡ Run Optimization", type="primary", use_container_width=True):
                    st.switch_page("pages/2_Planning.py")
        return False
    return True


def render_page_header(title: str, icon: str, subtitle: str = None, show_breadcrumbs: bool = True):
    """Render a consistent page header with optional breadcrumbs.

    Args:
        title: Page title
        icon: Emoji icon
        subtitle: Optional subtitle/caption
        show_breadcrumbs: Whether to show breadcrumb navigation
    """
    from ui.components.styling import apply_custom_css, section_header

    # Apply design system
    apply_custom_css()

    # Breadcrumbs
    if show_breadcrumbs:
        render_breadcrumbs(title)

    # Title
    st.markdown(section_header(title, level=1, icon=icon), unsafe_allow_html=True)

    # Subtitle
    if subtitle:
        st.caption(subtitle)
