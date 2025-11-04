#!/usr/bin/env python3
"""Test the verified model base works."""

import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from src.optimization.verified_sliding_window_model import VerifiedSlidingWindowModel
from src.models.unified_node import UnifiedNode, NodeCapabilities, StorageMode
from src.models.unified_route import UnifiedRoute, TransportMode
from src.models.product import Product
from src.models.forecast import Forecast, ForecastEntry
from src.models.labor_calendar import LaborCalendar, LaborDay
from src.models.cost_structure import CostStructure


def main():
    print("Testing Verified Model Base...")

    # Simple network
    mfg = UnifiedNode(
        id='MFG',
        name='Manufacturing',
        capabilities=NodeCapabilities(
            can_manufacture=True,
            production_rate_per_hour=1400,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            has_demand=False
        )
    )

    demand_node = UnifiedNode(
        id='DEMAND',
        name='Demand',
        capabilities=NodeCapabilities(
            can_manufacture=False,
            can_store=True,
            storage_mode=StorageMode.AMBIENT,
            has_demand=True
        )
    )

    nodes = [mfg, demand_node]

    routes = [
        UnifiedRoute(
            id='R1',
            origin_node_id='MFG',
            destination_node_id='DEMAND',
            transit_days=2,
            transport_mode=TransportMode.AMBIENT,
            cost_per_unit=0.10
        )
    ]

    products = {
        'PROD_A': Product(id='PROD_A', sku='PROD_A', name='Product A', units_per_mix=415)
    }

    # Forecast
    start_date = date(2025, 11, 3)
    end_date = start_date + timedelta(days=7)

    entries = []
    for i in range(8):
        d = start_date + timedelta(days=i)
        qty = 200 if i >= 3 else 0
        entries.append(ForecastEntry(
            location_id='DEMAND',
            product_id='PROD_A',
            forecast_date=d,
            quantity=qty
        ))

    forecast = Forecast(name='Test', entries=entries)

    # Labor calendar
    labor_days = []
    for i in range(8):
        labor_days.append(LaborDay(
            date=start_date + timedelta(days=i),
            fixed_hours=12,
            overtime_hours=2,
            regular_rate=20.0,
            overtime_rate=30.0,
            non_fixed_rate=40.0
        ))

    labor_cal = LaborCalendar(name='Test', labor_days=labor_days)

    cost = CostStructure(
        production_cost_per_unit=1.30,
        shortage_penalty_per_unit=10.00
    )

    # Build model
    verified = VerifiedSlidingWindowModel(
        nodes=nodes,
        routes=routes,
        forecast=forecast,
        products=products,
        labor_calendar=labor_cal,
        cost_structure=cost,
        start_date=start_date,
        end_date=end_date,
        initial_inventory={('MFG', 'PROD_A', 'ambient'): 100},
        inventory_snapshot_date=start_date,
        allow_shortages=True
    )

    model = verified.build_model()

    # Solve
    from pyomo.environ import SolverFactory
    solver = SolverFactory('appsi_highs')
    result = solver.solve(model, tee=False)

    print(f"\nResult: {result.solver.termination_condition}")

    # Extract
    solution = verified.extract_solution(model)

    print(f"\nProduction: {solution['total_production']:.0f}")
    print(f"Shortage: {solution['total_shortage']:.0f}")
    print(f"Demand: {solution['total_demand']:.0f}")

    if solution['total_production'] > 0:
        print(f"\n✅ VERIFIED MODEL BASE WORKS! Production = {solution['total_production']:.0f}")
        return True
    else:
        print(f"\n❌ VERIFIED MODEL BASE PRODUCES ZERO!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
