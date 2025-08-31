import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy.stats import nbinom
from scipy import stats, optimize
from scipy.optimize import minimize_scalar, minimize


# =========================
# Helpers
# =========================

def _nb_params_from_moments(mean, var):
    """
    NB-parameterisatie: X in {1,2,...}, k = X-1 ~ NB(r, p) met E[k] = r(1-p)/p, Var[k] = r(1-p)/p^2.
    Voor X geldt E[X] = 1 + r(1-p)/p en Var[X] = r(1-p)/p^2.
    We fitten op X en schuiven intern naar k = X-1.
    """
    if var <= mean:
        raise ValueError("NB-fit onhaalbaar: variantie ≤ gemiddelde (geen overdispersie).")
    p = mean / var
    r = mean**2 / (var - mean)
    if not (0 < p < 1) or r <= 0:
        raise ValueError("NB-parameters ongeldig: controleer data en momentfit.")
    return r, p


def _expected_counts_nb_bins(n, r, p, bins):
    """
    Theoretische expected counts per samengevouwen bin (discrete):
    bins: array van grenzen in X-ruimte (bv. [1, 3, 6, 9, ...]), integers.
    Voor elke bin [a, b) sommen we PMF(X=x) voor x = a..b-1.
    NB is gedefinieerd op k = x-1 ≥ 0: pmf_k = NB(k; r, p) => pmf_x = NB(x-1; r, p).
    """
    exp_counts = np.zeros(len(bins) - 1, dtype=float)
    for i in range(len(bins) - 1):
        a, b = int(bins[i]), int(bins[i+1])  # [a, b)
        if b <= a:
            continue
        ks = np.arange(a - 1, b - 1)  # k = x-1
        exp_counts[i] = n * np.sum(stats.nbinom.pmf(ks, r, p))
    return exp_counts


def _expected_counts_zinb_bins(n, r, p, pi, bins, x_max=None):
    """
    Expected counts voor ZINB met inflatie op X=1.
    pmf_ZINB(X=1) = pi + (1-pi)*NB(k=0); pmf_ZINB(X=x>1) = (1-pi)*NB(k=x-1).
    """
    if x_max is None:
        x_max = int(bins[-1] - 1)
    # bouw volledige pmf over x=1..x_max
    x_vals = np.arange(1, x_max + 1)
    mix_pmf = np.zeros_like(x_vals, dtype=float)
    # x=1 (k=0)
    mix_pmf[0] = pi + (1 - pi) * stats.nbinom.pmf(0, r, p)
    # x>=2
    if len(x_vals) > 1:
        mix_pmf[1:] = (1 - pi) * stats.nbinom.pmf(x_vals[1:] - 1, r, p)

    # sommeer per bin
    exp_counts = np.zeros(len(bins) - 1, dtype=float)
    for i in range(len(bins) - 1):
        a, b = int(bins[i]), int(bins[i+1])  # [a,b)
        if b <= a:
            continue
        exp_counts[i] = n * np.sum(mix_pmf[(x_vals >= a) & (x_vals < b)])
    return exp_counts


def get_valid_chi2_bins(data, r, p, min_expected=5):
    """
    Genereert samengevoegde bins (in X) zodat elke bin minstens 'min_expected'
    verwachte waarden heeft o.b.v. de NB(r,p).
    We voegen van rechts (staart) samen. Grenzen zijn integer X-waarden.
    """
    data = np.array(data, dtype=int)
    max_val = int(data.max())
    n = len(data)
    # begin met enkelvoudige integer-bins [1,2,3,...,max+1]
    bins = list(range(1, max_val + 2))

    # expected per afzonderlijke X-waarde
    single_exp = n * stats.nbinom.pmf(np.arange(0, max_val), r, p)  # k=0..max-1 ↔ x=1..max

    valid_bins = []
    acc = 0.0
    # loop van rechts naar links over enkelvoudige waarden
    for i in reversed(range(len(single_exp))):  # i ↔ x = i+1
        acc += single_exp[i]
        if acc >= min_expected:
            # we sluiten bin af op rechtergrens x+1
            valid_bins.insert(0, bins[i + 1])
            acc = 0.0
    # linkergrens
    valid_bins.insert(0, 1)
    return np.array(valid_bins, dtype=int)


# =========================
# Datalezer + eerste vergelijking
# =========================

def NBVerdeling(method):
    input_folder = Path(__file__).resolve().parents[2] / 'Data' / 'Input'
    bestandspaden = sorted([str(p) for p in input_folder.glob('[1-6]_VerdelingItem*.xlsx')])

    alle_bestellingen = []
    for pad in bestandspaden:
        df = pd.read_excel(pad, sheet_name="BestellingDensity")
        order_sizes = df['Outbound order number'].value_counts().values
        alle_bestellingen.extend(order_sizes)

    data = np.array(alle_bestellingen, dtype=int)

    gemiddelde = np.mean(data)
    variantie = np.var(data, ddof=1)
    print(f"Gemiddelde aantal items per bestelling: {gemiddelde:.2f}")
    print(f"Variantie: {variantie:.2f}")

    # Geometric fit (X>=1): p = 1/μ
    p_geom = 1.0 / gemiddelde
    simulated_geom = np.random.geometric(p_geom, size=len(data))

    # NB via momenten
    try:
        r_nb, p_nb = _nb_params_from_moments(gemiddelde, variantie)
        simulated_nb = np.random.negative_binomial(r_nb, p_nb, size=len(data))
    except ValueError as e:
        print(f"⚠️ {e}")
        simulated_nb = None
        r_nb = p_nb = np.nan

    # Plot
    bins_plot = np.arange(1, int(data.max()) + 2)
    plt.figure(figsize=(12, 6))
    plt.hist(data, bins=bins_plot, density=True, alpha=0.6, label='Originele data')
    plt.hist(simulated_geom, bins=bins_plot, density=True, alpha=0.4, label='Geometrisch (geschat)')
    if simulated_nb is not None:
        plt.hist(simulated_nb, bins=bins_plot, density=True, alpha=0.4, label='Negatief Binomiaal (geschat)')
    plt.title("Vergelijking: Originele data vs Geometrisch & NB fit")
    plt.xlabel("Aantal items per bestelling")
    plt.ylabel("Genormaliseerde frequentie")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("fit_verdelingen_plot.png", dpi=300)
    plt.show()

    print(f"📌 Geometric p = {p_geom:.4f}")
    if simulated_nb is not None:
        print(f"📌 NB r = {r_nb:.2f}, p = {p_nb:.4f}")
    print("Plot opgeslagen als 'fit_verdelingen_plot.png'")

    # Outlier-trim
    if method == 1:
        data = data[data < 50]
    elif method == 2:
        threshold = np.percentile(data, 99)
        data = data[data <= threshold]
    else:
        data = data[data < 100]
    return data


# =========================
# Rapporten
# =========================

def nb_fit_report(data, n_bins=18):
    data = np.array(data, dtype=int)
    mean = np.mean(data)
    var = np.var(data, ddof=1)
    try:
        r, p = _nb_params_from_moments(mean, var)
    except ValueError as e:
        print(f"⚠️ {e}")
        return np.nan, np.nan

    # Gebruik samengevoegde bins met min_expected=5
    bins = get_valid_chi2_bins(data, r, p, min_expected=5)
    obs_counts, _ = np.histogram(data, bins=bins)
    expected_counts = _expected_counts_nb_bins(len(data), r, p, bins)

    # Chi²-test
    valid = expected_counts >= 5
    chi2_stat = np.sum((obs_counts[valid] - expected_counts[valid]) ** 2 / expected_counts[valid])
    df = np.sum(valid) - 1 - 2  # -1 voor som-constraint, -2 voor r en p
    chi2_p = 1 - stats.chi2.cdf(chi2_stat, max(df, 1))

    # KS-test (discrete CDF, conservatieve p-waarde)
    sorted_data = np.sort(data)
    emp_cdf = np.arange(1, len(data) + 1) / len(data)
    theo_cdf = stats.nbinom.cdf(sorted_data - 1, r, p)
    ks_stat = np.max(np.abs(emp_cdf - theo_cdf))
    ks_p = stats.kstwobign.sf(ks_stat * np.sqrt(len(data)))

    # SSE op empirische PMF (op integer-waarden)
    x_vals = np.arange(1, data.max() + 1)
    counts_all = np.bincount(data, minlength=data.max() + 1)[1:]
    rel_obs = counts_all / counts_all.sum()
    pmf_vals = stats.nbinom.pmf(x_vals - 1, r, p)
    square_error = np.mean((rel_obs - pmf_vals) ** 2)

    print("\nDistribution Summary")
    print("Distribution: Negative Binomial")
    print(f"Expression: NB(r={r:.2f}, p={p:.4f})")
    print(f"Square Error: {square_error:.6f}")

    print("\nChi Square Test")
    print(f"Number of intervals (valid) = {np.sum(valid)}")
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
    return r, p


def gamma_fit_report(data, n_bins=18):
    data = np.array(data, dtype=float)
    shape, loc, scale = stats.gamma.fit(data, floc=0)

    counts, bin_edges = np.histogram(data, bins=n_bins)
    total = len(data)

    cdf_vals = stats.gamma.cdf(bin_edges, shape, loc=loc, scale=scale)
    expected_freq = total * np.diff(cdf_vals)

    valid = expected_freq >= 5
    chi2_stat = np.sum((counts[valid] - expected_freq[valid]) ** 2 / expected_freq[valid])
    df = np.sum(valid) - 1 - 2  # -1 som-constraint, -2 (shape & scale)
    chi2_p = 1 - stats.chi2.cdf(chi2_stat, max(df, 1))

    d_stat, ks_p = stats.kstest(data, 'gamma', args=(shape, loc, scale))

    # Square error tov genormaliseerd histogram
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    pdf_vals = stats.gamma.pdf(bin_centers, shape, loc=loc, scale=scale)
    square_error = np.mean((counts / total - pdf_vals * np.diff(bin_edges)[0]) ** 2)

    print("\nDistribution Summary")
    print(f"Distribution: Gamma")
    print(f"Expression: GAMM({shape:.2f}, {scale:.3f})")
    print(f"Square Error: {square_error:.6f}")

    print("\nChi Square Test")
    print(f"Number of intervals (valid) = {np.sum(valid)}")
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
    data = np.array(data, dtype=int)
    n = len(data)

    # NB fit op gehele data (zonder simulatie); robuust
    mean = np.mean(data)
    var = np.var(data, ddof=1)
    r_nb, p_nb = _nb_params_from_moments(mean, var)

    # π optimaliseren op (0,1) met clipping
    def zinb_neg_loglik(pi):
        # pmf NB op k = x-1
        pmf_nb = stats.nbinom.pmf(data - 1, r_nb, p_nb)
        # ZINB pmf
        zinb_p = np.where(
            data == 1,
            pi + (1 - pi) * stats.nbinom.pmf(0, r_nb, p_nb),
            (1 - pi) * pmf_nb
        )
        zinb_p = np.clip(zinb_p, 1e-12, 1.0)
        return -np.sum(np.log(zinb_p))

    result = minimize_scalar(zinb_neg_loglik, bounds=(0.0, 1.0), method='bounded')
    pi_opt = float(np.clip(result.x, 1e-9, 1 - 1e-9))

    # Bins op basis van ZINB-expected (we gebruiken NB-binning als proxy)
    bins = get_valid_chi2_bins(data, r_nb, p_nb, min_expected=5)
    obs_counts, _ = np.histogram(data, bins=bins)
    expected_counts = _expected_counts_zinb_bins(n, r_nb, p_nb, pi_opt, bins)

    # Chi²
    valid = expected_counts >= 5
    chi2_stat = np.sum((obs_counts[valid] - expected_counts[valid]) ** 2 / expected_counts[valid])
    df = np.sum(valid) - 1 - 3  # -1 som-constraint, -3 (r,p,pi)
    chi2_p = 1 - stats.chi2.cdf(chi2_stat, max(df, 1))

    # KS met juiste ZINB-CDF: F_ZINB(x) = pi + (1-pi)*F_NB(x-1) voor alle x≥1
    sorted_data = np.sort(data)
    emp_cdf = np.arange(1, n + 1) / n
    nb_cdf = stats.nbinom.cdf(sorted_data - 1, r_nb, p_nb)
    zinb_cdf = pi_opt + (1 - pi_opt) * nb_cdf
    ks_stat = np.max(np.abs(emp_cdf - zinb_cdf))
    ks_p = stats.kstwobign.sf(ks_stat * np.sqrt(n))

    # Square error (empirische PMF vs ZINB-PMF)
    x_vals = np.arange(1, data.max() + 1)
    counts_all = np.bincount(data, minlength=data.max() + 1)[1:]
    rel_obs = counts_all / counts_all.sum()
    mix_pmf = np.zeros_like(x_vals, dtype=float)
    mix_pmf[0] = pi_opt + (1 - pi_opt) * stats.nbinom.pmf(0, r_nb, p_nb)
    if len(x_vals) > 1:
        mix_pmf[1:] = (1 - pi_opt) * stats.nbinom.pmf(x_vals[1:] - 1, r_nb, p_nb)
    square_error = np.mean((rel_obs - mix_pmf) ** 2)

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


def evaluate_negative_binomial_fit(data, r, p, bins=None):
    data = np.array(data, dtype=int)
    n = len(data)

    # Bepaal bins indien niet opgegeven
    if bins is None:
        bins = get_valid_chi2_bins(data, r, p, min_expected=5)

    # Observaties per bin
    obs_counts, _ = np.histogram(data, bins=bins)

    # Theoretische expected per bin (samengevoegd)
    expected_counts = _expected_counts_nb_bins(n, r, p, bins)

    # Chi²-test op geldige bins
    valid = expected_counts >= 5
    chi2_stat = np.sum((obs_counts[valid] - expected_counts[valid]) ** 2 / expected_counts[valid])
    chi2_df = np.sum(valid) - 1 - 2  # -1 som-constraint, -2 parameters
    chi2_p = 1 - stats.chi2.cdf(chi2_stat, max(chi2_df, 1))

    # KS-test (discrete)
    sorted_data = np.sort(data)
    empirical_cdf = np.arange(1, n + 1) / n
    theoretical_cdf = stats.nbinom.cdf(sorted_data - 1, r, p)
    ks_stat = np.max(np.abs(empirical_cdf - theoretical_cdf))
    ks_p = stats.kstwobign.sf(ks_stat * np.sqrt(n))

    # Square error tussen empirische en theoretische PMF (op integers)
    x_vals = np.arange(1, data.max() + 1)
    counts_all = np.bincount(data, minlength=data.max() + 1)[1:]
    obs_probs = counts_all / counts_all.sum()
    pmf_vals = stats.nbinom.pmf(x_vals - 1, r, p)
    square_error = np.mean((obs_probs - pmf_vals) ** 2)

    # Log-likelihood en AIC/BIC (op individuele X)
    log_likelihood = np.sum(stats.nbinom.logpmf(data - 1, r, p))
    k_params = 2
    aic = 2 * k_params - 2 * log_likelihood
    bic = k_params * np.log(n) - 2 * log_likelihood

    print("\n📊 Negative Binomial Fit Evaluation")
    print(f"r = {r:.4f}, p = {p:.4f}")
    print(f"Sample size: {n}")
    print(f"\nChi² Test: stat = {chi2_stat:.2f}, df = {chi2_df}, p = {chi2_p:.4f}")
    print(f"KS Test: stat = {ks_stat:.4f}, p = {ks_p:.4f}")
    print(f"Square Error = {square_error:.6f}")
    print(f"Log-Likelihood = {log_likelihood:.2f}")
    print(f"AIC = {aic:.2f}, BIC = {bic:.2f}")

    # Visualisatie: histogram + NB-PMF
    plt.figure(figsize=(10, 6))
    plt.hist(data, bins=np.arange(1, data.max() + 2), density=True, alpha=0.6, label='Originele data', edgecolor='black')
    x_plot = np.arange(1, data.max() + 1)
    pmf_plot = stats.nbinom.pmf(x_plot - 1, r, p)
    plt.plot(x_plot, pmf_plot, 'o-', label='NB PMF')
    plt.xlabel("Aantal items per bestelling")
    plt.ylabel("Genormaliseerde frequentie")
    plt.title("Negative Binomial vs Originele data")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("nb_fit_vs_data.png", dpi=300)
    plt.show()
    print("Plot opgeslagen als 'nb_fit_vs_data.png'")

    # Extra: puntenvergelijking (empirische PMF vs NB-PMF)
    plt.figure(figsize=(10, 6))
    plt.plot(x_vals, obs_probs, 'o-', label='Waargenomen frequentie')
    plt.plot(x_vals, pmf_vals, 's--', label='NB PMF')
    plt.xlabel("Aantal items per bestelling")
    plt.ylabel("Kans / Frequentie")
    plt.title("Vergelijking: Waargenomen vs NB-PMF (geen histogram)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("nb_fit_lineplot.png", dpi=300)
    plt.show()
    print("Extra plot opgeslagen als 'nb_fit_lineplot.png'")

# ---------- 1) NB MLE-fit (op X>=1, met k=X-1) ----------
def fit_nb_mle(data):
    data = np.asarray(data, dtype=int)
    k = data - 1  # NB op k>=0

    # reparam: r = exp(a) > 0, p = sigmoid(b) in (0,1)
    def nll(theta):
        a, b = theta
        r = np.exp(a)
        p = 1.0 / (1.0 + np.exp(-b))
        # neg log-likelihood
        ll = stats.nbinom.logpmf(k, r, p)
        return -np.sum(ll)

    # startwaarden uit moments als die geldig zijn, anders grove starts
    m, v = data.mean(), data.var(ddof=1)
    if v > m:
        p0 = m / v
        r0 = m**2 / (v - m)
        a0 = np.log(max(r0, 1e-3))
        b0 = np.log(p0/(1-p0))
    else:
        a0, b0 = np.log(1.0), 0.0

    res = optimize.minimize(nll, x0=np.array([a0, b0]), method="L-BFGS-B")
    a_hat, b_hat = res.x
    r_hat = float(np.exp(a_hat))
    p_hat = float(1.0 / (1.0 + np.exp(-b_hat)))
    return r_hat, p_hat, res

def plot_nb_vs_data(data, r, p, title="NB (MLE) vs data"):
    data = np.asarray(data, dtype=int)
    plt.figure(figsize=(10,6))
    plt.hist(data, bins=np.arange(1, data.max()+2), density=True, alpha=0.6, label="Originele data", edgecolor='black')
    x = np.arange(1, data.max()+1)
    pmf = stats.nbinom.pmf(x-1, r, p)
    plt.plot(x, pmf, 'o-', label=f'NB PMF (r={r:.2f}, p={p:.3f})')
    plt.xlabel("Aantal items per bestelling")
    plt.ylabel("Genormaliseerde frequentie")
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

# ---------- 2) Hurdle (one-inflated) NB ----------
def fit_hurdle_one(data):
    """
    Hurdle op x=1: P(X=1)=pi, P(X=x>1)=(1-pi)*NB(k=x-1 | k>=1) met conditionering.
    NB: we gebruiken NB op k (k>=0), maar voor x>1 geldt k>=1.
    """
    data = np.asarray(data, dtype=int)
    n = len(data)
    ones = np.sum(data == 1)
    rest = data[data > 1]
    if len(rest) == 0:
        raise ValueError("Alle data zijn 1: hurdle niet zinvol.")
    # eerste schatting pi
    pi0 = ones / n

    # fit NB (MLE) op k = x-1, maar alleen k>=1
    k_rest = rest - 1

    def nll_nb_rest(theta):
        a, b = theta
        r = np.exp(a)
        p = 1.0 / (1.0 + np.exp(-b))
        # Likelihood op k>=1 geconditioneerd: pmf(k)/P(k>=1)
        pmf_k = stats.nbinom.pmf(k_rest, r, p)
        tail = 1.0 - stats.nbinom.cdf(0, r, p)  # P(k>=1)
        pmf_cond = pmf_k / np.clip(tail, 1e-12, 1.0)
        return -np.sum(np.log(np.clip(pmf_cond, 1e-12, 1.0)))

    # starts uit NB MLE op volledige data:
    r_ini, p_ini, _ = fit_nb_mle(data)
    a0, b0 = np.log(r_ini), np.log(p_ini/(1-p_ini))
    res_nb = optimize.minimize(nll_nb_rest, x0=np.array([a0, b0]), method="L-BFGS-B")
    a_hat, b_hat = res_nb.x
    r_hat = float(np.exp(a_hat))
    p_hat = float(1.0 / (1.0 + np.exp(-b_hat)))

    # refine pi via 1D-optimalisatie (max L):
    def nll_pi(pi):
        pi = np.clip(pi, 1e-9, 1-1e-9)
        # L = pi^#1 * (1-pi)^(#rest) * Π pmf_cond(k_i)  (pmf_cond hangt niet af van pi)
        return -(ones*np.log(pi) + (n-ones)*np.log(1-pi))
    pi_hat = float(np.clip(optimize.minimize_scalar(nll_pi, bounds=(0,1), method='bounded').x, 1e-9, 1-1e-9))

    return pi_hat, r_hat, p_hat

def plot_hurdle_one_vs_data(data, pi, r, p, title="Hurdle(1) NB vs data"):
    data = np.asarray(data, dtype=int)
    plt.figure(figsize=(10,6))
    plt.hist(data, bins=np.arange(1, data.max()+2), density=True, alpha=0.6, label="Originele data", edgecolor='black')

    x = np.arange(1, data.max()+1)
    pmf_nb = stats.nbinom.pmf(x-1, r, p)       # ongeconditioneerde NB op k=x-1
    tail = 1.0 - stats.nbinom.cdf(0, r, p)     # P(k>=1)
    pmf_cond = pmf_nb.copy()
    pmf_cond[0] = 0.0                          # x=1 → k=0 valt buiten k>=1
    pmf_cond[1:] /= np.clip(tail, 1e-12, 1.0)  # conditionering voor x>=2

    pmf_hurdle = np.zeros_like(x, dtype=float)
    pmf_hurdle[0] = pi                         # massa op x=1
    pmf_hurdle[1:] = (1 - pi) * pmf_cond[1:]   # rest

    plt.plot(x, pmf_hurdle, 'o-', label=f'Hurdle PMF (π={pi:.3f}, r={r:.2f}, p={p:.3f})')
    plt.xlabel("Aantal items per bestelling")
    plt.ylabel("Genormaliseerde frequentie")
    plt.title(title)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()
# =========================
# Main
# =========================


# =========================================================
# NB-helpers
# =========================================================
def _nb_params_from_moments(mean, var):
    if var <= mean:
        raise ValueError("NB-momentfit onhaalbaar: variantie ≤ gemiddelde.")
    p = mean / var
    r = mean**2 / (var - mean)
    if not (0 < p < 1) or r <= 0:
        raise ValueError("NB-parameters ongeldig uit momenten.")
    return r, p

def fit_nb_mle(data):
    """
    NB op k = X-1 (k>=0). MLE met reparam: r=exp(a), p=sigmoid(b).
    """
    data = np.asarray(data, dtype=int)
    k = data - 1

    def nll(theta):
        a, b = theta
        r = np.exp(a)
        p = 1.0 / (1.0 + np.exp(-b))
        return -np.sum(stats.nbinom.logpmf(k, r, p))

    m, v = data.mean(), data.var(ddof=1)
    if v > m:
        p0 = m / v
        r0 = m**2 / (v - m)
        a0 = np.log(max(r0, 1e-6))
        b0 = np.log(p0/(1-p0))
    else:
        a0, b0 = np.log(1.0), 0.0

    res = minimize(nll, x0=np.array([a0, b0]), method="L-BFGS-B")
    a_hat, b_hat = res.x
    r_hat = float(np.exp(a_hat))
    p_hat = float(1.0 / (1.0 + np.exp(-b_hat)))
    return r_hat, p_hat

# =========================================================
# Hurdle(1) NB (aparte massa op X=1, NB geconditioneerd voor X≥2)
# =========================================================
def fit_hurdle_one(data):
    data = np.asarray(data, dtype=int)
    n = len(data)
    n1 = int(np.sum(data == 1))
    rest = data[data > 1]
    if rest.size == 0:
        raise ValueError("Alle data zijn 1; hurdle-fit niet zinvol.")

    # NB-parameters op k_rest = x-1 (maar k>=1) via geconditioneerde likelihood
    k_rest = rest - 1  # k>=1

    def nll_nb_rest(theta):
        a, b = theta
        r = np.exp(a)
        p = 1.0 / (1.0 + np.exp(-b))
        pmf_k = stats.nbinom.pmf(k_rest, r, p)
        tail = 1.0 - stats.nbinom.cdf(0, r, p)  # P(k>=1)
        pmf_cond = pmf_k / np.clip(tail, 1e-12, 1.0)
        return -np.sum(np.log(np.clip(pmf_cond, 1e-12, 1.0)))

    # starts: NB-MLE op volledige data
    r0, p0 = fit_nb_mle(data)
    a0, b0 = np.log(r0), np.log(p0/(1-p0))
    _ = minimize(nll_nb_rest, x0=np.array([a0, b0]), method="L-BFGS-B")
    a_hat, b_hat = _.x
    r_hat = float(np.exp(a_hat))
    p_hat = float(1.0 / (1.0 + np.exp(-b_hat)))

    # π via 1D MLE (gesloten vorm ≈ n1/n, maar we optimaliseren netjes)
    def nll_pi(pi):
        pi = np.clip(pi, 1e-12, 1-1e-12)
        return -(n1*np.log(pi) + (n-n1)*np.log(1-pi))
    pi_hat = float(np.clip(minimize_scalar(nll_pi, bounds=(0,1), method='bounded').x, 1e-9, 1-1e-9))

    return pi_hat, r_hat, p_hat

# =========================================================
# Bins + expected per bin
# =========================================================
def _get_bins_by_expected_nb(data, r, p, min_expected=5):
    data = np.asarray(data, dtype=int)
    n = len(data)
    max_x = int(data.max())
    # expected per individuele waarde x
    exp_single = n * stats.nbinom.pmf(np.arange(1, max_x+1)-1, r, p)  # x=1..max
    # voeg staart samen van rechts tot elke bin >= min_expected
    bins = list(range(1, max_x+2))  # [1,2,...,max+1]
    edges = []
    acc = 0.0
    for i in reversed(range(len(exp_single))):
        acc += exp_single[i]
        if acc >= min_expected:
            edges.insert(0, bins[i+1])
            acc = 0.0
    edges.insert(0, 1)
    return np.array(edges, dtype=int)

def _expected_counts_nb_bins(n, r, p, bins):
    exp = np.zeros(len(bins)-1)
    for i in range(len(bins)-1):
        a, b = bins[i], bins[i+1]  # [a,b)
        ks = np.arange(a-1, b-1)  # k=x-1
        exp[i] = n * np.sum(stats.nbinom.pmf(ks, r, p))
    return exp

def _hurdle_uncond_pmf(x, pi, r, p):
    """
    Ongeconditioneerde PMF voor Hurdle(1):
    P(X=1)=pi; P(X=x≥2)=(1-pi)* NB(k=x-1)/P(k≥1)
    """
    x = np.asarray(x, dtype=int)
    pmf_nb = stats.nbinom.pmf(x-1, r, p)
    tail = 1.0 - stats.nbinom.cdf(0, r, p)
    pmf = np.zeros_like(x, dtype=float)
    pmf[x == 1] = pi
    mask = x >= 2
    pmf[mask] = (1 - pi) * pmf_nb[mask] / np.clip(tail, 1e-12, 1.0)
    return pmf

def _hurdle_cdf(x, pi, r, p):
    """
    Ongeconditioneerde CDF voor Hurdle(1).
    Voor x>=2: F(x)=pi + (1-pi)* (F_NB(x-1)-P(k=0)) / P(k>=1)
    """
    x = np.asarray(x, dtype=int)
    cdf = np.zeros_like(x, dtype=float)
    nb_cdf = stats.nbinom.cdf(x-1, r, p)
    p0 = stats.nbinom.pmf(0, r, p)
    denom = np.clip(1 - p0, 1e-12, 1.0)
    cdf = np.where(x < 1, 0.0, cdf)
    cdf = np.where(x == 1, pi, cdf)
    mask = x >= 2
    cdf[mask] = pi + (1 - pi) * (nb_cdf[mask] - p0) / denom
    return cdf

def _get_bins_by_expected_hurdle(data, pi, r, p, min_expected=5):
    data = np.asarray(data, dtype=int)
    n = len(data)
    max_x = int(data.max())
    x = np.arange(1, max_x+1)
    exp_single = n * _hurdle_uncond_pmf(x, pi, r, p)
    bins = list(range(1, max_x+2))
    edges, acc = [], 0.0
    for i in reversed(range(len(exp_single))):
        acc += exp_single[i]
        if acc >= min_expected:
            edges.insert(0, bins[i+1])
            acc = 0.0
    edges.insert(0, 1)
    return np.array(edges, dtype=int)

# =========================================================
# Metrics per model
# =========================================================
def _empirical_pmf(data):
    data = np.asarray(data, dtype=int)
    max_x = data.max()
    counts = np.bincount(data, minlength=max_x+1)[1:]
    pmf = counts / counts.sum()
    x = np.arange(1, max_x+1)
    return x, pmf

def _ks_discrete(sorted_data, cdf_at_values):
    n = len(sorted_data)
    emp_cdf = np.arange(1, n+1) / n
    ks = float(np.max(np.abs(emp_cdf - cdf_at_values)))
    # conservatieve p-waarde voor discrete
    pval = stats.kstwobign.sf(ks*np.sqrt(n))
    return ks, pval

def _aic_bic(loglik, k, n):
    aic = 2*k - 2*loglik
    bic = k*np.log(n) - 2*loglik
    return float(aic), float(bic)

def compare_nb_models(data, show_plot=True):
    data = np.asarray(data, dtype=int)
    n = len(data)
    max_x = data.max()
    x_vals = np.arange(1, max_x+1)
    sorted_data = np.sort(data)

    results = []

    # ---------- NB (moments)
    try:
        r_m, p_m = _nb_params_from_moments(data.mean(), data.var(ddof=1))
        pmf_m = stats.nbinom.pmf(x_vals-1, r_m, p_m)
        cdf_m = stats.nbinom.cdf(x_vals-1, r_m, p_m)
        # loglik over individuele observaties
        loglik_m = float(np.sum(np.log(np.clip(stats.nbinom.pmf(data-1, r_m, p_m), 1e-12, 1.0))))
        aic_m, bic_m = _aic_bic(loglik_m, k=2, n=n)
        # χ² met model-specifieke bins
        bins_m = _get_bins_by_expected_nb(data, r_m, p_m, min_expected=5)
        obs_m, _ = np.histogram(data, bins=bins_m)
        exp_m = _expected_counts_nb_bins(n, r_m, p_m, bins_m)
        valid = exp_m >= 5
        chi2_m = float(np.sum((obs_m[valid] - exp_m[valid])**2 / exp_m[valid]))
        df_m = int(np.sum(valid) - 1 - 2)
        chi2p_m = float(1 - stats.chi2.cdf(chi2_m, max(df_m, 1)))
        # KS
        cdf_at_sorted = stats.nbinom.cdf(sorted_data-1, r_m, p_m)
        ks_m, ksp_m = _ks_discrete(sorted_data, cdf_at_sorted)
        # SSE
        _, emp_pmf = _empirical_pmf(data)
        sse_m = float(np.mean((emp_pmf - pmf_m)**2))
        results.append(dict(Model="NB (moments)", r=r_m, p=p_m, pi=np.nan,
                            AIC=aic_m, BIC=bic_m, Chi2=chi2_m, Chi2_df=df_m, Chi2_p=chi2p_m,
                            KS=ks_m, KS_p=ksp_m, SSE=sse_m))
    except ValueError:
        pass

    # ---------- NB (MLE)
    r_ml, p_ml = fit_nb_mle(data)
    pmf_ml = stats.nbinom.pmf(x_vals-1, r_ml, p_ml)
    cdf_ml = stats.nbinom.cdf(x_vals-1, r_ml, p_ml)
    loglik_ml = float(np.sum(np.log(np.clip(stats.nbinom.pmf(data-1, r_ml, p_ml), 1e-12, 1.0))))
    aic_ml, bic_ml = _aic_bic(loglik_ml, k=2, n=n)
    bins_ml = _get_bins_by_expected_nb(data, r_ml, p_ml, min_expected=5)
    obs_ml, _ = np.histogram(data, bins=bins_ml)
    exp_ml = _expected_counts_nb_bins(n, r_ml, p_ml, bins_ml)
    valid = exp_ml >= 5
    chi2_ml = float(np.sum((obs_ml[valid] - exp_ml[valid])**2 / exp_ml[valid]))
    df_ml = int(np.sum(valid) - 1 - 2)
    chi2p_ml = float(1 - stats.chi2.cdf(chi2_ml, max(df_ml, 1)))
    cdf_at_sorted_ml = stats.nbinom.cdf(sorted_data-1, r_ml, p_ml)
    ks_ml, ksp_ml = _ks_discrete(sorted_data, cdf_at_sorted_ml)
    _, emp_pmf = _empirical_pmf(data)
    sse_ml = float(np.mean((emp_pmf - pmf_ml)**2))
    results.append(dict(Model="NB (MLE)", r=r_ml, p=p_ml, pi=np.nan,
                        AIC=aic_ml, BIC=bic_ml, Chi2=chi2_ml, Chi2_df=df_ml, Chi2_p=chi2p_ml,
                        KS=ks_ml, KS_p=ksp_ml, SSE=sse_ml))

    # ---------- Hurdle(1) NB
    pi_h, r_h, p_h = fit_hurdle_one(data)
    pmf_h = _hurdle_uncond_pmf(x_vals, pi_h, r_h, p_h)
    cdf_h = _hurdle_cdf(x_vals, pi_h, r_h, p_h)
    # loglik: π voor x=1; (1-π)*NB_cond voor x≥2
    k = data - 1
    p0 = stats.nbinom.pmf(0, r_h, p_h)
    tail = np.clip(1 - p0, 1e-12, 1.0)
    ll_h = np.where(data == 1,
                    np.log(np.clip(pi_h, 1e-12, 1.0)),
                    np.log(np.clip((1 - pi_h), 1e-12, 1.0)) +
                    stats.nbinom.logpmf(k, r_h, p_h) - np.log(tail))
    loglik_h = float(np.sum(ll_h))
    aic_h, bic_h = _aic_bic(loglik_h, k=3, n=n)
    bins_h = _get_bins_by_expected_hurdle(data, pi_h, r_h, p_h, min_expected=5)
    obs_h, _ = np.histogram(data, bins=bins_h)
    # expected per bin via onvoorwaardelijke hurdle-PMF
    exp_single_h = n * _hurdle_uncond_pmf(np.arange(1, data.max()+1), pi_h, r_h, p_h)
    exp_h = np.array([exp_single_h[a-1:b-1].sum() for a, b in zip(bins_h[:-1], bins_h[1:])])
    valid = exp_h >= 5
    chi2_h = float(np.sum((obs_h[valid] - exp_h[valid])**2 / exp_h[valid]))
    df_h = int(np.sum(valid) - 1 - 3)
    chi2p_h = float(1 - stats.chi2.cdf(chi2_h, max(df_h, 1)))
    # KS
    cdf_at_sorted_h = _hurdle_cdf(sorted_data, pi_h, r_h, p_h)
    ks_h, ksp_h = _ks_discrete(sorted_data, cdf_at_sorted_h)
    sse_h = float(np.mean((emp_pmf - pmf_h)**2))
    results.append(dict(Model="Hurdle(1) NB", r=r_h, p=p_h, pi=pi_h,
                        AIC=aic_h, BIC=bic_h, Chi2=chi2_h, Chi2_df=df_h, Chi2_p=chi2p_h,
                        KS=ks_h, KS_p=ksp_h, SSE=sse_h))

    df = pd.DataFrame(results)
    df_sorted = df.sort_values("AIC").reset_index(drop=True)

    # Plot
    if show_plot:
        plt.figure(figsize=(11,6))
        plt.hist(data, bins=np.arange(1, max_x+2), density=True, alpha=0.45,
                 label="Originele data", edgecolor='black')
        if "NB (moments)" in df["Model"].values:
            plt.plot(x_vals, pmf_m, 'o-', label=f"NB (moments) r={r_m:.2f}, p={p_m:.3f}")
        plt.plot(x_vals, pmf_ml, 's--', label=f"NB (MLE) r={r_ml:.2f}, p={p_ml:.3f}")
        plt.plot(x_vals, pmf_h, 'x-', label=f"Hurdle(1) π={pi_h:.3f}, r={r_h:.2f}, p={p_h:.3f}")
        plt.xlabel("Aantal items per bestelling")
        plt.ylabel("Genormaliseerde frequentie")
        plt.title("Vergelijking modellen: NB (moments) vs NB (MLE) vs Hurdle(1)")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

    return df_sorted

if __name__ == "__main__":
    data = NBVerdeling(2)
    # r, p = nb_fit_report(data)
    # bins = get_valid_chi2_bins(data, r, p, min_expected=5)
    # evaluate_negative_binomial_fit(data, r, p, bins)

    # # 1) NB MLE
    # r_mle, p_mle, _ = fit_nb_mle(data)
    # plot_nb_vs_data(data, r_mle, p_mle, title="NB (MLE) vs data")
    #
    # # 2) Hurdle op 1 (pakt de piek)
    # pi, r_h, p_h = fit_hurdle_one(data)
    # plot_hurdle_one_vs_data(data, pi, r_h, p_h, title="Hurdle(1) NB vs data")
    # gamma_fit_report(data)
    # fit_zinb_and_report(data)

    try:
        comparison = compare_nb_models(data, show_plot=True)
        print("\n=== Modelvergelijking (gesorteerd op AIC, lager = beter) ===")
        print(comparison.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    except NameError:
        print("Definieer eerst 'data' of roep NBVerdeling(method) aan.")

