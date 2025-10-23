#!/usr/bin/env python3
"""
Script to automatically fix all test files to include products parameter.

This script:
1. Scans all test files for UnifiedNodeModel instantiations
2. Extracts product_ids from forecast objects
3. Adds products parameter using create_test_products helper
"""

import re
import os
from pathlib import Path

def fix_test_file(filepath):
    """Fix a single test file by adding products parameter."""

    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content

    # Check if already has products parameter
    if re.search(r'products\s*=\s*create_test_products', content):
        print(f"  ✓ Already fixed: {filepath.name}")
        return False

    # Check if UnifiedNodeModel is used
    if 'UnifiedNodeModel(' not in content:
        return False

    # Add import for create_test_products if not present
    if 'from tests.conftest import create_test_products' not in content:
        # Find the imports section
        if 'import pytest' in content:
            content = content.replace(
                'import pytest',
                'import pytest\nfrom tests.conftest import create_test_products'
            )
        elif 'from src' in content:
            # Add at the top after initial imports
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if line.startswith('from src'):
                    lines.insert(i, 'from tests.conftest import create_test_products')
                    break
            content = '\n'.join(lines)

    # Find all UnifiedNodeModel instantiations and add products before them
    # Pattern: find "model = UnifiedNodeModel(" or "model_start = time.time()\n\n    model = UnifiedNodeModel("

    # Strategy: Add products creation just before UnifiedNodeModel call
    # Look for forecast parameter to extract product_ids

    pattern = r'([ \t]*)(model = UnifiedNodeModel\()'

    def replacement(match):
        indent = match.group(1)
        model_line = match.group(2)

        # Add products creation before model instantiation
        products_code = f'\n{indent}# Create products for model\n'
        products_code += f'{indent}product_ids = sorted(set(entry.product_id for entry in forecast.entries))\n'
        products_code += f'{indent}products = create_test_products(product_ids)\n\n'
        products_code += f'{indent}{model_line}'

        return products_code

    content = re.sub(pattern, replacement, content)

    # Now add products=products parameter to UnifiedNodeModel calls
    # Find all UnifiedNodeModel( ... ) blocks and add products parameter

    def add_products_param(match):
        full_match = match.group(0)

        # Check if products already in parameters
        if 'products=' in full_match:
            return full_match

        # Add products parameter after forecast parameter
        if 'forecast=' in full_match:
            # Add after forecast line
            modified = re.sub(
                r'(forecast=[^,]+,)',
                r'\1\n        products=products,',
                full_match
            )
            return modified

        return full_match

    # Match UnifiedNodeModel(...) including multiline
    pattern = r'UnifiedNodeModel\([^)]+\)'
    content = re.sub(pattern, add_products_param, content, flags=re.DOTALL)

    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✓ Fixed: {filepath.name}")
        return True

    return False

def main():
    tests_dir = Path('/home/sverzijl/planning_latest/tests')

    # Find all test files with UnifiedNodeModel
    test_files = []
    for test_file in tests_dir.glob('test_*.py'):
        with open(test_file, 'r') as f:
            if 'UnifiedNodeModel(' in f.read():
                test_files.append(test_file)

    print(f"Found {len(test_files)} test files with UnifiedNodeModel")
    print("=" * 80)

    fixed_count = 0
    for test_file in sorted(test_files):
        if fix_test_file(test_file):
            fixed_count += 1

    print("=" * 80)
    print(f"Fixed {fixed_count} test files")
    print(f"Already fixed or no changes needed: {len(test_files) - fixed_count}")

if __name__ == '__main__':
    main()
