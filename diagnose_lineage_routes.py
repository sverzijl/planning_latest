"""Diagnose why Lineage → 6130 (WA) route has no flow."""

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.optimization.unified_node_model import UnifiedNodeModel
from datetime import date, timedelta

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast, locations, routes, labor_calendar, truck_schedules, cost_structure = parser.parse_all()

# Find manufacturing site
mfg_site = next((loc for loc in locations if loc.id == '6122'), None)

# Convert
converter = LegacyToUnifiedConverter()
nodes, unified_routes, unified_trucks = converter.convert_all(
    manufacturing_site=mfg_site,
    locations=locations,
    routes=routes,
    truck_schedules=truck_schedules,
    forecast=forecast
)

# Get products (they might be strings or Product objects)
products_list = parser.parse_products()
if products_list and hasattr(products_list[0], 'product_id'):
    products_dict = {p.product_id: p for p in products_list}
else:
    # Products are strings
    from src.models.product import Product
    products_dict = {p: Product(product_id=p, name=p) for p in products_list}

# Build model (just to create shipment cohorts, don't solve)
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

print("=== BUILDING MODEL TO CREATE SHIPMENT COHORTS ===\n")

# This creates shipment cohort indices
model.build()

print(f"\n=== LINEAGE SHIPMENT COHORTS ===\n")

# Check shipments involving Lineage
to_lineage = [sc for sc in model.shipment_cohort_index_set if sc[1] == 'Lineage']
from_lineage = [sc for sc in model.shipment_cohort_index_set if sc[0] == 'Lineage']

print(f"Shipments TO Lineage: {len(to_lineage)}")
print(f"Shipments FROM Lineage: {len(from_lineage)}")

if len(from_lineage) == 0:
    print(f"\n🚨 NO SHIPMENT COHORTS FROM LINEAGE!")
    print(f"   This is why WA has no flow")
    print(f"   Shipments from Lineage are being filtered out during cohort creation")

    # Check why
    print(f"\n=== WHY ARE THEY FILTERED? ===")

    # Check if Lineage → 6130 route exists
    lineage_wa_route = next((r for r in unified_routes if r.origin_node_id == 'Lineage' and r.destination_node_id == '6130'), None)

    if lineage_wa_route:
        print(f"\n✅ Lineage → 6130 route EXISTS")
        print(f"   Transport mode: {lineage_wa_route.transport_mode}")
        print(f"   Transit days: {lineage_wa_route.transit_days}")

        # Manually check shelf life filtering
        print(f"\n=== MANUAL SHELF LIFE CHECK ===")
        prod_date = date(2025, 10, 28)
        delivery_date = date(2025, 11, 5)  # 8 days later
        age_at_arrival = (delivery_date - prod_date).days

        print(f"   Production: {prod_date}")
        print(f"   Delivery to WA: {delivery_date}")
        print(f"   Age at arrival: {age_at_arrival} days")
        print(f"   Route is FROZEN: {lineage_wa_route.transport_mode == 'frozen'}")
        print(f"   WA has ambient storage: True")
        print(f"   → Thaw event: shelf life resets to 14 days")
        print(f"   → Remaining: 14 days > 7-day minimum ✅")
        print(f"\n   Should NOT be filtered... but it is!")

    else:
        print(f"\n❌ Lineage → 6130 route NOT FOUND in unified routes")

else:
    print(f"\n✅ Shipment cohorts FROM Lineage exist")
    print(f"\nSample FROM Lineage cohorts:")
    for sc in sorted(from_lineage)[:5]:
        origin, dest, prod, prod_date, delivery_date, state = sc
        print(f"  {origin} → {dest}, {prod}, prod={prod_date}, deliv={delivery_date}, state={state}")
