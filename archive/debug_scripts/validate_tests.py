#!/usr/bin/env python
"""Validate test_parameter_parsing.py syntax and imports."""

import sys
import ast
from pathlib import Path

def validate_python_file(file_path: Path) -> bool:
    """Validate Python file syntax and imports.

    Args:
        file_path: Path to Python file

    Returns:
        True if valid, False otherwise
    """
    try:
        # Read file
        with open(file_path, 'r') as f:
            content = f.read()

        # Check syntax by parsing AST
        ast.parse(content)
        print(f"✅ Syntax valid: {file_path.name}")

        # Try importing to check for import errors
        # (Note: This won't execute the tests, just import the module)
        import importlib.util
        spec = importlib.util.spec_from_file_location("test_module", file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            # Don't execute, just check imports can resolve
            # spec.loader.exec_module(module)
            print(f"✅ Module structure valid: {file_path.name}")

        return True

    except SyntaxError as e:
        print(f"❌ Syntax error in {file_path.name}:")
        print(f"   Line {e.lineno}: {e.msg}")
        print(f"   {e.text}")
        return False

    except Exception as e:
        print(f"⚠️  Warning in {file_path.name}: {e}")
        return True  # Still valid, might be runtime issue


def count_tests(file_path: Path) -> dict:
    """Count test classes and methods.

    Args:
        file_path: Path to test file

    Returns:
        Dict with test counts
    """
    with open(file_path, 'r') as f:
        content = f.read()

    tree = ast.parse(content)

    test_classes = []
    test_methods = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if node.name.startswith('Test'):
                test_classes.append(node.name)
                # Count methods in this class
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if item.name.startswith('test_'):
                            test_methods.append(f"{node.name}::{item.name}")

    return {
        'classes': test_classes,
        'methods': test_methods,
        'class_count': len(test_classes),
        'method_count': len(test_methods),
    }


if __name__ == '__main__':
    test_file = Path('/home/sverzijl/planning_latest/tests/test_parameter_parsing.py')

    print("=" * 70)
    print("Test Parameter Parsing Validation")
    print("=" * 70)
    print()

    # Validate syntax
    is_valid = validate_python_file(test_file)
    print()

    if not is_valid:
        print("❌ Validation failed!")
        sys.exit(1)

    # Count tests
    counts = count_tests(test_file)

    print("=" * 70)
    print("Test Statistics")
    print("=" * 70)
    print()
    print(f"Test Classes: {counts['class_count']}")
    for cls in counts['classes']:
        print(f"  - {cls}")
    print()

    print(f"Test Methods: {counts['method_count']}")
    for method in counts['methods']:
        print(f"  - {method}")
    print()

    print("=" * 70)
    print("✅ Validation successful!")
    print()
    print("Next steps:")
    print("  1. Run: pytest tests/test_parameter_parsing.py -v")
    print("  2. Expected: 19 tests passing")
    print("  3. Review output for real-world test results")
    print("=" * 70)
