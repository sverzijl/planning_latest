"""Tests for Excel parser."""

import pytest
import pandas as pd
from pathlib import Path
from datetime import date

from src.parsers import ExcelParser
from src.models import CostStructure


class TestExcelParser:
    """Tests for ExcelParser class."""

    def test_parser_initialization_with_nonexistent_file(self):
        """Test that parser raises error for non-existent file."""
        with pytest.raises(FileNotFoundError):
            ExcelParser("nonexistent_file.xlsm")

    def test_parser_initialization_with_wrong_extension(self, tmp_path):
        """Test that parser raises error for wrong file extension."""
        # Create a temporary file with wrong extension
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        with pytest.raises(ValueError, match="must be .xlsm or .xlsx"):
            ExcelParser(test_file)

    # TODO: Add tests with actual Excel files
    # These will require sample Excel files in data/examples/
    # def test_parse_forecast(self):
    #     """Test parsing forecast data."""
    #     pass
    #
    # def test_parse_locations(self):
    #     """Test parsing location data."""
    #     pass
    #
    # def test_parse_routes(self):
    #     """Test parsing route data."""
    #     pass


class TestExcelParserCostStructureStateSpecific:
    """Tests for parsing state-specific fixed pallet costs from Excel."""

    def test_parse_cost_structure_with_state_specific_fixed_costs(self, tmp_path):
        """
        Test parsing state-specific fixed pallet costs from CostParameters sheet.

        When storage_cost_fixed_per_pallet_frozen and
        storage_cost_fixed_per_pallet_ambient are present in the Excel file,
        they should be parsed into CostStructure and accessible via
        get_fixed_pallet_costs().
        """
        test_file = tmp_path / "test_costs.xlsx"

        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            {'cost_type': 'storage_cost_fixed_per_pallet_frozen', 'value': 5.0},
            {'cost_type': 'storage_cost_fixed_per_pallet_ambient', 'value': 2.0},
            {'cost_type': 'shortage_penalty_per_unit', 'value': 10.0},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify fields are parsed correctly
        assert cost_structure.storage_cost_fixed_per_pallet_frozen == 5.0
        assert cost_structure.storage_cost_fixed_per_pallet_ambient == 2.0

        # Verify get_fixed_pallet_costs() returns state-specific values
        frozen_fixed, ambient_fixed = cost_structure.get_fixed_pallet_costs()
        assert frozen_fixed == 5.0, "Frozen fixed cost should be 5.0"
        assert ambient_fixed == 2.0, "Ambient fixed cost should be 2.0"

    def test_parse_cost_structure_backward_compatibility(self, tmp_path):
        """
        Test backward compatibility when only legacy field is present.

        When only storage_cost_fixed_per_pallet is present (legacy format),
        it should be applied to both frozen and ambient states via
        get_fixed_pallet_costs().
        """
        test_file = tmp_path / "test_costs.xlsx"

        # Legacy format: only storage_cost_fixed_per_pallet (no state-specific)
        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            {'cost_type': 'storage_cost_fixed_per_pallet', 'value': 3.0},
            {'cost_type': 'shortage_penalty_per_unit', 'value': 10.0},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify legacy field is parsed
        assert cost_structure.storage_cost_fixed_per_pallet == 3.0

        # Verify state-specific fields are None
        assert cost_structure.storage_cost_fixed_per_pallet_frozen is None
        assert cost_structure.storage_cost_fixed_per_pallet_ambient is None

        # Verify get_fixed_pallet_costs() falls back to legacy value
        frozen_fixed, ambient_fixed = cost_structure.get_fixed_pallet_costs()
        assert frozen_fixed == 3.0, "Frozen should use legacy value"
        assert ambient_fixed == 3.0, "Ambient should use legacy value"

    def test_parse_cost_structure_mixed_state_specific_and_legacy(self, tmp_path):
        """
        Test parsing when both state-specific and legacy fields are present.

        When both formats are present, state-specific fields should be stored
        correctly and take precedence via get_fixed_pallet_costs().
        """
        test_file = tmp_path / "test_costs.xlsx"

        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            # State-specific (should take precedence)
            {'cost_type': 'storage_cost_fixed_per_pallet_frozen', 'value': 5.0},
            {'cost_type': 'storage_cost_fixed_per_pallet_ambient', 'value': 2.0},
            # Legacy (should be ignored when state-specific present)
            {'cost_type': 'storage_cost_fixed_per_pallet', 'value': 3.0},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify all fields are parsed
        assert cost_structure.storage_cost_fixed_per_pallet_frozen == 5.0
        assert cost_structure.storage_cost_fixed_per_pallet_ambient == 2.0
        assert cost_structure.storage_cost_fixed_per_pallet == 3.0

        # Verify get_fixed_pallet_costs() uses state-specific values
        frozen_fixed, ambient_fixed = cost_structure.get_fixed_pallet_costs()
        assert frozen_fixed == 5.0, "State-specific frozen should take precedence"
        assert ambient_fixed == 2.0, "State-specific ambient should take precedence"

    def test_parse_cost_structure_partial_state_specific(self, tmp_path):
        """
        Test parsing when only one state-specific field is present.

        When only frozen OR ambient state-specific field is present,
        the other should fall back to legacy value.
        """
        test_file = tmp_path / "test_costs.xlsx"

        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            {'cost_type': 'storage_cost_fixed_per_pallet_frozen', 'value': 5.0},
            # No ambient state-specific
            {'cost_type': 'storage_cost_fixed_per_pallet', 'value': 3.0},  # Legacy fallback
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify parsed values
        assert cost_structure.storage_cost_fixed_per_pallet_frozen == 5.0
        assert cost_structure.storage_cost_fixed_per_pallet_ambient is None
        assert cost_structure.storage_cost_fixed_per_pallet == 3.0

        # Verify get_fixed_pallet_costs() uses state-specific for frozen, legacy for ambient
        frozen_fixed, ambient_fixed = cost_structure.get_fixed_pallet_costs()
        assert frozen_fixed == 5.0, "Frozen should use state-specific value"
        assert ambient_fixed == 3.0, "Ambient should fall back to legacy value"

    def test_parse_cost_structure_zero_state_specific_values(self, tmp_path):
        """
        Test parsing with explicit zero values for state-specific costs.

        Explicit zero values should be treated as valid (not None),
        indicating intentional disabling of fixed pallet costs.
        """
        test_file = tmp_path / "test_costs.xlsx"

        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            {'cost_type': 'storage_cost_fixed_per_pallet_frozen', 'value': 0.0},  # Explicit zero
            {'cost_type': 'storage_cost_fixed_per_pallet_ambient', 'value': 0.0},  # Explicit zero
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify zeros are stored (not None)
        assert cost_structure.storage_cost_fixed_per_pallet_frozen == 0.0
        assert cost_structure.storage_cost_fixed_per_pallet_ambient == 0.0

        # Verify get_fixed_pallet_costs() returns zeros
        frozen_fixed, ambient_fixed = cost_structure.get_fixed_pallet_costs()
        assert frozen_fixed == 0.0, "Explicit zero should be preserved"
        assert ambient_fixed == 0.0, "Explicit zero should be preserved"

    def test_parse_cost_structure_missing_all_fixed_pallet_costs(self, tmp_path):
        """
        Test parsing when no fixed pallet cost fields are present.

        When no pallet cost fields are present, all should be None,
        and get_fixed_pallet_costs() should return (0.0, 0.0).
        """
        test_file = tmp_path / "test_costs.xlsx"

        # No pallet-related costs at all
        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            {'cost_type': 'shortage_penalty_per_unit', 'value': 10.0},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify all fixed pallet costs are None
        assert cost_structure.storage_cost_fixed_per_pallet is None
        assert cost_structure.storage_cost_fixed_per_pallet_frozen is None
        assert cost_structure.storage_cost_fixed_per_pallet_ambient is None

        # Verify get_fixed_pallet_costs() returns defaults
        frozen_fixed, ambient_fixed = cost_structure.get_fixed_pallet_costs()
        assert frozen_fixed == 0.0, "Should default to 0.0 when no costs set"
        assert ambient_fixed == 0.0, "Should default to 0.0 when no costs set"

    def test_parse_cost_structure_all_pallet_costs_together(self, tmp_path):
        """
        Test parsing when all pallet-related costs are present together.

        Verifies that parser correctly handles:
        - State-specific fixed costs (frozen/ambient)
        - Legacy fixed cost
        - Daily holding costs (frozen/ambient)
        All coexisting in the same file.
        """
        test_file = tmp_path / "test_costs.xlsx"

        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            # Fixed pallet costs (state-specific)
            {'cost_type': 'storage_cost_fixed_per_pallet_frozen', 'value': 5.0},
            {'cost_type': 'storage_cost_fixed_per_pallet_ambient', 'value': 2.0},
            # Fixed pallet cost (legacy)
            {'cost_type': 'storage_cost_fixed_per_pallet', 'value': 3.0},
            # Daily holding costs
            {'cost_type': 'storage_cost_per_pallet_day_frozen', 'value': 0.5},
            {'cost_type': 'storage_cost_per_pallet_day_ambient', 'value': 0.2},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify all fields are parsed
        assert cost_structure.storage_cost_fixed_per_pallet_frozen == 5.0
        assert cost_structure.storage_cost_fixed_per_pallet_ambient == 2.0
        assert cost_structure.storage_cost_fixed_per_pallet == 3.0
        assert cost_structure.storage_cost_per_pallet_day_frozen == 0.5
        assert cost_structure.storage_cost_per_pallet_day_ambient == 0.2

        # Verify get_fixed_pallet_costs() returns state-specific values
        frozen_fixed, ambient_fixed = cost_structure.get_fixed_pallet_costs()
        assert frozen_fixed == 5.0
        assert ambient_fixed == 2.0


class TestExcelParserRealFiles:
    """Tests using actual data files to verify state-specific parsing."""

    def test_parse_real_network_config_state_specific_costs(self):
        """
        Test parsing state-specific fixed pallet costs from actual Network_Config.xlsx.

        This integration test verifies that the real data file can be parsed
        and state-specific costs are accessible if present.
        """
        config_file = Path("/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx")

        if not config_file.exists():
            pytest.skip(f"Network_Config.xlsx not found at {config_file}")

        from src.parsers.unified_model_parser import UnifiedModelParser

        try:
            # Parse using UnifiedModelParser (which internally uses ExcelParser)
            parser = UnifiedModelParser(str(config_file))
            costs = parser._parse_cost_parameters()

            # Test that get_fixed_pallet_costs() works
            frozen_fixed, ambient_fixed = costs.get_fixed_pallet_costs()

            # Print actual values for debugging
            print(f"\nState-specific fixed pallet costs from Network_Config.xlsx:")
            print(f"  Frozen fixed cost: ${frozen_fixed}/pallet")
            print(f"  Ambient fixed cost: ${ambient_fixed}/pallet")
            print(f"\nField values:")
            print(f"  storage_cost_fixed_per_pallet_frozen: {costs.storage_cost_fixed_per_pallet_frozen}")
            print(f"  storage_cost_fixed_per_pallet_ambient: {costs.storage_cost_fixed_per_pallet_ambient}")
            print(f"  storage_cost_fixed_per_pallet (legacy): {costs.storage_cost_fixed_per_pallet}")

            # Verify that method returns valid numbers (not None)
            assert isinstance(frozen_fixed, (int, float)), "Frozen fixed cost should be numeric"
            assert isinstance(ambient_fixed, (int, float)), "Ambient fixed cost should be numeric"
            assert frozen_fixed >= 0.0, "Frozen fixed cost should be non-negative"
            assert ambient_fixed >= 0.0, "Ambient fixed cost should be non-negative"

        except Exception as e:
            pytest.fail(f"Failed to parse state-specific costs from Network_Config.xlsx: {e}")


class TestExcelParserProducts:
    """Tests for parsing Products sheet with units_per_mix."""

    def test_parse_products_with_all_columns(self, tmp_path):
        """Test parsing products with all columns including units_per_mix."""
        test_file = tmp_path / "test_products.xlsx"

        products_df = pd.DataFrame([
            {
                'product_id': 'G144',
                'name': 'Product A',
                'sku': 'G144',
                'shelf_life_ambient_days': 17,
                'shelf_life_frozen_days': 120,
                'shelf_life_after_thaw_days': 14,
                'min_acceptable_shelf_life_days': 7,
                'units_per_mix': 415
            },
            {
                'product_id': 'G145',
                'name': 'Product B',
                'sku': 'G145',
                'shelf_life_ambient_days': 17,
                'shelf_life_frozen_days': 120,
                'shelf_life_after_thaw_days': 14,
                'min_acceptable_shelf_life_days': 7,
                'units_per_mix': 387
            },
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            products_df.to_excel(writer, sheet_name='Products', index=False)

        parser = ExcelParser(test_file)
        products = parser.parse_products()

        # Verify parsing
        assert len(products) == 2
        assert 'G144' in products
        assert 'G145' in products

        # Verify Product A
        prod_a = products['G144']
        assert prod_a.id == 'G144'
        assert prod_a.name == 'Product A'
        assert prod_a.sku == 'G144'
        assert prod_a.ambient_shelf_life_days == 17
        assert prod_a.frozen_shelf_life_days == 120
        assert prod_a.thawed_shelf_life_days == 14
        assert prod_a.min_acceptable_shelf_life_days == 7
        assert prod_a.units_per_mix == 415

        # Verify Product B
        prod_b = products['G145']
        assert prod_b.units_per_mix == 387

    def test_parse_products_with_minimal_columns(self, tmp_path):
        """Test parsing products with only required columns and defaults for optional."""
        test_file = tmp_path / "test_products.xlsx"

        products_df = pd.DataFrame([
            {
                'product_id': 'P1',
                'name': 'Minimal Product',
                'sku': 'P001',
                'units_per_mix': 500
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            products_df.to_excel(writer, sheet_name='Products', index=False)

        parser = ExcelParser(test_file)
        products = parser.parse_products()

        # Verify parsing with defaults
        assert len(products) == 1
        prod = products['P1']
        assert prod.id == 'P1'
        assert prod.name == 'Minimal Product'
        assert prod.sku == 'P001'
        assert prod.units_per_mix == 500
        # Check defaults
        assert prod.ambient_shelf_life_days == 17.0
        assert prod.frozen_shelf_life_days == 120.0
        assert prod.thawed_shelf_life_days == 14.0
        assert prod.min_acceptable_shelf_life_days == 7.0

    def test_parse_products_missing_units_per_mix_column(self, tmp_path):
        """Test that parser raises clear error when units_per_mix column is missing."""
        test_file = tmp_path / "test_products.xlsx"

        # Create Products sheet WITHOUT units_per_mix
        products_df = pd.DataFrame([
            {
                'product_id': 'G144',
                'name': 'Product A',
                'sku': 'G144',
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            products_df.to_excel(writer, sheet_name='Products', index=False)

        parser = ExcelParser(test_file)

        # Should raise ValueError with helpful message
        with pytest.raises(ValueError) as exc_info:
            parser.parse_products()

        error_msg = str(exc_info.value)
        assert "units_per_mix" in error_msg.lower()
        assert "required" in error_msg.lower()
        assert "2025-10-23" in error_msg  # Date when requirement added

    def test_parse_products_missing_products_sheet(self, tmp_path):
        """Test that parser raises clear error when Products sheet doesn't exist."""
        test_file = tmp_path / "test_no_products.xlsx"

        # Create file with different sheet
        dummy_df = pd.DataFrame([{'col1': 'value1'}])
        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            dummy_df.to_excel(writer, sheet_name='OtherSheet', index=False)

        parser = ExcelParser(test_file)

        # Should raise ValueError with helpful message
        with pytest.raises(ValueError) as exc_info:
            parser.parse_products()

        error_msg = str(exc_info.value)
        assert "MISSING PRODUCTS SHEET" in error_msg
        assert "REQUIRED ACTION" in error_msg

    def test_parse_products_missing_required_column(self, tmp_path):
        """Test that parser raises error when other required columns are missing."""
        test_file = tmp_path / "test_products.xlsx"

        # Missing 'name' column
        products_df = pd.DataFrame([
            {
                'product_id': 'G144',
                'sku': 'G144',
                'units_per_mix': 415
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            products_df.to_excel(writer, sheet_name='Products', index=False)

        parser = ExcelParser(test_file)

        with pytest.raises(ValueError) as exc_info:
            parser.parse_products()

        error_msg = str(exc_info.value)
        assert "name" in error_msg.lower()

    def test_parse_products_empty_units_per_mix(self, tmp_path):
        """Test that parser raises error when units_per_mix is empty/NaN."""
        test_file = tmp_path / "test_products.xlsx"

        # Product with empty units_per_mix
        products_df = pd.DataFrame([
            {
                'product_id': 'G144',
                'name': 'Gluten Free White',
                'sku': 'G144',
                'units_per_mix': None  # Empty/NaN value
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            products_df.to_excel(writer, sheet_name='Products', index=False)

        parser = ExcelParser(test_file)

        with pytest.raises(ValueError) as exc_info:
            parser.parse_products()

        error_msg = str(exc_info.value)
        assert "EMPTY units_per_mix VALUE" in error_msg
        assert "REQUIRED ACTION" in error_msg
        assert "G144" in error_msg  # Should mention the product ID

    def test_parse_products_from_real_network_config(self):
        """Test parsing products from actual Network_Config.xlsx file."""
        config_file = Path("/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx")

        if not config_file.exists():
            pytest.skip(f"Network_Config.xlsx not found at {config_file}")

        parser = ExcelParser(config_file)
        products = parser.parse_products()

        # Verify we got products
        assert len(products) > 0, "Should have at least one product"

        # Verify all products have units_per_mix > 0
        for product_id, product in products.items():
            assert product.units_per_mix > 0, f"Product {product_id} should have units_per_mix > 0"
            assert isinstance(product.units_per_mix, int), f"Product {product_id} units_per_mix should be integer"
            # Verify all required fields present
            assert product.id
            assert product.name
            assert product.sku
            assert product.ambient_shelf_life_days >= 0
            assert product.frozen_shelf_life_days >= 0
            assert product.thawed_shelf_life_days >= 0
            assert product.min_acceptable_shelf_life_days >= 0
