"""
Trace disposal mechanism in constrained solution.

Check:
1. WHEN does disposal happen? (which dates)
2. WHAT is being disposed? (which products/nodes)
3. WHY is it being disposed? (is it actually expired or forced by constraint?)
"""

from datetime import datetime, timedelta
from pyomo.core.base import value
from pyomo.environ import Constraint

from src.validation.data_coordinator import DataCoordinator
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.sliding_window_model import SlidingWindowModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.forecast import Forecast, ForecastEntry
from src.models.location import LocationType


print("="*100)
print("DISPOSAL MECHANISM INVESTIGATION")
print("="*100)

# Solve with constraint
coordinator = DataCoordinator(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)
validated = coordinator.load_and_validate()

forecast_entries = [
    ForecastEntry(location_id=e.node_id, product_id=e.product_id,
                 forecast_date=e.demand_date, quantity=e.quantity)
    for e in validated.demand_entries
]
forecast = Forecast(name="Test", entries=forecast_entries)

parser = MultiFileParser(
    'data/examples/Gluten Free Forecast - Latest.xlsm',
    'data/examples/Network_Config.xlsx',
    'data/examples/inventory_latest.XLSX'
)
_, locations, routes_legacy, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manufacturing_site = manufacturing_locations[0]

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes_legacy)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)
products_dict = {p.id: p for p in validated.products}

start = validated.planning_start_date
end = (datetime.combine(start, datetime.min.time()) + timedelta(days=27)).date()

model_builder = SlidingWindowModel(
    nodes, unified_routes, forecast, labor_calendar, cost_structure,
    products_dict, start, end, unified_truck_schedules,
    validated.get_inventory_dict(), validated.inventory_snapshot_date,
    True, True, True
)

result = model_builder.solve(solver_name='appsi_highs', time_limit_seconds=180, mip_gap=0.01)
model = model_builder.model

# Add constraint
last_date = max(model.dates)
total_end_inv = sum(
    model.inventory[n, p, s, last_date]
    for (n, p, s, t) in model.inventory
    if t == last_date
)

model.force_low_end_inv = Constraint(expr=total_end_inv <= 2000)

# Resolve
from pyomo.opt import SolverFactory
solver = SolverFactory('appsi_highs')
solver.options['time_limit'] = 180
solver.options['mip_rel_gap'] = 0.01

print("\nSolving with end_inv <= 2000 constraint...")
result = solver.solve(model, tee=False)

print("Solved!\n")

# Extract disposal details
print("="*100)
print("DISPOSAL ANALYSIS")
print("="*100)

if not hasattr(model, 'disposal'):
    print("\n❌ No disposal variables in model!")
    exit(0)

# Get disposal variable values
disposal_list = []
for (node_id, prod, state, t) in model.disposal:
    qty = value(model.disposal[node_id, prod, state, t])
    if qty > 0.01:
        disposal_list.append({
            'node': node_id,
            'product': prod,
            'state': state,
            'date': t,
            'quantity': qty
        })

print(f"\nTotal disposal: {len(disposal_list)} non-zero disposal entries")
print(f"Total disposed: {sum(d['quantity'] for d in disposal_list):,.0f} units")

if len(disposal_list) == 0:
    print("\n✓ No disposal in this solution")
    exit(0)

# For each disposal, check if it's valid (inventory actually expired)
print(f"\n\nDisposal details:")
print(f"{'Node':<10} {'Product':<40} {'State':<8} {'Date':<12} {'Qty':>10} {'Expired?':<10}")
print("-"*100)

inventory_snapshot_date = model_builder.inventory_snapshot_date

for item in sorted(disposal_list, key=lambda x: -x['quantity'])[:20]:
    # Calculate expiration date for this initial inventory
    state = item['state']
    if state == 'ambient':
        shelf_life = 17
    elif state == 'frozen':
        shelf_life = 120
    elif state == 'thawed':
        shelf_life = 14

    expiration_date = inventory_snapshot_date + timedelta(days=shelf_life)
    disposal_date = item['date']

    # Check if disposal is valid (on or after expiration)
    is_valid = disposal_date >= expiration_date
    age_at_disposal = (disposal_date - inventory_snapshot_date).days

    validity = "✓ Valid" if is_valid else f"❌ BUG! Age={age_at_disposal}"

    print(f"{item['node']:<10} {item['product'][:40]:<40} {item['state']:<8} {item['date']} {item['quantity']:>10,.0f} {validity:<10}")

# Summary
print("\n\n" + "="*100)
print("DISPOSAL VALIDITY CHECK:")
print("="*100)

valid_disposals = [d for d in disposal_list
                   if d['date'] >= (inventory_snapshot_date + timedelta(days=(17 if d['state']=='ambient' else 120 if d['state']=='frozen' else 14)))]

invalid_disposals = [d for d in disposal_list if d not in valid_disposals]

print(f"\nValid disposals (actually expired): {len(valid_disposals)} entries, {sum(d['quantity'] for d in valid_disposals):,.0f} units")
print(f"Invalid disposals (before expiration): {len(invalid_disposals)} entries, {sum(d['quantity'] for d in invalid_disposals):,.0f} units")

if len(invalid_disposals) > 0:
    print(f"\n❌ BUG FOUND: Disposal happening BEFORE expiration!")
    print(f"   {sum(d['quantity'] for d in invalid_disposals):,.0f} units disposed before they expire")
    print(f"\n   This should be impossible - disposal variables should only exist for dates >= expiration")
else:
    print(f"\n✓ All disposal is valid (inventory actually expired)")
    print(f"\n   But then WHY does constraining end_inv INCREASE disposal?")
    print(f"   Theory: Constraint forces different production timing,")
    print(f"   which prevents consuming initial inventory before it expires")

print("\n" + "="*100)
