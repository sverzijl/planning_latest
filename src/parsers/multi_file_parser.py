"""Multi-file parser for separate forecast and network configuration files."""

from pathlib import Path
from typing import Optional
from datetime import date as Date

from .excel_parser import ExcelParser
from .product_alias_resolver import ProductAliasResolver
from .inventory_parser import InventoryParser
from ..models import (
    Forecast,
    Location,
    Route,
    LaborCalendar,
    TruckSchedule,
    CostStructure,
)
from ..models.inventory import InventorySnapshot


class MultiFileParser:
    """
    Parser for handling separate forecast and network configuration files.

    Enables users to maintain forecast data separately from network/operations
    configuration, which is useful when:
    - Forecast data updates frequently (weekly/monthly from SAP IBP exports)
    - Network configuration changes infrequently (locations, routes, labor, trucks)
    - Different teams manage forecast vs. operations data

    Usage:
        # Parse both files
        parser = MultiFileParser(
            forecast_file="GFree Forecast.xlsm",
            network_file="Network_Config.xlsx"
        )
        forecast, locations, routes, labor, trucks, costs = parser.parse_all()

        # Or parse individually
        forecast = parser.parse_forecast()
        locations = parser.parse_locations()
    """

    def __init__(
        self,
        forecast_file: Optional[Path | str] = None,
        network_file: Optional[Path | str] = None,
        inventory_file: Optional[Path | str] = None,
    ):
        """
        Initialize multi-file parser.

        Args:
            forecast_file: Path to file containing Forecast sheet (optional)
            network_file: Path to file containing Locations, Routes, LaborCalendar,
                         TruckSchedules, CostParameters, and Alias sheets (optional)
            inventory_file: Path to file containing inventory snapshot data (optional)

        Raises:
            ValueError: If both forecast_file and network_file are None
            FileNotFoundError: If specified file doesn't exist

        Note:
            At least one of forecast_file or network_file must be provided.
            inventory_file is optional and can be added later.
        """
        if forecast_file is None and network_file is None:
            raise ValueError("At least one of forecast_file or network_file must be provided")

        self.forecast_file = Path(forecast_file) if forecast_file else None
        self.network_file = Path(network_file) if network_file else None
        self.inventory_file = Path(inventory_file) if inventory_file else None

        # Validate files exist
        if self.forecast_file and not self.forecast_file.exists():
            raise FileNotFoundError(f"Forecast file not found: {forecast_file}")
        if self.network_file and not self.network_file.exists():
            raise FileNotFoundError(f"Network file not found: {network_file}")
        if self.inventory_file and not self.inventory_file.exists():
            raise FileNotFoundError(f"Inventory file not found: {inventory_file}")

        # Create parsers
        self._forecast_parser = ExcelParser(self.forecast_file) if self.forecast_file else None
        self._network_parser = ExcelParser(self.network_file) if self.network_file else None
        self._product_alias_resolver: Optional[ProductAliasResolver] = None
        self._inventory_parser: Optional[InventoryParser] = None

    def parse_forecast(self, sheet_name: str = "Forecast") -> Forecast:
        """
        Parse forecast data.

        Args:
            sheet_name: Name of forecast sheet (default: "Forecast")

        Returns:
            Forecast object with entries

        Raises:
            ValueError: If forecast_file was not provided
            ValueError: If sheet is missing or malformed
        """
        if self._forecast_parser is None:
            raise ValueError("Cannot parse forecast: no forecast_file provided")
        return self._forecast_parser.parse_forecast(sheet_name)

    def parse_locations(self, sheet_name: str = "Locations") -> list[Location]:
        """
        Parse location data from network file.

        Args:
            sheet_name: Name of locations sheet (default: "Locations")

        Returns:
            List of Location objects

        Raises:
            ValueError: If network_file was not provided
            ValueError: If sheet is missing or malformed
        """
        if self._network_parser is None:
            raise ValueError("Cannot parse locations: no network_file provided")
        return self._network_parser.parse_locations(sheet_name)

    def parse_routes(self, sheet_name: str = "Routes") -> list[Route]:
        """
        Parse route data from network file.

        Args:
            sheet_name: Name of routes sheet (default: "Routes")

        Returns:
            List of Route objects

        Raises:
            ValueError: If network_file was not provided
            ValueError: If sheet is missing or malformed
        """
        if self._network_parser is None:
            raise ValueError("Cannot parse routes: no network_file provided")
        return self._network_parser.parse_routes(sheet_name)

    def parse_labor_calendar(self, sheet_name: str = "LaborCalendar") -> LaborCalendar:
        """
        Parse labor calendar from network file.

        Args:
            sheet_name: Name of labor calendar sheet (default: "LaborCalendar")

        Returns:
            LaborCalendar object with daily entries

        Raises:
            ValueError: If network_file was not provided
            ValueError: If sheet is missing or malformed
        """
        if self._network_parser is None:
            raise ValueError("Cannot parse labor calendar: no network_file provided")
        return self._network_parser.parse_labor_calendar(sheet_name)

    def parse_truck_schedules(self, sheet_name: str = "TruckSchedules") -> list[TruckSchedule]:
        """
        Parse truck schedules from network file.

        Args:
            sheet_name: Name of truck schedules sheet (default: "TruckSchedules")

        Returns:
            List of TruckSchedule objects

        Raises:
            ValueError: If network_file was not provided
            ValueError: If sheet is missing or malformed
        """
        if self._network_parser is None:
            raise ValueError("Cannot parse truck schedules: no network_file provided")
        return self._network_parser.parse_truck_schedules(sheet_name)

    def parse_cost_structure(self, sheet_name: str = "CostParameters") -> CostStructure:
        """
        Parse cost structure from network file.

        Args:
            sheet_name: Name of cost parameters sheet (default: "CostParameters")

        Returns:
            CostStructure object

        Raises:
            ValueError: If network_file was not provided
            ValueError: If sheet is missing or malformed
        """
        if self._network_parser is None:
            raise ValueError("Cannot parse cost structure: no network_file provided")
        return self._network_parser.parse_cost_structure(sheet_name)

    def parse_all(
        self,
        forecast_sheet: str = "Forecast",
        locations_sheet: str = "Locations",
        routes_sheet: str = "Routes",
        labor_sheet: str = "LaborCalendar",
        trucks_sheet: str = "TruckSchedules",
        costs_sheet: str = "CostParameters",
    ) -> tuple[Forecast, list[Location], list[Route], LaborCalendar, list[TruckSchedule], CostStructure]:
        """
        Parse all data from both files.

        Args:
            forecast_sheet: Name of forecast sheet
            locations_sheet: Name of locations sheet
            routes_sheet: Name of routes sheet
            labor_sheet: Name of labor calendar sheet
            trucks_sheet: Name of truck schedules sheet
            costs_sheet: Name of cost parameters sheet

        Returns:
            Tuple of (Forecast, locations, routes, labor_calendar, truck_schedules, cost_structure)

        Raises:
            ValueError: If required files not provided
            ValueError: If sheets are missing or malformed
        """
        forecast = self.parse_forecast(forecast_sheet)
        locations = self.parse_locations(locations_sheet)
        routes = self.parse_routes(routes_sheet)
        labor_calendar = self.parse_labor_calendar(labor_sheet)
        truck_schedules = self.parse_truck_schedules(trucks_sheet)
        cost_structure = self.parse_cost_structure(costs_sheet)

        return forecast, locations, routes, labor_calendar, truck_schedules, cost_structure

    def validate_consistency(self, forecast: Forecast, locations: list[Location], routes: list[Route]) -> dict[str, list[str]]:
        """
        Validate consistency between forecast and network configuration.

        Checks:
        - All forecast location_ids exist in locations list
        - All route origin_ids and destination_ids exist in locations list
        - Detects locations defined but not used in forecast or routes

        Args:
            forecast: Forecast object
            locations: List of Location objects
            routes: List of Route objects

        Returns:
            Dictionary with validation results:
            {
                "missing_locations": [location_ids in forecast but not in locations],
                "missing_route_locations": [location_ids in routes but not in locations],
                "unused_locations": [location_ids in locations but not used],
                "warnings": [list of warning messages]
            }
        """
        location_ids = {loc.id for loc in locations}
        forecast_location_ids = {entry.location_id for entry in forecast.entries}
        route_location_ids = set()
        for route in routes:
            route_location_ids.add(route.origin_id)
            route_location_ids.add(route.destination_id)

        # Find issues
        missing_locations = forecast_location_ids - location_ids
        missing_route_locations = route_location_ids - location_ids
        unused_locations = location_ids - forecast_location_ids - route_location_ids

        # Generate warnings
        warnings = []
        if missing_locations:
            warnings.append(
                f"Forecast contains {len(missing_locations)} location(s) not defined in Locations sheet: "
                f"{', '.join(sorted(missing_locations))}"
            )
        if missing_route_locations:
            warnings.append(
                f"Routes reference {len(missing_route_locations)} location(s) not defined in Locations sheet: "
                f"{', '.join(sorted(missing_route_locations))}"
            )
        if unused_locations:
            warnings.append(
                f"{len(unused_locations)} location(s) defined but not used in forecast or routes: "
                f"{', '.join(sorted(unused_locations))}"
            )

        return {
            "missing_locations": sorted(missing_locations),
            "missing_route_locations": sorted(missing_route_locations),
            "unused_locations": sorted(unused_locations),
            "warnings": warnings,
        }

    def parse_product_aliases(self, sheet_name: str = "Alias") -> ProductAliasResolver:
        """
        Parse product aliases from network file.

        Args:
            sheet_name: Name of alias sheet (default: "Alias")

        Returns:
            ProductAliasResolver object

        Raises:
            ValueError: If network_file was not provided

        Note:
            If the Alias sheet doesn't exist, an empty resolver is returned (no aliases).
        """
        if self.network_file is None:
            raise ValueError("Cannot parse product aliases: no network_file provided")

        if self._product_alias_resolver is None:
            self._product_alias_resolver = ProductAliasResolver(
                self.network_file,
                sheet_name=sheet_name
            )

        return self._product_alias_resolver

    def parse_inventory(
        self,
        snapshot_date: Optional[Date] = None,
        sheet_name: str | int = 0,
    ) -> InventorySnapshot:
        """
        Parse inventory snapshot from inventory file.

        Args:
            snapshot_date: Date of inventory snapshot (default: today)
            sheet_name: Sheet name or index (default: 0 for first sheet)

        Returns:
            InventorySnapshot object

        Raises:
            ValueError: If inventory_file was not provided

        Note:
            Product codes in inventory are automatically resolved using
            the product alias resolver from the network file (if available).
        """
        if self.inventory_file is None:
            raise ValueError("Cannot parse inventory: no inventory_file provided")

        # Parse product aliases if not already done
        alias_resolver = None
        if self.network_file:
            try:
                alias_resolver = self.parse_product_aliases()
            except Exception:
                # If alias parsing fails, continue without it
                pass

        # Create inventory parser
        if self._inventory_parser is None:
            self._inventory_parser = InventoryParser(
                self.inventory_file,
                product_alias_resolver=alias_resolver,
                snapshot_date=snapshot_date,
            )

        return self._inventory_parser.parse(sheet_name=sheet_name)
