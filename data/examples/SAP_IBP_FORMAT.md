# SAP IBP Format Notes

## Gfree Forecast.xlsm

This file is an **SAP Integrated Business Planning (IBP) export** in its native format. It contains real forecast data but requires preprocessing before use with the application parser.

### File Characteristics

- **Source System:** SAP IBP
- **Planning Area:** GFIBPPRD01
- **Template:** DP130 Demand Planning_G610_RET
- **Market Segment:** G610_01_01
- **Unit of Measure:** ZSF (standard units)
- **Currency:** AUD
- **Key Figure:** Approved Forecast
- **Last Refresh:** 2025-Jun-2 09:28:08

### Data Structure

**Sheet:** G610 RET

- **Row 1:** Sheet metadata (title)
- **Row 2:** Attribute-based filters (Market Segment, Product IDs, Location IDs)
- **Row 3:** UoM and Currency information
- **Row 4:** Empty
- **Row 5:** Column headers (Product Desc, Product ID, Location ID, Location, Key Figure, Dates...)
- **Row 6+:** Data rows

**Column Structure:**
- Columns 1-5: Empty (potential merged cell artifacts)
- Column 6: Product Description
- Column 7: Product ID
- Column 8: Location ID
- Column 9: Location Name
- Column 10: Key Figure (always "Approved Forecast" in this file)
- Columns 11+: Daily forecast values (dates in format DD.MM.YYYY)

### Products (5 total)

| Product ID | Description |
|------------|-------------|
| 168846 | HELGAS GFREE TRAD WHITE 470G |
| 168847 | HELGAS GFREE MIXED GRAIN 500G |
| 168848 | HELGAS GFREE WHOLEM 500G |
| 179649 | WONDER GFREE WHITE 470G |
| 179650 | WONDER GFREE WHOLEM 500G |

### Breadroom Locations (9 total)

| Location ID | Location Name | Role | Total Demand |
|-------------|---------------|------|--------------|
| 6103 | QBA-Canberra | Breadroom (via hub 6104) | 115,400 units |
| 6104 | QBA-Moorebank | **Hub + Breadroom** | 432,595 units |
| 6105 | QBA-Rydalmere | Breadroom (via hub 6104) | 301,846 units |
| 6110 | QBA-Burleigh Heads | Breadroom (direct) | 542,121 units |
| 6120 | QBA-Hobart | Breadroom (via hub 6125) | 58,458 units |
| 6123 | QBA-Clayton - Fairbank | Breadroom (via hub 6125) | 339,750 units |
| 6125 | QBA -Keilor Park | **Hub + Breadroom** | 258,739 units |
| 6130 | QBA-Canning Vale | Breadroom (frozen route) | 111,341 units |
| 6134 | QBA-West Richmond SA | Breadroom (via hub 6125) | 247,050 units |

**QBA = Quality Bakers Australia**

**Total Network Demand:** 2,407,299 units (204 days, 5 products)

**Critical Understanding:** Each location has an INDEPENDENT demand forecast:
- 6104 forecast = ONLY Moorebank local market (432,595 units)
- 6104 does NOT include demand for 6105 or 6103
- 6125 forecast = ONLY Keilor Park local market (258,739 units)
- 6125 does NOT include demand for 6123, 6134, or 6120
- Total demand = sum of all 9 independent forecasts

### Forecast Timeframe

- **Start Date:** 02.06.2025 (June 2, 2025)
- **End Date:** 22.12.2025 (December 22, 2025)
- **Duration:** 204 days (~6.7 months)
- **Granularity:** Daily

### Data Rows

The file contains **45 primary data rows** (9 locations × 5 products), with each row representing the daily forecast for a specific product-location combination. Additional rows may contain aggregations or alternate key figures.

## Format Conversion Required

This SAP IBP format differs from the simplified format expected by the application parser. To use this file:

1. **Option A: Manual Preprocessing**
   - Extract forecast data from columns 6-11+
   - Reshape from wide format (dates as columns) to long format (date as a field)
   - Create separate sheets for Locations, Routes, LaborCalendar, TruckSchedules, CostParameters

2. **Option B: Format Converter (Future)**
   - Build a preprocessing script to transform SAP IBP exports
   - Map IBP "Location ID" to application "location_id"
   - Map IBP "Product ID" to application "product_id"
   - Pivot date columns to rows with (location_id, product_id, date, quantity) format

3. **Option C: Parser Extension (Future)**
   - Extend ExcelParser to support SAP IBP format directly
   - Add `parse_sap_ibp()` method
   - Handle embedded filters and metadata

## Expected Application Format

The application parser expects files with these sheets:

1. **Forecast:** Columns `location_id`, `product_id`, `date`, `quantity`, `confidence` (optional)
2. **Locations:** Columns `id`, `name`, `type`, `storage_mode`, ...
3. **Routes:** Columns `id`, `origin_id`, `destination_id`, `transport_mode`, `transit_time_days`, ...
4. **LaborCalendar:** Columns `date`, `fixed_hours`, `regular_rate`, `overtime_rate`, ...
5. **TruckSchedules:** Columns `id`, `truck_name`, `departure_type`, `departure_time`, ...
6. **CostParameters:** Columns `cost_type`, `value`, `unit`

See `forecast_template_structure.md` for complete format specification.

## Notes for Integration Testing

When creating test data based on this file:

- Use the 9 breadroom locations as destinations
- Manufacturing site ID is 6122 (per project spec)
- Need to define routes from 6122 to each of the 9 breadrooms
- Need to define labor calendar for the date range
- Need to define truck schedules (morning/afternoon)
- Forecast quantities are in units (loaves of bread)
