#!/usr/bin/env python3
"""
Diagnostic script to trace why model produces zero production.

Adds instrumentation at each component boundary to find where issue occurs.
"""

from datetime import date, timedelta
from pathlib import Path
from pyomo.environ import value

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel

print("="*80)
print("DIAGNOSTIC: Zero Production Investigation")
print("="*80)

# Component 1: Load Data
print("\n[1] LOADING DATA")
print("-" * 80)

base_dir = Path("data/examples")
parser = MultiFileParser(
    network_file=base_dir / "Network_Config.xlsx",
    forecast_file=base_dir / "Gluten Free Forecast - Latest.xlsm",
    inventory_file=None  # Skip inventory for simplicity
)

forecast, locations, routes, labor_cal, trucks, costs = parser.parse_all()
products = parser.parse_products()

print(f"✓ Forecast entries: {len(forecast.entries)}")
print(f"✓ Locations loaded: {len(locations)}")
print(f"✓ Routes loaded: {len(routes)}")
print(f"✓ Products loaded: {len(products)}")
print(f"  Product IDs: {list(products.keys())}")

# Component 2: Verify Product Data
print("\n[2] PRODUCT DATA VERIFICATION")
print("-" * 80)

print("Products with units_per_mix:")
for prod_id, product in products.items():
    print(f"  {prod_id}: {product.units_per_mix} units/mix (name={product.name})")

# Component 3: Verify Forecast Data in Planning Period
print("\n[3] FORECAST DATA FOR PLANNING PERIOD")
print("-" * 80)

start_date = date(2025, 10, 16)  # First day of forecast
end_date = start_date + timedelta(days=6)  # 1 week

print(f"Planning period: {start_date} to {end_date}")

# Filter forecast to planning period
period_demand = [e for e in forecast.entries
                 if start_date <= e.forecast_date <= end_date]

print(f"Forecast entries in period: {len(period_demand)}")

# Group by product
from collections import defaultdict
demand_by_product = defaultdict(float)
for entry in period_demand:
    demand_by_product[entry.product_id] += entry.quantity

print(f"\nDemand by product:")
for prod_id, qty in sorted(demand_by_product.items()):
    print(f"  {prod_id}: {qty:,.0f} units")

total_demand = sum(demand_by_product.values())
print(f"\nTotal demand: {total_demand:,.0f} units")

# Component 4: Check Product ID Matching
print("\n[4] PRODUCT ID MATCHING")
print("-" * 80)

forecast_products = set(demand_by_product.keys())
model_products = set(products.keys())

print(f"Product IDs in forecast: {sorted(forecast_products)}")
print(f"Product IDs in model: {sorted(model_products)}")
print(f"Intersection: {sorted(forecast_products & model_products)}")
print(f"Only in forecast: {sorted(forecast_products - model_products)}")
print(f"Only in model: {sorted(model_products - forecast_products)}")

if len(forecast_products & model_products) == 0:
    print("\n❌ CRITICAL: NO PRODUCT ID OVERLAP!")
    print("   Forecast and model have completely different product IDs.")
    print("   This explains zero production - demand for products that don't exist in model!")
else:
    print(f"\n✓ {len(forecast_products & model_products)} products match")

# Component 5: Convert to Unified Format
print("\n[5] CONVERTING TO UNIFIED FORMAT")
print("-" * 80)

from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter

converter = LegacyToUnifiedConverter()
unified_nodes = converter.convert_locations_to_nodes(locations)
unified_routes = converter.convert_routes(routes)

print(f"✓ Converted {len(locations)} locations to {len(unified_nodes)} nodes")
print(f"✓ Converted {len(routes)} routes to {len(unified_routes)} unified routes")

# Component 6: Create Model
print("\n[6] MODEL CREATION")
print("-" * 80)

model = UnifiedNodeModel(
    nodes=unified_nodes,
    routes=unified_routes,
    forecast=forecast,
    products=products,
    labor_calendar=labor_cal,
    cost_structure=costs,
    start_date=start_date,
    end_date=end_date,
    truck_schedules=trucks,
    use_batch_tracking=True,
    allow_shortages=True  # Allow shortcuts to see what solver does
)

print("✓ Model created successfully")

# Component 7: Build Model
print("\n[7] MODEL BUILD")
print("-" * 80)

model.build()

print(f"✓ Model built")
print(f"  Manufacturing nodes: {len(model.manufacturing_nodes)}")
print(f"  Products in model: {model.product_ids}")
print(f"  Dates: {len(model.dates)}")

# Check if mix_count variable exists
if hasattr(model.model, 'mix_count'):
    print(f"✓ mix_count variable exists")
    # Count mix_count variables
    mix_count_vars = len([v for v in model.model.mix_count.values()])
    print(f"  mix_count variables: {mix_count_vars}")
else:
    print("❌ mix_count variable NOT FOUND")

# Check if production is Expression
from pyomo.environ import Expression
if hasattr(model.model, 'production'):
    is_expr = isinstance(model.model.production, Expression)
    print(f"  production is Expression: {is_expr}")
    if not is_expr:
        print(f"  production type: {type(model.model.production)}")
else:
    print("❌ production NOT FOUND")

# Component 8: Solve
print("\n[8] SOLVING MODEL")
print("-" * 80)

result = model.solve(
    solver='appsi_highs',
    time_limit=60,
    mip_gap=0.01,
    tee=False
)

print(f"✓ Solve completed")
print(f"  Status: {result.status}")
print(f"  Objective: ${result.objective_value:,.2f}")

# Component 9: Extract and Analyze Solution
print("\n[9] SOLUTION EXTRACTION")
print("-" * 80)

solution = model.extract_solution(model.model)

print(f"Solution keys: {list(solution.keys())}")

# Check mix_counts
if 'mix_counts' in solution:
    print(f"\n✓ mix_counts in solution")
    print(f"  Number of mix production events: {len(solution['mix_counts'])}")

    if len(solution['mix_counts']) > 0:
        print("\n  Sample mix_counts:")
        for i, ((node, prod, dt), data) in enumerate(list(solution['mix_counts'].items())[:5]):
            print(f"    {dt} | {prod} | mixes={data['mix_count']}, units={data['units']}")
    else:
        print("  ❌ mix_counts is EMPTY")
else:
    print("❌ mix_counts NOT in solution")

# Check production_by_date_product
if 'production_by_date_product' in solution:
    print(f"\n✓ production_by_date_product in solution")
    print(f"  Number of production events: {len(solution['production_by_date_product'])}")

    if len(solution['production_by_date_product']) > 0:
        print("\n  Sample production:")
        for i, ((dt, prod), qty) in enumerate(list(solution['production_by_date_product'].items())[:5]):
            print(f"    {dt} | {prod} | {qty:.0f} units")
    else:
        print("  ❌ production_by_date_product is EMPTY")
else:
    print("❌ production_by_date_product NOT in solution")

# Check total_mixes
total_mixes = solution.get('total_mixes', 0)
print(f"\nTotal mixes: {total_mixes}")

# Check total_production_quantity
total_prod = solution.get('total_production_quantity', 0)
print(f"Total production: {total_prod:,.0f} units")

# Component 10: Directly Query Model Variables
print("\n[10] DIRECT VARIABLE INSPECTION")
print("-" * 80)

print("\nDirectly querying mix_count variables:")
mix_count_nonzero = []
for node_id in model.manufacturing_nodes:
    for prod in model.model.products:
        for dt in model.model.dates:
            if (node_id, prod, dt) in model.model.mix_count:
                val = value(model.model.mix_count[node_id, prod, dt])
                if val > 0.01:
                    mix_count_nonzero.append((node_id, prod, dt, val))

print(f"Non-zero mix_count variables: {len(mix_count_nonzero)}")
if len(mix_count_nonzero) > 0:
    print("\nSample non-zero mix_counts:")
    for node, prod, dt, val in mix_count_nonzero[:10]:
        units_per_mix = products[prod].units_per_mix if prod in products else 0
        calc_units = val * units_per_mix
        print(f"  {dt} | {prod} | mix_count={val:.2f} → {calc_units:.0f} units (@ {units_per_mix} units/mix)")

print("\nDirectly evaluating production expression:")
prod_expr_nonzero = []
for node_id in model.manufacturing_nodes:
    for prod in model.model.products:
        for dt in model.model.dates:
            if (node_id, prod, dt) in model.model.production:
                val = value(model.model.production[node_id, prod, dt])
                if val > 0.01:
                    prod_expr_nonzero.append((node_id, prod, dt, val))

print(f"Non-zero production expression values: {len(prod_expr_nonzero)}")
if len(prod_expr_nonzero) > 0:
    print("\nSample non-zero production:")
    for node, prod, dt, val in prod_expr_nonzero[:10]:
        print(f"  {dt} | {prod} | {val:.0f} units")

# Component 11: Check Demand Satisfaction
print("\n[11] DEMAND SATISFACTION CHECK")
print("-" * 80)

if 'shortages' in solution:
    total_shortage = sum(solution['shortages'].values())
    print(f"Total shortages: {total_shortage:,.0f} units")

    if total_shortage > 0:
        print("\nSample shortages:")
        for key, val in list(solution['shortages'].items())[:5]:
            print(f"  {key}: {val:,.0f} units")

# Summary
print("\n" + "="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80)

if len(forecast_products & model_products) == 0:
    print("\n❌ ROOT CAUSE IDENTIFIED: Product ID mismatch")
    print("   Forecast has product IDs that don't exist in Products sheet")
    print("   Model cannot produce for products it doesn't know about!")
elif len(mix_count_nonzero) == 0:
    print("\n❌ ISSUE: mix_count variables are all zero")
    print("   Need to investigate why solver isn't producing")
elif len(prod_expr_nonzero) == 0:
    print("\n❌ ISSUE: production expression evaluates to zero despite non-zero mix_count")
    print("   Expression formula may be broken")
else:
    print(f"\n✓ Model has non-zero production: {len(prod_expr_nonzero)} production events")
    print("   Issue may be in extraction logic")
