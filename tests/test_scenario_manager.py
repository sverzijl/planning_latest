"""Tests for scenario management system."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

from src.scenario import ScenarioManager, Scenario


@pytest.fixture
def temp_storage():
    """Create temporary storage directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def scenario_manager(temp_storage):
    """Create scenario manager with temporary storage."""
    return ScenarioManager(storage_dir=temp_storage)


@pytest.fixture
def sample_scenario_data():
    """Sample scenario data for testing."""
    return {
        'name': 'Test Scenario',
        'description': 'A test scenario',
        'forecast_data': pd.DataFrame({'location': [1, 2], 'demand': [100, 200]}),
        'planning_mode': 'optimization',
        'total_cost': 50000.0,
        'labor_cost': 20000.0,
        'production_cost': 15000.0,
        'transport_cost': 10000.0,
        'waste_cost': 5000.0,
        'demand_satisfaction_pct': 95.5,
        'total_production_units': 1000,
        'planning_time_seconds': 12.5,
        'tags': ['test', 'baseline'],
    }


class TestScenario:
    """Test Scenario dataclass."""

    def test_scenario_creation(self):
        """Test creating a scenario."""
        scenario = Scenario(
            id='test-123',
            name='Test Scenario',
            description='Test description',
        )

        assert scenario.id == 'test-123'
        assert scenario.name == 'Test Scenario'
        assert scenario.description == 'Test description'
        assert scenario.tags == []
        assert isinstance(scenario.created_at, datetime)
        assert isinstance(scenario.modified_at, datetime)

    def test_scenario_with_metrics(self):
        """Test scenario with computed metrics."""
        scenario = Scenario(
            id='test-123',
            name='Test Scenario',
            total_cost=50000.0,
            labor_cost=20000.0,
            demand_satisfaction_pct=95.5,
            total_production_units=1000,
        )

        assert scenario.total_cost == 50000.0
        assert scenario.labor_cost == 20000.0
        assert scenario.demand_satisfaction_pct == 95.5
        assert scenario.total_production_units == 1000

    def test_scenario_to_dict(self):
        """Test converting scenario to dictionary."""
        scenario = Scenario(
            id='test-123',
            name='Test Scenario',
            tags=['test'],
        )

        data = scenario.to_dict()

        assert isinstance(data, dict)
        assert data['id'] == 'test-123'
        assert data['name'] == 'Test Scenario'
        assert data['tags'] == ['test']

    def test_scenario_from_dict(self):
        """Test creating scenario from dictionary."""
        data = {
            'id': 'test-123',
            'name': 'Test Scenario',
            'description': 'Test',
            'created_at': datetime.now(),
            'modified_at': datetime.now(),
            'tags': ['test'],
            'forecast_data': None,
            'labor_calendar': None,
            'truck_schedules': None,
            'cost_parameters': None,
            'locations': None,
            'routes': None,
            'manufacturing_site': None,
            'planning_mode': None,
            'optimization_config': None,
            'planning_results': None,
            'optimization_results': None,
            'total_cost': None,
            'labor_cost': None,
            'production_cost': None,
            'transport_cost': None,
            'waste_cost': None,
            'demand_satisfaction_pct': None,
            'total_production_units': None,
            'planning_time_seconds': None,
        }

        scenario = Scenario.from_dict(data)

        assert scenario.id == 'test-123'
        assert scenario.name == 'Test Scenario'
        assert scenario.tags == ['test']


class TestScenarioManager:
    """Test ScenarioManager class."""

    def test_manager_initialization(self, scenario_manager, temp_storage):
        """Test scenario manager initialization."""
        assert scenario_manager.storage_dir == Path(temp_storage)
        assert scenario_manager.storage_dir.exists()
        assert scenario_manager.index_file.exists()

    def test_save_scenario(self, scenario_manager, sample_scenario_data):
        """Test saving a scenario."""
        scenario = scenario_manager.save_scenario(**sample_scenario_data)

        assert scenario is not None
        assert scenario.id is not None
        assert scenario.name == 'Test Scenario'
        assert scenario.description == 'A test scenario'
        assert scenario.total_cost == 50000.0
        assert scenario.tags == ['test', 'baseline']

        # Check file was created
        scenario_file = scenario_manager.storage_dir / f"{scenario.id}.pkl"
        assert scenario_file.exists()

    def test_save_scenario_generates_unique_ids(self, scenario_manager, sample_scenario_data):
        """Test that each saved scenario gets a unique ID."""
        scenario1 = scenario_manager.save_scenario(**sample_scenario_data)
        scenario2 = scenario_manager.save_scenario(**sample_scenario_data)

        assert scenario1.id != scenario2.id

    def test_load_scenario(self, scenario_manager, sample_scenario_data):
        """Test loading a scenario."""
        # Save scenario first
        saved_scenario = scenario_manager.save_scenario(**sample_scenario_data)

        # Load scenario
        loaded_scenario = scenario_manager.load_scenario(saved_scenario.id)

        assert loaded_scenario.id == saved_scenario.id
        assert loaded_scenario.name == saved_scenario.name
        assert loaded_scenario.description == saved_scenario.description
        assert loaded_scenario.total_cost == saved_scenario.total_cost
        assert loaded_scenario.tags == saved_scenario.tags

        # Check forecast data was preserved
        assert loaded_scenario.forecast_data is not None
        pd.testing.assert_frame_equal(loaded_scenario.forecast_data, saved_scenario.forecast_data)

    def test_load_nonexistent_scenario(self, scenario_manager):
        """Test loading a scenario that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            scenario_manager.load_scenario('nonexistent-id')

    def test_list_scenarios_empty(self, scenario_manager):
        """Test listing scenarios when none exist."""
        scenarios = scenario_manager.list_scenarios()
        assert scenarios == []

    def test_list_scenarios(self, scenario_manager, sample_scenario_data):
        """Test listing all scenarios."""
        # Save multiple scenarios
        scenario1 = scenario_manager.save_scenario(
            name='Scenario 1',
            **{k: v for k, v in sample_scenario_data.items() if k != 'name'}
        )
        scenario2 = scenario_manager.save_scenario(
            name='Scenario 2',
            **{k: v for k, v in sample_scenario_data.items() if k != 'name'}
        )

        # List scenarios
        scenarios = scenario_manager.list_scenarios()

        assert len(scenarios) == 2
        scenario_ids = [s.id for s in scenarios]
        assert scenario1.id in scenario_ids
        assert scenario2.id in scenario_ids

    def test_list_scenarios_filtered_by_tags(self, scenario_manager, sample_scenario_data):
        """Test filtering scenarios by tags."""
        # Save scenarios with different tags
        scenario1 = scenario_manager.save_scenario(
            name='Baseline',
            tags=['baseline', 'Q1'],
            **{k: v for k, v in sample_scenario_data.items() if k not in ['name', 'tags']}
        )
        scenario2 = scenario_manager.save_scenario(
            name='High Demand',
            tags=['high-demand', 'Q1'],
            **{k: v for k, v in sample_scenario_data.items() if k not in ['name', 'tags']}
        )
        scenario3 = scenario_manager.save_scenario(
            name='Optimization',
            tags=['optimization', 'Q2'],
            **{k: v for k, v in sample_scenario_data.items() if k not in ['name', 'tags']}
        )

        # Filter by 'baseline' tag
        baseline_scenarios = scenario_manager.list_scenarios(tags=['baseline'])
        assert len(baseline_scenarios) == 1
        assert baseline_scenarios[0].id == scenario1.id

        # Filter by 'Q1' tag (should match scenario1 and scenario2)
        q1_scenarios = scenario_manager.list_scenarios(tags=['Q1'])
        assert len(q1_scenarios) == 2
        q1_ids = [s.id for s in q1_scenarios]
        assert scenario1.id in q1_ids
        assert scenario2.id in q1_ids

        # Filter by multiple tags (any match)
        filtered = scenario_manager.list_scenarios(tags=['baseline', 'optimization'])
        assert len(filtered) == 2

    def test_list_scenarios_sorted(self, scenario_manager, sample_scenario_data):
        """Test sorting scenarios."""
        # Create scenarios with different costs and timestamps
        import time

        scenario1 = scenario_manager.save_scenario(
            name='High Cost',
            total_cost=100000.0,
            **{k: v for k, v in sample_scenario_data.items() if k not in ['name', 'total_cost']}
        )
        time.sleep(0.01)  # Small delay to ensure different timestamps

        scenario2 = scenario_manager.save_scenario(
            name='Low Cost',
            total_cost=30000.0,
            **{k: v for k, v in sample_scenario_data.items() if k not in ['name', 'total_cost']}
        )

        # Sort by created_at (newest first - default)
        scenarios = scenario_manager.list_scenarios(sort_by='created_at', reverse=True)
        assert scenarios[0].id == scenario2.id  # Newest first

        # Sort by created_at (oldest first)
        scenarios = scenario_manager.list_scenarios(sort_by='created_at', reverse=False)
        assert scenarios[0].id == scenario1.id  # Oldest first

        # Sort by name
        scenarios = scenario_manager.list_scenarios(sort_by='name', reverse=False)
        assert scenarios[0].name == 'High Cost'  # Alphabetically first

        # Sort by total_cost (low to high)
        scenarios = scenario_manager.list_scenarios(sort_by='total_cost', reverse=False)
        assert scenarios[0].total_cost == 30000.0

    def test_delete_scenario(self, scenario_manager, sample_scenario_data):
        """Test deleting a scenario."""
        # Save scenario
        scenario = scenario_manager.save_scenario(**sample_scenario_data)

        # Verify file exists
        scenario_file = scenario_manager.storage_dir / f"{scenario.id}.pkl"
        assert scenario_file.exists()

        # Delete scenario
        result = scenario_manager.delete_scenario(scenario.id)

        assert result is True
        assert not scenario_file.exists()

        # Verify scenario is not in list
        scenarios = scenario_manager.list_scenarios()
        assert len(scenarios) == 0

    def test_delete_nonexistent_scenario(self, scenario_manager):
        """Test deleting a scenario that doesn't exist."""
        result = scenario_manager.delete_scenario('nonexistent-id')
        assert result is False

    def test_update_scenario(self, scenario_manager, sample_scenario_data):
        """Test updating scenario metadata."""
        # Save scenario
        scenario = scenario_manager.save_scenario(**sample_scenario_data)
        original_modified_at = scenario.modified_at

        # Update scenario
        import time
        time.sleep(0.01)  # Ensure modified_at is different

        updated_scenario = scenario_manager.update_scenario(
            scenario.id,
            name='Updated Name',
            description='Updated description',
            tags=['updated', 'test']
        )

        assert updated_scenario.id == scenario.id
        assert updated_scenario.name == 'Updated Name'
        assert updated_scenario.description == 'Updated description'
        assert updated_scenario.tags == ['updated', 'test']
        assert updated_scenario.modified_at > original_modified_at

        # Verify changes persist
        loaded = scenario_manager.load_scenario(scenario.id)
        assert loaded.name == 'Updated Name'
        assert loaded.description == 'Updated description'
        assert loaded.tags == ['updated', 'test']

    def test_update_scenario_partial(self, scenario_manager, sample_scenario_data):
        """Test partial update of scenario metadata."""
        # Save scenario
        scenario = scenario_manager.save_scenario(**sample_scenario_data)

        # Update only name
        updated = scenario_manager.update_scenario(
            scenario.id,
            name='New Name'
        )

        assert updated.name == 'New Name'
        assert updated.description == scenario.description  # Unchanged
        assert updated.tags == scenario.tags  # Unchanged

    def test_compare_scenarios(self, scenario_manager, sample_scenario_data):
        """Test comparing multiple scenarios."""
        # Save multiple scenarios with different costs
        scenario1 = scenario_manager.save_scenario(
            name='Baseline',
            total_cost=50000.0,
            labor_cost=20000.0,
            demand_satisfaction_pct=95.0,
            **{k: v for k, v in sample_scenario_data.items()
               if k not in ['name', 'total_cost', 'labor_cost', 'demand_satisfaction_pct']}
        )

        scenario2 = scenario_manager.save_scenario(
            name='Optimized',
            total_cost=45000.0,
            labor_cost=18000.0,
            demand_satisfaction_pct=98.0,
            **{k: v for k, v in sample_scenario_data.items()
               if k not in ['name', 'total_cost', 'labor_cost', 'demand_satisfaction_pct']}
        )

        scenario3 = scenario_manager.save_scenario(
            name='High Demand',
            total_cost=60000.0,
            labor_cost=25000.0,
            demand_satisfaction_pct=100.0,
            **{k: v for k, v in sample_scenario_data.items()
               if k not in ['name', 'total_cost', 'labor_cost', 'demand_satisfaction_pct']}
        )

        # Compare scenarios
        comparison_df = scenario_manager.compare_scenarios([
            scenario1.id,
            scenario2.id,
            scenario3.id
        ])

        assert isinstance(comparison_df, pd.DataFrame)
        assert len(comparison_df) == 3

        # Check columns exist
        assert 'Scenario' in comparison_df.columns
        assert 'Total Cost' in comparison_df.columns
        assert 'Labor Cost' in comparison_df.columns

        # Check scenario names
        scenario_names = comparison_df['Scenario'].tolist()
        assert 'Baseline' in scenario_names
        assert 'Optimized' in scenario_names
        assert 'High Demand' in scenario_names

    def test_export_scenario_pickle(self, scenario_manager, sample_scenario_data, temp_storage):
        """Test exporting scenario to pickle format."""
        # Save scenario
        scenario = scenario_manager.save_scenario(**sample_scenario_data)

        # Export to pickle
        export_path = Path(temp_storage) / 'exported_scenario.pkl'
        result_path = scenario_manager.export_scenario(
            scenario.id,
            str(export_path),
            format='pickle'
        )

        assert Path(result_path).exists()
        assert export_path.exists()

        # Verify exported file can be loaded
        import pickle
        with open(export_path, 'rb') as f:
            exported_scenario = pickle.load(f)

        assert exported_scenario.id == scenario.id
        assert exported_scenario.name == scenario.name

    def test_export_scenario_json(self, scenario_manager, sample_scenario_data, temp_storage):
        """Test exporting scenario to JSON format."""
        # Save scenario
        scenario = scenario_manager.save_scenario(**sample_scenario_data)

        # Export to JSON
        export_path = Path(temp_storage) / 'exported_scenario.json'
        result_path = scenario_manager.export_scenario(
            scenario.id,
            str(export_path),
            format='json'
        )

        assert Path(result_path).exists()

        # Verify JSON file contents
        import json
        with open(export_path, 'r') as f:
            data = json.load(f)

        assert data['id'] == scenario.id
        assert data['name'] == scenario.name
        assert data['total_cost'] == scenario.total_cost

    def test_export_scenario_excel(self, scenario_manager, sample_scenario_data, temp_storage):
        """Test exporting scenario to Excel format."""
        # Save scenario
        scenario = scenario_manager.save_scenario(**sample_scenario_data)

        # Export to Excel
        export_path = Path(temp_storage) / 'exported_scenario.xlsx'
        result_path = scenario_manager.export_scenario(
            scenario.id,
            str(export_path),
            format='excel'
        )

        assert Path(result_path).exists()

        # Verify Excel file can be read
        df = pd.read_excel(export_path)
        assert 'Field' in df.columns
        assert 'Value' in df.columns

    def test_export_scenario_invalid_format(self, scenario_manager, sample_scenario_data):
        """Test exporting scenario with invalid format."""
        scenario = scenario_manager.save_scenario(**sample_scenario_data)

        with pytest.raises(ValueError, match="Unsupported export format"):
            scenario_manager.export_scenario(
                scenario.id,
                '/tmp/test.txt',
                format='invalid'
            )

    def test_import_scenario_pickle(self, scenario_manager, sample_scenario_data, temp_storage):
        """Test importing scenario from pickle format."""
        # Save and export scenario
        original_scenario = scenario_manager.save_scenario(**sample_scenario_data)
        export_path = Path(temp_storage) / 'export.pkl'
        scenario_manager.export_scenario(original_scenario.id, str(export_path), format='pickle')

        # Create new manager (fresh state)
        new_manager = ScenarioManager(storage_dir=Path(temp_storage) / 'new')

        # Import scenario
        imported_scenario = new_manager.import_scenario(str(export_path), format='pickle')

        assert imported_scenario.name == original_scenario.name
        assert imported_scenario.total_cost == original_scenario.total_cost
        assert imported_scenario.id != original_scenario.id  # New ID assigned

    def test_import_scenario_json(self, scenario_manager, sample_scenario_data, temp_storage):
        """Test importing scenario from JSON format."""
        # Save and export scenario
        original_scenario = scenario_manager.save_scenario(**sample_scenario_data)
        export_path = Path(temp_storage) / 'export.json'
        scenario_manager.export_scenario(original_scenario.id, str(export_path), format='json')

        # Create new manager
        new_manager = ScenarioManager(storage_dir=Path(temp_storage) / 'new')

        # Import scenario
        imported_scenario = new_manager.import_scenario(str(export_path), format='json')

        assert imported_scenario.name == original_scenario.name
        assert imported_scenario.total_cost == original_scenario.total_cost
        assert imported_scenario.id != original_scenario.id  # New ID assigned

    def test_import_scenario_nonexistent_file(self, scenario_manager):
        """Test importing from a file that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            scenario_manager.import_scenario('/nonexistent/file.pkl', format='pickle')

    def test_get_storage_size(self, scenario_manager, sample_scenario_data):
        """Test getting total storage size."""
        # Initially should be small (just index)
        initial_size = scenario_manager.get_storage_size()
        assert initial_size > 0

        # Save scenario
        scenario_manager.save_scenario(**sample_scenario_data)

        # Size should increase
        new_size = scenario_manager.get_storage_size()
        assert new_size > initial_size

    def test_cleanup_orphaned_files(self, scenario_manager, sample_scenario_data, temp_storage):
        """Test cleaning up orphaned scenario files."""
        # Save scenario
        scenario = scenario_manager.save_scenario(**sample_scenario_data)

        # Manually create an orphaned file (not in index)
        orphaned_file = Path(temp_storage) / 'orphaned-id.pkl'
        with open(orphaned_file, 'wb') as f:
            import pickle
            pickle.dump({'test': 'data'}, f)

        assert orphaned_file.exists()

        # Run cleanup
        removed = scenario_manager.cleanup_orphaned_files()

        assert removed == 1
        assert not orphaned_file.exists()

        # Verify real scenario still exists
        scenario_file = Path(temp_storage) / f"{scenario.id}.pkl"
        assert scenario_file.exists()

    def test_scenario_deepcopy_isolation(self, scenario_manager):
        """Test that saved scenarios are isolated from original objects."""
        # Create mutable data
        original_data = {'key': 'value'}
        original_tags = ['tag1', 'tag2']

        # Save scenario
        scenario = scenario_manager.save_scenario(
            name='Test',
            cost_parameters=original_data,
            tags=original_tags
        )

        # Modify original data
        original_data['key'] = 'modified'
        original_tags.append('tag3')

        # Load scenario and verify data is unchanged
        loaded = scenario_manager.load_scenario(scenario.id)
        assert loaded.cost_parameters['key'] == 'value'
        assert loaded.tags == ['tag1', 'tag2']

    def test_index_persistence(self, scenario_manager, sample_scenario_data, temp_storage):
        """Test that index persists across manager instances."""
        # Save scenario
        scenario = scenario_manager.save_scenario(**sample_scenario_data)

        # Create new manager instance with same storage
        new_manager = ScenarioManager(storage_dir=temp_storage)

        # Verify scenario is in new manager's index
        scenarios = new_manager.list_scenarios()
        assert len(scenarios) == 1
        assert scenarios[0].id == scenario.id

    def test_concurrent_managers(self, temp_storage, sample_scenario_data):
        """Test multiple managers using same storage."""
        manager1 = ScenarioManager(storage_dir=temp_storage)
        manager2 = ScenarioManager(storage_dir=temp_storage)

        # Save with manager1
        # Filter out name from sample_scenario_data to avoid duplicate
        data = {k: v for k, v in sample_scenario_data.items() if k != "name"}
        scenario1 = manager1.save_scenario(name="Scenario 1", **data)

        # Load index with manager2
        manager2._load_index()
        scenarios = manager2.list_scenarios()

        assert len(scenarios) == 1
        assert scenarios[0].id == scenario1.id
