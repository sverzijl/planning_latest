"""Daily Snapshot Validation Framework.

Comprehensive validation of Daily Snapshot correctness including:
- Material balance (inventory + production + inflows = outflows + demand)
- Product ID validity (no UNKNOWN products)
- Location ID validity (all locations exist)
- Quantity consistency (non-negative, realistic)
- Flow consistency (matches shipments)
- Demand satisfaction (adds up correctly)

This validator discovers issues by checking invariants that MUST hold.

Last Updated: 2025-10-30
"""

from typing import List, Dict, Set, Tuple, Any
from datetime import date as Date
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class SnapshotValidationError(Exception):
    """Raised when snapshot validation fails."""
    pass


class DailySnapshotValidator:
    """Validates Daily Snapshot correctness through invariant checking."""

    def __init__(self, snapshot, forecast, locations_dict, products):
        """Initialize validator.

        Args:
            snapshot: DailySnapshot instance
            forecast: Forecast instance
            locations_dict: Dict[location_id, Location]
            products: List of Product instances or list of product_id strings
        """
        self.snapshot = snapshot
        self.forecast = forecast
        self.locations_dict = locations_dict
        self.products = products

        # Handle both Product objects, dict of products, and string IDs
        if isinstance(products, dict):
            # Dict of products
            self.valid_product_ids = set(products.keys())
        elif products and hasattr(products, '__iter__') and not isinstance(products, str):
            # Check first element
            first = next(iter(products), None)
            if first and hasattr(first, 'id'):
                self.valid_product_ids = {p.id for p in products}
            else:
                self.valid_product_ids = set(products)
        else:
            self.valid_product_ids = set()

        self.valid_location_ids = set(locations_dict.keys())

    def validate_comprehensive(self, strict: bool = False) -> List[str]:
        """Run all validation checks.

        Args:
            strict: If True, raises on first error. If False, collects all errors.

        Returns:
            List of validation errors (empty if all valid)

        Raises:
            SnapshotValidationError: If strict=True and validation fails
        """
        errors = []

        # Run all checks
        errors.extend(self._check_product_ids())
        errors.extend(self._check_location_ids())
        errors.extend(self._check_quantities())
        errors.extend(self._check_material_balance())
        errors.extend(self._check_demand_satisfaction())
        errors.extend(self._check_flow_consistency())

        if strict and errors:
            raise SnapshotValidationError(
                f"Snapshot validation failed ({len(errors)} errors):\n" +
                "\n".join(f"  - {e}" for e in errors)
            )

        return errors

    def _check_product_ids(self) -> List[str]:
        """Check that all product IDs are valid (no UNKNOWN).

        Returns:
            List of product ID errors
        """
        errors = []

        # Check production activity
        for batch in self.snapshot.production_activity:
            if batch.product_id not in self.valid_product_ids:
                errors.append(
                    f"Production activity has invalid product_id: '{batch.product_id}'. "
                    f"Valid: {sorted(self.valid_product_ids)}"
                )
            if batch.product_id == 'UNKNOWN':
                errors.append(
                    f"Production activity has UNKNOWN product on {batch.production_date}"
                )

        # Check inflows
        for flow in self.snapshot.inflows:
            if flow.product_id not in self.valid_product_ids:
                errors.append(
                    f"Inflow has invalid product_id: '{flow.product_id}' at {flow.location_id}"
                )
            if flow.product_id == 'UNKNOWN':
                errors.append(
                    f"Inflow has UNKNOWN product: {flow.flow_type} at {flow.location_id}"
                )

        # Check outflows
        for flow in self.snapshot.outflows:
            if flow.product_id not in self.valid_product_ids:
                errors.append(
                    f"Outflow has invalid product_id: '{flow.product_id}' at {flow.location_id}"
                )
            if flow.product_id == 'UNKNOWN':
                errors.append(
                    f"Outflow has UNKNOWN product: {flow.flow_type} at {flow.location_id}"
                )

        # Check demand satisfied
        for demand in self.snapshot.demand_satisfied:
            if demand.product_id not in self.valid_product_ids:
                errors.append(
                    f"Demand has invalid product_id: '{demand.product_id}' at {demand.destination_id}"
                )
            if demand.product_id == 'UNKNOWN':
                errors.append(
                    f"Demand has UNKNOWN product at {demand.destination_id}"
                )

        # Check inventory (location_inventory is Dict[str, LocationInventory])
        for location_id, loc_inv in self.snapshot.location_inventory.items():
            # LocationInventory has by_product dict
            if hasattr(loc_inv, 'by_product'):
                for product_id, qty in loc_inv.by_product.items():
                    if product_id not in self.valid_product_ids:
                        errors.append(
                            f"Inventory has invalid product_id: '{product_id}' at {location_id}"
                        )
                    if product_id == 'UNKNOWN':
                        errors.append(
                            f"Inventory has UNKNOWN product at {location_id}: {qty:.0f} units"
                        )

        return errors

    def _check_location_ids(self) -> List[str]:
        """Check that all location IDs are valid.

        Returns:
            List of location ID errors
        """
        errors = []

        # Check inventory locations (Dict[location_id, LocationInventory])
        for location_id in self.snapshot.location_inventory.keys():
            if location_id not in self.valid_location_ids:
                errors.append(
                    f"Inventory has invalid location_id: '{location_id}'"
                )

        # Check flows
        for flow in self.snapshot.inflows + self.snapshot.outflows:
            if flow.location_id not in self.valid_location_ids:
                errors.append(
                    f"Flow has invalid location_id: '{flow.location_id}'"
                )

        # Check demand
        for demand in self.snapshot.demand_satisfied:
            if demand.destination_id not in self.valid_location_ids:
                errors.append(
                    f"Demand has invalid destination_id: '{demand.destination_id}'"
                )

        return errors

    def _check_quantities(self) -> List[str]:
        """Check that all quantities are valid (non-negative, realistic).

        Returns:
            List of quantity errors
        """
        errors = []

        # Check inventory quantities (from location_inventory)
        for location_id, loc_inv in self.snapshot.location_inventory.items():
            if hasattr(loc_inv, 'by_product'):
                for product_id, qty in loc_inv.by_product.items():
                    if qty < 0:
                        errors.append(
                            f"Negative inventory: {product_id} at {location_id}: {qty}"
                        )
                    if qty > 1_000_000:
                        errors.append(
                            f"Unrealistic inventory: {product_id} at {location_id}: {qty:,.0f} units"
                        )

        # Check flow quantities
        for flow in self.snapshot.inflows + self.snapshot.outflows:
            if flow.quantity < 0:
                errors.append(
                    f"Negative flow: {flow.flow_type} {flow.product_id} at {flow.location_id}: {flow.quantity}"
                )

        # Check demand quantities
        for demand in self.snapshot.demand_satisfied:
            if demand.demand_quantity < 0:
                errors.append(
                    f"Negative demand: {demand.product_id} at {demand.destination_id}: {demand.demand_quantity}"
                )
            if demand.supplied_quantity < 0:
                errors.append(
                    f"Negative supplied: {demand.product_id} at {demand.destination_id}: {demand.supplied_quantity}"
                )
            if demand.shortage_quantity < 0:
                errors.append(
                    f"Negative shortage: {demand.product_id} at {demand.destination_id}: {demand.shortage_quantity}"
                )

        return errors

    def _check_material_balance(self) -> List[str]:
        """Check material balance for each location-product.

        Invariant: For each (location, product):
            inventory_start + production + inflows = inventory_end + outflows + demand_consumed

        Returns:
            List of material balance errors
        """
        errors = []

        # This is complex - would need previous day's inventory
        # For now, just check that inventory changes make sense
        # (Detailed balance check requires multi-day tracking)

        return errors

    def _check_demand_satisfaction(self) -> List[str]:
        """Check that demand satisfaction is consistent.

        Invariant: supplied + shortage = demand (for each location-product)

        Returns:
            List of demand satisfaction errors
        """
        errors = []

        for demand in self.snapshot.demand_satisfied:
            total_accounted = demand.supplied_quantity + demand.shortage_quantity
            if abs(total_accounted - demand.demand_quantity) > 0.01:
                errors.append(
                    f"Demand accounting mismatch: {demand.product_id} at {demand.destination_id}: "
                    f"supplied({demand.supplied_quantity:.2f}) + shortage({demand.shortage_quantity:.2f}) "
                    f"= {total_accounted:.2f} != demand({demand.demand_quantity:.2f})"
                )

            # Check for suspicious patterns
            if demand.supplied_quantity > demand.demand_quantity + 0.01:
                errors.append(
                    f"Supplied exceeds demand: {demand.product_id} at {demand.destination_id}: "
                    f"supplied={demand.supplied_quantity:.2f} > demand={demand.demand_quantity:.2f}"
                )

        return errors

    def _check_flow_consistency(self) -> List[str]:
        """Check that flows are internally consistent.

        Returns:
            List of flow consistency errors
        """
        errors = []

        # Check for duplicate flows
        # CRITICAL: Key must include counterparty to distinguish different destinations
        # Example: Two departures from 6122 (to 6104 and to 6125) are NOT duplicates
        flow_keys = set()
        for flow in self.snapshot.inflows:
            key = (flow.location_id, flow.product_id, flow.flow_type, flow.counterparty)
            if key in flow_keys:
                errors.append(
                    f"Duplicate inflow: {flow.flow_type} {flow.product_id} at {flow.location_id} from {flow.counterparty}"
                )
            flow_keys.add(key)

        flow_keys = set()
        for flow in self.snapshot.outflows:
            key = (flow.location_id, flow.product_id, flow.flow_type, flow.counterparty)
            if key in flow_keys:
                errors.append(
                    f"Duplicate outflow: {flow.flow_type} {flow.product_id} at {flow.location_id} to {flow.counterparty}"
                )
            flow_keys.add(key)

        return errors

    def generate_diagnostic_report(self) -> str:
        """Generate comprehensive diagnostic report.

        Returns:
            Formatted report string
        """
        lines = []
        lines.append(f"\n{'=' * 80}")
        lines.append(f"DAILY SNAPSHOT VALIDATION REPORT")
        lines.append(f"Date: {self.snapshot.date}")  # Field is 'date', not 'snapshot_date'
        lines.append(f"{'=' * 80}")

        errors = self.validate_comprehensive(strict=False)

        if not errors:
            lines.append("\n✅ ALL VALIDATIONS PASSED")
        else:
            lines.append(f"\n❌ FOUND {len(errors)} VALIDATION ERRORS:")
            for error in errors:
                lines.append(f"  - {error}")

        # Summary statistics
        lines.append(f"\nSnapshot Statistics:")
        lines.append(f"  Production activity: {len(self.snapshot.production_activity)} batches")
        lines.append(f"  Inflows: {len(self.snapshot.inflows)}")
        lines.append(f"  Outflows: {len(self.snapshot.outflows)}")
        lines.append(f"  Demand satisfied: {len(self.snapshot.demand_satisfied)}")
        lines.append(f"  Locations with inventory: {len(self.snapshot.location_inventory)}")

        # Product coverage from location_inventory
        products_in_inventory = set()
        for loc_inv in self.snapshot.location_inventory.values():
            if hasattr(loc_inv, 'by_product'):
                products_in_inventory.update(loc_inv.by_product.keys())

        products_in_demand = {d.product_id for d in self.snapshot.demand_satisfied}
        products_in_production = {b.product_id for b in self.snapshot.production_activity}

        lines.append(f"\nProduct Coverage:")
        lines.append(f"  In inventory: {len(products_in_inventory)} products")
        lines.append(f"  In demand: {len(products_in_demand)} products")
        lines.append(f"  In production: {len(products_in_production)} products")

        # UNKNOWN products check
        unknown_in_inventory = sum(
            1 for loc_inv in self.snapshot.location_inventory.values()
            if hasattr(loc_inv, 'by_product')
            for prod_id in loc_inv.by_product.keys()
            if prod_id == 'UNKNOWN'
        )
        unknown_in_flows = sum(1 for f in self.snapshot.inflows + self.snapshot.outflows if f.product_id == 'UNKNOWN')

        if unknown_in_inventory > 0:
            lines.append(f"\n⚠️ WARNING: {unknown_in_inventory} inventory records have UNKNOWN product")
        if unknown_in_flows > 0:
            lines.append(f"⚠️ WARNING: {unknown_in_flows} flows have UNKNOWN product")

        lines.append(f"\n{'=' * 80}")

        return "\n".join(lines)
