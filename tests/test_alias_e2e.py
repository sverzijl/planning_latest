"""End-to-end integration tests for product alias resolution."""

import pytest
from pathlib import Path
from datetime import date
import pandas as pd

from src.parsers.multi_file_parser import MultiFileParser
from src.parsers.inventory_parser import InventoryParser
from src.parsers.product_alias_resolver import ProductAliasResolver


@pytest.fixture
def complete_test_dataset(tmp_path):
    """Create a complete test dataset with network config, forecast, and inventory."""
    network_file = tmp_path / "network_config.xlsx"
    forecast_file = tmp_path / "forecast.xlsx"
    inventory_file = tmp_path / "inventory.xlsx"

    # 1. Create Network Config with Alias sheet
    alias_data = {
        'Alias1': ['BREAD_WHITE_500G', 'BREAD_MULTIGRAIN_500G'],
        'Alias2': ['168846', '168847'],
        'Alias3': ['176299', '176283'],
        'Alias4': ['184226', '184222'],
    }
    alias_df = pd.DataFrame(alias_data)

    locations_data = {
        'id': ['6122', '6104', '6125', '6130'],
        'name': ['Manufacturing', 'Hub NSW', 'Hub VIC', 'Breadroom WA'],
        'type': ['manufacturing', 'storage', 'storage', 'breadroom'],
        'storage_mode': ['ambient', 'ambient', 'ambient', 'ambient'],
        'production_rate': [1400.0, None, None, None],
    }
    locations_df = pd.DataFrame(locations_data)

    routes_data = {
        'id': ['R1', 'R2', 'R3'],
        'origin_id': ['6122', '6122', '6104'],
        'destination_id': ['6104', '6125', '6130'],
        'transport_mode': ['ambient', 'ambient', 'ambient'],
        'transit_time_days': [1.0, 1.0, 2.0],
    }
    routes_df = pd.DataFrame(routes_data)

    labor_data = {
        'date': [date(2025, 1, 1), date(2025, 1, 2)],
        'fixed_hours': [12.0, 12.0],
        'regular_rate': [20.0, 20.0],
        'overtime_rate': [30.0, 30.0],
    }
    labor_df = pd.DataFrame(labor_data)

    trucks_data = {
        'id': ['T1', 'T2'],
        'truck_name': ['Morning NSW', 'Morning VIC'],
        'departure_type': ['morning', 'morning'],
        'departure_time': ['08:00:00', '08:00:00'],
        'destination_id': ['6104', '6125'],
        'capacity': [14080.0, 14080.0],
    }
    trucks_df = pd.DataFrame(trucks_data)

    costs_data = {
        'cost_type': ['production_cost_per_unit', 'shortage_penalty_per_unit'],
        'value': [0.5, 10.0],
    }
    costs_df = pd.DataFrame(costs_data)

    with pd.ExcelWriter(network_file, engine='openpyxl') as writer:
        alias_df.to_excel(writer, sheet_name='Alias', index=False)
        locations_df.to_excel(writer, sheet_name='Locations', index=False)
        routes_df.to_excel(writer, sheet_name='Routes', index=False)
        labor_df.to_excel(writer, sheet_name='LaborCalendar', index=False)
        trucks_df.to_excel(writer, sheet_name='TruckSchedules', index=False)
        costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

    # 2. Create Forecast using alias codes
    # Alias mapping:
    # Row 0: BREAD_WHITE_500G -> 168846 (Alias2), 176299 (Alias3), 184226 (Alias4)
    # Row 1: BREAD_MULTIGRAIN_500G -> 168847 (Alias2), 176283 (Alias3), 184222 (Alias4)
    forecast_data = {
        'location_id': ['6130', '6130', '6130', '6130'],
        'product_id': ['168846', '176283', '184226', '168847'],  # Mix of Alias2, Alias3, Alias4
        'date': [date(2025, 1, 5), date(2025, 1, 5), date(2025, 1, 6), date(2025, 1, 6)],
        'quantity': [100.0, 150.0, 120.0, 200.0],
    }
    forecast_df = pd.DataFrame(forecast_data)

    with pd.ExcelWriter(forecast_file, engine='openpyxl') as writer:
        forecast_df.to_excel(writer, sheet_name='Forecast', index=False)

    # 3. Create Inventory using different alias codes
    inventory_data = {
        'Material': ['176299', '184222', '168847'],  # Different aliases for same products
        'Plant': [6122, 6122, 6104],
        'Storage Location': [4000, 4000, 4000],
        'Unrestricted': [50.0, 30.0, 40.0],  # In cases
    }
    inventory_df = pd.DataFrame(inventory_data)

    with pd.ExcelWriter(inventory_file, engine='openpyxl') as writer:
        inventory_df.to_excel(writer, sheet_name='Sheet1', index=False)

    return {
        'network_file': network_file,
        'forecast_file': forecast_file,
        'inventory_file': inventory_file,
    }


class TestEndToEndWorkflow:
    """End-to-end tests for complete workflow with alias resolution."""

    def test_full_data_loading_workflow(self, complete_test_dataset):
        """Test complete workflow: load all data with alias resolution."""
        # Create multi-file parser
        parser = MultiFileParser(
            forecast_file=complete_test_dataset['forecast_file'],
            network_file=complete_test_dataset['network_file'],
            inventory_file=complete_test_dataset['inventory_file']
        )

        # Parse all data
        forecast, locations, routes, labor, trucks, costs = parser.parse_all()

        # Verify all data loaded correctly
        assert len(forecast.entries) == 4
        assert len(locations) == 4
        assert len(routes) == 3
        assert len(labor.days) == 2
        assert len(trucks) == 2

        # Check alias resolution worked
        product_ids = {entry.product_id for entry in forecast.entries}
        assert 'BREAD_WHITE_500G' in product_ids
        assert 'BREAD_MULTIGRAIN_500G' in product_ids

        # Original codes should NOT be present
        assert '168846' not in product_ids
        assert '176283' not in product_ids

    def test_forecast_inventory_product_alignment(self, complete_test_dataset):
        """Test that forecast and inventory products align after resolution."""
        # Create multi-file parser
        parser = MultiFileParser(
            forecast_file=complete_test_dataset['forecast_file'],
            network_file=complete_test_dataset['network_file'],
            inventory_file=complete_test_dataset['inventory_file']
        )

        # Parse forecast and inventory
        forecast = parser.parse_forecast()
        inventory = parser.parse_inventory()

        # Get product IDs from both
        forecast_products = {entry.product_id for entry in forecast.entries}
        inventory_products = {entry.product_id for entry in inventory.entries}

        # Should have common products (after alias resolution)
        common_products = forecast_products & inventory_products
        assert 'BREAD_WHITE_500G' in common_products or 'BREAD_MULTIGRAIN_500G' in common_products

    def test_product_consistency_validation(self, complete_test_dataset):
        """Test that all product references are consistent after resolution."""
        # Create multi-file parser
        parser = MultiFileParser(
            forecast_file=complete_test_dataset['forecast_file'],
            network_file=complete_test_dataset['network_file'],
            inventory_file=complete_test_dataset['inventory_file']
        )

        # Load all data
        forecast = parser.parse_forecast()
        inventory = parser.parse_inventory()

        # Get canonical products from resolver
        resolver = parser.parse_product_aliases()
        canonical_products = resolver.get_canonical_products()

        # All forecast products should be canonical
        forecast_products = {entry.product_id for entry in forecast.entries}
        assert forecast_products.issubset(canonical_products)

        # All inventory products should be canonical
        inventory_products = {entry.product_id for entry in inventory.entries}
        assert inventory_products.issubset(canonical_products)

    def test_location_consistency_validation(self, complete_test_dataset):
        """Test location consistency between network config and forecast."""
        # Create multi-file parser
        parser = MultiFileParser(
            forecast_file=complete_test_dataset['forecast_file'],
            network_file=complete_test_dataset['network_file']
        )

        # Parse data
        forecast = parser.parse_forecast()
        locations = parser.parse_locations()

        # Run consistency validation
        validation = parser.validate_consistency(forecast, locations, [])

        # Should have no missing locations
        assert len(validation['missing_locations']) == 0

    def test_quantity_aggregation_with_aliases(self, complete_test_dataset):
        """Test that quantities aggregate correctly when same product has multiple aliases."""
        # Create multi-file parser
        parser = MultiFileParser(
            forecast_file=complete_test_dataset['forecast_file'],
            network_file=complete_test_dataset['network_file'],
            inventory_file=complete_test_dataset['inventory_file']
        )

        # Parse forecast
        forecast = parser.parse_forecast()

        # Group by product and sum quantities
        product_totals = {}
        for entry in forecast.entries:
            if entry.product_id not in product_totals:
                product_totals[entry.product_id] = 0.0
            product_totals[entry.product_id] += entry.quantity

        # Check that products are properly aggregated
        # From forecast_data:
        # - 168846 -> BREAD_WHITE_500G: 100
        # - 176283 -> BREAD_MULTIGRAIN_500G: 150
        # - 184226 -> BREAD_WHITE_500G: 120
        # - 168847 -> BREAD_MULTIGRAIN_500G: 200
        # Total: BREAD_WHITE_500G = 100 + 120 = 220, BREAD_MULTIGRAIN_500G = 150 + 200 = 350
        assert product_totals.get('BREAD_WHITE_500G') == 220.0
        assert product_totals.get('BREAD_MULTIGRAIN_500G') == 350.0


class TestInventoryAliasResolution:
    """Tests for inventory parsing with alias resolution."""

    def test_inventory_parser_with_resolver(self, complete_test_dataset):
        """Test inventory parser with alias resolver."""
        # Create resolver
        resolver = ProductAliasResolver(
            complete_test_dataset['network_file'],
            sheet_name='Alias'
        )

        # Create inventory parser with resolver
        inv_parser = InventoryParser(
            complete_test_dataset['inventory_file'],
            product_alias_resolver=resolver
        )

        # Parse inventory
        inventory = inv_parser.parse()

        # Check that product codes are resolved
        product_ids = {entry.product_id for entry in inventory.entries}
        assert 'BREAD_WHITE_500G' in product_ids
        assert 'BREAD_MULTIGRAIN_500G' in product_ids

        # Original codes should NOT be present
        assert '176299' not in product_ids
        assert '184222' not in product_ids

    def test_inventory_quantities_converted_and_resolved(self, complete_test_dataset):
        """Test that inventory quantities are converted from cases to units AND resolved."""
        # Create resolver
        resolver = ProductAliasResolver(
            complete_test_dataset['network_file'],
            sheet_name='Alias'
        )

        # Create inventory parser with resolver
        inv_parser = InventoryParser(
            complete_test_dataset['inventory_file'],
            product_alias_resolver=resolver
        )

        # Parse inventory
        inventory = inv_parser.parse()

        # Check quantities (should be in units, not cases)
        # From inventory_data:
        # - 176299 (Alias3, Row 0) -> BREAD_WHITE_500G: 50 cases * 10 = 500 units
        # - 184222 (Alias4, Row 1) -> BREAD_MULTIGRAIN_500G: 30 cases * 10 = 300 units
        # - 168847 (Alias2, Row 1) -> BREAD_MULTIGRAIN_500G: 40 cases * 10 = 400 units

        product_quantities = {}
        for entry in inventory.entries:
            if entry.product_id not in product_quantities:
                product_quantities[entry.product_id] = 0.0
            product_quantities[entry.product_id] += entry.quantity

        # Note: 184222 and 168847 both resolve to BREAD_MULTIGRAIN_500G
        # They should be aggregated: 300 + 400 = 700 units
        assert product_quantities['BREAD_WHITE_500G'] == 500.0
        assert product_quantities['BREAD_MULTIGRAIN_500G'] == 700.0


class TestRealWorldScenarios:
    """Tests simulating real-world scenarios."""

    def test_sap_export_with_mixed_codes(self, tmp_path):
        """Test handling SAP export where forecast and inventory use different alias codes."""
        # Network config with aliases
        network_file = tmp_path / "network.xlsx"
        alias_data = {
            'Alias1': ['PRODUCT_A'],
            'Alias2': ['SAP_CODE_1'],
            'Alias3': ['SAP_CODE_2'],
            'Alias4': ['SAP_CODE_3'],
        }
        alias_df = pd.DataFrame(alias_data)

        locations_data = {
            'id': ['6122'],
            'name': ['Manufacturing'],
            'type': ['manufacturing'],
            'storage_mode': ['ambient'],
            'production_rate': [1400.0],
        }
        locations_df = pd.DataFrame(locations_data)

        with pd.ExcelWriter(network_file, engine='openpyxl') as writer:
            alias_df.to_excel(writer, sheet_name='Alias', index=False)
            locations_df.to_excel(writer, sheet_name='Locations', index=False)

        # Forecast using SAP_CODE_1
        forecast_file = tmp_path / "forecast.xlsx"
        forecast_data = {
            'location_id': ['6122'],
            'product_id': ['SAP_CODE_1'],
            'date': [date(2025, 1, 1)],
            'quantity': [100.0],
        }
        forecast_df = pd.DataFrame(forecast_data)

        with pd.ExcelWriter(forecast_file, engine='openpyxl') as writer:
            forecast_df.to_excel(writer, sheet_name='Forecast', index=False)

        # Inventory using SAP_CODE_2 and SAP_CODE_3
        inventory_file = tmp_path / "inventory.xlsx"
        inventory_data = {
            'Material': ['SAP_CODE_2', 'SAP_CODE_3'],
            'Plant': [6122, 6122],
            'Storage Location': [4000, 4000],
            'Unrestricted': [10.0, 20.0],
        }
        inventory_df = pd.DataFrame(inventory_data)

        with pd.ExcelWriter(inventory_file, engine='openpyxl') as writer:
            inventory_df.to_excel(writer, sheet_name='Sheet1', index=False)

        # Parse all data
        parser = MultiFileParser(
            forecast_file=forecast_file,
            network_file=network_file,
            inventory_file=inventory_file
        )

        forecast = parser.parse_forecast()
        inventory = parser.parse_inventory()

        # All should resolve to PRODUCT_A
        assert forecast.entries[0].product_id == 'PRODUCT_A'
        assert all(entry.product_id == 'PRODUCT_A' for entry in inventory.entries)

    def test_migration_scenario_add_aliases_to_existing_system(self, tmp_path):
        """Test migration scenario: adding aliases to existing system."""
        # Step 1: System without aliases
        network_file_v1 = tmp_path / "network_v1.xlsx"
        locations_data = {
            'id': ['6122'],
            'name': ['Manufacturing'],
            'type': ['manufacturing'],
            'storage_mode': ['ambient'],
            'production_rate': [1400.0],
        }
        locations_df = pd.DataFrame(locations_data)

        with pd.ExcelWriter(network_file_v1, engine='openpyxl') as writer:
            locations_df.to_excel(writer, sheet_name='Locations', index=False)

        forecast_file = tmp_path / "forecast.xlsx"
        forecast_data = {
            'location_id': ['6122'],
            'product_id': ['OLD_CODE'],
            'date': [date(2025, 1, 1)],
            'quantity': [100.0],
        }
        forecast_df = pd.DataFrame(forecast_data)

        with pd.ExcelWriter(forecast_file, engine='openpyxl') as writer:
            forecast_df.to_excel(writer, sheet_name='Forecast', index=False)

        # Parse without aliases
        parser_v1 = MultiFileParser(
            forecast_file=forecast_file,
            network_file=network_file_v1
        )
        forecast_v1 = parser_v1.parse_forecast()
        assert forecast_v1.entries[0].product_id == 'OLD_CODE'

        # Step 2: Add Alias sheet to network config
        network_file_v2 = tmp_path / "network_v2.xlsx"
        alias_data = {
            'Alias1': ['NEW_PRODUCT_NAME'],
            'Alias2': ['OLD_CODE'],
        }
        alias_df = pd.DataFrame(alias_data)

        with pd.ExcelWriter(network_file_v2, engine='openpyxl') as writer:
            alias_df.to_excel(writer, sheet_name='Alias', index=False)
            locations_df.to_excel(writer, sheet_name='Locations', index=False)

        # Parse with aliases
        parser_v2 = MultiFileParser(
            forecast_file=forecast_file,
            network_file=network_file_v2
        )
        forecast_v2 = parser_v2.parse_forecast()

        # Old code should now resolve to new name
        assert forecast_v2.entries[0].product_id == 'NEW_PRODUCT_NAME'

        # Quantities should be identical
        assert forecast_v1.entries[0].quantity == forecast_v2.entries[0].quantity
