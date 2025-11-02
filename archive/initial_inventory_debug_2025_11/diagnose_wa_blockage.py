"""Diagnostic to find why WA (6130) route via Lineage has no flow.

This creates a minimal model with forced Lineage flow to identify the
blocking constraint.
"""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel
from src.models.product import Product
from datetime import date

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

# Convert
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    forecast=forecast
)

# Get products
products_list = parser.parse_products()
products_dict = {p: Product(product_id=p, name=p) for p in products_list}

print("=== TESTING LINEAGE ROUTE WITH FORCED FLOW ===\n")

# Create model
model = UnifiedNodeModel(
    nodes=nodes,
    routes=unified_routes,
    forecast=forecast,
    labor_calendar=labor_calendar,
    cost_structure=cost_structure,
    products=products_dict,
    start_date=date(2025, 10, 28),
    end_date=date(2025, 11, 24),
    truck_schedules=unified_trucks,
    use_batch_tracking=True,
    allow_shortages=True,
)

# Build but don't solve
print("Building model...")
try:
    pyomo_model = model.build_model()
    print("✅ Model built successfully\n")

    # Check shipment cohorts for Lineage
    lineage_cohorts = [sc for sc in model.shipment_cohort_index_set if 'Lineage' in str(sc)]
    to_lineage = [sc for sc in lineage_cohorts if sc[1] == 'Lineage']
    from_lineage = [sc for sc in lineage_cohorts if sc[0] == 'Lineage']

    print(f"Shipment cohorts TO Lineage: {len(to_lineage)}")
    print(f"Shipment cohorts FROM Lineage: {len(from_lineage)}")

    if len(from_lineage) == 0:
        print(f"\n🚨 NO SHIPMENT COHORTS FROM LINEAGE!")
        print(f"   This is the root cause - cohorts aren't being created")
        print(f"   Check _build_shipment_cohort_indices() filtering logic")
    else:
        print(f"\n✅ Shipment cohorts FROM Lineage exist")
        print(f"\nSample cohorts FROM Lineage:")
        for sc in sorted(from_lineage)[:10]:
            origin, dest, prod, prod_date, deliv_date, state = sc
            print(f"  {origin} → {dest}, {prod[:30]:30s}, prod={prod_date}, deliv={deliv_date}, state={state}")

    if len(to_lineage) == 0:
        print(f"\n🚨 NO SHIPMENT COHORTS TO LINEAGE!")
    else:
        print(f"\n✅ Shipment cohorts TO Lineage exist")
        print(f"\nSample cohorts TO Lineage:")
        for sc in sorted(to_lineage)[:10]:
            origin, dest, prod, prod_date, deliv_date, state = sc
            print(f"  {origin} → {dest}, {prod[:30]:30s}, prod={prod_date}, deliv={deliv_date}, state={state}")

except Exception as e:
    print(f"❌ Model build failed: {e}")
    import traceback
    traceback.print_exc()
