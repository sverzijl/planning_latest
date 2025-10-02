"""Network visualization page."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from ui import session_state
from ui.components import render_network_graph, render_connectivity_matrix
from src.network import NetworkGraphBuilder

# Page config
st.set_page_config(
    page_title="Network Visualization",
    page_icon="🌐",
    layout="wide",
)

# Initialize session state
session_state.initialize_session_state()

st.header("🌐 Network Visualization")

# Check if data uploaded
if not session_state.is_data_uploaded():
    st.warning("⚠️ No data loaded. Please upload files first.")
    if st.button("📤 Go to Upload Page", type="primary"):
        st.switch_page("pages/1_Upload_Data.py")
    st.stop()

# Get data
data = session_state.get_parsed_data()

# Build graph
graph_builder = NetworkGraphBuilder(data['locations'], data['routes'])
graph = graph_builder.build_graph()

# Network statistics
st.subheader("📊 Network Statistics")

col1, col2, col3, col4 = st.columns(4)

manufacturing_nodes = graph_builder.get_manufacturing_nodes()
breadroom_nodes = graph_builder.get_breadroom_nodes()
hub_nodes = graph_builder.get_hub_nodes()

with col1:
    st.metric("Total Nodes", graph.number_of_nodes())
    st.metric("Manufacturing", len(manufacturing_nodes))

with col2:
    st.metric("Total Edges", graph.number_of_edges())
    st.metric("Hubs/Storage", len(hub_nodes))

with col3:
    st.metric("Breadrooms", len(breadroom_nodes))
    # Calculate average path length
    if manufacturing_nodes and breadroom_nodes:
        total_hops = 0
        count = 0
        for mfg in manufacturing_nodes:
            for br in breadroom_nodes:
                path_len = graph_builder.get_shortest_path_length(mfg, br)
                if path_len is not None:
                    total_hops += path_len
                    count += 1
        avg_hops = total_hops / count if count > 0 else 0
        st.metric("Avg Path Length", f"{avg_hops:.1f} hops")

with col4:
    # Connectivity check
    connected_pairs = 0
    total_pairs = len(manufacturing_nodes) * len(breadroom_nodes)
    for mfg in manufacturing_nodes:
        for br in breadroom_nodes:
            if graph_builder.is_reachable(mfg, br):
                connected_pairs += 1
    connectivity_pct = (connected_pairs / total_pairs * 100) if total_pairs > 0 else 0
    st.metric("Connectivity", f"{connectivity_pct:.0f}%")

st.divider()

# Visualizations
tab1, tab2, tab3 = st.tabs(["Network Graph", "Connectivity Matrix", "Location Details"])

with tab1:
    st.subheader("Interactive Network Graph")

    # Filters
    col1, col2 = st.columns(2)

    with col1:
        show_manufacturing = st.checkbox("Show Manufacturing", value=True)
        show_hubs = st.checkbox("Show Hubs/Storage", value=True)
        show_breadrooms = st.checkbox("Show Breadrooms", value=True)

    with col2:
        # Path highlighting (if planning complete)
        if session_state.is_planning_complete():
            highlight_routes = st.checkbox("Highlight Routes from Plan", value=False)
        else:
            highlight_routes = False

    st.divider()

    # Render graph
    fig = render_network_graph(
        graph_builder,
        title="Distribution Network",
        highlight_paths=None,  # TODO: Add path highlighting
        height=700,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption("""
    **Legend:**
    - 🔴 Red Square: Manufacturing site
    - 🔵 Cyan Diamond: Hub/Storage location
    - 🟢 Green Circle: Breadroom destination
    - Arrows: Routes with transit time and mode
    """)

with tab2:
    st.subheader("Connectivity Matrix")

    st.markdown("Shows which locations can reach which destinations through the network.")

    fig = render_connectivity_matrix(graph_builder)
    st.plotly_chart(fig, use_container_width=True)

    st.caption("✅ Blue cells indicate a route exists between origin and destination")

with tab3:
    st.subheader("Location Details")

    # Location selector
    all_locations = [loc.id for loc in data['locations']]
    selected_location = st.selectbox("Select Location", all_locations)

    if selected_location:
        # Find location
        location = next((loc for loc in data['locations'] if loc.id == selected_location), None)

        if location:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"**Name:** {location.name}")
                st.markdown(f"**ID:** {location.id}")
                st.markdown(f"**Type:** {location.type}")
                st.markdown(f"**Storage Mode:** {location.storage_mode}")

            with col2:
                if location.capacity:
                    st.markdown(f"**Capacity:** {location.capacity:,.0f} units")

                # Get successors (outgoing routes)
                successors = graph_builder.get_successors(selected_location)
                st.markdown(f"**Outgoing Routes:** {len(successors)}")
                if successors:
                    st.write(", ".join(successors))

                # Get predecessors (incoming routes)
                predecessors = graph_builder.get_predecessors(selected_location)
                st.markdown(f"**Incoming Routes:** {len(predecessors)}")
                if predecessors:
                    st.write(", ".join(predecessors))

st.divider()

# Navigation
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Data Summary", use_container_width=True):
        st.switch_page("pages/2_Data_Summary.py")

with col2:
    if st.button("Route Analysis →", use_container_width=True):
        st.switch_page("pages/8_Route_Analysis.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
