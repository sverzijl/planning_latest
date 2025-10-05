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
                <li><strong>Forecast File:</strong> Sales demand by location and date</li>
                <li><strong>Network Configuration File:</strong> Locations, routes, labor, trucks, and costs</li>
            </ol>
            <div style="margin-top: 12px; font-size: 13px; color: #757575;">
                This separation allows you to update forecast data frequently while keeping network configuration stable.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Two-column layout for file uploads
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(section_header("1️⃣ Forecast File", level=3), unsafe_allow_html=True)
        forecast_file = st.file_uploader(
            "Choose forecast file",
            type=["xlsm", "xlsx"],
            help="Excel file containing Forecast sheet with demand data",
            key="forecast_uploader",
        )
        if forecast_file:
            st.markdown(success_badge(forecast_file.name), unsafe_allow_html=True)

    with col2:
        st.markdown(section_header("2️⃣ Network Configuration File", level=3), unsafe_allow_html=True)
        network_file = st.file_uploader(
            "Choose network config file",
            type=["xlsm", "xlsx"],
            help="Excel file with Locations, Routes, LaborCalendar, TruckSchedules, and CostParameters sheets",
            key="network_uploader",
        )
        if network_file:
            st.markdown(success_badge(network_file.name), unsafe_allow_html=True)

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

        # Forecast tab
        if forecast_file:
            with preview_tabs[tab_idx]:
                try:
                    df_forecast = pd.read_excel(forecast_file, sheet_name="Forecast", engine="openpyxl")
                    st.dataframe(df_forecast.head(100), use_container_width=True)
                    st.caption(f"📊 {len(df_forecast)} forecast entries (showing first 100)")
                except Exception as e:
                    st.error(f"Error reading Forecast sheet: {e}")
                    st.info("If you have a SAP IBP file, use the SAP IBP converter (coming soon)")
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
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f_forecast:
                            f_forecast.write(forecast_file.getvalue())
                            forecast_path = f_forecast.name

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as f_network:
                            f_network.write(network_file.getvalue())
                            network_path = f_network.name

                        # Parse files
                        parser = MultiFileParser(
                            forecast_file=forecast_path,
                            network_file=network_path
                        )

                        forecast_obj, locations, routes, labor_calendar, truck_schedules_list, cost_structure = parser.parse_all()

                        # Wrap truck_schedules list in TruckScheduleCollection
                        from src.models.truck_schedule import TruckScheduleCollection
                        truck_schedules = TruckScheduleCollection(schedules=truck_schedules_list)

                        # Find manufacturing site
                        manufacturing_site = None
                        for loc in locations:
                            if loc.type == LocationType.MANUFACTURING:
                                # Convert Location to ManufacturingSite
                                from src.models.manufacturing import ManufacturingSite
                                manufacturing_site = ManufacturingSite(
                                    id=loc.id,
                                    name=loc.name,
                                    type=loc.type,
                                    storage_mode=loc.storage_mode,
                                    capacity=loc.capacity,
                                    latitude=loc.latitude,
                                    longitude=loc.longitude,
                                    production_rate=1400.0,  # Default
                                    labor_calendar=labor_calendar,
                                    changeover_time_hours=0.5,  # Default
                                )
                                break

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

        **Forecast File** should contain a sheet named "Forecast" with columns:
        - `location_id`: Destination location ID
        - `product_id`: Product identifier
        - `date`: Forecast date (YYYY-MM-DD)
        - `quantity`: Forecasted demand (units)

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
