"""Debug demand cohort filtering to understand zero production."""
from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from datetime import date, timedelta

# Parse data
parser = MultiFileParser(
    forecast_file='data/examples/Gluten Free Forecast - Latest.xlsm',
    network_file='data/examples/Network_Config.xlsx'
)

forecast_data = parser.parse_forecast()
network_data = parser.parse_network()
initial_inventory = parser.parse_initial_inventory()

# Build model (don't solve)
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

# Check demand cohort structure
print("=" * 80)
print("DEMAND COHORT ANALYSIS")
print("=" * 80)

# Sample a few demand entries
sample_demands = list(forecast_data['demand'].items())[:5]
print(f"\n📋 Sample Demands:")
for (node_id, prod, demand_date), qty in sample_demands:
    print(f"  {node_id}, {prod[:30]}, {demand_date}: {qty} units")

# Build cohort indices
from datetime import date as Date
dates = [model.start_date + timedelta(days=i) for i in range((model.end_date - model.start_date).days + 1)]
demand_cohorts = model._build_demand_cohort_indices(dates)

print(f"\n📊 Demand Cohort Statistics:")
print(f"  Total demand cohorts: {len(demand_cohorts):,}")

# Analyze first demand location
first_demand = sample_demands[0]
node_id, prod, demand_date = first_demand[0]

print(f"\n🔍 Analyzing demand: {node_id}, {prod[:30]}, {demand_date}")

# Find all cohorts for this demand
cohorts_for_demand = [
    (n, p, pd, dd, s) for (n, p, pd, dd, s) in demand_cohorts
    if n == node_id and p == prod and dd == demand_date
]

print(f"  Cohorts available: {len(cohorts_for_demand)}")
print(f"\n  Sample cohorts (first 10):")
for cohort in cohorts_for_demand[:10]:
    n, p, pd, dd, s = cohort
    age = (dd - pd).days
    print(f"    prod_date={pd}, demand_date={dd}, state={s}, age={age} days")

# Check production dates
prod_dates_in_cohorts = set(pd for (n, p, pd, dd, s) in cohorts_for_demand)
print(f"\n  Production dates in cohorts: {sorted(prod_dates_in_cohorts)}")
print(f"  Planning horizon starts: {model.start_date}")
print(f"  Earliest prod_date in cohorts: {min(prod_dates_in_cohorts) if prod_dates_in_cohorts else 'NONE'}")

# Check if any production dates are in planning horizon
horizon_prod_dates = [pd for pd in prod_dates_in_cohorts if pd >= model.start_date]
print(f"  Prod dates in planning horizon: {len(horizon_prod_dates)}")
if len(horizon_prod_dates) == 0:
    print(f"  ⚠️  NO PRODUCTION DATES IN HORIZON CAN SATISFY DEMAND!")
    print(f"  ⚠️  This would cause zero production!")

# Check states
states_in_cohorts = set(s for (n, p, pd, dd, s) in cohorts_for_demand)
print(f"\n  States in cohorts: {sorted(states_in_cohorts)}")
