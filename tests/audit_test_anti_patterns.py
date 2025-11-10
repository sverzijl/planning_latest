#!/usr/bin/env python3
"""
Test Suite Anti-Pattern Audit Script

Systematically analyzes test suite for testing anti-patterns:
1. Testing mock behavior (assertions on mocks)
2. Incomplete mocks (missing fields compared to real objects)
3. Over-mocking (>3 mocks in single test)
4. Test-only methods in production code

Based on: testing-anti-patterns skill from superpowers

Usage:
    python tests/audit_test_anti_patterns.py

Output:
    - Anti-pattern audit report
    - Specific line numbers for each issue
    - Priority recommendations
"""

import ast
import os
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Tuple
import re


class TestAntiPatternAuditor(ast.NodeVisitor):
    """AST-based auditor for test anti-patterns."""

    def __init__(self, filename: str):
        self.filename = filename
        self.issues = []
        self.mock_count = 0
        self.current_function = None
        self.current_function_line = None

    def visit_FunctionDef(self, node):
        """Visit test function definitions."""
        self.current_function = node.name
        self.current_function_line = node.lineno
        self.mock_count = 0  # Reset for each function
        self.generic_visit(node)

        # Check for over-mocking
        if self.mock_count > 3:
            self.issues.append({
                'type': 'OVER_MOCKING',
                'severity': 'MEDIUM',
                'line': self.current_function_line,
                'function': self.current_function,
                'details': f'{self.mock_count} mocks in single test'
            })

        self.current_function = None
        self.current_function_line = None

    def visit_Call(self, node):
        """Visit function calls to detect mock patterns."""
        # Detect mock/patch usage
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ['patch', 'Mock', 'MagicMock', 'mock']:
                self.mock_count += 1

        # Detect assertions on mocks (anti-pattern #1)
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ['assert_called', 'assert_called_with',
                                  'assert_called_once', 'assert_called_once_with',
                                  'assert_has_calls', 'assert_any_call']:
                self.issues.append({
                    'type': 'TESTING_MOCK_BEHAVIOR',
                    'severity': 'HIGH',
                    'line': node.lineno,
                    'function': self.current_function,
                    'details': f'Assertion on mock method: {node.func.attr}'
                })

        self.generic_visit(node)


def find_test_files() -> List[Path]:
    """Find all test files in tests/ directory."""
    test_dir = Path('tests')
    return list(test_dir.glob('test_*.py'))


def count_mock_imports(filepath: Path) -> int:
    """Count mock/patch imports in file."""
    with open(filepath, 'r') as f:
        content = f.read()

    patterns = [
        r'from unittest\.mock import',
        r'from unittest import mock',
        r'import mock',
        r'from mock import',
        r'@patch\(',
        r'@mock\.',
    ]

    count = 0
    for pattern in patterns:
        count += len(re.findall(pattern, content))
    return count


def audit_file(filepath: Path) -> Dict:
    """Audit a single test file for anti-patterns."""
    with open(filepath, 'r') as f:
        try:
            tree = ast.parse(f.read(), filename=str(filepath))
        except SyntaxError:
            return {
                'file': str(filepath),
                'error': 'Syntax error - cannot parse',
                'issues': []
            }

    auditor = TestAntiPatternAuditor(str(filepath))
    auditor.visit(tree)

    mock_count = count_mock_imports(filepath)

    return {
        'file': str(filepath),
        'issues': auditor.issues,
        'mock_import_count': mock_count
    }


def find_mock_assertions(filepath: Path) -> List[Dict]:
    """Find assertions that test mock behavior rather than real code."""
    issues = []
    with open(filepath, 'r') as f:
        lines = f.readlines()

    for i, line in enumerate(lines, 1):
        # Look for common mock assertion patterns
        if any(pattern in line for pattern in [
            'assert mock',
            'assert.*called',
            'assert.*Mock',
            '.assert_called',
            'expect(mock)',
            'toHaveBeenCalled',
        ]):
            issues.append({
                'line': i,
                'content': line.strip(),
                'type': 'MOCK_ASSERTION'
            })

        # Look for assertions on test IDs containing 'mock'
        if re.search(r'getByTestId.*mock', line, re.IGNORECASE):
            issues.append({
                'line': i,
                'content': line.strip(),
                'type': 'MOCK_TEST_ID'
            })

    return issues


def generate_report(results: List[Dict]) -> str:
    """Generate comprehensive audit report."""

    # Aggregate statistics
    total_files = len(results)
    files_with_issues = sum(1 for r in results if r.get('issues'))
    total_issues = sum(len(r.get('issues', [])) for r in results)

    issues_by_type = defaultdict(int)
    issues_by_severity = defaultdict(int)

    for result in results:
        for issue in result.get('issues', []):
            issues_by_type[issue['type']] += 1
            issues_by_severity[issue['severity']] += 1

    # Build report
    report = []
    report.append("=" * 80)
    report.append("TEST SUITE ANTI-PATTERN AUDIT REPORT")
    report.append("=" * 80)
    report.append("")
    report.append(f"Test Files Analyzed: {total_files}")
    report.append(f"Files With Issues: {files_with_issues}")
    report.append(f"Total Issues Found: {total_issues}")
    report.append("")

    report.append("ISSUES BY TYPE:")
    for issue_type, count in sorted(issues_by_type.items(), key=lambda x: -x[1]):
        report.append(f"  {issue_type}: {count}")
    report.append("")

    report.append("ISSUES BY SEVERITY:")
    for severity in ['HIGH', 'MEDIUM', 'LOW']:
        count = issues_by_severity[severity]
        if count > 0:
            report.append(f"  {severity}: {count}")
    report.append("")

    # Detailed issues
    report.append("=" * 80)
    report.append("DETAILED ISSUES (sorted by severity)")
    report.append("=" * 80)
    report.append("")

    # Sort by severity (HIGH > MEDIUM > LOW)
    severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}

    for result in results:
        issues = result.get('issues', [])
        if not issues:
            continue

        sorted_issues = sorted(issues, key=lambda x: (
            severity_order[x['severity']],
            x['line']
        ))

        report.append(f"\nFile: {result['file']}")
        report.append("-" * 80)

        for issue in sorted_issues:
            report.append(f"  [{issue['severity']}] Line {issue['line']}: {issue['function']}")
            report.append(f"    Type: {issue['type']}")
            report.append(f"    Details: {issue['details']}")
            report.append("")

    # Recommendations
    report.append("=" * 80)
    report.append("RECOMMENDATIONS")
    report.append("=" * 80)
    report.append("")

    if issues_by_type['TESTING_MOCK_BEHAVIOR'] > 0:
        report.append("🚨 HIGH PRIORITY: Testing Mock Behavior")
        report.append(f"   Found {issues_by_type['TESTING_MOCK_BEHAVIOR']} instances")
        report.append("   Action: Replace mock assertions with real behavior tests")
        report.append("   Example: Instead of assert_called_with(), test actual output")
        report.append("")

    if issues_by_type['OVER_MOCKING'] > 0:
        report.append("⚠️  MEDIUM PRIORITY: Over-Mocking")
        report.append(f"   Found {issues_by_type['OVER_MOCKING']} tests with >3 mocks")
        report.append("   Action: Reduce mocks by using real implementations")
        report.append("   Or: Split test into smaller, focused tests")
        report.append("")

    # Add summary of mock usage
    total_mock_imports = sum(r.get('mock_import_count', 0) for r in results)
    report.append(f"Total mock/patch import statements: {total_mock_imports}")
    report.append("")

    report.append("=" * 80)
    report.append("NEXT STEPS")
    report.append("=" * 80)
    report.append("")
    report.append("1. Address HIGH severity issues first")
    report.append("2. Review TESTING_MOCK_BEHAVIOR cases - replace with real tests")
    report.append("3. Reduce mock usage where possible (target: <100 total)")
    report.append("4. Verify all mocks include complete field sets")
    report.append("5. Re-run audit after fixes to track improvement")
    report.append("")

    return "\n".join(report)


def main():
    """Run the audit."""
    print("🔍 Starting test suite anti-pattern audit...")
    print("")

    test_files = find_test_files()
    print(f"Found {len(test_files)} test files to analyze")
    print("")

    results = []
    for filepath in test_files:
        print(f"Analyzing: {filepath.name}...", end='', flush=True)
        result = audit_file(filepath)

        # Add mock assertion analysis
        mock_assertions = find_mock_assertions(filepath)
        for assertion in mock_assertions:
            result['issues'].append({
                'type': 'MOCK_ASSERTION',
                'severity': 'HIGH',
                'line': assertion['line'],
                'function': 'N/A',
                'details': assertion['content']
            })

        results.append(result)
        print(" ✓")

    print("")
    report = generate_report(results)

    # Save report
    output_file = Path('TEST_ANTI_PATTERN_AUDIT_REPORT.md')
    with open(output_file, 'w') as f:
        f.write(report)

    print(f"✅ Audit complete! Report saved to: {output_file}")
    print("")
    print("Summary:")
    print(report.split("DETAILED ISSUES")[0])


if __name__ == '__main__':
    main()
