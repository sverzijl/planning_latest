#!/usr/bin/env python3
"""Check transport costs to disposal nodes to verify hypothesis."""

from src.parsers.excel_parser import ExcelParser

# Parse routes
parser = ExcelParser('data/examples/Network_Config.xlsx')
routes = parser.parse_routes()

# Disposal nodes
disposal_nodes = ['6110', '6120', '6123', '6130', '6104']

print('=' * 80)
print('ROUTE COSTS TO DISPOSAL NODES')
print('=' * 80)

# Group routes by destination
routes_to_disposal = {}
for route in routes:
    if route.to_location in disposal_nodes:
        if route.to_location not in routes_to_disposal:
            routes_to_disposal[route.to_location] = []
        routes_to_disposal[route.to_location].append(route)

# Print routes to each disposal node
for node in sorted(disposal_nodes):
    print(f'\nRoutes TO {node}:')
    print('-' * 80)
    if node in routes_to_disposal:
        for route in sorted(routes_to_disposal[node], key=lambda r: r.cost):
            print(f'  {route.from_location} → {route.to_location}:')
            print(f'    Cost: ${route.cost:.2f}/unit')
            print(f'    Mode: {route.transport_mode}, Transit: {route.transit_time_days} days')
    else:
        print('  No inbound routes')

# Economic analysis
print('\n' + '=' * 80)
print('ECONOMIC ANALYSIS')
print('=' * 80)
shortage_cost = 10.0
disposal_cost = 15.0
total_alternative = shortage_cost + disposal_cost

print(f'Shortage cost: ${shortage_cost:.2f}/unit')
print(f'Disposal cost: ${disposal_cost:.2f}/unit')
print(f'Total (shortage + disposal): ${total_alternative:.2f}/unit')
print()
print(f'If route cost > ${total_alternative:.2f}/unit, model prefers shortage + disposal!')
print()

# Check which routes exceed this threshold
print('Routes where transport > shortage + disposal:')
print('-' * 80)
expensive_routes = []
for node in disposal_nodes:
    if node in routes_to_disposal:
        for route in routes_to_disposal[node]:
            if route.cost > total_alternative:
                expensive_routes.append((route, node))
                print(f'  {route.from_location} → {node}: ${route.cost:.2f}/unit (${route.cost - total_alternative:.2f} MORE expensive)')

if not expensive_routes:
    print('  ❌ NO ROUTES EXCEED THRESHOLD!')
    print('  → Hypothesis REJECTED - transport costs are NOT the cause')
    print()
    print('Alternative hypothesis: Model is choosing to minimize END INVENTORY')
    print('by taking shortages EARLY (when transport would be needed) and')
    print('letting initial inventory expire (disposal happens LATE at Day 24-28).')
    print()
    print('This makes sense if:')
    print('  - Transport cost + holding cost > shortage cost')
    print('  - Model optimizes across full horizon')
    print('  - Early shortages with late disposal minimizes total inventory held')
else:
    print(f'\n✓ Found {len(expensive_routes)} routes where model would prefer shortage + disposal')
