#!/usr/bin/env python3
"""Comprehensive Test Validation After Non-Fixed Day Fix

This script validates the fix in unified_node_model.py (lines 343-346)
that changed day_hours from labor_day.fixed_hours (was 0) to 24.0 for non-fixed days.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


class TestValidator:
    """Runs comprehensive test validation and generates report."""

    def __init__(self):
        self.venv_python = Path("/home/sverzijl/planning_latest/venv/bin/python")
        self.results = {
            'phase1': {},
            'phase2': {},
            'phase3': {},
        }
        self.start_time = None
        self.end_time = None

    def run_test(self, test_path, name):
        """Run a single test and return result."""
        print(f"\n{'='*80}")
        print(f"Running: {name}")
        print(f"{'='*80}")

        cmd = [str(self.venv_python), "-m", "pytest", test_path, "-v"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            passed = result.returncode == 0

            # Print output
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            return {
                'passed': passed,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
            }

        except subprocess.TimeoutExpired:
            print(f"TIMEOUT: Test exceeded 120 seconds")
            return {
                'passed': False,
                'returncode': -1,
                'stdout': '',
                'stderr': 'Test timeout',
            }

        except Exception as e:
            print(f"ERROR: {e}")
            return {
                'passed': False,
                'returncode': -2,
                'stdout': '',
                'stderr': str(e),
            }

    def run_phase1(self):
        """Phase 1: Non-Fixed Day Unit Tests"""
        print("\n" + "="*80)
        print("PHASE 1: NON-FIXED DAY UNIT TESTS")
        print("="*80)

        tests = {
            'test1_weekend_below_min': {
                'path': 'tests/test_labor_cost_piecewise.py::test_piecewise_non_fixed_day_below_minimum',
                'name': 'Weekend Production Below Minimum',
            },
            'test2_holiday_above_min': {
                'path': 'tests/test_labor_overhead_holiday.py::test_public_holiday_overhead_included',
                'name': 'Public Holiday Overhead (Above Minimum)',
            },
            'test3_holiday_below_min': {
                'path': 'tests/test_labor_overhead_holiday.py::test_public_holiday_overhead_below_minimum',
                'name': 'Public Holiday Overhead (Below Minimum)',
            },
        }

        for test_id, test_info in tests.items():
            self.results['phase1'][test_id] = self.run_test(
                test_info['path'],
                test_info['name'],
            )

    def run_phase2(self):
        """Phase 2: Regression Test Suite"""
        print("\n" + "="*80)
        print("PHASE 2: REGRESSION TEST SUITE")
        print("="*80)

        tests = {
            'suite1_weekday_labor': {
                'path': 'tests/test_labor_cost_piecewise.py',
                'name': 'Weekday Labor Costs',
            },
            'suite2_multi_day': {
                'path': 'tests/test_labor_overhead_multi_day.py',
                'name': 'Multi-Day Consistency',
            },
            'suite3_overtime': {
                'path': 'tests/test_overtime_preference.py',
                'name': 'Overtime Preference',
            },
            'suite4_baseline': {
                'path': 'tests/test_labor_cost_baseline.py',
                'name': 'Baseline Labor Costs',
            },
            'suite5_isolation': {
                'path': 'tests/test_labor_cost_isolation.py',
                'name': 'Labor Cost Isolation',
            },
            'suite6_unified': {
                'path': 'tests/test_unified_node_model.py',
                'name': 'Unified Model Core',
            },
        }

        for suite_id, suite_info in tests.items():
            self.results['phase2'][suite_id] = self.run_test(
                suite_info['path'],
                suite_info['name'],
            )

    def run_phase3(self):
        """Phase 3: Integration Test"""
        print("\n" + "="*80)
        print("PHASE 3: INTEGRATION TEST")
        print("="*80)

        self.results['phase3']['integration'] = self.run_test(
            'tests/test_integration_ui_workflow.py',
            'UI Workflow (4-week horizon)',
        )

    def print_summary(self):
        """Print validation summary."""
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)

        # Phase 1 Results
        print("\nPHASE 1: Non-Fixed Day Unit Tests")
        phase1_tests = [
            ('test1_weekend_below_min', 'Weekend Below Min'),
            ('test2_holiday_above_min', 'Holiday Above Min'),
            ('test3_holiday_below_min', 'Holiday Below Min'),
        ]

        for test_id, test_name in phase1_tests:
            result = self.results['phase1'].get(test_id, {})
            passed = result.get('passed', False)
            status = 'PASS ✓' if passed else 'FAIL ✗'
            print(f"  {test_name:30s}: {status}")

        # Phase 2 Results
        print("\nPHASE 2: Regression Test Suite")
        phase2_suites = [
            ('suite1_weekday_labor', 'Weekday Labor'),
            ('suite2_multi_day', 'Multi-Day'),
            ('suite3_overtime', 'Overtime Preference'),
            ('suite4_baseline', 'Baseline Labor'),
            ('suite5_isolation', 'Labor Isolation'),
            ('suite6_unified', 'Unified Model Core'),
        ]

        for suite_id, suite_name in phase2_suites:
            result = self.results['phase2'].get(suite_id, {})
            passed = result.get('passed', False)
            status = 'PASS ✓' if passed else 'FAIL ✗'
            print(f"  {suite_name:30s}: {status}")

        # Phase 3 Results
        print("\nPHASE 3: Integration Test")
        integration_result = self.results['phase3'].get('integration', {})
        integration_passed = integration_result.get('passed', False)
        status = 'PASS ✓' if integration_passed else 'FAIL ✗'
        print(f"  Integration Test:             {status}")

        # Overall Status
        print("\n" + "="*80)

        # Count failures
        phase1_failures = sum(1 for r in self.results['phase1'].values() if not r.get('passed', False))
        phase2_failures = sum(1 for r in self.results['phase2'].values() if not r.get('passed', False))
        phase3_failures = sum(1 for r in self.results['phase3'].values() if not r.get('passed', False))
        total_failures = phase1_failures + phase2_failures + phase3_failures

        # Count fixed tests (Phase 1)
        phase1_passed = sum(1 for r in self.results['phase1'].values() if r.get('passed', False))

        # Total tests
        total_tests = (
            len(self.results['phase1']) +
            len(self.results['phase2']) +
            len(self.results['phase3'])
        )
        total_passed = total_tests - total_failures

        if total_failures == 0:
            print("OVERALL STATUS: SUCCESS ✓")
            print(f"All {total_tests} test suites passed!")
            print(f"\nTests Fixed: {phase1_passed} (were INFEASIBLE, now PASS)")
            print("No regressions detected.")
        else:
            print("OVERALL STATUS: FAILURE ✗")
            print(f"Total: {total_passed}/{total_tests} test suites passed")
            print(f"Phase 1 failures: {phase1_failures}")
            print(f"Phase 2 failures: {phase2_failures}")
            print(f"Phase 3 failures: {phase3_failures}")

        # Timing
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            print(f"\nTotal execution time: {duration:.1f} seconds")

        print("="*80)
        print()

        return total_failures

    def run_all(self):
        """Run all validation phases."""
        self.start_time = datetime.now()

        print("="*80)
        print("COMPREHENSIVE TEST VALIDATION - NON-FIXED DAY FIX")
        print("="*80)
        print()
        print("Fix: Changed day_hours = labor_day.fixed_hours (was 0)")
        print("     to day_hours = 24.0 for non-fixed days")
        print()
        print(f"Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

        # Run phases
        self.run_phase1()
        self.run_phase2()
        self.run_phase3()

        self.end_time = datetime.now()

        # Print summary
        failures = self.print_summary()

        return failures


def main():
    """Main entry point."""
    validator = TestValidator()
    failures = validator.run_all()
    sys.exit(failures)


if __name__ == "__main__":
    main()
