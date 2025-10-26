"""Network Analysis - Visualize supply chain network and analyze routes.

Consolidates:
- 7_Network_Visualization.py
- 8_Route_Analysis.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from ui import session_state
from ui.components.styling import apply_custom_css, section_header, colored_metric
from ui.components.navigation import render_page_header, check_data_required
from ui.components import render_network_graph, render_connectivity_matrix
from src.network import NetworkGraphBuilder, RouteFinder
from src.shelf_life import ProductState

# Page config
st.set_page_config(
    page_title="Network Analysis - GF Bread Production",
    page_icon="🗺️",
    layout="wide",
)

# Apply design system
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

# Page header
render_page_header(
    title="Network Analysis",
    icon="🗺️",
    subtitle="Visualize the supply chain network and analyze routes"
)

# Check if data is loaded
if not check_data_required():
    st.stop()

st.divider()

# Build graph
data = session_state.get_parsed_data()
graph_builder = NetworkGraphBuilder(data['locations'], data['routes'])
graph = graph_builder.build_graph()
route_finder = RouteFinder(graph_builder)

# Network Statistics (top-level metrics)
st.markdown(section_header("Network Statistics", level=3, icon="📊"), unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)

manufacturing_nodes = graph_builder.get_manufacturing_nodes()
breadroom_nodes = graph_builder.get_breadroom_nodes()
hub_nodes = graph_builder.get_hub_nodes()

with col1:
    st.markdown(colored_metric("Total Nodes", str(graph.number_of_nodes()), "primary"), unsafe_allow_html=True)
    st.markdown(colored_metric("Manufacturing", str(len(manufacturing_nodes)), "primary"), unsafe_allow_html=True)

with col2:
    st.markdown(colored_metric("Total Edges", str(graph.number_of_edges()), "secondary"), unsafe_allow_html=True)
    st.markdown(colored_metric("Hubs/Storage", str(len(hub_nodes)), "secondary"), unsafe_allow_html=True)

with col3:
    st.markdown(colored_metric("Breadrooms", str(len(breadroom_nodes)), "accent"), unsafe_allow_html=True)
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
        st.markdown(colored_metric("Avg Path Length", f"{avg_hops:.1f} hops", "accent"), unsafe_allow_html=True)

with col4:
    # Connectivity check
    connected_pairs = 0
    total_pairs = len(manufacturing_nodes) * len(breadroom_nodes)
    for mfg in manufacturing_nodes:
        for br in breadroom_nodes:
            if graph_builder.is_reachable(mfg, br):
                connected_pairs += 1
    connectivity_pct = (connected_pairs / total_pairs * 100) if total_pairs > 0 else 0
    st.markdown(colored_metric("Connectivity", f"{connectivity_pct:.0f}%", "success"), unsafe_allow_html=True)

st.divider()

# Create tabs for network views
tab_visualization, tab_routes = st.tabs(["🌐 Visualization", "🛣️ Routes"])


# ===========================
# TAB 1: NETWORK VISUALIZATION
# ===========================

with tab_visualization:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">🌐 Network Visualization</div>
        <div>Interactive graph view of the distribution network showing locations and routes.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    viz_subtab1, viz_subtab2, viz_subtab3 = st.tabs(["Network Graph", "Connectivity Matrix", "Location Details"])

    with viz_subtab1:
        st.markdown(section_header("Interactive Network Graph", level=4), unsafe_allow_html=True)

        # Filters
        col1, col2 = st.columns(2)

        with col1:
            show_manufacturing = st.checkbox("Show Manufacturing", value=True, key="viz_show_mfg")
            show_hubs = st.checkbox("Show Hubs/Storage", value=True, key="viz_show_hubs")
            show_breadrooms = st.checkbox("Show Breadrooms", value=True, key="viz_show_breadrooms")

        with col2:
            # Path highlighting (if planning complete)
            if session_state.is_planning_complete():
                highlight_routes = st.checkbox("Highlight Routes from Plan", value=False, key="viz_highlight")
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
        st.plotly_chart(fig, use_container_width=True, key="network_graph_visualization")

        st.caption("""
        **Legend:**
        - 🔴 Red Square: Manufacturing site
        - 🔵 Cyan Diamond: Hub/Storage location
        - 🟢 Green Circle: Breadroom destination
        - Arrows: Routes with transit time and mode
        """)

    with viz_subtab2:
        st.markdown(section_header("Connectivity Matrix", level=4), unsafe_allow_html=True)

        st.markdown("Shows which locations can reach which destinations through the network.")

        fig = render_connectivity_matrix(graph_builder)
        st.plotly_chart(fig, use_container_width=True, key="network_connectivity_matrix")

        st.caption("✅ Blue cells indicate a route exists between origin and destination")

    with viz_subtab3:
        st.markdown(section_header("Location Details", level=4), unsafe_allow_html=True)

        # Location selector
        all_locations = [loc.id for loc in data['locations']]
        selected_location = st.selectbox("Select Location", all_locations, key="viz_location_select")

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


# ===========================
# TAB 2: ROUTE ANALYSIS
# ===========================

with tab_routes:
    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">🛣️ Route Analysis</div>
        <div>Find and analyze routes between locations, compare paths, and view route usage.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    route_subtab1, route_subtab2 = st.tabs(["Route Finder", "Bulk Analysis"])

    with route_subtab1:
        st.markdown(section_header("Find Routes Between Locations", level=4, icon="🔍"), unsafe_allow_html=True)

        all_nodes = [loc.id for loc in data['locations']]

        col1, col2 = st.columns(2)

        with col1:
            origin = st.selectbox(
                "Origin",
                options=all_nodes,
                index=all_nodes.index(manufacturing_nodes[0]) if manufacturing_nodes else 0,
                key="route_origin_selector"
            )

        with col2:
            destination = st.selectbox(
                "Destination",
                options=all_nodes,
                index=all_nodes.index(breadroom_nodes[0]) if breadroom_nodes else 1,
                key="route_destination_selector"
            )

        if origin and destination:
            if origin == destination:
                st.warning("⚠️ Origin and destination are the same location")
            else:
                if st.button("🔎 Find All Routes", type="primary", use_container_width=True, key="find_routes_btn"):
                    with st.spinner("Finding routes..."):
                        # Find all paths
                        all_paths = route_finder.find_all_paths(origin, destination, max_hops=5)

                        if not all_paths:
                            st.error(f"❌ No routes found from {origin} to {destination}")
                        else:
                            st.success(f"✅ Found {len(all_paths)} route(s)")

                            # Display routes
                            route_data = []
                            for i, route_path in enumerate(all_paths, 1):
                                path_str = " → ".join(route_path.path)
                                route_data.append({
                                    '#': i,
                                    'Route': path_str,
                                    'Hops': route_path.num_hops,
                                    'Transit Days': route_path.total_transit_days,
                                    'Cost/Unit': f"${route_path.total_cost:.2f}",
                                    'Modes': ", ".join(set(route_path.transport_modes)),
                                })

                            df = pd.DataFrame(route_data)
                            st.dataframe(df, use_container_width=True, hide_index=True)

                            # Show best routes
                            st.divider()

                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("**Shortest Path (by time):**")
                                shortest = route_finder.find_shortest_path(origin, destination)
                                if shortest:
                                    st.info(f"{' → '.join(shortest.path)} ({shortest.total_transit_days} days)")
                                else:
                                    st.warning("No path found")

                            with col2:
                                st.markdown("**Cheapest Path (by cost):**")
                                cheapest = route_finder.find_cheapest_path(origin, destination)
                                if cheapest:
                                    st.info(f"{' → '.join(cheapest.path)} (${cheapest.total_cost:.2f}/unit)")
                                else:
                                    st.warning("No path found")

    with route_subtab2:
        st.markdown(section_header("Bulk Route Analysis", level=4, icon="📋"), unsafe_allow_html=True)

        st.markdown("Find recommended routes from manufacturing to all breadrooms.")

        if manufacturing_nodes and breadroom_nodes:
            if st.button("🚀 Analyze All Routes", type="primary", use_container_width=True, key="analyze_all_btn"):
                with st.spinner("Analyzing routes to all breadrooms..."):
                    # Get routes to all breadrooms
                    routes_dict = route_finder.get_routes_to_all_breadrooms(
                        source=manufacturing_nodes[0],
                        initial_state=ProductState.AMBIENT
                    )

                    # Display results
                    route_data = []
                    for breadroom, route_path in routes_dict.items():
                        if route_path:
                            path_str = " → ".join(route_path.path)
                            route_data.append({
                                'Destination': breadroom,
                                'Route': path_str,
                                'Hops': route_path.num_hops,
                                'Transit Days': route_path.total_transit_days,
                                'Cost/Unit': f"${route_path.total_cost:.2f}",
                                'Modes': ", ".join(set(route_path.transport_modes)),
                            })
                        else:
                            route_data.append({
                                'Destination': breadroom,
                                'Route': 'No route found',
                                'Hops': '-',
                                'Transit Days': '-',
                                'Cost/Unit': '-',
                                'Modes': '-',
                            })

                    df = pd.DataFrame(route_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    # Summary stats
                    st.divider()

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        reachable = sum(1 for r in routes_dict.values() if r is not None)
                        st.metric("Reachable Breadrooms", f"{reachable}/{len(breadroom_nodes)}")

                    with col2:
                        avg_transit = sum(r.total_transit_days for r in routes_dict.values() if r) / reachable if reachable > 0 else 0
                        st.metric("Avg Transit Time", f"{avg_transit:.1f} days")

                    with col3:
                        avg_cost = sum(r.total_cost for r in routes_dict.values() if r) / reachable if reachable > 0 else 0
                        st.metric("Avg Cost/Unit", f"${avg_cost:.2f}")

        else:
            st.info("No manufacturing sites or breadrooms found in network")

    # Planning results integration
    if session_state.is_planning_complete():
        st.divider()
        st.markdown(section_header("Routes Used in Planning", level=4, icon="📦"), unsafe_allow_html=True)

        results = session_state.get_planning_results()
        shipments = results['shipments']

        if shipments:
            # Count shipments by route
            route_counts = {}
            for shipment in shipments:
                if shipment.route:
                    route_key = " → ".join(shipment.route.path)
                    if route_key not in route_counts:
                        route_counts[route_key] = {
                            'shipments': 0,
                            'units': 0,
                            'transit_days': shipment.route.total_transit_days,
                            'cost': shipment.route.total_cost,
                        }
                    route_counts[route_key]['shipments'] += 1
                    route_counts[route_key]['units'] += shipment.quantity

            # Display
            route_data = []
            for route, stats in sorted(route_counts.items(), key=lambda x: x[1]['units'], reverse=True):
                route_data.append({
                    'Route': route,
                    'Shipments': stats['shipments'],
                    'Total Units': f"{stats['units']:,.0f}",
                    'Transit Days': stats['transit_days'],
                    'Cost/Unit': f"${stats['cost']:.2f}",
                })

            df = pd.DataFrame(route_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(route_data)} unique routes used in the plan")
