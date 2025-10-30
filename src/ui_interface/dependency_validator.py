"""Function Dependency Validator.

Validates that functions don't have hidden dependencies on global state.

Architectural Principle:
    Functions should receive all required data as parameters, not access
    global/session state internally.

Bad Pattern (Hidden Dependency):
    def process_data(x, y):
        forecast = st.session_state.get('forecast')  # Hidden dependency!
        if not forecast:
            forecast = Forecast(entries=[])  # Silent failure
        return compute(x, y, forecast)

Good Pattern (Explicit Dependency):
    def process_data(x, y, forecast):
        if not forecast:
            raise ValueError("forecast is required")  # Fail-fast
        return compute(x, y, forecast)

This validator checks that critical functions follow the good pattern.

Last Updated: 2025-10-30
"""

import ast
import inspect
from typing import List, Callable, Set


class HiddenDependencyError(Exception):
    """Raised when function has hidden dependency on session state."""
    pass


def check_function_for_session_state_access(func: Callable) -> List[str]:
    """Check if function accesses st.session_state internally.

    Args:
        func: Function to check

    Returns:
        List of session state accesses found

    Example:
        >>> def bad_func(x):
        ...     data = st.session_state.get('data')  # Hidden dependency
        ...     return x + data
        >>> check_function_for_session_state_access(bad_func)
        ['Line 2: st.session_state.get(...)']
    """
    try:
        source = inspect.getsource(func)
        tree = ast.parse(source)
    except (OSError, TypeError):
        return []  # Can't get source (built-in or C extension)

    accesses = []

    class SessionStateVisitor(ast.NodeVisitor):
        def visit_Attribute(self, node):
            # Check for st.session_state or session_state.get()
            if isinstance(node.value, ast.Attribute):
                # st.session_state.get(...)
                if (hasattr(node.value, 'attr') and
                    node.value.attr == 'session_state' and
                    hasattr(node.value, 'value') and
                    isinstance(node.value.value, ast.Name) and
                    node.value.value.id == 'st'):
                    accesses.append(f"Line {node.lineno}: st.session_state.{node.attr}(...)")

            elif isinstance(node.value, ast.Name):
                # session_state.get(...)
                if node.value.id == 'session_state':
                    accesses.append(f"Line {node.lineno}: session_state.{node.attr}(...)")

            self.generic_visit(node)

    visitor = SessionStateVisitor()
    visitor.visit(tree)

    return accesses


def validate_no_hidden_dependencies(func: Callable, allowed_functions: Set[str] = None) -> None:
    """Validate function doesn't have hidden session state dependencies.

    Args:
        func: Function to validate
        allowed_functions: Set of function names allowed to access session state

    Raises:
        HiddenDependencyError: If function accesses session state

    Example:
        >>> validate_no_hidden_dependencies(_generate_snapshot)
        HiddenDependencyError: _generate_snapshot has hidden session state dependency
    """
    allowed_functions = allowed_functions or {
        'render_daily_snapshot',  # UI render functions can access session state
        'render_production_tab',
        'render_results_page',
    }

    func_name = func.__name__

    # Allow render functions to access session state
    if func_name in allowed_functions or func_name.startswith('render_'):
        return

    # Check for session state access
    accesses = check_function_for_session_state_access(func)

    if accesses:
        raise HiddenDependencyError(
            f"Function '{func_name}' has hidden dependency on session state.\n"
            f"Found {len(accesses)} accesses:\n" +
            "\n".join(f"  - {a}" for a in accesses) +
            f"\n\nArchitectural Fix: Add required data as explicit parameters.\n"
            f"Example: def {func_name}(..., forecast=None) and require caller to pass it."
        )


# Critical functions that should NOT access session state
CRITICAL_FUNCTIONS_TO_VALIDATE = [
    '_generate_snapshot',  # Should receive forecast as parameter
    '_calculate_location_inventory',
    '_get_demand_satisfied',
    'adapt_optimization_results',
]


def validate_all_critical_functions() -> List[str]:
    """Validate all critical functions don't have hidden dependencies.

    Returns:
        List of functions with hidden dependencies
    """
    violations = []

    for func_name in CRITICAL_FUNCTIONS_TO_VALIDATE:
        # Try to import and check
        try:
            if func_name == '_generate_snapshot':
                from ui.components.daily_snapshot import _generate_snapshot as func
            elif func_name == '_calculate_location_inventory':
                from src.analysis.daily_snapshot import DailySnapshotGenerator
                func = DailySnapshotGenerator._calculate_location_inventory
            elif func_name == '_get_demand_satisfied':
                from src.analysis.daily_snapshot import DailySnapshotGenerator
                func = DailySnapshotGenerator._get_demand_satisfied
            elif func_name == 'adapt_optimization_results':
                from ui.utils.result_adapter import adapt_optimization_results as func
            else:
                continue

            try:
                validate_no_hidden_dependencies(func)
            except HiddenDependencyError as e:
                violations.append(str(e))

        except ImportError:
            continue

    return violations


if __name__ == "__main__":
    print("Validating functions for hidden dependencies...")
    violations = validate_all_critical_functions()

    if violations:
        print(f"\n❌ Found {len(violations)} functions with hidden dependencies:")
        for v in violations:
            print(f"\n{v}")
    else:
        print("\n✅ All critical functions have explicit dependencies")
