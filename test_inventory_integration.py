#!/usr/bin/env python3
"""Integration test for inventory upload functionality."""

from datetime import date
from pathlib import Path

from src.parsers import MultiFileParser, ProductAliasResolver, InventoryParser
from src.models import InventorySnapshot

# File paths
NETWORK_FILE = "data/examples/Network_Config.xlsx"
INVENTORY_FILE = "data/examples/inventory.XLSX"

def test_product_alias_resolver():
    """Test product alias resolution."""
    print("=" * 80)
    print("TEST 1: Product Alias Resolver")
    print("=" * 80)

    resolver = ProductAliasResolver(NETWORK_FILE)

    print(f"Alias resolver: {resolver}")
    print(f"Canonical products: {resolver.get_canonical_products()}")

    # Test resolving a known alias
    product_code = "176283"
    canonical = resolver.resolve_product_id(product_code)
    print(f"\nResolved {product_code} → {canonical}")

    # Test unmapped code
    unmapped = "999999"
    resolved_unmapped = resolver.resolve_product_id(unmapped)
    print(f"Unmapped {unmapped} → {resolved_unmapped}")

    print("✓ Product alias resolver test passed\n")


def test_inventory_parser():
    """Test inventory parsing."""
    print("=" * 80)
    print("TEST 2: Inventory Parser")
    print("=" * 80)

    # Create alias resolver
    alias_resolver = ProductAliasResolver(NETWORK_FILE)

    # Create inventory parser
    parser = InventoryParser(
        INVENTORY_FILE,
        product_alias_resolver=alias_resolver,
        snapshot_date=date(2025, 1, 1)
    )

    # Parse inventory
    inventory = parser.parse()

    print(f"Inventory snapshot: {inventory}")
    print(f"Total entries: {inventory.get_entry_count()}")
    print(f"Total quantity: {inventory.get_total_quantity():.0f} units")

    print(f"\nQuantity by location:")
    for loc_id, qty in inventory.get_quantity_by_location().items():
        print(f"  {loc_id}: {qty:.0f} units")

    print(f"\nQuantity by product:")
    for prod_id, qty in list(inventory.get_quantity_by_product().items())[:5]:
        print(f"  {prod_id}: {qty:.0f} units")

    print(f"\nQuantity by storage location:")
    for stor_loc, qty in inventory.get_quantity_by_storage_location().items():
        print(f"  {stor_loc}: {qty:.0f} units")

    # Test optimization dict conversion
    opt_dict = inventory.to_optimization_dict()
    print(f"\nOptimization dict entries: {len(opt_dict)}")
    print(f"Sample entries:")
    for i, (key, qty) in enumerate(list(opt_dict.items())[:3]):
        print(f"  {key}: {qty:.0f} units")
        if i >= 2:
            break

    print("✓ Inventory parser test passed\n")


def test_multi_file_parser():
    """Test MultiFileParser with inventory."""
    print("=" * 80)
    print("TEST 3: MultiFileParser Integration")
    print("=" * 80)

    parser = MultiFileParser(
        forecast_file=None,  # Not testing forecast
        network_file=NETWORK_FILE,
        inventory_file=INVENTORY_FILE
    )

    # Parse aliases
    aliases = parser.parse_product_aliases()
    print(f"Product aliases: {aliases}")

    # Parse inventory
    inventory = parser.parse_inventory(snapshot_date=date(2025, 1, 1))
    print(f"Inventory: {inventory}")
    print(f"Total: {inventory.get_total_quantity():.0f} units")

    # Verify alias resolution worked
    opt_dict = inventory.to_optimization_dict()
    print(f"\nOptimization dict has {len(opt_dict)} location-product combinations")

    print("✓ MultiFileParser integration test passed\n")


def main():
    """Run all tests."""
    print("\n")
    print("*" * 80)
    print("INVENTORY INTEGRATION TESTS")
    print("*" * 80)
    print()

    try:
        test_product_alias_resolver()
        test_inventory_parser()
        test_multi_file_parser()

        print("=" * 80)
        print("ALL TESTS PASSED ✓")
        print("=" * 80)
        print()

    except Exception as e:
        print()
        print("=" * 80)
        print(f"TEST FAILED ✗")
        print("=" * 80)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
