"""Excel parser for reading forecast files (.xlsm format)."""

from datetime import date
from pathlib import Path
from typing import Optional
import warnings

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
    Product,
)
from .product_alias_resolver import ProductAliasResolver


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
    - Sheet 'Alias' (optional): columns [Alias1, Alias2, Alias3, ...] where Alias1 is canonical product name

    Also supports SAP IBP export format (wide format with dates as columns).
    """

    def __init__(self, file_path: Path | str, product_alias_resolver: Optional[ProductAliasResolver] = None):
        """
        Initialize parser with Excel file path.

        Args:
            file_path: Path to the Excel file (.xlsm or .xlsx)
            product_alias_resolver: Optional product alias resolver for mapping product codes to canonical IDs

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If file is not .xlsm or .xlsx
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if self.file_path.suffix.lower() not in [".xlsm", ".xlsx"]:
            raise ValueError(f"File must be .xlsm or .xlsx: {file_path}")

        self.product_alias_resolver = product_alias_resolver

    def parse_forecast(self, sheet_name: str = "Forecast") -> Forecast:
        """
        Parse forecast data from Excel sheet.

        Supports both standard long format and SAP IBP wide format.
        If sheet_name="Forecast" doesn't exist, auto-detects SAP IBP format.

        Args:
            sheet_name: Name of the sheet containing forecast data (default: "Forecast")

        Returns:
            Forecast object with entries

        Raises:
            ValueError: If sheet is missing or malformed
        """
        # Try standard format first
        try:
            df = pd.read_excel(
                self.file_path,
                sheet_name=sheet_name,
                engine="openpyxl"
            )

            # Validate required columns
            required_cols = {"location_id", "product_id", "date", "quantity"}
            if required_cols.issubset(df.columns):
                # Standard format - use existing parsing logic
                entries = []
                unmapped_products = set()

                for _, row in df.iterrows():
                    raw_product_id = str(row["product_id"])

                    # Resolve product alias if resolver provided
                    product_id = raw_product_id
                    if self.product_alias_resolver:
                        resolved_id = self.product_alias_resolver.resolve_product_id(raw_product_id)
                        if resolved_id != raw_product_id:
                            product_id = resolved_id
                        elif not self.product_alias_resolver.is_mapped(raw_product_id):
                            unmapped_products.add(raw_product_id)

                    entry = ForecastEntry(
                        location_id=str(row["location_id"]),
                        product_id=product_id,  # Use resolved ID
                        forecast_date=pd.to_datetime(row["date"]).date(),
                        quantity=float(row["quantity"]),
                        confidence=float(row["confidence"]) if "confidence" in row and pd.notna(row["confidence"]) else None,
                    )
                    entries.append(entry)

                # Warn about unmapped products
                if unmapped_products:
                    warnings.warn(
                        f"Forecast contains {len(unmapped_products)} unmapped product codes: "
                        f"{sorted(list(unmapped_products)[:5])}{'...' if len(unmapped_products) > 5 else ''}. "
                        f"These will be used as-is. Consider adding them to the Alias sheet.",
                        UserWarning
                    )

                forecast_name = f"Forecast from {self.file_path.name}"
                return Forecast(name=forecast_name, entries=entries)
        except Exception:
            # Sheet doesn't exist or isn't standard format
            pass

        # Try SAP IBP format detection
        from .sap_ibp_parser import SapIbpParser
        sap_sheet = SapIbpParser.detect_sap_ibp_format(self.file_path)
        if sap_sheet:
            return SapIbpParser.parse_sap_ibp_forecast(
                self.file_path,
                sap_sheet,
                product_alias_resolver=self.product_alias_resolver  # Pass through resolver
            )

        # Neither format found
        raise ValueError(
            f"Could not find valid forecast data. "
            f"Tried: standard format in sheet '{sheet_name}', SAP IBP format auto-detection"
        )

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
                    location_name = row.get('name', 'Unknown')
                    raise ValueError(
                        f"\n{'='*70}\n"
                        f"MISSING REQUIRED PARAMETER: production_rate\n"
                        f"{'='*70}\n"
                        f"\n"
                        f"Manufacturing location '{location_name}' (ID: {row['id']}) is missing\n"
                        f"the required 'production_rate' column.\n"
                        f"\n"
                        f"REQUIRED ACTION:\n"
                        f"  1. Open your Network Configuration Excel file\n"
                        f"  2. Go to the 'Locations' sheet\n"
                        f"  3. Add a 'production_rate' column (if not present)\n"
                        f"  4. For location {row['id']}, set production_rate = 1400.0\n"
                        f"\n"
                        f"EXPLANATION:\n"
                        f"  - production_rate = units produced per labor hour\n"
                        f"  - Standard QBA manufacturing rate: 1400.0 units/hour\n"
                        f"  - This parameter is required for production scheduling\n"
                        f"    and optimization model constraints\n"
                        f"\n"
                        f"DOCUMENTATION:\n"
                        f"  - Template spec: data/examples/EXCEL_TEMPLATE_SPEC.md\n"
                        f"  - Migration guide: NETWORK_CONFIG_UPDATE_INSTRUCTIONS.md\n"
                        f"  - Example file: data/examples/Network_Config.xlsx\n"
                        f"\n"
                        f"{'='*70}\n"
                    )

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
                overtime_hours=float(row["overtime_hours"]) if "overtime_hours" in row and pd.notna(row["overtime_hours"]) else 2.0,
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
            # Pallet-based storage costs (legacy - 2025-10-17)
            storage_cost_fixed_per_pallet=cost_dict.get("storage_cost_fixed_per_pallet"),  # None if not present
            storage_cost_per_pallet_day_frozen=cost_dict.get("storage_cost_per_pallet_day_frozen"),  # None if not present
            storage_cost_per_pallet_day_ambient=cost_dict.get("storage_cost_per_pallet_day_ambient"),  # None if not present
            # Pallet-based storage costs (state-specific - 2025-10-18)
            storage_cost_fixed_per_pallet_frozen=cost_dict.get("storage_cost_fixed_per_pallet_frozen"),  # None if not present
            storage_cost_fixed_per_pallet_ambient=cost_dict.get("storage_cost_fixed_per_pallet_ambient"),  # None if not present
            waste_cost_multiplier=cost_dict.get("waste_cost_multiplier", 1.5),
            shortage_penalty_per_unit=cost_dict.get("shortage_penalty_per_unit", 10.0),
            # Freshness incentive (2025-10-22)
            freshness_incentive_weight=cost_dict.get("freshness_incentive_weight", 0.0),
            # Changeover cost (2025-10-22)
            changeover_cost_per_start=cost_dict.get("changeover_cost_per_start", 0.0),
            # Changeover waste/yield loss (2025-10-27)
            changeover_waste_units=cost_dict.get("changeover_waste_units", 0.0),
        )

    def parse_products(self, sheet_name: str = "Products") -> dict[str, Product]:
        """
        Parse product definitions from Excel sheet.

        Args:
            sheet_name: Name of the sheet containing product data (default: "Products")

        Returns:
            Dictionary mapping product_id to Product object

        Raises:
            ValueError: If sheet is missing or malformed
            ValueError: If units_per_mix column is missing (required as of 2025-10-23)
        """
        try:
            df = pd.read_excel(
                self.file_path,
                sheet_name=sheet_name,
                engine="openpyxl"
            )
        except ValueError as e:
            if "Worksheet" in str(e) and ("not found" in str(e) or "does not exist" in str(e)):
                raise ValueError(
                    f"\n{'='*70}\n"
                    f"MISSING PRODUCTS SHEET\n"
                    f"{'='*70}\n"
                    f"\n"
                    f"The Excel file '{self.file_path.name}' does not contain a '{sheet_name}' sheet.\n"
                    f"\n"
                    f"REQUIRED ACTION:\n"
                    f"  1. Open your Excel file: {self.file_path}\n"
                    f"  2. Create a new sheet named '{sheet_name}'\n"
                    f"  3. Add the following columns:\n"
                    f"     - product_id (string, required)\n"
                    f"     - name (string, required)\n"
                    f"     - sku (string, required)\n"
                    f"     - shelf_life_ambient_days (float, default: 17)\n"
                    f"     - shelf_life_frozen_days (float, default: 120)\n"
                    f"     - shelf_life_after_thaw_days (float, default: 14)\n"
                    f"     - min_acceptable_shelf_life_days (float, default: 7)\n"
                    f"     - units_per_mix (integer, required, must be > 0)\n"
                    f"\n"
                    f"EXAMPLE:\n"
                    f"  product_id | name      | sku   | ... | units_per_mix\n"
                    f"  -----------|-----------|-------|-----|---------------\n"
                    f"  G144       | Product A | G144  | ... | 415\n"
                    f"  G145       | Product B | G145  | ... | 387\n"
                    f"\n"
                    f"DOCUMENTATION:\n"
                    f"  - See: data/examples/EXCEL_TEMPLATE_SPEC.md\n"
                    f"  - Example: data/examples/Network_Config.xlsx\n"
                    f"\n"
                    f"{'='*70}\n"
                ) from e
            raise

        # Validate required columns
        required_cols = {"product_id", "name", "sku", "units_per_mix"}
        if not required_cols.issubset(df.columns):
            missing = required_cols - set(df.columns)

            # Special error for units_per_mix (new required field)
            if "units_per_mix" in missing:
                raise ValueError(
                    f"\n{'='*70}\n"
                    f"MISSING REQUIRED COLUMN: units_per_mix\n"
                    f"{'='*70}\n"
                    f"\n"
                    f"The Products sheet in '{self.file_path.name}' is missing the\n"
                    f"'units_per_mix' column, which is required as of 2025-10-23.\n"
                    f"\n"
                    f"REQUIRED ACTION:\n"
                    f"  1. Open your Excel file: {self.file_path}\n"
                    f"  2. Go to the '{sheet_name}' sheet\n"
                    f"  3. Add a new column named 'units_per_mix'\n"
                    f"  4. Fill in the number of units produced per mix for each product\n"
                    f"     (e.g., 415, 387, 520)\n"
                    f"\n"
                    f"EXPLANATION:\n"
                    f"  - units_per_mix defines how many units are produced in one batch\n"
                    f"  - Production must be in integer multiples of this value\n"
                    f"  - Example: If units_per_mix = 415, you can produce 0, 415, 830, 1245... units\n"
                    f"  - This enforces discrete batch production (mix-based planning)\n"
                    f"\n"
                    f"EXAMPLE:\n"
                    f"  product_id | name      | units_per_mix\n"
                    f"  -----------|-----------|--------------\n"
                    f"  G144       | Product A | 415\n"
                    f"  G145       | Product B | 387\n"
                    f"\n"
                    f"DOCUMENTATION:\n"
                    f"  - Design doc: docs/plans/2025-10-23-mix-based-production-design.md\n"
                    f"  - Template spec: data/examples/EXCEL_TEMPLATE_SPEC.md\n"
                    f"\n"
                    f"{'='*70}\n"
                )

            # Generic error for other missing columns
            raise ValueError(f"Missing required columns in Products sheet: {missing}")

        # Parse products
        products = {}
        for _, row in df.iterrows():
            # Check for empty/NaN units_per_mix before conversion
            if pd.isna(row["units_per_mix"]):
                raise ValueError(
                    f"\n{'='*70}\n"
                    f"EMPTY units_per_mix VALUE\n"
                    f"{'='*70}\n"
                    f"\n"
                    f"Product '{row['product_id']}' has an empty units_per_mix value.\n"
                    f"Each product must specify how many units are produced per mix.\n"
                    f"\n"
                    f"REQUIRED ACTION:\n"
                    f"  1. Open: {self.file_path}\n"
                    f"  2. Go to Products sheet, row for product '{row['product_id']}'\n"
                    f"  3. Fill in units_per_mix column with a positive integer\n"
                    f"     (e.g., 415, 387, 520)\n"
                    f"\n"
                    f"{'='*70}\n"
                )

            product = Product(
                id=str(row["product_id"]),
                name=str(row["name"]),
                sku=str(row["sku"]),
                ambient_shelf_life_days=float(row.get("shelf_life_ambient_days", 17.0)) if pd.notna(row.get("shelf_life_ambient_days")) else 17.0,
                frozen_shelf_life_days=float(row.get("shelf_life_frozen_days", 120.0)) if pd.notna(row.get("shelf_life_frozen_days")) else 120.0,
                thawed_shelf_life_days=float(row.get("shelf_life_after_thaw_days", 14.0)) if pd.notna(row.get("shelf_life_after_thaw_days")) else 14.0,
                min_acceptable_shelf_life_days=float(row.get("min_acceptable_shelf_life_days", 7.0)) if pd.notna(row.get("min_acceptable_shelf_life_days")) else 7.0,
                units_per_mix=int(row["units_per_mix"]),
            )
            products[product.id] = product

        return products

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
