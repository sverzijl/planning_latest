"""Route analysis and route finding page."""

import streamlit as st
import pandas as pd
from ui import session_state
from src.network import NetworkGraphBuilder, RouteFinder
from src.shelf_life import ProductState

# Page config
st.set_page_config(
    page_title="Route Analysis",
    page_icon="📊",
    layout="wide",
)

# Initialize session state
session_state.initialize_session_state()

st.header("📊 Route Analysis")

# Check if data uploaded
if not session_state.is_data_uploaded():
    st.warning("⚠️ No data loaded. Please upload files first.")
    if st.button("📤 Go to Upload Page", type="primary"):
        st.switch_page("pages/1_Upload_Data.py")
    st.stop()

# Get data
data = session_state.get_parsed_data()

# Build graph and route finder
graph_builder = NetworkGraphBuilder(data['locations'], data['routes'])
route_finder = RouteFinder(graph_builder)

# Get nodes
manufacturing_nodes = graph_builder.get_manufacturing_nodes()
breadroom_nodes = graph_builder.get_breadroom_nodes()
all_nodes = [loc.id for loc in data['locations']]

st.divider()

# Route finder tool
tab1, tab2 = st.tabs(["Route Finder", "Bulk Analysis"])

with tab1:
    st.subheader("🔍 Find Routes Between Locations")

    col1, col2 = st.columns(2)

    with col1:
        origin = st.selectbox(
            "Origin",
            options=all_nodes,
            index=all_nodes.index(manufacturing_nodes[0]) if manufacturing_nodes else 0,
            key="origin_selector"
        )

    with col2:
        destination = st.selectbox(
            "Destination",
            options=all_nodes,
            index=all_nodes.index(breadroom_nodes[0]) if breadroom_nodes else 1,
            key="destination_selector"
        )

    if origin and destination:
        if origin == destination:
            st.warning("⚠️ Origin and destination are the same location")
        else:
            if st.button("🔎 Find All Routes", type="primary"):
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

with tab2:
    st.subheader("📋 Bulk Route Analysis")

    st.markdown("Find recommended routes from manufacturing to all breadrooms.")

    if manufacturing_nodes and breadroom_nodes:
        if st.button("🚀 Analyze All Routes", type="primary"):
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
    st.subheader("📦 Routes Used in Planning")

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

st.divider()

# Navigation
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("← Network Visualization", use_container_width=True):
        st.switch_page("pages/7_Network_Visualization.py")

with col2:
    if st.button("Settings →", use_container_width=True):
        st.switch_page("pages/9_Settings.py")

with col3:
    if st.button("🏠 Home", use_container_width=True):
        st.switch_page("app.py")
