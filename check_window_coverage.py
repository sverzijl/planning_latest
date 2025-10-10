"""Check if windows cover all dates in committed regions."""

from datetime import date, timedelta

# Window configuration
start_date = date(2025, 6, 2)
end_date = date(2025, 12, 22)
window_size = 7
overlap = 3
committed_size = window_size - overlap  # 4 days

# Calculate windows
current = start_date
window_num = 0
all_committed_dates = set()

print("Window Coverage Analysis:")
print("=" * 80)

while current <= end_date:
    window_num += 1
    window_end = min(current + timedelta(days=window_size - 1), end_date)
    
    # Calculate committed region
    is_last = window_end >= end_date
    if not is_last:
        committed_end = window_end - timedelta(days=overlap)
    else:
        committed_end = window_end
    
    # Add committed dates
    committed_dates = []
    d = current
    while d <= committed_end:
        committed_dates.append(d)
        all_committed_dates.add(d)
        d += timedelta(days=1)
    
    print(f"Window {window_num}: {current} to {window_end} (committed: {current} to {committed_end}, {len(committed_dates)} days)")
    
    # Move to next window
    current = current + timedelta(days=committed_size)

print(f"\n" + "=" * 80)
print(f"Total committed dates: {len(all_committed_dates)}")

# Check for gaps
all_forecast_dates = set()
d = start_date
while d <= end_date:
    all_forecast_dates.add(d)
    d += timedelta(days=1)

print(f"Total forecast dates: {len(all_forecast_dates)}")

missing_dates = all_forecast_dates - all_committed_dates
if missing_dates:
    print(f"\n❌ MISSING DATES IN COMMITTED REGIONS: {sorted(missing_dates)}")
else:
    print(f"\n✅ All forecast dates are covered by committed regions")
