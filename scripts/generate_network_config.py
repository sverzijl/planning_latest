"""
Script to generate Network_Config.xlsx with operational data.

This file contains:
- Locations: All network nodes (manufacturing, storage, breadrooms)
- Routes: All transport connections
- LaborCalendar: Daily labor availability for Jun 2 - Dec 22, 2025
- TruckSchedules: Weekly truck departure schedule
- CostParameters: Cost coefficients for optimization

Run: python scripts/generate_network_config.py
Output: data/examples/Network_Config.xlsx
"""

import pandas as pd
from datetime import date, time, timedelta
from pathlib import Path


def generate_locations():
    """Generate Locations sheet data."""
    locations = [
        # Manufacturing
        {"id": "6122", "name": "Manufacturing Site", "type": "manufacturing", "storage_mode": "both", "capacity": 100000},
        # Breadrooms (Hubs)
        {"id": "6104", "name": "QBA-Moorebank (NSW Hub)", "type": "breadroom", "storage_mode": "ambient", "capacity": 50000},
        {"id": "6125", "name": "QBA-Keilor Park (VIC Hub)", "type": "breadroom", "storage_mode": "ambient", "capacity": 50000},
        # Breadrooms (Hub-served)
        {"id": "6105", "name": "QBA-Rydalmere", "type": "breadroom", "storage_mode": "ambient", "capacity": 30000},
        {"id": "6103", "name": "QBA-Canberra", "type": "breadroom", "storage_mode": "ambient", "capacity": 15000},
        {"id": "6123", "name": "QBA-Clayton-Fairbank", "type": "breadroom", "storage_mode": "ambient", "capacity": 35000},
        {"id": "6134", "name": "QBA-West Richmond SA", "type": "breadroom", "storage_mode": "ambient", "capacity": 25000},
        {"id": "6120", "name": "QBA-Hobart", "type": "breadroom", "storage_mode": "both", "capacity": 10000},
        # Breadrooms (Direct/Special)
        {"id": "6110", "name": "QBA-Burleigh Heads", "type": "breadroom", "storage_mode": "ambient", "capacity": 40000},
        {"id": "6130", "name": "QBA-Canning Vale (WA Thawing)", "type": "breadroom", "storage_mode": "both", "capacity": 15000},
        # Frozen storage
        {"id": "Lineage", "name": "Lineage Frozen Storage", "type": "storage", "storage_mode": "frozen", "capacity": 50000},
    ]
    return pd.DataFrame(locations)


def generate_routes():
    """Generate Routes sheet data."""
    routes = [
        # Primary routes (Manufacturing to Hubs/Direct)
        {"id": "R1", "origin_id": "6122", "destination_id": "6104", "transport_mode": "ambient", "transit_time_days": 1.0, "cost": 0.30, "capacity": 14080},
        {"id": "R2", "origin_id": "6122", "destination_id": "6110", "transport_mode": "ambient", "transit_time_days": 1.5, "cost": 0.40, "capacity": 14080},
        {"id": "R3", "origin_id": "6122", "destination_id": "6125", "transport_mode": "ambient", "transit_time_days": 1.0, "cost": 0.30, "capacity": 14080},
        {"id": "R4", "origin_id": "6122", "destination_id": "Lineage", "transport_mode": "frozen", "transit_time_days": 0.5, "cost": 0.50, "capacity": 14080},
        # Secondary routes (Hubs to Spokes)
        {"id": "R5", "origin_id": "6104", "destination_id": "6105", "transport_mode": "ambient", "transit_time_days": 0.5, "cost": 0.15, "capacity": 14080},
        {"id": "R6", "origin_id": "6104", "destination_id": "6103", "transport_mode": "ambient", "transit_time_days": 1.0, "cost": 0.25, "capacity": 14080},
        {"id": "R7", "origin_id": "6125", "destination_id": "6123", "transport_mode": "ambient", "transit_time_days": 0.5, "cost": 0.15, "capacity": 14080},
        {"id": "R8", "origin_id": "6125", "destination_id": "6134", "transport_mode": "ambient", "transit_time_days": 1.5, "cost": 0.35, "capacity": 14080},
        {"id": "R9", "origin_id": "6125", "destination_id": "6120", "transport_mode": "ambient", "transit_time_days": 2.0, "cost": 0.45, "capacity": 14080},
        # Special frozen route (Frozen buffer to WA with thawing)
        {"id": "R10", "origin_id": "Lineage", "destination_id": "6130", "transport_mode": "frozen", "transit_time_days": 3.0, "cost": 1.20, "capacity": 14080},
    ]
    return pd.DataFrame(routes)


def generate_labor_calendar(start_date=date(2025, 6, 2), end_date=date(2025, 12, 22)):
    """
    Generate LaborCalendar sheet data for June 2 - Dec 22, 2025.

    Rules:
    - Monday-Friday: 12h fixed, regular/OT rates
    - Weekends: 0h fixed, 4h minimum, non-fixed rate
    - Public holidays: Same as weekends
    """
    # Public holidays in date range (2025)
    public_holidays = {
        date(2025, 6, 9),   # King's Birthday
        date(2025, 9, 26),  # Friday before AFL Grand Final
        date(2025, 11, 4),  # Melbourne Cup
        # Dec 25/26 are outside range (ends Dec 22)
    }

    labor_days = []
    current_date = start_date

    while current_date <= end_date:
        is_weekday = current_date.weekday() < 5  # 0-4 = Mon-Fri
        is_holiday = current_date in public_holidays

        if is_weekday and not is_holiday:
            # Standard weekday
            labor_days.append({
                "date": current_date,
                "fixed_hours": 12.0,
                "regular_rate": 25.00,
                "overtime_rate": 37.50,
                "non_fixed_rate": None,
                "minimum_hours": 0.0,
                "is_fixed_day": True,
            })
        else:
            # Weekend or public holiday
            labor_days.append({
                "date": current_date,
                "fixed_hours": 0.0,
                "regular_rate": 25.00,
                "overtime_rate": 37.50,
                "non_fixed_rate": 40.00,
                "minimum_hours": 4.0,
                "is_fixed_day": False,
            })

        current_date += timedelta(days=1)

    return pd.DataFrame(labor_days)


def generate_truck_schedules():
    """Generate TruckSchedules sheet data."""
    trucks = [
        # Morning trucks to 6125 (5x/week Mon-Fri)
        {"id": "T1", "truck_name": "Morning 6125 (Mon)", "departure_type": "morning", "departure_time": "08:00:00", "destination_id": "6125", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.30, "day_of_week": None, "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        {"id": "T2", "truck_name": "Morning 6125 (Tue)", "departure_type": "morning", "departure_time": "08:00:00", "destination_id": "6125", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.30, "day_of_week": None, "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        {"id": "T3", "truck_name": "Morning 6125 (Wed via Lineage)", "departure_type": "morning", "departure_time": "08:00:00", "destination_id": "6125", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.35, "day_of_week": "wednesday", "intermediate_stops": "Lineage", "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        {"id": "T4", "truck_name": "Morning 6125 (Thu)", "departure_type": "morning", "departure_time": "08:00:00", "destination_id": "6125", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.30, "day_of_week": None, "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        {"id": "T5", "truck_name": "Morning 6125 (Fri)", "departure_type": "morning", "departure_time": "08:00:00", "destination_id": "6125", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.30, "day_of_week": None, "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        # Afternoon trucks (day-specific destinations)
        {"id": "T6", "truck_name": "Afternoon 6104 (Mon)", "departure_type": "afternoon", "departure_time": "14:00:00", "destination_id": "6104", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.30, "day_of_week": "monday", "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        {"id": "T7", "truck_name": "Afternoon 6110 (Tue)", "departure_type": "afternoon", "departure_time": "14:00:00", "destination_id": "6110", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.40, "day_of_week": "tuesday", "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        {"id": "T8", "truck_name": "Afternoon 6104 (Wed)", "departure_type": "afternoon", "departure_time": "14:00:00", "destination_id": "6104", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.30, "day_of_week": "wednesday", "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        {"id": "T9", "truck_name": "Afternoon 6110 (Thu)", "departure_type": "afternoon", "departure_time": "14:00:00", "destination_id": "6110", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.40, "day_of_week": "thursday", "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        {"id": "T10", "truck_name": "Afternoon 6110 (Fri)", "departure_type": "afternoon", "departure_time": "14:00:00", "destination_id": "6110", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.40, "day_of_week": "friday", "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
        {"id": "T11", "truck_name": "Afternoon 6104 (Fri #2)", "departure_type": "afternoon", "departure_time": "14:00:00", "destination_id": "6104", "capacity": 14080, "cost_fixed": 100.0, "cost_per_unit": 0.30, "day_of_week": "friday", "intermediate_stops": None, "pallet_capacity": 44, "units_per_pallet": 320, "units_per_case": 10},
    ]
    return pd.DataFrame(trucks)


def generate_cost_parameters():
    """Generate CostParameters sheet data."""
    costs = [
        {"cost_type": "production_cost_per_unit", "value": 5.00, "unit": "$/unit"},
        {"cost_type": "setup_cost", "value": 0.00, "unit": "$"},
        {"cost_type": "default_regular_rate", "value": 25.00, "unit": "$/hour"},
        {"cost_type": "default_overtime_rate", "value": 37.50, "unit": "$/hour"},
        {"cost_type": "default_non_fixed_rate", "value": 40.00, "unit": "$/hour"},
        {"cost_type": "transport_cost_frozen_per_unit", "value": 0.50, "unit": "$/unit"},
        {"cost_type": "transport_cost_ambient_per_unit", "value": 0.30, "unit": "$/unit"},
        {"cost_type": "truck_fixed_cost", "value": 100.00, "unit": "$/departure"},
        {"cost_type": "storage_cost_frozen_per_unit_day", "value": 0.10, "unit": "$/(unit·day)"},
        {"cost_type": "storage_cost_ambient_per_unit_day", "value": 0.05, "unit": "$/(unit·day)"},
        {"cost_type": "waste_cost_multiplier", "value": 1.5, "unit": "-"},
        {"cost_type": "shortage_penalty_per_unit", "value": 10.00, "unit": "$/unit"},
    ]
    return pd.DataFrame(costs)


def main():
    """Generate Network_Config.xlsx file."""
    # Generate all sheets
    print("Generating Locations sheet...")
    df_locations = generate_locations()

    print("Generating Routes sheet...")
    df_routes = generate_routes()

    print("Generating LaborCalendar sheet (204 days)...")
    df_labor = generate_labor_calendar()

    print("Generating TruckSchedules sheet...")
    df_trucks = generate_truck_schedules()

    print("Generating CostParameters sheet...")
    df_costs = generate_cost_parameters()

    # Create output path
    output_path = Path(__file__).parent.parent / "data" / "examples" / "Network_Config.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to Excel with multiple sheets
    print(f"Writing to {output_path}...")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_locations.to_excel(writer, sheet_name="Locations", index=False)
        df_routes.to_excel(writer, sheet_name="Routes", index=False)
        df_labor.to_excel(writer, sheet_name="LaborCalendar", index=False)
        df_trucks.to_excel(writer, sheet_name="TruckSchedules", index=False)
        df_costs.to_excel(writer, sheet_name="CostParameters", index=False)

    print(f"✅ Successfully created {output_path}")
    print("\nSummary:")
    print(f"  - Locations: {len(df_locations)} locations")
    print(f"  - Routes: {len(df_routes)} routes")
    print(f"  - LaborCalendar: {len(df_labor)} days (Jun 2 - Dec 22, 2025)")
    print(f"  - TruckSchedules: {len(df_trucks)} weekly truck departures")
    print(f"  - CostParameters: {len(df_costs)} cost types")


if __name__ == "__main__":
    main()
