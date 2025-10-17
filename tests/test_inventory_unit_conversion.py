"""Comprehensive tests for inventory parser unit conversion functionality.

This test suite validates:
1. Unit conversion (EA, CAS, unknown types)
2. Case-insensitive unit handling
3. Storage Location 5000 filtering
4. Negative quantity handling
5. Zero quantity skipping
6. Aggregation by material+plant+storage location
7. Missing columns validation
8. Product alias resolution integration
9. to_optimization_dict() output
10. Warning message emission
"""

import pytest
import pandas as pd
import warnings
from datetime import date
from pathlib import Path
from io import BytesIO
from openpyxl import Workbook

from src.parsers.inventory_parser import InventoryParser
from src.parsers.product_alias_resolver import ProductAliasResolver
from src.models.inventory import InventorySnapshot, InventoryEntry


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_product_alias_resolver():
    """Create a mock product alias resolver with test mappings."""
    # Create a simple alias resolver with some test mappings
    class MockResolver:
        def __init__(self):
            self.mappings = {
                "999999": "176283",  # Alias maps to canonical product
                "888888": "168846",
            }

        def resolve_product_id(self, material: str) -> str:
            """Resolve product alias to canonical ID."""
            return self.mappings.get(material, material)

        def is_mapped(self, material: str) -> bool:
            """Check if material is in the mapping."""
            # Consider both keys and values as mapped
            return material in self.mappings or material in self.mappings.values()

    return MockResolver()


@pytest.fixture
def create_test_excel_file(tmp_path):
    """Factory fixture to create test Excel files with specified data."""
    def _create_file(data: list[dict], filename: str = "test_inventory.xlsx") -> Path:
        """Create an Excel file with the given data.

        Args:
            data: List of dictionaries representing rows
            filename: Name of the Excel file

        Returns:
            Path to the created file
        """
        df = pd.DataFrame(data)
        file_path = tmp_path / filename
        df.to_excel(file_path, index=False, engine="openpyxl")
        return file_path

    return _create_file


# ============================================================================
# Unit Conversion Tests
# ============================================================================

def test_ea_unit_conversion_1_to_1(create_test_excel_file):
    """Test that EA units use 1:1 conversion."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == 100.0  # 100 EA * 1 = 100 units


def test_cas_unit_conversion_10_to_1(create_test_excel_file):
    """Test that CAS units use 10:1 conversion (10 units per case)."""
    data = [
        {"Material": 176283, "Plant": 6122, "Storage Location": 4070,
         "Base Unit of Measure": "CAS", "Unrestricted": 32.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == 320.0  # 32 CAS * 10 = 320 units


@pytest.mark.parametrize("base_unit,expected_factor", [
    ("EA", 1.0),
    ("CAS", 10.0),
])
def test_unit_conversion_factors(create_test_excel_file, base_unit, expected_factor):
    """Test multiple unit types with parameterized conversion factors."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": base_unit, "Unrestricted": 50.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == 50.0 * expected_factor


@pytest.mark.parametrize("quantity_raw", [
    0.5,      # Fractional case
    1.0,      # Single case
    10.0,     # Multiple cases
    100.5,    # Large fractional quantity
    9999.99,  # Very large quantity
])
def test_cas_conversion_various_quantities(create_test_excel_file, quantity_raw):
    """Test CAS conversion with various quantity values."""
    data = [
        {"Material": 176283, "Plant": 6122, "Storage Location": 4070,
         "Base Unit of Measure": "CAS", "Unrestricted": quantity_raw},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == pytest.approx(quantity_raw * 10.0)


# ============================================================================
# Case-Insensitive Unit Handling
# ============================================================================

@pytest.mark.parametrize("unit_variant", [
    "ea", "EA", "Ea", "eA",  # EA variations
    "cas", "CAS", "Cas", "cAs", "cAS",  # CAS variations
])
def test_case_insensitive_unit_types(create_test_excel_file, unit_variant):
    """Test that unit types are handled case-insensitively."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": unit_variant, "Unrestricted": 10.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    # Determine expected quantity based on unit type
    unit_upper = unit_variant.upper()
    expected_factor = 10.0 if unit_upper == "CAS" else 1.0
    expected_qty = 10.0 * expected_factor

    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == pytest.approx(expected_qty)


# ============================================================================
# Unknown Unit Type Handling
# ============================================================================

@pytest.mark.parametrize("unknown_unit", [
    "PALLET", "BOX", "KG", "LBS", "DOZEN", "UNIT", "PKG"
])
def test_unknown_unit_types_default_to_1_to_1(create_test_excel_file, unknown_unit):
    """Test that unknown unit types default to 1:1 conversion with warning."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": unknown_unit, "Unrestricted": 50.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        snapshot = parser.parse()

        # Check that warning was issued
        assert len(w) == 1
        assert "unknown unit types" in str(w[0].message).lower()
        assert unknown_unit in str(w[0].message)

    # Verify 1:1 conversion was applied
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == 50.0


def test_multiple_unknown_units_single_warning(create_test_excel_file):
    """Test that multiple unknown unit types produce a single aggregated warning."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "BOX", "Unrestricted": 10.0},
        {"Material": 176283, "Plant": 6125, "Storage Location": 4000,
         "Base Unit of Measure": "PALLET", "Unrestricted": 5.0},
        {"Material": 168847, "Plant": 6104, "Storage Location": 4000,
         "Base Unit of Measure": "KG", "Unrestricted": 20.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        snapshot = parser.parse()

        # Should have exactly one warning about unknown units
        unknown_warnings = [warning for warning in w if "unknown unit types" in str(warning.message).lower()]
        assert len(unknown_warnings) == 1

        # All three unknown unit types should be mentioned
        warning_text = str(unknown_warnings[0].message)
        assert "BOX" in warning_text
        assert "PALLET" in warning_text
        assert "KG" in warning_text

    assert len(snapshot.entries) == 3


# ============================================================================
# Storage Location 5000 Filtering
# ============================================================================

def test_storage_location_5000_excluded(create_test_excel_file):
    """Test that Storage Location 5000 entries are excluded."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
        {"Material": 176283, "Plant": 6122, "Storage Location": 5000,
         "Base Unit of Measure": "CAS", "Unrestricted": 50.0},
        {"Material": 168847, "Plant": 6125, "Storage Location": 4070,
         "Base Unit of Measure": "EA", "Unrestricted": 75.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        snapshot = parser.parse()

        # Check warning about skipped entries
        skip_warnings = [warning for warning in w if "5000" in str(warning.message)]
        assert len(skip_warnings) == 1
        assert "Skipped 1 entries" in str(skip_warnings[0].message)

    # Should have 2 entries (5000 excluded)
    assert len(snapshot.entries) == 2

    # Verify no 5000 entries
    for entry in snapshot.entries:
        assert entry.storage_location != "5000"

    # Verify the correct entries were kept
    locations = {entry.storage_location for entry in snapshot.entries}
    assert locations == {"4000", "4070"}


def test_all_entries_storage_5000_result_empty(create_test_excel_file):
    """Test that file with only 5000 entries results in empty snapshot."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 5000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
        {"Material": 176283, "Plant": 6125, "Storage Location": 5000,
         "Base Unit of Measure": "CAS", "Unrestricted": 50.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        snapshot = parser.parse()

        # Check warning about skipped entries
        skip_warnings = [warning for warning in w if "5000" in str(warning.message)]
        assert len(skip_warnings) == 1
        assert "Skipped 2 entries" in str(skip_warnings[0].message)

    assert len(snapshot.entries) == 0


# ============================================================================
# Negative Quantity Handling
# ============================================================================

def test_negative_quantities_set_to_zero_with_warning(create_test_excel_file):
    """Test that negative quantities are set to 0 and warning is emitted."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": -50.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        snapshot = parser.parse()

        # Check warning about negative quantities
        neg_warnings = [warning for warning in w if "negative" in str(warning.message).lower()]
        assert len(neg_warnings) == 1
        assert "Found 1 negative quantity values" in str(neg_warnings[0].message)

    # Entry should be skipped (zero quantity entries are skipped)
    assert len(snapshot.entries) == 0


def test_multiple_negative_quantities_aggregated_warning(create_test_excel_file):
    """Test that multiple negative quantities produce single aggregated warning."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": -10.0},
        {"Material": 176283, "Plant": 6125, "Storage Location": 4070,
         "Base Unit of Measure": "CAS", "Unrestricted": -5.0},
        {"Material": 168847, "Plant": 6104, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},  # Positive
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        snapshot = parser.parse()

        # Check warning mentions 2 negative values
        neg_warnings = [warning for warning in w if "negative" in str(warning.message).lower()]
        assert len(neg_warnings) == 1
        assert "Found 2 negative quantity values" in str(neg_warnings[0].message)

    # Only the positive entry should remain
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].product_id == "168847"


# ============================================================================
# Zero Quantity Skipping
# ============================================================================

def test_zero_quantities_skipped(create_test_excel_file):
    """Test that zero quantity entries are skipped."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 0.0},
        {"Material": 176283, "Plant": 6125, "Storage Location": 4070,
         "Base Unit of Measure": "CAS", "Unrestricted": 10.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    # Only non-zero entry should be included
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].product_id == "176283"
    assert snapshot.entries[0].quantity == 100.0


def test_very_small_quantities_not_skipped(create_test_excel_file):
    """Test that very small (but non-zero) quantities are preserved."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 0.001},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == pytest.approx(0.001)


# ============================================================================
# Aggregation Tests
# ============================================================================

def test_aggregation_by_material_plant_storage(create_test_excel_file):
    """Test that quantities are aggregated by (material, plant, storage location)."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 30.0},
        {"Material": 168846, "Plant": 6122, "Storage Location": 4070,
         "Base Unit of Measure": "EA", "Unrestricted": 20.0},  # Different storage
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    # Should have 2 entries (storage 4000 aggregated, 4070 separate)
    assert len(snapshot.entries) == 2

    # Check aggregated 4000
    entry_4000 = [e for e in snapshot.entries if e.storage_location == "4000"][0]
    assert entry_4000.quantity == 80.0  # 50 + 30

    # Check separate 4070
    entry_4070 = [e for e in snapshot.entries if e.storage_location == "4070"][0]
    assert entry_4070.quantity == 20.0


def test_aggregation_different_plants_separate(create_test_excel_file):
    """Test that same material at different plants are kept separate."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},
        {"Material": 168846, "Plant": 6125, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 30.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    # Should have 2 separate entries
    assert len(snapshot.entries) == 2

    # Check both plants present
    plants = {e.location_id for e in snapshot.entries}
    assert plants == {"6122", "6125"}


def test_aggregation_different_materials_separate(create_test_excel_file):
    """Test that different materials at same plant are kept separate."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},
        {"Material": 176283, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "CAS", "Unrestricted": 10.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    # Should have 2 separate entries
    assert len(snapshot.entries) == 2

    # Check both products present
    products = {e.product_id for e in snapshot.entries}
    assert products == {"168846", "176283"}


def test_aggregation_mixed_units_converted_before_aggregation(create_test_excel_file):
    """Test that mixed units (EA and CAS) are converted before aggregation."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},  # 100 units
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "CAS", "Unrestricted": 10.0},  # 100 units (10*10)
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    # Should aggregate to single entry
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == 200.0  # 100 + 100


# ============================================================================
# Missing Column Validation
# ============================================================================

def test_missing_material_column_raises_error(create_test_excel_file):
    """Test that missing Material column raises ValueError."""
    data = [
        {"Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with pytest.raises(ValueError, match="Missing required columns.*Material"):
        parser.parse()


def test_missing_plant_column_raises_error(create_test_excel_file):
    """Test that missing Plant column raises ValueError."""
    data = [
        {"Material": 168846, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with pytest.raises(ValueError, match="Missing required columns.*Plant"):
        parser.parse()


def test_missing_unrestricted_column_raises_error(create_test_excel_file):
    """Test that missing Unrestricted column raises ValueError."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA"},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with pytest.raises(ValueError, match="Missing required columns.*Unrestricted"):
        parser.parse()


def test_missing_base_unit_column_raises_error(create_test_excel_file):
    """Test that missing Base Unit of Measure column raises ValueError."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Unrestricted": 100.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with pytest.raises(ValueError, match="Missing required columns.*Base Unit of Measure"):
        parser.parse()


def test_missing_storage_location_column_works(create_test_excel_file):
    """Test that missing Storage Location column is handled gracefully."""
    data = [
        {"Material": 168846, "Plant": 6122,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    # Should parse successfully with None storage location
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].storage_location is None


# ============================================================================
# Empty File Handling
# ============================================================================

def test_empty_file_returns_empty_snapshot(create_test_excel_file):
    """Test that empty file (with headers only) returns empty snapshot."""
    data = []  # No data rows
    file_path = create_test_excel_file(data)

    # Manually add headers since pandas won't create them with empty data
    df = pd.DataFrame(columns=["Material", "Plant", "Storage Location",
                                "Base Unit of Measure", "Unrestricted"])
    df.to_excel(file_path, index=False, engine="openpyxl")

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    assert len(snapshot.entries) == 0
    assert snapshot.get_total_quantity() == 0


# ============================================================================
# Product Alias Resolution Integration
# ============================================================================

def test_product_alias_resolution_applied(create_test_excel_file, mock_product_alias_resolver):
    """Test that product aliases are resolved to canonical IDs."""
    data = [
        {"Material": 999999, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},  # Alias for 176283
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(
        file_path=file_path,
        snapshot_date=date(2025, 1, 15),
        product_alias_resolver=mock_product_alias_resolver
    )
    snapshot = parser.parse()

    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].product_id == "176283"  # Resolved from 999999


def test_product_alias_aggregation(create_test_excel_file, mock_product_alias_resolver):
    """Test that aliases are aggregated with canonical product IDs."""
    data = [
        {"Material": 999999, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},  # Alias for 176283
        {"Material": 176283, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 30.0},  # Canonical ID
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(
        file_path=file_path,
        snapshot_date=date(2025, 1, 15),
        product_alias_resolver=mock_product_alias_resolver
    )
    snapshot = parser.parse()

    # Should aggregate to single entry under canonical ID
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].product_id == "176283"
    assert snapshot.entries[0].quantity == 80.0


def test_unmapped_product_warning(create_test_excel_file, mock_product_alias_resolver):
    """Test that unmapped products generate a warning."""
    data = [
        {"Material": 777777, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},  # Not in mapping
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(
        file_path=file_path,
        snapshot_date=date(2025, 1, 15),
        product_alias_resolver=mock_product_alias_resolver
    )

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        snapshot = parser.parse()

        # Check for unmapped product warning
        unmapped_warnings = [warning for warning in w if "unmapped product" in str(warning.message).lower()]
        assert len(unmapped_warnings) == 1
        assert "777777" in str(unmapped_warnings[0].message)


# ============================================================================
# to_optimization_dict() Method Tests
# ============================================================================

def test_to_optimization_dict_structure(create_test_excel_file):
    """Test that to_optimization_dict returns correct structure."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
        {"Material": 176283, "Plant": 6125, "Storage Location": 4070,
         "Base Unit of Measure": "CAS", "Unrestricted": 32.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()
    opt_dict = snapshot.to_optimization_dict()

    # Check structure
    assert isinstance(opt_dict, dict)
    assert len(opt_dict) == 2

    # Check keys are tuples
    for key in opt_dict.keys():
        assert isinstance(key, tuple)
        assert len(key) == 2
        assert isinstance(key[0], str)  # location_id
        assert isinstance(key[1], str)  # product_id

    # Check values
    assert opt_dict[("6122", "168846")] == 100.0
    assert opt_dict[("6125", "176283")] == 320.0


def test_to_optimization_dict_aggregates_storage_locations(create_test_excel_file):
    """Test that to_optimization_dict aggregates across storage locations."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},
        {"Material": 168846, "Plant": 6122, "Storage Location": 4070,
         "Base Unit of Measure": "EA", "Unrestricted": 30.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()
    opt_dict = snapshot.to_optimization_dict()

    # Should aggregate across storage locations
    assert len(opt_dict) == 1
    assert opt_dict[("6122", "168846")] == 80.0


def test_to_optimization_dict_keeps_plants_separate(create_test_excel_file):
    """Test that to_optimization_dict keeps different plants separate."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},
        {"Material": 168846, "Plant": 6125, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 30.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()
    opt_dict = snapshot.to_optimization_dict()

    # Should keep plants separate
    assert len(opt_dict) == 2
    assert opt_dict[("6122", "168846")] == 50.0
    assert opt_dict[("6125", "168846")] == 30.0


# ============================================================================
# InventorySnapshot Utility Method Tests
# ============================================================================

def test_get_total_quantity(create_test_excel_file):
    """Test get_total_quantity returns correct sum."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
        {"Material": 176283, "Plant": 6125, "Storage Location": 4070,
         "Base Unit of Measure": "CAS", "Unrestricted": 10.0},  # 100 units
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    assert snapshot.get_total_quantity() == 200.0


def test_get_quantity_by_location(create_test_excel_file):
    """Test get_quantity_by_location aggregates correctly."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
        {"Material": 176283, "Plant": 6122, "Storage Location": 4070,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},
        {"Material": 168847, "Plant": 6125, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 75.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()
    location_totals = snapshot.get_quantity_by_location()

    assert location_totals["6122"] == 150.0  # 100 + 50
    assert location_totals["6125"] == 75.0


def test_get_quantity_by_product(create_test_excel_file):
    """Test get_quantity_by_product aggregates correctly."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
        {"Material": 168846, "Plant": 6125, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},
        {"Material": 176283, "Plant": 6122, "Storage Location": 4070,
         "Base Unit of Measure": "EA", "Unrestricted": 75.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()
    product_totals = snapshot.get_quantity_by_product()

    assert product_totals["168846"] == 150.0  # 100 + 50
    assert product_totals["176283"] == 75.0


def test_get_quantity_by_storage_location(create_test_excel_file):
    """Test get_quantity_by_storage_location aggregates correctly."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
        {"Material": 176283, "Plant": 6125, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},
        {"Material": 168847, "Plant": 6122, "Storage Location": 4070,
         "Base Unit of Measure": "EA", "Unrestricted": 75.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()
    storage_totals = snapshot.get_quantity_by_storage_location()

    assert storage_totals["4000"] == 150.0  # 100 + 50
    assert storage_totals["4070"] == 75.0


# ============================================================================
# Integration Test with Real File (if available)
# ============================================================================

def test_real_file_integration():
    """Integration test with actual inventory file if available."""
    real_file_path = Path("data/examples/inventory_latest.XLSX")

    if not real_file_path.exists():
        pytest.skip("Real inventory file not available")

    parser = InventoryParser(
        file_path=real_file_path,
        snapshot_date=date(2025, 1, 15)
    )

    snapshot = parser.parse()

    # Basic validations
    assert snapshot is not None
    assert snapshot.snapshot_date == date(2025, 1, 15)
    assert len(snapshot.entries) > 0
    assert snapshot.get_total_quantity() > 0

    # Verify no Storage Location 5000
    for entry in snapshot.entries:
        assert entry.storage_location != "5000"

    # Verify optimization dict structure
    opt_dict = snapshot.to_optimization_dict()
    assert isinstance(opt_dict, dict)
    assert len(opt_dict) > 0

    # All keys should be (location_id, product_id) tuples
    for key, value in opt_dict.items():
        assert isinstance(key, tuple)
        assert len(key) == 2
        assert isinstance(value, float)
        assert value > 0


# ============================================================================
# Edge Cases and Boundary Conditions
# ============================================================================

def test_very_large_quantity_handled(create_test_excel_file):
    """Test that very large quantities are handled correctly."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "CAS", "Unrestricted": 999999.99},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == pytest.approx(9999999.9)


def test_null_plant_value_skipped(create_test_excel_file):
    """Test that rows with null Plant values are skipped."""
    data = [
        {"Material": 168846, "Plant": None, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
        {"Material": 176283, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 50.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))
    snapshot = parser.parse()

    # Only entry with valid plant should be included
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].product_id == "176283"


def test_null_base_unit_treated_as_unknown(create_test_excel_file):
    """Test that null Base Unit of Measure is treated as unknown."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": None, "Unrestricted": 100.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path, snapshot_date=date(2025, 1, 15))

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        snapshot = parser.parse()

        # Should warn about unknown unit (None)
        unknown_warnings = [warning for warning in w if "unknown unit" in str(warning.message).lower()]
        assert len(unknown_warnings) == 1

    # Should use 1:1 conversion
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].quantity == 100.0


def test_snapshot_date_set_correctly(create_test_excel_file):
    """Test that snapshot date is set correctly."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
    ]
    file_path = create_test_excel_file(data)

    test_date = date(2025, 6, 15)
    parser = InventoryParser(file_path=file_path, snapshot_date=test_date)
    snapshot = parser.parse()

    assert snapshot.snapshot_date == test_date


def test_default_snapshot_date_is_today(create_test_excel_file):
    """Test that default snapshot date is today if not provided."""
    data = [
        {"Material": 168846, "Plant": 6122, "Storage Location": 4000,
         "Base Unit of Measure": "EA", "Unrestricted": 100.0},
    ]
    file_path = create_test_excel_file(data)

    parser = InventoryParser(file_path=file_path)  # No snapshot_date
    snapshot = parser.parse()

    assert snapshot.snapshot_date == date.today()


def test_file_not_found_raises_error():
    """Test that FileNotFoundError is raised for non-existent files."""
    with pytest.raises(FileNotFoundError):
        InventoryParser(file_path="nonexistent_file.xlsx", snapshot_date=date(2025, 1, 15))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
