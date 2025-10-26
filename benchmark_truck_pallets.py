#!/usr/bin/env python3
"""Benchmark Truck Pallet Tracking Performance.

Tests the performance impact of adding integer pallet variables to truck loading
across different planning horizons (1-4 weeks).

Compares:
- WITH pallet tracking: Integer pallet counts (enforce ceiling rounding)
- WITHOUT pallet tracking: Continuous unit-based capacity

Measures:
- Solve time
- MIP gap
- Total cost
- Integer variable count
- Business logic correctness (O/T usage, weekend minimization, SKU efficiency)
"""

import sys
from pathlib import Path
from datetime import date, timedelta
import time
from typing import Dict, Any, List
import json

sys.path.insert(0, str(Path(__file__).parent))

from src.parsers.multi_file_parser import MultiFileParser
from src.optimization.unified_node_model import UnifiedNodeModel
from src.optimization.legacy_to_unified_converter import LegacyToUnifiedConverter
from src.models.manufacturing import ManufacturingSite
from src.models.location import LocationType
from pyomo.environ import Var, value as pyo_value


def count_variables(model):
    """Count variables by type."""
    binary = sum(1 for v in model.component_data_objects(ctype=Var, active=True) if v.is_binary())
    integer = sum(1 for v in model.component_data_objects(ctype=Var, active=True) if v.is_integer())
    continuous = sum(1 for v in model.component_data_objects(ctype=Var, active=True) if v.is_continuous())
    return binary, integer, continuous


def validate_truck_pallets(model_obj, pyomo_model) -> Dict[str, Any]:
    """Validate truck pallet loading constraints."""
    validation = {
        "total_trucks_used": 0,
        "trucks_over_capacity": 0,
        "max_pallets_on_truck": 0.0,
        "trucks_checked": 0,
        "product_ceiling_violations": 0,
    }

    if not hasattr(pyomo_model, 'truck_pallet_load'):
        return validation

    if not hasattr(pyomo_model, 'truck_used'):
        return validation

    # Check each truck departure
    for truck_idx in range(len(model_obj.truck_schedules)):
        for date_val in pyomo_model.dates:
            if (truck_idx, date_val) not in pyomo_model.truck_used:
                continue

            try:
                truck_used = pyo_value(pyomo_model.truck_used[truck_idx, date_val])
            except:
                continue  # Variable not initialized

            if truck_used < 0.5:  # Truck not used
                continue

            validation["total_trucks_used"] += 1
            validation["trucks_checked"] += 1

            # Sum pallets on this truck departure
            total_pallets = 0
            truck = model_obj.truck_by_index[truck_idx]
            truck_destinations = [truck.destination_node_id]
            if truck.has_intermediate_stops():
                truck_destinations.extend(truck.intermediate_stops)

            for dest in truck_destinations:
                route = next((r for r in model_obj.routes
                             if r.origin_node_id == truck.origin_node_id
                             and r.destination_node_id == dest), None)
                if not route:
                    continue

                delivery_date = date_val + timedelta(days=route.transit_days)
                if delivery_date not in pyomo_model.dates:
                    continue

                for prod in pyomo_model.products:
                    if (truck_idx, dest, prod, delivery_date) in pyomo_model.truck_pallet_load:
                        try:
                            pallet_count = pyo_value(pyomo_model.truck_pallet_load[truck_idx, dest, prod, delivery_date])
                            units = pyo_value(pyomo_model.truck_load[truck_idx, dest, prod, delivery_date])

                            # Validate ceiling constraint
                            if pallet_count * 320 < units - 0.1:  # Allow small numerical error
                                validation["product_ceiling_violations"] += 1

                            total_pallets += pallet_count
                        except:
                            pass  # Variable not initialized

            validation["max_pallets_on_truck"] = max(validation["max_pallets_on_truck"], total_pallets)

            if total_pallets > 44.1:  # Allow small numerical error
                validation["trucks_over_capacity"] += 1

    return validation


def analyze_labor_usage(model_obj, pyomo_model) -> Dict[str, Any]:
    """Analyze labor usage patterns."""
    labor_stats = {
        "total_regular_hours": 0.0,
        "total_overtime_hours": 0.0,
        "weekend_production_days": 0,
        "weekday_production_days": 0,
        "total_production_days": 0,
    }

    if not hasattr(pyomo_model, 'production_day'):
        return labor_stats

    manufacturing_nodes = [n.id for n in model_obj.nodes_list if n.capabilities.can_manufacture]

    for node_id in manufacturing_nodes:
        for date_val in pyomo_model.dates:
            if (node_id, date_val) in pyomo_model.production_day:
                try:
                    prod_day = pyo_value(pyomo_model.production_day[node_id, date_val])

                    if prod_day > 0.5:  # Production occurred
                        labor_stats["total_production_days"] += 1

                        if date_val.weekday() < 5:  # Weekday
                            labor_stats["weekday_production_days"] += 1
                        else:  # Weekend
                            labor_stats["weekend_production_days"] += 1
                except:
                    pass  # Variable not initialized

            # Count labor hours
            if hasattr(pyomo_model, 'fixed_hours_used') and (node_id, date_val) in pyomo_model.fixed_hours_used:
                try:
                    labor_stats["total_regular_hours"] += pyo_value(pyomo_model.fixed_hours_used[node_id, date_val])
                except:
                    pass

            if hasattr(pyomo_model, 'overtime_hours_used') and (node_id, date_val) in pyomo_model.overtime_hours_used:
                try:
                    labor_stats["total_overtime_hours"] += pyo_value(pyomo_model.overtime_hours_used[node_id, date_val])
                except:
                    pass

    return labor_stats


def analyze_sku_efficiency(model_obj, pyomo_model) -> Dict[str, Any]:
    """Analyze SKU selection efficiency."""
    sku_stats = {
        "days_with_production": 0,
        "total_skus_produced": 0,
        "avg_skus_per_day": 0.0,
        "max_skus_per_day": 0,
        "min_skus_per_day": 999,
    }

    # Check if model has the required attribute
    if not hasattr(pyomo_model, 'product_produced'):
        return sku_stats

    manufacturing_nodes = [n.id for n in model_obj.nodes_list if n.capabilities.can_manufacture]

    for node_id in manufacturing_nodes:
        for date_val in pyomo_model.dates:
            # Count SKUs by checking product_produced binaries
            num_skus = 0
            for prod in pyomo_model.products:
                if (node_id, prod, date_val) in pyomo_model.product_produced:
                    try:
                        if pyo_value(pyomo_model.product_produced[node_id, prod, date_val]) > 0.5:
                            num_skus += 1
                    except:
                        pass  # Variable not initialized

            if num_skus > 0:  # Production occurred
                sku_stats["days_with_production"] += 1
                sku_stats["total_skus_produced"] += num_skus
                sku_stats["max_skus_per_day"] = max(sku_stats["max_skus_per_day"], num_skus)
                sku_stats["min_skus_per_day"] = min(sku_stats["min_skus_per_day"], num_skus)

    if sku_stats["days_with_production"] > 0:
        sku_stats["avg_skus_per_day"] = sku_stats["total_skus_produced"] / sku_stats["days_with_production"]
    else:
        sku_stats["min_skus_per_day"] = 0

    return sku_stats


def run_benchmark(weeks: int, use_pallet_tracking: bool) -> Dict[str, Any]:
    """Run a single benchmark test.

    Args:
        weeks: Number of weeks in planning horizon
        use_pallet_tracking: Whether to enable pallet tracking

    Returns:
        Dictionary with benchmark results
    """
    print(f"\n{'='*80}")
    print(f"BENCHMARK: {weeks}-week horizon, Pallet Tracking: {'ENABLED' if use_pallet_tracking else 'DISABLED'}")
    print(f"{'='*80}")

    # Load data
    parser = MultiFileParser(
        forecast_file="data/examples/Gluten Free Forecast - Latest.xlsm",
        network_file="data/examples/Network_Config.xlsx",
        inventory_file="data/examples/inventory_latest.XLSX",
    )

    forecast, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

    # Parse products with units_per_mix
    products_dict = parser.parse_products()

    manufacturing_locations = [loc for loc in locations if loc.type == LocationType.MANUFACTURING]
    manuf_loc = manufacturing_locations[0]
    manufacturing_site = ManufacturingSite(
        id=manuf_loc.id, name=manuf_loc.name, storage_mode=manuf_loc.storage_mode,
        production_rate=1400.0, daily_startup_hours=0.5, daily_shutdown_hours=0.25,
        default_changeover_hours=0.5, production_cost_per_unit=cost_structure.production_cost_per_unit,
    )

    converter = LegacyToUnifiedConverter()
    nodes = converter.convert_nodes(manufacturing_site, locations, forecast)
    unified_routes = converter.convert_routes(routes)
    unified_truck_schedules = converter.convert_truck_schedules(truck_schedules_list, manufacturing_site.id)

    inventory_snapshot = parser.parse_inventory(snapshot_date=None)
    initial_inventory = inventory_snapshot.to_optimization_dict() if inventory_snapshot else None
    inventory_date = inventory_snapshot.snapshot_date if inventory_snapshot else None

    # Set date range
    start_date = date(2025, 10, 20)
    end_date = start_date + timedelta(days=weeks*7 - 1)

    print(f"\nConfiguration:")
    print(f"  Horizon: {weeks} weeks ({(end_date - start_date).days + 1} days)")
    print(f"  Pallet tracking: {use_pallet_tracking}")

    # Create model
    model_obj = UnifiedNodeModel(
        nodes=nodes,
        routes=unified_routes,
        forecast=forecast,
        labor_calendar=labor_calendar,
        cost_structure=cost_structure,
        products=products_dict,
        start_date=start_date,
        end_date=end_date,
        truck_schedules=unified_truck_schedules,
        initial_inventory=initial_inventory,
        inventory_snapshot_date=inventory_date,
        use_batch_tracking=True,
        allow_shortages=True,
        enforce_shelf_life=True,
        force_all_skus_daily=False,
        use_truck_pallet_tracking=use_pallet_tracking,  # KEY PARAMETER
    )

    # Solve model (builds internally)
    print(f"\nSolving...")
    total_start = time.time()

    result = model_obj.solve(
        solver_name='appsi_highs',
        time_limit_seconds=1800,  # 30 minutes
        mip_gap=0.01,
        use_warmstart=False,  # Disable warmstart for fair comparison
    )

    total_time = time.time() - total_start

    # Get the model after solve
    pyomo_model = model_obj.model

    # Count variables
    binary, integer, continuous = count_variables(pyomo_model)

    print(f"\nModel Statistics:")
    print(f"  Binary vars: {binary:,}")
    print(f"  Integer vars: {integer:,}")
    print(f"  Continuous vars: {continuous:,}")
    print(f"  Total vars: {binary + integer + continuous:,}")

    # Extract results from OptimizationResult object
    total_cost = result.objective_value if result.success else None
    status = result.termination_condition
    solve_time = result.solve_time_seconds if hasattr(result, 'solve_time_seconds') else total_time
    mip_gap = result.gap if hasattr(result, 'gap') and result.gap is not None else None

    # Validate results only if solve succeeded
    if result.success and pyomo_model is not None:
        truck_validation = validate_truck_pallets(model_obj, pyomo_model)
        labor_stats = analyze_labor_usage(model_obj, pyomo_model)
        sku_stats = analyze_sku_efficiency(model_obj, pyomo_model)
    else:
        truck_validation = {"error": "Solve failed"}
        labor_stats = {"error": "Solve failed"}
        sku_stats = {"error": "Solve failed"}

    print(f"\nSolve Results:")
    print(f"  Solve time: {solve_time:.1f}s")
    print(f"  Status: {status}")
    print(f"  Success: {result.success}")
    print(f"  Total cost: ${total_cost:,.2f}" if total_cost else "  Total cost: N/A")
    print(f"  MIP gap: {mip_gap*100:.2f}%" if mip_gap is not None else "  MIP gap: N/A")

    if result.success:
        if use_pallet_tracking and 'error' not in truck_validation:
            print(f"\nTruck Pallet Validation:")
            print(f"  Trucks used: {truck_validation['total_trucks_used']}")
            print(f"  Max pallets on truck: {truck_validation['max_pallets_on_truck']:.1f} / 44")
            print(f"  Trucks over capacity: {truck_validation['trucks_over_capacity']}")
            print(f"  Ceiling violations: {truck_validation['product_ceiling_violations']}")

        if 'error' not in labor_stats:
            print(f"\nLabor Usage:")
            print(f"  Total production days: {labor_stats['total_production_days']}")
            print(f"  Weekday production: {labor_stats['weekday_production_days']}")
            print(f"  Weekend production: {labor_stats['weekend_production_days']}")
            print(f"  Regular hours: {labor_stats['total_regular_hours']:.1f}h")
            print(f"  Overtime hours: {labor_stats['total_overtime_hours']:.1f}h")

        if 'error' not in sku_stats:
            print(f"\nSKU Efficiency:")
            print(f"  Avg SKUs/day: {sku_stats['avg_skus_per_day']:.1f}")
            print(f"  Max SKUs/day: {sku_stats['max_skus_per_day']}")
            print(f"  Min SKUs/day: {sku_stats['min_skus_per_day']}")
    else:
        print(f"\n⚠️  Solve failed - skipping validation")
        if result.infeasibility_message:
            print(f"  Reason: {result.infeasibility_message}")

    # Return benchmark data
    return {
        "weeks": weeks,
        "pallet_tracking": use_pallet_tracking,
        "solve_time": solve_time,
        "total_time": total_time,
        "status": str(status),
        "success": result.success,
        "total_cost": float(total_cost) if total_cost else None,
        "mip_gap": float(mip_gap) if mip_gap is not None else None,
        "variables": {
            "binary": binary,
            "integer": integer,
            "continuous": continuous,
            "total": binary + integer + continuous,
        },
        "truck_validation": truck_validation,
        "labor_stats": labor_stats,
        "sku_stats": sku_stats,
    }


def main():
    """Run benchmark suite."""
    print("="*80)
    print("TRUCK PALLET TRACKING BENCHMARK SUITE")
    print("="*80)
    print("\nTesting performance impact of integer pallet variables on truck loading")
    print("\nHorizons: 1, 2, 3, 4 weeks")
    print("Modes: WITH and WITHOUT pallet tracking")

    results = []

    # Test each horizon with both modes
    for weeks in [1, 2, 3, 4]:
        for pallet_tracking in [False, True]:  # Test WITHOUT first for baseline
            try:
                result = run_benchmark(weeks, pallet_tracking)
                results.append(result)

                # Save intermediate results
                with open('benchmark_truck_pallets_results.json', 'w') as f:
                    json.dump(results, f, indent=2)

            except Exception as e:
                print(f"\n❌ ERROR: Benchmark failed for {weeks} weeks, pallet_tracking={pallet_tracking}")
                print(f"Error: {str(e)}")
                import traceback
                traceback.print_exc()

    # Print summary table
    print("\n" + "="*80)
    print("BENCHMARK SUMMARY")
    print("="*80)

    print("\n{:<8} {:<12} {:<12} {:<12} {:<12} {:<10}".format(
        "Weeks", "Pallet", "Solve Time", "Total Cost", "MIP Gap", "Int Vars"
    ))
    print("-" * 80)

    for r in results:
        pallet_mode = "ENABLED" if r["pallet_tracking"] else "DISABLED"
        gap_str = f"{r['mip_gap']*100:.2f}%" if r["mip_gap"] is not None else "N/A"
        cost_str = f"${r['total_cost']:,.0f}" if r["total_cost"] else "N/A"

        print("{:<8} {:<12} {:<12.1f}s {:<12} {:<10} {:<10,}".format(
            r["weeks"], pallet_mode, r["solve_time"], cost_str, gap_str, r["variables"]["integer"]
        ))

    # Performance comparison
    print("\n" + "="*80)
    print("PERFORMANCE IMPACT ANALYSIS")
    print("="*80)

    for weeks in [1, 2, 3, 4]:
        without = next((r for r in results if r["weeks"] == weeks and not r["pallet_tracking"]), None)
        with_pallet = next((r for r in results if r["weeks"] == weeks and r["pallet_tracking"]), None)

        if without and with_pallet:
            time_increase = ((with_pallet["solve_time"] - without["solve_time"]) / without["solve_time"]) * 100
            var_increase = ((with_pallet["variables"]["integer"] - without["variables"]["integer"]) /
                           without["variables"]["integer"]) * 100

            print(f"\n{weeks}-week horizon:")
            print(f"  Solve time: {without['solve_time']:.1f}s → {with_pallet['solve_time']:.1f}s ({time_increase:+.1f}%)")
            print(f"  Integer vars: {without['variables']['integer']:,} → {with_pallet['variables']['integer']:,} ({var_increase:+.1f}%)")

            if with_pallet["total_cost"] and without["total_cost"]:
                cost_diff = ((with_pallet["total_cost"] - without["total_cost"]) / without["total_cost"]) * 100
                print(f"  Total cost: ${without['total_cost']:,.0f} → ${with_pallet['total_cost']:,.0f} ({cost_diff:+.2f}%)")

    print("\n" + "="*80)
    print("BENCHMARK COMPLETE")
    print("="*80)
    print(f"\nResults saved to: benchmark_truck_pallets_results.json")

    return 0


if __name__ == "__main__":
    exit(main())
