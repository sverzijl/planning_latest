# Production Labeling Requirements

## Overview

When stock is sent via frozen routes (e.g., through Lineage cold storage), it requires different labeling at the factory. This document explains how to identify frozen vs. ambient labeling requirements from optimization results.

## The Problem

**Factory Requirement:** Production team needs to know **at production time** which batches need:
- **FROZEN labels** (for routes through freezers)
- **AMBIENT labels** (for direct/ambient routes)

**Challenge:** A single production day may require BOTH label types if output goes to multiple routes.

### Example Scenario

**Monday Production: 5,000 units of Product A**
- 3,000 units → Lineage (frozen route) → **Requires FROZEN labels**
- 2,000 units → 6125 Hub (ambient route) → **Requires AMBIENT labels**

## Solution

### Automated Labeling Report

The system generates production labeling requirements based on optimization routing decisions.

#### Key Features

1. **Daily Production Split:** Shows how much of each product needs frozen vs. ambient labels
2. **Destination Tracking:** Identifies which destinations receive frozen/ambient shipments
3. **Split Batch Alerts:** Highlights when a single production day requires both label types
4. **Export Capability:** Generate CSV/Excel reports for factory floor

## Usage

### Option 1: Python API

```python
from src.analysis import ProductionLabelingReportGenerator

# After solving optimization model
result = model.solve(...)

# Create report generator
generator = ProductionLabelingReportGenerator(result.solution)
generator.set_leg_states(model.leg_arrival_state)

# Generate report
requirements = generator.generate_labeling_requirements()

# Print summary
generator.print_summary()

# Export to Excel
generator.export_to_excel('production_labeling_report.xlsx')

# Get specific date
today_requirements = generator.generate_daily_work_orders(date(2025, 1, 15))
for req in today_requirements:
    print(f"{req.product_id}:")
    print(f"  Frozen:  {req.frozen_quantity:,.0f} units → {req.frozen_destinations}")
    print(f"  Ambient: {req.ambient_quantity:,.0f} units → {req.ambient_destinations}")
```

### Option 2: Streamlit UI

The production labeling view is integrated into the Results page:

1. **Run Optimization** in the Planning tab
2. **Navigate to Results** → Production Labeling section
3. **View labeling requirements** by date, product, or label type
4. **Export CSV** for factory distribution

#### UI Features

- **Filter by date range** to focus on upcoming production
- **Filter by label type** (frozen only, ambient only, split batches)
- **Highlight split batches** that require both label types
- **Download CSV** for factory floor systems

### Option 3: Work Order Integration

Integrate into existing factory systems:

```python
# Daily production work order generation
from src.analysis import ProductionLabelingReportGenerator
from datetime import date

# Get today's work orders
generator = ProductionLabelingReportGenerator(optimization_result)
generator.set_leg_states(model.leg_arrival_state)

work_orders = generator.generate_daily_work_orders(date.today())

# Export to factory system format
for wo in work_orders:
    factory_system.create_work_order(
        date=wo.production_date,
        product=wo.product_id,
        frozen_qty=wo.frozen_quantity,
        ambient_qty=wo.ambient_quantity,
        instructions=wo._get_label_notes()
    )
```

## Report Format

### LabelingRequirement Object

```python
@dataclass
class LabelingRequirement:
    production_date: Date
    product_id: str
    frozen_quantity: float       # Units requiring frozen labels
    ambient_quantity: float      # Units requiring ambient labels
    total_quantity: float        # Total production
    frozen_destinations: List[str]   # e.g., ['Lineage', '6130']
    ambient_destinations: List[str]  # e.g., ['6125', '6104']
```

### CSV Export Format

| Production Date | Product | Total Quantity | Frozen Labels | Ambient Labels | Frozen % | Frozen Destinations | Ambient Destinations | Label Notes |
|-----------------|---------|----------------|---------------|----------------|----------|---------------------|----------------------|-------------|
| 2025-01-15 | PROD-A | 5000 | 3000 | 2000 | 60.0% | Lineage | 6125 | SPLIT BATCH: 3000 frozen, 2000 ambient |
| 2025-01-15 | PROD-B | 2000 | 2000 | 0 | 100.0% | Lineage | - | ALL FROZEN LABELS |
| 2025-01-16 | PROD-A | 4000 | 0 | 4000 | 0.0% | - | 6125, 6104 | ALL AMBIENT LABELS |

## Routing Logic

The system determines labeling requirements based on **first-leg routing** from manufacturing (6122_Storage):

### Frozen Routes
- `6122 → Lineage` (frozen leg to cold storage)
- Any leg with `transport_mode='frozen'` AND `destination.storage_mode=FROZEN`

### Ambient Routes
- `6122 → 6125` (ambient hub)
- `6122 → 6104` (ambient hub)
- `6122 → 6110` (direct to breadroom)
- All other standard routes

### State Tracking

The optimization model tracks product state through the network:
1. **Production:** All batches start AMBIENT at 6122
2. **Frozen Route:** Batch sent to Lineage → Frozen label required
3. **Ambient Route:** Batch sent to hubs → Ambient label required

## Implementation Details

### How It Works

1. **Optimization Solving:** Model determines optimal routing
2. **Shipment Extraction:** Extract all shipments from 6122_Storage
3. **Leg State Lookup:** Check if each leg is frozen or ambient
4. **Aggregation:** Sum quantities by (production_date, product, state)
5. **Report Generation:** Create labeling requirements

### Data Flow

```
Optimization Model
    ↓
shipments_by_leg_product_date
    ↓
Filter: origin == '6122_Storage'
    ↓
Check: leg_arrival_state[leg] == 'frozen'
    ↓
Aggregate by (prod_date, product, state)
    ↓
LabelingRequirement objects
    ↓
Report/CSV/UI
```

## Best Practices

### Factory Integration

1. **Daily Work Orders:** Generate reports each evening for next-day production
2. **Split Batch Protocol:** Train staff to prepare both label types when flagged
3. **Destination Verification:** Cross-reference destinations with shipping schedule
4. **Quality Control:** Verify label type matches first truck destination

### Advance Planning

Run optimization **24-48 hours ahead** to give production team time to:
- Order correct label stock
- Schedule labeling equipment
- Brief packaging team on split batches

### System Integration

```python
# Example: Nightly batch job
from datetime import date, timedelta

def generate_tomorrows_work_orders():
    # Run optimization
    result = model.solve(...)

    # Generate work orders for tomorrow
    tomorrow = date.today() + timedelta(days=1)
    generator = ProductionLabelingReportGenerator(result.solution)
    generator.set_leg_states(model.leg_arrival_state)

    work_orders = generator.generate_daily_work_orders(tomorrow)

    # Send to factory system
    for wo in work_orders:
        if wo.needs_frozen_labels and wo.needs_ambient_labels:
            send_alert("SPLIT BATCH TOMORROW", wo)

        factory_system.schedule_production(wo)

    # Export for production floor
    generator.export_to_excel(f'work_orders_{tomorrow}.xlsx')
```

## Troubleshooting

### "All batches show ambient"

**Cause:** `leg_arrival_state` not provided to generator

**Fix:**
```python
generator.set_leg_states(model.leg_arrival_state)
```

### "Quantities don't match production totals"

**Cause:** Using simplified date mapping (placeholder logic)

**Fix:** Upgrade to cohort-based tracking:
- Enable `use_batch_tracking=True` in optimization
- Extract production dates from `cohort_shipment` variables
- Map shipments to exact production batches

### "No frozen routes found"

**Check:**
1. Network config has frozen transport modes defined
2. Routes to Lineage exist in route definitions
3. Lineage location has `storage_mode=FROZEN`

## Future Enhancements

### Potential Additions

1. **Barcode Generation:** Auto-generate frozen vs. ambient barcodes
2. **Label Printer Integration:** Direct output to label printers
3. **Packaging Material Planning:** Calculate label stock requirements
4. **Historical Analysis:** Track frozen/ambient ratio trends
5. **Batch Splitting Optimization:** Prefer single-label batches when possible

## Support

For questions or issues:
- Check optimization model has `leg_arrival_state` populated
- Verify frozen routes exist in network configuration
- Review shipment extraction logic in `extract_solution()`
- Enable debug logging in `ProductionLabelingReportGenerator`
