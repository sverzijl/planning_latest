"""Parser for Unified Node Model Excel format.

Reads Excel files with Nodes/Routes/TruckSchedules sheets in unified format.
"""

import pandas as pd
from typing import List, Tuple
from datetime import time, datetime

from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.unified_truck_schedule import UnifiedTruckSchedule, DayOfWeek, DepartureType
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure


class UnifiedModelParser:
    """Parser for unified node model Excel format.

    Expected sheets:
    - Nodes: Node definitions with capability flags
    - Routes: Route connections between nodes
    - TruckSchedules: Truck schedules with origin_node_id
    - LaborCalendar: Labor availability (same as legacy)
    - CostParameters: Cost structure (same as legacy)
    - Forecast: Demand forecast (same as legacy)
    """

    def __init__(self, file_path: str):
        """Initialize parser.

        Args:
            file_path: Path to Excel file
        """
        self.file_path = file_path

    def parse_nodes(self) -> List[UnifiedNode]:
        """Parse Nodes sheet.

        Returns:
            List of UnifiedNode objects
        """
        df = pd.read_excel(self.file_path, sheet_name='Nodes', engine='openpyxl')

        nodes = []

        for _, row in df.iterrows():
            # Parse capability flags
            capabilities = NodeCapabilities(
                can_manufacture=bool(row.get('can_manufacture', False)),
                production_rate_per_hour=float(row['production_rate_per_hour']) if pd.notna(row.get('production_rate_per_hour')) else None,
                # Manufacturing overhead parameters (defaults match NodeCapabilities model)
                daily_startup_hours=float(row.get('daily_startup_hours', 0.5)),
                daily_shutdown_hours=float(row.get('daily_shutdown_hours', 0.5)),
                default_changeover_hours=float(row.get('default_changeover_hours', 1.0)),
                can_store=bool(row.get('can_store', True)),
                storage_mode=self._parse_storage_mode(row.get('storage_mode', 'ambient')),
                storage_capacity=float(row['storage_capacity']) if pd.notna(row.get('storage_capacity')) else None,
                has_demand=bool(row.get('has_demand', False)),
                requires_truck_schedules=bool(row.get('requires_truck_schedules', False)),
            )

            node = UnifiedNode(
                id=str(row['node_id']),
                name=str(row['node_name']),
                capabilities=capabilities,
                latitude=float(row['latitude']) if pd.notna(row.get('latitude')) else None,
                longitude=float(row['longitude']) if pd.notna(row.get('longitude')) else None,
            )

            nodes.append(node)

        return nodes

    def parse_routes(self) -> List[UnifiedRoute]:
        """Parse Routes sheet.

        Returns:
            List of UnifiedRoute objects
        """
        df = pd.read_excel(self.file_path, sheet_name='Routes', engine='openpyxl')

        routes = []

        for _, row in df.iterrows():
            route = UnifiedRoute(
                id=str(row['route_id']),
                origin_node_id=str(row['origin_node_id']),
                destination_node_id=str(row['destination_node_id']),
                transit_days=float(row['transit_days']),
                transport_mode=self._parse_transport_mode(row.get('transport_mode', 'ambient')),
                cost_per_unit=float(row['cost_per_unit']) if pd.notna(row.get('cost_per_unit')) else 0.0,
            )

            routes.append(route)

        return routes

    def parse_truck_schedules(self) -> List[UnifiedTruckSchedule]:
        """Parse TruckSchedules sheet with origin_node_id column.

        Returns:
            List of UnifiedTruckSchedule objects
        """
        df = pd.read_excel(self.file_path, sheet_name='TruckSchedules', engine='openpyxl')

        trucks = []

        for _, row in df.iterrows():
            # Parse time
            departure_time_val = row['departure_time']
            if isinstance(departure_time_val, datetime):
                departure_time = departure_time_val.time()
            elif isinstance(departure_time_val, str):
                departure_time = datetime.strptime(departure_time_val, "%H:%M").time()
            else:
                departure_time = time(8, 0)  # Default

            # Parse day of week
            day_of_week = None
            if 'day_of_week' in row and pd.notna(row['day_of_week']):
                day_str = str(row['day_of_week']).lower()
                try:
                    day_of_week = DayOfWeek(day_str)
                except ValueError:
                    pass  # Invalid day, leave as None (daily)

            # Parse intermediate stops
            intermediate_stops = []
            if 'intermediate_stops' in row and pd.notna(row['intermediate_stops']):
                stops_str = str(row['intermediate_stops'])
                intermediate_stops = [s.strip() for s in stops_str.split(',')]

            truck = UnifiedTruckSchedule(
                id=str(row['truck_id']),
                origin_node_id=str(row['origin_node_id']),  # KEY: Explicit origin!
                destination_node_id=str(row['destination_node_id']),
                departure_type=self._parse_departure_type(row['departure_type']),
                departure_time=departure_time,
                day_of_week=day_of_week,
                capacity=float(row['capacity']),
                cost_fixed=float(row.get('cost_fixed', 0.0)),
                cost_per_unit=float(row.get('cost_per_unit', 0.0)),
                intermediate_stops=intermediate_stops,
                pallet_capacity=int(row.get('pallet_capacity', 44)),
                units_per_pallet=int(row.get('units_per_pallet', 320)),
                units_per_case=int(row.get('units_per_case', 10)),
            )

            trucks.append(truck)

        return trucks

    def parse_all(self) -> Tuple[List[UnifiedNode], List[UnifiedRoute], List[UnifiedTruckSchedule], Forecast, LaborCalendar, CostStructure]:
        """Parse all sheets from unified format Excel file.

        Returns:
            Tuple of (nodes, routes, trucks, forecast, labor_calendar, cost_structure)
        """
        nodes = self.parse_nodes()
        routes = self.parse_routes()
        trucks = self.parse_truck_schedules()

        # These sheets have same format as legacy
        forecast = self._parse_forecast()
        labor_calendar = self._parse_labor_calendar()
        cost_structure = self._parse_cost_parameters()

        return nodes, routes, trucks, forecast, labor_calendar, cost_structure

    def _parse_forecast(self) -> Forecast:
        """Parse Forecast sheet (same as legacy format)."""
        df = pd.read_excel(self.file_path, sheet_name='Forecast', engine='openpyxl')

        entries = []
        for _, row in df.iterrows():
            entry = ForecastEntry(
                location_id=str(row['location_id']),
                product_id=str(row['product_id']),
                forecast_date=pd.to_datetime(row['forecast_date']).date(),
                quantity=float(row['quantity']),
            )
            entries.append(entry)

        return Forecast(name=f"Forecast from {self.file_path}", entries=entries)

    def _parse_labor_calendar(self) -> LaborCalendar:
        """Parse LaborCalendar sheet (same as legacy format)."""
        df = pd.read_excel(self.file_path, sheet_name='LaborCalendar', engine='openpyxl')

        days = []
        for _, row in df.iterrows():
            day = LaborDay(
                date=pd.to_datetime(row['date']).date(),
                fixed_hours=float(row.get('fixed_hours', 0.0)),
                regular_rate=float(row['regular_rate']),
                overtime_rate=float(row['overtime_rate']),
                non_fixed_rate=float(row['non_fixed_rate']) if pd.notna(row.get('non_fixed_rate')) else None,
                minimum_hours=float(row.get('minimum_hours', 0.0)),
                is_fixed_day=bool(row.get('is_fixed_day', True)),
            )
            days.append(day)

        return LaborCalendar(name=f"Labor Calendar from {self.file_path}", days=days)

    def _parse_cost_parameters(self) -> CostStructure:
        """Parse CostParameters sheet (same as legacy format)."""
        df = pd.read_excel(self.file_path, sheet_name='CostParameters', engine='openpyxl')

        costs = {}
        for _, row in df.iterrows():
            cost_type = str(row['cost_type']).lower().replace(' ', '_')
            costs[cost_type] = float(row['value'])

        return CostStructure(
            production_cost_per_unit=costs.get('production_cost_per_unit', 5.0),
            transport_cost_per_unit=costs.get('transport_cost_per_unit', 1.0),
            storage_cost_per_unit_per_day=costs.get('storage_cost_per_unit_per_day', 0.01),
            waste_cost_per_unit=costs.get('waste_cost_per_unit', 10.0),
            shortage_penalty_per_unit=costs.get('shortage_penalty_per_unit', 10000.0),
        )

    def _parse_storage_mode(self, mode_str: str) -> StorageMode:
        """Parse storage mode string to enum."""
        mode_lower = str(mode_str).lower().strip()

        if mode_lower == 'frozen':
            return StorageMode.FROZEN
        elif mode_lower == 'ambient':
            return StorageMode.AMBIENT
        elif mode_lower == 'both':
            # 'both' no longer supported - default to ambient
            return StorageMode.AMBIENT
        else:
            return StorageMode.AMBIENT  # Default

    def _parse_transport_mode(self, mode_str: str) -> TransportMode:
        """Parse transport mode string to enum."""
        mode_lower = str(mode_str).lower().strip()

        if mode_lower == 'frozen':
            return TransportMode.FROZEN
        else:
            return TransportMode.AMBIENT  # Default

    def _parse_departure_type(self, type_str: str) -> DepartureType:
        """Parse departure type string to enum."""
        type_lower = str(type_str).lower().strip()

        if type_lower == 'morning':
            return DepartureType.MORNING
        elif type_lower == 'afternoon':
            return DepartureType.AFTERNOON
        else:
            return DepartureType.MORNING  # Default
