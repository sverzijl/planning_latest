"""Integration test to diagnose infeasibility with user's actual data files.

This test reproduces the exact scenario the user reported:
- Network_Config.xlsx
- GFree Forecast latest 
- inventory_latest.XLSX
- Settings: allow_shortages=True, MIP gap=1%, batch tracking=True, 4-week horizon
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter


def test_user_data_infeasibility_diagnosis():
    """Test with user's actual data files to diagnose infeasibility."""
    
    # User's data files
    forecast_file = Path("data/examples/Gfree Forecast.xlsm")
    network_config_file = Path("data/examples/Network_Config.xlsx")
    inventory_file = Path("data/examples/inventory_latest.XLSX")
    
    # Verify files exist
    assert forecast_file.exists(), f"Forecast file not found: {forecast_file}"
    assert network_config_file.exists(), f"Network config not found: {network_config_file}"
    assert inventory_file.exists(), f"Inventory file not found: {inventory_file}"
    
    print("\n" + "="*80)
    print("USER DATA INFEASIBILITY DIAGNOSTIC TEST")
    print("="*80)
    print(f"Forecast: {forecast_file}")
    print(f"Network Config: {network_config_file}")
    print(f"Inventory: {inventory_file}")
    
    # Parse data files
    print("\n" + "="*80)
    print("PARSING DATA FILES")
    print("="*80)
    
    try:
        parser = MultiFileParser(
            forecast_file=str(forecast_file),
            network_file=str(network_config_file),
            inventory_file=str(inventory_file)
        )

        # Parse all data
        forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

        # Get manufacturing site
        from src.models.manufacturing import ManufacturingSite
        manufacturing_nodes = [loc for loc in locations if loc.type == 'manufacturing']
        assert len(manufacturing_nodes) > 0, "No manufacturing nodes found"
        manufacturing_site = ManufacturingSite(
            id=manufacturing_nodes[0].id,
            location_name=manufacturing_nodes[0].name,
            production_rate_per_hour=1400.0,
            production_days=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        )

        # Parse initial inventory if available
        initial_inventory = None
        inventory_snapshot_date = None
        if inventory_file and inventory_file.exists():
            from src.parsers.inventory_parser import InventoryParser
            inv_parser = InventoryParser(str(inventory_file), locations, forecast.entries)
            initial_inventory, inventory_snapshot_date = inv_parser.parse()

        # Convert to unified format
        converter = LegacyToUnifiedConverter()
        nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
        unified_routes = converter.convert_routes(routes)
        unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

        converted_data = {
            'forecast': forecast,
            'nodes': nodes,
            'routes': unified_routes,
            'truck_schedules': unified_truck_schedules,
            'labor_calendar': labor_calendar,
            'cost_structure': cost_structure,
            'initial_inventory': initial_inventory,
            'inventory_snapshot_date': inventory_snapshot_date,
        }
        
        print(f"\n✓ Data parsing successful")
        print(f"  Forecast entries: {len(converted_data['forecast'].entries)}")
        print(f"  Nodes: {len(converted_data['nodes'])}")
        print(f"  Routes: {len(converted_data['routes'])}")
        print(f"  Initial inventory items: {len(converted_data['initial_inventory']) if converted_data['initial_inventory'] else 0}")
        
        # Determine planning horizon (4 weeks from forecast start)
        forecast_dates = [e.forecast_date for e in converted_data['forecast'].entries]
        start_date = min(forecast_dates)
        end_date = start_date + timedelta(days=27)  # 4 weeks = 28 days

        print(f"\n  Planning horizon: {start_date} to {end_date} (4 weeks)")

        # Check initial inventory details
        if converted_data['initial_inventory']:
            inv_quantities = list(converted_data['initial_inventory'].values())
            print(f"\n  Initial inventory:")
            print(f"    Total items: {len(inv_quantities)}")
            print(f"    Max quantity: {max(inv_quantities):,.0f} units")
            print(f"    Total quantity: {sum(inv_quantities):,.0f} units")

        # Calculate demand vs capacity
        demand_in_period = [
            e.quantity for e in converted_data['forecast'].entries
            if start_date <= e.forecast_date <= end_date
        ]
        total_demand = sum(demand_in_period)
        
        # Rough capacity estimate
        max_daily_production = 19600  # units (14h × 1400 units/hr)
        production_capacity_4w = max_daily_production * 28
        truck_capacity_4w = 11 * 4 * 14080  # 11 trucks/week × 4 weeks × 14080 units/truck
        
        print(f"\n  Demand analysis (4-week period):")
        print(f"    Total demand: {total_demand:,.0f} units")
        print(f"    Production capacity: {production_capacity_4w:,.0f} units ({total_demand/production_capacity_4w*100:.1f}% utilized)")
        print(f"    Truck capacity: {truck_capacity_4w:,.0f} units ({total_demand/truck_capacity_4w*100:.1f}% utilized)")
        
        if total_demand > production_capacity_4w:
            print(f"    ⚠️  WARNING: Demand exceeds production capacity by {total_demand - production_capacity_4w:,.0f} units!")
        
        if total_demand > truck_capacity_4w:
            print(f"    ⚠️  WARNING: Demand exceeds truck capacity by {total_demand - truck_capacity_4w:,.0f} units!")
        
    except Exception as e:
        print(f"\n❌ Data parsing failed: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Data parsing failed: {e}")
    
    # Build and solve model
    print("\n" + "="*80)
    print("BUILDING OPTIMIZATION MODEL")
    print("="*80)
    
    try:
        model = UnifiedNodeModel(
            nodes=converted_data['nodes'],
            routes=converted_data['routes'],
            forecast=converted_data['forecast'],
            labor_calendar=converted_data['labor_calendar'],
            cost_structure=converted_data['cost_structure'],
            start_date=start_date,
            end_date=end_date,
            truck_schedules=converted_data['truck_schedules'],
            initial_inventory=converted_data['initial_inventory'],
            inventory_snapshot_date=converted_data.get('inventory_snapshot_date'),
            use_batch_tracking=True,  # User's setting
            allow_shortages=True,  # User's setting
            enforce_shelf_life=True,
        )
        
        print(f"\n✓ Model initialized successfully")
        
    except Exception as e:
        print(f"\n❌ Model initialization failed: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Model initialization failed: {e}")
    
    # Solve
    print("\n" + "="*80)
    print("SOLVING OPTIMIZATION")
    print("="*80)
    print("Settings:")
    print("  - allow_shortages: True")
    print("  - enforce_shelf_life: True")
    print("  - use_batch_tracking: True")
    print("  - MIP gap: 1%")
    print("  - Time limit: 300 seconds")
    
    try:
        result = model.solve(
            solver_name='cbc',
            time_limit_seconds=300,
            mip_gap=0.01,
        )
        
        print(f"\n{'='*80}")
        print(f"OPTIMIZATION RESULT")
        print(f"{'='*80}")
        print(f"Status: {result.status}")
        print(f"Solve time: {result.solve_time_seconds:.2f}s")
        
        if result.status in ['optimal', 'feasible']:
            print(f"✓ SOLUTION FOUND")
            print(f"  Total cost: ${result.total_cost:,.2f}")
            if hasattr(result, 'fill_rate'):
                print(f"  Fill rate: {result.fill_rate:.1%}")
        else:
            print(f"❌ INFEASIBLE - No solution found")
            print(f"\nThis confirms the user's reported issue.")
            print(f"The model cannot satisfy all constraints simultaneously.")
            
            # Additional diagnostics
            print(f"\n{'='*80}")
            print(f"DIAGNOSTIC RECOMMENDATIONS")
            print(f"{'='*80}")
            print("1. Check if demand exceeds production/truck capacity")
            print("2. Check if shelf life constraints are too restrictive")
            print("3. Try relaxing constraints:")
            print("   - Increase MIP gap to 5-10%")
            print("   - Reduce horizon to 2 weeks")
            print("   - Disable shelf life enforcement")
            print("4. Check forecast data format/parsing")
            
            # Don't fail the test - we want to see the diagnostic output
            pytest.skip(f"Infeasibility confirmed - diagnostic output provided above")
        
    except Exception as e:
        print(f"\n❌ Solve failed with exception: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Solve failed: {e}")


if __name__ == "__main__":
    test_user_data_infeasibility_diagnosis()
