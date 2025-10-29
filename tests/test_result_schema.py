"""Tests for optimization result schema validation.

This module validates the Pydantic schema for OptimizationSolution,
ensuring that:
1. Valid data structures pass validation
2. Invalid data structures raise ValidationError
3. Cross-field validations work correctly
4. Extra fields are permitted
5. JSON serialization works

Run: pytest tests/test_result_schema.py -v
"""

import pytest
from datetime import date, timedelta
from pydantic import ValidationError

from src.optimization.result_schema import (
    OptimizationSolution,
    ProductionBatchResult,
    LaborHoursBreakdown,
    ShipmentResult,
    TotalCostBreakdown,
    LaborCostBreakdown,
    ProductionCostBreakdown,
    TransportCostBreakdown,
    HoldingCostBreakdown,
    WasteCostBreakdown,
    StorageState,
)


class TestProductionBatchResult:
    """Test ProductionBatchResult validation."""

    def test_valid_batch(self):
        """Test that valid batch data validates successfully."""
        batch = ProductionBatchResult(
            node="6122",
            product="PROD1",
            date=date(2025, 10, 1),
            quantity=1000.0
        )
        assert batch.node == "6122"
        assert batch.product == "PROD1"
        assert batch.quantity == 1000.0

    def test_negative_quantity_fails(self):
        """Test that negative quantity raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ProductionBatchResult(
                node="6122",
                product="PROD1",
                date=date(2025, 10, 1),
                quantity=-100.0  # Invalid!
            )
        assert "greater than or equal to 0" in str(exc_info.value).lower()

    def test_extra_fields_allowed(self):
        """Test that extra fields are permitted."""
        batch = ProductionBatchResult(
            node="6122",
            product="PROD1",
            date=date(2025, 10, 1),
            quantity=1000.0,
            custom_field="extra_data"  # Extra field
        )
        assert batch.custom_field == "extra_data"


class TestLaborHoursBreakdown:
    """Test LaborHoursBreakdown validation."""

    def test_valid_labor_hours(self):
        """Test valid labor hours breakdown."""
        labor = LaborHoursBreakdown(
            used=12.0,
            paid=12.0,
            fixed=12.0,
            overtime=0.0,
            non_fixed=0.0
        )
        assert labor.used == 12.0
        assert labor.paid == 12.0

    def test_paid_less_than_used_fails(self):
        """Test that paid < used raises ValidationError (violates minimum payment)."""
        with pytest.raises(ValidationError) as exc_info:
            LaborHoursBreakdown(
                used=12.0,
                paid=10.0,  # Invalid! Paid must be >= used
                fixed=10.0,
                overtime=0.0,
                non_fixed=0.0
            )
        assert "paid" in str(exc_info.value).lower()

    def test_defaults_to_zero(self):
        """Test that fields default to 0.0."""
        labor = LaborHoursBreakdown()
        assert labor.used == 0.0
        assert labor.paid == 0.0
        assert labor.fixed == 0.0


class TestShipmentResult:
    """Test ShipmentResult validation."""

    def test_valid_shipment(self):
        """Test valid shipment data."""
        shipment = ShipmentResult(
            origin="6122",
            destination="6104",
            product="PROD1",
            quantity=500.0,
            delivery_date=date(2025, 10, 5)
        )
        assert shipment.origin == "6122"
        assert shipment.quantity == 500.0

    def test_zero_quantity_fails(self):
        """Test that zero quantity raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ShipmentResult(
                origin="6122",
                destination="6104",
                product="PROD1",
                quantity=0.0,  # Invalid! Must be > 0
                delivery_date=date(2025, 10, 5)
            )
        assert "greater than 0" in str(exc_info.value).lower()

    def test_optional_fields(self):
        """Test that optional fields can be None."""
        shipment = ShipmentResult(
            origin="6122",
            destination="6104",
            product="PROD1",
            quantity=500.0,
            delivery_date=date(2025, 10, 5),
            production_date=None,
            state=None,
            assigned_truck_id=None
        )
        assert shipment.production_date is None
        assert shipment.state is None


class TestCostBreakdowns:
    """Test cost breakdown structures."""

    def test_valid_total_cost_breakdown(self):
        """Test valid complete cost breakdown."""
        costs = TotalCostBreakdown(
            total_cost=1000.0,
            labor=LaborCostBreakdown(total=200.0),
            production=ProductionCostBreakdown(total=300.0, unit_cost=1.0, total_units=300.0),
            transport=TransportCostBreakdown(total=200.0),
            holding=HoldingCostBreakdown(total=200.0),
            waste=WasteCostBreakdown(total=100.0)
        )
        assert costs.total_cost == 1000.0
        assert costs.labor.total == 200.0

    def test_cost_sum_mismatch_fails(self):
        """Test that total_cost != sum(components) raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TotalCostBreakdown(
                total_cost=2000.0,  # Doesn't match sum (1000.0)
                labor=LaborCostBreakdown(total=200.0),
                production=ProductionCostBreakdown(total=300.0, unit_cost=1.0, total_units=300.0),
                transport=TransportCostBreakdown(total=200.0),
                holding=HoldingCostBreakdown(total=200.0),
                waste=WasteCostBreakdown(total=100.0)  # Sum = 1000
            )
        assert "total_cost" in str(exc_info.value).lower()


class TestOptimizationSolution:
    """Test top-level OptimizationSolution validation."""

    def test_valid_sliding_window_solution(self):
        """Test valid SlidingWindowModel solution."""
        solution = OptimizationSolution(
            model_type="sliding_window",
            production_batches=[
                ProductionBatchResult(node="6122", product="PROD1", date=date(2025, 10, 1), quantity=1000.0)
            ],
            labor_hours_by_date={
                date(2025, 10, 1): LaborHoursBreakdown(used=8.0, paid=8.0, fixed=8.0)
            },
            shipments=[
                ShipmentResult(
                    origin="6122", destination="6104", product="PROD1",
                    quantity=500.0, delivery_date=date(2025, 10, 3)
                )
            ],
            costs=TotalCostBreakdown(
                total_cost=1000.0,
                labor=LaborCostBreakdown(total=200.0),
                production=ProductionCostBreakdown(total=300.0, unit_cost=1.0, total_units=1000.0),
                transport=TransportCostBreakdown(total=200.0),
                holding=HoldingCostBreakdown(total=200.0),
                waste=WasteCostBreakdown(total=100.0)
            ),
            total_cost=1000.0,
            fill_rate=0.95,
            total_production=1000.0,
            has_aggregate_inventory=True,
            inventory_state={(
"6122", "PROD1", "ambient", date(2025, 10, 1)): 500.0}  # Tuple keys allowed!
        )

        assert solution.model_type == "sliding_window"
        assert solution.has_aggregate_inventory is True
        assert solution.get_inventory_format() == "state"

    def test_valid_unified_node_solution(self):
        """Test valid UnifiedNodeModel solution."""
        solution = OptimizationSolution(
            model_type="unified_node",
            production_batches=[
                ProductionBatchResult(node="6122", product="PROD1", date=date(2025, 10, 1), quantity=1000.0)
            ],
            labor_hours_by_date={
                date(2025, 10, 1): LaborHoursBreakdown(used=8.0, paid=8.0, fixed=8.0)
            },
            shipments=[
                ShipmentResult(
                    origin="6122", destination="6104", product="PROD1",
                    quantity=500.0, delivery_date=date(2025, 10, 3)
                )
            ],
            costs=TotalCostBreakdown(
                total_cost=1000.0,
                labor=LaborCostBreakdown(total=200.0),
                production=ProductionCostBreakdown(total=300.0, unit_cost=1.0, total_units=1000.0),
                transport=TransportCostBreakdown(total=200.0),
                holding=HoldingCostBreakdown(total=200.0),
                waste=WasteCostBreakdown(total=100.0)
            ),
            total_cost=1000.0,
            fill_rate=0.95,
            total_production=1000.0,
            use_batch_tracking=True,
            cohort_inventory={("6122", "PROD1", date(2025, 10, 1), date(2025, 10, 1), date(2025, 10, 1), "ambient"): 500.0}  # 6-tuple keys!
        )

        assert solution.model_type == "unified_node"
        assert solution.use_batch_tracking is True
        assert solution.get_inventory_format() == "cohort"

    def test_missing_required_field_fails(self):
        """Test that missing required field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            OptimizationSolution(
                model_type="sliding_window",
                # Missing production_batches - required!
                labor_hours_by_date={},
                shipments=[],
                costs=TotalCostBreakdown(
                    total_cost=0.0,
                    labor=LaborCostBreakdown(total=0.0),
                    production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=0.0),
                    transport=TransportCostBreakdown(total=0.0),
                    holding=HoldingCostBreakdown(total=0.0),
                    waste=WasteCostBreakdown(total=0.0)
                ),
                total_cost=0.0,
                fill_rate=1.0,
                total_production=0.0
            )
        assert "production_batches" in str(exc_info.value).lower()

    def test_invalid_fill_rate_fails(self):
        """Test that fill_rate > 1.0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            OptimizationSolution(
                model_type="sliding_window",
                production_batches=[],
                labor_hours_by_date={},
                shipments=[],
                costs=TotalCostBreakdown(
                    total_cost=0.0,
                    labor=LaborCostBreakdown(total=0.0),
                    production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=0.0),
                    transport=TransportCostBreakdown(total=0.0),
                    holding=HoldingCostBreakdown(total=0.0),
                    waste=WasteCostBreakdown(total=0.0)
                ),
                total_cost=0.0,
                fill_rate=1.5,  # Invalid! Must be <= 1.0
                total_production=0.0,
                has_aggregate_inventory=True
            )
        assert "fill_rate" in str(exc_info.value).lower()

    def test_total_cost_mismatch_fails(self):
        """Test that total_cost != costs.total_cost raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            OptimizationSolution(
                model_type="sliding_window",
                production_batches=[],
                labor_hours_by_date={},
                shipments=[],
                costs=TotalCostBreakdown(
                    total_cost=500.0,  # Costs say 500
                    labor=LaborCostBreakdown(total=100.0),
                    production=ProductionCostBreakdown(total=100.0, unit_cost=1.0, total_units=100.0),
                    transport=TransportCostBreakdown(total=100.0),
                    holding=HoldingCostBreakdown(total=100.0),
                    waste=WasteCostBreakdown(total=100.0)
                ),
                total_cost=999.0,  # But top-level says 999!
                fill_rate=1.0,
                total_production=0.0,
                has_aggregate_inventory=True
            )
        assert "total_cost" in str(exc_info.value).lower()

    def test_total_production_mismatch_fails(self):
        """Test that total_production != sum(batches) raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            OptimizationSolution(
                model_type="sliding_window",
                production_batches=[
                    ProductionBatchResult(node="6122", product="PROD1", date=date(2025, 10, 1), quantity=1000.0)
                ],  # Sum = 1000
                labor_hours_by_date={},
                shipments=[],
                costs=TotalCostBreakdown(
                    total_cost=0.0,
                    labor=LaborCostBreakdown(total=0.0),
                    production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=1000.0),
                    transport=TransportCostBreakdown(total=0.0),
                    holding=HoldingCostBreakdown(total=0.0),
                    waste=WasteCostBreakdown(total=0.0)
                ),
                total_cost=0.0,
                fill_rate=1.0,
                total_production=5000.0,  # Mismatch! Should be 1000
                has_aggregate_inventory=True
            )
        assert "total_production" in str(exc_info.value).lower()

    def test_extra_fields_preserved(self):
        """Test that extra model-specific fields are preserved."""
        solution = OptimizationSolution(
            model_type="sliding_window",
            production_batches=[],
            labor_hours_by_date={},
            shipments=[],
            costs=TotalCostBreakdown(
                total_cost=0.0,
                labor=LaborCostBreakdown(total=0.0),
                production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=0.0),
                transport=TransportCostBreakdown(total=0.0),
                holding=HoldingCostBreakdown(total=0.0),
                waste=WasteCostBreakdown(total=0.0)
            ),
            total_cost=0.0,
            fill_rate=1.0,
            total_production=0.0,
            has_aggregate_inventory=True
        )

        # Add extra field after creation
        solution.custom_metric = 42.0
        solution.debug_info = "test"

        assert solution.custom_metric == 42.0
        assert solution.debug_info == "test"

    def test_sliding_window_without_aggregate_flag_fails(self):
        """Test that SlidingWindowModel must set has_aggregate_inventory=True."""
        with pytest.raises(ValidationError) as exc_info:
            OptimizationSolution(
                model_type="sliding_window",
                production_batches=[],
                labor_hours_by_date={},
                shipments=[],
                costs=TotalCostBreakdown(
                    total_cost=0.0,
                    labor=LaborCostBreakdown(total=0.0),
                    production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=0.0),
                    transport=TransportCostBreakdown(total=0.0),
                    holding=HoldingCostBreakdown(total=0.0),
                    waste=WasteCostBreakdown(total=0.0)
                ),
                total_cost=0.0,
                fill_rate=1.0,
                total_production=0.0,
                has_aggregate_inventory=False  # Invalid for sliding_window!
            )
        assert "has_aggregate_inventory" in str(exc_info.value).lower()

    def test_unified_node_without_batch_flag_fails(self):
        """Test that UnifiedNodeModel must set use_batch_tracking=True."""
        with pytest.raises(ValidationError) as exc_info:
            OptimizationSolution(
                model_type="unified_node",
                production_batches=[],
                labor_hours_by_date={},
                shipments=[],
                costs=TotalCostBreakdown(
                    total_cost=0.0,
                    labor=LaborCostBreakdown(total=0.0),
                    production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=0.0),
                    transport=TransportCostBreakdown(total=0.0),
                    holding=HoldingCostBreakdown(total=0.0),
                    waste=WasteCostBreakdown(total=0.0)
                ),
                total_cost=0.0,
                fill_rate=1.0,
                total_production=0.0,
                use_batch_tracking=False  # Invalid for unified_node!
            )
        assert "use_batch_tracking" in str(exc_info.value).lower()

    def test_get_inventory_format(self):
        """Test get_inventory_format() helper method."""
        # SlidingWindow model
        sliding_solution = OptimizationSolution(
            model_type="sliding_window",
            production_batches=[],
            labor_hours_by_date={},
            shipments=[],
            costs=TotalCostBreakdown(
                total_cost=0.0,
                labor=LaborCostBreakdown(total=0.0),
                production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=0.0),
                transport=TransportCostBreakdown(total=0.0),
                holding=HoldingCostBreakdown(total=0.0),
                waste=WasteCostBreakdown(total=0.0)
            ),
            total_cost=0.0,
            fill_rate=1.0,
            total_production=0.0,
            has_aggregate_inventory=True
        )
        assert sliding_solution.get_inventory_format() == "state"

        # UnifiedNode model
        unified_solution = OptimizationSolution(
            model_type="unified_node",
            production_batches=[],
            labor_hours_by_date={},
            shipments=[],
            costs=TotalCostBreakdown(
                total_cost=0.0,
                labor=LaborCostBreakdown(total=0.0),
                production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=0.0),
                transport=TransportCostBreakdown(total=0.0),
                holding=HoldingCostBreakdown(total=0.0),
                waste=WasteCostBreakdown(total=0.0)
            ),
            total_cost=0.0,
            fill_rate=1.0,
            total_production=0.0,
            use_batch_tracking=True
        )
        assert unified_solution.get_inventory_format() == "cohort"

    def test_production_batches_sorted(self):
        """Test that production_batches are sorted by date."""
        solution = OptimizationSolution(
            model_type="sliding_window",
            production_batches=[
                ProductionBatchResult(node="6122", product="PROD1", date=date(2025, 10, 3), quantity=100.0),
                ProductionBatchResult(node="6122", product="PROD2", date=date(2025, 10, 1), quantity=200.0),
                ProductionBatchResult(node="6122", product="PROD1", date=date(2025, 10, 2), quantity=150.0),
            ],
            labor_hours_by_date={},
            shipments=[],
            costs=TotalCostBreakdown(
                total_cost=0.0,
                labor=LaborCostBreakdown(total=0.0),
                production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=450.0),
                transport=TransportCostBreakdown(total=0.0),
                holding=HoldingCostBreakdown(total=0.0),
                waste=WasteCostBreakdown(total=0.0)
            ),
            total_cost=0.0,
            fill_rate=1.0,
            total_production=450.0,
            has_aggregate_inventory=True
        )

        # Check batches are sorted
        dates = [b.date for b in solution.production_batches]
        assert dates == sorted(dates), "Batches should be sorted by date"
        assert dates[0] == date(2025, 10, 1)

    def test_tuple_keys_preserved(self):
        """Test that tuple keys in dicts are preserved (not converted to strings)."""
        solution = OptimizationSolution(
            model_type="sliding_window",
            production_batches=[],
            labor_hours_by_date={},
            shipments=[],
            costs=TotalCostBreakdown(
                total_cost=0.0,
                labor=LaborCostBreakdown(total=0.0),
                production=ProductionCostBreakdown(total=0.0, unit_cost=0.0, total_units=0.0),
                transport=TransportCostBreakdown(total=0.0),
                holding=HoldingCostBreakdown(total=0.0),
                waste=WasteCostBreakdown(total=0.0)
            ),
            total_cost=0.0,
            fill_rate=1.0,
            total_production=0.0,
            has_aggregate_inventory=True,
            production_by_date_product={
                ("6122", "PROD1", date(2025, 10, 1)): 1000.0,  # Tuple key
                ("6122", "PROD2", date(2025, 10, 1)): 500.0,
            }
        )

        # Verify tuple keys are preserved
        assert len(solution.production_by_date_product) == 2
        assert ("6122", "PROD1", date(2025, 10, 1)) in solution.production_by_date_product
        assert solution.production_by_date_product[("6122", "PROD1", date(2025, 10, 1))] == 1000.0


class TestStorageState:
    """Test StorageState enum."""

    def test_valid_states(self):
        """Test that all valid states work."""
        assert StorageState.AMBIENT == "ambient"
        assert StorageState.FROZEN == "frozen"
        assert StorageState.THAWED == "thawed"

    def test_invalid_state_fails(self):
        """Test that invalid state string fails."""
        with pytest.raises(ValueError):
            StorageState("invalid_state")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
