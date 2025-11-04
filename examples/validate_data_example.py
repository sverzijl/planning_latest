#!/usr/bin/env python3
"""
Example: Using the Data Validation Architecture

This script demonstrates how to use the robust data validation layer
to load and validate planning data before optimization.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.validation.data_coordinator import load_validated_data
from src.validation.planning_data_schema import ValidationError


def main():
    """Load and validate planning data with fail-fast error handling."""

    print("=" * 80)
    print("DATA VALIDATION EXAMPLE")
    print("=" * 80)

    # Define data files
    forecast_file = "data/examples/Gluten Free Forecast - Latest.xlsm"
    network_file = "data/examples/Network_Config.xlsx"
    inventory_file = "data/examples/inventory_latest.XLSX"

    print(f"\nData files:")
    print(f"  Forecast: {forecast_file}")
    print(f"  Network:  {network_file}")
    print(f"  Inventory: {inventory_file}")

    # Attempt to load and validate
    print(f"\nLoading and validating data...")
    print(f"(This will fail fast if any data issues are found)")

    try:
        # Load with validation
        data = load_validated_data(
            forecast_file=forecast_file,
            network_file=network_file,
            inventory_file=inventory_file,
            planning_weeks=4
        )

        # If we get here, data is valid!
        print(f"\n✓ DATA VALIDATION SUCCESSFUL!")
        print(data.summary())

        # Show some statistics
        print(f"\nValidation Statistics:")
        print(f"  Products validated: {len(data.products)}")
        print(f"  Nodes validated: {len(data.nodes)}")
        print(f"  Demand entries validated: {len(data.demand_entries)}")
        print(f"  Inventory entries validated: {len(data.inventory_entries)}")

        # Check for common issues
        demand_product_ids = {e.product_id for e in data.demand_entries}
        inventory_product_ids = {e.product_id for e in data.inventory_entries}

        common_products = demand_product_ids & inventory_product_ids
        demand_only = demand_product_ids - inventory_product_ids
        inventory_only = inventory_product_ids - demand_product_ids

        print(f"\nProduct ID Analysis:")
        print(f"  Products with both demand and inventory: {len(common_products)}")
        print(f"  Products with demand only (no inventory): {len(demand_only)}")
        print(f"  Products with inventory only (no demand): {len(inventory_only)}")

        if inventory_only:
            print(f"\n⚠️  Warning: {len(inventory_only)} products have inventory but no demand")
            print(f"   Sample: {list(inventory_only)[:5]}")
            print(f"   This inventory may not be used by the model")

        # Ready for optimization
        print(f"\n✓ Data is ready for optimization model!")

        return 0

    except ValidationError as e:
        # Validation failed - print detailed error
        print(f"\n✗ DATA VALIDATION FAILED!")
        print(f"\n{e}")

        print(f"\nRecommended Actions:")
        if "product ID" in str(e).lower():
            print(f"  1. Check if inventory uses SKU codes while forecast uses product names")
            print(f"  2. Add ProductAliasResolver to map SKU codes to product names")
            print(f"  3. Update inventory file to use consistent product IDs")
        elif "node" in str(e).lower():
            print(f"  1. Check node IDs in forecast match network config")
            print(f"  2. Add missing nodes to network config")
            print(f"  3. Fix typos in node IDs")
        elif "date" in str(e).lower():
            print(f"  1. Check planning start date vs inventory snapshot date")
            print(f"  2. Ensure inventory is measured before planning starts")
            print(f"  3. Adjust date ranges as needed")

        return 1

    except Exception as e:
        # Unexpected error
        print(f"\n✗ UNEXPECTED ERROR!")
        print(f"\n{type(e).__name__}: {e}")

        import traceback
        traceback.print_exc()

        return 1


if __name__ == "__main__":
    sys.exit(main())
