#!/usr/bin/env python3
"""
Verify that the Pyomo model correctly tracks inventory at ALL locations.

This script examines the model structure to confirm:
1. All 10 locations are in self.inventory_locations
2. Inventory variables are created for all locations
3. Inventory balance constraints are created for all locations
"""

from datetime import datetime, timedelta
from pathlib import Path

from src.parsers.excel_parser import ExcelParser
from src.optimization.integrated_model import IntegratedProductionDistributionModel
from src.models.truck_schedule import TruckScheduleCollection
from src.models.location import LocationType


def main():
    print("=" * 80)
    print("PYOMO MODEL INVENTORY LOCATION VERIFICATION")
    print("=" * 80)
    print()

    # Parse data
    print("Parsing data...")
    network_parser = ExcelParser('/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx')
    forecast_parser = ExcelParser('/home/sverzijl/planning_latest/data/examples/Gfree Forecast_Converted.xlsx')

    locations = network_parser.parse_locations()
    routes = network_parser.parse_routes()
    labor_calendar = network_parser.parse_labor_calendar()
    truck_schedules_list = network_parser.parse_truck_schedules()
    truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)
    cost_structure = network_parser.parse_cost_structure()
    manufacturing_site = next((loc for loc in locations if loc.type == LocationType.MANUFACTURING), None)
    forecast = forecast_parser.parse_forecast()
    print("Data parsed successfully!")
    print()

    # Create model
    print("Creating optimization model...")
    model = IntegratedProductionDistributionModel(
        forecast=forecast,
        locations=locations,
        routes=routes,
        manufacturing_site=manufacturing_site,
        labor_calendar=labor_calendar,
        truck_schedules=truck_schedules,
        cost_structure=cost_structure,
        allow_shortages=True,
        enforce_shelf_life=True
    )
    print(f"Model planning horizon: {model.start_date} to {model.end_date}")
    print()

    # Expected locations
    expected_locations = {
        '6122',  # Manufacturing
        '6104',  # NSW/ACT Hub
        '6125',  # VIC/TAS/SA Hub
        '6103',  # Sydney breadroom
        '6105',  # Melbourne breadroom
        '6107',  # Brisbane breadroom
        '6110',  # Canberra breadroom
        '6115',  # Hobart breadroom
        '6118',  # Perth breadroom
        '6123',  # Adelaide breadroom
        '6127',  # Gold Coast breadroom
        '6130',  # Cairns breadroom (with thawing!)
    }

    print("EXPECTED LOCATIONS (10 total):")
    print("-" * 80)
    for loc_id in sorted(expected_locations):
        loc = model.location_by_id.get(loc_id)
        if loc:
            loc_type = loc.type.value if hasattr(loc.type, 'value') else str(loc.type)
            storage_mode = loc.storage_mode.value if hasattr(loc.storage_mode, 'value') else str(loc.storage_mode)
            print(f"  {loc_id}: {loc.name} ({loc_type}, {storage_mode})")
        else:
            print(f"  {loc_id}: NOT FOUND IN LOCATION DATA")
    print()

    # Check model.destinations
    print("MODEL DESTINATIONS (from forecast):")
    print("-" * 80)
    print(f"  Count: {len(model.destinations)}")
    for loc_id in sorted(model.destinations):
        print(f"  - {loc_id}")
    print()

    # Check model.intermediate_storage
    print("MODEL INTERMEDIATE STORAGE:")
    print("-" * 80)
    print(f"  Count: {len(model.intermediate_storage)}")
    for loc_id in sorted(model.intermediate_storage):
        loc = model.location_by_id.get(loc_id)
        if loc:
            print(f"  - {loc_id}: {loc.name}")
        else:
            print(f"  - {loc_id}: (location object not found)")
    print()

    # Check model.inventory_locations
    print("MODEL INVENTORY_LOCATIONS:")
    print("-" * 80)
    print(f"  Count: {len(model.inventory_locations)}")
    for loc_id in sorted(model.inventory_locations):
        if loc_id == '6122_Storage':
            print(f"  - {loc_id}: Virtual manufacturing storage")
        else:
            loc = model.location_by_id.get(loc_id)
            if loc:
                print(f"  - {loc_id}: {loc.name}")
            else:
                print(f"  - {loc_id}: (location object not found)")
    print()

    # Check which expected locations are missing
    missing_from_inventory = expected_locations - model.inventory_locations
    if missing_from_inventory:
        print("WARNING: MISSING FROM INVENTORY_LOCATIONS:")
        print("-" * 80)
        for loc_id in sorted(missing_from_inventory):
            loc = model.location_by_id.get(loc_id)
            if loc:
                loc_type = loc.type.value if hasattr(loc.type, 'value') else str(loc.type)
                print(f"  - {loc_id}: {loc.name} ({loc_type})")
            else:
                print(f"  - {loc_id}: (location object not found)")
        print()

    # Build the model to create variables
    print("Building Pyomo model...")
    pyomo_model = model.build_model()
    print("Model built successfully!")
    print()

    # Check inventory variable index sets
    print("INVENTORY VARIABLE INDEX SETS:")
    print("-" * 80)

    # Frozen inventory
    frozen_locations = set()
    for (loc, prod, date) in model.inventory_frozen_index_set:
        frozen_locations.add(loc)

    print(f"Frozen inventory locations (count: {len(frozen_locations)}):")
    for loc_id in sorted(frozen_locations):
        if loc_id == '6122_Storage':
            print(f"  - {loc_id}: Virtual storage (should NOT have frozen)")
        else:
            loc = model.location_by_id.get(loc_id)
            if loc:
                storage_mode = loc.storage_mode.value if hasattr(loc.storage_mode, 'value') else str(loc.storage_mode)
                print(f"  - {loc_id}: {loc.name} ({storage_mode})")
            else:
                print(f"  - {loc_id}: (location object not found)")
    print()

    # Ambient inventory
    ambient_locations = set()
    for (loc, prod, date) in model.inventory_ambient_index_set:
        ambient_locations.add(loc)

    print(f"Ambient inventory locations (count: {len(ambient_locations)}):")
    for loc_id in sorted(ambient_locations):
        if loc_id == '6122_Storage':
            print(f"  - {loc_id}: Virtual manufacturing storage")
        else:
            loc = model.location_by_id.get(loc_id)
            if loc:
                storage_mode = loc.storage_mode.value if hasattr(loc.storage_mode, 'value') else str(loc.storage_mode)
                print(f"  - {loc_id}: {loc.name} ({storage_mode})")
            else:
                print(f"  - {loc_id}: (location object not found)")
    print()

    # Check for missing expected locations
    all_inventory_locations = frozen_locations | ambient_locations
    # Remove virtual location for comparison
    actual_physical_locations = all_inventory_locations - {'6122_Storage'}

    missing_from_variables = expected_locations - actual_physical_locations
    if missing_from_variables:
        print("WARNING: EXPECTED LOCATIONS MISSING FROM INVENTORY VARIABLES:")
        print("-" * 80)
        for loc_id in sorted(missing_from_variables):
            loc = model.location_by_id.get(loc_id)
            if loc:
                loc_type = loc.type.value if hasattr(loc.type, 'value') else str(loc.type)
                storage_mode = loc.storage_mode.value if hasattr(loc.storage_mode, 'value') else str(loc.storage_mode)
                print(f"  - {loc_id}: {loc.name} ({loc_type}, {storage_mode})")
            else:
                print(f"  - {loc_id}: (location object not found)")
        print()
    else:
        print("SUCCESS: All expected locations have inventory variables!")
        print()

    # Check inventory balance constraints
    print("INVENTORY BALANCE CONSTRAINTS:")
    print("-" * 80)

    frozen_constraint_locs = set()
    for (loc, prod, date) in pyomo_model.inventory_frozen_index:
        frozen_constraint_locs.add(loc)

    ambient_constraint_locs = set()
    for (loc, prod, date) in pyomo_model.inventory_ambient_index:
        ambient_constraint_locs.add(loc)

    print(f"Frozen balance constraints: {len(frozen_constraint_locs)} locations")
    print(f"Ambient balance constraints: {len(ambient_constraint_locs)} locations")
    print()

    all_constraint_locations = frozen_constraint_locs | ambient_constraint_locs
    actual_constraint_locations = all_constraint_locations - {'6122_Storage'}

    missing_from_constraints = expected_locations - actual_constraint_locations
    if missing_from_constraints:
        print("WARNING: EXPECTED LOCATIONS MISSING FROM INVENTORY CONSTRAINTS:")
        print("-" * 80)
        for loc_id in sorted(missing_from_constraints):
            loc = model.location_by_id.get(loc_id)
            if loc:
                loc_type = loc.type.value if hasattr(loc.type, 'value') else str(loc.type)
                storage_mode = loc.storage_mode.value if hasattr(loc.storage_mode, 'value') else str(loc.storage_mode)
                print(f"  - {loc_id}: {loc.name} ({loc_type}, {storage_mode})")
            else:
                print(f"  - {loc_id}: (location object not found)")
        print()
    else:
        print("SUCCESS: All expected locations have inventory balance constraints!")
        print()

    # Summary
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Expected locations: {len(expected_locations)}")
    print(f"Locations in inventory_locations set: {len(model.inventory_locations)}")
    print(f"Locations with inventory variables: {len(actual_physical_locations)}")
    print(f"Locations with inventory constraints: {len(actual_constraint_locations)}")
    print()

    if missing_from_inventory or missing_from_variables or missing_from_constraints:
        print("RESULT: ISSUES FOUND - Some locations are missing from model!")
    else:
        print("RESULT: MODEL IS CORRECT - All locations properly tracked!")
    print()

    # Check specific locations of interest
    print("SPECIFIC LOCATION CHECKS:")
    print("-" * 80)

    for loc_id in ['6104', '6125', '6130']:
        loc = model.location_by_id.get(loc_id)
        if not loc:
            print(f"{loc_id}: NOT FOUND in location data")
            continue

        print(f"\n{loc_id} ({loc.name}):")
        loc_type = loc.type.value if hasattr(loc.type, 'value') else str(loc.type)
        storage_mode = loc.storage_mode.value if hasattr(loc.storage_mode, 'value') else str(loc.storage_mode)
        print(f"  Type: {loc_type}")
        print(f"  Storage mode: {storage_mode}")
        print(f"  In destinations: {loc_id in model.destinations}")
        print(f"  In intermediate_storage: {loc_id in model.intermediate_storage}")
        print(f"  In inventory_locations: {loc_id in model.inventory_locations}")
        print(f"  Has frozen variables: {loc_id in frozen_locations}")
        print(f"  Has ambient variables: {loc_id in ambient_locations}")
        print(f"  Has frozen constraints: {loc_id in frozen_constraint_locs}")
        print(f"  Has ambient constraints: {loc_id in ambient_constraint_locs}")


if __name__ == "__main__":
    main()
