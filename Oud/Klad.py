import pandas as pd
from collections import Counter

# Load the CSV file
df = pd.read_csv("sim_output.csv")  # Replace with your actual file name

# Count item frequencies
freqs = Counter(df['item_code'])

# Filter items with frequency > 1 and sort by frequency descending
filtered_sorted = sorted(
    ((item_code, count) for item_code, count in freqs.items() if count > 1),
    key=lambda x: -x[1]
)

# Print results
print("📊 Items with frequency > 1 (sorted by frequency):")
for item_code, count in filtered_sorted:
    print(f"Item {item_code}: {count} times")
