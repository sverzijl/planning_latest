"""Streamlit component to launch the retro visualization.

This component provides a button in the Streamlit UI to launch the pyxel
visualization in a separate process.
"""

import streamlit as st
import subprocess
import tempfile
import pickle
from pathlib import Path
from typing import Dict, Any, List, Optional


def create_visualization_launcher(
    solution: Dict[str, Any],
    network_config: Any,
    truck_schedules: Optional[List] = None,
):
    """
    Create a Streamlit component to launch the retro visualization.

    Since pyxel creates its own window and blocks execution, we run it
    in a separate process to avoid blocking the Streamlit UI.

    Args:
        solution: Solution dictionary from optimization
        network_config: Network configuration object
        truck_schedules: Optional truck schedules
    """
    st.subheader("🎮 8-Bit Retro Visualization")

    st.markdown("""
    Launch an 8-bit retro-style animated visualization of the production plan.
    The visualization shows:
    - **Map of Australia** with all locations
    - **Trucks traveling** between locations in real-time
    - **Inventory levels** at each location (bars above locations)
    - **Production activity** at manufacturing site (pulsing indicator)
    - **Frozen vs Ambient** transport (cyan vs white trucks)

    **Controls:**
    - `SPACE` - Pause/unpause
    - `R` - Reset to start
    - `↑/↓` - Increase/decrease speed
    - `MOUSE` - Click locations for details
    - `Q` - Quit
    """)

    # Animation speed control
    col1, col2 = st.columns([2, 1])

    with col1:
        animation_speed = st.slider(
            "Animation Speed",
            min_value=0.1,
            max_value=10.0,
            value=2.0,
            step=0.1,
            help="Speed multiplier for the animation (1.0 = normal speed)"
        )

    with col2:
        launch_button = st.button(
            "🚀 Launch Visualization",
            use_container_width=True,
            type="primary",
        )

    if launch_button:
        # Save solution data to temporary file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as f:
            temp_file = f.name
            pickle.dump({
                'solution': solution,
                'network_config': network_config,
                'truck_schedules': truck_schedules,
                'animation_speed': animation_speed,
            }, f)

        st.info("Launching visualization in separate window...")

        try:
            # Launch visualization script
            script_path = Path(__file__).parent.parent.parent / "src" / "visualization" / "_run_viz.py"

            # If script doesn't exist, create it
            if not script_path.exists():
                _create_viz_runner_script(script_path)

            # Run in subprocess
            subprocess.Popen([
                'python',
                str(script_path),
                temp_file,
            ])

            st.success("""
            ✅ Visualization launched!

            A new window should appear with the 8-bit retro visualization.
            If the window doesn't appear, check the console for errors.

            The visualization window is independent of this Streamlit app and can be
            closed at any time with the 'Q' key.
            """)

        except Exception as e:
            st.error(f"Error launching visualization: {e}")
            st.exception(e)

    # Show preview of what to expect
    with st.expander("Preview: What to expect"):
        st.markdown("""
        ### Visualization Elements

        **Locations:**
        - 🔴 Red circle - Manufacturing site (6122)
        - 🟡 Yellow circles - Regional hubs (6104, 6125)
        - ⚪ White circles - Breadroom locations
        - 🟢 Green bars - Inventory levels (height = quantity)
        - 🟠 Pulsing ring - Active production

        **Trucks:**
        - ⚪ White rectangles - Ambient transport
        - 🔵 Cyan rectangles - Frozen transport
        - → Arrow - Direction of travel

        **Map:**
        - Navy background represents the ocean/space
        - Green areas represent land (simplified Australia shape)
        - Gray lines connect locations with active routes

        **UI Elements:**
        - Top bar: Title and current date
        - Bottom bar: Active truck count, animation speed, controls
        - Right panel (when location selected): Detailed inventory and shipment info

        ### Tips:
        1. Click on any location to see detailed information
        2. Use UP/DOWN arrows to speed up or slow down the animation
        3. Press SPACE to pause and examine the current state
        4. Press R to restart from the beginning
        """)


def _create_viz_runner_script(script_path: Path):
    """Create the visualization runner script if it doesn't exist."""
    script_path.parent.mkdir(parents=True, exist_ok=True)

    script_content = '''"""Runner script for pyxel visualization (launched from Streamlit)."""

import sys
import pickle
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))

from visualization.retro_viz import visualize_solution


def main():
    if len(sys.argv) < 2:
        print("Usage: python _run_viz.py <data_file.pkl>")
        sys.exit(1)

    data_file = sys.argv[1]

    # Load data
    with open(data_file, 'rb') as f:
        data = pickle.load(f)

    solution = data['solution']
    network_config = data['network_config']
    truck_schedules = data.get('truck_schedules')
    animation_speed = data.get('animation_speed', 1.0)

    # Launch visualization
    visualize_solution(
        solution=solution,
        network_config=network_config,
        truck_schedules=truck_schedules,
        animation_speed=animation_speed,
    )


if __name__ == "__main__":
    main()
'''

    script_path.write_text(script_content)
    print(f"Created visualization runner script: {script_path}")
