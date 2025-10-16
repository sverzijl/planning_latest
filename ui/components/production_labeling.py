"""UI component for production labeling requirements."""

import streamlit as st
import pandas as pd
from datetime import date as Date, timedelta
from typing import Optional

from src.analysis.production_labeling_report import ProductionLabelingReportGenerator


def render_production_labeling_view(optimization_model, optimization_result):
    """Render production labeling requirements view.

    Args:
        optimization_model: The optimization model instance (for leg_states)
        optimization_result: The optimization solution dictionary
    """
    st.markdown("### 🏷️ Production Labeling Requirements")

    st.markdown("""
    <div class="info-box">
        <strong>Factory Labeling Guide:</strong> This report shows which quantities need
        frozen vs. ambient labeling based on their destination routes. Stock going through
        freezers (like Lineage) requires different labeling at production time.
    </div>
    """, unsafe_allow_html=True)

    # Debug info
    with st.expander("🔍 Debug Info", expanded=False):
        st.write("**Optimization Result Keys:**", list(optimization_result.keys()))
        st.write("**Batch Tracking Enabled:**", optimization_result.get('use_batch_tracking', False))
        st.write("**Batch Shipments Count:**", len(optimization_result.get('batch_shipments', [])))
        st.write("**Production Batches Count:**", len(optimization_result.get('production_by_date_product', {})))

        # Check for both legacy (leg_arrival_state) and unified (route_arrival_state) models
        has_leg_state = hasattr(optimization_model, 'leg_arrival_state')
        has_route_state = hasattr(optimization_model, 'route_arrival_state')
        st.write("**Has leg_arrival_state (legacy):**", has_leg_state)
        st.write("**Has route_arrival_state (unified):**", has_route_state)

        if has_leg_state:
            frozen_legs = [(o, d) for (o, d), state in optimization_model.leg_arrival_state.items() if state == 'frozen']
            st.write("**Frozen Legs (legacy):**", frozen_legs)
        if has_route_state:
            frozen_routes = [(o, d) for (o, d), state in optimization_model.route_arrival_state.items() if state == 'frozen']
            st.write("**Frozen Routes (unified):**", frozen_routes)

    # Create report generator
    generator = ProductionLabelingReportGenerator(optimization_result)

    # Set leg/route states from model (support both legacy and unified models)
    if hasattr(optimization_model, 'leg_arrival_state'):
        # Legacy model
        generator.set_leg_states(optimization_model.leg_arrival_state)
    elif hasattr(optimization_model, 'route_arrival_state'):
        # Unified model
        generator.set_leg_states(optimization_model.route_arrival_state)
    else:
        st.warning("⚠️ Route state information not available from model. Cannot distinguish frozen vs ambient routes.")

    # Generate report
    df = generator.generate_report_dataframe()

    if df.empty:
        st.warning("No production labeling requirements found.")

        # Diagnostic messages
        if not optimization_result.get('use_batch_tracking', False):
            st.info("""
            **Batch tracking is disabled.** Production labeling requires batch tracking to be enabled.

            To enable: Go to **Planning → Optimization** and check **"Enable Batch Tracking"** before solving.
            """)
        elif not optimization_result.get('batch_shipments'):
            st.warning("No batch_shipments data in solution. This may indicate the model wasn't solved with batch tracking enabled.")
        else:
            st.info("Production data exists but no shipments from manufacturing found. Check if production occurred.")

        return

    # Summary metrics
    st.markdown("#### Summary")
    col1, col2, col3, col4 = st.columns(4)

    total_production = df['Total Quantity'].sum()
    total_frozen = df['Frozen Labels'].sum()
    total_ambient = df['Ambient Labels'].sum()
    split_batches = len(df[df['Label Notes'].str.contains('SPLIT')])

    with col1:
        st.metric("Total Production", f"{int(total_production):,} units")
    with col2:
        st.metric("Frozen Labels", f"{int(total_frozen):,} units",
                  delta=f"{total_frozen/total_production*100:.1f}%" if total_production > 0 else None)
    with col3:
        st.metric("Ambient Labels", f"{int(total_ambient):,} units",
                  delta=f"{total_ambient/total_production*100:.1f}%" if total_production > 0 else None)
    with col4:
        st.metric("Split Batches", str(split_batches))

    st.divider()

    # Filter options
    st.markdown("#### Filter Options")
    col1, col2, col3 = st.columns(3)

    with col1:
        # Date range filter
        min_date = pd.to_datetime(df['Production Date']).min().date()
        max_date = pd.to_datetime(df['Production Date']).max().date()

        date_range = st.date_input(
            "Production Date Range",
            value=(min_date, min(min_date + timedelta(days=7), max_date)),
            min_value=min_date,
            max_value=max_date,
            key="labeling_date_range"
        )

    with col2:
        # Label type filter
        label_filter = st.selectbox(
            "Label Type",
            options=["All", "Frozen Only", "Ambient Only", "Split Batches"],
            key="labeling_type_filter"
        )

    with col3:
        # Product filter
        products = ['All'] + sorted(df['Product'].unique().tolist())
        product_filter = st.selectbox(
            "Product",
            options=products,
            key="labeling_product_filter"
        )

    # Apply filters
    filtered_df = df.copy()

    # Date filter
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df['Production Date']).dt.date >= start_date) &
            (pd.to_datetime(filtered_df['Production Date']).dt.date <= end_date)
        ]

    # Label type filter
    if label_filter == "Frozen Only":
        filtered_df = filtered_df[filtered_df['Frozen Labels'] > 0]
        filtered_df = filtered_df[filtered_df['Ambient Labels'] == 0]
    elif label_filter == "Ambient Only":
        filtered_df = filtered_df[filtered_df['Ambient Labels'] > 0]
        filtered_df = filtered_df[filtered_df['Frozen Labels'] == 0]
    elif label_filter == "Split Batches":
        filtered_df = filtered_df[filtered_df['Label Notes'].str.contains('SPLIT')]

    # Product filter
    if product_filter != 'All':
        filtered_df = filtered_df[filtered_df['Product'] == product_filter]

    st.divider()

    # Display table
    st.markdown("#### Production Labeling Schedule")

    if filtered_df.empty:
        st.info("No records match the selected filters.")
    else:
        # Style the dataframe
        def highlight_split_batches(row):
            if 'SPLIT' in str(row['Label Notes']):
                return ['background-color: #fff3cd'] * len(row)
            return [''] * len(row)

        styled_df = filtered_df.style.apply(highlight_split_batches, axis=1)

        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True
        )

        # Export button
        st.markdown("#### Export")
        col1, col2 = st.columns([3, 1])

        with col2:
            csv = filtered_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"production_labeling_{Date.today().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        # Detailed instructions for split batches
        split_batches_df = filtered_df[filtered_df['Label Notes'].str.contains('SPLIT')]
        if not split_batches_df.empty:
            st.divider()
            st.markdown("#### ⚠️ Split Batch Details")
            st.markdown("""
            <div class="warning-box">
                <strong>Important:</strong> The following batches require BOTH frozen and ambient
                labeling. Coordinate with packaging team to ensure correct label quantities.
            </div>
            """, unsafe_allow_html=True)

            for _, row in split_batches_df.iterrows():
                with st.expander(f"{row['Production Date']} - {row['Product']}", expanded=False):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**Frozen Labels:**")
                        st.metric("Quantity", f"{int(row['Frozen Labels']):,} units")
                        st.caption(f"Destinations: {row['Frozen Destinations']}")

                    with col2:
                        st.markdown("**Ambient Labels:**")
                        st.metric("Quantity", f"{int(row['Ambient Labels']):,} units")
                        st.caption(f"Destinations: {row['Ambient Destinations']}")
