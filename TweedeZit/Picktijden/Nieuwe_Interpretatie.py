import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.mixture import GaussianMixture
from sklearn.model_selection import GridSearchCV
from sklearn.neighbors import KernelDensity
from scipy.stats import norm


# ---------- helpers ----------
def load_filtered(csv_path, col="Picktijd (sec)"):
    df = pd.read_csv(csv_path, usecols=[col]).dropna()
    t = pd.to_numeric(df[col], errors="coerce").dropna().values.astype(float)
    t = t[t > 0]
    q1, q3 = np.percentile(t, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5*iqr, q3 + 1.5*iqr
    keep = (t >= lo) & (t <= hi)
    return t[keep]

def freedman_diaconis_bins(x):
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    bw = 2 * iqr / np.cbrt(len(x))
    if bw <= 0:
        return 60
    return max(20, int(np.ceil((x.max() - x.min()) / bw)))

def kde_log_cv(t, grid_pts=1200, cv_max_n=30000,
               bw_grid=np.logspace(-1.2, 0.7, 25), random_state=0):
    """
    KDE op y=log(1+t):
    - Kies bandbreedte via 5-fold CV op een subsample (max cv_max_n punten).
    - Fit KDE op alle data met die beste bandbreedte.
    - Transformeer terug naar f_T(x) = f_Y(log(1+x)) / (1+x).
    """
    y = np.log1p(t).reshape(-1, 1)
    n = len(y)

    # Subsample voor CV (voorkomt NxN geheugen/werk)
    if n > cv_max_n:
        rng = np.random.default_rng(random_state)
        idx = rng.choice(n, size=cv_max_n, replace=False)
        y_cv = y[idx]
    else:
        y_cv = y

    # Bandbreedte-selectie via k-fold CV
    search = GridSearchCV(
        KernelDensity(kernel="gaussian"),
        param_grid={"bandwidth": bw_grid},
        cv=5,
        n_jobs=-1
    )
    search.fit(y_cv)
    best_bw = float(search.best_params_["bandwidth"])

    # Fit KDE op alle punten met gekozen bandbreedte
    kde = KernelDensity(kernel="gaussian", bandwidth=best_bw).fit(y)

    # Evaluate op grid en terugtransformeren met de jacobiaan
    xgrid = np.linspace(0, np.percentile(t, 99.5), grid_pts)
    ygrid = np.log1p(xgrid).reshape(-1, 1)
    log_fY = kde.score_samples(ygrid)
    fY = np.exp(log_fY)
    fT = fY / (1.0 + xgrid)

    return xgrid, fT, best_bw
# --- Parametrische fits ---
def fit_families(t):
    # Lognormaal: pas op – scipy gebruikt s=shape (sigma), scale=exp(mu)
    shape, loc, scale = stats.lognorm.fit(t, floc=0)
    ln_params = dict(s=shape, scale=scale)
    ln_loglik = np.sum(stats.lognorm.logpdf(t, **ln_params))
    ln_k = 2  # (s, scale)

    # Gamma
    a, locg, scaleg = stats.gamma.fit(t, floc=0)
    ga_params = dict(a=a, scale=scaleg)
    ga_loglik = np.sum(stats.gamma.logpdf(t, **ga_params))
    ga_k = 2

    # Weibull (scipy: c=shape)
    c, locw, scalew = stats.weibull_min.fit(t, floc=0)
    wb_params = dict(c=c, scale=scalew)
    wb_loglik = np.sum(stats.weibull_min.logpdf(t, **wb_params))
    wb_k = 2

    n = len(t)
    def aic(ll, k): return 2*k - 2*ll
    def bic(ll, k): return k*np.log(n) - 2*ll

    models = [
        ("Lognormal", ln_params, ln_loglik, ln_k, aic(ln_loglik, ln_k), bic(ln_loglik, ln_k)),
        ("Gamma",     ga_params, ga_loglik, ga_k, aic(ga_loglik, ga_k), bic(ga_loglik, ga_k)),
        ("Weibull",   wb_params, wb_loglik, wb_k, aic(wb_loglik, wb_k), bic(wb_loglik, wb_k)),
    ]
    models.sort(key=lambda r: r[5])  # sort by BIC (lowest best)
    return models  # list of tuples

def pdf_from_best(model_name, params, x):
    if model_name == "Lognormal":
        return stats.lognorm.pdf(x, **params)
    if model_name == "Gamma":
        return stats.gamma.pdf(x, **params)
    if model_name == "Weibull":
        return stats.weibull_min.pdf(x, **params)
    raise ValueError("Unknown model")

# --- Optioneel: 2-lognormaal (alleen als duidelijk beter & componenten niet mini) ---
def fit_two_lognormal_if_needed(t, best_bic):
    y = np.log1p(t).reshape(-1,1)
    gmm = GaussianMixture(n_components=2, covariance_type="full",
                          random_state=42, n_init=10, max_iter=500, reg_covar=1e-6)
    gmm.fit(y)
    bic2 = gmm.bic(y)
    weights = gmm.weights_
    min_w = weights.min()
    return gmm, bic2, min_w

# ---------- hoofdfunctie: één verdedigbare plot ----------
def plot_explained_picktijden(csv="test.csv", col="Picktijd (sec)", xlim=30):
    t = load_filtered(csv, col)
    n = len(t)

    # 1) histogram-bins
    bins = freedman_diaconis_bins(t)

    # 2) KDE op log-schaal (CV-bandbreedte)
    xgrid, kde_pdf, bw = kde_log_cv(t)

    # 3) param-families
    fams = fit_families(t)
    best_name, best_params, best_ll, best_k, best_aic, best_bic = fams[0]

    # 4) check 2-lnorm
    gmm2, bic2, min_w = fit_two_lognormal_if_needed(t, best_bic)
    use_mix2 = (bic2 + 10 < best_bic) and (min_w >= 0.05)  # streng
    if use_mix2:
        ygrid = np.log1p(xgrid).reshape(-1,1)
        pdf_y = np.exp(gmm2.score_samples(ygrid))
        mix2_pdf = pdf_y / (1.0 + xgrid)

    # 5) plot
    # jiter voor heaping zichtbaar maken (alleen voor visueel histogram)
    rng = np.random.default_rng(0)
    t_jit = t + rng.uniform(-0.25, 0.25, size=n)

    plt.figure(figsize=(11,6))
    plt.hist(t_jit, bins=bins, density=True, alpha=0.45, label="Empirisch (gefilterd, ±0.25s jitter)")
    plt.plot(xgrid, kde_pdf, label=f"KDE (log-schaal, bw={bw:.3f})", linewidth=2)

    if use_mix2:
        plt.plot(xgrid, mix2_pdf, label=f"2-lognorm mix (BIC={bic2:.0f}, min w={min_w:.2f})", linewidth=2)
        model_line = "—"
    else:
        best_pdf = pdf_from_best(best_name, best_params, xgrid)
        plt.plot(xgrid, best_pdf, label=f"Beste param: {best_name} (BIC={best_bic:.0f})", linewidth=2)
        model_line = best_name

    plt.xlim(0, xlim); plt.xlabel("Picktijd (sec)"); plt.ylabel("Dichtheid")
    plt.title("Picktijdverdeling: data vs KDE (log-correctie) vs parametrisch model")
    plt.grid(True); plt.legend()
    plt.tight_layout()
    plt.savefig("picktijden_verdedigbaar.png", dpi=200)
    plt.show()

    # 6) korte verantwoording printen
    med = np.median(t); p90 = np.percentile(t, 90)
    print(f"n={n}, median={med:.2f}s, p90={p90:.2f}s")
    print(f"KDE-bandbreedte (log) gekozen via CV: {bw:.3f}")
    if use_mix2:
        print(f"2-lognormaal gekozen boven {model_line} omdat ΔBIC≥10 en min. gewicht ≥5% → plausibel 'twee contexten'.")
    else:
        print(f"Beste enkelvoudig model volgens BIC: {best_name} — gebruik deze curve als compacte rapportage.")

# ---------- hergebruikte loader (uit jouw pipeline) ----------
def load_filtered(csv_path, col="Picktijd (sec)"):
    df = pd.read_csv(csv_path, usecols=[col]).dropna()
    t = pd.to_numeric(df[col], errors="coerce").dropna().values.astype(float)
    t = t[t > 0]
    q1, q3 = np.percentile(t, [25, 75]); iqr = q3 - q1
    lo, hi = q1 - 1.5*iqr, q3 + 1.5*iqr
    return t[(t >= lo) & (t <= hi)]

# ---------- util: mixture percentielen en drempel ----------
def mixture_cdf(t, weights, mus, sigmas):
    """
    CDF van 2-lognormale mixture op de oorspronkelijke schaal (seconden).
    t mag scalar of array zijn.
    """
    t = np.asarray(t).ravel()              # <-- vlak maken
    y = np.log1p(t)
    z = (y[:, None] - mus[None, :]) / sigmas[None, :]
    cdf_vals = (norm.cdf(z) * weights).sum(axis=1)
    return np.clip(cdf_vals, 0.0, 1.0)

def mixture_quantile(p, weights, mus, sigmas, lo=0.0, hi=60.0):
    # bisection in seconds
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if mixture_cdf(np.array([mid]), weights, mus, sigmas)[0] < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

def decision_threshold(weights, mus, sigmas):
    # solve w1*N(y|μ1,σ1) = w2*N(y|μ2,σ2) in y-space; pick root between means
    w1, w2 = weights
    m1, m2 = mus
    s1, s2 = sigmas
    a = 0.5 * (1/s2**2 - 1/s1**2)
    b = (m1/s1**2 - m2/s2**2)
    c = 0.5 * (m2**2/s2**2 - m1**2/s1**2) + np.log((w2*s1)/(w1*s2))
    # a*y^2 + b*y + c = 0
    disc = b*b - 4*a*c
    roots = []
    if disc >= 0:
        r1 = (-b + np.sqrt(disc)) / (2*a) if a != 0 else None
        r2 = (-b - np.sqrt(disc)) / (2*a) if a != 0 else None
        roots = [r for r in [r1, r2] if r is not None]
    # kies root tussen μ1 en μ2, anders neem degene ertussen het dichtstbij
    root = min(roots, key=lambda r: abs(r - 0.5*(m1+m2))) if roots else (m1+m2)/2
    return np.expm1(root)  # terug naar seconden

# ---------- fit + rapport ----------
def fit_two_lognormal(csv="test.csv", col="Picktijd (sec)", seed=42):
    t = load_filtered(csv, col)
    y = np.log1p(t).reshape(-1,1)

    gmm = GaussianMixture(n_components=2, covariance_type="full",
                          random_state=seed, n_init=10, max_iter=500, reg_covar=1e-6).fit(y)
    weights = gmm.weights_.astype(float)
    mus = gmm.means_.ravel().astype(float)
    sigmas = np.sqrt(gmm.covariances_.reshape(-1)).astype(float)
    # order by mean
    order = np.argsort(mus); weights, mus, sigmas = weights[order], mus[order], sigmas[order]

    bic = gmm.bic(y)
    # component stats on original scale
    comp_median = np.exp(mus) - 1
    comp_mean   = np.exp(mus + 0.5*sigmas**2) - 1
    mix_mean    = float(np.dot(weights, comp_mean))
    p50 = mixture_quantile(0.50, weights, mus, sigmas)
    p90 = mixture_quantile(0.90, weights, mus, sigmas)
    t_star = decision_threshold(weights, mus, sigmas)

    # KS (empirical vs mixture)
    from scipy.stats import kstest
    # custom CDF for kstest
    cdf_func = lambda x: mixture_cdf(x, weights, mus, sigmas)
    ks_stat, ks_p = kstest(t, cdf_func)

    summary = {
        "n": int(len(t)),
        "weights": list(map(float, weights)),
        "mu":      list(map(float, mus)),
        "sigma":   list(map(float, sigmas)),
        "bic":     float(bic),
        "component_median_sec": list(map(float, comp_median)),
        "component_mean_sec":   list(map(float, comp_mean)),
        "mixture_mean_sec":     mix_mean,
        "mixture_p50_sec":      float(p50),
        "mixture_p90_sec":      float(p90),
        "threshold_t_star_sec": float(t_star),
        "ks_stat": float(ks_stat),
        "ks_p":    float(ks_p)
    }
    return t, summary

def save_model_json(summary, path="picktijd_model_2lognorm.json"):
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"💾 Modelparameters opgeslagen: {path}")

def simulate_picktijden(n, summary, seed=123):
    rng = np.random.default_rng(seed)
    w = np.array(summary["weights"])
    mu = np.array(summary["mu"])
    sigma = np.array(summary["sigma"])
    comps = rng.choice(len(w), size=n, p=w)
    y = rng.normal(loc=mu[comps], scale=sigma[comps])
    return np.expm1(y)

def pp_plot(t, summary, out_png="pp_plot.png"):
    w = np.array(summary["weights"]); mu = np.array(summary["mu"]); sigma = np.array(summary["sigma"])
    t_sorted = np.sort(t)
    emp_p = (np.arange(1, len(t_sorted)+1) - 0.5) / len(t_sorted)
    theo_p = mixture_cdf(t_sorted, w, mu, sigma)
    plt.figure(figsize=(6,6))
    plt.plot(emp_p, theo_p, '.', alpha=0.5)
    plt.plot([0,1],[0,1], 'k--')
    plt.xlabel("Empirische CDF"); plt.ylabel("Theoretische CDF (2-lognorm)")
    plt.title("PP-plot (hoe dichter op diagonaal, hoe beter)")
    plt.grid(True); plt.tight_layout(); plt.savefig(out_png, dpi=160); plt.show()
    print(f"PP-plot opgeslagen als '{out_png}'")
# ------------------------------ MAIN ------------------------------
if __name__ == "__main__":
    # Pad naar je CSV met kolom "Picktijd (sec)"
    CSV_PATH = "test.csv"
    COL_NAME = "Picktijd (sec)"

    # Max x-as voor de figuur (pas aan als je wilt)
    XLIM = 30

    # 1 call die alles doet:
    # - IQR-filter
    # - histogram (Freedman–Diaconis, met kleine jitter i.v.m. heaping)
    # - KDE op log-schaal met CV-bandbreedte
    # - beste parametrische fit (lognormaal/gamma/weibull) o.b.v. BIC
    #   of 2-lognormaal als dat objectief beter is (ΔBIC ≥ 10 en min weight ≥ 5%)
    plot_explained_picktijden(csv=CSV_PATH, col=COL_NAME, xlim=XLIM)

    print("✅ Klaar. Figuur opgeslagen als 'picktijden_verdedigbaar.png'.")

    # Fit en rapport
    t, model = fit_two_lognormal(csv=CSV_PATH, col=COL_NAME)
    print("\n=== 2-lognormaal samenvatting ===")
    print(json.dumps(model, indent=2))

    # Bewaar parameters en maak PP-plot
    save_model_json(model, "picktijd_model_2lognorm.json")
    pp_plot(t, model, out_png="pp_plot.png")

    # Voor simulaties (voorbeeld)
    sims = simulate_picktijden(10_000, model, seed=1)
    print(f"\nSimulatie: mean={sims.mean():.2f}s, p90={np.percentile(sims, 90):.2f}s")


