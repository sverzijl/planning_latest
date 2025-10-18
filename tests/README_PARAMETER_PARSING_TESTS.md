# Parameter Parsing Tests

## Overview

Comprehensive unit tests for new parameter parsing functionality added in the piecewise labor cost implementation (2025-10-17).

## What's Being Tested

### 1. Manufacturing Overhead Parameters
New parameters added to the **Locations sheet** for manufacturing capacity modeling:
- `daily_startup_hours` (default: 0.5h)
- `daily_shutdown_hours` (default: 0.5h)
- `default_changeover_hours` (default: 1.0h)

**Why these matter:**
- Critical for accurate labor cost calculation
- Used in UnifiedNodeModel to calculate total labor hours
- Previously hardcoded in optimization model
- Now configurable via Excel input

### 2. Pallet-Based Storage Costs
New parameters added to the **CostParameters sheet** for pallet-granular holding costs:
- `storage_cost_fixed_per_pallet` (one-time charge when pallet enters storage)
- `storage_cost_per_pallet_day_frozen` (daily cost per pallet in frozen storage)
- `storage_cost_per_pallet_day_ambient` (daily cost per pallet in ambient storage)

**Why these matter:**
- Enforces "partial pallets occupy full pallet space" business rule
- More accurate cost representation than unit-based costs
- Used in UnifiedNodeModel pallet-based holding cost constraints
- Coexists with legacy unit-based costs for backward compatibility

## Test File

**Location:** `tests/test_parameter_parsing.py`

**Test Count:** 19 tests across 6 test classes

## Test Classes

### TestManufacturingOverheadParsing
Tests for parsing overhead parameters via ExcelParser.parse_locations()

- ✅ Default values (0.5, 0.5, 1.0)
- ✅ Custom values
- ✅ Missing columns (backward compatibility)
- ✅ Partial columns
- ✅ Non-manufacturing locations

### TestPalletStorageCostParsing
Tests for parsing pallet costs via ExcelParser.parse_cost_structure()

- ✅ All pallet costs present
- ✅ All pallet costs missing (backward compatibility)
- ✅ Both pallet and unit costs present
- ✅ Partial pallet costs

### TestUnifiedModelParserOverhead
Tests for UnifiedModelParser.parse_nodes() overhead handling

- ✅ Overhead parameters parsed correctly
- ✅ Missing columns handled with defaults
- ✅ Overhead on non-manufacturing nodes

### TestIntegrationWithOptimizationModel
Tests verifying optimization model can access parsed parameters

- ✅ NodeCapabilities overhead accessible
- ✅ CostStructure pallet costs accessible

### TestRealWorldDataFiles
Tests using actual Network_Config.xlsx

- ✅ Parse real network config file
- ✅ Parse real cost parameters

### TestErrorHandling
Tests for proper error handling

- ✅ Missing production_rate raises error
- ✅ Invalid overhead values rejected

## Running the Tests

### Quick Start
```bash
# Run all parameter parsing tests
pytest tests/test_parameter_parsing.py -v

# Expected output: 19 passed
```

### With Output
```bash
# Run with print statements visible
pytest tests/test_parameter_parsing.py -v -s
```

### Specific Test Class
```bash
# Run only manufacturing overhead tests
pytest tests/test_parameter_parsing.py::TestManufacturingOverheadParsing -v
```

### Specific Test
```bash
# Run single test
pytest tests/test_parameter_parsing.py::TestManufacturingOverheadParsing::test_parse_manufacturing_overhead_defaults -v
```

### With Coverage
```bash
# Run with coverage report
pytest tests/test_parameter_parsing.py --cov=src/parsers --cov-report=term-missing
```

## Expected Results

### Success Criteria
- ✅ 19/19 tests pass
- ✅ Test execution time < 10 seconds
- ✅ Real-world tests parse Network_Config.xlsx successfully
- ✅ No import errors or syntax errors

### Real-World Test Output
The real-world tests print actual values from Network_Config.xlsx:

```
Manufacturing node overhead parameters:
  Startup: 0.5h
  Shutdown: 0.5h
  Changeover: 1.0h

Pallet-based costs present: True
  Fixed per pallet: $0.0
  Frozen per pallet/day: $0.5
  Ambient per pallet/day: $0.2
```

## Backward Compatibility

All new parameters are **optional** and have sensible defaults:

### Missing Overhead Columns
- Falls back to defaults: `startup=0.5, shutdown=0.5, changeover=1.0`
- No breaking changes to existing Excel files
- Explicitly tested in: `test_parse_manufacturing_overhead_missing_columns_legacy_compat`

### Missing Pallet Cost Rows
- Falls back to `None` (not used in optimization)
- Legacy unit-based costs still work
- Explicitly tested in: `test_parse_pallet_storage_costs_missing_legacy_compat`

## Integration with Optimization Model

The tests verify parameters are accessible exactly as the UnifiedNodeModel uses them:

### Overhead Parameters (UnifiedNodeModel lines 1762-1764, 1951-1953)
```python
startup_hours = node.capabilities.daily_startup_hours
shutdown_hours = node.capabilities.daily_shutdown_hours
changeover_hours = node.capabilities.default_changeover_hours
```

### Pallet Costs (UnifiedNodeModel storage cost section)
```python
fixed_cost = cost_structure.storage_cost_fixed_per_pallet
frozen_daily = cost_structure.storage_cost_per_pallet_day_frozen
ambient_daily = cost_structure.storage_cost_per_pallet_day_ambient
```

## Test Design Principles

1. **Isolation:** Each test creates temporary Excel files
2. **Independence:** Tests don't rely on each other
3. **Clarity:** Clear assertions with descriptive names
4. **Real-World:** Tests against actual Network_Config.xlsx
5. **Backward Compatibility:** Explicit tests for missing columns
6. **Error Handling:** Tests for invalid inputs

## Troubleshooting

### Test Failures

**Import errors:**
- Ensure virtual environment is activated: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

**File not found errors:**
- Real-world tests gracefully skip if Network_Config.xlsx not found
- Check path: `/home/sverzijl/planning_latest/data/examples/Network_Config.xlsx`

**Assertion failures:**
- Review test output to see expected vs actual values
- Check if Excel parsing logic changed
- Verify model field names match parser output

### Debugging

**Run single test with verbose output:**
```bash
pytest tests/test_parameter_parsing.py::TestManufacturingOverheadParsing::test_parse_manufacturing_overhead_defaults -v -s
```

**Check test file syntax:**
```bash
python validate_tests.py
```

**Run with debugger:**
```bash
pytest tests/test_parameter_parsing.py --pdb
```

## Related Documentation

- **Implementation:** `PIECEWISE_LABOR_COST_IMPLEMENTATION.md`
- **Test Summary:** `TEST_PARAMETER_PARSING_SUMMARY.md`
- **Excel Format:** `data/examples/EXCEL_TEMPLATE_SPEC.md`
- **Optimization Model:** `src/optimization/unified_node_model.py`

## Maintenance

### Adding New Parameters

When adding new parameters in the future:

1. **Update Model:** Add field to Pydantic model with default
2. **Update Parser:** Add parsing with `pd.notna()` check
3. **Add Tests:** Create test class in this file
4. **Test Pattern:**
   - Value present test
   - Value missing test (backward compat)
   - Invalid value test (error handling)
   - Integration test (optimization model access)

### Updating Tests

- Keep tests focused on parsing logic
- Don't test optimization model logic here
- Use temporary files (don't modify real data)
- Document expected values clearly

## Questions?

If you have questions about these tests:

1. Review test docstrings in `test_parameter_parsing.py`
2. Check implementation in `src/parsers/excel_parser.py`
3. Review model definitions in `src/models/`
4. See `TEST_PARAMETER_PARSING_SUMMARY.md` for detailed documentation

## Success!

If all tests pass, you've successfully validated:
- ✅ Manufacturing overhead parameters parse correctly
- ✅ Pallet-based storage costs parse correctly
- ✅ Backward compatibility is maintained
- ✅ Integration with optimization model works
- ✅ Error handling is proper
- ✅ Real-world data files are compatible

**Next step:** Run integration test to verify end-to-end optimization:
```bash
pytest tests/test_integration_ui_workflow.py -v
```
