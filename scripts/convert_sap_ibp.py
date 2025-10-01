"""
Command-line utility to convert SAP IBP format files to long format.

Usage:
    python scripts/convert_sap_ibp.py input_file.xlsm [output_file.xlsx]

Examples:
    # Convert with default output name
    python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm"

    # Convert with custom output name
    python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm" "Forecast_Long_Format.xlsx"

    # Convert from data/examples/ directory
    python scripts/convert_sap_ibp.py "data/examples/Gfree Forecast.xlsm"
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers import SapIbpConverter


def main():
    """Main entry point for SAP IBP converter CLI."""
    parser = argparse.ArgumentParser(
        description="Convert SAP IBP format Excel files to long format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/convert_sap_ibp.py "Gfree Forecast.xlsm"
    python scripts/convert_sap_ibp.py input.xlsm output.xlsx
    python scripts/convert_sap_ibp.py "data/examples/Gfree Forecast.xlsm"
        """,
    )

    parser.add_argument(
        "input_file",
        type=str,
        help="Path to SAP IBP format Excel file (.xlsm or .xlsx)",
    )

    parser.add_argument(
        "output_file",
        type=str,
        nargs="?",
        help="Path for output Excel file (optional, default: input_file_Converted.xlsx)",
    )

    parser.add_argument(
        "--sheet",
        type=str,
        default=None,
        help="Sheet name to read (optional, auto-detects if not specified)",
    )

    parser.add_argument(
        "--output-sheet",
        type=str,
        default="Forecast",
        help="Output sheet name (default: Forecast)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Determine output file
    if args.output_file:
        output_path = Path(args.output_file)
    else:
        # Default: input_file_Converted.xlsx
        output_path = input_path.parent / f"{input_path.stem}_Converted{input_path.suffix}"

    print(f"🔄 Converting SAP IBP file...")
    print(f"   Input:  {input_path}")
    print(f"   Output: {output_path}")

    if args.verbose and args.sheet:
        print(f"   Sheet:  {args.sheet}")

    try:
        # Detect SAP IBP format
        if not SapIbpConverter.detect_sap_ibp_format(input_path):
            print("⚠️  Warning: File may not be in SAP IBP format", file=sys.stderr)
            response = input("Continue anyway? [y/N]: ")
            if response.lower() not in ["y", "yes"]:
                print("Cancelled.")
                return 1

        # Create converter
        converter = SapIbpConverter(input_path)

        if args.verbose:
            print("\n📊 Reading SAP IBP data...")
            df_raw = converter.read_sap_ibp_data(args.sheet)
            print(f"   Raw data shape: {df_raw.shape}")

        # Convert
        if args.verbose:
            print("\n🔄 Converting to long format...")

        df_forecast = converter.convert(args.sheet)

        if args.verbose:
            print(f"   Converted shape: {df_forecast.shape}")
            print(f"\n📈 Summary:")
            print(f"   - Total entries: {len(df_forecast)}")
            print(f"   - Unique locations: {df_forecast['location_id'].nunique()}")
            print(f"   - Unique products: {df_forecast['product_id'].nunique()}")
            print(f"   - Date range: {df_forecast['date'].min()} to {df_forecast['date'].max()}")

        # Save
        if args.verbose:
            print(f"\n💾 Saving to: {output_path}")

        converter.convert_and_save(
            output_path,
            sheet_name=args.sheet,
            output_sheet_name=args.output_sheet,
        )

        print(f"\n✅ Conversion successful!")
        print(f"   Output file: {output_path}")
        print(f"   Entries: {len(df_forecast)}")

        return 0

    except Exception as e:
        print(f"\n❌ Conversion failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
