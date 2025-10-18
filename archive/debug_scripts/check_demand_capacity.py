import pandas as pd
from datetime import datetime, timedelta

# Read forecast file
forecast_file = 'data/examples/Gfree Forecast.xlsm'
try:
    df = pd.read_excel(forecast_file, sheet_name='Forecast')
    print("Forecast file columns:", df.columns.tolist())
    print("\nFirst few rows:")
    print(df.head())
    
    # Parse forecast data
    if 'Date' in df.columns and 'Quantity' in df.columns:
        # Filter to 4-week horizon from latest date
        df['Date'] = pd.to_datetime(df['Date'])
        start_date = df['Date'].min()
        end_date = start_date + timedelta(days=28)
        
        df_period = df[(df['Date'] >= start_date) & (df['Date'] <= end_date)]
        
        print(f"\n{'='*60}")
        print(f"DEMAND ANALYSIS (4-week period)")
        print(f"{'='*60}")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"Total demand: {df_period['Quantity'].sum():,.0f} units")
        print(f"Daily average: {df_period.groupby('Date')['Quantity'].sum().mean():,.0f} units/day")
        print(f"Max daily demand: {df_period.groupby('Date')['Quantity'].sum().max():,.0f} units/day")
        
        # Check production capacity
        max_daily_production = 19600
        total_production_capacity_4weeks = max_daily_production * 28
        print(f"\n{'='*60}")
        print(f"CAPACITY ANALYSIS")
        print(f"{'='*60}")
        print(f"Max daily production: {max_daily_production:,.0f} units/day")
        print(f"Total production capacity (28 days): {total_production_capacity_4weeks:,.0f} units")
        print(f"Demand vs capacity: {(df_period['Quantity'].sum() / total_production_capacity_4weeks * 100):.1f}%")
        
        if df_period['Quantity'].sum() > total_production_capacity_4weeks:
            print(f"\n🔴 INFEASIBILITY: Demand exceeds production capacity!")
            print(f"  Shortage: {df_period['Quantity'].sum() - total_production_capacity_4weeks:,.0f} units")
        
        # Check truck capacity
        trucks_per_week = 11  # From CLAUDE.md
        truck_capacity = 14080
        total_truck_capacity_4weeks = trucks_per_week * 4 * truck_capacity
        print(f"\nTruck capacity (11 trucks/week × 4 weeks): {total_truck_capacity_4weeks:,.0f} units")
        print(f"Demand vs truck capacity: {(df_period['Quantity'].sum() / total_truck_capacity_4weeks * 100):.1f}%")
        
        if df_period['Quantity'].sum() > total_truck_capacity_4weeks:
            print(f"\n🔴 POTENTIAL ISSUE: Demand exceeds truck capacity!")
            print(f"  Shortage: {df_period['Quantity'].sum() - total_truck_capacity_4weeks:,.0f} units")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
