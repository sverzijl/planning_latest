"""Excel parser for reading forecast files (.xlsm format)."""

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from openpyxl import load_workbook

from ..models import (
    Forecast,
    ForecastEntry,
    Location,
    LocationType,
    Route,
    StorageMode,
    ManufacturingSite,
    TruckSchedule,
    DepartureType,
    DayOfWeek,
    LaborCalendar,
    LaborDay,
    CostStructure,
)


class ExcelParser:
    """
    Parser for Excel forecast files.

    Expected file format:
    - Sheet 'Forecast': columns [location_id, product_id, date, quantity, confidence?]
    - Sheet 'Locations': columns [id, name, type, storage_mode, capacity?, lat?, lon?]
    - Sheet 'Routes': columns [id, origin_id, destination_id, transport_mode, transit_time_days, cost?, capacity?]
    - Sheet 'LaborCalendar': columns [date, fixed_hours, regular_rate, overtime_rate, non_fixed_rate?, minimum_hours?, is_fixed_day?]
    - Sheet 'TruckSchedules': columns [id, truck_name, departure_type, departure_time, destination_id?, capacity, cost_fixed?, cost_per_unit?, day_of_week?, intermediate_stops?, pallet_capacity?, units_per_pallet?, units_per_case?]
    - Sheet 'CostParameters': columns [cost_type, value, unit?]
    """

    def __init__(self, file_path: Path | str):
        """
        Initialize parser with Excel file path.

        Args:
            file_path: Path to the Excel file (.xlsm or .xlsx)

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If file is not .xlsm or .xlsx
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if self.file_path.suffix not in [".xlsm", ".xlsx"]:
            raise ValueError(f"File must be .xlsm or .xlsx: {file_path}")

    def parse_forecast(self, sheet_name: str = "Forecast") -> Forecast:
        """
        Parse forecast data from Excel sheet.

        Args:
            sheet_name: Name of the sheet containing forecast data

        Returns:
            Forecast object with entries

        Raises:
            ValueError: If sheet is missing or malformed
        """
        df = pd.read_excel(
            self.file_path,
            sheet_name=sheet_name,
            engine="openpyxl"
        )

        # Validate required columns
        required_cols = {"location_id", "product_id", "date", "quantity"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        # Parse entries
        entries = []
        for _, row in df.iterrows():
            entry = ForecastEntry(
                location_id=str(row["location_id"]),
                product_id=str(row["product_id"]),
                forecast_date=pd.to_datetime(row["date"]).date(),
                quantity=float(row["quantity"]),
                confidence=float(row["confidence"]) if "confidence" in row and pd.notna(row["confidence"]) else None,
            )
            entries.append(entry)

        forecast_name = f"Forecast from {self.file_path.name}"
        return Forecast(name=forecast_name, entries=entries)

    def parse_locations(self, sheet_name: str = "Locations") -> list[Location]:
        """
        Parse location data from Excel sheet.

        Args:
            sheet_name: Name of the sheet containing location data

        Returns:
            List of Location objects

        Raises:
            ValueError: If sheet is missing or malformed
        """
        df = pd.read_excel(
            self.file_path,
            sheet_name=sheet_name,
            engine="openpyxl"
        )

        # Validate required columns
        required_cols = {"id", "name", "type", "storage_mode"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        # Parse locations
        locations = []
        for _, row in df.iterrows():
            loc_type = LocationType(row["type"].lower())

            # Build base location parameters
            base_params = {
                "id": str(row["id"]),
                "name": str(row["name"]),
                "type": loc_type,
                "storage_mode": StorageMode(row["storage_mode"].lower()),
                "capacity": float(row["capacity"]) if "capacity" in row and pd.notna(row["capacity"]) else None,
                "latitude": float(row["latitude"]) if "latitude" in row and pd.notna(row["latitude"]) else None,
                "longitude": float(row["longitude"]) if "longitude" in row and pd.notna(row["longitude"]) else None,
            }

            # Check if this is a manufacturing location
            if loc_type == LocationType.MANUFACTURING:
                # Manufacturing-specific parameters
                if "production_rate" not in row or pd.isna(row["production_rate"]):
                    raise ValueError(f"Manufacturing location {row['id']} missing required 'production_rate' parameter")

                mfg_params = {
                    **base_params,
                    "production_rate": float(row["production_rate"]),
                    "max_daily_capacity": float(row["max_daily_capacity"]) if "max_daily_capacity" in row and pd.notna(row["max_daily_capacity"]) else None,
                    "daily_startup_hours": float(row["daily_startup_hours"]) if "daily_startup_hours" in row and pd.notna(row["daily_startup_hours"]) else 0.5,
                    "daily_shutdown_hours": float(row["daily_shutdown_hours"]) if "daily_shutdown_hours" in row and pd.notna(row["daily_shutdown_hours"]) else 0.5,
                    "default_changeover_hours": float(row["default_changeover_hours"]) if "default_changeover_hours" in row and pd.notna(row["default_changeover_hours"]) else 1.0,
                    "morning_truck_cutoff_hour": int(row["morning_truck_cutoff_hour"]) if "morning_truck_cutoff_hour" in row and pd.notna(row["morning_truck_cutoff_hour"]) else 24,
                    "afternoon_truck_cutoff_hour": int(row["afternoon_truck_cutoff_hour"]) if "afternoon_truck_cutoff_hour" in row and pd.notna(row["afternoon_truck_cutoff_hour"]) else 12,
                }
                location = ManufacturingSite(**mfg_params)
            else:
                # Regular location (storage or breadroom)
                location = Location(**base_params)

            locations.append(location)

        return locations

    def parse_routes(self, sheet_name: str = "Routes") -> list[Route]:
        """
        Parse route data from Excel sheet.

        Args:
            sheet_name: Name of the sheet containing route data

        Returns:
            List of Route objects

        Raises:
            ValueError: If sheet is missing or malformed
        """
        df = pd.read_excel(
            self.file_path,
            sheet_name=sheet_name,
            engine="openpyxl"
        )

        # Validate required columns
        required_cols = {"id", "origin_id", "destination_id", "transport_mode", "transit_time_days"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        # Parse routes
        routes = []
        for _, row in df.iterrows():
            route = Route(
                id=str(row["id"]),
                origin_id=str(row["origin_id"]),
                destination_id=str(row["destination_id"]),
                transport_mode=StorageMode(row["transport_mode"].lower()),
                transit_time_days=float(row["transit_time_days"]),
                cost=float(row["cost"]) if "cost" in row and pd.notna(row["cost"]) else None,
                capacity=float(row["capacity"]) if "capacity" in row and pd.notna(row["capacity"]) else None,
            )
            routes.append(route)

        return routes

    def parse_labor_calendar(self, sheet_name: str = "LaborCalendar") -> LaborCalendar:
        """
        Parse labor calendar data from Excel sheet.

        Args:
            sheet_name: Name of the sheet containing labor calendar data

        Returns:
            LaborCalendar object with daily entries

        Raises:
            ValueError: If sheet is missing or malformed
        """
        df = pd.read_excel(
            self.file_path,
            sheet_name=sheet_name,
            engine="openpyxl"
        )

        # Validate required columns
        required_cols = {"date", "regular_rate", "overtime_rate"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        # Parse labor days
        days = []
        for _, row in df.iterrows():
            day = LaborDay(
                date=pd.to_datetime(row["date"]).date(),
                fixed_hours=float(row["fixed_hours"]) if "fixed_hours" in row and pd.notna(row["fixed_hours"]) else 0.0,
                regular_rate=float(row["regular_rate"]),
                overtime_rate=float(row["overtime_rate"]),
                non_fixed_rate=float(row["non_fixed_rate"]) if "non_fixed_rate" in row and pd.notna(row["non_fixed_rate"]) else None,
                minimum_hours=float(row["minimum_hours"]) if "minimum_hours" in row and pd.notna(row["minimum_hours"]) else 0.0,
                is_fixed_day=bool(row["is_fixed_day"]) if "is_fixed_day" in row and pd.notna(row["is_fixed_day"]) else True,
            )
            days.append(day)

        calendar_name = f"Labor Calendar from {self.file_path.name}"
        return LaborCalendar(name=calendar_name, days=days)

    def parse_truck_schedules(self, sheet_name: str = "TruckSchedules") -> list[TruckSchedule]:
        """
        Parse truck schedule data from Excel sheet.

        Args:
            sheet_name: Name of the sheet containing truck schedule data

        Returns:
            List of TruckSchedule objects

        Raises:
            ValueError: If sheet is missing or malformed
        """
        df = pd.read_excel(
            self.file_path,
            sheet_name=sheet_name,
            engine="openpyxl"
        )

        # Validate required columns
        required_cols = {"id", "truck_name", "departure_type", "departure_time", "capacity"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        # Parse truck schedules
        schedules = []
        for _, row in df.iterrows():
            # Parse day of week if present
            day_of_week = None
            if "day_of_week" in row and pd.notna(row["day_of_week"]):
                day_str = str(row["day_of_week"]).lower()
                try:
                    day_of_week = DayOfWeek(day_str)
                except ValueError:
                    # Invalid day name, leave as None (daily schedule)
                    pass

            # Parse intermediate stops if present (comma-separated string)
            intermediate_stops = []
            if "intermediate_stops" in row and pd.notna(row["intermediate_stops"]):
                stops_str = str(row["intermediate_stops"])
                intermediate_stops = [s.strip() for s in stops_str.split(",") if s.strip()]

            schedule = TruckSchedule(
                id=str(row["id"]),
                truck_name=str(row["truck_name"]),
                departure_type=DepartureType(row["departure_type"].lower()),
                departure_time=pd.to_datetime(row["departure_time"]).time(),
                destination_id=str(row["destination_id"]) if "destination_id" in row and pd.notna(row["destination_id"]) else None,
                capacity=float(row["capacity"]),
                cost_fixed=float(row["cost_fixed"]) if "cost_fixed" in row and pd.notna(row["cost_fixed"]) else 0.0,
                cost_per_unit=float(row["cost_per_unit"]) if "cost_per_unit" in row and pd.notna(row["cost_per_unit"]) else 0.0,
                day_of_week=day_of_week,
                intermediate_stops=intermediate_stops,
                pallet_capacity=int(row["pallet_capacity"]) if "pallet_capacity" in row and pd.notna(row["pallet_capacity"]) else 44,
                units_per_pallet=int(row["units_per_pallet"]) if "units_per_pallet" in row and pd.notna(row["units_per_pallet"]) else 320,
                units_per_case=int(row["units_per_case"]) if "units_per_case" in row and pd.notna(row["units_per_case"]) else 10,
            )
            schedules.append(schedule)

        return schedules

    def parse_cost_structure(self, sheet_name: str = "CostParameters") -> CostStructure:
        """
        Parse cost structure from Excel sheet.

        Expected format: rows with cost_type, value, unit (optional)
        cost_type values: production_cost_per_unit, setup_cost, default_regular_rate, etc.

        Args:
            sheet_name: Name of the sheet containing cost parameters

        Returns:
            CostStructure object

        Raises:
            ValueError: If sheet is missing or malformed
        """
        df = pd.read_excel(
            self.file_path,
            sheet_name=sheet_name,
            engine="openpyxl"
        )

        # Validate required columns
        required_cols = {"cost_type", "value"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        # Convert to dictionary
        cost_dict = {}
        for _, row in df.iterrows():
            cost_type = str(row["cost_type"]).strip()
            value = float(row["value"])
            cost_dict[cost_type] = value

        # Map to CostStructure fields (with defaults)
        return CostStructure(
            production_cost_per_unit=cost_dict.get("production_cost_per_unit", 0.0),
            setup_cost=cost_dict.get("setup_cost", 0.0),
            default_regular_rate=cost_dict.get("default_regular_rate", 20.0),
            default_overtime_rate=cost_dict.get("default_overtime_rate", 30.0),
            default_non_fixed_rate=cost_dict.get("default_non_fixed_rate", 40.0),
            transport_cost_frozen_per_unit=cost_dict.get("transport_cost_frozen_per_unit", 0.5),
            transport_cost_ambient_per_unit=cost_dict.get("transport_cost_ambient_per_unit", 0.3),
            truck_fixed_cost=cost_dict.get("truck_fixed_cost", 100.0),
            storage_cost_frozen_per_unit_day=cost_dict.get("storage_cost_frozen_per_unit_day", 0.05),
            storage_cost_ambient_per_unit_day=cost_dict.get("storage_cost_ambient_per_unit_day", 0.02),
            waste_cost_multiplier=cost_dict.get("waste_cost_multiplier", 1.5),
            shortage_penalty_per_unit=cost_dict.get("shortage_penalty_per_unit", 10.0),
        )

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
        Parse all data from Excel file.

        Args:
            forecast_sheet: Name of forecast sheet
            locations_sheet: Name of locations sheet
            routes_sheet: Name of routes sheet
            labor_sheet: Name of labor calendar sheet
            trucks_sheet: Name of truck schedules sheet
            costs_sheet: Name of cost parameters sheet

        Returns:
            Tuple of (Forecast, locations, routes, labor_calendar, truck_schedules, cost_structure)
        """
        forecast = self.parse_forecast(forecast_sheet)
        locations = self.parse_locations(locations_sheet)
        routes = self.parse_routes(routes_sheet)
        labor_calendar = self.parse_labor_calendar(labor_sheet)
        truck_schedules = self.parse_truck_schedules(trucks_sheet)
        cost_structure = self.parse_cost_structure(costs_sheet)
        return forecast, locations, routes, labor_calendar, truck_schedules, cost_structure
