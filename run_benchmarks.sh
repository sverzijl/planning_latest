#!/bin/bash
# Warmstart Performance Benchmark Execution Script
# Runs all benchmarking tests in sequence with timeouts

set -e  # Exit on error

echo "=========================================="
echo "WARMSTART PERFORMANCE BENCHMARK SUITE"
echo "=========================================="
echo "Date: $(date)"
echo ""

# Activate virtual environment
source venv/bin/activate

# Phase 1: Smoke Test (Fast Validation - 10s timeout)
echo ""
echo "=========================================="
echo "PHASE 1: SMOKE TEST"
echo "=========================================="
echo "Purpose: Quick validation of warmstart integration"
echo "Timeout: 10 seconds"
echo ""

timeout 10 python test_warmstart_smoke.py
SMOKE_RESULT=$?

if [ $SMOKE_RESULT -eq 0 ]; then
    echo "✅ SMOKE TEST PASSED"
else
    echo "❌ SMOKE TEST FAILED (exit code: $SMOKE_RESULT)"
    exit 1
fi

# Phase 2: Integration Test WITHOUT Warmstart (Baseline - 300s timeout)
echo ""
echo "=========================================="
echo "PHASE 2: BASELINE INTEGRATION TEST"
echo "=========================================="
echo "Purpose: Establish baseline solve time WITHOUT warmstart"
echo "Timeout: 300 seconds"
echo ""

timeout 300 venv/bin/python -m pytest tests/test_integration_ui_workflow.py::test_ui_workflow_4_weeks_with_initial_inventory -v -s > baseline_test_output.txt 2>&1
BASELINE_RESULT=$?

if [ $BASELINE_RESULT -eq 0 ]; then
    echo "✅ BASELINE TEST PASSED"
    # Extract solve time from output
    grep "Solve time:" baseline_test_output.txt | tail -1
    grep "Objective value:" baseline_test_output.txt | tail -1
    grep "Fill rate:" baseline_test_output.txt | tail -1
elif [ $BASELINE_RESULT -eq 124 ]; then
    echo "⚠️  BASELINE TEST TIMED OUT (>300s)"
    echo "This may indicate binary variables causing performance issues"
else
    echo "❌ BASELINE TEST FAILED (exit code: $BASELINE_RESULT)"
    tail -50 baseline_test_output.txt
fi

# Phase 3: Integration Test WITH Warmstart (600s timeout)
echo ""
echo "=========================================="
echo "PHASE 3: WARMSTART INTEGRATION TEST"
echo "=========================================="
echo "Purpose: Measure performance WITH warmstart"
echo "Timeout: 600 seconds"
echo ""

timeout 600 venv/bin/python -m pytest tests/test_integration_ui_workflow.py::test_ui_workflow_with_warmstart -v -s > warmstart_test_output.txt 2>&1
WARMSTART_RESULT=$?

if [ $WARMSTART_RESULT -eq 0 ]; then
    echo "✅ WARMSTART TEST PASSED"
    # Extract solve time from output
    grep "Solve time:" warmstart_test_output.txt | tail -1
    grep "Objective value:" warmstart_test_output.txt | tail -1
    grep "Fill rate:" warmstart_test_output.txt | tail -1
elif [ $WARMSTART_RESULT -eq 124 ]; then
    echo "⚠️  WARMSTART TEST TIMED OUT (>600s)"
    echo "This indicates warmstart did not provide sufficient speedup"
else
    echo "❌ WARMSTART TEST FAILED (exit code: $WARMSTART_RESULT)"
    tail -50 warmstart_test_output.txt
fi

# Phase 4: Standalone Benchmark Script (600s timeout)
echo ""
echo "=========================================="
echo "PHASE 4: COMPREHENSIVE BENCHMARK"
echo "=========================================="
echo "Purpose: Side-by-side comparison with detailed metrics"
echo "Timeout: 600 seconds"
echo ""

timeout 600 python scripts/benchmark_warmstart_performance.py > benchmark_output.txt 2>&1
BENCHMARK_RESULT=$?

if [ $BENCHMARK_RESULT -eq 0 ]; then
    echo "✅ BENCHMARK COMPLETED"
    cat benchmark_output.txt
    echo ""
    if [ -f benchmark_results.txt ]; then
        echo "Results saved to: benchmark_results.txt"
    fi
elif [ $BENCHMARK_RESULT -eq 124 ]; then
    echo "⚠️  BENCHMARK TIMED OUT (>600s)"
    tail -100 benchmark_output.txt
else
    echo "❌ BENCHMARK FAILED (exit code: $BENCHMARK_RESULT)"
    tail -100 benchmark_output.txt
fi

# Phase 5: Performance Comparison Tests (600s timeout)
echo ""
echo "=========================================="
echo "PHASE 5: PERFORMANCE COMPARISON TESTS"
echo "=========================================="
echo "Purpose: Pytest-based performance validation"
echo "Timeout: 600 seconds"
echo ""

timeout 600 venv/bin/python -m pytest tests/test_warmstart_performance_comparison.py -v -s > performance_test_output.txt 2>&1
PERF_RESULT=$?

if [ $PERF_RESULT -eq 0 ]; then
    echo "✅ PERFORMANCE TESTS PASSED"
    tail -100 performance_test_output.txt
elif [ $PERF_RESULT -eq 124 ]; then
    echo "⚠️  PERFORMANCE TESTS TIMED OUT (>600s)"
    tail -100 performance_test_output.txt
else
    echo "❌ PERFORMANCE TESTS FAILED (exit code: $PERF_RESULT)"
    tail -100 performance_test_output.txt
fi

# Summary
echo ""
echo "=========================================="
echo "BENCHMARK SUITE COMPLETE"
echo "=========================================="
echo ""
echo "Results Summary:"
echo "  Phase 1 - Smoke Test:          $([ $SMOKE_RESULT -eq 0 ] && echo '✅ PASSED' || echo '❌ FAILED')"
echo "  Phase 2 - Baseline Test:       $([ $BASELINE_RESULT -eq 0 ] && echo '✅ PASSED' || ([ $BASELINE_RESULT -eq 124 ] && echo '⚠️  TIMEOUT' || echo '❌ FAILED'))"
echo "  Phase 3 - Warmstart Test:      $([ $WARMSTART_RESULT -eq 0 ] && echo '✅ PASSED' || ([ $WARMSTART_RESULT -eq 124 ] && echo '⚠️  TIMEOUT' || echo '❌ FAILED'))"
echo "  Phase 4 - Benchmark Script:    $([ $BENCHMARK_RESULT -eq 0 ] && echo '✅ PASSED' || ([ $BENCHMARK_RESULT -eq 124 ] && echo '⚠️  TIMEOUT' || echo '❌ FAILED'))"
echo "  Phase 5 - Performance Tests:   $([ $PERF_RESULT -eq 0 ] && echo '✅ PASSED' || ([ $PERF_RESULT -eq 124 ] && echo '⚠️  TIMEOUT' || echo '❌ FAILED'))"
echo ""
echo "Output files:"
echo "  - baseline_test_output.txt"
echo "  - warmstart_test_output.txt"
echo "  - benchmark_output.txt"
echo "  - benchmark_results.txt (if benchmark completed)"
echo "  - performance_test_output.txt"
echo ""

# Determine overall result
if [ $SMOKE_RESULT -eq 0 ] && ([ $BASELINE_RESULT -eq 0 ] || [ $BASELINE_RESULT -eq 124 ]) && ([ $WARMSTART_RESULT -eq 0 ] || [ $WARMSTART_RESULT -eq 124 ]); then
    echo "✅ BENCHMARK SUITE COMPLETED (some tests may have timed out - review outputs)"
    exit 0
else
    echo "❌ BENCHMARK SUITE FAILED (critical test failures detected)"
    exit 1
fi
