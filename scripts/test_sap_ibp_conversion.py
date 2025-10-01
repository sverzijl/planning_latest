"""
Quick test script to verify SAP IBP converter works with GFree Forecast.xlsm
"""

from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers import SapIbpConverter


def main():
    print("=" * 60)
    print("Testing SAP IBP Converter")
    print("=" * 60)

    sap_file = Path("data/examples/Gfree Forecast.xlsm")

    print(f"\n1. Checking file: {sap_file}")
    if not sap_file.exists():
        print(f"❌ File not found: {sap_file}")
        return 1

    print(f"   ✅ File exists ({sap_file.stat().st_size / 1024:.1f} KB)")

    # Detect SAP IBP format
    print("\n2. Detecting format...")
    is_sap_ibp = SapIbpConverter.detect_sap_ibp_format(sap_file)
    if is_sap_ibp:
        print("   ✅ SAP IBP format detected")
    else:
        print("   ❌ SAP IBP format not detected")
        return 1

    # Create converter
    print("\n3. Creating converter...")
    try:
        converter = SapIbpConverter(sap_file)
        print("   ✅ Converter created")
    except Exception as e:
        print(f"   ❌ Error creating converter: {e}")
        return 1

    # Find data sheet
    print("\n4. Finding data sheet...")
    try:
        sheet_name = converter.find_data_sheet()
        print(f"   ✅ Found data sheet: {sheet_name}")
    except Exception as e:
        print(f"   ❌ Error finding data sheet: {e}")
        return 1

    # Read raw data
    print("\n5. Reading SAP IBP data...")
    try:
        df_raw = converter.read_sap_ibp_data()
        print(f"   ✅ Raw data shape: {df_raw.shape}")
    except Exception as e:
        print(f"   ❌ Error reading data: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Convert to long format
    print("\n6. Converting to long format...")
    try:
        df_forecast = converter.convert()
        print(f"   ✅ Converted data shape: {df_forecast.shape}")
        print(f"   ✅ Forecast entries: {len(df_forecast)}")
    except Exception as e:
        print(f"   ❌ Error converting: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Display summary
    print("\n7. Conversion Summary:")
    print(f"   - Total entries: {len(df_forecast)}")
    print(f"   - Unique locations: {df_forecast['location_id'].nunique()}")
    print(f"   - Unique products: {df_forecast['product_id'].nunique()}")
    print(f"   - Date range: {df_forecast['date'].min()} to {df_forecast['date'].max()}")

    print("\n   Locations:")
    for loc_id in sorted(df_forecast['location_id'].unique()):
        count = len(df_forecast[df_forecast['location_id'] == loc_id])
        print(f"      - {loc_id}: {count} entries")

    print("\n   Products:")
    for prod_id in sorted(df_forecast['product_id'].unique()):
        count = len(df_forecast[df_forecast['product_id'] == prod_id])
        print(f"      - {prod_id}: {count} entries")

    print("\n   Sample data:")
    print(df_forecast.head(10).to_string(index=False))

    # Save converted file
    output_path = Path("data/examples/Gfree Forecast_Converted.xlsx")
    print(f"\n8. Saving converted file to: {output_path}")
    try:
        converter.convert_and_save(output_path)
        print(f"   ✅ File saved ({output_path.stat().st_size / 1024:.1f} KB)")
    except Exception as e:
        print(f"   ❌ Error saving: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 60)
    print("✅ SAP IBP conversion test completed successfully!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
