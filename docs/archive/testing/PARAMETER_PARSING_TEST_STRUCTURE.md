# Parameter Parsing Test Structure

## Test Architecture

```
tests/test_parameter_parsing.py (19 tests)
│
├─── TestManufacturingOverheadParsing (6 tests)
│    │
│    ├── test_parse_manufacturing_overhead_defaults
│    │   └── Verifies: startup=0.5, shutdown=0.5, changeover=1.0
│    │
│    ├── test_parse_manufacturing_overhead_custom_values
│    │   └── Verifies: Custom values (0.75, 0.25, 0.5) parsed correctly
│    │
│    ├── test_parse_manufacturing_overhead_missing_columns_legacy_compat
│    │   └── Verifies: Defaults applied when columns missing
│    │
│    └── test_parse_manufacturing_overhead_partial_columns
│        └── Verifies: Mix of custom and default values
│
├─── TestPalletStorageCostParsing (4 tests)
│    │
│    ├── test_parse_pallet_storage_costs_present
│    │   └── Verifies: fixed=0.0, frozen=0.5, ambient=0.2
│    │
│    ├── test_parse_pallet_storage_costs_missing_legacy_compat
│    │   └── Verifies: None values when pallet costs absent
│    │
│    ├── test_parse_pallet_storage_costs_precedence
│    │   └── Verifies: Both pallet and unit costs can coexist
│    │
│    └── test_parse_pallet_storage_costs_partial
│        └── Verifies: None for missing pallet parameters
│
├─── TestUnifiedModelParserOverhead (3 tests)
│    │
│    ├── test_unified_parser_overhead_parameters
│    │   └── Verifies: UnifiedModelParser parses overhead correctly
│    │
│    ├── test_unified_parser_overhead_missing_columns
│    │   └── Verifies: Defaults applied in UnifiedModelParser
│    │
│    └── test_unified_parser_overhead_only_for_manufacturing
│        └── Verifies: Overhead on non-manufacturing nodes handled
│
├─── TestIntegrationWithOptimizationModel (2 tests)
│    │
│    ├── test_node_capabilities_accessible_in_model
│    │   └── Verifies: node.capabilities.daily_startup_hours accessible
│    │
│    └── test_cost_structure_pallet_costs_accessible
│        └── Verifies: cost_structure.storage_cost_fixed_per_pallet accessible
│
├─── TestRealWorldDataFiles (2 tests)
│    │
│    ├── test_parse_real_network_config_file
│    │   └── Verifies: Actual Network_Config.xlsx parses successfully
│    │
│    └── test_parse_real_cost_parameters
│        └── Verifies: Actual cost parameters parse successfully
│
└─── TestErrorHandling (2 tests)
     │
     ├── test_missing_production_rate_for_manufacturing
     │   └── Verifies: Clear error when production_rate missing
     │
     └── test_invalid_overhead_values_rejected
         └── Verifies: Negative overhead values rejected
```

## Test Coverage Map

```
┌─────────────────────────────────────────────────────────────────┐
│ Manufacturing Overhead Parameters                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Excel File (Locations sheet)                                  │
│  ┌───────────────────────────────────────────────────┐        │
│  │ id | name | type | daily_startup_hours | ...      │        │
│  │ 6122 | Mfg | manufacturing | 0.5 | ...            │        │
│  └───────────────────────────────────────────────────┘        │
│                          ↓                                      │
│  ExcelParser.parse_locations()                                 │
│  ┌───────────────────────────────────────────────────┐        │
│  │ Lines 226-228: Overhead parameter parsing         │        │
│  │   daily_startup_hours = row.get(..., 0.5)         │        │
│  │   daily_shutdown_hours = row.get(..., 0.5)        │        │
│  │   default_changeover_hours = row.get(..., 1.0)    │        │
│  └───────────────────────────────────────────────────┘        │
│                          ↓                                      │
│  ManufacturingSite Model                                       │
│  ┌───────────────────────────────────────────────────┐        │
│  │ daily_startup_hours: float = 0.5                  │        │
│  │ daily_shutdown_hours: float = 0.5                 │        │
│  │ default_changeover_hours: float = 1.0             │        │
│  └───────────────────────────────────────────────────┘        │
│                          ↓                                      │
│  UnifiedNode.capabilities                                      │
│  ┌───────────────────────────────────────────────────┐        │
│  │ NodeCapabilities(                                  │        │
│  │   daily_startup_hours=0.5,                         │        │
│  │   daily_shutdown_hours=0.5,                        │        │
│  │   default_changeover_hours=1.0                     │        │
│  │ )                                                  │        │
│  └───────────────────────────────────────────────────┘        │
│                          ↓                                      │
│  UnifiedNodeModel (lines 1762-1764, 1951-1953)                │
│  ┌───────────────────────────────────────────────────┐        │
│  │ startup = node.capabilities.daily_startup_hours    │        │
│  │ shutdown = node.capabilities.daily_shutdown_hours  │        │
│  │ changeover = node.capabilities.default_changeover  │        │
│  └───────────────────────────────────────────────────┘        │
│                                                                 │
│  TESTED BY: TestManufacturingOverheadParsing (6 tests)        │
│  TESTED BY: TestUnifiedModelParserOverhead (3 tests)          │
│  TESTED BY: TestIntegrationWithOptimizationModel (1 test)     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Pallet-Based Storage Costs                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Excel File (CostParameters sheet)                             │
│  ┌───────────────────────────────────────────────────┐        │
│  │ cost_type | value                                  │        │
│  │ storage_cost_fixed_per_pallet | 0.0                │        │
│  │ storage_cost_per_pallet_day_frozen | 0.5           │        │
│  │ storage_cost_per_pallet_day_ambient | 0.2          │        │
│  └───────────────────────────────────────────────────┘        │
│                          ↓                                      │
│  ExcelParser.parse_cost_structure()                            │
│  ┌───────────────────────────────────────────────────┐        │
│  │ Lines 434-437: Pallet cost parsing                 │        │
│  │   storage_cost_fixed_per_pallet = cost_dict.get()  │        │
│  │   storage_cost_per_pallet_day_frozen = ...         │        │
│  │   storage_cost_per_pallet_day_ambient = ...        │        │
│  └───────────────────────────────────────────────────┘        │
│                          ↓                                      │
│  CostStructure Model                                           │
│  ┌───────────────────────────────────────────────────┐        │
│  │ storage_cost_fixed_per_pallet: Optional[float]     │        │
│  │ storage_cost_per_pallet_day_frozen: Optional[float]│        │
│  │ storage_cost_per_pallet_day_ambient: Optional[float]│       │
│  └───────────────────────────────────────────────────┘        │
│                          ↓                                      │
│  UnifiedNodeModel (storage cost section)                       │
│  ┌───────────────────────────────────────────────────┐        │
│  │ if cost_structure.storage_cost_fixed_per_pallet:   │        │
│  │   # Create integer pallet_count variables          │        │
│  │   # Enforce ceiling: pallet_count * 320 >= qty     │        │
│  │   # Cost: pallet_count * pallet_cost_rate          │        │
│  └───────────────────────────────────────────────────┘        │
│                                                                 │
│  TESTED BY: TestPalletStorageCostParsing (4 tests)            │
│  TESTED BY: TestIntegrationWithOptimizationModel (1 test)     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Test Data Flow

```
Test Execution Flow:
═══════════════════

1. Create Temporary Excel File
   ┌────────────────────────────────┐
   │ pd.DataFrame([...])            │
   │ pd.ExcelWriter(tmp_path/...)   │
   └────────────────────────────────┘
              ↓
2. Parse with Parser
   ┌────────────────────────────────┐
   │ ExcelParser(test_file)         │
   │ parser.parse_locations()       │
   │ parser.parse_cost_structure()  │
   └────────────────────────────────┘
              ↓
3. Extract Parsed Values
   ┌────────────────────────────────┐
   │ mfg.daily_startup_hours        │
   │ costs.storage_cost_fixed...    │
   └────────────────────────────────┘
              ↓
4. Assert Expected Values
   ┌────────────────────────────────┐
   │ assert value == expected       │
   │ assert field is None (missing) │
   │ assert isinstance(...)         │
   └────────────────────────────────┘
```

## Test Scenarios Matrix

```
┌──────────────────────────┬──────────┬──────────┬──────────┐
│ Scenario                 │ Overhead │ Pallet   │ Status   │
│                          │ Params   │ Costs    │          │
├──────────────────────────┼──────────┼──────────┼──────────┤
│ All present (defaults)   │    ✓     │    ✓     │ TESTED   │
│ All present (custom)     │    ✓     │    ✓     │ TESTED   │
│ All missing              │    ✓     │    ✓     │ TESTED   │
│ Partial present          │    ✓     │    ✓     │ TESTED   │
│ Invalid values           │    ✓     │    -     │ TESTED   │
│ Non-manufacturing node   │    ✓     │    -     │ TESTED   │
│ Real-world file          │    ✓     │    ✓     │ TESTED   │
│ Both pallet & unit costs │    -     │    ✓     │ TESTED   │
└──────────────────────────┴──────────┴──────────┴──────────┘

Legend:
  ✓ = Test scenario covered
  - = Not applicable
```

## Backward Compatibility Matrix

```
┌─────────────────────────┬──────────────┬──────────────┐
│ File Version            │ Overhead     │ Pallet Costs │
├─────────────────────────┼──────────────┼──────────────┤
│ Legacy (pre-2025-10-17) │ Defaults     │ None (unit)  │
│ New (post-2025-10-17)   │ From Excel   │ From Excel   │
│ Mixed (partial)         │ Mixed/Def    │ Partial/None │
└─────────────────────────┴──────────────┴──────────────┘

All scenarios tested and working! ✅
```

## Test Dependencies

```
test_parameter_parsing.py
│
├── pytest                  (testing framework)
├── pandas                  (Excel I/O, DataFrame)
├── tempfile               (temporary file creation)
├── pathlib                (file path handling)
│
├── src.parsers
│   ├── excel_parser       (ExcelParser class)
│   └── unified_model_parser (UnifiedModelParser class)
│
└── src.models
    ├── manufacturing      (ManufacturingSite)
    ├── location          (Location, LocationType, StorageMode)
    ├── cost_structure    (CostStructure)
    └── unified_node      (UnifiedNode, NodeCapabilities)
```

## Quick Reference Commands

```bash
# Run all parameter parsing tests
pytest tests/test_parameter_parsing.py -v

# Run specific test class
pytest tests/test_parameter_parsing.py::TestManufacturingOverheadParsing -v

# Run with output visible
pytest tests/test_parameter_parsing.py -v -s

# Run with coverage
pytest tests/test_parameter_parsing.py --cov=src/parsers --cov-report=term-missing

# Validate syntax
python validate_tests.py

# Run integration test (verify no regressions)
pytest tests/test_integration_ui_workflow.py -v
```

## Test Execution Timeline

```
Expected Test Execution:
═══════════════════════

Total Time: < 10 seconds

Phase 1: Manufacturing Overhead Tests (6 tests)
├─ Create temp Excel files    [0.5s]
├─ Parse with ExcelParser     [0.5s]
├─ Assert values              [0.1s]
└─ Cleanup                    [0.1s]
                              ─────
                              ~1.2s

Phase 2: Pallet Cost Tests (4 tests)
├─ Create temp Excel files    [0.3s]
├─ Parse with ExcelParser     [0.3s]
├─ Assert values              [0.1s]
└─ Cleanup                    [0.1s]
                              ─────
                              ~0.8s

Phase 3: UnifiedModelParser Tests (3 tests)
├─ Create temp Excel files    [0.5s]
├─ Parse with UnifiedParser   [0.5s]
├─ Assert values              [0.1s]
└─ Cleanup                    [0.1s]
                              ─────
                              ~1.2s

Phase 4: Integration Tests (2 tests)
├─ Create temp Excel files    [0.3s]
├─ Parse and verify access    [0.3s]
└─ Cleanup                    [0.1s]
                              ─────
                              ~0.7s

Phase 5: Real-World Tests (2 tests)
├─ Parse Network_Config.xlsx  [0.5s]
├─ Verify and print values    [0.1s]
                              ─────
                              ~0.6s

Phase 6: Error Handling Tests (2 tests)
├─ Create invalid data        [0.2s]
├─ Assert errors raised       [0.1s]
                              ─────
                              ~0.3s

                    TOTAL: ~4.8s
```

## Success Indicators

```
✅ All 19 tests pass
✅ Execution time < 10 seconds
✅ No import errors
✅ No syntax errors
✅ Real-world tests print actual values
✅ Integration test passes (no regressions)
✅ Backward compatibility validated
✅ Error handling verified
```

## File Locations

```
Repository: /home/sverzijl/planning_latest/

Tests:
  tests/test_parameter_parsing.py              (PRIMARY TEST FILE)
  tests/README_PARAMETER_PARSING_TESTS.md      (Quick start guide)

Documentation:
  TEST_PARAMETER_PARSING_SUMMARY.md            (Detailed breakdown)
  PARAMETER_PARSING_TEST_DELIVERABLES.md       (Deliverables list)
  PARAMETER_PARSING_TEST_STRUCTURE.md          (This file)

Utilities:
  validate_tests.py                            (Syntax validator)
  run_parameter_tests.py                       (Test runner)

Source Code (tested):
  src/parsers/excel_parser.py                  (Lines 226-228, 434-437)
  src/parsers/unified_model_parser.py          (Lines 54-56)
  src/models/unified_node.py                   (Lines 46-60)
  src/models/cost_structure.py                 (Lines 98-112)
```
