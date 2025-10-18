#!/usr/bin/env python3
"""Check if the inventory balance equation has correct signs in the .lp file."""

from datetime import date, timedelta
from src.optimization.unified_node_model import UnifiedNodeModel
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure

# Set up minimal test case
day_1 = date(2025, 1, 1)
day_7 = date(2025, 1, 7)

# Create nodes
manufacturing = UnifiedNode(
    id='MFG',
    name='Manufacturing',
    capabilities=NodeCapabilities(
        can_manufacture=True,
        can_store=True,
        production_rate_per_hour=1400.0
    ),
    storage_mode=StorageMode.AMBIENT
)

breadroom = UnifiedNode(
    id='BR1',
    name='Breadroom 1',
    capabilities=NodeCapabilities(can_store=True, has_demand=True),
    storage_mode=StorageMode.AMBIENT
)

# Create route
route = UnifiedRoute(
    id='R1',
    origin_node_id='MFG',
    destination_node_id='BR1',
    transit_days=1.0,
    transport_mode=TransportMode.AMBIENT,
    cost_per_unit=0.5
)

# Create forecast: 1,000 units on day 7 ONLY
forecast = Forecast(
    name='Minimal Test',
    entries=[
        ForecastEntry(location_id='BR1', product_id='PROD1', forecast_date=day_7, quantity=1000.0)
    ]
)

# Labor calendar (allow production every day)
labor_days = []
for i in range(7):
    labor_days.append(
        LaborDay(
            date=day_1 + timedelta(days=i),
            fixed_hours=12.0,
            regular_rate=25.0,
            overtime_rate=35.0,
            is_fixed_day=True
        )
    )

labor_calendar = LaborCalendar(name='Test Calendar', days=labor_days)

# Cost structure
cost_structure = CostStructure(
    production_cost_per_unit=5.0,
    transport_cost_per_km=0.1,
    holding_cost_per_unit_per_day=0.01,
    shortage_penalty_per_unit=100.0
)

# Create model
model = UnifiedNodeModel(
    nodes=[manufacturing, breadroom],
    routes=[route],
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    start_date=day_1,
    end_date=day_7,
    truck_schedules=None,
    initial_inventory=None,
    use_batch_tracking=True,
    allow_shortages=True,
    enforce_shelf_life=True,
)

# Build model
pyomo_model = model.build_model()

# Write .lp file
pyomo_model.write('check_sign.lp', io_options={'symbolic_solver_labels': True})

print("\n" + "="*80)
print("CHECKING INVENTORY BALANCE EQUATION SIGNS")
print("="*80)

# Read and check the balance equation for BR1 on day 7
with open('check_sign.lp', 'r') as f:
    lines = f.readlines()

# Find the inventory balance constraint for BR1 on day 7
in_balance = False
balance_lines = []

for i, line in enumerate(lines):
    if 'inventory_balance_con' in line and 'BR1' in line and 'PROD1' in line and '2025_01_07' in line:
        # Found a balance constraint for BR1, PROD1 on day 7
        in_balance = True
        balance_lines.append(line.strip())
    elif in_balance:
        balance_lines.append(line.strip())
        if '=' in line or '<=' in line or '>=' in line:
            # End of constraint
            break

if balance_lines:
    print("\nInventory Balance Constraint (BR1, PROD1, Day 7):")
    print("-" * 80)
    for line in balance_lines:
        print(line)
    print("-" * 80)

    # Check for demand_from_cohort term
    demand_sign = None
    for line in balance_lines:
        if 'demand_from_cohort' in line:
            # Extract the coefficient
            parts = line.strip().split()
            for i, part in enumerate(parts):
                if 'demand_from_cohort' in part:
                    # Coefficient is the previous token
                    if i > 0:
                        coef = parts[i-1]
                        if coef == '+1':
                            demand_sign = 'POSITIVE (+1)'
                        elif coef == '-1':
                            demand_sign = 'NEGATIVE (-1)'
                        else:
                            demand_sign = coef
                    break

    print("\n" + "="*80)
    if demand_sign:
        if 'POSITIVE' in demand_sign:
            print("❌ BUG FOUND: demand_from_cohort has POSITIVE coefficient (+1)")
            print("   This means demand ADDS to inventory instead of subtracting!")
            print("   Expected: -1 demand_from_cohort (demand reduces inventory)")
            print("   Actual: +1 demand_from_cohort (demand increases inventory!)")
        elif 'NEGATIVE' in demand_sign:
            print("✓ CORRECT: demand_from_cohort has NEGATIVE coefficient (-1)")
            print("  Demand correctly reduces inventory")
        else:
            print(f"? Unexpected coefficient: {demand_sign}")
    else:
        print("⚠ Could not find demand_from_cohort term in constraint")
    print("="*80)
else:
    print("\n⚠ Could not find inventory balance constraint for BR1 on day 7")

# Also check a few other constraints to see the pattern
print("\n\nSearching for ALL demand_from_cohort terms in .lp file:")
print("-" * 80)
for i, line in enumerate(lines):
    if 'demand_from_cohort' in line and 'BR1' in line:
        # Show line with context
        print(f"Line {i}: {line.strip()}")
print("-" * 80)
