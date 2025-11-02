#!/usr/bin/env python3
"""Check routes to/from Lineage."""

from src.parsers.multi_file_parser import MultiFileParser

parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

_, locations, routes, _, _, _ = parser.parse_all()

print("="*80)
print("LINEAGE NETWORK CONNECTIVITY")
print("="*80)

lineage = None
for loc in locations:
    if loc.id == "Lineage":
        lineage = loc
        break

if lineage:
    print(f"\nLineage: type={lineage.type}, storage={lineage.storage_mode}")

routes_to = [r for r in routes if r.destination_id == "Lineage"]
print(f"\nRoutes TO Lineage: {len(routes_to)}")
for route in routes_to:
    print(f"  {route.origin_id} → Lineage (mode={route.transport_mode}, days={route.transit_time_days})")

routes_from = [r for r in routes if r.origin_id == "Lineage"]
print(f"\nRoutes FROM Lineage: {len(routes_from)}")
for route in routes_from:
    print(f"  Lineage → {route.destination_id} (mode={route.transport_mode}, days={route.transit_time_days})")

if not routes_from:
    print("\nWARNING: No routes FROM Lineage → frozen inventory has no outlet!")

print("="*80)
