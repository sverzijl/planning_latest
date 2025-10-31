"""Test if corrected shelf life constraints eliminate expired inventory."""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from tests.conftest import create_test_products
from datetime import timedelta, date

# Patch the shelf life constraint before importing model
import src.optimization.sliding_window_model as swm_module

# Save original
original_build = swm_module.SlidingWindowModel.build_model

def patched_build_model(self):
    """Build model with CORRECTED shelf life constraints."""
    from pyomo.environ import Constraint
    from datetime import timedelta
    from src.models.route import TransportMode
    
    # Call original to build everything
    model = original_build(self)
    
    # Remove old buggy constraint
    del model.ambient_shelf_life_con
    
    # Add corrected constraint
    def ambient_shelf_life_corrected(m, node_id, prod, t):
        node = self.nodes[node_id]
        if not node.supports_ambient_storage():
            return Constraint.Skip
        
        window_start = max(0, list(m.dates).index(t) - 16)
        window_dates = list(m.dates)[window_start:list(m.dates).index(t)+1]
        
        # Inflows: initial_inv (if day 0 in window) + production + thaw + arrivals
        Q_ambient = 0
        first_date = min(m.dates)
        if first_date in window_dates:
            Q_ambient += self.initial_inventory.get((node_id, prod, 'ambient'), 0)
        
        for tau in window_dates:
            if node.can_produce() and (node_id, prod, tau) in m.production:
                if node.get_production_state() == 'ambient':
                    Q_ambient += m.production[node_id, prod, tau]
            if (node_id, prod, tau) in m.thaw:
                Q_ambient += m.thaw[node_id, prod, tau]
            for route in self.routes_to_node[node_id]:
                arrival_state = self._determine_arrival_state(route, node)
                if arrival_state == 'ambient':
                    if (route.origin_node_id, node_id, prod, tau, 'ambient') in m.shipment:
                        Q_ambient += m.shipment[route.origin_node_id, node_id, prod, tau, 'ambient']
        
        # Outflows: shipments + freeze + DEMAND
        O_ambient = 0
        for tau in window_dates:
            for route in self.routes_from_node[node_id]:
                if route.transport_mode != TransportMode.FROZEN:
                    delivery_date = tau + timedelta(days=route.transit_days)
                    if (node_id, route.destination_node_id, prod, delivery_date, 'ambient') in m.shipment:
                        O_ambient += m.shipment[node_id, route.destination_node_id, prod, delivery_date, 'ambient']
            if (node_id, prod, tau) in m.freeze:
                O_ambient += m.freeze[node_id, prod, tau]
            if node.has_demand_capability() and (node_id, prod, tau) in m.demand_consumed:
                O_ambient += m.demand_consumed[node_id, prod, tau]
        
        if Q_ambient is 0 and O_ambient is 0:
            return Constraint.Skip
        
        # CORRECTED: inventory[t] <= Q - O
        return m.inventory[node_id, prod, 'ambient', t] <= Q_ambient - O_ambient
    
    model.ambient_shelf_life_con = Constraint(
        [(n, p, t) for n, node in self.nodes.items()
         if node.supports_ambient_storage()
         for p in model.products for t in model.dates],
        rule=ambient_shelf_life_corrected,
        doc="CORRECTED: Ambient shelf life with demand in outflows"
    )
    
    return model

# Apply patch
swm_module.SlidingWindowModel.build_model = patched_build_model

# Now test
from src.optimization.sliding_window_model import SlidingWindowModel

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx',
    inventory_file='data/examples/inventory_latest.XLSX'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_params = parser.parse_all()
inventory = parser.parse_inventory()

mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site, locations=locations, routes=routes,
    truck_schedules=truck_schedules, forecast=forecast
)

start = inventory.snapshot_date
end = start + timedelta(weeks=4)
product_ids = sorted(set(entry.product_id for entry in forecast.entries))
products = create_test_products(product_ids)

print('Testing CORRECTED shelf life constraints via monkey patch...')

model = SlidingWindowModel(
    nodes=nodes, routes=unified_routes, forecast=forecast,
    products=products, labor_calendar=labor_calendar,
    cost_structure=cost_params,
    start_date=start, end_date=end,
    truck_schedules=unified_trucks,
    initial_inventory=inventory.to_optimization_dict(),
    inventory_snapshot_date=inventory.snapshot_date,
    allow_shortages=True,
    use_pallet_tracking=False
)

result = model.solve(solver_name='appsi_highs', time_limit_seconds=180, tee=False)

print(f'Result: {result.termination_condition}')

if result.is_optimal() or result.is_feasible():
    solution = model.get_solution()
    
    last_date_val = date(2025, 11, 27)
    end_inv = sum(qty for (node, prod, state, dt), qty in solution.inventory_state.items() if dt == last_date_val)
    expired = sum(qty for (n, p, d), qty in solution.production_by_date_product.items() if (last_date_val - d).days > 17)
    
    print(f'\\nWith CORRECTED constraints:')
    print(f'  End inventory: {end_inv:,.0f} (was 17,520)')
    print(f'  Expired inventory: {expired:,.0f} (was 103,335)')
    print(f'  Shortage: {solution.total_shortage_units:,.0f}')
    
    if expired < 100:
        print(f'\\n  ✅ SUCCESS: No expired inventory!')
    elif expired < 50000:
        print(f'\\n  ✅ IMPROVED: Expired reduced by {103335 - expired:.0f}')
    
    if end_inv < 1000:
        print(f'  ✅ End inventory near-zero!')
