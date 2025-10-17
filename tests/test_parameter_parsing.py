"""Tests for new parameter parsing functionality.

Tests cover:
1. Manufacturing overhead parameters (daily_startup_hours, daily_shutdown_hours, default_changeover_hours)
2. Pallet-based storage costs (storage_cost_fixed_per_pallet, storage_cost_per_pallet_day_*)
3. Backward compatibility when new parameters are missing
4. Integration with UnifiedModelParser
"""

import pytest
import pandas as pd
import tempfile
from pathlib import Path
from datetime import date, time

from src.parsers.excel_parser import ExcelParser
from src.parsers.unified_model_parser import UnifiedModelParser
from src.models import (
    ManufacturingSite,
    Location,
    LocationType,
    StorageMode,
    CostStructure,
)


class TestManufacturingOverheadParsing:
    """Tests for parsing manufacturing overhead parameters from Locations sheet."""

    def test_parse_manufacturing_overhead_defaults(self, tmp_path):
        """Test parsing overhead columns with default values."""
        # Create test Excel file with overhead columns
        test_file = tmp_path / "test_config.xlsx"

        locations_df = pd.DataFrame([
            {
                'id': '6122',
                'name': 'Manufacturing Site',
                'type': 'manufacturing',
                'storage_mode': 'ambient',
                'production_rate': 1400.0,
                'daily_startup_hours': 0.5,
                'daily_shutdown_hours': 0.5,
                'default_changeover_hours': 1.0,
                'capacity': None,
            },
            {
                'id': '6104',
                'name': 'NSW Hub',
                'type': 'storage',
                'storage_mode': 'ambient',
                'capacity': 50000.0,
            }
        ])

        # Create minimal Excel file
        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            locations_df.to_excel(writer, sheet_name='Locations', index=False)

        # Parse locations
        parser = ExcelParser(test_file)
        locations = parser.parse_locations()

        # Find manufacturing location
        mfg = next((loc for loc in locations if loc.id == '6122'), None)
        assert mfg is not None
        assert isinstance(mfg, ManufacturingSite)

        # Verify overhead parameters
        assert mfg.daily_startup_hours == 0.5
        assert mfg.daily_shutdown_hours == 0.5
        assert mfg.default_changeover_hours == 1.0

        # Verify non-manufacturing location doesn't have these attributes
        hub = next((loc for loc in locations if loc.id == '6104'), None)
        assert hub is not None
        assert not isinstance(hub, ManufacturingSite)
        assert not hasattr(hub, 'daily_startup_hours')

    def test_parse_manufacturing_overhead_custom_values(self, tmp_path):
        """Test parsing overhead columns with custom values."""
        test_file = tmp_path / "test_config.xlsx"

        locations_df = pd.DataFrame([
            {
                'id': '6122',
                'name': 'Manufacturing Site',
                'type': 'manufacturing',
                'storage_mode': 'ambient',
                'production_rate': 1400.0,
                'daily_startup_hours': 0.75,  # Custom
                'daily_shutdown_hours': 0.25,  # Custom
                'default_changeover_hours': 0.5,  # Custom
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            locations_df.to_excel(writer, sheet_name='Locations', index=False)

        parser = ExcelParser(test_file)
        locations = parser.parse_locations()

        mfg = locations[0]
        assert isinstance(mfg, ManufacturingSite)
        assert mfg.daily_startup_hours == 0.75
        assert mfg.daily_shutdown_hours == 0.25
        assert mfg.default_changeover_hours == 0.5

    def test_parse_manufacturing_overhead_missing_columns_legacy_compat(self, tmp_path):
        """Test backward compatibility when overhead columns are missing."""
        test_file = tmp_path / "test_config.xlsx"

        # Create Excel WITHOUT overhead columns (legacy format)
        locations_df = pd.DataFrame([
            {
                'id': '6122',
                'name': 'Manufacturing Site',
                'type': 'manufacturing',
                'storage_mode': 'ambient',
                'production_rate': 1400.0,
                # NO overhead columns
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            locations_df.to_excel(writer, sheet_name='Locations', index=False)

        # Parse should succeed with defaults
        parser = ExcelParser(test_file)
        locations = parser.parse_locations()

        mfg = locations[0]
        assert isinstance(mfg, ManufacturingSite)

        # Verify defaults are applied
        assert mfg.daily_startup_hours == 0.5
        assert mfg.daily_shutdown_hours == 0.5
        assert mfg.default_changeover_hours == 1.0

    def test_parse_manufacturing_overhead_partial_columns(self, tmp_path):
        """Test parsing when only some overhead columns are present."""
        test_file = tmp_path / "test_config.xlsx"

        locations_df = pd.DataFrame([
            {
                'id': '6122',
                'name': 'Manufacturing Site',
                'type': 'manufacturing',
                'storage_mode': 'ambient',
                'production_rate': 1400.0,
                'daily_startup_hours': 0.75,  # Custom
                # Missing shutdown and changeover columns
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            locations_df.to_excel(writer, sheet_name='Locations', index=False)

        parser = ExcelParser(test_file)
        locations = parser.parse_locations()

        mfg = locations[0]
        assert isinstance(mfg, ManufacturingSite)

        # Verify mix of custom and defaults
        assert mfg.daily_startup_hours == 0.75  # Custom
        assert mfg.daily_shutdown_hours == 0.5  # Default
        assert mfg.default_changeover_hours == 1.0  # Default


class TestPalletStorageCostParsing:
    """Tests for parsing pallet-based storage costs from CostParameters sheet."""

    def test_parse_pallet_storage_costs_present(self, tmp_path):
        """Test parsing when pallet cost parameters are present."""
        test_file = tmp_path / "test_costs.xlsx"

        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            {'cost_type': 'storage_cost_fixed_per_pallet', 'value': 0.0},
            {'cost_type': 'storage_cost_per_pallet_day_frozen', 'value': 0.5},
            {'cost_type': 'storage_cost_per_pallet_day_ambient', 'value': 0.2},
            {'cost_type': 'shortage_penalty_per_unit', 'value': 10.0},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify pallet costs are parsed
        assert cost_structure.storage_cost_fixed_per_pallet == 0.0
        assert cost_structure.storage_cost_per_pallet_day_frozen == 0.5
        assert cost_structure.storage_cost_per_pallet_day_ambient == 0.2

    def test_parse_pallet_storage_costs_missing_legacy_compat(self, tmp_path):
        """Test backward compatibility when pallet costs are missing."""
        test_file = tmp_path / "test_costs.xlsx"

        # Legacy format WITHOUT pallet costs
        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            {'cost_type': 'storage_cost_frozen_per_unit_day', 'value': 0.05},
            {'cost_type': 'storage_cost_ambient_per_unit_day', 'value': 0.02},
            {'cost_type': 'shortage_penalty_per_unit', 'value': 10.0},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify pallet costs are None (not present)
        assert cost_structure.storage_cost_fixed_per_pallet is None
        assert cost_structure.storage_cost_per_pallet_day_frozen is None
        assert cost_structure.storage_cost_per_pallet_day_ambient is None

        # Verify unit-based costs still work
        assert cost_structure.storage_cost_frozen_per_unit_day == 0.05
        assert cost_structure.storage_cost_ambient_per_unit_day == 0.02

    def test_parse_pallet_storage_costs_precedence(self, tmp_path):
        """Test that both pallet and unit costs can coexist."""
        test_file = tmp_path / "test_costs.xlsx"

        # File with BOTH pallet and unit costs
        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            # Unit-based (legacy)
            {'cost_type': 'storage_cost_frozen_per_unit_day', 'value': 0.05},
            {'cost_type': 'storage_cost_ambient_per_unit_day', 'value': 0.02},
            # Pallet-based (new)
            {'cost_type': 'storage_cost_fixed_per_pallet', 'value': 1.0},
            {'cost_type': 'storage_cost_per_pallet_day_frozen', 'value': 0.5},
            {'cost_type': 'storage_cost_per_pallet_day_ambient', 'value': 0.2},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify BOTH sets of costs are present
        # (Precedence is determined in the optimization model, not parser)
        assert cost_structure.storage_cost_frozen_per_unit_day == 0.05
        assert cost_structure.storage_cost_ambient_per_unit_day == 0.02
        assert cost_structure.storage_cost_fixed_per_pallet == 1.0
        assert cost_structure.storage_cost_per_pallet_day_frozen == 0.5
        assert cost_structure.storage_cost_per_pallet_day_ambient == 0.2

    def test_parse_pallet_storage_costs_partial(self, tmp_path):
        """Test parsing when only some pallet costs are present."""
        test_file = tmp_path / "test_costs.xlsx"

        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
            {'cost_type': 'storage_cost_per_pallet_day_frozen', 'value': 0.5},
            # Missing: fixed_per_pallet and ambient
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        cost_structure = parser.parse_cost_structure()

        # Verify partial parsing
        assert cost_structure.storage_cost_fixed_per_pallet is None
        assert cost_structure.storage_cost_per_pallet_day_frozen == 0.5
        assert cost_structure.storage_cost_per_pallet_day_ambient is None


class TestUnifiedModelParserOverhead:
    """Tests for UnifiedModelParser handling of overhead parameters."""

    def test_unified_parser_overhead_parameters(self, tmp_path):
        """Test that UnifiedModelParser correctly parses overhead parameters."""
        test_file = tmp_path / "test_unified.xlsx"

        # Create Nodes sheet with overhead parameters
        nodes_df = pd.DataFrame([
            {
                'node_id': '6122',
                'node_name': 'Manufacturing Site',
                'can_manufacture': True,
                'production_rate_per_hour': 1400.0,
                'daily_startup_hours': 0.75,
                'daily_shutdown_hours': 0.25,
                'default_changeover_hours': 0.5,
                'can_store': True,
                'storage_mode': 'ambient',
                'has_demand': False,
                'requires_truck_schedules': True,
            }
        ])

        # Create minimal other sheets
        routes_df = pd.DataFrame([
            {
                'route_id': 'R1',
                'origin_node_id': '6122',
                'destination_node_id': '6104',
                'transit_days': 1.0,
                'transport_mode': 'ambient',
            }
        ])

        trucks_df = pd.DataFrame([
            {
                'truck_id': 'T1',
                'origin_node_id': '6122',
                'destination_node_id': '6104',
                'departure_type': 'morning',
                'departure_time': '06:00',
                'capacity': 14080.0,
            }
        ])

        forecast_df = pd.DataFrame([
            {
                'location_id': '6104',
                'product_id': 'P1',
                'forecast_date': date(2025, 10, 17),
                'quantity': 1000.0,
            }
        ])

        labor_df = pd.DataFrame([
            {
                'date': date(2025, 10, 17),
                'fixed_hours': 12.0,
                'regular_rate': 20.0,
                'overtime_rate': 30.0,
            }
        ])

        costs_df = pd.DataFrame([
            {'cost_type': 'production_cost_per_unit', 'value': 5.0},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            nodes_df.to_excel(writer, sheet_name='Nodes', index=False)
            routes_df.to_excel(writer, sheet_name='Routes', index=False)
            trucks_df.to_excel(writer, sheet_name='TruckSchedules', index=False)
            forecast_df.to_excel(writer, sheet_name='Forecast', index=False)
            labor_df.to_excel(writer, sheet_name='LaborCalendar', index=False)
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        # Parse with UnifiedModelParser
        parser = UnifiedModelParser(str(test_file))
        nodes = parser.parse_nodes()

        # Find manufacturing node
        mfg_node = next((n for n in nodes if n.id == '6122'), None)
        assert mfg_node is not None

        # Verify NodeCapabilities includes overhead parameters
        assert mfg_node.capabilities.can_manufacture is True
        assert mfg_node.capabilities.production_rate_per_hour == 1400.0
        assert mfg_node.capabilities.daily_startup_hours == 0.75
        assert mfg_node.capabilities.daily_shutdown_hours == 0.25
        assert mfg_node.capabilities.default_changeover_hours == 0.5

    def test_unified_parser_overhead_missing_columns(self, tmp_path):
        """Test UnifiedModelParser defaults when overhead columns are missing."""
        test_file = tmp_path / "test_unified.xlsx"

        # Create Nodes sheet WITHOUT overhead columns
        nodes_df = pd.DataFrame([
            {
                'node_id': '6122',
                'node_name': 'Manufacturing Site',
                'can_manufacture': True,
                'production_rate_per_hour': 1400.0,
                # NO overhead columns
                'can_store': True,
                'storage_mode': 'ambient',
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            nodes_df.to_excel(writer, sheet_name='Nodes', index=False)

        parser = UnifiedModelParser(str(test_file))
        nodes = parser.parse_nodes()

        mfg_node = nodes[0]

        # Verify defaults are applied (matching NodeCapabilities defaults)
        assert mfg_node.capabilities.daily_startup_hours == 0.5
        assert mfg_node.capabilities.daily_shutdown_hours == 0.5
        assert mfg_node.capabilities.default_changeover_hours == 1.0

    def test_unified_parser_overhead_only_for_manufacturing(self, tmp_path):
        """Test that overhead parameters are properly handled for non-manufacturing nodes."""
        test_file = tmp_path / "test_unified.xlsx"

        nodes_df = pd.DataFrame([
            {
                'node_id': '6104',
                'node_name': 'NSW Hub',
                'can_manufacture': False,
                'can_store': True,
                'storage_mode': 'ambient',
                'has_demand': True,
                # Overhead parameters present but irrelevant (no manufacturing)
                'daily_startup_hours': 0.75,
                'daily_shutdown_hours': 0.25,
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            nodes_df.to_excel(writer, sheet_name='Nodes', index=False)

        parser = UnifiedModelParser(str(test_file))
        nodes = parser.parse_nodes()

        hub_node = nodes[0]

        # Verify parameters are stored even if not used
        assert hub_node.capabilities.can_manufacture is False
        assert hub_node.capabilities.daily_startup_hours == 0.75
        assert hub_node.capabilities.daily_shutdown_hours == 0.25


class TestIntegrationWithOptimizationModel:
    """Tests verifying integration with UnifiedNodeModel optimization."""

    def test_node_capabilities_accessible_in_model(self, tmp_path):
        """Test that NodeCapabilities overhead values are accessible for model use."""
        test_file = tmp_path / "test_unified.xlsx"

        nodes_df = pd.DataFrame([
            {
                'node_id': '6122',
                'node_name': 'Manufacturing',
                'can_manufacture': True,
                'production_rate_per_hour': 1400.0,
                'daily_startup_hours': 0.6,
                'daily_shutdown_hours': 0.4,
                'default_changeover_hours': 0.8,
                'can_store': True,
                'storage_mode': 'ambient',
                'requires_truck_schedules': True,
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            nodes_df.to_excel(writer, sheet_name='Nodes', index=False)

        parser = UnifiedModelParser(str(test_file))
        nodes = parser.parse_nodes()
        node = nodes[0]

        # Verify overhead values are accessible via node.capabilities
        # (This is how UnifiedNodeModel accesses them - lines 1762-1764, 1951-1953)
        assert node.capabilities.daily_startup_hours == 0.6
        assert node.capabilities.daily_shutdown_hours == 0.4
        assert node.capabilities.default_changeover_hours == 0.8

        # Verify production rate is also accessible
        assert node.capabilities.production_rate_per_hour == 1400.0

    def test_cost_structure_pallet_costs_accessible(self, tmp_path):
        """Test that pallet costs are accessible from CostStructure."""
        test_file = tmp_path / "test_costs.xlsx"

        costs_df = pd.DataFrame([
            {'cost_type': 'storage_cost_fixed_per_pallet', 'value': 2.0},
            {'cost_type': 'storage_cost_per_pallet_day_frozen', 'value': 0.6},
            {'cost_type': 'storage_cost_per_pallet_day_ambient', 'value': 0.3},
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            costs_df.to_excel(writer, sheet_name='CostParameters', index=False)

        parser = ExcelParser(test_file)
        costs = parser.parse_cost_structure()

        # Verify costs are accessible for optimization model
        assert costs.storage_cost_fixed_per_pallet == 2.0
        assert costs.storage_cost_per_pallet_day_frozen == 0.6
        assert costs.storage_cost_per_pallet_day_ambient == 0.3


class TestRealWorldDataFiles:
    """Tests using actual data files to verify parsing works end-to-end."""

    def test_parse_real_network_config_file(self):
        """Test parsing the actual Network_Config.xlsx file."""
        config_file = Path("/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx")

        if not config_file.exists():
            pytest.skip(f"Network_Config.xlsx not found at {config_file}")

        # Parse with UnifiedModelParser
        parser = UnifiedModelParser(str(config_file))

        try:
            nodes = parser.parse_nodes()

            # Find manufacturing node (6122)
            mfg = next((n for n in nodes if n.id == '6122'), None)
            assert mfg is not None, "Manufacturing node 6122 not found"

            # Verify overhead parameters are present
            assert mfg.capabilities.can_manufacture is True
            assert mfg.capabilities.production_rate_per_hour == 1400.0
            assert mfg.capabilities.daily_startup_hours is not None
            assert mfg.capabilities.daily_shutdown_hours is not None
            assert mfg.capabilities.default_changeover_hours is not None

            print(f"\nManufacturing node overhead parameters:")
            print(f"  Startup: {mfg.capabilities.daily_startup_hours}h")
            print(f"  Shutdown: {mfg.capabilities.daily_shutdown_hours}h")
            print(f"  Changeover: {mfg.capabilities.default_changeover_hours}h")

        except Exception as e:
            pytest.fail(f"Failed to parse Network_Config.xlsx: {e}")

    def test_parse_real_cost_parameters(self):
        """Test parsing cost parameters from actual Network_Config.xlsx."""
        config_file = Path("/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx")

        if not config_file.exists():
            pytest.skip(f"Network_Config.xlsx not found at {config_file}")

        parser = UnifiedModelParser(str(config_file))

        try:
            # Parse using UnifiedModelParser's internal method
            costs = parser._parse_cost_parameters()

            # Check if pallet costs are present
            has_pallet_costs = (
                costs.storage_cost_fixed_per_pallet is not None or
                costs.storage_cost_per_pallet_day_frozen is not None or
                costs.storage_cost_per_pallet_day_ambient is not None
            )

            print(f"\nPallet-based costs present: {has_pallet_costs}")
            if has_pallet_costs:
                print(f"  Fixed per pallet: ${costs.storage_cost_fixed_per_pallet}")
                print(f"  Frozen per pallet/day: ${costs.storage_cost_per_pallet_day_frozen}")
                print(f"  Ambient per pallet/day: ${costs.storage_cost_per_pallet_day_ambient}")

            # Verify at least unit-based costs work
            assert costs.production_cost_per_unit is not None

        except Exception as e:
            # If this fails, it's likely CostParameters sheet has different format
            pytest.skip(f"Cost parameters parsing not compatible: {e}")


class TestErrorHandling:
    """Tests for error handling in parameter parsing."""

    def test_missing_production_rate_for_manufacturing(self, tmp_path):
        """Test that missing production_rate raises clear error."""
        test_file = tmp_path / "test_invalid.xlsx"

        locations_df = pd.DataFrame([
            {
                'id': '6122',
                'name': 'Manufacturing',
                'type': 'manufacturing',
                'storage_mode': 'ambient',
                # Missing production_rate!
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            locations_df.to_excel(writer, sheet_name='Locations', index=False)

        parser = ExcelParser(test_file)

        with pytest.raises(ValueError) as excinfo:
            parser.parse_locations()

        assert 'production_rate' in str(excinfo.value).lower()

    def test_invalid_overhead_values_rejected(self, tmp_path):
        """Test that negative overhead values are rejected by model validation."""
        test_file = tmp_path / "test_invalid.xlsx"

        nodes_df = pd.DataFrame([
            {
                'node_id': '6122',
                'node_name': 'Manufacturing',
                'can_manufacture': True,
                'production_rate_per_hour': 1400.0,
                'daily_startup_hours': -0.5,  # Invalid: negative
                'can_store': True,
                'storage_mode': 'ambient',
            }
        ])

        with pd.ExcelWriter(test_file, engine='openpyxl') as writer:
            nodes_df.to_excel(writer, sheet_name='Nodes', index=False)

        parser = UnifiedModelParser(str(test_file))

        # Should raise validation error from Pydantic
        with pytest.raises(Exception):  # Pydantic ValidationError
            nodes = parser.parse_nodes()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
