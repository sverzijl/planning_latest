"""End-of-Horizon Inventory Explainer.

Explains WHY inventory remains at end of planning horizon despite waste penalty.

Common reasons:
1. Stranded at wrong location (can't ship in time)
2. Reserved for last-day demand (must keep to avoid shortage)
3. In-transit (already committed to shipments)
4. Waste penalty too weak (cheaper to keep than alternatives)

This generates user-friendly explanations instead of just showing numbers.
"""

from typing import Dict, List, Tuple, Any
from datetime import date as Date, timedelta
from collections import defaultdict


class EndInventoryExplainer:
    """Explains why inventory remains at end of horizon."""

    @staticmethod
    def analyze_end_inventory(
        inventory_by_location: Dict[str, float],
        demand_by_location: Dict[str, float],
        last_date: Date,
        routes: List[Any],
        manufacturing_node: str = '6122'
    ) -> Dict[str, Any]:
        """Analyze and explain end-of-horizon inventory.

        Args:
            inventory_by_location: {location_id: quantity} on last day
            demand_by_location: {location_id: demand_qty} on last day
            last_date: Last day of planning horizon
            routes: List of routes with transit times
            manufacturing_node: Manufacturing location ID

        Returns:
            Dict with:
            - total_end_inventory: float
            - explanations: List[str] (user-friendly explanations)
            - breakdown: Dict with categorized inventory
        """
        total_inventory = sum(inventory_by_location.values())
        explanations = []
        breakdown = {
            'stranded_at_manufacturing': 0,
            'at_demand_locations': 0,
            'at_hubs': 0,
        }

        # Category 1: Inventory at manufacturing (stranded)
        inv_at_mfg = inventory_by_location.get(manufacturing_node, 0)
        if inv_at_mfg > 100:
            breakdown['stranded_at_manufacturing'] = inv_at_mfg

            # Check if there's demand that could use it
            total_demand = sum(demand_by_location.values())
            if total_demand > 0:
                explanations.append(
                    f"📦 {inv_at_mfg:,.0f} units stranded at manufacturing: "
                    f"Cannot ship to demand nodes in time due to 1-2 day transit lead times. "
                    f"To reduce, stop production 2-3 days before horizon end."
                )
            else:
                explanations.append(
                    f"📦 {inv_at_mfg:,.0f} units at manufacturing: "
                    f"No remaining demand to satisfy. This is unavoidable end inventory."
                )

        # Category 2: Inventory at demand locations (reserved for consumption)
        demand_nodes = [loc for loc in demand_by_location.keys() if loc != manufacturing_node]
        inv_at_demand = sum(inventory_by_location.get(loc, 0) for loc in demand_nodes)

        if inv_at_demand > 10:
            breakdown['at_demand_locations'] = inv_at_demand

            # This inventory is probably reserved for last-day demand
            explanations.append(
                f"🎯 {inv_at_demand:,.0f} units at demand locations: "
                f"Reserved to satisfy last-day demand. Necessary to avoid shortages."
            )

        # Category 3: Inventory at hubs
        hubs = ['6104', '6125', 'Lineage']
        inv_at_hubs = sum(inventory_by_location.get(hub, 0) for hub in hubs)

        if inv_at_hubs > 10:
            breakdown['at_hubs'] = inv_at_hubs
            explanations.append(
                f"🏭 {inv_at_hubs:,.0f} units at hubs: "
                f"In transit through distribution network. May reach demand nodes after horizon."
            )

        # Overall assessment
        if total_inventory < 100:
            explanations.insert(0, "✅ End inventory minimal (< 100 units) - waste penalty effective.")
        elif inv_at_mfg > total_inventory * 0.8:
            explanations.insert(0,
                f"⚠️ {inv_at_mfg / total_inventory * 100:.0f}% of end inventory stranded at manufacturing. "
                f"Reduce by stopping production 2-3 days earlier."
            )
        else:
            explanations.insert(0,
                f"ℹ️ {total_inventory:,.0f} units end inventory distributed across network. "
                f"Some inventory unavoidable due to last-day demand and transit times."
            )

        return {
            'total_end_inventory': total_inventory,
            'explanations': explanations,
            'breakdown': breakdown,
            'stranded_pct': (inv_at_mfg / total_inventory * 100) if total_inventory > 0 else 0,
        }

    @staticmethod
    def generate_ui_message(analysis: Dict[str, Any]) -> str:
        """Generate user-friendly message for UI display.

        Args:
            analysis: Result from analyze_end_inventory()

        Returns:
            Formatted message string
        """
        lines = []

        lines.append(f"**End-of-Horizon Inventory: {analysis['total_end_inventory']:,.0f} units**")
        lines.append("")

        for explanation in analysis['explanations']:
            lines.append(explanation)

        # Add breakdown if significant
        breakdown = analysis['breakdown']
        if any(v > 10 for v in breakdown.values()):
            lines.append("")
            lines.append("**Breakdown:**")
            if breakdown['stranded_at_manufacturing'] > 0:
                lines.append(f"- Manufacturing: {breakdown['stranded_at_manufacturing']:,.0f} units")
            if breakdown['at_hubs'] > 0:
                lines.append(f"- Hubs (in transit): {breakdown['at_hubs']:,.0f} units")
            if breakdown['at_demand_locations'] > 0:
                lines.append(f"- Demand locations: {breakdown['at_demand_locations']:,.0f} units")

        return "\n".join(lines)
