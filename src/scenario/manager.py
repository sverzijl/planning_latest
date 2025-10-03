"""Scenario manager for saving, loading, and comparing planning scenarios.

This module provides the ScenarioManager class for managing multiple planning scenarios,
enabling save/load/compare workflows for "what-if" analysis.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import pickle
import json
import uuid
import pandas as pd
from copy import deepcopy


@dataclass
class Scenario:
    """A saved planning scenario with inputs, configuration, and results.

    Attributes:
        id: Unique identifier (UUID)
        name: User-provided name
        description: Optional user notes
        created_at: Creation timestamp
        modified_at: Last modification timestamp

        Input data (snapshot at time of scenario creation):
        forecast_data: Forecast DataFrame or serialized forecast
        labor_calendar: LaborCalendar object
        truck_schedules: List of TruckSchedule objects
        cost_parameters: Cost structure dict
        locations: List of Location objects
        routes: List of Route objects
        manufacturing_site: ManufacturingSite object

        Planning configuration:
        planning_mode: "heuristic" or "optimization"
        optimization_config: Solver settings if optimization mode

        Results (if planning was run):
        planning_results: Heuristic planning results
        optimization_results: Optimization results (OptimizationResult object)

        Computed metrics (for quick comparison):
        total_cost: Total cost to serve
        labor_cost: Labor cost component
        production_cost: Production cost component
        transport_cost: Transport cost component
        waste_cost: Waste cost component
        demand_satisfaction_pct: Percentage of demand satisfied
        total_production_units: Total units produced
        planning_time_seconds: Time taken to run planning

        Organization:
        tags: List of tags for filtering/grouping
    """
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)

    # Input data
    forecast_data: Optional[Any] = None
    labor_calendar: Optional[Any] = None
    truck_schedules: Optional[List[Any]] = None
    cost_parameters: Optional[Dict[str, float]] = None
    locations: Optional[List[Any]] = None
    routes: Optional[List[Any]] = None
    manufacturing_site: Optional[Any] = None

    # Planning configuration
    planning_mode: Optional[str] = None  # "heuristic" or "optimization"
    optimization_config: Optional[Dict[str, Any]] = None

    # Results
    planning_results: Optional[Any] = None  # Heuristic results
    optimization_results: Optional[Any] = None  # Optimization results

    # Computed metrics
    total_cost: Optional[float] = None
    labor_cost: Optional[float] = None
    production_cost: Optional[float] = None
    transport_cost: Optional[float] = None
    waste_cost: Optional[float] = None
    demand_satisfaction_pct: Optional[float] = None
    total_production_units: Optional[int] = None
    planning_time_seconds: Optional[float] = None

    # Organization
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert scenario to dictionary (for JSON serialization)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Scenario':
        """Create scenario from dictionary."""
        # Convert datetime strings back to datetime objects
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('modified_at'), str):
            data['modified_at'] = datetime.fromisoformat(data['modified_at'])
        return cls(**data)


class ScenarioManager:
    """Manages scenario persistence and retrieval.

    Handles saving, loading, comparing, and exporting planning scenarios.
    Uses file-based storage with pickle for full object serialization.

    Storage structure:
        {storage_dir}/
            {scenario_id}.pkl  - Pickled scenario objects
            index.json         - Metadata index for fast listing

    Example:
        >>> manager = ScenarioManager()
        >>>
        >>> # Save a scenario
        >>> scenario = manager.save_scenario(
        ...     name="Baseline Q1 2025",
        ...     description="No overtime, standard routing",
        ...     forecast_data=forecast,
        ...     planning_results=results,
        ...     tags=["baseline", "Q1"]
        ... )
        >>>
        >>> # List scenarios
        >>> scenarios = manager.list_scenarios(tags=["baseline"])
        >>>
        >>> # Load a scenario
        >>> loaded = manager.load_scenario(scenario.id)
        >>>
        >>> # Compare scenarios
        >>> comparison = manager.compare_scenarios([id1, id2, id3])
    """

    def __init__(self, storage_dir: str = ".scenarios"):
        """Initialize scenario manager.

        Args:
            storage_dir: Directory for storing scenario files (default: .scenarios)
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.index_file = self.storage_dir / "index.json"

        # Load or create index
        self._load_index()

    def _load_index(self) -> None:
        """Load scenario index from disk."""
        if self.index_file.exists():
            with open(self.index_file, 'r') as f:
                self._index = json.load(f)
        else:
            self._index = {}
            # Save empty index file
            self._save_index()

    def _save_index(self) -> None:
        """Save scenario index to disk."""
        with open(self.index_file, 'w') as f:
            json.dump(self._index, f, indent=2, default=str)

    def _update_index(self, scenario: Scenario) -> None:
        """Update index with scenario metadata."""
        self._index[scenario.id] = {
            'id': scenario.id,
            'name': scenario.name,
            'description': scenario.description,
            'created_at': scenario.created_at.isoformat(),
            'modified_at': scenario.modified_at.isoformat(),
            'tags': scenario.tags,
            'planning_mode': scenario.planning_mode,
            'total_cost': scenario.total_cost,
            'demand_satisfaction_pct': scenario.demand_satisfaction_pct,
        }
        self._save_index()

    def _remove_from_index(self, scenario_id: str) -> None:
        """Remove scenario from index."""
        if scenario_id in self._index:
            del self._index[scenario_id]
            self._save_index()

    def _save_to_file(self, scenario: Scenario) -> None:
        """Save scenario to pickle file."""
        file_path = self.storage_dir / f"{scenario.id}.pkl"
        with open(file_path, 'wb') as f:
            pickle.dump(scenario, f)

    def _load_from_file(self, scenario_id: str) -> Scenario:
        """Load scenario from pickle file."""
        file_path = self.storage_dir / f"{scenario_id}.pkl"
        if not file_path.exists():
            raise FileNotFoundError(f"Scenario {scenario_id} not found")

        with open(file_path, 'rb') as f:
            return pickle.load(f)

    def save_scenario(
        self,
        name: str,
        description: str = "",
        forecast_data: Optional[Any] = None,
        labor_calendar: Optional[Any] = None,
        truck_schedules: Optional[List[Any]] = None,
        cost_parameters: Optional[Dict[str, float]] = None,
        locations: Optional[List[Any]] = None,
        routes: Optional[List[Any]] = None,
        manufacturing_site: Optional[Any] = None,
        planning_mode: Optional[str] = None,
        optimization_config: Optional[Dict[str, Any]] = None,
        planning_results: Optional[Any] = None,
        optimization_results: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> Scenario:
        """Save current state as a named scenario.

        Args:
            name: Scenario name (required)
            description: Optional description/notes
            forecast_data: Forecast data (DataFrame or Forecast object)
            labor_calendar: LaborCalendar object
            truck_schedules: List of TruckSchedule objects
            cost_parameters: Cost structure dictionary
            locations: List of Location objects
            routes: List of Route objects
            manufacturing_site: ManufacturingSite object
            planning_mode: "heuristic" or "optimization"
            optimization_config: Solver configuration if optimization mode
            planning_results: Results from heuristic planning
            optimization_results: Results from optimization (OptimizationResult)
            tags: List of tags for organization
            **kwargs: Additional metadata fields

        Returns:
            Saved Scenario object with generated ID

        Example:
            >>> scenario = manager.save_scenario(
            ...     name="High Demand Q1",
            ...     description="Forecast increased by 20%",
            ...     forecast_data=adjusted_forecast,
            ...     optimization_results=opt_result,
            ...     tags=["high-demand", "Q1", "optimization"]
            ... )
        """
        # Generate unique ID
        scenario_id = str(uuid.uuid4())

        # Extract metrics from results
        total_cost = None
        labor_cost = None
        production_cost = None
        transport_cost = None
        waste_cost = None
        demand_satisfaction_pct = None
        total_production_units = None
        planning_time_seconds = None

        # Try to extract from optimization results
        if optimization_results is not None:
            if hasattr(optimization_results, 'objective_value'):
                total_cost = optimization_results.objective_value
            if hasattr(optimization_results, 'solve_time_seconds'):
                planning_time_seconds = optimization_results.solve_time_seconds
            if hasattr(optimization_results, 'metadata'):
                metadata = optimization_results.metadata
                labor_cost = metadata.get('labor_cost')
                production_cost = metadata.get('production_cost')
                transport_cost = metadata.get('transport_cost')
                waste_cost = metadata.get('waste_cost')
                demand_satisfaction_pct = metadata.get('demand_satisfaction_pct')
                total_production_units = metadata.get('total_production_units')

        # Try to extract from heuristic results (cost_breakdown)
        elif planning_results is not None:
            if hasattr(planning_results, 'total_cost'):
                total_cost = planning_results.total_cost
            if hasattr(planning_results, 'labor'):
                labor_cost = planning_results.labor.total_cost
            if hasattr(planning_results, 'production'):
                production_cost = planning_results.production.total_cost
            if hasattr(planning_results, 'transport'):
                transport_cost = planning_results.transport.total_cost
            if hasattr(planning_results, 'waste'):
                waste_cost = planning_results.waste.total_cost

        # Override with explicit kwargs if provided
        total_cost = kwargs.get("total_cost", total_cost)
        labor_cost = kwargs.get("labor_cost", labor_cost)
        production_cost = kwargs.get("production_cost", production_cost)
        transport_cost = kwargs.get("transport_cost", transport_cost)
        waste_cost = kwargs.get("waste_cost", waste_cost)
        demand_satisfaction_pct = kwargs.get("demand_satisfaction_pct", demand_satisfaction_pct)
        total_production_units = kwargs.get("total_production_units", total_production_units)
        planning_time_seconds = kwargs.get("planning_time_seconds", planning_time_seconds)

        # Create scenario
        scenario = Scenario(
            id=scenario_id,
            name=name,
            description=description,
            forecast_data=deepcopy(forecast_data) if forecast_data is not None else None,
            labor_calendar=deepcopy(labor_calendar) if labor_calendar is not None else None,
            truck_schedules=deepcopy(truck_schedules) if truck_schedules is not None else None,
            cost_parameters=deepcopy(cost_parameters) if cost_parameters is not None else None,
            locations=deepcopy(locations) if locations is not None else None,
            routes=deepcopy(routes) if routes is not None else None,
            manufacturing_site=deepcopy(manufacturing_site) if manufacturing_site is not None else None,
            planning_mode=planning_mode,
            optimization_config=deepcopy(optimization_config) if optimization_config is not None else None,
            planning_results=deepcopy(planning_results) if planning_results is not None else None,
            optimization_results=deepcopy(optimization_results) if optimization_results is not None else None,
            total_cost=total_cost,
            labor_cost=labor_cost,
            production_cost=production_cost,
            transport_cost=transport_cost,
            waste_cost=waste_cost,
            demand_satisfaction_pct=demand_satisfaction_pct,
            total_production_units=total_production_units,
            planning_time_seconds=planning_time_seconds,
            tags=tags or [],
        )

        # Save to file and update index
        self._save_to_file(scenario)
        self._update_index(scenario)

        return scenario

    def load_scenario(self, scenario_id: str) -> Scenario:
        """Load scenario by ID.

        Args:
            scenario_id: Unique scenario identifier

        Returns:
            Loaded Scenario object

        Raises:
            FileNotFoundError: If scenario doesn't exist

        Example:
            >>> scenario = manager.load_scenario("abc-123-def")
        """
        return self._load_from_file(scenario_id)

    def list_scenarios(
        self,
        tags: Optional[List[str]] = None,
        sort_by: str = "created_at",
        reverse: bool = True
    ) -> List[Scenario]:
        """List all scenarios, optionally filtered by tags.

        Args:
            tags: Filter by tags (any match). None = all scenarios
            sort_by: Sort field - "created_at", "modified_at", "name", or "total_cost"
            reverse: Sort in descending order (newest/highest first)

        Returns:
            List of Scenario objects (metadata only, not full objects)

        Example:
            >>> # List all scenarios
            >>> scenarios = manager.list_scenarios()
            >>>
            >>> # Filter by tags
            >>> baseline_scenarios = manager.list_scenarios(tags=["baseline"])
            >>>
            >>> # Sort by cost
            >>> scenarios = manager.list_scenarios(sort_by="total_cost", reverse=False)
        """
        scenarios = []

        for scenario_id, metadata in self._index.items():
            # Filter by tags
            if tags is not None:
                scenario_tags = set(metadata.get('tags', []))
                if not any(tag in scenario_tags for tag in tags):
                    continue

            # Load full scenario to return
            try:
                scenario = self._load_from_file(scenario_id)
                scenarios.append(scenario)
            except FileNotFoundError:
                # Scenario file missing - remove from index
                self._remove_from_index(scenario_id)
                continue

        # Sort scenarios
        if sort_by == "created_at":
            scenarios.sort(key=lambda s: s.created_at, reverse=reverse)
        elif sort_by == "modified_at":
            scenarios.sort(key=lambda s: s.modified_at, reverse=reverse)
        elif sort_by == "name":
            scenarios.sort(key=lambda s: s.name.lower(), reverse=reverse)
        elif sort_by == "total_cost":
            scenarios.sort(
                key=lambda s: s.total_cost if s.total_cost is not None else float('inf'),
                reverse=reverse
            )

        return scenarios

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario.

        Args:
            scenario_id: Unique scenario identifier

        Returns:
            True if deleted successfully, False if not found

        Example:
            >>> manager.delete_scenario("abc-123-def")
        """
        file_path = self.storage_dir / f"{scenario_id}.pkl"

        if file_path.exists():
            file_path.unlink()
            self._remove_from_index(scenario_id)
            return True

        return False

    def update_scenario(
        self,
        scenario_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Scenario:
        """Update scenario metadata.

        Args:
            scenario_id: Unique scenario identifier
            name: New name (None = no change)
            description: New description (None = no change)
            tags: New tags list (None = no change)

        Returns:
            Updated Scenario object

        Raises:
            FileNotFoundError: If scenario doesn't exist

        Example:
            >>> scenario = manager.update_scenario(
            ...     "abc-123",
            ...     name="Updated Name",
            ...     tags=["baseline", "approved"]
            ... )
        """
        scenario = self._load_from_file(scenario_id)

        # Update fields
        if name is not None:
            scenario.name = name
        if description is not None:
            scenario.description = description
        if tags is not None:
            scenario.tags = tags

        scenario.modified_at = datetime.now()

        # Save updated scenario
        self._save_to_file(scenario)
        self._update_index(scenario)

        return scenario

    def compare_scenarios(
        self,
        scenario_ids: List[str]
    ) -> pd.DataFrame:
        """Compare multiple scenarios.

        Args:
            scenario_ids: List of scenario IDs to compare

        Returns:
            DataFrame with metrics side-by-side

        Example:
            >>> comparison = manager.compare_scenarios([id1, id2, id3])
            >>> print(comparison)
        """
        scenarios = [self._load_from_file(sid) for sid in scenario_ids]

        # Build comparison data
        data = []

        for scenario in scenarios:
            row = {
                'Scenario': scenario.name,
                'ID': scenario.id[:8] + '...',  # Abbreviated ID
                'Created': scenario.created_at.strftime('%Y-%m-%d %H:%M'),
                'Mode': scenario.planning_mode or 'N/A',
                'Tags': ', '.join(scenario.tags) if scenario.tags else 'None',
            }

            # Cost metrics
            if scenario.total_cost is not None:
                row['Total Cost'] = f"${scenario.total_cost:,.2f}"
            else:
                row['Total Cost'] = 'N/A'

            if scenario.labor_cost is not None:
                row['Labor Cost'] = f"${scenario.labor_cost:,.2f}"
            else:
                row['Labor Cost'] = 'N/A'

            if scenario.production_cost is not None:
                row['Production Cost'] = f"${scenario.production_cost:,.2f}"
            else:
                row['Production Cost'] = 'N/A'

            if scenario.transport_cost is not None:
                row['Transport Cost'] = f"${scenario.transport_cost:,.2f}"
            else:
                row['Transport Cost'] = 'N/A'

            if scenario.waste_cost is not None:
                row['Waste Cost'] = f"${scenario.waste_cost:,.2f}"
            else:
                row['Waste Cost'] = 'N/A'

            # Performance metrics
            if scenario.demand_satisfaction_pct is not None:
                row['Demand Satisfaction'] = f"{scenario.demand_satisfaction_pct:.1f}%"
            else:
                row['Demand Satisfaction'] = 'N/A'

            if scenario.total_production_units is not None:
                row['Total Production'] = f"{scenario.total_production_units:,} units"
            else:
                row['Total Production'] = 'N/A'

            if scenario.planning_time_seconds is not None:
                row['Planning Time'] = f"{scenario.planning_time_seconds:.2f}s"
            else:
                row['Planning Time'] = 'N/A'

            data.append(row)

        df = pd.DataFrame(data)

        # Add delta columns if 2+ scenarios
        if len(scenarios) >= 2:
            baseline = scenarios[0]

            for i, scenario in enumerate(scenarios[1:], start=1):
                deltas = {}

                # Cost delta
                if baseline.total_cost is not None and scenario.total_cost is not None:
                    delta = scenario.total_cost - baseline.total_cost
                    pct = (delta / baseline.total_cost) * 100 if baseline.total_cost != 0 else 0
                    deltas[f'Δ Cost vs {baseline.name[:15]}'] = f"{delta:+,.2f} ({pct:+.1f}%)"

                # Demand satisfaction delta
                if (baseline.demand_satisfaction_pct is not None and
                    scenario.demand_satisfaction_pct is not None):
                    delta = scenario.demand_satisfaction_pct - baseline.demand_satisfaction_pct
                    deltas[f'Δ Demand vs {baseline.name[:15]}'] = f"{delta:+.1f}%"

                # Update row with deltas
                for key, value in deltas.items():
                    if key not in df.columns:
                        df[key] = ''
                    df.loc[i, key] = value

        return df

    def export_scenario(
        self,
        scenario_id: str,
        output_path: str,
        format: str = "pickle"
    ) -> str:
        """Export scenario to file.

        Args:
            scenario_id: Unique scenario identifier
            output_path: Output file path
            format: Export format - "pickle", "json", or "excel"

        Returns:
            Path to exported file

        Raises:
            ValueError: If format not supported
            FileNotFoundError: If scenario doesn't exist

        Example:
            >>> path = manager.export_scenario(
            ...     "abc-123",
            ...     "baseline_scenario.pkl",
            ...     format="pickle"
            ... )
        """
        scenario = self._load_from_file(scenario_id)
        output_path = Path(output_path)

        if format == "pickle":
            with open(output_path, 'wb') as f:
                pickle.dump(scenario, f)

        elif format == "json":
            # JSON export (limited - can't serialize complex objects)
            # Export only metadata and metrics
            export_data = {
                'id': scenario.id,
                'name': scenario.name,
                'description': scenario.description,
                'created_at': scenario.created_at.isoformat(),
                'modified_at': scenario.modified_at.isoformat(),
                'planning_mode': scenario.planning_mode,
                'total_cost': scenario.total_cost,
                'labor_cost': scenario.labor_cost,
                'production_cost': scenario.production_cost,
                'transport_cost': scenario.transport_cost,
                'waste_cost': scenario.waste_cost,
                'demand_satisfaction_pct': scenario.demand_satisfaction_pct,
                'total_production_units': scenario.total_production_units,
                'planning_time_seconds': scenario.planning_time_seconds,
                'tags': scenario.tags,
            }

            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

        elif format == "excel":
            # Excel export - summary only
            summary_data = {
                'Field': [
                    'Scenario ID',
                    'Name',
                    'Description',
                    'Created At',
                    'Modified At',
                    'Planning Mode',
                    'Total Cost',
                    'Labor Cost',
                    'Production Cost',
                    'Transport Cost',
                    'Waste Cost',
                    'Demand Satisfaction (%)',
                    'Total Production Units',
                    'Planning Time (seconds)',
                    'Tags',
                ],
                'Value': [
                    scenario.id,
                    scenario.name,
                    scenario.description or '',
                    scenario.created_at.isoformat(),
                    scenario.modified_at.isoformat(),
                    scenario.planning_mode or '',
                    scenario.total_cost or '',
                    scenario.labor_cost or '',
                    scenario.production_cost or '',
                    scenario.transport_cost or '',
                    scenario.waste_cost or '',
                    scenario.demand_satisfaction_pct or '',
                    scenario.total_production_units or '',
                    scenario.planning_time_seconds or '',
                    ', '.join(scenario.tags) if scenario.tags else '',
                ]
            }

            df = pd.DataFrame(summary_data)
            df.to_excel(output_path, index=False, sheet_name='Scenario Summary')

        else:
            raise ValueError(f"Unsupported export format: {format}")

        return str(output_path)

    def import_scenario(
        self,
        file_path: str,
        format: str = "pickle"
    ) -> Scenario:
        """Import scenario from file.

        Args:
            file_path: Path to scenario file
            format: Import format - "pickle" or "json"

        Returns:
            Imported Scenario object (with new ID)

        Raises:
            ValueError: If format not supported
            FileNotFoundError: If file doesn't exist

        Example:
            >>> scenario = manager.import_scenario(
            ...     "backup_scenario.pkl",
            ...     format="pickle"
            ... )
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if format == "pickle":
            with open(file_path, 'rb') as f:
                scenario = pickle.load(f)

            # Generate new ID and timestamp
            scenario.id = str(uuid.uuid4())
            scenario.created_at = datetime.now()
            scenario.modified_at = datetime.now()

            # Save imported scenario
            self._save_to_file(scenario)
            self._update_index(scenario)

            return scenario

        elif format == "json":
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Create scenario from JSON (limited data)
            scenario = Scenario.from_dict(data)
            scenario.id = str(uuid.uuid4())  # New ID
            scenario.created_at = datetime.now()
            scenario.modified_at = datetime.now()

            # Save imported scenario
            self._save_to_file(scenario)
            self._update_index(scenario)

            return scenario

        else:
            raise ValueError(f"Unsupported import format: {format}")

    def get_storage_size(self) -> int:
        """Get total storage size in bytes.

        Returns:
            Total size of all scenario files in bytes

        Example:
            >>> size = manager.get_storage_size()
            >>> print(f"Storage: {size / 1024 / 1024:.2f} MB")
        """
        total_size = 0

        for file_path in self.storage_dir.glob("*.pkl"):
            total_size += file_path.stat().st_size

        # Add index file size
        if self.index_file.exists():
            total_size += self.index_file.stat().st_size

        return total_size

    def cleanup_orphaned_files(self) -> int:
        """Remove scenario files not in index.

        Returns:
            Number of files removed

        Example:
            >>> removed = manager.cleanup_orphaned_files()
            >>> print(f"Removed {removed} orphaned files")
        """
        index_ids = set(self._index.keys())
        removed = 0

        for file_path in self.storage_dir.glob("*.pkl"):
            scenario_id = file_path.stem  # Filename without extension

            if scenario_id not in index_ids:
                file_path.unlink()
                removed += 1

        return removed
