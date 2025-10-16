"""Test script for daily snapshot UI component.

Run with: streamlit run test_daily_snapshot_ui.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from datetime import date, timedelta

from ui.components.styling import apply_custom_css
from ui.components.daily_snapshot import render_daily_snapshot
from src.models.location import Location
from src.production.scheduler import ProductionSchedule, ProductionBatch
from src.models.shipment import Shipment

# Page config
st.set_page_config(
    page_title="Daily Snapshot Test",
    page_icon="📸",
    layout="wide",
)

# Apply styling
apply_custom_css()

st.title("📸 Daily Snapshot Component Test")

st.markdown("""
This is a test page for the daily snapshot UI component. It uses mock data
to demonstrate the component's features.
""")

st.divider()

# Create mock data
manufacturing_site_id = "6122"
start_date = date(2025, 1, 6)  # Monday
end_date = start_date + timedelta(days=13)  # Two weeks

# Mock locations
locations = {
    "6122": Location(
        location_id="6122",
        name="Manufacturing Site",
        location_type="manufacturing",
        address="123 Factory St",
        storage_capacity_units=100000,
    ),
    "6104": Location(
        location_id="6104",
        name="NSW/ACT Hub",
        location_type="hub",
        address="456 Hub Rd",
        storage_capacity_units=50000,
    ),
    "6125": Location(
        location_id="6125",
        name="VIC/TAS/SA Hub",
        location_type="hub",
        address="789 Hub Ave",
        storage_capacity_units=50000,
    ),
    "6103": Location(
        location_id="6103",
        name="Sydney Breadroom",
        location_type="breadroom",
        address="101 Bread St",
    ),
    "6130": Location(
        location_id="6130",
        name="Perth Breadroom",
        location_type="breadroom",
        address="202 Bread Ave",
    ),
}

# Mock production batches
batches = []
current_date = start_date
batch_id = 1

# Create production every weekday for 2 weeks
while current_date <= end_date:
    if current_date.weekday() < 5:  # Monday-Friday
        # Product 176283
        batches.append(ProductionBatch(
            id=f"BATCH-{batch_id:04d}",
            product_id="176283",
            manufacturing_site_id=manufacturing_site_id,
            production_date=current_date,
            quantity=5000,
            labor_hours_used=8.5,
            production_cost=5000 * 1.2,
        ))
        batch_id += 1

        # Product 176284
        batches.append(ProductionBatch(
            id=f"BATCH-{batch_id:04d}",
            product_id="176284",
            manufacturing_site_id=manufacturing_site_id,
            production_date=current_date,
            quantity=3000,
            labor_hours_used=5.1,
            production_cost=3000 * 1.2,
        ))
        batch_id += 1

    current_date += timedelta(days=1)

# Build daily totals and labor hours
daily_totals = {}
daily_labor_hours = {}

for batch in batches:
    daily_totals[batch.production_date] = daily_totals.get(batch.production_date, 0) + batch.quantity
    daily_labor_hours[batch.production_date] = daily_labor_hours.get(batch.production_date, 0) + batch.labor_hours_used

# Create production schedule
production_schedule = ProductionSchedule(
    manufacturing_site_id=manufacturing_site_id,
    schedule_start_date=start_date,
    schedule_end_date=end_date,
    production_batches=batches,
    daily_totals=daily_totals,
    daily_labor_hours=daily_labor_hours,
    infeasibilities=[],
    total_units=sum(daily_totals.values()),
    total_labor_hours=sum(daily_labor_hours.values()),
    requirements=None,
)

# Mock shipments
shipments = []
shipment_id = 1

# Create shipments from manufacturing to hubs
for batch in batches[:10]:  # First 10 batches
    shipment_date = batch.production_date + timedelta(days=1)  # Ship next day
    arrival_date = shipment_date + timedelta(days=1)  # Arrive day after

    destination = "6104" if shipment_id % 2 == 0 else "6125"

    shipments.append(Shipment(
        shipment_id=f"SHIP-{shipment_id:04d}",
        product_id=batch.product_id,
        origin_id=manufacturing_site_id,
        destination_id=destination,
        quantity=batch.quantity,
        departure_date=shipment_date,
        arrival_date=arrival_date,
        production_date=batch.production_date,
        transport_mode="ambient",
        assigned_truck_id=f"TRUCK-{shipment_id % 3 + 1}",
    ))
    shipment_id += 1

# Mock forecast (for demand satisfaction)
from src.models.forecast import Forecast, ForecastEntry

forecast_entries = []
for i in range(10):
    forecast_date = start_date + timedelta(days=i)

    # Add demand for Sydney
    forecast_entries.append(ForecastEntry(
        location_id="6103",
        product_id="176283",
        date=forecast_date,
        quantity=1000,
    ))

    # Add demand for Perth
    forecast_entries.append(ForecastEntry(
        location_id="6130",
        product_id="176284",
        date=forecast_date,
        quantity=500,
    ))

forecast = Forecast(
    entries=forecast_entries,
    start_date=start_date,
    end_date=end_date,
    source_file="mock_forecast.xlsx",
)

# Store in session state for the component to access
if 'forecast' not in st.session_state:
    st.session_state['forecast'] = forecast

# Create results dict
results = {
    'production_schedule': production_schedule,
    'shipments': shipments,
    'cost_breakdown': None,  # Not needed for this test
}

# Render the component
st.divider()

render_daily_snapshot(
    results=results,
    locations=locations,
    key_prefix="test_snapshot"
)

# Show component info
with st.expander("📋 Component Information", expanded=False):
    st.markdown("""
    ### Daily Snapshot Component

    This component displays comprehensive daily inventory information:

    **Features:**
    - 📅 Interactive date selector with previous/next navigation
    - 📊 Summary metrics (inventory, in-transit, production, demand)
    - 📦 Location-based inventory with batch details
    - 🚚 In-transit shipments
    - 🏭 Manufacturing activity
    - ⬇️ Inflows (production, arrivals)
    - ⬆️ Outflows (departures, demand)
    - ✅ Demand satisfaction tracking

    **Color Coding:**
    - **Batch Age:** Green (fresh 0-3 days), Yellow (medium 4-7 days), Red (old 8+ days)
    - **Inflows:** Blue (production), Green (arrivals)
    - **Outflows:** Yellow (departures), Light blue (demand)
    - **Demand Status:** Green (met), Yellow (shortage)

    **Mock Data:**
    - Production: Monday-Friday for 2 weeks
    - Products: 176283 (5,000 units/day), 176284 (3,000 units/day)
    - Shipments: First 10 batches shipped to hubs
    - Demand: Daily demand for Sydney (1,000) and Perth (500)
    """)

st.divider()

# Additional controls
st.markdown("### Test Controls")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Production Schedule Info**")
    st.metric("Total Batches", len(production_schedule.production_batches))
    st.metric("Total Units", f"{production_schedule.total_units:,.0f}")
    st.metric("Total Labor Hours", f"{production_schedule.total_labor_hours:.1f}h")

with col2:
    st.markdown("**Shipment Info**")
    st.metric("Total Shipments", len(shipments))
    st.metric("Total Shipped Units", f"{sum(s.quantity for s in shipments):,.0f}")
    st.metric("Unique Destinations", len(set(s.destination_id for s in shipments)))
