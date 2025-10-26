"""Solve file serialization and deserialization.

This module handles converting WorkflowResult objects to/from JSON format for
persistent storage on the file system.
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from ..workflows.base_workflow import WorkflowResult, WorkflowType
from ..optimization.solution import PyomoSolution

logger = logging.getLogger(__name__)


class SolveFile:
    """Handles serialization/deserialization of solve results to/from JSON files.

    File Format:
        {
            "workflow_type": "initial",
            "solve_timestamp": "2025-10-26T06:45:00",
            "success": true,
            "solve_time_seconds": 234.5,
            "objective_value": 125430.50,
            "mip_gap": 0.008,
            "solver_status": "ok",
            "solver_message": "Optimal solution found",
            "metadata": {...},
            "solution_data": {
                "variable_values": {...},
                "constraint_duals": {...},
                ...
            }
        }

    Example Usage:
        ```python
        # Save a result
        solve_file = SolveFile(file_path="solves/2025/wk43/initial_20251026_0645.json")
        solve_file.save(workflow_result)

        # Load a result
        loaded_result = solve_file.load()
        ```
    """

    def __init__(self, file_path: Path | str):
        """Initialize SolveFile.

        Args:
            file_path: Path to JSON file for save/load operations
        """
        self.file_path = Path(file_path)

    def save(self, result: WorkflowResult) -> None:
        """Save WorkflowResult to JSON file.

        Args:
            result: WorkflowResult to save

        Raises:
            IOError: If file cannot be written
        """
        logger.info(f"Saving solve result to {self.file_path}")

        # Create parent directory if it doesn't exist
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dictionary
        data = self._result_to_dict(result)

        # Write to file
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2, default=self._json_serializer)

        logger.info(f"Successfully saved solve result ({len(data)} keys)")

    def load(self) -> WorkflowResult:
        """Load WorkflowResult from JSON file.

        Returns:
            Loaded WorkflowResult

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        logger.info(f"Loading solve result from {self.file_path}")

        if not self.file_path.exists():
            raise FileNotFoundError(f"Solve file not found: {self.file_path}")

        # Read from file
        with open(self.file_path, 'r') as f:
            data = json.load(f)

        # Convert to WorkflowResult
        result = self._dict_to_result(data)

        logger.info(f"Successfully loaded {result.workflow_type.value} solve result")
        return result

    def exists(self) -> bool:
        """Check if solve file exists.

        Returns:
            True if file exists, False otherwise
        """
        return self.file_path.exists()

    def _result_to_dict(self, result: WorkflowResult) -> Dict[str, Any]:
        """Convert WorkflowResult to dictionary for JSON serialization.

        Args:
            result: WorkflowResult to convert

        Returns:
            Dictionary representation
        """
        data = {
            "workflow_type": result.workflow_type.value,
            "solve_timestamp": result.solve_timestamp.isoformat(),
            "success": result.success,
            "solve_time_seconds": result.solve_time_seconds,
            "objective_value": result.objective_value,
            "mip_gap": result.mip_gap,
            "solver_status": result.solver_status,
            "solver_message": result.solver_message,
            "metadata": result.metadata,
            "error_message": result.error_message,
        }

        # Serialize solution if present
        if result.solution:
            data["solution_data"] = self._solution_to_dict(result.solution)
        else:
            data["solution_data"] = None

        return data

    def _dict_to_result(self, data: Dict[str, Any]) -> WorkflowResult:
        """Convert dictionary to WorkflowResult.

        Args:
            data: Dictionary from JSON file

        Returns:
            WorkflowResult object
        """
        # Parse workflow type
        workflow_type = WorkflowType(data["workflow_type"])

        # Parse timestamp
        solve_timestamp = datetime.fromisoformat(data["solve_timestamp"])

        # Parse solution if present
        solution = None
        if data.get("solution_data"):
            solution = self._dict_to_solution(data["solution_data"])

        return WorkflowResult(
            workflow_type=workflow_type,
            solve_timestamp=solve_timestamp,
            solution=solution,
            success=data["success"],
            solve_time_seconds=data.get("solve_time_seconds"),
            objective_value=data.get("objective_value"),
            mip_gap=data.get("mip_gap"),
            solver_status=data.get("solver_status"),
            solver_message=data.get("solver_message"),
            metadata=data.get("metadata", {}),
            error_message=data.get("error_message"),
        )

    def _solution_to_dict(self, solution: PyomoSolution) -> Dict[str, Any]:
        """Convert PyomoSolution to dictionary.

        Args:
            solution: PyomoSolution to serialize

        Returns:
            Dictionary representation
        """
        # Extract variable values
        variable_values = {}
        if hasattr(solution, 'variables') and solution.variables:
            for var_name, var_data in solution.variables.items():
                # Convert to serializable format
                if isinstance(var_data, dict):
                    variable_values[var_name] = {
                        str(k): v for k, v in var_data.items()
                    }
                else:
                    variable_values[var_name] = var_data

        return {
            "objective_value": solution.objective_value,
            "solver_status": solution.solver_status,
            "solver_message": solution.solver_message,
            "solve_time": solution.solve_time,
            "mip_gap": solution.mip_gap,
            "variable_values": variable_values,
            # Note: Full solution object attributes may be added here
            # as needed for warmstart and analysis
        }

    def _dict_to_solution(self, data: Dict[str, Any]) -> PyomoSolution:
        """Convert dictionary to PyomoSolution.

        Args:
            data: Dictionary from JSON

        Returns:
            PyomoSolution object

        Note:
            This creates a partial PyomoSolution with key attributes.
            The full Pyomo model is not reconstructed (not needed for warmstart).
        """
        solution = PyomoSolution(
            model=None,  # Model not stored in file
            solver_results=None,  # Results not stored in file
        )

        solution.objective_value = data.get("objective_value")
        solution.solver_status = data.get("solver_status")
        solution.solver_message = data.get("solver_message")
        solution.solve_time = data.get("solve_time")
        solution.mip_gap = data.get("mip_gap")
        solution.variables = data.get("variable_values", {})

        return solution

    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for non-standard types.

        Args:
            obj: Object to serialize

        Returns:
            Serializable representation

        Raises:
            TypeError: If object type not supported
        """
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
