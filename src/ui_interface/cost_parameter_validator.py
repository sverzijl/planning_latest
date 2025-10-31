"""Cost Parameter Validator - Ensures penalties are correctly configured.

Validates that cost parameters are set appropriately for desired behavior:
1. Waste penalty strong enough to drive end inventory → 0
2. Shortage penalty strong enough to meet demand
3. Relative penalties make economic sense

Architectural Principle:
  Cost parameters encode business priorities
  Validators ensure parameters achieve desired model behavior
"""

from typing import List, Tuple


class CostParameterValidator:
    """Validates cost parameter configuration."""

    @staticmethod
    def validate_waste_penalty_strength(
        waste_multiplier: float,
        production_cost: float,
        shortage_penalty: float,
        desired_behavior: str = "zero_end_inventory"
    ) -> List[str]:
        """Validate waste penalty is strong enough for desired behavior.

        Args:
            waste_multiplier: Waste cost multiplier
            production_cost: Production cost per unit
            shortage_penalty: Shortage penalty per unit
            desired_behavior: 'zero_end_inventory' or 'allow_end_inventory'

        Returns:
            List of validation errors
        """
        errors = []

        waste_penalty_per_unit = waste_multiplier * production_cost
        ratio = shortage_penalty / waste_penalty_per_unit if waste_penalty_per_unit > 0 else float('inf')

        if desired_behavior == "zero_end_inventory":
            # Waste penalty should be >= shortage penalty to truly drive inventory to zero
            if waste_penalty_per_unit < shortage_penalty:
                errors.append(
                    f"Waste penalty (${waste_penalty_per_unit:.2f}/unit) < shortage penalty (${shortage_penalty:.2f}/unit). "
                    f"Model will keep end-of-horizon inventory rather than risk shortages. "
                    f"To achieve zero end inventory, increase waste_cost_multiplier from {waste_multiplier:.1f} to "
                    f"{shortage_penalty / production_cost:.1f} (or higher)."
                )

            # Warn if penalty is much weaker
            if ratio > 3:
                errors.append(
                    f"Waste penalty is {ratio:.1f}× weaker than shortage penalty. "
                    f"End-of-horizon inventory will remain high ({ratio:.1f}× less painful to keep than short)."
                )

        return errors

    @staticmethod
    def validate_penalty_relationships(
        waste_multiplier: float,
        production_cost: float,
        shortage_penalty: float,
        holding_cost_per_day: float
    ) -> List[str]:
        """Validate relative penalty strengths make business sense.

        Args:
            waste_multiplier: Waste cost multiplier
            production_cost: Production cost per unit
            shortage_penalty: Shortage penalty per unit
            holding_cost_per_day: Holding cost per unit per day

        Returns:
            List of validation warnings
        """
        warnings = []

        waste_penalty = waste_multiplier * production_cost

        # Holding cost for 30 days should be less than waste penalty
        holding_30_days = holding_cost_per_day * 30
        if holding_30_days > waste_penalty:
            warnings.append(
                f"Holding for 30 days (${holding_30_days:.2f}) > waste penalty (${waste_penalty:.2f}). "
                f"Model may prefer disposing over holding."
            )

        # Shortage should be most expensive
        if shortage_penalty < waste_penalty:
            warnings.append(
                f"Shortage penalty (${shortage_penalty:.2f}) < waste penalty (${waste_penalty:.2f}). "
                f"Model prefers shortages over waste - usually wrong priority."
            )

        return warnings

    @staticmethod
    def recommend_waste_multiplier(
        production_cost: float,
        shortage_penalty: float,
        target_behavior: str = "zero_end_inventory"
    ) -> Tuple[float, str]:
        """Recommend waste_cost_multiplier for desired behavior.

        Args:
            production_cost: Production cost per unit
            shortage_penalty: Shortage penalty per unit
            target_behavior: Desired end-of-horizon behavior

        Returns:
            (recommended_multiplier, explanation)
        """
        if target_behavior == "zero_end_inventory":
            # Waste penalty should equal or exceed shortage penalty
            recommended = shortage_penalty / production_cost
            explanation = (
                f"To drive end inventory → 0, waste penalty must be ≥ shortage penalty. "
                f"Recommended: {recommended:.1f} (gives ${shortage_penalty:.2f}/unit, equal to shortage)"
            )
            return recommended, explanation

        elif target_behavior == "minimal_end_inventory":
            # Waste penalty should be 50-75% of shortage
            recommended = (shortage_penalty * 0.65) / production_cost
            explanation = (
                f"To minimize (but allow some) end inventory, use 50-75% of shortage penalty. "
                f"Recommended: {recommended:.1f} (gives ${recommended * production_cost:.2f}/unit)"
            )
            return recommended, explanation

        else:
            # Allow end inventory (waste penalty < holding costs)
            recommended = 1.0
            explanation = "To allow end inventory, use minimal penalty (~1.0 multiplier)"
            return recommended, explanation


def validate_cost_parameters_comprehensive(cost_structure) -> List[str]:
    """Run all cost parameter validations.

    Args:
        cost_structure: CostStructure instance

    Returns:
        List of all validation errors and warnings
    """
    issues = []

    waste_mult = cost_structure.waste_cost_multiplier or 0
    prod_cost = cost_structure.production_cost_per_unit or 1.3
    shortage_penalty = cost_structure.shortage_penalty_per_unit or 10.0

    # Get holding cost if available
    holding_cost = getattr(cost_structure, 'storage_cost_ambient_per_unit_day', 0) or 0

    # Validate waste penalty strength
    issues.extend(
        CostParameterValidator.validate_waste_penalty_strength(
            waste_mult, prod_cost, shortage_penalty, desired_behavior="zero_end_inventory"
        )
    )

    # Validate penalty relationships
    issues.extend(
        CostParameterValidator.validate_penalty_relationships(
            waste_mult, prod_cost, shortage_penalty, holding_cost
        )
    )

    return issues
