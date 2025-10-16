"""Production labeling report generator.

Generates work orders showing which quantities need frozen vs ambient labeling,
based on the optimization model's routing decisions.
"""

from dataclasses import dataclass
from datetime import date as Date
from typing import Dict, List, Tuple
from collections import defaultdict
import pandas as pd


@dataclass
class LabelingRequirement:
    """Labeling requirement for a production batch."""
    production_date: Date
    product_id: str
    frozen_quantity: float
    ambient_quantity: float
    total_quantity: float
    frozen_destinations: List[str]
    ambient_destinations: List[str]

    @property
    def needs_frozen_labels(self) -> bool:
        """Check if any frozen labeling is required."""
        return self.frozen_quantity > 0.01

    @property
    def needs_ambient_labels(self) -> bool:
        """Check if any ambient labeling is required."""
        return self.ambient_quantity > 0.01

    @property
    def frozen_percentage(self) -> float:
        """Percentage of production requiring frozen labels."""
        if self.total_quantity == 0:
            return 0.0
        return (self.frozen_quantity / self.total_quantity) * 100

    def to_dict(self) -> Dict:
        """Convert to dictionary for DataFrame export."""
        return {
            'Production Date': self.production_date,
            'Product': self.product_id,
            'Total Quantity': int(self.total_quantity),
            'Frozen Labels': int(self.frozen_quantity),
            'Ambient Labels': int(self.ambient_quantity),
            'Frozen %': f"{self.frozen_percentage:.1f}%",
            'Frozen Destinations': ', '.join(self.frozen_destinations) if self.frozen_destinations else '-',
            'Ambient Destinations': ', '.join(self.ambient_destinations) if self.ambient_destinations else '-',
            'Label Notes': self._get_label_notes()
        }

    def _get_label_notes(self) -> str:
        """Generate labeling instructions."""
        if self.needs_frozen_labels and self.needs_ambient_labels:
            return f"SPLIT BATCH: {int(self.frozen_quantity)} frozen, {int(self.ambient_quantity)} ambient"
        elif self.needs_frozen_labels:
            return "ALL FROZEN LABELS"
        elif self.needs_ambient_labels:
            return "ALL AMBIENT LABELS"
        else:
            return "NO SHIPMENTS"


class ProductionLabelingReportGenerator:
    """Generate production labeling reports from optimization results."""

    def __init__(self, optimization_result: Dict):
        """Initialize with optimization solution.

        Args:
            optimization_result: Dictionary from IntegratedProductionDistributionModel.extract_solution()
        """
        self.result = optimization_result
        self.shipments = optimization_result.get('shipments_by_leg_product_date', {})
        self.leg_states = {}  # Will be populated if available

    def set_leg_states(self, leg_arrival_state: Dict[Tuple[str, str], str]):
        """Set leg state mapping (frozen/ambient).

        Args:
            leg_arrival_state: Dict mapping (origin, dest) to 'frozen' or 'ambient'
        """
        self.leg_states = leg_arrival_state

    def generate_labeling_requirements(self) -> List[LabelingRequirement]:
        """Generate labeling requirements for all production.

        Returns:
            List of LabelingRequirement objects, one per (date, product) combination
        """
        # Aggregate shipments by production date and product
        # Key: (prod_date, product_id)
        # Value: {frozen_qty, ambient_qty, frozen_dests, ambient_dests}
        aggregated = defaultdict(lambda: {
            'frozen': 0.0,
            'ambient': 0.0,
            'frozen_dests': set(),
            'ambient_dests': set()
        })

        # Process all shipments from manufacturing (6122_Storage)
        for (leg, product_id, delivery_date), qty in self.shipments.items():
            if qty <= 0.01:
                continue

            origin, dest = leg
            if origin != '6122_Storage':
                continue  # Only care about shipments from manufacturing

            # Determine production date (need to look at production batches or assume delivery_date mapping)
            # For simplicity, use delivery_date minus transit time as approximation
            # In real implementation, should extract from cohort shipments
            # For now, use a simplified mapping - this is a placeholder
            prod_date = delivery_date  # FIXME: Should extract actual prod_date from cohort tracking

            # Determine if frozen or ambient
            is_frozen = self.leg_states.get(leg, 'ambient') == 'frozen'

            key = (prod_date, product_id)
            if is_frozen:
                aggregated[key]['frozen'] += qty
                aggregated[key]['frozen_dests'].add(dest)
            else:
                aggregated[key]['ambient'] += qty
                aggregated[key]['ambient_dests'].add(dest)

        # Convert to LabelingRequirement objects
        requirements = []
        for (prod_date, product_id), data in aggregated.items():
            frozen_qty = data['frozen']
            ambient_qty = data['ambient']
            total = frozen_qty + ambient_qty

            if total > 0.01:  # Only include if there's actual production
                req = LabelingRequirement(
                    production_date=prod_date,
                    product_id=product_id,
                    frozen_quantity=frozen_qty,
                    ambient_quantity=ambient_qty,
                    total_quantity=total,
                    frozen_destinations=sorted(list(data['frozen_dests'])),
                    ambient_destinations=sorted(list(data['ambient_dests']))
                )
                requirements.append(req)

        # Sort by date then product
        requirements.sort(key=lambda r: (r.production_date, r.product_id))
        return requirements

    def generate_report_dataframe(self) -> pd.DataFrame:
        """Generate pandas DataFrame report.

        Returns:
            DataFrame with production labeling requirements
        """
        requirements = self.generate_labeling_requirements()
        data = [req.to_dict() for req in requirements]
        return pd.DataFrame(data)

    def generate_daily_work_orders(self, target_date: Date) -> List[LabelingRequirement]:
        """Generate work orders for a specific production date.

        Args:
            target_date: Production date to generate work orders for

        Returns:
            List of LabelingRequirement objects for that date
        """
        all_requirements = self.generate_labeling_requirements()
        return [req for req in all_requirements if req.production_date == target_date]

    def export_to_excel(self, output_path: str):
        """Export labeling report to Excel.

        Args:
            output_path: Path to output Excel file
        """
        df = self.generate_report_dataframe()
        df.to_excel(output_path, index=False, sheet_name='Production Labeling')

    def print_summary(self):
        """Print summary of labeling requirements."""
        requirements = self.generate_labeling_requirements()

        print("\n" + "=" * 80)
        print("PRODUCTION LABELING SUMMARY")
        print("=" * 80)

        total_frozen = sum(req.frozen_quantity for req in requirements)
        total_ambient = sum(req.ambient_quantity for req in requirements)
        total_production = total_frozen + total_ambient

        print(f"\nTotal Production: {total_production:,.0f} units")
        print(f"  - Frozen Labels:  {total_frozen:,.0f} units ({total_frozen/total_production*100:.1f}%)")
        print(f"  - Ambient Labels: {total_ambient:,.0f} units ({total_ambient/total_production*100:.1f}%)")

        split_batches = [req for req in requirements if req.needs_frozen_labels and req.needs_ambient_labels]
        print(f"\nBatches requiring split labeling: {len(split_batches)}")

        if split_batches:
            print("\nSplit Batch Details:")
            for req in split_batches[:10]:  # Show first 10
                print(f"  {req.production_date} - {req.product_id}:")
                print(f"    {req.frozen_quantity:,.0f} frozen → {', '.join(req.frozen_destinations)}")
                print(f"    {req.ambient_quantity:,.0f} ambient → {', '.join(req.ambient_destinations)}")
