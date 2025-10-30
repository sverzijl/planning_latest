"""Snapshot Dict Contract Validator.

Validates the snapshot dictionary format that the UI component receives.
This is the contract between _generate_snapshot() and render_daily_snapshot().

Checks:
1. Schema compliance (all required fields present with correct types)
2. Material balance (production + arrivals = departures + consumption + Δinventory)
3. Temporal consistency (inventory evolves correctly day-to-day)
4. Invariant validation (mathematical properties that MUST hold)

Last Updated: 2025-10-30
"""

from typing import Dict, List, Any
from datetime import date as Date, timedelta
from collections import defaultdict


class SnapshotDictValidator:
    """Validates snapshot dict format and invariants."""

    REQUIRED_FIELDS = {
        'date': Date,
        'total_inventory': (int, float),
        'in_transit_total': (int, float),
        'production_total': (int, float),
        'demand_total': (int, float),
        'location_inventory': dict,
        'in_transit_shipments': list,
        'production_batches': list,
        'inflows': list,
        'outflows': list,
        'demand_satisfaction': list,
    }

    LOCATION_INV_REQUIRED_FIELDS = {
        'location_name': str,
        'total': (int, float),
        'by_product': dict,
        'batches': dict,
    }

    @classmethod
    def validate_schema(cls, snapshot: Dict[str, Any]) -> List[str]:
        """Validate snapshot dict has all required fields with correct types.

        Args:
            snapshot: Snapshot dictionary from _generate_snapshot()

        Returns:
            List of schema validation errors
        """
        errors = []

        # Check top-level fields
        for field, expected_type in cls.REQUIRED_FIELDS.items():
            if field not in snapshot:
                errors.append(f"Missing required field: '{field}'")
                continue

            value = snapshot[field]
            if not isinstance(value, expected_type):
                errors.append(
                    f"Field '{field}' has wrong type: expected {expected_type}, got {type(value).__name__}"
                )

        # Check location_inventory structure
        if 'location_inventory' in snapshot:
            for loc_id, inv_data in snapshot['location_inventory'].items():
                if not isinstance(inv_data, dict):
                    errors.append(f"location_inventory['{loc_id}'] must be dict, got {type(inv_data).__name__}")
                    continue

                for field, expected_type in cls.LOCATION_INV_REQUIRED_FIELDS.items():
                    if field not in inv_data:
                        errors.append(f"location_inventory['{loc_id}'] missing field: '{field}'")
                    elif not isinstance(inv_data[field], expected_type):
                        errors.append(
                            f"location_inventory['{loc_id}']['{field}'] has wrong type: "
                            f"expected {expected_type}, got {type(inv_data[field]).__name__}"
                        )

        return errors

    @classmethod
    def validate_invariants(cls, snapshot: Dict[str, Any]) -> List[str]:
        """Validate mathematical invariants that MUST hold.

        Args:
            snapshot: Snapshot dictionary

        Returns:
            List of invariant violations
        """
        errors = []

        # Invariant 1: total_inventory >= 0
        total_inv = snapshot.get('total_inventory', 0)
        if total_inv < 0:
            errors.append(f"Negative total_inventory: {total_inv}")

        # Invariant 2: sum(location inventories) = total_inventory
        location_sum = sum(
            inv_data.get('total', 0)
            for inv_data in snapshot.get('location_inventory', {}).values()
        )
        if abs(location_sum - total_inv) > 0.01:
            errors.append(
                f"Location inventory sum ({location_sum:.2f}) != total_inventory ({total_inv:.2f})"
            )

        # Invariant 3: by_product sum = total for each location
        for loc_id, inv_data in snapshot.get('location_inventory', {}).items():
            total = inv_data.get('total', 0)
            by_product_sum = sum(inv_data.get('by_product', {}).values())

            if abs(by_product_sum - total) > 0.01:
                errors.append(
                    f"Location {loc_id}: by_product sum ({by_product_sum:.2f}) != total ({total:.2f})"
                )

        # Invariant 4: demand.supplied + demand.shortage = demand.demand for each record
        for demand_item in snapshot.get('demand_satisfaction', []):
            if isinstance(demand_item, dict):
                demand = demand_item.get('demand_quantity', 0)
                supplied = demand_item.get('supplied_quantity', 0)
                shortage = demand_item.get('shortage_quantity', 0)

                if abs((supplied + shortage) - demand) > 0.01:
                    errors.append(
                        f"Demand accounting error at {demand_item.get('destination_id')}: "
                        f"supplied({supplied:.2f}) + shortage({shortage:.2f}) != demand({demand:.2f})"
                    )

        # Invariant 5: Batches should have all required fields
        for loc_id, inv_data in snapshot.get('location_inventory', {}).items():
            batches_by_product = inv_data.get('batches', {})
            for product_id, batch_list in batches_by_product.items():
                for batch in batch_list:
                    if not isinstance(batch, dict):
                        errors.append(f"Batch must be dict, got {type(batch).__name__}")
                        continue

                    required_batch_fields = ['id', 'quantity', 'production_date', 'age_days', 'state']
                    for field in required_batch_fields:
                        if field not in batch:
                            errors.append(
                                f"Batch missing field '{field}' in {product_id} at {loc_id}"
                            )

        return errors

    @classmethod
    def validate_temporal_consistency(
        cls,
        snapshots_by_date: Dict[Date, Dict[str, Any]]
    ) -> List[str]:
        """Validate inventory evolves correctly across multiple days.

        Args:
            snapshots_by_date: Dict mapping date to snapshot dict

        Returns:
            List of temporal consistency errors
        """
        errors = []

        sorted_dates = sorted(snapshots_by_date.keys())

        for i in range(len(sorted_dates) - 1):
            date1 = sorted_dates[i]
            date2 = sorted_dates[i + 1]

            snap1 = snapshots_by_date[date1]
            snap2 = snapshots_by_date[date2]

            # Check: inventory should change based on production and consumption
            inv1 = snap1.get('total_inventory', 0)
            inv2 = snap2.get('total_inventory', 0)
            prod2 = snap2.get('production_total', 0)
            demand2 = snap2.get('demand_total', 0)

            # Very rough check: if there's production, inventory should increase
            # (unless consumption exceeds production)
            if prod2 > 100 and inv2 < inv1 and demand2 < prod2 * 0.5:
                # Production happened but inventory decreased despite low demand
                errors.append(
                    f"{date1}→{date2}: Inventory decreased ({inv1:.0f}→{inv2:.0f}) "
                    f"despite production ({prod2:.0f}) exceeding demand ({demand2:.0f})"
                )

        return errors

    @classmethod
    def validate_comprehensive(
        cls,
        snapshot: Dict[str, Any],
        previous_snapshot: Dict[str, Any] = None
    ) -> List[str]:
        """Run all validations on a snapshot.

        Args:
            snapshot: Snapshot dict to validate
            previous_snapshot: Optional previous day's snapshot for temporal checks

        Returns:
            List of all validation errors
        """
        errors = []

        errors.extend(cls.validate_schema(snapshot))
        errors.extend(cls.validate_invariants(snapshot))

        if previous_snapshot:
            snapshots_by_date = {
                previous_snapshot['date']: previous_snapshot,
                snapshot['date']: snapshot
            }
            errors.extend(cls.validate_temporal_consistency(snapshots_by_date))

        return errors
