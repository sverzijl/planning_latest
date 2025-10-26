"""Repository for managing solve files on the file system.

This module provides high-level operations for storing, retrieving, and discovering
solve results organized in a hierarchical folder structure.

Folder Structure:
    solves/
    ├── 2025/
    │   ├── wk43/
    │   │   ├── initial_20251021_0830.json
    │   │   ├── daily_20251021_0615.json
    │   │   ├── daily_20251022_0610.json
    │   │   ├── daily_20251023_0608.json
    │   │   ├── ...
    │   │   └── weekly_20251027_0730.json
    │   └── wk44/
    │       ├── daily_20251028_0612.json
    │       └── ...
    └── 2026/
        └── ...
"""

from datetime import datetime, date as Date
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging
from dataclasses import dataclass

from .solve_file import SolveFile
from ..workflows.base_workflow import WorkflowResult, WorkflowType

logger = logging.getLogger(__name__)


@dataclass
class SolveMetadata:
    """Metadata for a solve file (without loading full solution).

    Attributes:
        file_path: Path to solve file
        workflow_type: Type of workflow
        solve_timestamp: When solve was executed
        success: Whether solve was successful
        objective_value: Objective value (if successful)
        week_number: ISO week number
        year: Year
    """
    file_path: Path
    workflow_type: WorkflowType
    solve_timestamp: datetime
    success: bool
    objective_value: Optional[float]
    week_number: int
    year: int


class SolveRepository:
    """Manages solve file storage and retrieval.

    The repository organizes solve files in a hierarchical structure:
    - solves/{year}/wk{week}/{workflow_type}_{YYYYMMDD}_{HHMM}.json

    This enables:
    - Easy discovery of solves by date, week, or type
    - Automatic cleanup of old solves
    - Fast lookup of most recent solve for warmstart

    Example Usage:
        ```python
        repo = SolveRepository(base_path="solves")

        # Save a solve result
        repo.save(workflow_result)

        # Get most recent solve of any type
        latest = repo.get_latest_solve()

        # Get most recent Weekly solve
        latest_weekly = repo.get_latest_solve(workflow_type=WorkflowType.WEEKLY)

        # Get all solves for a specific week
        week_solves = repo.get_solves_for_week(year=2025, week=43)

        # List all available solves
        all_solves = repo.list_all_solves()
        ```
    """

    def __init__(self, base_path: Path | str = "solves"):
        """Initialize SolveRepository.

        Args:
            base_path: Base directory for solve storage (default: "solves")
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized SolveRepository at {self.base_path}")

    def save(self, result: WorkflowResult) -> Path:
        """Save a solve result to the repository.

        Args:
            result: WorkflowResult to save

        Returns:
            Path where result was saved

        Raises:
            ValueError: If result is invalid
        """
        if not result.success and result.solution is None:
            logger.warning(
                f"Saving failed solve result "
                f"({result.workflow_type.value}, {result.error_message})"
            )

        # Generate file path
        file_path = self._generate_file_path(
            workflow_type=result.workflow_type,
            timestamp=result.solve_timestamp
        )

        # Save to file
        solve_file = SolveFile(file_path)
        solve_file.save(result)

        logger.info(f"Saved {result.workflow_type.value} solve to {file_path}")
        return file_path

    def load(self, file_path: Path | str) -> WorkflowResult:
        """Load a solve result from file.

        Args:
            file_path: Path to solve file

        Returns:
            Loaded WorkflowResult

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        solve_file = SolveFile(file_path)
        return solve_file.load()

    def get_latest_solve(
        self,
        workflow_type: Optional[WorkflowType] = None,
        successful_only: bool = True
    ) -> Optional[WorkflowResult]:
        """Get the most recent solve result.

        Args:
            workflow_type: Filter by workflow type (None = any type)
            successful_only: Only return successful solves (default: True)

        Returns:
            Most recent WorkflowResult, or None if no solves found
        """
        solves = self.list_all_solves(
            workflow_type=workflow_type,
            successful_only=successful_only
        )

        if not solves:
            return None

        # Sort by timestamp (most recent first)
        solves.sort(key=lambda s: s.solve_timestamp, reverse=True)
        latest_metadata = solves[0]

        # Load and return full result
        return self.load(latest_metadata.file_path)

    def get_solves_for_week(
        self,
        year: int,
        week: int,
        workflow_type: Optional[WorkflowType] = None
    ) -> List[SolveMetadata]:
        """Get all solves for a specific week.

        Args:
            year: Year (e.g., 2025)
            week: ISO week number (1-53)
            workflow_type: Filter by workflow type (None = all types)

        Returns:
            List of SolveMetadata for the specified week
        """
        week_dir = self.base_path / str(year) / f"wk{week:02d}"

        if not week_dir.exists():
            return []

        # Find all JSON files in week directory
        solves = []
        for file_path in week_dir.glob("*.json"):
            try:
                metadata = self._extract_metadata(file_path)

                # Filter by workflow type if specified
                if workflow_type and metadata.workflow_type != workflow_type:
                    continue

                solves.append(metadata)

            except Exception as e:
                logger.warning(f"Failed to load metadata from {file_path}: {e}")
                continue

        # Sort by timestamp
        solves.sort(key=lambda s: s.solve_timestamp, reverse=True)
        return solves

    def list_all_solves(
        self,
        workflow_type: Optional[WorkflowType] = None,
        successful_only: bool = False,
        limit: Optional[int] = None
    ) -> List[SolveMetadata]:
        """List all solves in the repository.

        Args:
            workflow_type: Filter by workflow type (None = all types)
            successful_only: Only include successful solves (default: False)
            limit: Maximum number of solves to return (None = all)

        Returns:
            List of SolveMetadata, sorted by timestamp (most recent first)
        """
        solves = []

        # Recursively find all JSON files
        for file_path in self.base_path.rglob("*.json"):
            try:
                metadata = self._extract_metadata(file_path)

                # Apply filters
                if workflow_type and metadata.workflow_type != workflow_type:
                    continue

                if successful_only and not metadata.success:
                    continue

                solves.append(metadata)

            except Exception as e:
                logger.warning(f"Failed to load metadata from {file_path}: {e}")
                continue

        # Sort by timestamp (most recent first)
        solves.sort(key=lambda s: s.solve_timestamp, reverse=True)

        # Apply limit
        if limit:
            solves = solves[:limit]

        return solves

    def delete_old_solves(
        self,
        keep_latest_n: int = 100,
        workflow_type: Optional[WorkflowType] = None
    ) -> int:
        """Delete old solve files, keeping only the N most recent.

        Args:
            keep_latest_n: Number of most recent solves to keep (default: 100)
            workflow_type: Only delete solves of this type (None = all types)

        Returns:
            Number of files deleted
        """
        logger.info(
            f"Cleaning up old solves (keeping latest {keep_latest_n} "
            f"of type {workflow_type.value if workflow_type else 'all'})"
        )

        # Get all solves
        all_solves = self.list_all_solves(workflow_type=workflow_type)

        # Determine which to delete
        to_delete = all_solves[keep_latest_n:]

        # Delete files
        deleted_count = 0
        for metadata in to_delete:
            try:
                metadata.file_path.unlink()
                deleted_count += 1
                logger.debug(f"Deleted old solve: {metadata.file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete {metadata.file_path}: {e}")

        logger.info(f"Deleted {deleted_count} old solve files")
        return deleted_count

    def _generate_file_path(
        self,
        workflow_type: WorkflowType,
        timestamp: datetime
    ) -> Path:
        """Generate file path for a solve result.

        Format: solves/{year}/wk{week}/{workflow_type}_{YYYYMMDD}_{HHMM}.json

        Args:
            workflow_type: Type of workflow
            timestamp: Solve timestamp

        Returns:
            Path object for file
        """
        # Get ISO week number
        year, week, _ = timestamp.isocalendar()

        # Create directory structure
        week_dir = self.base_path / str(year) / f"wk{week:02d}"
        week_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        date_str = timestamp.strftime("%Y%m%d")
        time_str = timestamp.strftime("%H%M")
        filename = f"{workflow_type.value}_{date_str}_{time_str}.json"

        return week_dir / filename

    def _extract_metadata(self, file_path: Path) -> SolveMetadata:
        """Extract metadata from a solve file without loading full solution.

        Args:
            file_path: Path to solve file

        Returns:
            SolveMetadata object
        """
        import json

        # Read just the metadata (not full solution)
        with open(file_path, 'r') as f:
            data = json.load(f)

        workflow_type = WorkflowType(data["workflow_type"])
        solve_timestamp = datetime.fromisoformat(data["solve_timestamp"])
        year, week, _ = solve_timestamp.isocalendar()

        return SolveMetadata(
            file_path=file_path,
            workflow_type=workflow_type,
            solve_timestamp=solve_timestamp,
            success=data["success"],
            objective_value=data.get("objective_value"),
            week_number=week,
            year=year,
        )
