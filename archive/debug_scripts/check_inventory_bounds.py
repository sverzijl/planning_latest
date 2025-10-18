import pandas as pd
import sys

# Read inventory file
try:
    df = pd.read_excel('data/examples/inventory_latest.XLSX')
    
    # SAP format - 'Unrestricted' is likely the quantity column
    print("Inventory file format: SAP-style")
    print("Columns:", df.columns.tolist())
    
    # Check Unrestricted column
    if 'Unrestricted' in df.columns:
        print("\n" + "="*60)
        print("INVENTORY QUANTITY ANALYSIS")
        print("="*60)
        
        max_qty = df['Unrestricted'].max()
        print(f"\nMax individual quantity: {max_qty:,.0f} units")
        print(f"Max daily production capacity: 19,600 units")
        print(f"❌ Exceeds bound? {max_qty > 19_600}")
        
        # Check for cohorts by Plant (location) and Material (product)
        if 'Plant' in df.columns and 'Material' in df.columns:
            grouped = df.groupby(['Plant', 'Material'])['Unrestricted'].sum()
            max_cohort = grouped.max()
            print(f"\nMax cohort quantity (by Plant/Material): {max_cohort:,.0f} units")
            print(f"❌ Exceeds bound? {max_cohort > 19_600}")
            
            # Show problematic cohorts
            problem_cohorts = grouped[grouped > 19_600]
            if len(problem_cohorts) > 0:
                print(f"\n🔴 CONFIRMED: Found {len(problem_cohorts)} cohorts exceeding 19,600 units")
                print("\nTop problematic cohorts:")
                for (plant, material), qty in problem_cohorts.sort_values(ascending=False).head(10).items():
                    pallets_needed = int(qty / 320) + 1
                    print(f"  Plant {plant}, Material {material}: {qty:,.0f} units ({pallets_needed} pallets)")
                
                # Calculate required bounds
                max_pallets_needed = int(max_cohort / 320) + 1
                print(f"\n📦 REQUIRED FIXES:")
                print(f"  - Max pallets needed: {max_pallets_needed} (current bound: 62)")
                print(f"  - Max units needed: {max_cohort:,.0f} (current bound: 19,600)")
                print(f"\n✅ HYPOTHESIS CONFIRMED: Bound-tightening bug causes infeasibility")
            else:
                print("\n✅ No cohorts exceed bound - hypothesis NOT confirmed")
    else:
        print("\nNo 'Unrestricted' column found")
        
except Exception as e:
    print(f"Error reading inventory file: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
