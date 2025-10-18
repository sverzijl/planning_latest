#!/usr/bin/env python3
"""Update example Network_Config.xlsx to include production_rate column."""

import pandas as pd
from pathlib import Path

# Path to the example file
network_config_path = Path("data/examples/Network_Config.xlsx")

print(f"Updating {network_config_path}...")

# Read all sheets
with pd.ExcelFile(network_config_path, engine="openpyxl") as xl:
    sheets = {sheet_name: pd.read_excel(xl, sheet_name=sheet_name) for sheet_name in xl.sheet_names}

# Update Locations sheet to add production_rate column
if 'Locations' in sheets:
    df_locations = sheets['Locations']

    print(f"\nBefore update:")
    print(f"Columns: {list(df_locations.columns)}")
    print(f"\n{df_locations.to_string()}")

    # Add production_rate column if it doesn't exist
    if 'production_rate' not in df_locations.columns:
        # Insert production_rate column after storage_mode
        if 'storage_mode' in df_locations.columns:
            storage_mode_idx = df_locations.columns.get_loc('storage_mode')
            df_locations.insert(storage_mode_idx + 1, 'production_rate', None)
        else:
            df_locations['production_rate'] = None

        print(f"\n✓ Added production_rate column")

    # Set production_rate = 1400.0 for manufacturing locations
    manufacturing_mask = df_locations['type'].str.lower() == 'manufacturing'
    df_locations.loc[manufacturing_mask, 'production_rate'] = 1400.0

    print(f"\n✓ Set production_rate = 1400.0 for manufacturing locations")

    # Update the sheet
    sheets['Locations'] = df_locations

    print(f"\nAfter update:")
    print(f"Columns: {list(df_locations.columns)}")
    print(f"\n{df_locations.to_string()}")

# Write back to Excel
with pd.ExcelWriter(network_config_path, engine="openpyxl") as writer:
    for sheet_name, df in sheets.items():
        df.to_excel(writer, sheet_name=sheet_name, index=False)

print(f"\n✓ Successfully updated {network_config_path}")
