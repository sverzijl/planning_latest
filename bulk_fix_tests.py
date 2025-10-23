#!/usr/bin/env python3
"""Bulk fix all test files to add products parameter to UnifiedNodeModel."""

import re
from pathlib import Path

def fix_file(filepath):
    """Fix a single test file."""
    with open(filepath, 'r') as f:
        content = f.read()

    original_content = content

    # Skip if already has the import
    already_fixed = 'from tests.conftest import create_test_products' in content

    # Skip if doesn't use UnifiedNodeModel
    if 'UnifiedNodeModel(' not in content:
        return False, "No UnifiedNodeModel usage"

    # Add import if not present
    if not already_fixed:
        # Find import section and add our import
        if 'from src.optimization.unified_node_model import UnifiedNodeModel' in content:
            content = content.replace(
                'from src.optimization.unified_node_model import UnifiedNodeModel',
                'from src.optimization.unified_node_model import UnifiedNodeModel\nfrom tests.conftest import create_test_products'
            )
        elif 'import pytest' in content:
            content = content.replace(
                'import pytest',
                'import pytest\nfrom tests.conftest import create_test_products'
            )

    # Find all UnifiedNodeModel( instantiations and add products setup before them
    # Look for pattern: "model = UnifiedNodeModel("

    lines = content.split('\n')
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line starts a UnifiedNodeModel instantiation
        if re.search(r'\s*model = UnifiedNodeModel\(', line):
            # Check if we already added products on previous lines
            # Look back up to 5 lines
            already_has_products = False
            for j in range(max(0, i-5), i):
                if 'products = create_test_products' in lines[j]:
                    already_has_products = True
                    break

            if not already_has_products:
                # Add products setup before this line
                indent = re.match(r'(\s*)', line).group(1)

                # Add comment and products creation
                new_lines.append(f"{indent}# Create products for model (extract unique product IDs from forecast)")
                new_lines.append(f"{indent}product_ids = sorted(set(entry.product_id for entry in forecast.entries))")
                new_lines.append(f"{indent}products = create_test_products(product_ids)")
                new_lines.append("")  # Blank line

        new_lines.append(line)
        i += 1

    content = '\n'.join(new_lines)

    # Now add products=products parameter to all UnifiedNodeModel calls
    # Use a more careful regex that handles multiline calls

    def add_products_to_call(match):
        full_call = match.group(0)

        # Skip if already has products parameter
        if 'products=' in full_call:
            return full_call

        # Add products parameter after forecast parameter
        if 'forecast=' in full_call:
            # Find the forecast parameter line and add products after it
            modified = re.sub(
                r'(forecast=[^,\n]+,)\n',
                r'\1\n        products=products,\n',
                full_call,
                count=1
            )
            return modified

        return full_call

    # Match UnifiedNodeModel(...) including multiline - be careful with nesting
    # This regex matches from UnifiedNodeModel( to the matching closing paren

    # Simpler approach: just look for forecast= line and add products after it
    content = re.sub(
        r'(        forecast=[^,\n]+,)\n(        (?!products=))',
        r'\1\n        products=products,\n\2',
        content
    )

    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        return True, "Fixed"
    else:
        return False, "No changes needed"

def main():
    tests_dir = Path('/home/sverzijl/planning_latest/tests')

    # Get all test files with UnifiedNodeModel
    test_files = []
    for f in sorted(tests_dir.glob('test_*.py')):
        with open(f) as file:
            if 'UnifiedNodeModel(' in file.read():
                test_files.append(f)

    print(f"Found {len(test_files)} test files with UnifiedNodeModel\n")

    # Skip integration test as we already fixed it manually
    test_files = [f for f in test_files if 'test_integration_ui_workflow.py' not in str(f)]

    fixed_count = 0
    skipped_count = 0

    for filepath in test_files:
        changed, reason = fix_file(filepath)
        if changed:
            print(f"✓ {filepath.name}: {reason}")
            fixed_count += 1
        else:
            print(f"  {filepath.name}: {reason}")
            skipped_count += 1

    print(f"\n{'='*80}")
    print(f"Fixed: {fixed_count}")
    print(f"Skipped: {skipped_count}")
    print(f"Total: {len(test_files)}")

if __name__ == '__main__':
    main()
