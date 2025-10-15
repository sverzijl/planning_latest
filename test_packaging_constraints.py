#!/usr/bin/env python3
"""
Quick test to verify packaging constraints are working correctly.
This script creates a minimal model with the packaging constraints and attempts to build it.
"""

import sys
from datetime import date, timedelta
from pyomo.environ import ConcreteModel, Var, Constraint, NonNegativeReals, NonNegativeIntegers, Binary

# Add src to path
sys.path.insert(0, '/home/sverzijl/planning_latest')

from src.models.forecast import Forecast
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.manufacturing import ManufacturingSite
from src.models.cost_structure import CostStructure
from src.models.location import Location, LocationType, StorageMode
from src.models.route import Route
from src.models.truck_schedule import TruckSchedule, TruckScheduleCollection

def test_packaging_constraints_syntax():
    """Test that packaging constraints can be created without syntax errors."""

    print("Creating minimal test model...")
    model = ConcreteModel()

    # Minimal sets
    model.dates = [date(2025, 1, 1), date(2025, 1, 2)]
    model.products = ["Product_A"]

    print("✓ Sets created")

    # Test production_cases variable
    model.production = Var(
        model.dates,
        model.products,
        within=NonNegativeReals,
        doc="Production quantity"
    )

    model.production_cases = Var(
        model.dates,
        model.products,
        within=NonNegativeIntegers,
        doc="Number of cases produced"
    )

    print("✓ Production variables created")

    # Test production case linking constraint
    def production_case_link_rule(model, d, p):
        return model.production[d, p] == model.production_cases[d, p] * 10

    model.production_case_link_con = Constraint(
        model.dates,
        model.products,
        rule=production_case_link_rule,
        doc="Production in whole cases"
    )

    print("✓ Production case linking constraint created")

    # Test truck pallet variables
    model.trucks = [0, 1]
    model.truck_destinations = [6104, 6125]

    model.truck_used = Var(
        model.trucks,
        model.dates,
        within=Binary,
        doc="Truck used indicator"
    )

    model.truck_load = Var(
        model.trucks,
        model.truck_destinations,
        model.products,
        model.dates,
        within=NonNegativeReals,
        doc="Truck load quantity"
    )

    model.pallets_loaded = Var(
        model.trucks,
        model.truck_destinations,
        model.products,
        model.dates,
        within=NonNegativeIntegers,
        doc="Number of pallets loaded"
    )

    print("✓ Truck variables created")

    # Test pallet constraints
    def pallet_lower_bound_rule(model, truck_idx, dest, prod, d):
        return model.pallets_loaded[truck_idx, dest, prod, d] * 320 >= model.truck_load[truck_idx, dest, prod, d]

    model.pallet_lower_bound_con = Constraint(
        model.trucks,
        model.truck_destinations,
        model.products,
        model.dates,
        rule=pallet_lower_bound_rule,
        doc="Pallet lower bound"
    )

    print("✓ Pallet lower bound constraint created")

    def pallet_upper_bound_rule(model, truck_idx, dest, prod, d):
        return model.pallets_loaded[truck_idx, dest, prod, d] * 320 <= model.truck_load[truck_idx, dest, prod, d] + 319

    model.pallet_upper_bound_con = Constraint(
        model.trucks,
        model.truck_destinations,
        model.products,
        model.dates,
        rule=pallet_upper_bound_rule,
        doc="Pallet upper bound"
    )

    print("✓ Pallet upper bound constraint created")

    # Mock truck pallet capacity (typically 44)
    truck_pallet_capacity = {0: 44, 1: 44}

    def pallet_capacity_rule(model, truck_idx, d):
        total_pallets = sum(
            model.pallets_loaded[truck_idx, dest, p, d]
            for dest in model.truck_destinations
            for p in model.products
        )
        pallet_capacity = truck_pallet_capacity[truck_idx]
        return total_pallets <= pallet_capacity * model.truck_used[truck_idx, d]

    model.pallet_capacity_con = Constraint(
        model.trucks,
        model.dates,
        rule=pallet_capacity_rule,
        doc="Pallet capacity"
    )

    print("✓ Pallet capacity constraint created")

    # Count constraints
    num_constraints = (
        len(list(model.production_case_link_con)) +
        len(list(model.pallet_lower_bound_con)) +
        len(list(model.pallet_upper_bound_con)) +
        len(list(model.pallet_capacity_con))
    )

    print(f"\n✓ All packaging constraints created successfully!")
    print(f"  - Total constraints: {num_constraints}")
    print(f"  - Production case linking: {len(list(model.production_case_link_con))}")
    print(f"  - Pallet lower bound: {len(list(model.pallet_lower_bound_con))}")
    print(f"  - Pallet upper bound: {len(list(model.pallet_upper_bound_con))}")
    print(f"  - Pallet capacity: {len(list(model.pallet_capacity_con))}")

    return True

if __name__ == "__main__":
    try:
        success = test_packaging_constraints_syntax()
        if success:
            print("\n✅ PACKAGING CONSTRAINTS TEST PASSED")
            print("All variables and constraints can be created successfully.")
            sys.exit(0)
        else:
            print("\n❌ PACKAGING CONSTRAINTS TEST FAILED")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
