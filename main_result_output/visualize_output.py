import os
import json
import numpy as np
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from collections import Counter

def load_rounded_half_second_durations(filepath, time_key):
    durations = []
    with open(filepath, "r") as f:
        for line in f:
            data = json.loads(line)
            duration = data[time_key]
            rounded = round(duration * 2) / 2  # nearest 0.5 seconds
            durations.append(rounded)
    return durations

def plot_histogram(durations, title, xlabel):
    counts = Counter(durations)
    bins = sorted(counts.keys())
    heights = [counts[b] for b in bins]

    plt.rcParams['axes.titlesize'] = 21
    plt.rcParams['axes.labelsize'] = 19
    plt.rcParams['xtick.labelsize'] = 15  # Lettergrootte van x-as tick labels
    plt.rcParams['ytick.labelsize'] = 15  # Lettergrootte van y-as tick labels

    plt.figure(figsize=(10, 5))
    plt.bar(bins, heights, width=0.5, align='center')
    plt.xlabel(xlabel)
    plt.ylabel("Frequentie")
    plt.title(title)
    plt.grid(axis='y')

    # Set axis limits
    plt.xlim(0, 140)
    plt.ylim(0, 13000)   # 5800   50000

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    folder = "base_vul_strategie_2"

    # Handling time plot
    handling_durations = load_rounded_half_second_durations(
        os.path.join(folder, "handling_times.jsonl"), "handling_time"
    )
    plot_histogram(handling_durations, f"Verwerkingstijden items - Sequentiële plaatsing", "Verwerkingstijd (s)")

    # Picking time plot
    # picking_durations = load_rounded_half_second_durations(
    #     os.path.join(folder, "picking_times.jsonl"), "picking_time"
    # )
    # plot_histogram(picking_durations, "Picking Time Distribution", "Picking Time (s)")
