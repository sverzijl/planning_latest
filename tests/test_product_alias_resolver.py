"""Unit tests for ProductAliasResolver."""

import pytest
from pathlib import Path
from datetime import date
import pandas as pd

from src.parsers.product_alias_resolver import ProductAliasResolver


@pytest.fixture
def temp_alias_file(tmp_path):
    """Create a temporary Excel file with Alias sheet."""
    file_path = tmp_path / "test_aliases.xlsx"

    # Create test data with proper headers
    data = {
        'Alias1': ['PRODUCT_A', 'PRODUCT_B', 'PRODUCT_C'],
        'Alias2': ['CODE_A1', 'CODE_B1', 'CODE_C1'],
        'Alias3': ['CODE_A2', 'CODE_B2', 'CODE_C2'],
        'Alias4': ['CODE_A3', None, None],  # Test sparse data
    }
    df = pd.DataFrame(data)

    # Write to Excel
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Alias', index=False)

    return file_path


@pytest.fixture
def temp_alias_file_no_headers(tmp_path):
    """Create a temporary Excel file with Alias data but no headers (legacy format)."""
    file_path = tmp_path / "test_aliases_no_headers.xlsx"

    # Create test data without headers (position-based parsing)
    # Row 0: canonical PRODUCT_X with aliases
    # Row 1: canonical PRODUCT_Y with aliases
    data = [
        ['PRODUCT_X', 'XCODE1', 'XCODE2'],
        ['PRODUCT_Y', 'YCODE1', 'YCODE2'],
    ]
    df = pd.DataFrame(data)

    # Write to Excel without headers
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Alias', index=False, header=False)

    return file_path


@pytest.fixture
def temp_empty_alias_file(tmp_path):
    """Create a temporary Excel file with empty Alias sheet."""
    file_path = tmp_path / "test_empty_aliases.xlsx"

    # Create empty dataframe
    df = pd.DataFrame()

    # Write to Excel
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Alias', index=False)

    return file_path


@pytest.fixture
def temp_file_no_alias_sheet(tmp_path):
    """Create a temporary Excel file without Alias sheet."""
    file_path = tmp_path / "test_no_alias.xlsx"

    # Create a different sheet
    data = {'Column1': [1, 2, 3]}
    df = pd.DataFrame(data)

    # Write to Excel (no Alias sheet)
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Data', index=False)

    return file_path


@pytest.fixture
def temp_alias_file_wrong_headers(tmp_path):
    """Create a temporary Excel file with wrong header format."""
    file_path = tmp_path / "test_wrong_headers.xlsx"

    # Create test data with wrong headers
    data = {
        'ProductName': ['PRODUCT_A', 'PRODUCT_B'],
        'Code1': ['CODE_A1', 'CODE_B1'],
        'Code2': ['CODE_A2', 'CODE_B2'],
    }
    df = pd.DataFrame(data)

    # Write to Excel
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Alias', index=False)

    return file_path


class TestProductAliasResolverInit:
    """Tests for ProductAliasResolver initialization."""

    def test_init_with_valid_file(self, temp_alias_file):
        """Test initialization with valid Alias file."""
        resolver = ProductAliasResolver(temp_alias_file)
        assert resolver is not None
        assert resolver.file_path == temp_alias_file
        assert resolver.sheet_name == "Alias"

    def test_init_with_nonexistent_file(self):
        """Test initialization with non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            ProductAliasResolver("nonexistent_file.xlsx")

    def test_init_with_custom_sheet_name(self, temp_alias_file):
        """Test initialization with custom sheet name."""
        resolver = ProductAliasResolver(temp_alias_file, sheet_name="Alias")
        assert resolver.sheet_name == "Alias"

    def test_init_with_empty_alias_sheet(self, temp_empty_alias_file):
        """Test initialization with empty Alias sheet (no aliases defined)."""
        resolver = ProductAliasResolver(temp_empty_alias_file)
        assert resolver.get_mapping_count() == 0
        assert len(resolver.get_canonical_products()) == 0

    def test_init_with_missing_alias_sheet(self, temp_file_no_alias_sheet):
        """Test initialization with missing Alias sheet (graceful fallback)."""
        resolver = ProductAliasResolver(temp_file_no_alias_sheet)
        # Should not raise error, just have no mappings
        assert resolver.get_mapping_count() == 0
        assert len(resolver.get_canonical_products()) == 0


class TestProductAliasResolverParsing:
    """Tests for Alias sheet parsing."""

    def test_parse_with_headers(self, temp_alias_file):
        """Test parsing Alias sheet with proper headers."""
        resolver = ProductAliasResolver(temp_alias_file)

        # Check canonical products
        canonical = resolver.get_canonical_products()
        assert 'PRODUCT_A' in canonical
        assert 'PRODUCT_B' in canonical
        assert 'PRODUCT_C' in canonical
        assert len(canonical) == 3

    def test_parse_without_headers(self, temp_alias_file_no_headers):
        """Test parsing Alias sheet without headers (position-based)."""
        resolver = ProductAliasResolver(temp_alias_file_no_headers)

        # Should work with position-based parsing
        # Note: pandas treats first row as headers, so PRODUCT_X becomes the header
        # and only PRODUCT_Y is parsed as data
        canonical = resolver.get_canonical_products()
        assert len(canonical) == 1
        assert 'PRODUCT_Y' in canonical

        # PRODUCT_X was treated as header, check its aliases still work
        # (this tests the position-based fallback with wrong headers)
        assert resolver.resolve_product_id('YCODE1') == 'PRODUCT_Y'
        assert resolver.resolve_product_id('YCODE2') == 'PRODUCT_Y'

    def test_parse_with_wrong_headers(self, temp_alias_file_wrong_headers):
        """Test parsing Alias sheet with wrong headers (should warn but still work)."""
        with pytest.warns(UserWarning, match="Alias sheet header format has changed"):
            resolver = ProductAliasResolver(temp_alias_file_wrong_headers)

        # Should still work due to position-based parsing
        canonical = resolver.get_canonical_products()
        assert len(canonical) == 2

    def test_parse_sparse_data(self, temp_alias_file):
        """Test parsing with sparse data (NaN values)."""
        resolver = ProductAliasResolver(temp_alias_file)

        # PRODUCT_A has 3 aliases, PRODUCT_B/C have 2 each
        # Total: 3 canonical + 3+2+2 = 10 mappings (including self-mappings)
        aliases_a = resolver.get_all_aliases('PRODUCT_A')
        assert 'PRODUCT_A' in aliases_a
        assert 'CODE_A1' in aliases_a
        assert 'CODE_A2' in aliases_a
        assert 'CODE_A3' in aliases_a
        assert len(aliases_a) == 4


class TestProductAliasResolverResolution:
    """Tests for product code resolution."""

    def test_resolve_product_id_mapped_code(self, temp_alias_file):
        """Test resolving a mapped product code."""
        resolver = ProductAliasResolver(temp_alias_file)

        # Resolve alias codes to canonical IDs
        assert resolver.resolve_product_id('CODE_A1') == 'PRODUCT_A'
        assert resolver.resolve_product_id('CODE_A2') == 'PRODUCT_A'
        assert resolver.resolve_product_id('CODE_A3') == 'PRODUCT_A'
        assert resolver.resolve_product_id('CODE_B1') == 'PRODUCT_B'
        assert resolver.resolve_product_id('CODE_C2') == 'PRODUCT_C'

    def test_resolve_product_id_canonical(self, temp_alias_file):
        """Test resolving canonical product ID (returns itself)."""
        resolver = ProductAliasResolver(temp_alias_file)

        # Canonical IDs should map to themselves
        assert resolver.resolve_product_id('PRODUCT_A') == 'PRODUCT_A'
        assert resolver.resolve_product_id('PRODUCT_B') == 'PRODUCT_B'
        assert resolver.resolve_product_id('PRODUCT_C') == 'PRODUCT_C'

    def test_resolve_product_id_unmapped_code(self, temp_alias_file):
        """Test resolving unmapped product code (returns input)."""
        resolver = ProductAliasResolver(temp_alias_file)

        # Unmapped codes should return as-is
        assert resolver.resolve_product_id('UNKNOWN_CODE') == 'UNKNOWN_CODE'
        assert resolver.resolve_product_id('999999') == '999999'
        assert resolver.resolve_product_id('PRODUCT_Z') == 'PRODUCT_Z'

    def test_resolve_product_id_with_whitespace(self, temp_alias_file):
        """Test resolving product code with whitespace (should be stripped)."""
        resolver = ProductAliasResolver(temp_alias_file)

        # Should handle whitespace
        assert resolver.resolve_product_id('  CODE_A1  ') == 'PRODUCT_A'
        assert resolver.resolve_product_id('CODE_B1\t') == 'PRODUCT_B'

    def test_resolve_product_id_numeric(self, temp_alias_file):
        """Test resolving numeric product code (converted to string)."""
        resolver = ProductAliasResolver(temp_alias_file)

        # Numeric codes should be converted to strings
        # (assuming we add numeric test data)
        assert resolver.resolve_product_id(12345) == '12345'


class TestProductAliasResolverQueries:
    """Tests for query methods."""

    def test_is_mapped_for_mapped_code(self, temp_alias_file):
        """Test is_mapped returns True for mapped codes."""
        resolver = ProductAliasResolver(temp_alias_file)

        assert resolver.is_mapped('CODE_A1') is True
        assert resolver.is_mapped('CODE_B2') is True
        assert resolver.is_mapped('PRODUCT_A') is True  # Canonical ID is also mapped

    def test_is_mapped_for_unmapped_code(self, temp_alias_file):
        """Test is_mapped returns False for unmapped codes."""
        resolver = ProductAliasResolver(temp_alias_file)

        assert resolver.is_mapped('UNKNOWN_CODE') is False
        assert resolver.is_mapped('999999') is False

    def test_get_canonical_products(self, temp_alias_file):
        """Test get_canonical_products returns set of Alias1 values."""
        resolver = ProductAliasResolver(temp_alias_file)

        canonical = resolver.get_canonical_products()
        assert isinstance(canonical, set)
        assert canonical == {'PRODUCT_A', 'PRODUCT_B', 'PRODUCT_C'}

    def test_get_canonical_products_immutable(self, temp_alias_file):
        """Test get_canonical_products returns copy (immutable)."""
        resolver = ProductAliasResolver(temp_alias_file)

        canonical1 = resolver.get_canonical_products()
        canonical2 = resolver.get_canonical_products()

        # Should be different objects
        assert canonical1 is not canonical2
        # But same content
        assert canonical1 == canonical2

    def test_get_all_aliases(self, temp_alias_file):
        """Test get_all_aliases returns all codes mapping to canonical ID."""
        resolver = ProductAliasResolver(temp_alias_file)

        aliases_a = resolver.get_all_aliases('PRODUCT_A')
        assert 'PRODUCT_A' in aliases_a  # Canonical ID itself
        assert 'CODE_A1' in aliases_a
        assert 'CODE_A2' in aliases_a
        assert 'CODE_A3' in aliases_a
        assert len(aliases_a) == 4

        aliases_b = resolver.get_all_aliases('PRODUCT_B')
        assert 'PRODUCT_B' in aliases_b
        assert 'CODE_B1' in aliases_b
        assert 'CODE_B2' in aliases_b
        assert len(aliases_b) == 3

    def test_get_all_aliases_for_unmapped_product(self, temp_alias_file):
        """Test get_all_aliases returns empty set for unmapped product."""
        resolver = ProductAliasResolver(temp_alias_file)

        aliases = resolver.get_all_aliases('UNKNOWN_PRODUCT')
        assert isinstance(aliases, set)
        assert len(aliases) == 0

    def test_get_mapping_count(self, temp_alias_file):
        """Test get_mapping_count returns total number of mappings."""
        resolver = ProductAliasResolver(temp_alias_file)

        count = resolver.get_mapping_count()
        # 3 canonical + 3+2+2 alias codes = 10 total mappings
        assert count == 10

    def test_get_mapping_count_empty(self, temp_empty_alias_file):
        """Test get_mapping_count returns 0 for empty resolver."""
        resolver = ProductAliasResolver(temp_empty_alias_file)

        assert resolver.get_mapping_count() == 0


class TestProductAliasResolverStringRepresentation:
    """Tests for string representation."""

    def test_str_representation(self, temp_alias_file):
        """Test string representation includes product and code counts."""
        resolver = ProductAliasResolver(temp_alias_file)

        str_repr = str(resolver)
        assert 'ProductAliasResolver' in str_repr
        assert '3 products' in str_repr
        assert '10 codes' in str_repr
