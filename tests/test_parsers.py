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
