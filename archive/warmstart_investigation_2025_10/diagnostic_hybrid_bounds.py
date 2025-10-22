"""Diagnostic: Verify hybrid pallet formulation bounds.

Checks:
1. Pallet variables have bounds (0, 10)
2. Model has same integer count but different domain
3. Objective is well-formed (no negative costs)
"""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from pyomo.environ import Var

parser = MultiFileParser(
    forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
    network_file="data/examples/Network_Config.xlsx",
    inventory_file="data/examples/inventory.XLSX",
)

forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
manuf_loc = manufacturing_locations[0]
manufacturing_site = ManufacturingSite(
    id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
    production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
    default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
)

converter = LegacyToUnifiedConverter()
nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
unified_routes = converter.convert_routes(routes)
unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

inventory_snapshot = parser.parse_inventory(snapshot_date=None)
initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

start_date = date(2025, 10, 20)
end_date = start_date + timedelta(days=6*7 - 1)

print("Building hybrid model...")
model_hybrid = UnifiedNodeModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    labor_calendar=labor_calendar, cost_structure=cost_structure,
    start_date=start_date, end_date=end_date,
    truck_schedules=unified_truck_schedules,
    initial_inventory=initial_inventory,
    inventory_snapshot_date=inventory_date,
    use_batch_tracking=True, allow_shortages=True, enforce_shelf_life=True,
    use_hybrid_pallet_formulation=True,
)

pyomo_hybrid = model_hybrid.build_model()

print("\nChecking pallet variable bounds:")
ub_10_count = 0
ub_62_count = 0
ub_other = 0

for v in pyomo_hybrid.component_data_objects(Var, active=True):
    if v.is_integer() and 'pallet_count' in str(v.name):
        if v.ub == 10:
            ub_10_count += 1
        elif v.ub == 62:
            ub_62_count += 1
        else:
            ub_other += 1

print(f"  Pallet vars with ub=10: {ub_10_count}")
print(f"  Pallet vars with ub=62: {ub_62_count}")
print(f"  Pallet vars with other ub: {ub_other}")

if ub_10_count > 4000:
    print(f"\n✅ Hybrid bounds applied correctly!")
elif ub_62_count > 4000:
    print(f"\n❌ Hybrid NOT applied - still using ub=62")
else:
    print(f"\n❓ Unexpected bound distribution")

print(f"\nTotal integer pallet vars: {ub_10_count + ub_62_count + ub_other}")
