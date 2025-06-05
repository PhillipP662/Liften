import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import numpy as np
from scipy import stats
from scipy.stats import chisquare, hypergeom
def get_freqs(dataset, bins):
    counts, _ = np.histogram(dataset, bins=bins)
    return counts


def genereer_nb_waarde(r, p):
    return stats.nbinom.rvs(r, p) +1;

# === Functie: Genereer waarde volgens Zero-Inflated Negatief Binomiaal ===
def genereer_zinb_waarde(pi,r, p):
    if np.random.rand() < pi:
        return 1
    else:
        return stats.nbinom.rvs(r, p) +1




# Bestanden
bestandspaden = [
    'ExcelData/1_VerdelingItem01_03.xlsx',
    'ExcelData/2_VerdelingItem04_06.xlsx',
    'ExcelData/3_VerdelingItem07_09.xlsx',
    'ExcelData/4_VerdelingItem10_12.xlsx',
    'ExcelData/5_VerdelingItem13_15.xlsx',
    'ExcelData/6_VerdelingItem16_19.xlsx',
]

# Gegevens samenvoegen
alle_bestellingen = []
for pad in bestandspaden:
    df = pd.read_excel(pad, sheet_name="BestellingSize")
    order_sizes = df['Outbound order number'].value_counts().values
    alle_bestellingen.extend(order_sizes)

data = np.array(alle_bestellingen)
n = len(data)

# Negatief-bin verdeling
mean = np.mean(data)
var = np.var(data, ddof=1)
p_nb = mean / var
r_nb = mean**2 / (var - mean)

# Pi-optimalisatie ZINB
data_nb_part = data[data > 1]
mean_nb = np.mean(data_nb_part)
var_nb = np.var(data_nb_part, ddof=1)
p_zinb = mean_nb / var_nb
r_zinb = mean_nb**2 / (var_nb - mean_nb)

# Bepaal bins
bins = np.arange(1, max(data) + 2)

def get_freqs(dataset, bins):
    counts, _ = np.histogram(dataset, bins=bins)
    return counts

# Zoek beste pi op log-likelihood
results = []
for pi in np.arange(0.25, 0.61, 0.001):
    np.random.seed(42)
    zinb_sim = np.where(
        np.random.rand(n) < pi,
        1,
        stats.nbinom.rvs(r_zinb, p_zinb, size=n) + 1
    )
    obs = get_freqs(data, bins)
    exp = get_freqs(zinb_sim, bins)

    mask = (exp >= 5) & (obs >= 5)
    if mask.sum() < 5:
        continue

    obs_f = obs[mask]
    exp_f = exp[mask]
    exp_scaled = exp_f * (obs_f.sum() / exp_f.sum())

    chi2, pval = stats.chisquare(f_obs=obs_f, f_exp=exp_scaled)
    ll = np.sum(np.log(pi * (data == 1) + (1 - pi) * stats.nbinom.pmf(data - 1, r_zinb, p_zinb)))
    results.append((pi, chi2, pval, ll))

beste_pi = sorted(results, key=lambda x: x[3], reverse=True)[0]
pi_opt = beste_pi[0]

print(f"Beste pi op log-likelihood: {pi_opt:.2f}")
print(f"Log-likelihood ZINB: {beste_pi[3]:.2f}")
print(f"Chi²-statistiek ZINB: {beste_pi[1]:.2f}, p = {beste_pi[2]:.4f}")

# NB simulatie (correctie +1)
np.random.seed(42)
simulated_nb = stats.nbinom.rvs(r_nb, p_nb, size=n) + 1

# ZINB simulatie (correctie +1)
np.random.seed(42)
draws = np.random.rand(n)
simulated_zinb = np.where(draws < pi_opt, 1, stats.nbinom.rvs(r_zinb, p_zinb, size=n) + 1)

# Log-likelihood NB (ook shift bij pmf)
ll_nb = np.sum(stats.nbinom.logpmf(data - 1, r_nb, p_nb))
print(f"\nLog-likelihood NB: {ll_nb:.2f}")

# Plot
# plt.figure(figsize=(12, 6))
# plt.hist(data, bins=bins, alpha=0.6, label='Origineel', density=True)
# plt.hist(simulated_nb, bins=bins, alpha=0.4, label='Negatief Binomiaal', density=True)
# plt.hist(simulated_zinb, bins=bins, alpha=0.4, label=f'ZINB (beste pi={pi_opt:.2f})', density=True)
# plt.xlabel("Aantal items per bestelling")
# plt.ylabel("Genormaliseerde frequentie")
# plt.title("Overlay: Originele data vs NB en ZINB simulaties")
# plt.legend()
# plt.grid(True)
# plt.tight_layout()
# plt.show()

# Versie voor FigureCanvasAgg (had fouten met mijn versie) ===================
fig = plt.figure(figsize=(12, 6))
canvas = FigureCanvas(fig)
ax = fig.add_subplot(111)

# Replot using ax instead of plt
ax.hist(data, bins=bins, alpha=0.6, label='Origineel', density=True)
ax.hist(simulated_nb, bins=bins, alpha=0.4, label='Negatief Binomiaal', density=True)
ax.hist(simulated_zinb, bins=bins, alpha=0.4, label=f'ZINB (beste pi={pi_opt:.2f})', density=True)
ax.set_xlabel("Aantal items per bestelling")
ax.set_ylabel("Genormaliseerde frequentie")
ax.set_title("Overlay: Originele data vs NB en ZINB simulaties")
ax.legend()
ax.grid(True)

ax.set_xlim(0, 60)  # Adjust as needed
canvas.draw()
image = canvas.buffer_rgba()  # Or use .tostring_rgb() if needed

fig.savefig("zinb_plot.png", dpi=300)
print("Plot saved as 'zinb_plot.png'")
# Versie voor FigureCanvasAgg (had fouten met mijn versie) ===================

print("NB sample:", genereer_nb_waarde(r_nb,p_nb))
print("ZINB sample:", genereer_zinb_waarde(pi_opt,r_zinb,p_zinb))