#!/usr/bin/env python3
"""Test: Temporarily disable binary product constraints to isolate issue."""

from datetime import date, timedelta
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.sliding_window_model import SlidingWindowModel
from tests.conftest import create_test_products
from src.models.inventory import InventorySnapshot, InventoryEntry

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)
forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

# Create minimal inventory at plant
plant_inventory = InventorySnapshot(
    snapshot_date=date(2025, 10, 16),
    entries=[
        InventoryEntry(
            location_id='6122',
            product_id='HELGAS GFREE MIXED GRAIN 500G',
            quantity=320.0,
            storage_location='4000'
        )
    ]
)

# Convert to optimization format
initial_inv_dict = {}
for entry in plant_inventory.entries:
    # Infer state (plant is ambient)
    initial_inv_dict[('6122', entry.product_id, 'ambient')] = entry.quantity

print(f"Initial inventory: {initial_inv_dict}")

# 1-week test
start = date(2025, 10, 17)
end = start + timedelta(days=6)  # 1 week only
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print(f"\nScenario:")
print(f"  Horizon: {start} to {end} (1 week)")
print(f"  Initial inventory: {sum(initial_inv_dict.values()):.0f} units")

# Create model WITHOUT binary constraints by monkey-patching
class TestSlidingWindowModel(SlidingWindowModel):
    def _add_production_constraints(self, model):
        """Override to skip binary linking constraints."""
        print("  SKIPPING binary product constraints for test...")
        # Call parent but catch and skip the binary constraint part
        from pyomo.environ import Constraint

        # Only add mix-based production, skip binary linking
        if hasattr(model, 'mix_count'):
            def mix_production_rule(model, node_id, prod, t):
                if (node_id, prod, t) not in model.mix_count:
                    return Constraint.Skip
                product = self.products[prod]
                units_per_mix = getattr(product, 'units_per_mix', 415)
                return model.production[node_id, prod, t] == model.mix_count[node_id, prod, t] * units_per_mix

            model.mix_production_con = Constraint(
                model.mix_count.index_set(),
                rule=mix_production_rule
            )

        print("  Binary constraints SKIPPED")

model = TestSlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params, start_date=start, end_date=end,
    truck_schedules=unified_trucks, initial_inventory=initial_inv_dict,
    allow_shortages=True, use_pallet_tracking=False, use_truck_pallet_tracking=False
)

print("\n" + "="*80)
print("TEST: Minimal inventory WITHOUT binary product constraints")
print("="*80)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=60, mip_gap=0.01, tee=False)

print(f"\nSolve: {result.termination_condition}")
print(f"Objective: ${result.objective_value:,.2f}" if result.objective_value else "N/A")

if result.is_optimal():
    print("✓ OPTIMAL - Binary constraints were causing infeasibility!")
else:
    print("✗ STILL INFEASIBLE - Issue is elsewhere")

print("="*80)
