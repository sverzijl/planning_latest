# Daily Snapshot UI Integration Test Suite

## Overview

This document describes the comprehensive integration test suite for the Daily Snapshot UI component, which validates the integration between the UI layer (`ui/components/daily_snapshot.py`) and the backend snapshot generator (`src/analysis/daily_snapshot.py`).

## Test File Location

`/home/sverzijl/planning_latest/tests/test_daily_snapshot_ui_integration.py`

## Purpose

The test suite validates that the UI component correctly:
1. Calls the backend `DailySnapshotGenerator`
2. Converts backend dataclasses to UI-friendly dict format
3. Displays accurate inventory, shipment, and demand data
4. Respects planning horizons and filters historical data
5. Handles edge cases and missing data gracefully

## Test Coverage Summary

### Total Tests: 20

#### Test Category 1: Multi-Location Inventory Display (3 tests)
- ✅ `test_multi_location_inventory_display` - Verifies inventory appears at all locations (manufacturing, hub, destination) with correct quantities
- ✅ `test_manufacturing_inventory_decreases_after_shipment` - Confirms manufacturing inventory decreases after shipments depart
- ✅ `test_hub_inventory_increases_after_arrival` - Validates hub inventory increases when shipments arrive

#### Test Category 2: In-Transit Detection (4 tests)
- ✅ `test_in_transit_detection` - Verifies in-transit shipments are correctly identified with proper origin, destination, quantity, and days_in_transit
- ✅ `test_no_in_transit_before_departure` - Ensures shipments not yet departed don't appear in transit
- ✅ `test_no_in_transit_after_arrival` - Confirms shipments already arrived don't appear in transit
- ✅ `test_multi_leg_in_transit` - Tests in-transit detection on second leg of multi-leg routes

#### Test Category 3: Outflow Tracking (2 tests)
- ✅ `test_outflow_tracking_departures` - Validates departure outflows appear with correct type, location, product, and quantity
- ✅ `test_outflow_tracking_demand` - Verifies demand outflows appear when deliveries occur

#### Test Category 4: Demand Satisfaction Accuracy (2 tests)
- ✅ `test_demand_satisfaction_partial` - Tests partial fulfillment scenarios (demand > supplied)
- ✅ `test_demand_satisfaction_status` - Validates status indicators (✅ Met vs ⚠️ Short)

#### Test Category 5: Planning Horizon Respect (2 tests)
- ✅ `test_planning_horizon_respect` - Ensures date range starts at `schedule_start_date`, not historical production dates
- ✅ `test_date_range_filters_historical_production` - Confirms historical production dates are filtered from date range

#### Test Category 6: Edge Cases (6 tests)
- ✅ `test_empty_forecast` - Handles empty forecast (no demand data)
- ✅ `test_no_shipments` - Works with production only (no shipments)
- ✅ `test_missing_location_in_dict` - Gracefully handles missing locations in locations_dict
- ✅ `test_snapshot_before_production` - Correctly shows zero inventory before production starts
- ✅ `test_snapshot_after_all_deliveries` - Properly displays final inventory after all deliveries complete
- ✅ `test_snapshot_data_types` - Validates all dict fields have correct data types (dict, list, float, date, str)

#### Test Category 7: Quantity Validation (1 test)
- ✅ `test_exact_quantities` - Verifies exact quantity calculations, not just presence

## Test Data

### Locations
- **6122** - Manufacturing Site (MANUFACTURING, BOTH storage modes, 100,000 capacity)
- **6125** - Hub VIC (STORAGE, BOTH storage modes, 50,000 capacity)
- **6103** - Breadroom VIC (BREADROOM, AMBIENT storage mode, 5,000 capacity)

### Products
- **176283** - Test product 1
- **176284** - Test product 2

### Production Schedule
- **Base Date**: October 15, 2025
- **BATCH-001**: 320 units of 176283, produced Oct 15
- **BATCH-002**: 640 units of 176284, produced Oct 15
- **Total Production**: 960 units

### Shipments
- **Multi-leg route**: 6122 → 6125 (1 day) → 6103 (1 day) = 2 days total transit
- **SHIP-001**: 320 units of 176283, departs Oct 16, arrives Oct 18
- **SHIP-002**: 200 units of 176284, departs Oct 16, arrives Oct 18 (partial fulfillment)

### Forecast Demand (Oct 18)
- **6103, 176283**: 320 units (fully satisfied)
- **6103, 176284**: 640 units (partially satisfied - only 200 supplied)

## Key Test Scenarios

### Scenario 1: Inventory Flow Through Network
1. **Oct 15 (Production)**: 960 units at 6122 manufacturing
2. **Oct 16 (Departure)**: 520 units depart 6122, 440 remain
3. **Oct 17 (Hub Arrival)**: 520 units arrive at 6125 hub
4. **Oct 17 (Hub Departure)**: 520 units depart 6125
5. **Oct 18 (Final Delivery)**: 520 units arrive at 6103 destination

### Scenario 2: In-Transit Tracking
- **Oct 16**: In transit on first leg (6122 → 6125), days_in_transit = 0
- **Oct 17**: In transit on second leg (6125 → 6103), days_in_transit = 0
- **Oct 15**: Not in transit (not yet departed)
- **Oct 19**: Not in transit (already arrived)

### Scenario 3: Demand Satisfaction
- **Product 176283**: Demand 320, Supplied 320, Status ✅ Met
- **Product 176284**: Demand 640, Supplied 200, Status ⚠️ Short 440

## Technical Implementation

### Streamlit Mocking Strategy
```python
# Mock streamlit module before importing UI components
sys.modules['streamlit'] = MagicMock()

# Mock session state for forecast
mock_session_state = {'forecast': forecast}
with patch('streamlit.session_state', mock_session_state):
    snapshot = _generate_snapshot(...)
```

### Helper Function
```python
def generate_snapshot_with_forecast(...) -> Dict:
    """Generate snapshot by mocking Streamlit session state with forecast."""
    mock_session_state = {'forecast': forecast}
    with patch('streamlit.session_state', mock_session_state):
        return _generate_snapshot(...)
```

### Mock Route Classes
```python
@dataclass
class MockRouteLeg:
    from_location_id: str
    to_location_id: str
    transit_days: int
    transport_mode: str = "ambient"

@dataclass
class MockRoute:
    route_legs: List[MockRouteLeg]

    @property
    def total_transit_days(self) -> int:
        return sum(leg.transit_days for leg in self.route_legs)
```

## Issues Verified as Fixed

The test suite confirms the following UI integration issues are resolved:

### ✅ Issue 1: Multi-Location Inventory Display
- **Problem**: UI only showed inventory at manufacturing (6122)
- **Fix**: Now displays inventory at all locations (6122, 6125, 6103)
- **Tests**: `test_multi_location_inventory_display`, `test_hub_inventory_increases_after_arrival`

### ✅ Issue 2: In-Transit Shipments
- **Problem**: In-transit detection was incomplete
- **Fix**: Correctly identifies shipments in transit with origin, destination, and transit days
- **Tests**: `test_in_transit_detection`, `test_multi_leg_in_transit`

### ✅ Issue 3: Outflow Departures
- **Problem**: Departure outflows were missing
- **Fix**: Now shows all departure events with correct location and destination
- **Tests**: `test_outflow_tracking_departures`

### ✅ Issue 4: Demand Satisfaction Accuracy
- **Problem**: Supplied quantity didn't match actual shipment deliveries
- **Fix**: Accurately tracks supplied vs demand quantities
- **Tests**: `test_demand_satisfaction_partial`, `test_demand_satisfaction_status`

### ✅ Issue 5: Planning Horizon Respect
- **Problem**: Date range included pre-planning historical dates
- **Fix**: Date range now starts at `schedule_start_date`
- **Tests**: `test_planning_horizon_respect`, `test_date_range_filters_historical_production`

## Running the Tests

### Run All Integration Tests
```bash
pytest tests/test_daily_snapshot_ui_integration.py -v
```

### Run Specific Test Category
```bash
# Multi-location inventory tests
pytest tests/test_daily_snapshot_ui_integration.py::test_multi_location_inventory_display -v

# In-transit detection tests
pytest tests/test_daily_snapshot_ui_integration.py::test_in_transit_detection -v

# Demand satisfaction tests
pytest tests/test_daily_snapshot_ui_integration.py::test_demand_satisfaction_partial -v
```

### Run with Shell Script
```bash
bash run_ui_integration_tests.sh
```

## Assertions and Validations

### Data Type Validations
- Top-level dict contains: date (date), total_inventory (float), in_transit_total (float), production_total (float), demand_total (float)
- Nested structures: location_inventory (dict), in_transit_shipments (list), production_batches (list), inflows (list), outflows (list), demand_satisfaction (list)

### Quantity Validations
- Exact values checked (not just presence)
- Conservation of mass: production = shipments + remaining inventory
- Flow balance: inflows and outflows correctly account for all movements

### Status Validations
- Demand satisfaction status: "✅ Met" when supplied >= demand
- Demand satisfaction status: "⚠️ Short {shortage}" when supplied < demand

## Dependencies

### Required Imports
- `pytest` - Testing framework
- `unittest.mock` - Mocking utilities (MagicMock, patch)
- `datetime` - Date handling
- `typing` - Type hints
- `dataclasses` - Mock data structures

### Project Modules
- `ui.components.daily_snapshot` - UI functions (`_generate_snapshot`, `_get_date_range`)
- `src.analysis.daily_snapshot` - Backend generator (`DailySnapshotGenerator`)
- `src.models.*` - Data models (Location, ProductionBatch, Shipment, Forecast, etc.)
- `src.production.scheduler` - Production schedule (`ProductionSchedule`)

## Success Criteria

All 20 tests must pass to confirm:
1. ✅ UI correctly integrates with backend generator
2. ✅ Data transformation from dataclasses to UI dicts works properly
3. ✅ All 5 identified issues are fixed
4. ✅ Edge cases are handled gracefully
5. ✅ Data types and quantities are accurate

## Maintenance Notes

### When to Update Tests
- **New UI features**: Add tests for new snapshot data fields
- **Backend changes**: Update mock structures if backend dataclasses change
- **Route logic changes**: Update MockRoute if route model changes
- **New locations**: Add to sample_locations fixture if testing new network configurations

### Future Enhancements
- Add tests for frozen/thawed state transitions
- Test shelf life calculations in snapshot
- Add performance tests for large datasets
- Test concurrent snapshot generation
- Add visual regression tests for UI rendering

## Related Files

- **Source Code**: `/home/sverzijl/planning_latest/ui/components/daily_snapshot.py`
- **Backend**: `/home/sverzijl/planning_latest/src/analysis/daily_snapshot.py`
- **Backend Tests**: `/home/sverzijl/planning_latest/tests/test_daily_snapshot.py`
- **Test Runner**: `/home/sverzijl/planning_latest/run_ui_integration_tests.sh`

## Contact

For questions about these tests or the Daily Snapshot UI integration, refer to:
- Project documentation: `CLAUDE.md`
- Test implementation: `tests/test_daily_snapshot_ui_integration.py`
- UI component: `ui/components/daily_snapshot.py`
