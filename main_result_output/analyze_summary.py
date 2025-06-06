import json
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt

summary_path = "base_big_trays/summary.jsonl"  # change path if needed

# Load data
summaries = []
with open(summary_path, "r") as f:
    for line in f:
        summaries.append(json.loads(line))

# Sanity check
if not summaries:
    raise ValueError("No data found in summary.jsonl")

# Extract values
handling_times = [entry["average_handling_time"] for entry in summaries]
picking_times = [entry["average_picking_time"] for entry in summaries]
throughputs = [entry["throughput_items_per_hour"] for entry in summaries]
run_indices = [entry.get("run_index", i) for i, entry in enumerate(summaries)]

# Compute totals/averages
avg_handling = sum(handling_times) / len(handling_times)
avg_picking = sum(picking_times) / len(picking_times)
avg_throughput = 3600 / avg_handling

print(f"📊 Total average handling time: {avg_handling:.2f} sec")
print(f"📊 Total average picking time: {avg_picking:.2f} sec")
print(f"📊 Average throughput: {avg_throughput:.2f} items/hour")

# Plot 1: average handling time per run
plt.figure(figsize=(10, 5))
plt.plot(run_indices, handling_times, marker='o')
plt.xlabel("Run index")
plt.ylabel("Average Handling Time (s)")
plt.title("Average Handling Time per Run")
plt.grid(True)
plt.tight_layout()
plt.show()

# Plot 2: throughput per run
plt.figure(figsize=(10, 5))
plt.plot(run_indices, throughputs, marker='o', color='green')
plt.xlabel("Run index")
plt.ylabel("Throughput (items/hour)")
plt.title("Throughput per Run")
plt.grid(True)
plt.tight_layout()
plt.show()
