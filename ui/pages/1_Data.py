"""Data Management - Upload, view, and edit forecast data.

Consolidates:
- 1_Upload_Data.py
- 2_Data_Summary.py
- 12_Forecast_Editor.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
import tempfile
from datetime import date
from ui import session_state
from ui.components.styling import (
    apply_custom_css,
    section_header,
    success_badge,
    info_badge,
    warning_badge,
    colored_metric,
    status_badge,
)
from ui.components.navigation import render_page_header
from ui.components.date_filter import render_date_range_filter, apply_date_filter
from src.models.forecast import ForecastEntry, Forecast

# Page config
st.set_page_config(
    page_title="Data Management - GF Bread Production",
    page_icon="📁",
    layout="wide",
)

# Apply design system
apply_custom_css()

# Initialize session state
session_state.initialize_session_state()

# Page header
render_page_header(
    title="Data Management",
    icon="📁",
    subtitle="Upload data files, view summaries, and edit forecasts"
)

st.divider()

# Create tabs for data management tasks
tab_upload, tab_summary, tab_editor = st.tabs(["📤 Upload", "📊 Summary", "✏️ Edit Forecast"])


# ===========================
# TAB 1: UPLOAD DATA
# ===========================

with tab_upload:
    st.markdown(
        """
        <div class="info-box">
            <div style="font-weight: 600; margin-bottom: 8px;">📋 Required Files</div>
            <div>Upload TWO separate Excel files:</div>
            <ol style="margin-top: 8px; padding-left: 20px;">
                <li><strong>Forecast File:</strong> Sales demand by location and date (supports SAP IBP format)</li>
                <li><strong>Network Configuration File:</strong> Locations, routes, labor, trucks, and costs</li>
            </ol>
            <div style="margin-top: 12px; font-size: 13px; color: #757575;">
                This separation allows you to update forecast data frequently while keeping network configuration stable.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Three-column layout for file uploads
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(section_header("1️⃣ Forecast File", level=3), unsafe_allow_html=True)
        forecast_file = st.file_uploader(
            "Choose forecast file",
            type=["xlsm", "xlsx"],
            help="Excel file with standard Forecast sheet or SAP IBP export format",
            key="forecast_uploader",
        )
        if forecast_file:
            st.markdown(success_badge(forecast_file.name), unsafe_allow_html=True)

    with col2:
        st.markdown(section_header("2️⃣ Network Configuration File", level=3), unsafe_allow_html=True)
        network_file = st.file_uploader(
            "Choose network config file",
            type=["xlsm", "xlsx"],
            help="Excel file with Locations, Routes, LaborCalendar, TruckSchedules, CostParameters, and Alias sheets",
            key="network_uploader",
        )
        if network_file:
            st.markdown(success_badge(network_file.name), unsafe_allow_html=True)

    with col3:
        st.markdown(section_header("3️⃣ Inventory File (Optional)", level=3), unsafe_allow_html=True)
        inventory_file = st.file_uploader(
            "Choose inventory file",
            type=["xlsm", "xlsx", "XLSX"],
            help="Optional: Excel file with current inventory snapshot",
            key="inventory_uploader",
        )
        if inventory_file:
            st.markdown(success_badge(inventory_file.name), unsafe_allow_html=True)

    # Display file contents if uploaded
    if forecast_file is not None or network_file is not None:
        st.divider()
        st.markdown(section_header("File Contents Preview", level=2, icon="📋"), unsafe_allow_html=True)

        # Create tabs based on what's uploaded
        if forecast_file and network_file:
            preview_tabs = st.tabs(["Forecast", "Locations", "Routes", "LaborCalendar", "TruckSchedules", "CostParameters"])
        elif forecast_file:
            preview_tabs = st.tabs(["Forecast"])
        else:
            preview_tabs = st.tabs(["Locations", "Routes", "LaborCalendar", "TruckSchedules", "CostParameters"])

        tab_idx = 0

        # Forecast tab with SAP IBP support
        if forecast_file:
            with preview_tabs[tab_idx]:
                try:
                    # Try standard format first
                    df_forecast = pd.read_excel(forecast_file, sheet_name="Forecast", engine="openpyxl")
                    st.markdown(info_badge("Format: Standard"), unsafe_allow_html=True)
                    st.dataframe(df_forecast.head(100), use_container_width=True)
                    st.caption(f"📊 {len(df_forecast)} forecast entries (showing first 100)")
                except Exception as e1:
                    # Try SAP IBP format
                    temp_path = None
                    try:
                        from src.parsers.sap_ibp_parser import SapIbpParser

                        # Save to temp file for parsing
                        # Create and write file, then close handle immediately (Windows fix)
                        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsm")
                        try:
                            temp_file.write(forecast_file.getvalue())
                            temp_path = Path(temp_file.name)
                        finally:
                            temp_file.close()  # Close handle before accessing file

                        # Detect SAP IBP format (file is now closed, can be accessed)
                        sap_sheet = SapIbpParser.detect_sap_ibp_format(temp_path)
                        if sap_sheet:
                            st.markdown(success_badge(f"Format: SAP IBP ({sap_sheet})"), unsafe_allow_html=True)

                            # Parse and show preview
                            forecast = SapIbpParser.parse_sap_ibp_forecast(temp_path, sap_sheet)

                            # Convert to dataframe for preview
                            preview_data = {
                                "location_id": [e.location_id for e in forecast.entries[:100]],
                                "product_id": [e.product_id for e in forecast.entries[:100]],
                                "date": [e.forecast_date for e in forecast.entries[:100]],
                                "quantity": [e.quantity for e in forecast.entries[:100]],
                            }
                            df_preview = pd.DataFrame(preview_data)
                            st.dataframe(df_preview, use_container_width=True)
                            st.caption(f"📊 {len(forecast.entries)} forecast entries (transformed from wide format, showing first 100)")

                            # Show some stats
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Products", len(set(e.product_id for e in forecast.entries)))
                            with col2:
                                st.metric("Locations", len(set(e.location_id for e in forecast.entries)))
                            with col3:
                                st.metric("Date Range (days)", len(set(e.forecast_date for e in forecast.entries)))
                        else:
                            raise ValueError("No valid forecast format detected")

                    except Exception as e2:
                        st.error(f"Error reading forecast data")
                        with st.expander("Error Details"):
                            st.write(f"**Standard format error:** {e1}")
                            st.write(f"**SAP IBP detection error:** {e2}")
                        st.info("**Supported formats:**\n- **Standard:** Forecast sheet with columns: location_id, product_id, date, quantity\n- **SAP IBP:** Wide format export with dates as columns")
                    finally:
                        # Clean up temp file with retry logic for Windows file locking
                        if temp_path and temp_path.exists():
                            import gc
                            import time

                            # Force garbage collection to close any lingering file handles
                            gc.collect()

                            # Retry deletion with delays (Windows compatibility)
                            max_retries = 3
                            for attempt in range(max_retries):
                                try:
                                    temp_path.unlink()
                                    break  # Success
                                except PermissionError as e:
                                    if attempt < max_retries - 1:
                                        # Wait and try again
                                        time.sleep(0.1)
                                        gc.collect()
                                    else:
                                        # Log warning but don't fail the preview
                                        st.warning(f"⚠️ Could not delete temporary file (will be cleaned by system): {temp_path.name}")
            tab_idx += 1

        # Network config tabs
        if network_file:
            # Locations
            with preview_tabs[tab_idx]:
                try:
                    df_locations = pd.read_excel(network_file, sheet_name="Locations", engine="openpyxl")
                    st.dataframe(df_locations, use_container_width=True)
                    st.caption(f"📍 {len(df_locations)} locations")
                except Exception as e:
                    st.error(f"Error reading Locations sheet: {e}")
            tab_idx += 1

            # Routes
            with preview_tabs[tab_idx]:
                try:
                    df_routes = pd.read_excel(network_file, sheet_name="Routes", engine="openpyxl")
                    st.dataframe(df_routes, use_container_width=True)
                    st.caption(f"🛣️ {len(df_routes)} routes")
                except Exception as e:
                    st.error(f"Error reading Routes sheet: {e}")
            tab_idx += 1

            # LaborCalendar
            with preview_tabs[tab_idx]:
                try:
                    df_labor = pd.read_excel(network_file, sheet_name="LaborCalendar", engine="openpyxl")
                    st.dataframe(df_labor.head(30), use_container_width=True)
                    st.caption(f"📅 {len(df_labor)} days (showing first 30)")
                except Exception as e:
                    st.error(f"Error reading LaborCalendar sheet: {e}")
            tab_idx += 1

            # TruckSchedules
            with preview_tabs[tab_idx]:
                try:
                    df_trucks = pd.read_excel(network_file, sheet_name="TruckSchedules", engine="openpyxl")
                    st.dataframe(df_trucks, use_container_width=True)
                    st.caption(f"🚚 {len(df_trucks)} truck schedules")
                except Exception as e:
                    st.error(f"Error reading TruckSchedules sheet: {e}")
            tab_idx += 1

            # CostParameters
            with preview_tabs[tab_idx]:
                try:
                    df_costs = pd.read_excel(network_file, sheet_name="CostParameters", engine="openpyxl")
                    st.dataframe(df_costs, use_container_width=True)
                    st.caption(f"💰 {len(df_costs)} cost parameters")
                except Exception as e:
                    st.error(f"Error reading CostParameters sheet: {e}")

        # Parse and validate button
        if forecast_file and network_file:
            st.divider()
            if st.button("✅ Parse and Validate Data", type="primary", use_container_width=True):
                with st.spinner("Parsing and validating data..."):
                    try:
                        from src.parsers import MultiFileParser
                        from src.models.location import LocationType

                        # Save uploaded files to temp locations
                        # Close file handles immediately for Windows compatibility
                        forecast_path = None
                        network_path = None
                        inventory_path = None

                        try:
                            # Forecast file
                            f_forecast = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
                            f_forecast.write(forecast_file.getvalue())
                            forecast_path = f_forecast.name
                            f_forecast.close()  # Close handle immediately

                            # Network file
                            f_network = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
                            f_network.write(network_file.getvalue())
                            network_path = f_network.name
                            f_network.close()  # Close handle immediately

                            # Inventory file (optional)
                            if inventory_file:
                                f_inventory = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
                                f_inventory.write(inventory_file.getvalue())
                                inventory_path = f_inventory.name
                                f_inventory.close()  # Close handle immediately
                        except Exception:
                            # If file creation fails, clean up any created files
                            for path in [forecast_path, network_path, inventory_path]:
                                if path and Path(path).exists():
                                    Path(path).unlink()
                            raise

                        # Pre-validate network configuration for common issues
                        if network_path:
                            try:
                                import pandas as pd
                                df_locs = pd.read_excel(network_path, sheet_name="Locations", engine="openpyxl")
                                mfg_locations = df_locs[df_locs['type'].str.lower() == 'manufacturing']

                                if not mfg_locations.empty:
                                    missing_prod_rate = []
                                    if 'production_rate' not in df_locs.columns:
                                        missing_prod_rate = mfg_locations['id'].tolist()
                                    else:
                                        missing_prod_rate = mfg_locations[
                                            pd.isna(mfg_locations['production_rate'])
                                        ]['id'].tolist()

                                    if missing_prod_rate:
                                        st.error(
                                            f"❌ **Missing Required Parameter: production_rate**\n\n"
                                            f"Manufacturing location(s) **{', '.join(str(x) for x in missing_prod_rate)}** "
                                            f"are missing the required `production_rate` column.\n\n"
                                            f"**To fix:**\n"
                                            f"1. Add a `production_rate` column to the Locations sheet\n"
                                            f"2. Set the value to **1400.0** (units per hour)\n\n"
                                            f"See `NETWORK_CONFIG_UPDATE_INSTRUCTIONS.md` for detailed guidance."
                                        )
                                        st.stop()
                            except Exception as e:
                                # If pre-validation fails, let normal parsing show the error
                                pass

                        parser = MultiFileParser(
                            forecast_file=forecast_path,
                            network_file=network_path,
                            inventory_file=inventory_path
                        )

                        forecast_obj, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

                        # Parse product aliases (optional)
                        product_aliases = None
                        try:
                            product_aliases = parser.parse_product_aliases()
                        except Exception:
                            pass  # Alias sheet is optional

                        # Parse inventory if provided
                        inventory_snapshot = None
                        if inventory_path:
                            try:
                                inventory_snapshot = parser.parse_inventory()
                            except Exception as e:
                                st.warning(f"⚠️ Error parsing inventory: {e}")

                        # Wrap truck_schedules list in TruckScheduleCollection
                        from src.models.truck_schedule import TruckScheduleCollection
                        truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

                        # Find manufacturing site (parser returns ManufacturingSite objects directly)
                        from src.models.manufacturing import ManufacturingSite
                        manufacturing_site = next(
                            (loc for loc in locations if isinstance(loc, ManufacturingSite)),
                            None
                        )

                        if manufacturing_site is None:
                            st.error("❌ No manufacturing location found in network configuration")
                        else:
                            # Validate consistency
                            validation_results = parser.validate_consistency(forecast_obj, locations, routes)

                            # Store in session state
                            session_state.store_parsed_data(
                                forecast=forecast_obj,
                                locations=locations,
                                routes=routes,
                                labor_calendar=labor_calendar,
                                truck_schedules=truck_schedules,
                                cost_structure=cost_structure,
                                manufacturing_site=manufacturing_site,
                                forecast_filename=forecast_file.name,
                                network_filename=network_file.name,
                                initial_inventory=inventory_snapshot,
                                product_aliases=product_aliases,
                                inventory_filename=inventory_file.name if inventory_file else None,
                            )

                            # Clear any previous planning results
                            session_state.clear_planning_results()

                            # Display results
                            st.success("✅ Parsing completed successfully!")
                            st.success("✅ Data stored in session state")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Forecast Entries", len(forecast_obj.entries))
                                st.metric("Locations", len(locations))
                            with col2:
                                st.metric("Routes", len(routes))
                                st.metric("Labor Days", len(labor_calendar.days))
                            with col3:
                                st.metric("Truck Schedules", len(truck_schedules))

                            # Show validation warnings
                            if validation_results["warnings"]:
                                st.warning("⚠️ Validation Warnings:")
                                for warning in validation_results["warnings"]:
                                    st.write(f"- {warning}")
                            else:
                                st.success("✅ All validation checks passed!")

                            # Next step guidance
                            st.divider()
                            st.info("✅ Data loaded successfully! Check the **Summary** tab to review your data, or go to **Planning** to run optimization.")

                        # Clean up temp files
                        Path(forecast_path).unlink()
                        Path(network_path).unlink()
                        if inventory_path:
                            Path(inventory_path).unlink()

                    except Exception as e:
                        st.error(f"❌ Error parsing files: {e}")
                        import traceback
                        with st.expander("Error Details"):
                            st.code(traceback.format_exc())

    else:
        st.info("👆 Please upload both files to get started")

        st.divider()

        st.markdown("""
        ### 📄 Required File Formats

        **Forecast File** can be in one of two formats:

        1. **Standard Format** - sheet named "Forecast" with columns:
           - `location_id`: Destination location ID
           - `product_id`: Product identifier
           - `date`: Forecast date (YYYY-MM-DD)
           - `quantity`: Forecasted demand (units)

        2. **SAP IBP Format** - Wide format export with:
           - Sheet name containing patterns like "RET", "IBP", "G610", etc.
           - Dates as columns (DD.MM.YYYY format)
           - Product ID and Location ID columns
           - Automatically detected and converted to standard format

        **Network Configuration File** should contain 5 sheets:
        - `Locations`: Location definitions (id, name, type, storage_mode)
        - `Routes`: Routes between locations (origin_id, destination_id, transit_time_days, cost)
        - `LaborCalendar`: Daily labor availability (date, fixed_hours, rates)
        - `TruckSchedules`: Truck departure schedules (truck_name, departure_type, destination_id, day_of_week)
        - `CostParameters`: Cost structure (production_cost_per_unit, labor rates, storage costs, waste multiplier)

        See `data/examples/EXCEL_TEMPLATE_SPEC.md` for complete specification.
        """)


# ===========================
# TAB 2: DATA SUMMARY
# ===========================

with tab_summary:
    # Check if data uploaded
    if not session_state.is_data_uploaded():
        st.warning("⚠️ No data loaded. Please upload files in the **Upload** tab first.")
        st.stop()

    # Get data
    data = session_state.get_parsed_data()
    stats = session_state.get_summary_stats()

    # Summary metrics
    st.markdown(section_header("Overview", level=2, icon="📈"), unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            colored_metric("Locations", str(stats.get('locations', 0)), "primary"),
            unsafe_allow_html=True
        )
        st.markdown(
            colored_metric("Routes", str(stats.get('routes', 0)), "primary"),
            unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            colored_metric("Forecast Entries", f"{stats.get('forecast_entries', 0):,}", "secondary"),
            unsafe_allow_html=True
        )
        st.markdown(
            colored_metric("Products", str(stats.get('products_in_forecast', 0)), "secondary"),
            unsafe_allow_html=True
        )

    with col3:
        st.markdown(
            colored_metric("Total Demand", f"{stats.get('total_demand', 0):,.0f}", "accent"),
            unsafe_allow_html=True
        )
        st.markdown(
            colored_metric("Planning Days", str(stats.get('date_range_days', 0)), "accent"),
            unsafe_allow_html=True
        )

    with col4:
        st.markdown(
            colored_metric("Labor Days", str(stats.get('labor_days', 0)), "success"),
            unsafe_allow_html=True
        )
        st.markdown(
            colored_metric("Trucks/Week", str(stats.get('truck_schedules', 0)), "success"),
            unsafe_allow_html=True
        )

    # File information
    if st.session_state.get('forecast_filename'):
        st.caption(f"**Forecast File:** {st.session_state['forecast_filename']}")
    if st.session_state.get('network_filename'):
        st.caption(f"**Network File:** {st.session_state['network_filename']}")

    st.divider()

    # Tabbed data views
    data_tab1, data_tab2, data_tab3, data_tab4, data_tab5, data_tab6 = st.tabs([
        "Forecast",
        "Locations",
        "Routes",
        "Labor Calendar",
        "Truck Schedules",
        "Cost Parameters"
    ])

    with data_tab1:
        st.markdown(section_header("Forecast Data", level=3), unsafe_allow_html=True)

        forecast = data['forecast']

        if forecast and forecast.entries:
            # Summary stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Entries", len(forecast.entries))
            with col2:
                st.metric("Date Range", f"{stats.get('date_range_start')} to {stats.get('date_range_end')}")
            with col3:
                st.metric("Total Demand", f"{sum(e.quantity for e in forecast.entries):,.0f} units")

            st.divider()

            # Convert to dataframe
            forecast_data = []
            for entry in forecast.entries:
                forecast_data.append({
                    'Location': entry.location_id,
                    'Product': entry.product_id,
                    'Date': entry.forecast_date,
                    'Quantity': entry.quantity,
                })

            df = pd.DataFrame(forecast_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(df)} forecast entries")
        else:
            st.info("No forecast data available")

    with data_tab2:
        st.markdown(section_header("Locations", level=3), unsafe_allow_html=True)

        locations = data['locations']

        if locations:
            loc_data = []
            for loc in locations:
                loc_data.append({
                    'ID': loc.id,
                    'Name': loc.name,
                    'Type': loc.type,
                    'Storage Mode': loc.storage_mode,
                    'Capacity': loc.capacity or '-',
                })

            df = pd.DataFrame(loc_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(df)} locations")
        else:
            st.info("No location data available")

    with data_tab3:
        st.markdown(section_header("Routes", level=3), unsafe_allow_html=True)

        routes = data['routes']

        if routes:
            route_data = []
            for route in routes:
                route_data.append({
                    'ID': route.id,
                    'Origin': route.origin_id,
                    'Destination': route.destination_id,
                    'Transit Days': route.transit_time_days,
                    'Mode': route.transport_mode,
                    'Cost/Unit': f"${route.cost:.2f}" if route.cost else '-',
                })

            df = pd.DataFrame(route_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(df)} routes")
        else:
            st.info("No route data available")

    with data_tab4:
        st.markdown(section_header("Labor Calendar", level=3), unsafe_allow_html=True)

        labor_calendar = data['labor_calendar']

        if labor_calendar and labor_calendar.days:
            labor_data = []
            for day in labor_calendar.days[:100]:  # Show first 100 days
                labor_data.append({
                    'Date': day.date,
                    'Fixed Hours': day.fixed_hours,
                    'Regular Rate': f"${day.regular_rate:.2f}",
                    'Overtime Rate': f"${day.overtime_rate:.2f}",
                    'Non-Fixed Rate': f"${day.non_fixed_rate:.2f}" if day.non_fixed_rate is not None else "N/A",
                    'Is Fixed Day': '✓' if day.is_fixed_day else '',
                })

            df = pd.DataFrame(labor_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Showing first 100 of {len(labor_calendar.days)} days")
        else:
            st.info("No labor calendar data available")

    with data_tab5:
        st.markdown(section_header("Truck Schedules", level=3), unsafe_allow_html=True)

        truck_schedules = data['truck_schedules']

        if truck_schedules:
            truck_data = []
            for truck in truck_schedules:
                truck_data.append({
                    'ID': truck.id,
                    'Name': truck.truck_name,
                    'Type': truck.departure_type,
                    'Destination': truck.destination_id,
                    'Day of Week': truck.day_of_week or 'Daily',
                    'Capacity': f"{truck.capacity:,.0f} units",
                    'Pallets': truck.pallet_capacity,
                })

            df = pd.DataFrame(truck_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(df)} truck schedules")
        else:
            st.info("No truck schedule data available")

    with data_tab6:
        st.markdown(section_header("Cost Parameters", level=3), unsafe_allow_html=True)

        cost_structure = data['cost_structure']

        if cost_structure:
            cost_data = [
                {'Parameter': 'Production Cost per Unit', 'Value': f"${cost_structure.production_cost_per_unit:.2f}"},
                {'Parameter': 'Default Regular Rate', 'Value': f"${cost_structure.default_regular_rate:.2f}/hour"},
                {'Parameter': 'Default Overtime Rate', 'Value': f"${cost_structure.default_overtime_rate:.2f}/hour"},
                {'Parameter': 'Default Non-Fixed Rate', 'Value': f"${cost_structure.default_non_fixed_rate:.2f}/hour"},
                {'Parameter': 'Storage Cost (Frozen)', 'Value': f"${cost_structure.storage_cost_frozen_per_unit_day:.3f}/unit/day"},
                {'Parameter': 'Storage Cost (Ambient)', 'Value': f"${cost_structure.storage_cost_ambient_per_unit_day:.3f}/unit/day"},
                {'Parameter': 'Waste Cost Multiplier', 'Value': f"{cost_structure.waste_cost_multiplier}x"},
                {'Parameter': 'Shortage Penalty', 'Value': f"${cost_structure.shortage_penalty_per_unit:.2f}/unit"},
            ]

            df = pd.DataFrame(cost_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No cost parameter data available")


# ===========================
# TAB 3: FORECAST EDITOR
# ===========================

with tab_editor:
    # Check if data uploaded
    if not session_state.is_data_uploaded():
        st.warning("⚠️ No data loaded. Please upload files in the **Upload** tab first.")
        st.stop()

    st.markdown("""
    <div class="info-box">
        <div style="font-weight: 600; margin-bottom: 8px;">✏️ Forecast Editor</div>
        <div>Adjust demand forecasts without re-uploading Excel files.</div>
        <div style="margin-top: 8px; font-size: 13px; color: #757575;">
            Make changes inline, see the impact, and apply adjustments to your planning data.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Get forecast data
    data = session_state.get_parsed_data()
    forecast = data['forecast']

    if not forecast or not forecast.entries:
        st.info("No forecast data available to edit")
        st.stop()

    # Convert forecast to editable DataFrame
    forecast_df = pd.DataFrame([{
        'Location': e.location_id,
        'Product': e.product_id,
        'Date': e.forecast_date,
        'Quantity': e.quantity
    } for e in forecast.entries])

    # Add filters
    st.markdown(section_header("Filters", level=3), unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        locations_available = sorted(forecast_df['Location'].unique())
        selected_locations = st.multiselect(
            "Filter by Location",
            options=locations_available,
            default=None,
            key="editor_location_filter"
        )

    with col2:
        products_available = sorted(forecast_df['Product'].unique())
        selected_products = st.multiselect(
            "Filter by Product",
            options=products_available,
            default=None,
            key="editor_product_filter"
        )

    with col3:
        # Date range filter
        min_date = forecast_df['Date'].min()
        max_date = forecast_df['Date'].max()
        date_range = st.date_input(
            "Filter by Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="editor_date_filter"
        )

    # Apply filters
    filtered_df = forecast_df.copy()

    if selected_locations:
        filtered_df = filtered_df[filtered_df['Location'].isin(selected_locations)]

    if selected_products:
        filtered_df = filtered_df[filtered_df['Product'].isin(selected_products)]

    if date_range and len(date_range) == 2:
        filtered_df = filtered_df[
            (filtered_df['Date'] >= date_range[0]) &
            (filtered_df['Date'] <= date_range[1])
        ]

    st.divider()

    # Display editable data
    st.markdown(section_header("Edit Forecast Data", level=3), unsafe_allow_html=True)
    st.caption(f"Showing {len(filtered_df)} of {len(forecast_df)} entries")

    edited_df = st.data_editor(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Quantity": st.column_config.NumberColumn(
                "Quantity",
                help="Forecasted demand in units",
                min_value=0,
                format="%.0f"
            ),
            "Date": st.column_config.DateColumn(
                "Date",
                help="Forecast date"
            )
        }
    )

    # Check for changes
    changes_made = not filtered_df.equals(edited_df)

    if changes_made:
        st.divider()
        st.markdown(section_header("Changes Summary", level=3), unsafe_allow_html=True)

        # Calculate deltas
        delta_quantity = edited_df['Quantity'].sum() - filtered_df['Quantity'].sum()
        pct_change = (delta_quantity / filtered_df['Quantity'].sum() * 100) if filtered_df['Quantity'].sum() > 0 else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Original Total", f"{filtered_df['Quantity'].sum():,.0f} units")
        with col2:
            st.metric("Adjusted Total", f"{edited_df['Quantity'].sum():,.0f} units")
        with col3:
            st.metric("Net Change", f"{delta_quantity:+,.0f} units", f"{pct_change:+.1f}%")

        st.divider()

        # Apply changes button
        if st.button("✅ Apply Changes to Forecast", type="primary", use_container_width=True):
            # Merge edited data back into full forecast
            # Update the original forecast_df with edited values
            for idx, row in edited_df.iterrows():
                mask = (
                    (forecast_df['Location'] == row['Location']) &
                    (forecast_df['Product'] == row['Product']) &
                    (forecast_df['Date'] == row['Date'])
                )
                forecast_df.loc[mask, 'Quantity'] = row['Quantity']

            # Convert back to Forecast object
            new_entries = []
            for _, row in forecast_df.iterrows():
                entry = ForecastEntry(
                    location_id=str(row['Location']),
                    product_id=str(row['Product']),
                    forecast_date=row['Date'],
                    quantity=float(row['Quantity'])
                )
                new_entries.append(entry)

            new_forecast = Forecast(
                name=f"{forecast.name} (Edited)",
                entries=new_entries,
                creation_date=date.today()
            )

            # Update session state
            data['forecast'] = new_forecast
            session_state.store_parsed_data(
                forecast=new_forecast,
                locations=data['locations'],
                routes=data['routes'],
                labor_calendar=data['labor_calendar'],
                truck_schedules=data['truck_schedules'],
                cost_structure=data['cost_structure'],
                manufacturing_site=data['manufacturing_site'],
                forecast_filename=st.session_state.get('forecast_filename', 'edited_forecast.xlsx'),
                network_filename=st.session_state.get('network_filename', 'network.xlsx'),
            )

            # Clear planning results since forecast changed
            session_state.clear_planning_results()

            st.success("✅ Forecast updated successfully! Planning results have been cleared.")
            st.info("⚡ Run planning again to see the impact of your changes.")
            st.rerun()
    else:
        st.info("ℹ️ Make changes to the forecast data above, then apply them to your planning data.")
