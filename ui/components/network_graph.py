"""Network graph visualization component using Plotly."""

import plotly.graph_objects as go
import networkx as nx
from typing import Optional
from src.network import NetworkGraphBuilder


def render_network_graph(
    graph_builder: NetworkGraphBuilder,
    title: str = "Distribution Network",
    highlight_paths: Optional[list] = None,
    height: int = 600,
):
    """
    Render an interactive network graph.

    Args:
        graph_builder: NetworkGraphBuilder instance
        title: Chart title
        highlight_paths: Optional list of paths to highlight
        height: Chart height in pixels

    Returns:
        Plotly figure object
    """
    graph = graph_builder.get_graph()

    # Use spring layout for positioning
    pos = nx.spring_layout(graph, k=2, iterations=50, seed=42)

    # Prepare node traces
    node_traces = _create_node_traces(graph, pos)

    # Prepare edge traces
    edge_traces = _create_edge_traces(graph, pos, highlight_paths)

    # Create figure
    fig = go.Figure(data=edge_traces + node_traces)

    # Update layout
    fig.update_layout(
        title=title,
        title_x=0.5,
        showlegend=True,
        hovermode='closest',
        height=height,
        margin=dict(b=20, l=5, r=5, t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor='rgba(240,240,240,0.9)',
    )

    return fig


def _create_node_traces(graph: nx.DiGraph, pos: dict) -> list:
    """Create node traces grouped by location type."""
    # Group nodes by type
    node_groups = {}
    for node, attrs in graph.nodes(data=True):
        loc_type = attrs.get('location_type', 'unknown')
        if loc_type not in node_groups:
            node_groups[loc_type] = []
        node_groups[loc_type].append((node, attrs))

    # Color and symbol mapping
    type_config = {
        'manufacturing': {
            'color': '#FF6B6B',
            'symbol': 'square',
            'size': 25,
            'name': 'Manufacturing'
        },
        'storage': {
            'color': '#4ECDC4',
            'symbol': 'diamond',
            'size': 20,
            'name': 'Hub/Storage'
        },
        'breadroom': {
            'color': '#95E1D3',
            'symbol': 'circle',
            'size': 15,
            'name': 'Breadroom'
        },
    }

    traces = []
    for loc_type, nodes in node_groups.items():
        config = type_config.get(loc_type, {
            'color': '#CCCCCC',
            'symbol': 'circle',
            'size': 15,
            'name': loc_type.title()
        })

        x_coords = []
        y_coords = []
        hover_texts = []

        for node, attrs in nodes:
            x, y = pos[node]
            x_coords.append(x)
            y_coords.append(y)

            hover_text = f"<b>{attrs.get('name', node)}</b><br>"
            hover_text += f"ID: {node}<br>"
            hover_text += f"Type: {loc_type}"
            hover_texts.append(hover_text)

        trace = go.Scatter(
            x=x_coords,
            y=y_coords,
            mode='markers+text',
            name=config['name'],
            marker=dict(
                size=config['size'],
                color=config['color'],
                symbol=config['symbol'],
                line=dict(width=2, color='white'),
            ),
            text=[attrs.get('name', node) for node, attrs in nodes],
            textposition="top center",
            textfont=dict(size=10),
            hovertext=hover_texts,
            hoverinfo='text',
        )
        traces.append(trace)

    return traces


def _create_edge_traces(graph: nx.DiGraph, pos: dict, highlight_paths: Optional[list] = None) -> list:
    """Create edge traces."""
    # Create set of highlighted edges if paths provided
    highlighted_edges = set()
    if highlight_paths:
        for path in highlight_paths:
            for i in range(len(path) - 1):
                highlighted_edges.add((path[i], path[i + 1]))

    # Separate regular and highlighted edges
    regular_edges = []
    highlighted_edge_list = []

    for edge in graph.edges(data=True):
        from_node, to_node, attrs = edge
        if (from_node, to_node) in highlighted_edges:
            highlighted_edge_list.append(edge)
        else:
            regular_edges.append(edge)

    traces = []

    # Regular edges
    if regular_edges:
        trace = _create_edge_trace(
            regular_edges,
            pos,
            color='rgba(150,150,150,0.3)',
            width=1,
            name='Routes'
        )
        traces.append(trace)

    # Highlighted edges
    if highlighted_edge_list:
        trace = _create_edge_trace(
            highlighted_edge_list,
            pos,
            color='rgba(255,107,107,0.8)',
            width=3,
            name='Highlighted Path'
        )
        traces.append(trace)

    return traces


def _create_edge_trace(edges: list, pos: dict, color: str, width: float, name: str) -> go.Scatter:
    """Create a single edge trace."""
    x_coords = []
    y_coords = []
    hover_texts = []

    for from_node, to_node, attrs in edges:
        x0, y0 = pos[from_node]
        x1, y1 = pos[to_node]

        # Add edge line
        x_coords.extend([x0, x1, None])
        y_coords.extend([y0, y1, None])

        # Hover text
        hover_text = f"{from_node} → {to_node}<br>"
        hover_text += f"Transit: {attrs.get('transit_days', 0)} days<br>"
        hover_text += f"Mode: {attrs.get('transport_mode', 'unknown')}"
        if attrs.get('cost_per_unit'):
            hover_text += f"<br>Cost: ${attrs.get('cost_per_unit'):.2f}/unit"
        hover_texts.extend([hover_text, hover_text, None])

    trace = go.Scatter(
        x=x_coords,
        y=y_coords,
        mode='lines',
        name=name,
        line=dict(width=width, color=color),
        hovertext=hover_texts,
        hoverinfo='text',
    )

    return trace


def render_connectivity_matrix(graph_builder: NetworkGraphBuilder):
    """
    Render a connectivity matrix heatmap.

    Args:
        graph_builder: NetworkGraphBuilder instance

    Returns:
        Plotly figure object
    """
    graph = graph_builder.get_graph()

    # Get all nodes
    nodes = list(graph.nodes())
    n = len(nodes)

    # Create connectivity matrix
    matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            if graph.has_edge(nodes[i], nodes[j]):
                row.append(1)
            else:
                row.append(0)
        matrix.append(row)

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=[graph.nodes[n].get('name', n) for n in nodes],
        y=[graph.nodes[n].get('name', n) for n in nodes],
        colorscale='Blues',
        showscale=False,
        hovertemplate='From: %{y}<br>To: %{x}<br>Connected: %{z}<extra></extra>',
    ))

    fig.update_layout(
        title='Network Connectivity Matrix',
        title_x=0.5,
        xaxis_title='Destination',
        yaxis_title='Origin',
        height=500,
    )

    return fig
