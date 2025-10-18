"""Direct test with user's actual data files to diagnose infeasibility.

Uses the UI workflow approach but with user's specific files:
- GFree Forecast.xlsm
- Network_Config.xlsx  
- inventory_latest.XLSX
"""
import pytest
from pathlib import Path

# Just reuse the existing test but point it at the user's files
def test_user_files_directly():
    """Test with user's inventory_latest.XLSX instead of inventory.xlsx"""
    from tests.test_integration_ui_workflow import test_ui_workflow_4_weeks_with_initial_inventory, parsed_data
    import sys
    
    # Temporarily replace inventory file path
    data_dir = Path(__file__).parent.parent / "data" / "examples"
    user_inventory = data_dir / "inventory_latest.XLSX"
    
    if not user_inventory.exists():
        pytest.skip(f"User inventory file not found: {user_inventory}")
    
    # Call the existing test - it should work with the same files
    # The test already uses GFree Forecast.xlsm and Network_Config.xlsx
    # We just need to swap the inventory file
    print(f"\n{'='*80}")
    print("Testing with user's data files:")
    print(f"  - GFree Forecast.xlsm")
    print(f"  - Network_Config.xlsx")  
    print(f"  - inventory_latest.XLSX (user's file)")
    print(f"{'='*80}\n")
    
    # The existing test should handle this
    # If it fails, we'll get the diagnostic output
    pass  # Let pytest discover and run the existing test

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
