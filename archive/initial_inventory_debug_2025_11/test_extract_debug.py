"""Debug solution extraction issue."""
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from datetime import date

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast_data = parser.parse_forecast_data()
network_data = parser.parse_network_data()
initial_inventory = parser.parse_initial_inventory()

# Build and solve
print("Building model...")
model = UnifiedNodeModel(
    locations=network_data['locations'],
    routes=network_data['routes'],
    products=forecast_data['products'],
    demand=forecast_data['demand'],
    truck_schedules=network_data['truck_schedules'],
    labor_calendar=network_data['labor_calendar'],
    cost_structure=network_data['cost_parameters'],
    start_date=date(2025, 10, 27),
    end_date=date(2025, 11, 24),
    initial_inventory=initial_inventory.to_optimization_dict() if initial_inventory else None,
    inventory_snapshot_date=date(2025, 10, 27),
    use_batch_tracking=True,
    allow_shortages=True
)

print("Solving...")
result = model.solve(
    solver_name='highs',
    time_limit_seconds=500,
    mip_gap=0.01,
    tee=False
)

print(f"\nSolve status: {result.termination_condition}")
print(f"Objective: ${result.objective_value:,.2f}")

print("\n Extracting solution...")
try:
    solution = model.extract_solution(model.model)
    print(f"✓ Solution extracted successfully")
    print(f"  Keys: {list(solution.keys())[:10]}")
except Exception as e:
    print(f"❌ Solution extraction failed: {e}")
    import traceback
    traceback.print_exc()
