#!/bin/bash
# Run product alias resolution test suite

echo "=========================================="
echo "Product Alias Resolution Test Suite"
echo "=========================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run tests with coverage
echo "Running tests with coverage..."
echo ""

pytest -v \
    tests/test_product_alias_resolver.py \
    tests/test_parser_alias_integration.py \
    tests/test_alias_e2e.py \
    tests/test_alias_backward_compatibility.py \
    --cov=src/parsers/product_alias_resolver \
    --cov=src/parsers/excel_parser \
    --cov=src/parsers/sap_ibp_parser \
    --cov=src/parsers/multi_file_parser \
    --cov-report=term-missing \
    --cov-report=html:htmlcov_alias

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Coverage report saved to: htmlcov_alias/index.html"
echo ""
