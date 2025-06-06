import os

import numpy as np
from numpy.random import default_rng
import pandas as pd
from matplotlib import pyplot as plt
from scipy import stats
from scipy.stats import lognorm, probplot, ks_2samp


USE_PRINT = False

def debug_print(*args, **kwargs):
    # use this instead of "print". it automatically checks if USE_PRINT is set or not
    if USE_PRINT:
        print(*args, **kwargs)

def afronden_op_seconde(dt_series):
    # Verwijder milliseconden (afronden naar beneden op de seconde)
    return dt_series.dt.floor('s')

def bereken_picktijden(timestamps):
    picktijden = []
    i = 0
    while i < len(timestamps) - 1:
        j = i + 1
        while j < len(timestamps) and timestamps[j] == timestamps[i]:
            j += 1
        if j < len(timestamps):
            verschil = (timestamps[j] - timestamps[i]).total_seconds()
            aantal_gelijke = j - i
            if aantal_gelijke > 0:
                per_stuk = verschil / (aantal_gelijke + 1)
                picktijden.extend([per_stuk] * aantal_gelijke)
        i += 1
    return picktijden

def filter_op_iqr(df):
    groeps = []
    for user, groep in df.groupby('Requester user code'):
        q1 = groep['Picktijd (sec)'].quantile(0.25)
        q3 = groep['Picktijd (sec)'].quantile(0.75)
        iqr = q3 - q1
        ondergrens = q1 - 1.5 * iqr
        bovengrens = q3 + 1.5 * iqr

        zonder_outliers = groep[
            (groep['Picktijd (sec)'] >= ondergrens) &
            (groep['Picktijd (sec)'] <= bovengrens)
        ]
        groeps.append(zonder_outliers)
    return pd.concat(groeps)


def sample_picktijd(verdelingen, gewichten, n=1):
    picktijden = []
    users = np.arange(len(verdelingen))

    # Eerst n users kiezen volgens de gewichten
    gekozen_users = np.random.choice(users, size=n, p=gewichten)

    for i in gekozen_users:
        shape, loc, scale = verdelingen[i]
        sample = lognorm.rvs(shape, loc=loc, scale=scale)
        picktijden.append(sample)

    return picktijden


def sample_globale_picktijd(n=1, np_rng=None):
    np_rng = np_rng or np.random.default_rng()

    picktijden = []
    users = np.arange(len(verdelingen))
    gekozen = np.random.choice(users, size=n, p=gewichten)
    for i in gekozen:
        shape, loc, scale = verdelingen[i]
        sample = lognorm.rvs(shape, loc=loc, scale=scale)
        picktijden.append(sample)
    return picktijden

def generate_picktime_samples(n=1000, data_folder='Dataverwerking_code/PicktijdenBerekening_IQR', np_rng=None):
    """
    Gebruikt om op te roepen in een ander script
    """
    np_rng = np_rng or np.random.default_rng()

    alle_df = []
    for bestand in os.listdir(data_folder):
        if bestand.endswith('_picktijden_IQR.csv'):
            df = pd.read_csv(os.path.join(data_folder, bestand))
            alle_df.append(df)

    if not alle_df:
        raise ValueError("Geen geldige CSV-bestanden gevonden in map:", data_folder)

    df_alle = pd.concat(alle_df, ignore_index=True)

    user_codes = df_alle['Requester user code'].unique()
    verdelingen = []
    gewichten = []
    totaal = len(df_alle)

    for user in user_codes:
        data = df_alle[df_alle['Requester user code'] == user]['Picktijd (sec)'].dropna().values
        if len(data) < 10:
            continue
        shape, loc, scale = lognorm.fit(data, floc=0)
        gewicht = len(data) / totaal
        verdelingen.append((shape, loc, scale))
        gewichten.append(gewicht)

    gewichten = np.array(gewichten)
    gewichten /= gewichten.sum()

    # Sampling
    picktijden = []
    users = np.arange(len(verdelingen))
    gekozen = np_rng.choice(users, size=n, p=gewichten)
    for i in gekozen:
        shape, loc, scale = verdelingen[i]
        sample = lognorm.rvs(shape, loc=loc, scale=scale, random_state=np_rng)
        picktijden.append(sample)

    return picktijden


if __name__ == "__main__":

    pad = 'PicktijdenBerekening_IQR'
    alle_df = []

    debug_print("📁 Bestanden gevonden in map:")
    debug_print(os.listdir(pad))

    for bestand in os.listdir(pad):
        if bestand.endswith('_picktijden_IQR.csv'):
            df = pd.read_csv(os.path.join(pad, bestand))
            alle_df.append(df)

    df_alle = pd.concat(alle_df, ignore_index=True)
    debug_print("Aantal rijen samengevoegd:", len(df_alle))

    # Sla gecombineerd bestand op
    output_path = os.path.join('TussenTijdseBerekening', 'AllePicktijdenSamengevoegd.csv')
    df_alle.to_csv(output_path, index=False)
    debug_print("✅ Samengevoegd bestand opgeslagen in:", os.path.abspath(output_path))

    # === STAP 2: Fit lognormale verdeling per user ===
    user_codes = df_alle['Requester user code'].unique()
    verdelingen = []
    gewichten = []
    totaal = len(df_alle)

    for user in user_codes:
        data = df_alle[df_alle['Requester user code'] == user]['Picktijd (sec)'].dropna().values
        if len(data) < 10:
            continue  # betrouwbaarheid
        shape, loc, scale = lognorm.fit(data, floc=0)
        gewicht = len(data) / totaal
        verdelingen.append((shape, loc, scale))
        gewichten.append(gewicht)

    gewichten = np.array(gewichten)
    gewichten = gewichten / gewichten.sum()
    debug_print(f"✅ {len(verdelingen)} gebruikers succesvol gefit.")



    # === STAP 4: Simulaties genereren ===
    simulaties = sample_globale_picktijd(100000)

    # === STAP 5: K-S test ===
    ks_resultaat = ks_2samp(df_alle['Picktijd (sec)'].values, simulaties)

    # === STAP 6: Histogram-verschil tussen echte data en simulatie ===
    counts_data, bins = np.histogram(df_alle['Picktijd (sec)'], bins=100, density=True)
    counts_model, _ = np.histogram(simulaties, bins=bins, density=True)
    histogram_verschil = np.abs(counts_data - counts_model).sum()

    # === STAP 7: Q-Q plot ===
    shape, loc, scale = lognorm.fit(simulaties, floc=0)

    # Maak de Q-Q plot
    plt.figure(figsize=(6, 6))
    probplot(simulaties, dist=lognorm(shape, loc=loc, scale=scale), plot=plt)
    plt.title("Q-Q plot van simulaties t.o.v. lognormale verdeling")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("Images/Q-QPlot.png")
    plt.close()

    # === STAP 8: Mixture model vs histogram plot ===
    x = np.linspace(0, np.percentile(df_alle['Picktijd (sec)'], 99.5), 1000)
    mixture_pdf = np.zeros_like(x)
    for i in range(len(verdelingen)):
        shape, loc, scale = verdelingen[i]
        w = gewichten[i]
        pdf = lognorm.pdf(x, shape, loc=loc, scale=scale)
        mixture_pdf += w * pdf

    plt.figure(figsize=(10, 6))
    plt.hist(df_alle['Picktijd (sec)'], bins=4000, density=True, alpha=0.5, label='Gecombineerde data')
    plt.plot(x, mixture_pdf, 'r-', label='Globaal mixture model', linewidth=2)
    plt.xlabel('Picktijd (sec)')
    plt.ylabel('Kansdichtheid')
    plt.title('Globale verdeling van picktijden via mixture model')
    plt.xlim(0, np.percentile(df_alle['Picktijd (sec)'], 99.5))
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("Images/histogram_met_mixture_model.png")
    plt.close()

    ########################### CDF berekening
    # === Stap 4: Bereken CDFs ===
    echte_data = np.sort(df['Picktijd (sec)'].values)
    simulaties = np.sort(simulaties)

    cdf_echt = np.arange(1, len(echte_data) + 1) / len(echte_data)
    cdf_sim = np.arange(1, len(simulaties) + 1) / len(simulaties)

    # === Stap 5: Plot ===
    plt.figure(figsize=(10, 6))
    plt.plot(echte_data, cdf_echt, label='Echte data (CDF)', linewidth=2)
    plt.plot(simulaties, cdf_sim, label='Simulatie (CDF)', linewidth=2, linestyle='--')
    plt.title('Vergelijking van CDFs: echte data vs simulatie')
    plt.xlabel('Picktijd (sec)')
    plt.ylabel('Cumulatieve kans')
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig("Images/cdf_vergelijking_echt_vs_simulatie.png")
    # === STAP 9: Samenvatting tonen ===
    debug_print("✅ K-S test tussen echte data en simulatie:")
    debug_print(f"   ➤ KS-statistic: {ks_resultaat.statistic:.4f}")
    debug_print(f"   ➤ p-waarde:     {ks_resultaat.pvalue:.4f}")
    debug_print(f"✅ Histogram verschil: {histogram_verschil:.4f}")
    debug_print("📊 Visualisaties opgeslagen als:")
    debug_print("   ➤ histogram_met_mixture_model.png")
    debug_print("   ➤ qqplot_simulatie_vs_normaal.png")
    debug_print("🎲 Voorbeeld gesimuleerde picktijden:", sample_globale_picktijd(5))
