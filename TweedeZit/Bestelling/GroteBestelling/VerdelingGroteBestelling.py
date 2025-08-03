import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy.stats import nbinom
from scipy import stats
from scipy.optimize import minimize_scalar


def main(method):
    input_folder = Path(__file__).resolve().parents[2] / 'Data' / 'Input'
    bestandspaden = sorted([
        str(p) for p in input_folder.glob('[1-6]_VerdelingItem*.xlsx')
    ])

    # 📊 Gegevens verzamelen
    alle_bestellingen = []
    for pad in bestandspaden:
        df = pd.read_excel(pad, sheet_name="BestellingDensity")
        # Tel hoe vaak elke ordernummer voorkomt = aantal items per bestelling
        order_sizes = df['Outbound order number'].value_counts().values
        alle_bestellingen.extend(order_sizes)

    # 📈 Zet om naar numpy-array voor analyse
    data = np.array(alle_bestellingen)

    # 📉 Bereken gemiddelde en variantie
    gemiddelde = np.mean(data)
    variantie = np.var(data, ddof=1)

    print(f"Gemiddelde aantal items per bestelling: {gemiddelde:.2f}")
    print(f"Variantie: {variantie:.2f}")

    # === Fit Geometric verdeling ===
    # Geometric start bij 1, dus we corrigeren bij simulatie
    p_geom = 1 / gemiddelde  # E[X] = 1/p ⇒ p = 1/μ
    simulated_geom = np.random.geometric(p_geom, size=len(data))

    # === Fit Negative Binomial verdeling ===
    # Formules afgeleid uit E[X] = r(1-p)/p en Var[X] = r(1-p)/p²
    p_nb = gemiddelde / variantie
    r_nb = gemiddelde ** 2 / (variantie - gemiddelde)
    simulated_nb = np.random.negative_binomial(r_nb, p_nb, size=len(data))

    # === Plot alle verdelingen samen ===
    bins = np.arange(1, max(data) + 2)

    plt.figure(figsize=(12, 6))
    plt.hist(data, bins=bins, density=True, alpha=0.6, label='Originele data')
    plt.hist(simulated_geom, bins=bins, density=True, alpha=0.4, label='Geometrisch (geschat)')
    plt.hist(simulated_nb, bins=bins, density=True, alpha=0.4, label='Negatief Binomiaal (geschat)')
    plt.title("Vergelijking: Originele data vs Geometrisch & NB fit")
    plt.xlabel("Aantal items per bestelling")
    plt.ylabel("Genormaliseerde frequentie")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("fit_verdelingen_plot.png", dpi=300)
    plt.show()

    print(f"📌 Geometric p = {p_geom:.4f}")
    print(f"📌 NB r = {r_nb:.2f}, p = {p_nb:.4f}")
    print("Plot opgeslagen als 'fit_verdelingen_plot.png'")

    if method == 1:
        data = data[data < 50]
    elif method == 2:
        threshold = np.percentile(data, 99)
        data = data[data <= threshold]
    else:
        data = data[data < 100]
    return data


def nb_fit_report(data, n_bins=18):
    # === 1. Parameters fitten via moments
    mean = np.mean(data)
    var = np.var(data, ddof=1)
    if var <= mean:
        print("⚠️ Geen geldige NB-fit mogelijk (var ≤ mean).")
        return
    p = mean / var
    r = mean**2 / (var - mean)

    # === 2. Histogram en verwachte waarden
    bins = np.arange(1, max(data)+2)
    counts, _ = np.histogram(data, bins=bins)
    total = len(data)
    pmf_vals = stats.nbinom.pmf(bins[:-1]-1, r, p)  # NB start bij 0 ⇒ shift

    expected_freq = total * pmf_vals

    # === 3. Chi²-test (enkel bins met verwachte freq ≥ 5)
    valid = expected_freq >= 5
    chi2_stat = np.sum((counts[valid] - expected_freq[valid])**2 / expected_freq[valid])
    df = np.sum(valid) - 2  # 2 parameters (r en p)
    chi2_p = 1 - stats.chi2.cdf(chi2_stat, df)

    # === 4. KS-test (discrete cumulatieve versie)
    sorted_data = np.sort(data)
    empirical_cdf = np.arange(1, len(data)+1) / len(data)
    theo_cdf = stats.nbinom.cdf(sorted_data-1, r, p)
    ks_stat = np.max(np.abs(empirical_cdf - theo_cdf))
    ks_p = stats.kstwobign.sf(ks_stat * np.sqrt(len(data)))

    # === 5. Square error op genormaliseerd histogram
    relative_obs = counts / total
    square_error = np.mean((relative_obs - pmf_vals)**2)

    # === 6. Rapport printen
    print("\nDistribution Summary")
    print("Distribution: Negative Binomial")
    print(f"Expression: NB(r={r:.2f}, p={p:.4f})")
    print(f"Square Error: {square_error:.6f}")

    print("\nChi Square Test")
    print(f"Number of intervals = {n_bins}")
    print(f"Degrees of freedom = {df}")
    print(f"Test Statistic = {chi2_stat:.2f}")
    print(f"Corresponding p-value = {chi2_p:.4f}")

    print("\nKolmogorov-Smirnov Test (discrete adjusted)")
    print(f"Test Statistic = {ks_stat:.4f}")
    print(f"Corresponding p-value = {ks_p:.4f}")

    print("\nData Summary")
    print(f"Number of Data Points = {len(data)}")
    print(f"Min Data Value = {np.min(data)}")
    print(f"Max Data Value = {np.max(data)}")
    print(f"Sample Mean = {mean:.2f}")
    print(f"Sample Std Dev = {np.std(data, ddof=1):.2f}")
    return r,p

def gamma_fit_report(data, n_bins=18):
    # === 1. Fit Gamma verdeling
    shape, loc, scale = stats.gamma.fit(data, floc=0)

    # === 2. Histogram en theoretische PDF
    counts, bin_edges = np.histogram(data, bins=n_bins)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    total = len(data)

    # Theoretische verwachtingen per bin
    cdf_vals = stats.gamma.cdf(bin_edges, shape, loc=loc, scale=scale)
    expected_freq = total * np.diff(cdf_vals)

    # === 3. Chi² test

    valid = expected_freq >= 5

    chi2_stat = np.sum((counts[valid] - expected_freq[valid]) ** 2 / expected_freq[valid])
    df = n_bins - 1 - 2  # a, scale geschat, geen loc
    chi2_p = 1 - stats.chi2.cdf(chi2_stat, df)

    # === 4. KS-test
    d_stat, ks_p = stats.kstest(data, 'gamma', args=(shape, loc, scale))

    # === 5. Square error (tussen histogram en model)
    pdf_vals = stats.gamma.pdf(bin_centers, shape, loc=loc, scale=scale)
    square_error = np.mean((counts / total - pdf_vals * np.diff(bin_edges)[0]) ** 2)

    # === 6. Samenvatting printen
    print("\nDistribution Summary")
    print(f"Distribution: Gamma")
    print(f"Expression: GAMM({shape:.2f}, {scale:.3f})")
    print(f"Square Error: {square_error:.6f}")

    print("\nChi Square Test")
    print(f"Number of intervals = {n_bins}")
    print(f"Degrees of freedom = {df}")
    print(f"Test Statistic = {chi2_stat:.1f}")
    print(f"Corresponding p-value = {chi2_p:.4f}")

    print("\nKolmogorov-Smirnov Test")
    print(f"Test Statistic = {d_stat:.4f}")
    print(f"Corresponding p-value = {ks_p:.4f}")

    print("\nData Summary")
    print(f"Number of Data Points = {len(data)}")
    print(f"Min Data Value = {np.min(data):.5f}")
    print(f"Max Data Value = {np.max(data):.2f}")
    print(f"Sample Mean = {np.mean(data):.2f}")
    print(f"Sample Std Dev = {np.std(data, ddof=1):.2f}")


def fit_zinb_and_report(data, n_bins=18):
    data = np.array(data)
    n = len(data)

    # === 1. Data splitsen: 1 versus >1
    ones = data[data == 1]
    rest = data[data > 1]

    # === 2. NB-parameters fitten op data > 1
    mean_rest = np.mean(rest)
    var_rest = np.var(rest, ddof=1)
    p_nb = mean_rest / var_rest
    r_nb = mean_rest**2 / (var_rest - mean_rest)

    # === 3. Optimaliseer pi (kans op 1 buiten NB)
    def zinb_log_likelihood(pi):
        pmf_nb = stats.nbinom.pmf(data - 1, r_nb, p_nb)
        zinb_prob = np.where(data == 1, pi + (1 - pi) * pmf_nb, (1 - pi) * pmf_nb)
        zinb_prob = np.clip(zinb_prob, 1e-10, 1.0)
        return -np.sum(np.log(zinb_prob))

    result = minimize_scalar(zinb_log_likelihood, bounds=(0.01, 0.9), method='bounded')
    pi_opt = result.x

    # === 4. Simuleer ZINB-data
    draws = np.random.rand(n)
    zinb_sim = np.where(draws < pi_opt, 1, stats.nbinom.rvs(r_nb, p_nb, size=n) + 1)

    # === 5. Binning
    bins = np.arange(1, max(data)+2)
    obs_counts, _ = np.histogram(data, bins=bins)
    sim_counts, _ = np.histogram(zinb_sim, bins=bins)
    obs_probs = obs_counts / n
    sim_probs = sim_counts / n
    square_error = np.mean((obs_probs - sim_probs)**2)

    # === 6. Chi² en KS-test
    expected_freq = sim_counts
    valid = expected_freq >= 5
    chi2_stat = np.sum((obs_counts[valid] - expected_freq[valid])**2 / expected_freq[valid])
    df = np.sum(valid) - 3  # r, p, pi
    chi2_p = 1 - stats.chi2.cdf(chi2_stat, df)

    sorted_data = np.sort(data)
    empirical_cdf = np.arange(1, n + 1) / n
    zinb_cdf = pi_opt * (sorted_data == 1).astype(float) + (1 - pi_opt) * stats.nbinom.cdf(sorted_data - 1, r_nb, p_nb)
    ks_stat = np.max(np.abs(empirical_cdf - zinb_cdf))
    ks_p = stats.kstwobign.sf(ks_stat * np.sqrt(n))

    # === 7. Rapport
    print("\nZINB Fit Report")
    print(f"π (kans op exact 1): {pi_opt:.4f}")
    print(f"NB parameters: r = {r_nb:.2f}, p = {p_nb:.4f}")
    print(f"Square Error: {square_error:.6f}")
    print("\nChi Square Test")
    print(f"Degrees of freedom = {df}")
    print(f"Chi² = {chi2_stat:.2f}, p = {chi2_p:.4f}")
    print("\nKolmogorov-Smirnov Test")
    print(f"KS = {ks_stat:.4f}, p = {ks_p:.4f}")
    print(f"\nData points: {n}, min = {np.min(data)}, max = {np.max(data)}, mean = {np.mean(data):.2f}, std = {np.std(data, ddof=1):.2f}")


def get_valid_chi2_bins(data, r, p, min_expected=5):
    """
    Genereert geldige bins voor een Chi²-test op discrete data,
    zodat elke bin minstens 'min_expected' verwachte waarden heeft.
    Bins worden van rechts samengevoegd (staartcompressie).
    """
    data = np.array(data)
    max_val = data.max()
    total = len(data)
    bins = list(range(1, max_val + 2))  # bv. [1, 2, 3, ..., 42] voor max = 41

    # Bereken verwachte frequenties per waarde
    expected_counts = total * nbinom.pmf(np.arange(1, max_val + 1) - 1, r, p)

    valid_bins = []
    current_count = 0
    current_bin_end = bins[-1]

    # We lopen van achter naar voor
    for i in reversed(range(len(expected_counts))):
        current_count += expected_counts[i]
        if current_count >= min_expected:
            valid_bins.insert(0, bins[i + 1])  # voeg rechtergrens van bin toe
            current_count = 0

    # Voeg linkergrens toe
    valid_bins.insert(0, 1)

    return np.array(valid_bins)



def evaluate_negative_binomial_fit(data, r, p, bins=None):
    data = np.array(data)
    n = len(data)

    # Bepaal bins als niet gespecificeerd
    if bins is None:
        bins = np.arange(1, data.max() + 2)

    # Histogrammen
    obs_counts, _ = np.histogram(data, bins=bins)
    bin_centers = 0.5 * (bins[:-1] + bins[1:])

    # Verwachte counts uit NB
    expected_probs = stats.nbinom.pmf(bins[:-1] - 1, r, p)
    expected_counts = expected_probs * n

    # Chi²-test op geldige bins
    valid = expected_counts >= 5
    chi2_stat = np.sum((obs_counts[valid] - expected_counts[valid]) ** 2 / expected_counts[valid])
    chi2_df = np.sum(valid) - 2  # twee parameters: r en p
    chi2_p = 1 - stats.chi2.cdf(chi2_stat, chi2_df)

    # Kolmogorov-Smirnov-test
    sorted_data = np.sort(data)
    empirical_cdf = np.arange(1, n + 1) / n
    theoretical_cdf = stats.nbinom.cdf(sorted_data - 1, r, p)
    ks_stat = np.max(np.abs(empirical_cdf - theoretical_cdf))
    ks_p = stats.kstwobign.sf(ks_stat * np.sqrt(n))

    # Square error tussen genormaliseerde histogrammen
    obs_probs = obs_counts / n
    expected_probs = expected_counts / n
    square_error = np.mean((obs_probs - expected_probs) ** 2)

    # Log-likelihood en AIC/BIC
    log_likelihood = np.sum(stats.nbinom.logpmf(data - 1, r, p))
    k_params = 2
    aic = 2 * k_params - 2 * log_likelihood
    bic = k_params * np.log(n) - 2 * log_likelihood

    # 📋 Rapport
    print("\n📊 Negative Binomial Fit Evaluation")
    print(f"r = {r:.4f}, p = {p:.4f}")
    print(f"Sample size: {n}")
    print(f"\nChi² Test: stat = {chi2_stat:.2f}, df = {chi2_df}, p = {chi2_p:.4f}")
    print(f"KS Test: stat = {ks_stat:.4f}, p = {ks_p:.4f}")
    print(f"Square Error = {square_error:.6f}")
    print(f"Log-Likelihood = {log_likelihood:.2f}")
    print(f"AIC = {aic:.2f}, BIC = {bic:.2f}")

    # 📈 Visualisatie
    plt.figure(figsize=(10, 6))
    plt.hist(data, bins=bins, density=True, alpha=0.6, label='Originele data', edgecolor='black')
    x_vals = np.arange(1, data.max() + 1)
    pmf_vals = stats.nbinom.pmf(x_vals - 1, r, p)
    plt.plot(x_vals, pmf_vals, 'o-', label='NB PMF', color='orange')
    plt.xlabel("Aantal items per bestelling")
    plt.ylabel("Genormaliseerde frequentie")
    plt.title("Negative Binomial vs Originele data")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("nb_fit_vs_data.png", dpi=300)
    plt.show()

    print("Plot opgeslagen als 'nb_fit_vs_data.png'")

    # 📈 Extra plot: discrete puntenvergelijking i.p.v. histogram
    plt.figure(figsize=(10, 6))

    # X-as: unieke itemaantallen
    x_vals = np.arange(1, max(data) + 1)

    # Waargenomen relatieve frequentie (empirische PMF)
    counts = np.bincount(data)[1:]  # [1:] want data start bij 1
    rel_freq = counts / np.sum(counts)
    x_obs = np.arange(1, len(rel_freq) + 1)

    # Theoretische NB PMF
    pmf_vals = stats.nbinom.pmf(x_obs - 1, r, p)

    # Plot beide als puntenlijnen
    plt.plot(x_obs, rel_freq, 'o-', label='Waargenomen frequentie', color='blue')
    plt.plot(x_obs, pmf_vals, 's--', label='NB PMF', color='orange')

    plt.xlabel("Aantal items per bestelling")
    plt.ylabel("Kans / Frequentie")
    plt.title("Vergelijking: Waargenomen vs NB-PMF (geen histogram)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("nb_fit_lineplot.png", dpi=300)
    plt.show()

    print("Extra plot opgeslagen als 'nb_fit_lineplot.png'")


if __name__ == "__main__":
    data = main(2)
    r,b = nb_fit_report(data)
    #gamma_fit_report(data)
    #fit_zinb_and_report(data)
    bins = np.arange(1, max(data) + 2)
    valid_bins = get_valid_chi2_bins(data,r,b,5)
    evaluate_negative_binomial_fit(data,r,b,valid_bins)