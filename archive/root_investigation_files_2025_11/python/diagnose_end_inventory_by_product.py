"""
Diagnose end inventory by product to see if it's a product mix issue.

From MIP theory: If end inventory is concentrated in specific products
while those same products have shortages, it's a timing/positioning mismatch.
"""

from datetime import datetime, timedelta
from pyomo.core.base import value

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


# Solve
print("Solving...")
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [ForecastEntry(location_id=e.node_id, product_id=e.product_id,
                                  forecast_date=e.demand_date, quantity=e.quantity)
                   for e in validated.demand_entries]
forecast = Forecast(name="Test", entries=forecast_entries)

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)
products_dict = {p.id: p for p in validated.products}

horizon_days = 28
start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=horizon_days-1)).date()

model_builder = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    products=products_dict, start_date=start, end_date=end,
    truck_schedules=unified_truck_schedules,
    initial_inventory=validated.get_inventory_dict(),
    inventory_snapshot_date=validated.inventory_snapshot_date,
    allow_shortages=True, use_pallet_tracking=True, use_truck_pallet_tracking=True
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)
if not result.success:
    exit(1)

print("Solved!\n")
model = model_builder.model
solution = model_builder.extract_solution(model)

# Analyze by product
print("="*120)
print("END INVENTORY BY PRODUCT (MIP Analysis)")
print("="*120)

last_date = max(model.dates)

# Get end inventory by product
end_inv_by_product = {}
if hasattr(model, 'inventory'):
    for (node_id, prod, state, t) in model.inventory:
        if t == last_date:
            try:
                qty = value(model.inventory[node_id, prod, state, t])
                if qty > 0.01:
                    end_inv_by_product[prod] = end_inv_by_product.get(prod, 0) + qty
            except:
                pass

# Get shortage by product
shortage_by_product = {}
if hasattr(solution, 'shortages'):
    for (node, prod, t), qty in solution.shortages.items():
        shortage_by_product[prod] = shortage_by_product.get(prod, 0) + qty

# Get total production and demand by product
prod_by_product = {}
demand_by_product = {}

for prod in model.products:
    # Production
    prod_total = sum(
        value(model.production[node_id, p, t])
        for (node_id, p, t) in model.production
        if p == prod
    )
    prod_by_product[prod] = prod_total

    # Demand
    demand_total = sum(
        qty for (node, p, t), qty in model_builder.demand.items()
        if p == prod
    )
    demand_by_product[prod] = demand_total

# Display
print(f"\n{'Product':<40} {'Production':>12} {'Demand':>12} {'Shortage':>12} {'EndInv':>12} {'Waste%':>8}")
print("-"*120)

for prod in sorted(end_inv_by_product.keys(), key=lambda p: -end_inv_by_product[p]):
    production = prod_by_product.get(prod, 0)
    demand = demand_by_product.get(prod, 0)
    shortage = shortage_by_product.get(prod, 0)
    end_inv = end_inv_by_product.get(prod, 0)

    waste_pct = end_inv / production * 100 if production > 0 else 0

    print(f"{prod[:40]:<40} {production:>12,.0f} {demand:>12,.0f} {shortage:>12,.0f} {end_inv:>12,.0f} {waste_pct:>7.1f}%")

print("-"*120)
print(f"{'TOTAL':<40} {sum(prod_by_product.values()):>12,.0f} {sum(demand_by_product.values()):>12,.0f} {sum(shortage_by_product.values()):>12,.0f} {sum(end_inv_by_product.values()):>12,.0f}")

# Analysis
print(f"\n\n{'='*120}")
print(f"MIP ANALYSIS:")
print(f"{'='*120}")

print(f"\nPattern check:")
has_both = []
for prod in model.products:
    end_inv = end_inv_by_product.get(prod, 0)
    shortage = shortage_by_product.get(prod, 0)

    if end_inv > 100 and shortage > 100:
        has_both.append((prod, end_inv, shortage))

if len(has_both) > 0:
    print(f"\n❌ FOUND {len(has_both)} PRODUCTS WITH BOTH END INVENTORY AND SHORTAGE!")
    print(f"\nThis is economically irrational - model should reallocate:")
    for prod, inv, short in has_both:
        realloc = min(inv, short)
        savings = realloc * (13 - 10)  # waste - shortage
        print(f"  {prod[:35]:<35}: waste {inv:>8,.0f}, shortage {short:>8,.0f} → save ${savings:>8,.0f} by producing {realloc:,.0f} less")

    total_realloc_savings = sum(min(inv, short) * 3 for _, inv, short in has_both)
    print(f"\n  Total potential savings: ${total_realloc_savings:,.0f}")
    print(f"\n  ROOT CAUSE: Model is producing the RIGHT total but WRONG timing/location")
    print(f"  The goods end up at wrong place/time and become waste while demand goes unmet")

else:
    print(f"\n✓ No products have both waste and shortage")
    print(f"  End inventory and shortage are in DIFFERENT products")
    print(f"  This suggests model is optimizing correctly given constraints")

print(f"\n{'='*120}")
