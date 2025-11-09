"""
DETAILED OBJECTIVE ANALYSIS: Extract EVERY cost from Pyomo objective

This will identify EXACTLY which cost(s) increase and why.
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


def solve_and_extract_all_costs(add_end_inv_constraint=False):
    """Solve and extract EVERY cost component from Pyomo variables."""

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
    if not result.success:
        return None

    model = model_builder.model

    if add_end_inv_constraint:
        last_date = max(model.dates)
        total_end_inv = sum(
            model.inventory[n, p, s, last_date]
            for (n, p, s, t) in model.inventory
            if t == last_date
        )
        model.force_low_end_inv = Constraint(expr=total_end_inv <= 2000)

        from pyomo.opt import SolverFactory
        solver = SolverFactory('appsi_highs')
        solver.options['time_limit'] = 180
        solver.options['mip_rel_gap'] = 0.01
        result = solver.solve(model, tee=False)

    # Now extract EVERY cost component from Pyomo model
    costs = {}

    # 1. PRODUCTION UNIT COST
    prod_qty = 0
    if hasattr(model, 'production'):
        for key in model.production:
            prod_qty += value(model.production[key])

    costs['production_units'] = prod_qty
    costs['production_unit_cost'] = prod_qty * 1.30

    # 2. LABOR COST (complex - by day type)
    labor_total = 0
    labor_overtime = 0
    labor_weekend = 0

    if hasattr(model, 'labor_hours_used') and hasattr(model, 'labor_hours_paid'):
        for (node_id, t) in model.labor_hours_used:
            hours_used = value(model.labor_hours_used[node_id, t])
            hours_paid = value(model.labor_hours_paid[node_id, t]) if (node_id, t) in model.labor_hours_paid else hours_used

            labor_day = model_builder.labor_calendar.get_labor_day(t)
            if labor_day:
                fixed_hours = labor_day.fixed_hours if hasattr(labor_day, 'fixed_hours') else 0

                if fixed_hours > 0:  # Weekday
                    # Fixed hours are FREE, only overtime charged
                    if hours_used > fixed_hours:
                        overtime = hours_used - fixed_hours
                        cost = overtime * labor_day.overtime_rate
                        labor_overtime += cost
                        labor_total += cost
                else:  # Weekend
                    cost = max(hours_paid, 4) * labor_day.non_fixed_rate
                    labor_weekend += cost
                    labor_total += cost

    costs['labor_total'] = labor_total
    costs['labor_overtime'] = labor_overtime
    costs['labor_weekend'] = labor_weekend

    # 3. TRANSPORT COST
    transport_total = 0
    if hasattr(model, 'in_transit'):
        for (origin, dest, prod, departure_date, state) in model.in_transit:
            var = model.in_transit[origin, dest, prod, departure_date, state]

            # Skip uninitialized variables
            if hasattr(var, 'stale') and var.stale:
                continue

            try:
                qty = value(var)
                if qty > 0.01:
                    route = next((r for r in model_builder.routes
                                 if r.origin_node_id == origin and r.destination_node_id == dest), None)
                    if route and hasattr(route, 'cost_per_unit'):
                        transport_total += route.cost_per_unit * qty
            except:
                pass

    costs['transport'] = transport_total

    # 4. HOLDING COST (pallet-days)
    holding_total = 0
    pallet_days_frozen = 0
    pallet_days_ambient = 0

    if hasattr(model, 'pallet_count'):
        frozen_rate = 0.98
        ambient_rate = 0.0  # Currently 0

        for (node_id, prod, state, t) in model.pallet_count:
            pallets = value(model.pallet_count[node_id, prod, state, t])
            if pallets > 0.01:
                if state == 'frozen':
                    pallet_days_frozen += pallets
                    holding_total += pallets * frozen_rate
                else:
                    pallet_days_ambient += pallets
                    holding_total += pallets * ambient_rate

    costs['holding_total'] = holding_total
    costs['pallet_days_frozen'] = pallet_days_frozen
    costs['pallet_days_ambient'] = pallet_days_ambient

    # 5. PALLET ENTRY COSTS (fixed cost per pallet entering storage)
    pallet_entry_cost = 0
    if hasattr(model, 'pallet_entry'):
        frozen_entry_cost = 14.26
        num_entries = sum(value(model.pallet_entry[k]) for k in model.pallet_entry if value(model.pallet_entry[k]) > 0.01)
        pallet_entry_cost = num_entries * frozen_entry_cost

    costs['pallet_entry_cost'] = pallet_entry_cost
    costs['pallet_entries'] = num_entries if 'num_entries' in locals() else 0

    # 6. SHORTAGE COST
    shortage_units = 0
    if hasattr(model, 'shortage'):
        for key in model.shortage:
            shortage_units += value(model.shortage[key])

    costs['shortage_units'] = shortage_units
    costs['shortage_cost'] = shortage_units * 10.0

    # 7. WASTE COST (end inventory + end in-transit)
    last_date = max(model.dates)

    end_inv_units = sum(
        value(model.inventory[n, p, s, last_date])
        for (n, p, s, t) in model.inventory
        if t == last_date and value(model.inventory[n, p, s, last_date]) > 0.01
    )

    end_in_transit_units = 0
    if hasattr(model, 'in_transit'):
        for (o, d, p, t, s) in model.in_transit:
            if t == last_date:
                var = model.in_transit[o, d, p, last_date, s]
                if hasattr(var, 'stale') and var.stale:
                    continue
                try:
                    qty = value(var)
                    if qty > 0.01:
                        end_in_transit_units += qty
                except:
                    pass

    total_end_units = end_inv_units + end_in_transit_units
    waste_mult = model_builder.cost_structure.waste_cost_multiplier
    waste_cost = total_end_units * waste_mult * 1.30

    costs['end_inventory_units'] = end_inv_units
    costs['end_in_transit_units'] = end_in_transit_units
    costs['waste_cost'] = waste_cost

    # 8. CHANGEOVER COSTS
    if hasattr(model, 'product_start'):
        num_starts = sum(value(model.product_start[k]) for k in model.product_start if value(model.product_start[k]) > 0.01)

        changeover_cost_per_start = 38.40
        changeover_waste_per_start = 30 * 1.30  # 30 units @ $1.30

        costs['num_changeovers'] = num_starts
        costs['changeover_cost'] = num_starts * changeover_cost_per_start
        costs['changeover_waste_cost'] = num_starts * changeover_waste_per_start

    # 9. DISPOSAL COST
    if hasattr(model, 'disposal'):
        disposal_units = sum(value(model.disposal[k]) for k in model.disposal if value(model.disposal[k]) > 0.01)
        disposal_penalty = 15.0

        costs['disposal_units'] = disposal_units
        costs['disposal_cost'] = disposal_units * disposal_penalty

    # 10. CALCULATE TOTAL (should match model.obj)
    costs['calculated_total'] = (
        costs.get('production_unit_cost', 0) +
        costs.get('labor_total', 0) +
        costs.get('transport', 0) +
        costs.get('holding_total', 0) +
        costs.get('pallet_entry_cost', 0) +
        costs.get('shortage_cost', 0) +
        costs.get('waste_cost', 0) +
        costs.get('changeover_cost', 0) +
        costs.get('changeover_waste_cost', 0) +
        costs.get('disposal_cost', 0)
    )

    costs['pyomo_objective'] = value(model.obj)

    return costs, model, model_builder


print("="*120)
print("SOLVING BOTH MODELS AND EXTRACTING ALL COSTS FROM PYOMO")
print("="*120)

# Reset waste_mult to 10 for fair comparison
import openpyxl
wb = openpyxl.load_workbook('data/examples/Network_Config.xlsx')
ws = wb['CostParameters']
for row in ws.iter_rows(min_row=2):
    if row[0].value == 'waste_cost_multiplier':
        row[1].value = 10.0
        break
wb.save('data/examples/Network_Config.xlsx')

print("\n1. Solving NATURAL (no constraint)...")
costs_nat, model_nat, builder_nat = solve_and_extract_all_costs(False)

print("\n2. Solving CONSTRAINED (end_inv <= 2000)...")
costs_con, model_con, builder_con = solve_and_extract_all_costs(True)

# DETAILED COMPARISON
print("\n\n" + "="*120)
print("COMPLETE COST BREAKDOWN COMPARISON")
print("="*120)

print(f"\n{'Cost Component':<35} {'Natural':>15} {'Constrained':>15} {'Difference':>15} {'Makes Sense?':<20}")
print("-"*120)

# Production
print(f"{'Production (units)':<35} {costs_nat['production_units']:>15,.0f} {costs_con['production_units']:>15,.0f} {costs_con['production_units'] - costs_nat['production_units']:>15,.0f} {'✓ Less is good':<20}")
print(f"{'Production unit cost':<35} ${costs_nat['production_unit_cost']:>14,.0f} ${costs_con['production_unit_cost']:>14,.0f} ${costs_con['production_unit_cost'] - costs_nat['production_unit_cost']:>14,.0f} {'✓ Should decrease':<20}")

# Labor
print(f"{'Labor TOTAL':<35} ${costs_nat['labor_total']:>14,.0f} ${costs_con['labor_total']:>14,.0f} ${costs_con['labor_total'] - costs_nat['labor_total']:>14,.0f} {'⚠️ Producing less!':<20}")
print(f"{'  - Overtime':<35} ${costs_nat['labor_overtime']:>14,.0f} ${costs_con['labor_overtime']:>14,.0f} ${costs_con['labor_overtime'] - costs_nat['labor_overtime']:>14,.0f}")
print(f"{'  - Weekend':<35} ${costs_nat['labor_weekend']:>14,.0f} ${costs_con['labor_weekend']:>14,.0f} ${costs_con['labor_weekend'] - costs_nat['labor_weekend']:>14,.0f}")

# Transport
print(f"{'Transport':<35} ${costs_nat['transport']:>14,.0f} ${costs_con['transport']:>14,.0f} ${costs_con['transport'] - costs_nat['transport']:>14,.0f} {'⚠️ Shipping less!':<20}")

# Holding
print(f"{'Holding (pallet-days frozen)':<35} {costs_nat['pallet_days_frozen']:>15,.0f} {costs_con['pallet_days_frozen']:>15,.0f} {costs_con['pallet_days_frozen'] - costs_nat['pallet_days_frozen']:>15,.0f}")
print(f"{'Holding (pallet-days ambient)':<35} {costs_nat['pallet_days_ambient']:>15,.0f} {costs_con['pallet_days_ambient']:>15,.0f} {costs_con['pallet_days_ambient'] - costs_nat['pallet_days_ambient']:>15,.0f}")
print(f"{'Holding cost total':<35} ${costs_nat['holding_total']:>14,.0f} ${costs_con['holding_total']:>14,.0f} ${costs_con['holding_total'] - costs_nat['holding_total']:>14,.0f} {'Could increase':<20}")

# Pallet entry
print(f"{'Pallet entries (frozen)':<35} {costs_nat['pallet_entries']:>15,.0f} {costs_con['pallet_entries']:>15,.0f} {costs_con['pallet_entries'] - costs_nat['pallet_entries']:>15,.0f}")
print(f"{'Pallet entry cost':<35} ${costs_nat['pallet_entry_cost']:>14,.0f} ${costs_con['pallet_entry_cost']:>14,.0f} ${costs_con['pallet_entry_cost'] - costs_nat['pallet_entry_cost']:>14,.0f}")

# Shortage
print(f"{'Shortage (units)':<35} {costs_nat['shortage_units']:>15,.0f} {costs_con['shortage_units']:>15,.0f} {costs_con['shortage_units'] - costs_nat['shortage_units']:>15,.0f} {'✓ Expected':<20}")
print(f"{'Shortage cost':<35} ${costs_nat['shortage_cost']:>14,.0f} ${costs_con['shortage_cost']:>14,.0f} ${costs_con['shortage_cost'] - costs_nat['shortage_cost']:>14,.0f} {'✓ More shortage':<20}")

# Waste
print(f"{'End inventory (units)':<35} {costs_nat['end_inventory_units']:>15,.0f} {costs_con['end_inventory_units']:>15,.0f} {costs_con['end_inventory_units'] - costs_nat['end_inventory_units']:>15,.0f} {'✓ Should decrease':<20}")
print(f"{'Waste cost':<35} ${costs_nat['waste_cost']:>14,.0f} ${costs_con['waste_cost']:>14,.0f} ${costs_con['waste_cost'] - costs_nat['waste_cost']:>14,.0f} {'✓ Less waste':<20}")

# Changeover
print(f"{'Changeovers (count)':<35} {costs_nat.get('num_changeovers', 0):>15,.0f} {costs_con.get('num_changeovers', 0):>15,.0f} {costs_con.get('num_changeovers', 0) - costs_nat.get('num_changeovers', 0):>15,.0f} {'❌ INVESTIGATE!':<20}")
print(f"{'Changeover cost':<35} ${costs_nat.get('changeover_cost', 0):>14,.0f} ${costs_con.get('changeover_cost', 0):>14,.0f} ${costs_con.get('changeover_cost', 0) - costs_nat.get('changeover_cost', 0):>14,.0f}")
print(f"{'Changeover waste cost':<35} ${costs_nat.get('changeover_waste_cost', 0):>14,.0f} ${costs_con.get('changeover_waste_cost', 0):>14,.0f} ${costs_con.get('changeover_waste_cost', 0) - costs_nat.get('changeover_waste_cost', 0):>14,.0f}")

# Disposal
print(f"{'Disposal (units)':<35} {costs_nat.get('disposal_units', 0):>15,.0f} {costs_con.get('disposal_units', 0):>15,.0f} {costs_con.get('disposal_units', 0) - costs_nat.get('disposal_units', 0):>15,.0f}")
print(f"{'Disposal cost':<35} ${costs_nat.get('disposal_cost', 0):>14,.0f} ${costs_con.get('disposal_cost', 0):>14,.0f} ${costs_con.get('disposal_cost', 0) - costs_nat.get('disposal_cost', 0):>14,.0f}")

print("-"*120)
print(f"{'CALCULATED TOTAL':<35} ${costs_nat['calculated_total']:>14,.0f} ${costs_con['calculated_total']:>14,.0f} ${costs_con['calculated_total'] - costs_nat['calculated_total']:>14,.0f}")
print(f"{'PYOMO OBJECTIVE':<35} ${costs_nat['pyomo_objective']:>14,.0f} ${costs_con['pyomo_objective']:>14,.0f} ${costs_con['pyomo_objective'] - costs_nat['pyomo_objective']:>14,.0f}")

# Verify
calc_vs_pyomo_nat = abs(costs_nat['calculated_total'] - costs_nat['pyomo_objective'])
calc_vs_pyomo_con = abs(costs_con['calculated_total'] - costs_con['pyomo_objective'])

if calc_vs_pyomo_nat > 1000 or calc_vs_pyomo_con > 1000:
    print(f"\n⚠️  VERIFICATION ERROR!")
    print(f"   Natural: Calculated vs Pyomo = ${calc_vs_pyomo_nat:,.0f}")
    print(f"   Constrained: Calculated vs Pyomo = ${calc_vs_pyomo_con:,.0f}")
    print(f"   → Missing some cost component in extraction!")

print("\n\n" + "="*120)
print("ANALYSIS:")
print("="*120)

# Find the culprits
obj_increase = costs_con['pyomo_objective'] - costs_nat['pyomo_objective']

print(f"\nTotal objective increase: ${obj_increase:,.0f}")
print(f"\nBreakdown of increase:")

components = [
    ('Production unit cost', 'production_unit_cost'),
    ('Labor', 'labor_total'),
    ('Transport', 'transport'),
    ('Holding', 'holding_total'),
    ('Pallet entry', 'pallet_entry_cost'),
    ('Shortage', 'shortage_cost'),
    ('Waste', 'waste_cost'),
    ('Changeover direct', 'changeover_cost'),
    ('Changeover waste', 'changeover_waste_cost'),
    ('Disposal', 'disposal_cost'),
]

for name, key in components:
    diff = costs_con.get(key, 0) - costs_nat.get(key, 0)
    if abs(diff) > 1000:
        pct = diff / obj_increase * 100 if obj_increase > 0 else 0
        print(f"  {name:<25}: ${diff:>12,.0f} ({pct:>5.1f}% of total increase)")

print("\n" + "="*120)
