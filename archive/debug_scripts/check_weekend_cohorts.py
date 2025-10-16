"""Quick check of weekend cohort inventory at hubs using saved solution."""

import sys
from pathlib import Path

# Check if solution file exists from a recent run
solution_files = list(Path('.').glob('*solution*.pkl'))

if solution_files:
    print(f"Found {len(solution_files)} solution files:")
    for f in solution_files:
        print(f"  {f}")
    print("\nPlease run the optimization from the UI first, then we can analyze the solution.")
else:
    print("No saved solution files found.")
    print("\nTo diagnose this issue:")
    print("1. Run optimization from the Streamlit UI (Planning tab)")
    print("2. Use 2-week horizon for faster results")
    print("3. Then I can analyze the solution data")
    print()
    print("OR run this command to see the cohort inventory structure:")
    print("  venv/bin/python -c \"from src.optimization.integrated_model import IntegratedProductionDistributionModel; help(IntegratedProductionDistributionModel)\"")
