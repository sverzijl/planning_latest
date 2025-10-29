"""Pydantic schemas for optimization model results.

This module defines the strict interface contract between optimization models
and the UI layer. All optimization models MUST return results conforming to
these schemas.

Design Principles:
1. Fail Fast: Invalid data raises ValidationError immediately at model-UI boundary
2. Single Source of Truth: This schema IS the specification
3. Open Extension: Models can add extra fields beyond the spec (Extra.allow)
4. Type Safety: Full type hints enable IDE support and static analysis

Development Workflow:
- UI needs change → Update this schema FIRST → Update models to conform
- Schema changes require updating MODEL_RESULT_SPECIFICATION.md
- All schema changes must be validated by tests

Last Updated: 2025-10-28
"""

from __future__ import annotations

from datetime import date as Date
from typing import Dict, List, Optional, Union, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from enum import Enum


class StorageState(str, Enum):
    """Product storage state (frozen/ambient/thawed)."""
    AMBIENT = "ambient"
    FROZEN = "frozen"
    THAWED = "thawed"


# ============================================================================
# Core Data Structures
# ============================================================================

class ProductionBatchResult(BaseModel):
    """Production batch from optimization solution.

    Represents a single production run for a product on a specific date.
    """
    node: str = Field(..., description="Manufacturing node ID (e.g., '6122')")
    product: str = Field(..., description="Product ID")
    date: Date = Field(..., description="Production date (ISO format)")
    quantity: float = Field(..., ge=0, description="Production quantity (units)")

    model_config = ConfigDict(extra="allow")


class LaborHoursBreakdown(BaseModel):
    """Labor hours breakdown for a single date.

    CRITICAL: This structure is ALWAYS used, never a simple float.
    Models must always return this nested structure.
    """
    used: float = Field(default=0.0, ge=0, description="Hours actually used for production")
    paid: float = Field(default=0.0, ge=0, description="Hours paid (including minimums)")
    fixed: float = Field(default=0.0, ge=0, description="Fixed hours (weekday regular)")
    overtime: float = Field(default=0.0, ge=0, description="Overtime hours (>12h weekdays)")
    non_fixed: float = Field(default=0.0, ge=0, description="Non-fixed hours (weekends/holidays)")

    model_config = ConfigDict(extra="allow")

    @field_validator('paid')
    @classmethod
    def paid_must_be_gte_used(cls, v, info):
        """Validate that paid hours >= used hours (due to minimums)."""
        used = info.data.get('used', 0)
        if v < used:
            raise ValueError(f"paid ({v}) must be >= used ({used})")
        return v


class ShipmentResult(BaseModel):
    """Shipment from optimization solution.

    Represents product movement between two nodes.
    """
    origin: str = Field(..., description="Origin node ID")
    destination: str = Field(..., description="Destination node ID")
    product: str = Field(..., description="Product ID")
    quantity: float = Field(..., gt=0, description="Shipment quantity (units)")
    delivery_date: Date = Field(..., description="Delivery date at destination")
    departure_date: Optional[Date] = Field(None, description="Departure date from origin")
    production_date: Optional[Date] = Field(None, description="Production date (if batch tracking enabled)")
    state: Optional[StorageState] = Field(None, description="Storage state (frozen/ambient/thawed)")
    assigned_truck_id: Optional[str] = Field(None, description="Assigned truck ID (None = unassigned)")
    first_leg_destination: Optional[str] = Field(None, description="First leg destination (for multi-hop routes)")

    model_config = ConfigDict(extra="allow")


# ============================================================================
# Cost Breakdown Structures
# ============================================================================

class LaborCostBreakdown(BaseModel):
    """Labor cost components."""
    total: float = Field(..., ge=0, description="Total labor cost")
    fixed_hours_cost: float = Field(default=0.0, ge=0, description="Cost for fixed hours (Mon-Fri 0-12h)")
    overtime_cost: float = Field(default=0.0, ge=0, description="Cost for overtime (Mon-Fri 12-14h)")
    non_fixed_cost: float = Field(default=0.0, ge=0, description="Cost for non-fixed days (weekends/holidays)")
    by_date: Optional[Dict[Date, float]] = Field(None, description="Daily labor costs")

    model_config = ConfigDict(extra="allow")


class ProductionCostBreakdown(BaseModel):
    """Production cost components."""
    total: float = Field(..., ge=0, description="Total production cost")
    unit_cost: float = Field(..., ge=0, description="Cost per unit produced")
    total_units: float = Field(..., ge=0, description="Total units produced")
    changeover_cost: float = Field(default=0.0, ge=0, description="Product changeover/setup cost")

    model_config = ConfigDict(extra="allow")


class TransportCostBreakdown(BaseModel):
    """Transport cost components."""
    total: float = Field(..., ge=0, description="Total transport cost")
    shipment_cost: float = Field(default=0.0, ge=0, description="Cost for shipments (per-unit route costs)")
    truck_fixed_cost: float = Field(default=0.0, ge=0, description="Fixed truck dispatch costs")
    freeze_transition_cost: float = Field(default=0.0, ge=0, description="Cost for ambient→frozen transitions")
    thaw_transition_cost: float = Field(default=0.0, ge=0, description="Cost for frozen→thawed transitions")

    model_config = ConfigDict(extra="allow")


class HoldingCostBreakdown(BaseModel):
    """Inventory holding cost components."""
    total: float = Field(..., ge=0, description="Total holding cost")
    frozen_storage: float = Field(default=0.0, ge=0, description="Frozen storage cost")
    ambient_storage: float = Field(default=0.0, ge=0, description="Ambient storage cost")
    thawed_storage: float = Field(default=0.0, ge=0, description="Thawed storage cost")

    model_config = ConfigDict(extra="allow")


class WasteCostBreakdown(BaseModel):
    """Waste and shortage cost components."""
    total: float = Field(..., ge=0, description="Total waste cost")
    shortage_penalty: float = Field(default=0.0, ge=0, description="Penalty for unmet demand")
    expiration_waste: float = Field(default=0.0, ge=0, description="Cost of expired inventory")

    model_config = ConfigDict(extra="allow")


class TotalCostBreakdown(BaseModel):
    """Complete cost breakdown aggregating all components."""
    total_cost: float = Field(..., ge=0, description="Total cost to serve")
    labor: LaborCostBreakdown = Field(..., description="Labor cost breakdown")
    production: ProductionCostBreakdown = Field(..., description="Production cost breakdown")
    transport: TransportCostBreakdown = Field(..., description="Transport cost breakdown")
    holding: HoldingCostBreakdown = Field(..., description="Holding cost breakdown")
    waste: WasteCostBreakdown = Field(..., description="Waste cost breakdown")
    cost_per_unit_delivered: Optional[float] = Field(None, ge=0, description="Average cost per unit delivered")

    model_config = ConfigDict(extra="allow")

    @model_validator(mode='after')
    def validate_total_cost(self):
        """Validate that total_cost equals sum of components."""
        component_sum = (
            self.labor.total +
            self.production.total +
            self.transport.total +
            self.holding.total +
            self.waste.total
        )

        # Allow 1% tolerance for rounding errors
        if abs(self.total_cost - component_sum) > 0.01 * max(self.total_cost, component_sum):
            raise ValueError(
                f"total_cost ({self.total_cost:.2f}) does not match sum of components ({component_sum:.2f})"
            )

        return self


# ============================================================================
# Inventory Structures (Model-Specific)
# ============================================================================

class InventoryStateKey(BaseModel):
    """4-tuple inventory key for SlidingWindowModel (state-based aggregate)."""
    node: str
    product: str
    state: StorageState
    date: Date

    model_config = ConfigDict(extra="forbid", frozen=True)  # Immutable key

    def __hash__(self):
        return hash((self.node, self.product, self.state, self.date))


class InventoryCohortKey(BaseModel):
    """6-tuple inventory key for UnifiedNodeModel (cohort-based age tracking)."""
    node: str
    product: str
    production_date: Date
    state_entry_date: Date
    current_date: Date
    state: StorageState

    model_config = ConfigDict(extra="forbid", frozen=True)  # Immutable key

    def __hash__(self):
        return hash((
            self.node, self.product, self.production_date,
            self.state_entry_date, self.current_date, self.state
        ))


# ============================================================================
# Top-Level Solution Schema
# ============================================================================

class OptimizationSolution(BaseModel):
    """Top-level optimization solution schema.

    This is the PRIMARY interface contract between models and UI.
    ALL optimization models MUST return this structure.

    Required Fields (Core):
        - model_type: Identifies model architecture ("sliding_window" or "unified_node")
        - production_batches: List of production runs
        - labor_hours_by_date: Daily labor hours (ALWAYS LaborHoursBreakdown)
        - shipments: List of shipments with routing and state
        - costs: Complete cost breakdown with all components
        - total_cost: Total objective value
        - fill_rate: Fraction of demand satisfied

    Model-Specific Fields:
        SlidingWindowModel:
            - inventory_state: Dict[(node, product, state, date), quantity]
            - has_aggregate_inventory: True

        UnifiedNodeModel:
            - cohort_inventory: Dict[(node, product, prod_date, state_entry_date, curr_date, state), quantity]
            - use_batch_tracking: True

    Optional Fields (All Models):
        - fefo_batches: Batch-level detail from FEFO post-processing
        - thaw_flows: Frozen→thawed state transitions
        - freeze_flows: Ambient→frozen state transitions
        - shortages: Unmet demand by location-product-date

    Extra Fields:
        Models may add implementation-specific fields (validated via Extra.allow)
    """

    # ========================================================================
    # Core Required Fields (ALL models must provide)
    # ========================================================================

    model_type: Literal["sliding_window", "unified_node"] = Field(
        ...,
        description="Model architecture type for UI dispatch"
    )

    production_batches: List[ProductionBatchResult] = Field(
        ...,
        description="All production runs in the solution"
    )

    labor_hours_by_date: Dict[Date, LaborHoursBreakdown] = Field(
        ...,
        description="Daily labor hours breakdown (ALWAYS nested dict, never simple float)"
    )

    shipments: List[ShipmentResult] = Field(
        ...,
        description="All shipments with routing, state, and truck assignments"
    )

    costs: TotalCostBreakdown = Field(
        ...,
        description="Complete cost breakdown with all components"
    )

    total_cost: float = Field(
        ...,
        ge=0,
        description="Total objective value (must match costs.total_cost)"
    )

    fill_rate: float = Field(
        ...,
        ge=0,
        le=1,
        description="Fraction of demand satisfied (0.0 to 1.0)"
    )

    total_production: float = Field(
        ...,
        ge=0,
        description="Total units produced across all batches"
    )

    total_shortage_units: float = Field(
        default=0.0,
        ge=0,
        description="Total units of unmet demand"
    )

    # ========================================================================
    # Model-Specific Inventory (discriminated union via model_type)
    # ========================================================================

    inventory_state: Optional[Dict[Any, float]] = Field(
        None,
        description="SlidingWindowModel inventory: {(node,product,state,date): quantity} - tuple keys preserved"
    )

    cohort_inventory: Optional[Dict[Any, float]] = Field(
        None,
        description="UnifiedNodeModel inventory: {(node,prod,prod_date,state_entry,curr_date,state): quantity} - tuple keys preserved"
    )

    has_aggregate_inventory: bool = Field(
        default=False,
        description="Flag: True for SlidingWindowModel (uses inventory_state)"
    )

    use_batch_tracking: bool = Field(
        default=False,
        description="Flag: True for UnifiedNodeModel (uses cohort_inventory)"
    )

    # ========================================================================
    # Optional Fields (all models)
    # ========================================================================

    production_by_date_product: Optional[Dict[Any, float]] = Field(
        None,
        description="Production quantity lookup: {(node,product,date): quantity} - tuple keys preserved"
    )

    thaw_flows: Optional[Dict[Any, float]] = Field(
        None,
        description="Frozen→thawed transitions: {(node,product,date): quantity} - tuple keys preserved"
    )

    freeze_flows: Optional[Dict[Any, float]] = Field(
        None,
        description="Ambient→frozen transitions: {(node,product,date): quantity} - tuple keys preserved"
    )

    shortages: Optional[Dict[Any, float]] = Field(
        None,
        description="Unmet demand: {(node,product,date): quantity} - tuple keys preserved"
    )

    truck_assignments: Optional[Dict[Any, Any]] = Field(
        None,
        description="Truck assignments: {(origin,dest,product,date): truck_id} - tuple keys preserved"
    )

    labor_cost_by_date: Optional[Dict[Date, float]] = Field(
        None,
        description="Daily labor costs ($ per day)"
    )

    # ========================================================================
    # FEFO Post-Processing (optional)
    # ========================================================================

    fefo_batches: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Batch-level detail from FEFO allocation (JSON-serializable dicts)"
    )

    fefo_batch_objects: Optional[List[Any]] = Field(
        None,
        description="Batch objects for in-memory use (not JSON-serializable)"
    )

    fefo_batch_inventory: Optional[Dict[str, List[Any]]] = Field(
        None,
        description="Batches grouped by (node,product,state)"
    )

    fefo_shipment_allocations: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Shipment-to-batch allocations from FEFO"
    )

    # ========================================================================
    # Configuration
    # ========================================================================

    model_config = ConfigDict(
        extra="allow",  # CRITICAL: Models can add extra fields
        validate_assignment=True,
        arbitrary_types_allowed=True,  # Allow non-Pydantic objects in extra fields
    )

    # ========================================================================
    # Validation
    # ========================================================================

    @model_validator(mode='after')
    def validate_consistency(self):
        """Cross-field consistency validation."""

        # Validate total_cost matches costs.total_cost
        if abs(self.total_cost - self.costs.total_cost) > 0.01 * max(self.total_cost, self.costs.total_cost, 1):
            raise ValueError(
                f"total_cost ({self.total_cost:.2f}) != costs.total_cost ({self.costs.total_cost:.2f})"
            )

        # Validate total_production matches sum of batches
        batch_production_sum = sum(b.quantity for b in self.production_batches)
        if abs(self.total_production - batch_production_sum) > 0.01 * max(self.total_production, batch_production_sum, 1):
            raise ValueError(
                f"total_production ({self.total_production:.2f}) != sum of batch quantities ({batch_production_sum:.2f})"
            )

        # Validate model_type-specific flags (but allow empty inventory)
        if self.model_type == "sliding_window":
            if not self.has_aggregate_inventory:
                raise ValueError("SlidingWindowModel must set has_aggregate_inventory=True")
            # inventory_state is optional (can be None or empty dict)

        elif self.model_type == "unified_node":
            if not self.use_batch_tracking:
                raise ValueError("UnifiedNodeModel must set use_batch_tracking=True")
            # cohort_inventory is optional (can be None or empty dict)

        return self

    @field_validator('production_batches')
    @classmethod
    def validate_production_batches(cls, v):
        """Ensure production batches are sorted by date."""
        if not v:
            return v  # Empty is OK

        # Sort by date for consistency
        return sorted(v, key=lambda b: (b.date, b.node, b.product))

    @field_validator('shipments')
    @classmethod
    def validate_shipments(cls, v):
        """Ensure shipments have positive quantities."""
        for shipment in v:
            if shipment.quantity <= 0:
                raise ValueError(f"Shipment has non-positive quantity: {shipment}")
        return v

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def get_inventory_format(self) -> Literal["state", "cohort", "none"]:
        """Determine inventory format for UI dispatch."""
        if self.has_aggregate_inventory:
            return "state"
        elif self.use_batch_tracking:
            return "cohort"
        else:
            return "none"

    def to_dict_json_safe(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict (excludes non-serializable fields)."""
        data = self.model_dump(mode='json', exclude={'fefo_batch_objects'})
        return data


# ============================================================================
# Type Aliases for Backward Compatibility
# ============================================================================

# Allow UI code to reference these types without importing multiple modules
ProductionBatch = ProductionBatchResult
Shipment = ShipmentResult
CostBreakdown = TotalCostBreakdown
