"""
Pydantic schemas for validated planning data.

This module defines the complete data schema for the planning model,
ensuring type safety and early error detection. All data must pass through
these schemas before reaching the optimization model.

Architecture:
    Raw Excel → Parsers → Pydantic Schemas (VALIDATION) → Optimization Model

Key Principles:
    1. Fail Fast: Validation errors raised at data load time, not solve time
    2. Type Safety: All fields have explicit types and constraints
    3. Cross-Validation: Relationships between entities are validated
    4. Clear Errors: Validation errors include context and suggested fixes
"""

from datetime import date, datetime
from typing import Dict, List, Set, Optional, Tuple
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class ProductID(BaseModel):
    """Product identifier with validation.

    Ensures consistent product ID format throughout the system.
    """
    id: str = Field(..., min_length=1, max_length=200, description="Product SKU or name")
    sku: Optional[str] = Field(None, description="Alternative SKU code")
    name: str = Field(..., min_length=1, description="Product display name")
    units_per_mix: Optional[int] = Field(None, gt=0, description="Units produced per mix/batch (required for mix-based production)")

    @field_validator('id', 'name')
    @classmethod
    def no_whitespace_only(cls, v: str) -> str:
        """Ensure ID and name are not just whitespace."""
        if not v.strip():
            raise ValueError("Product ID/name cannot be whitespace only")
        return v.strip()

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, ProductID):
            return self.id == other.id
        return False


class NodeID(BaseModel):
    """Node identifier with validation."""
    id: str = Field(..., min_length=1, max_length=50, description="Node location ID")
    name: str = Field(..., min_length=1, description="Node display name")

    @field_validator('id')
    @classmethod
    def valid_node_id(cls, v: str) -> str:
        """Validate node ID format."""
        if not v.strip():
            raise ValueError("Node ID cannot be whitespace only")
        return v.strip()

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, NodeID):
            return self.id == other.id
        return False


class DemandEntry(BaseModel):
    """Single demand entry with full validation."""
    node_id: str = Field(..., description="Demand location")
    product_id: str = Field(..., description="Product identifier")
    demand_date: date = Field(..., description="Date when demand occurs")
    quantity: float = Field(..., ge=0, description="Demand quantity (units)")

    @field_validator('quantity')
    @classmethod
    def quantity_reasonable(cls, v: float) -> float:
        """Validate quantity is reasonable (not astronomical or negative)."""
        if v < 0:
            raise ValueError(f"Demand quantity cannot be negative: {v}")
        if v > 1_000_000:
            raise ValueError(f"Demand quantity seems unreasonably large: {v:,.0f} units. Check data.")
        return v

    def to_dict_key(self) -> Tuple[str, str, date]:
        """Convert to dictionary key format for optimization model."""
        return (self.node_id, self.product_id, self.demand_date)


class InventoryEntry(BaseModel):
    """Single inventory entry with validation."""
    node_id: str = Field(..., description="Storage location")
    product_id: str = Field(..., description="Product identifier")
    state: str = Field(..., description="Storage state (ambient/frozen/thawed)")
    quantity: float = Field(..., ge=0, description="Inventory quantity (units)")
    age_days: Optional[int] = Field(None, ge=0, description="Age in days (for shelf life)")

    @field_validator('state')
    @classmethod
    def valid_state(cls, v: str) -> str:
        """Validate storage state."""
        valid_states = {'ambient', 'frozen', 'thawed'}
        if v.lower() not in valid_states:
            raise ValueError(f"Invalid storage state '{v}'. Must be one of: {valid_states}")
        return v.lower()

    @field_validator('quantity')
    @classmethod
    def quantity_reasonable(cls, v: float) -> float:
        """Validate quantity is reasonable."""
        if v < 0:
            raise ValueError(f"Inventory quantity cannot be negative: {v}")
        if v > 10_000_000:
            raise ValueError(f"Inventory quantity seems unreasonably large: {v:,.0f} units. Check data.")
        return v

    def to_dict_key(self) -> Tuple[str, str, str]:
        """Convert to dictionary key format for optimization model."""
        return (self.node_id, self.product_id, self.state)


class ValidatedPlanningData(BaseModel):
    """Complete validated planning dataset.

    This is the single source of truth for all planning data.
    All cross-validation happens here before data reaches the model.
    """
    # Core entities
    products: List[ProductID] = Field(..., min_length=1, description="All products")
    nodes: List[NodeID] = Field(..., min_length=1, description="All nodes")

    # Demand and inventory
    demand_entries: List[DemandEntry] = Field(..., min_length=1, description="Demand forecast")
    inventory_entries: List[InventoryEntry] = Field(default_factory=list, description="Initial inventory")

    # Date range
    planning_start_date: date = Field(..., description="First day of planning horizon")
    planning_end_date: date = Field(..., description="Last day of planning horizon")
    inventory_snapshot_date: Optional[date] = Field(None, description="Date when inventory was measured")

    # Metadata
    data_source: str = Field(..., description="Source file or system")
    loaded_at: datetime = Field(default_factory=datetime.now, description="Timestamp when data was loaded")

    @model_validator(mode='after')
    def validate_cross_references(self):
        """Validate all cross-references between entities."""

        # Build ID sets for fast lookup
        product_ids = {p.id for p in self.products}
        node_ids = {n.id for n in self.nodes}

        # Validate demand references
        invalid_demand = []
        for entry in self.demand_entries:
            errors = []
            if entry.product_id not in product_ids:
                errors.append(f"unknown product '{entry.product_id}'")
            if entry.node_id not in node_ids:
                errors.append(f"unknown node '{entry.node_id}'")
            if entry.demand_date < self.planning_start_date or entry.demand_date > self.planning_end_date:
                errors.append(f"date {entry.demand_date} outside planning horizon")

            if errors:
                invalid_demand.append(f"Demand entry {entry.node_id}/{entry.product_id}/{entry.demand_date}: {', '.join(errors)}")

        if invalid_demand:
            raise ValueError(f"Invalid demand entries found:\n" + "\n".join(invalid_demand[:10]))

        # Validate inventory references
        invalid_inventory = []
        for entry in self.inventory_entries:
            errors = []
            if entry.product_id not in product_ids:
                errors.append(f"unknown product '{entry.product_id}'")
            if entry.node_id not in node_ids:
                errors.append(f"unknown node '{entry.node_id}'")

            if errors:
                invalid_inventory.append(f"Inventory entry {entry.node_id}/{entry.product_id}/{entry.state}: {', '.join(errors)}")

        if invalid_inventory:
            raise ValueError(f"Invalid inventory entries found:\n" + "\n".join(invalid_inventory[:10]))

        # Validate date range
        if self.planning_start_date > self.planning_end_date:
            raise ValueError(f"Planning start date {self.planning_start_date} is after end date {self.planning_end_date}")

        # Validate inventory snapshot date
        if self.inventory_snapshot_date and self.inventory_entries:
            if self.inventory_snapshot_date > self.planning_start_date:
                raise ValueError(
                    f"Inventory snapshot date {self.inventory_snapshot_date} is AFTER planning start {self.planning_start_date}. "
                    f"Initial inventory should be measured before or at planning start."
                )

        return self

    @model_validator(mode='after')
    def validate_product_id_consistency(self):
        """Validate product IDs are used consistently."""

        # Check for product ID type inconsistency (numeric vs string)
        demand_product_ids = {entry.product_id for entry in self.demand_entries}
        inventory_product_ids = {entry.product_id for entry in self.inventory_entries}
        registered_product_ids = {p.id for p in self.products}

        # Products in demand but not in product list
        missing_from_products = demand_product_ids - registered_product_ids
        if missing_from_products:
            sample = list(missing_from_products)[:5]
            raise ValueError(
                f"Found {len(missing_from_products)} product IDs in demand that are not in products list. "
                f"Sample: {sample}. This usually means product IDs are inconsistent between files."
            )

        # Products in inventory but not in product list
        missing_from_products_inv = inventory_product_ids - registered_product_ids
        if missing_from_products_inv:
            sample = list(missing_from_products_inv)[:5]
            raise ValueError(
                f"Found {len(missing_from_products_inv)} product IDs in inventory that are not in products list. "
                f"Sample: {sample}. Check if inventory uses SKU codes while forecast uses product names."
            )

        return self

    def get_demand_dict(self) -> Dict[Tuple[str, str, date], float]:
        """Convert demand to optimization model format."""
        return {entry.to_dict_key(): entry.quantity for entry in self.demand_entries}

    def get_inventory_dict(self) -> Dict[Tuple[str, str, str], float]:
        """Convert inventory to optimization model format."""
        return {entry.to_dict_key(): entry.quantity for entry in self.inventory_entries}

    def get_product_id_set(self) -> Set[str]:
        """Get set of all product IDs."""
        return {p.id for p in self.products}

    def get_node_id_set(self) -> Set[str]:
        """Get set of all node IDs."""
        return {n.id for n in self.nodes}

    def summary(self) -> str:
        """Generate human-readable summary of validated data."""
        total_demand = sum(e.quantity for e in self.demand_entries)
        total_inventory = sum(e.quantity for e in self.inventory_entries)

        return f"""
Validated Planning Data Summary:
  Products: {len(self.products)}
  Nodes: {len(self.nodes)}
  Demand entries: {len(self.demand_entries)} ({total_demand:,.0f} units total)
  Inventory entries: {len(self.inventory_entries)} ({total_inventory:,.0f} units total)
  Planning horizon: {self.planning_start_date} to {self.planning_end_date} ({(self.planning_end_date - self.planning_start_date).days + 1} days)
  Inventory snapshot: {self.inventory_snapshot_date or 'N/A'}
  Data source: {self.data_source}
  Loaded at: {self.loaded_at}
"""


class ValidationError(Exception):
    """Custom exception for validation errors with context."""

    def __init__(self, message: str, context: Optional[Dict] = None):
        self.message = message
        self.context = context or {}
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format error message with context."""
        msg = f"Data Validation Error: {self.message}"
        if self.context:
            msg += "\n\nContext:"
            for key, value in self.context.items():
                msg += f"\n  {key}: {value}"
        return msg
