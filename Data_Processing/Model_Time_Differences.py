import os
import pickle
import numpy as np
import matplotlib.pyplot as plt
from fitter import Fitter
import scipy.stats as stats

def fit_best_distribution(data, output_path):
    # Filter: remove values < 2
    data = np.array(data, dtype=np.float64)
    data = data[data >= 2]

    if len(data) == 0:
        print("❌ No valid data.")
        return

    print(f"✅ Fitting {len(data)} data points...")

    # Fit many distributions
    f = Fitter(
        data,
        distributions=[
            'gamma', 'lognorm', 'beta', 'weibull_min', 'weibull_max',
            'norm', 'expon', 'uniform', 'triang', 'pareto'
        ],
        timeout=30
    )
    f.fit()

    # Get best distribution and params
    best = f.get_best()
    dist_name = list(best.keys())[0]
    params = f.fitted_param[dist_name]  # these are proper floats

    print(f"\n✅ Best fit: {dist_name} with params: {params}")

    # Plot histogram and best fit
    plt.figure(figsize=(10, 6))
    bins = np.arange(0, 52) - 0.5  # 1-second bins from 0–51
    counts, _, _ = plt.hist(data, bins=bins, edgecolor='black', color='skyblue',
                            density=False, label='Observed data')

    # Plot PDF scaled to match histogram frequency
    x_vals = np.linspace(0, 50, 500)
    bin_width = 1
    dist = getattr(stats, dist_name)
    pdf_vals = dist.pdf(x_vals, *[float(p) for p in params])
    pdf_scaled = pdf_vals * len(data) * bin_width
    plt.plot(x_vals, pdf_scaled, 'r-', lw=2, label=f'{dist_name} fit')

    plt.title(f"Best Fit Distribution: {dist_name}")
    plt.xlabel("Time difference (seconds)")
    plt.ylabel("Number of occurrences")
    plt.xlim(0, 50)
    plt.ylim(0, 1000)
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

    print(f"✅ Plot saved to: {output_path}")

def main():
    input_pkl = '../Data/Output/time_differences.pkl'
    output_plot = '../Data/Output/Plots/OSR_best_fit.png'

    with open(input_pkl, 'rb') as f:
        data = pickle.load(f)

    if 'OSR' in data:
        fit_best_distribution(data['OSR'], output_plot)
    else:
        print("❌ 'OSR' not found in the pickle file.")

if __name__ == "__main__":
    main()