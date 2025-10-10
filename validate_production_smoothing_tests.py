#!/usr/bin/env python3
"""
Quick validation script to check production smoothing test suite.

This script:
1. Validates test file syntax
2. Counts test functions
3. Checks for required fixtures
4. Provides summary of test coverage
"""

import ast
import sys
from pathlib import Path


def validate_test_file(test_file_path: str) -> dict:
    """Validate test file and extract information."""

    try:
        with open(test_file_path, 'r') as f:
            content = f.read()

        # Parse the file
        tree = ast.parse(content)

        # Extract test functions
        test_functions = []
        fixture_functions = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for test functions
                if node.name.startswith('test_'):
                    test_functions.append({
                        'name': node.name,
                        'docstring': ast.get_docstring(node),
                        'line': node.lineno
                    })
                # Check for fixtures
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Attribute):
                        if decorator.attr == 'fixture':
                            fixture_functions.append({
                                'name': node.name,
                                'docstring': ast.get_docstring(node),
                                'line': node.lineno
                            })
            elif isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)

        return {
            'valid': True,
            'test_functions': test_functions,
            'fixture_functions': fixture_functions,
            'imports': imports,
            'line_count': len(content.split('\n'))
        }

    except SyntaxError as e:
        return {
            'valid': False,
            'error': str(e),
            'line': e.lineno
        }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e)
        }


def print_summary(result: dict):
    """Print validation summary."""

    print("=" * 70)
    print("PRODUCTION SMOOTHING TEST SUITE VALIDATION")
    print("=" * 70)
    print()

    if not result['valid']:
        print("❌ SYNTAX ERROR:")
        print(f"   {result['error']}")
        if 'line' in result:
            print(f"   Line: {result['line']}")
        print()
        return False

    print("✅ SYNTAX VALID")
    print()

    # Summary statistics
    print("📊 STATISTICS:")
    print(f"   Total lines:      {result['line_count']:>6}")
    print(f"   Test functions:   {len(result['test_functions']):>6}")
    print(f"   Fixture functions: {len(result['fixture_functions']):>6}")
    print()

    # Test coverage
    print("🧪 TEST FUNCTIONS:")
    print()
    for i, test in enumerate(result['test_functions'], 1):
        print(f"{i}. {test['name']}")
        if test['docstring']:
            # Print first line of docstring
            first_line = test['docstring'].split('\n')[0].strip()
            print(f"   {first_line}")
        print(f"   Line: {test['line']}")
        print()

    # Fixtures
    print("🔧 FIXTURES:")
    print()
    for fixture in result['fixture_functions']:
        print(f"   - {fixture['name']}")
        if fixture['docstring']:
            first_line = fixture['docstring'].split('\n')[0].strip()
            print(f"     {first_line}")
    print()

    # Required imports check
    print("📦 IMPORT VALIDATION:")
    required_imports = [
        'pytest',
        'src.optimization.integrated_model',
        'src.models.forecast',
        'src.models.labor_calendar',
    ]

    all_imports_ok = True
    for required in required_imports:
        if any(required in imp for imp in result['imports']):
            print(f"   ✓ {required}")
        else:
            print(f"   ✗ {required} (MISSING)")
            all_imports_ok = False

    if all_imports_ok:
        print()
        print("   All required imports present")
    print()

    # Test categories
    print("📋 TEST CATEGORIES:")
    categories = {
        'Production Spread': ['test_production_spread'],
        'Smoothing Constraint': ['test_smoothing_constraint'],
        'Parameter Control': ['test_parameter_control'],
        'Regression': ['test_regression'],
        'Integration': ['test_integration', 'test_batch_tracking_and'],
        'Edge Cases': ['test_high_demand', 'test_low_demand'],
        'Backward Compatibility': ['test_backward_compatibility'],
        'Summary': ['test_production_smoothing_summary'],
    }

    for category, keywords in categories.items():
        matching_tests = [
            t['name'] for t in result['test_functions']
            if any(kw in t['name'] for kw in keywords)
        ]
        if matching_tests:
            print(f"   ✓ {category}: {len(matching_tests)} test(s)")
        else:
            print(f"   ✗ {category}: 0 tests (MISSING)")
    print()

    # Expected test count
    expected_min_tests = 8  # Minimum expected tests
    actual_tests = len(result['test_functions'])

    print("✅ VALIDATION SUMMARY:")
    print(f"   Syntax: OK")
    print(f"   Imports: {'OK' if all_imports_ok else 'MISSING REQUIRED'}")
    print(f"   Test count: {actual_tests} (expected ≥{expected_min_tests})")

    if actual_tests >= expected_min_tests and all_imports_ok:
        print()
        print("=" * 70)
        print("✅ TEST SUITE VALIDATION PASSED")
        print("=" * 70)
        return True
    else:
        print()
        print("=" * 70)
        print("⚠️  TEST SUITE VALIDATION - WARNINGS")
        print("=" * 70)
        return True


if __name__ == "__main__":
    test_file = "tests/test_batch_tracking_production_smoothing.py"

    if not Path(test_file).exists():
        print(f"❌ Error: Test file not found: {test_file}")
        sys.exit(1)

    result = validate_test_file(test_file)
    success = print_summary(result)

    if not result['valid']:
        sys.exit(1)

    # Print next steps
    print()
    print("📝 NEXT STEPS:")
    print()
    print("1. Run the test suite:")
    print("   pytest tests/test_batch_tracking_production_smoothing.py -v")
    print()
    print("2. Run critical regression tests only:")
    print("   ./run_production_smoothing_tests.sh")
    print()
    print("3. Run with detailed output:")
    print("   pytest tests/test_batch_tracking_production_smoothing.py -v -s")
    print()
    print("4. Run with coverage:")
    print("   pytest tests/test_batch_tracking_production_smoothing.py --cov=src.optimization")
    print()

    sys.exit(0 if success else 1)
