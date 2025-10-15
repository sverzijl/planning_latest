"""8-bit retro visualization using pyxel.

This module provides a retro-style visualization of the production planning solution
showing trucks moving between locations, inventory states, and production activity.
"""

import pyxel
from typing import Dict, List, Tuple, Optional
from datetime import date as Date, timedelta
from dataclasses import dataclass
import math

from .solution_extractor import SolutionDataExtractor, TruckMovement, LocationState


# Map layout - Australian geography inspired positions
# Screen size: 256x256 (power of 2, good for 8-bit aesthetic)
MAP_WIDTH = 256
MAP_HEIGHT = 256

# Location positions (x, y) - approximating Australian geography
LOCATION_POSITIONS = {
    "6122": (160, 200),  # Manufacturing (VIC - Melbourne area)
    "6104": (200, 160),  # Moorebank (NSW - Sydney area)
    "6105": (205, 165),  # Rydalmere (NSW - Sydney area, near 6104)
    "6103": (180, 180),  # Canberra (ACT - between Sydney and Melbourne)
    "6110": (220, 100),  # Burleigh Heads (QLD - Gold Coast/Brisbane)
    "6123": (155, 205),  # Clayton-Fairbank (VIC - Melbourne area)
    "6125": (150, 195),  # Keilor Park (VIC - Melbourne area, hub)
    "6130": (40, 180),   # Canning Vale (WA - Perth, far west)
    "6134": (120, 210),  # West Richmond (SA - Adelaide)
    "6120": (160, 240),  # Hobart (TAS - Tasmania, south of Melbourne)
    "Lineage": (80, 170),  # Lineage (frozen storage, on route to WA)
}

# Colors (pyxel 16-color palette)
# 0=black, 1=navy, 2=purple, 3=green, 4=brown, 5=dark_gray, 6=light_gray, 7=white
# 8=red, 9=orange, 10=yellow, 11=lime, 12=cyan, 13=gray, 14=pink, 15=beige
COLOR_BG = 1          # Navy background (retro space map)
COLOR_LAND = 3        # Green for land
COLOR_OCEAN = 12      # Cyan for ocean
COLOR_LOCATION = 7    # White for locations
COLOR_HUB = 10        # Yellow for hubs
COLOR_MFG = 8         # Red for manufacturing
COLOR_TRUCK_AMBIENT = 7  # White for ambient trucks
COLOR_TRUCK_FROZEN = 12  # Cyan for frozen trucks
COLOR_TEXT = 7        # White text
COLOR_ROUTE = 5       # Dark gray for route lines
COLOR_INVENTORY = 11  # Lime for inventory indicator
COLOR_PRODUCTION = 9  # Orange for production indicator


@dataclass
class AnimatedTruck:
    """Represents a truck being animated on the map."""
    movement: TruckMovement
    origin_pos: Tuple[int, int]
    dest_pos: Tuple[int, int]
    progress: float  # 0.0 to 1.0

    @property
    def current_pos(self) -> Tuple[int, int]:
        """Calculate current position based on progress."""
        x = int(self.origin_pos[0] + (self.dest_pos[0] - self.origin_pos[0]) * self.progress)
        y = int(self.origin_pos[1] + (self.dest_pos[1] - self.origin_pos[1]) * self.progress)
        return (x, y)


class RetroVisualization:
    """
    8-bit retro visualization of production planning solution using pyxel.

    This class creates an animated visualization showing:
    - Map of Australia with location markers
    - Trucks traveling between locations
    - Inventory levels at each location
    - Production activity at manufacturing site
    - Frozen vs ambient transport indicators
    """

    def __init__(
        self,
        extractor: SolutionDataExtractor,
        animation_speed: float = 1.0,
        title: str = "Gluten-Free Bread Distribution"
    ):
        """
        Initialize the visualization.

        Args:
            extractor: SolutionDataExtractor with solution data
            animation_speed: Speed multiplier for animations (1.0 = normal)
            title: Title to display at top of screen
        """
        self.extractor = extractor
        self.animation_speed = animation_speed
        self.title = title

        # Get all movements and dates
        self.all_movements = extractor.get_truck_movements()
        self.all_dates = extractor.get_all_dates()
        self.all_locations = extractor.get_all_locations()

        if not self.all_dates:
            raise ValueError("No dates found in solution data")

        self.start_date = self.all_dates[0]
        self.end_date = self.all_dates[-1]

        # Current simulation state
        self.current_date = self.start_date
        self.current_day_offset = 0.0  # 0.0 to 1.0 within current day
        self.frame_count = 0
        self.paused = False

        # Active trucks being animated
        self.active_trucks: List[AnimatedTruck] = []

        # Location states cache
        self.location_states: Dict[Tuple[str, Date], LocationState] = {}

        # Selected location for detail view
        self.selected_location: Optional[str] = None

        # Initialize pyxel
        pyxel.init(MAP_WIDTH, MAP_HEIGHT, title=title, fps=30)

        # Load or create assets (sprites, sounds, etc.)
        self._init_assets()

        # Run the app
        pyxel.run(self.update, self.draw)

    def _init_assets(self):
        """Initialize pyxel assets (sprites, sounds, etc.)."""
        # For now, we'll use simple shapes
        # In future, could create sprite sheets for trucks, buildings, etc.
        pass

    def update(self):
        """Update simulation state (called every frame by pyxel)."""
        # Handle input
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        if pyxel.btnp(pyxel.KEY_SPACE):
            self.paused = not self.paused

        if pyxel.btnp(pyxel.KEY_R):
            # Reset to start
            self.current_date = self.start_date
            self.current_day_offset = 0.0
            self.active_trucks = []

        # Speed controls
        if pyxel.btnp(pyxel.KEY_UP):
            self.animation_speed = min(10.0, self.animation_speed * 1.5)
        if pyxel.btnp(pyxel.KEY_DOWN):
            self.animation_speed = max(0.1, self.animation_speed / 1.5)

        # Location selection (mouse click)
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            self._handle_location_click(mx, my)

        if self.paused:
            return

        # Update simulation time
        self.frame_count += 1

        # Advance time based on animation speed
        # 1 day per 60 frames at speed 1.0
        days_per_frame = (1.0 / 60.0) * self.animation_speed
        self.current_day_offset += days_per_frame

        # Advance to next day
        if self.current_day_offset >= 1.0:
            self.current_day_offset = 0.0
            self._advance_to_next_day()

        # Update active trucks
        self._update_trucks()

    def _advance_to_next_day(self):
        """Advance simulation to the next day."""
        # Find next date
        current_idx = self.all_dates.index(self.current_date)
        if current_idx < len(self.all_dates) - 1:
            self.current_date = self.all_dates[current_idx + 1]
        else:
            # Loop back to start
            self.current_date = self.start_date

        # Spawn new trucks departing on this date
        self._spawn_trucks_for_date(self.current_date)

    def _spawn_trucks_for_date(self, date: Date):
        """Spawn trucks departing on the given date."""
        for movement in self.all_movements:
            if movement.departure_date == date:
                # Get positions
                origin_pos = LOCATION_POSITIONS.get(movement.origin, (MAP_WIDTH // 2, MAP_HEIGHT // 2))
                dest_pos = LOCATION_POSITIONS.get(movement.destination, (MAP_WIDTH // 2, MAP_HEIGHT // 2))

                animated_truck = AnimatedTruck(
                    movement=movement,
                    origin_pos=origin_pos,
                    dest_pos=dest_pos,
                    progress=0.0,
                )
                self.active_trucks.append(animated_truck)

    def _update_trucks(self):
        """Update positions of active trucks."""
        # Progress trucks based on transit time
        trucks_to_remove = []

        for truck in self.active_trucks:
            # Calculate progress increment
            # Transit should complete over the number of transit days
            transit_days = truck.movement.transit_days
            if transit_days == 0:
                transit_days = 1  # Avoid division by zero

            # Progress per frame = (1 / transit_days) / frames_per_day
            frames_per_day = 60 / self.animation_speed
            progress_per_frame = (1.0 / transit_days) / frames_per_day

            truck.progress += progress_per_frame

            # Remove trucks that have arrived
            if truck.progress >= 1.0:
                trucks_to_remove.append(truck)

        # Remove arrived trucks
        for truck in trucks_to_remove:
            self.active_trucks.remove(truck)

    def _handle_location_click(self, mx: int, my: int):
        """Handle mouse click for location selection."""
        # Check if click is near any location
        for loc_id, (x, y) in LOCATION_POSITIONS.items():
            dist = math.sqrt((mx - x)**2 + (my - y)**2)
            if dist < 10:  # Click radius
                self.selected_location = loc_id
                return

        # Click outside any location - deselect
        self.selected_location = None

    def draw(self):
        """Draw the visualization (called every frame by pyxel)."""
        # Clear screen
        pyxel.cls(COLOR_BG)

        # Draw simplified Australia map outline (just ocean/land colors)
        self._draw_map_background()

        # Draw routes between locations
        self._draw_routes()

        # Draw locations
        self._draw_locations()

        # Draw trucks
        self._draw_trucks()

        # Draw UI overlay
        self._draw_ui()

        # Draw detail panel if location selected
        if self.selected_location:
            self._draw_location_detail()

    def _draw_map_background(self):
        """Draw simplified map background."""
        # For now, just a solid background
        # Could add a simplified Australia outline or grid pattern
        pyxel.cls(COLOR_BG)

        # Draw a simple land mass (very simplified Australia shape)
        # Just draw some filled regions to suggest land
        # Simplified: draw a large irregular shape in the eastern side
        points = [
            (140, 80), (230, 80), (240, 120), (235, 180),
            (220, 220), (180, 240), (140, 245), (120, 230),
            (110, 200), (100, 160), (120, 120)
        ]

        # Draw filled polygon (pyxel doesn't have polygon fill, so approximate with circles)
        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            # Draw thick line as land
            for t in range(0, 20):
                offset = (t - 10) * 0.3
                pyxel.line(x1, y1 + offset, x2, y2 + offset, COLOR_LAND)

        # WA region (separate, on the left)
        pyxel.circ(60, 180, 25, COLOR_LAND)

    def _draw_routes(self):
        """Draw route lines between locations."""
        # Draw lines between connected locations based on movements
        drawn_routes = set()

        for movement in self.all_movements:
            origin = movement.origin
            dest = movement.destination

            # Avoid drawing duplicate routes
            route_key = tuple(sorted([origin, dest]))
            if route_key in drawn_routes:
                continue
            drawn_routes.add(route_key)

            # Get positions
            origin_pos = LOCATION_POSITIONS.get(origin)
            dest_pos = LOCATION_POSITIONS.get(dest)

            if origin_pos and dest_pos:
                # Draw route line
                pyxel.line(
                    origin_pos[0], origin_pos[1],
                    dest_pos[0], dest_pos[1],
                    COLOR_ROUTE
                )

    def _draw_locations(self):
        """Draw location markers on the map."""
        for loc_id, (x, y) in LOCATION_POSITIONS.items():
            # Get location state
            state = self._get_location_state(loc_id, self.current_date)

            # Determine location type and color
            if loc_id == "6122":
                color = COLOR_MFG  # Manufacturing site
                size = 4
            elif loc_id in ["6104", "6125"]:
                color = COLOR_HUB  # Hubs
                size = 3
            else:
                color = COLOR_LOCATION  # Regular locations
                size = 2

            # Draw location marker
            pyxel.circ(x, y, size, color)

            # Draw inventory indicator (bar above location)
            if state:
                total_inventory = sum(state.inventory_frozen.values()) + sum(state.inventory_ambient.values())
                if total_inventory > 0:
                    # Draw small bar indicating inventory level
                    bar_height = min(10, int(total_inventory / 1000))
                    if bar_height > 0:
                        pyxel.rect(x - 2, y - size - bar_height - 2, 4, bar_height, COLOR_INVENTORY)

            # Draw production indicator at manufacturing
            if loc_id == "6122" and state and state.production:
                total_production = sum(state.production.values())
                if total_production > 0:
                    # Draw pulsing circle for production
                    pulse = int(3 + math.sin(self.frame_count * 0.2) * 2)
                    pyxel.circb(x, y, size + pulse, COLOR_PRODUCTION)

            # Highlight selected location
            if loc_id == self.selected_location:
                pyxel.circb(x, y, size + 2, COLOR_TEXT)

            # Draw location label (abbreviated)
            label = loc_id[-4:] if loc_id.isdigit() else loc_id[:3]
            pyxel.text(x - 4, y + size + 2, label, COLOR_TEXT)

    def _draw_trucks(self):
        """Draw trucks traveling between locations."""
        for truck in self.active_trucks:
            x, y = truck.current_pos

            # Determine color based on frozen/ambient
            color = COLOR_TRUCK_FROZEN if truck.movement.is_frozen else COLOR_TRUCK_AMBIENT

            # Draw truck as small rectangle
            pyxel.rect(x - 2, y - 1, 4, 2, color)

            # Draw direction indicator (small arrow or line)
            # Calculate direction to destination
            dx = truck.dest_pos[0] - truck.origin_pos[0]
            dy = truck.dest_pos[1] - truck.origin_pos[1]
            length = math.sqrt(dx*dx + dy*dy)
            if length > 0:
                # Normalized direction
                ndx = dx / length
                ndy = dy / length

                # Draw small line in front of truck
                pyxel.line(x, y, int(x + ndx * 4), int(y + ndy * 4), color)

    def _draw_ui(self):
        """Draw UI overlay with date, stats, and controls."""
        # Top bar with title and date
        pyxel.rect(0, 0, MAP_WIDTH, 10, 0)  # Black bar
        pyxel.text(2, 2, self.title, COLOR_TEXT)

        # Current date
        date_str = self.current_date.strftime("%Y-%m-%d")
        pyxel.text(MAP_WIDTH - 60, 2, date_str, COLOR_TEXT)

        # Bottom bar with stats and controls
        pyxel.rect(0, MAP_HEIGHT - 20, MAP_WIDTH, 20, 0)

        # Stats
        active_trucks_count = len(self.active_trucks)
        speed_text = f"Speed: {self.animation_speed:.1f}x"
        trucks_text = f"Trucks: {active_trucks_count}"

        pyxel.text(2, MAP_HEIGHT - 16, trucks_text, COLOR_TEXT)
        pyxel.text(2, MAP_HEIGHT - 8, speed_text, COLOR_TEXT)

        # Controls
        controls = "SPACE:Pause R:Reset ↑↓:Speed Q:Quit"
        pyxel.text(MAP_WIDTH - 130, MAP_HEIGHT - 10, controls, COLOR_TEXT)

        # Paused indicator
        if self.paused:
            pyxel.text(MAP_WIDTH // 2 - 15, MAP_HEIGHT // 2, "PAUSED", COLOR_TEXT)

    def _draw_location_detail(self):
        """Draw detailed information about selected location."""
        if not self.selected_location:
            return

        # Get location state
        state = self._get_location_state(self.selected_location, self.current_date)
        if not state:
            return

        # Draw detail panel on the right side
        panel_x = MAP_WIDTH - 80
        panel_y = 20
        panel_width = 78
        panel_height = 100

        # Background
        pyxel.rect(panel_x, panel_y, panel_width, panel_height, 0)
        pyxel.rectb(panel_x, panel_y, panel_width, panel_height, COLOR_TEXT)

        # Title
        pyxel.text(panel_x + 2, panel_y + 2, f"Loc: {self.selected_location}", COLOR_TEXT)

        y_offset = panel_y + 12

        # Production
        if state.production:
            total_prod = sum(state.production.values())
            pyxel.text(panel_x + 2, y_offset, f"Prod: {int(total_prod)}", COLOR_PRODUCTION)
            y_offset += 8

        # Inventory
        frozen_inv = sum(state.inventory_frozen.values())
        ambient_inv = sum(state.inventory_ambient.values())

        if frozen_inv > 0:
            pyxel.text(panel_x + 2, y_offset, f"Frzn: {int(frozen_inv)}", COLOR_TRUCK_FROZEN)
            y_offset += 8

        if ambient_inv > 0:
            pyxel.text(panel_x + 2, y_offset, f"Ambt: {int(ambient_inv)}", COLOR_TRUCK_AMBIENT)
            y_offset += 8

        # Shipments
        if state.outbound_shipments:
            pyxel.text(panel_x + 2, y_offset, f"Out: {len(state.outbound_shipments)}", COLOR_TEXT)
            y_offset += 8

        if state.inbound_shipments:
            pyxel.text(panel_x + 2, y_offset, f"In: {len(state.inbound_shipments)}", COLOR_TEXT)
            y_offset += 8

    def _get_location_state(self, location_id: str, date: Date) -> Optional[LocationState]:
        """Get cached location state."""
        key = (location_id, date)
        if key not in self.location_states:
            self.location_states[key] = self.extractor.get_location_state(location_id, date)
        return self.location_states[key]


def visualize_solution(
    solution: Dict,
    network_config: any,
    truck_schedules: Optional[List] = None,
    animation_speed: float = 1.0,
):
    """
    Convenience function to visualize a solution.

    Args:
        solution: Solution dictionary from integrated model
        network_config: Network configuration
        truck_schedules: Optional truck schedules
        animation_speed: Animation speed multiplier

    Example:
        >>> result = model.solve()
        >>> if result.is_optimal():
        >>>     visualize_solution(
        >>>         result.metadata,
        >>>         network_config,
        >>>         truck_schedules
        >>>     )
    """
    extractor = SolutionDataExtractor(solution, network_config, truck_schedules)
    viz = RetroVisualization(extractor, animation_speed=animation_speed)
