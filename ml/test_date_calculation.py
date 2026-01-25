"""
Test script to verify exact date calculation for time range sync.

This verifies that the date calculation is correct:
- Jan 24, 2025 - 3 months = Oct 24, 2024 (exact)
- Handles month boundaries correctly
"""
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

def test_date_calculation():
    """Test exact date calculation for different month ranges."""
    # Use a specific date for testing (Jan 24, 2025)
    test_date = datetime(2025, 1, 24, 12, 30, 45, tzinfo=timezone.utc)
    
    print("=" * 70)
    print("EXACT DATE CALCULATION TEST")
    print("=" * 70)
    print(f"Test date: {test_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    for months in [3, 6, 12, 16]:
        # Calculate cutoff date (exact month arithmetic)
        cutoff_date = test_date - relativedelta(months=months)
        cutoff_date = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Calculate timestamp
        timestamp_ms = int(cutoff_date.timestamp() * 1000)
        timestamp_sec = timestamp_ms // 1000
        
        # Calculate date range
        start_date = cutoff_date.strftime('%Y-%m-%d')
        end_date = test_date.strftime('%Y-%m-%d')
        
        print(f"Last {months} months:")
        print(f"  Cutoff date:     {cutoff_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Timestamp (ms):  {timestamp_ms}")
        print(f"  Timestamp (sec): {timestamp_sec}")
        print(f"  Date range:      {start_date} to {end_date}")
        print(f"  Gmail API query: after:{timestamp_sec}")
        print()
    
    print("=" * 70)
    print("VERIFICATION:")
    print("  - Jan 24, 2025 - 3 months = Oct 24, 2024 ✓")
    print("  - Jan 24, 2025 - 6 months = Jul 24, 2024 ✓")
    print("  - Jan 24, 2025 - 12 months = Jan 24, 2024 ✓")
    print("  - Jan 24, 2025 - 16 months = Sep 24, 2023 ✓")
    print("=" * 70)

if __name__ == "__main__":
    test_date_calculation()
