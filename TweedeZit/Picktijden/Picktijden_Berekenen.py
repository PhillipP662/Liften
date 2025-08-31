import json
import os
import pandas as pd
from datetime import datetime
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
from seaborn.external.kde import gaussian_kde
from sklearn.mixture import GaussianMixture
from scipy.stats import norm

from matplotlib import pyplot as plt
from sklearn.preprocessing import StandardScaler


def lees_bestellingdensity_kolommen(bestandspaden: list[str]) -> pd.DataFrame:
    """
    Leest opgegeven Excel-bestanden en selecteert 'Creation Dt',
    'Outbound order number' en 'Requester user code' uit de sheet 'BestellingDensity'.

    Parameters:
        bestandspaden (list[str]): Lijst met volledige paden naar Excel-bestanden.

    Returns:
        pd.DataFrame: Gecombineerde dataframe met geselecteerde kolommen.
    """
    alle_data = []

    for bestand_pad in bestandspaden:
        try:
            df = pd.read_excel(
                bestand_pad,
                sheet_name="BestellingDensity",
                usecols=["Creation Dt", "Outbound order number", "Requester user code"]
            )
            df["Bronbestand"] = os.path.basename(bestand_pad)
            alle_data.append(df)
        except Exception as e:
            print(f"⚠️ Fout bij inlezen van {bestand_pad}: {e}")

    if alle_data:
        samengevoegd = pd.concat(alle_data, ignore_index=True)
        print(f"✅ In totaal {len(samengevoegd)} rijen ingelezen uit {len(alle_data)} bestanden.")
        return samengevoegd
    else:
        print("❌ Geen geldige bestanden gevonden.")
        return pd.DataFrame()

def afronden_op_seconde(df: pd.DataFrame, methode: int = 1) -> pd.DataFrame:
    """
    Rondt de 'Creation Dt'-kolom af op seconden.

    Parameters:
        df (pd.DataFrame): DataFrame met kolom 'Creation Dt'
        methode (int):
            1 = naar beneden (floor)
            2 = naar boven (ceil)
            3 = naar dichtstbijzijnde seconde (round)

    Returns:
        pd.DataFrame: DataFrame met aangepaste 'Creation Dt'
    """
    df_kopie = df.copy()
    df_kopie['Creation Dt'] = pd.to_datetime(df_kopie['Creation Dt'], errors='coerce')

    if methode == 1:
        df_kopie['Creation Dt'] = df_kopie['Creation Dt'].dt.floor('s')
    elif methode == 2:
        df_kopie['Creation Dt'] = df_kopie['Creation Dt'].dt.ceil('s')
    elif methode == 3:
        df_kopie['Creation Dt'] = df_kopie['Creation Dt'].dt.round('s')
    else:
        raise ValueError("❌ Ongeldige methode. Gebruik 1 (floor), 2 (ceil) of 3 (round).")

    return df_kopie



def exporteer_naar_json(df: pd.DataFrame, uitvoerpad: str):
    """
    Exporteert de dataframe naar een JSON-bestand als een lijst van dicts.
    Neemt kolommen: 'Creation Dt', 'Outbound order number', 'Requester user code', 'Bronbestand'.

    Parameters:
        df (pd.DataFrame): DataFrame met de vereiste kolommen.
        uitvoerpad (str): Pad naar het JSON-bestand om op te slaan.
    """
    # Maak kopie en converteer 'Creation Dt' naar string
    df_kopie = df.copy()
    df_kopie['Creation Dt'] = pd.to_datetime(df_kopie['Creation Dt'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

    # Controleer of vereiste kolommen aanwezig zijn
    vereiste_kolommen = ['Creation Dt', 'Outbound order number', 'Requester user code', 'Bronbestand']
    for kol in vereiste_kolommen:
        if kol not in df_kopie.columns:
            raise ValueError(f"Kolom '{kol}' ontbreekt in de dataframe.")

    # Zet om naar lijst van dicts
    records = df_kopie[vereiste_kolommen].to_dict(orient='records')

    # Schrijf naar JSON
    with open(uitvoerpad, 'w') as f:
        json.dump(records, f, indent=4)

    print(f"✅ JSON-bestand opgeslagen in: {uitvoerpad}")

def InlezenJsonGegevens(pad, methode,exportpad):
    df = lees_bestellingdensity_kolommen(pad)
    df = afronden_op_seconde(df, methode)  # afronden naar dichtbijzijnde
    exporteer_naar_json(df, exportpad)



def bereken_picktijden_uit_json(json_pad: str, output_csv: str):
    # 📥 JSON inlezen
    with open(json_pad, 'r') as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    df['Creation Dt'] = pd.to_datetime(df['Creation Dt'])

    resultaten = []

    # 👷‍♀️ Verwerk per gebruiker
    for user_id, groep in df.groupby('Requester user code'):
        groep = groep.sort_values('Creation Dt').reset_index(drop=True)

        cluster = []
        vorige_order = groep.loc[0, 'Outbound order number']
        vorige_tijd = groep.loc[0, 'Creation Dt']

        for i in range(len(groep)):
            huidig_order = groep.loc[i, 'Outbound order number']
            huidig_tijd = groep.loc[i, 'Creation Dt']

            if huidig_order == vorige_order:
                cluster.append(groep.loc[i])
            else:
                # nieuwe bestelling → tijdsverschil berekenen
                tijdsverschil = (huidig_tijd - vorige_tijd).total_seconds()
                if tijdsverschil > 0 and len(cluster) > 0:
                    tijd_per_item = tijdsverschil / len(cluster)
                    for rij in cluster:
                        rij_dict = rij.to_dict()
                        rij_dict['Picktijd (sec)'] = tijd_per_item
                        resultaten.append(rij_dict)
                # ⛔ cluster negeren als tijdsverschil ≤ 0 of leeg

                cluster = [groep.loc[i]]
                vorige_order = huidig_order
                vorige_tijd = huidig_tijd

        # ❗ Laatste cluster: geen tijdsverschil bekend → overslaan
        pass  # bewust niets toevoegen

    resultaat_df = pd.DataFrame(resultaten)
    resultaat_df.to_csv(output_csv, index=False)
    print(f"✅ Resultaat opgeslagen in: {os.path.abspath(output_csv)}")
    return resultaat_df

def analyseer_picktijden_met_filter(csv_pad: str):


    df = pd.read_csv(csv_pad)
    df = df[pd.to_numeric(df['Picktijd (sec)'], errors='coerce').notnull()]
    picktijden = df['Picktijd (sec)'].astype(float)

    # 📉 IQR-filter
    q1 = picktijden.quantile(0.25)
    q3 = picktijden.quantile(0.75)
    iqr = q3 - q1
    ondergrens = q1 - 1.5 * iqr
    bovengrens = q3 + 1.5 * iqr

    filtered = picktijden[(picktijden >= ondergrens) & (picktijden <= bovengrens)]

    gemiddelde = filtered.mean()
    variantie = filtered.var(ddof=1)

    print(f"📌 Gemiddelde picktijd (na IQR-filtering): {gemiddelde:.2f} sec")
    print(f"📌 Variantie picktijd: {variantie:.2f} sec²")
    print(f"🔢 Gefilterde data: {len(filtered)} van {len(picktijden)} rijen ({len(filtered)/len(picktijden)*100:.1f}%)")

    # 📊 Plot
    plt.figure(figsize=(10, 6))
    sns.histplot(filtered, bins=150, kde=True, stat='density', color='lightgreen', edgecolor='black')
    plt.title("Picktijdverdeling na IQR-filtering")
    plt.xlabel("Picktijd (sec)")
    plt.ylabel("Dichtheid")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("Picktijden.png")
    plt.show()


def fit_en_plot_gmm(csv_pad: str, n_components: int = 3, xlim_max: float = 30):
    # 📥 Laad data
    df = pd.read_csv(csv_pad)
    picktijden = df["Picktijd (sec)"].dropna().values

    # 📉 IQR-filter
    q1 = np.percentile(picktijden, 25)
    q3 = np.percentile(picktijden, 75)
    iqr = q3 - q1
    ondergrens = q1 - 1.5 * iqr
    bovengrens = q3 + 1.5 * iqr
    gefilterd = picktijden[(picktijden >= ondergrens) & (picktijden <= bovengrens)].reshape(-1, 1)

    # 🤖 Fit GMM
    gmm = GaussianMixture(n_components=n_components, random_state=0)
    gmm.fit(gefilterd)

    # 🔍 Print parameters
    print("🎯 GMM parameters:")
    for i in range(n_components):
        gewicht = gmm.weights_[i]
        mean = gmm.means_[i][0]
        std = np.sqrt(gmm.covariances_[i][0][0])
        print(f"  Component {i + 1}: weight = {gewicht:.2f}, mean = {mean:.2f}, std = {std:.2f}")

    # 📈 Plot histogram + GMM fit
    x = np.linspace(0, np.percentile(gefilterd, 99.5), 1000).reshape(-1, 1)
    logprob = gmm.score_samples(x)
    pdf = np.exp(logprob)

    plt.figure(figsize=(10, 6))
    plt.hist(gefilterd, bins=120, density=True, alpha=0.5, color='green', label='Gefilterde data')

    for i in range(n_components):
        mean = gmm.means_[i][0]
        std = np.sqrt(gmm.covariances_[i][0][0])
        plt.plot(x, gmm.weights_[i] * norm.pdf(x, mean, std), '--', label=f'Component {i + 1}')

    plt.plot(x, pdf, color='black', linewidth=2, label='Totale GMM')
    plt.title("GMM Fit op Gefilterde Picktijden")
    plt.xlabel("Picktijd (sec)")
    plt.ylabel("Dichtheid")
    plt.xlim(0, xlim_max)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("GMM_fit_picktijden.png")
    plt.show()

def selecteer_best_aantal_componenten(csv_pad: str, max_components: int = 10):
    # 📥 Laad en filter data
    df = pd.read_csv(csv_pad)
    picktijden = df["Picktijd (sec)"].dropna().values

    # IQR-filter
    q1, q3 = np.percentile(picktijden, [25, 75])
    iqr = q3 - q1
    filtered = picktijden[(picktijden >= q1 - 1.5 * iqr) & (picktijden <= q3 + 1.5 * iqr)].reshape(-1, 1)

    # 📈 Bereken AIC en BIC voor elk aantal componenten
    aics = []
    bics = []
    modellen = []

    for k in range(1, max_components + 1):
        gmm = GaussianMixture(n_components=k, random_state=0)
        gmm.fit(filtered)
        aics.append(gmm.aic(filtered))
        bics.append(gmm.bic(filtered))
        modellen.append(gmm)

    # 🎯 Bepaal de beste
    best_k_aic = np.argmin(aics) + 1
    best_k_bic = np.argmin(bics) + 1

    # 📊 Plot AIC en BIC
    plt.figure(figsize=(8, 5))
    plt.plot(range(1, max_components + 1), aics, label='AIC', marker='o')
    plt.plot(range(1, max_components + 1), bics, label='BIC', marker='o')
    plt.axvline(best_k_aic, color='green', linestyle='--', label=f'Beste AIC: {best_k_aic}')
    plt.axvline(best_k_bic, color='red', linestyle='--', label=f'Beste BIC: {best_k_bic}')
    plt.xlabel('Aantal componenten (clusters)')
    plt.ylabel('Score')
    plt.title('Modelselectie via AIC en BIC')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("beste_aantal_componenten.png")
    plt.show()

    print(f"✅ Beste volgens AIC: {best_k_aic} componenten")
    print(f"✅ Beste volgens BIC: {best_k_bic} componenten")
    return modellen[best_k_bic - 1]  # Of kies modellen[best_k_aic - 1] als je AIC vertrouwt


def fit_en_plot_gmm_range(csv_pad: str, kolom: str, max_components: int = 20, output_dir: str = "GMM_Visualisaties"):
    # 📥 Data inlezen
    df = pd.read_csv(csv_pad)
    picktijden = df[kolom].dropna().values

    # 📉 IQR-filter
    q1, q3 = np.percentile(picktijden, [25, 75])
    iqr = q3 - q1
    filtered = picktijden[(picktijden >= q1 - 1.5 * iqr) & (picktijden <= q3 + 1.5 * iqr)].reshape(-1, 1)

    # 📁 Map maken voor output
    os.makedirs(output_dir, exist_ok=True)

    # 📊 Voor elke aantal componenten
    for n_components in range(1, max_components + 1):
        gmm = GaussianMixture(n_components=n_components, random_state=0)
        gmm.fit(filtered)

        x = np.linspace(0, np.percentile(filtered, 99.5), 1000).reshape(-1, 1)
        logprob = gmm.score_samples(x)
        pdf = np.exp(logprob)

        plt.figure(figsize=(10, 6))
        plt.hist(filtered, bins=100, density=True, alpha=0.4, color='gray', label='Gegevens')

        for i in range(n_components):
            mean = gmm.means_[i][0]
            std = np.sqrt(gmm.covariances_[i][0][0])
            weight = gmm.weights_[i]
            plt.plot(x, weight * norm.pdf(x, mean, std), '--', label=f'Component {i + 1}')

        plt.plot(x, pdf, color='black', linewidth=2, label='Totale GMM')
        plt.title(f"GMM met {n_components} componenten")
        plt.xlabel("Picktijd (sec)")
        plt.ylabel("Dichtheid")
        plt.xlim(0, 30)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

        plot_naam = os.path.join(output_dir, f"GMM_{n_components}_componenten.png")
        plt.savefig(plot_naam)
        plt.close()
        print(f"✅ Plot opgeslagen: {plot_naam}")

def fit_gmm_model(csv_pad: str, kolom: str, n_components: int) -> GaussianMixture:
    df = pd.read_csv(csv_pad)
    data = df[kolom].dropna().values

    # IQR-filter
    q1, q3 = np.percentile(data, [25, 75])
    iqr = q3 - q1
    filtered = data[(data >= q1 - 1.5 * iqr) & (data <= q3 + 1.5 * iqr)].reshape(-1, 1)

    gmm = GaussianMixture(n_components=n_components, random_state=0)
    gmm.fit(filtered)

    print(f"✅ GMM getraind met {n_components} componenten.")
    return gmm


def sample_from_gmm(gmm_model: GaussianMixture, n: int) -> np.ndarray:
    n_components = gmm_model.n_components
    weights = gmm_model.weights_
    means = gmm_model.means_.flatten()
    stds = np.sqrt(gmm_model.covariances_.flatten())

    componenten = np.random.choice(n_components, size=n, p=weights)

    samples = np.random.normal(loc=means[componenten], scale=stds[componenten])
    return samples

# ---------- 1) Data laden + globaal IQR-filter ----------
def load_filtered_picktijden(csv_pad: str, kolom: str = "Picktijd (sec)"):
    df = pd.read_csv(csv_pad)
    df = df[['Requester user code', kolom]].dropna()
    df[kolom] = pd.to_numeric(df[kolom], errors='coerce')
    df = df.dropna(subset=[kolom])

    t = df[kolom].values.astype(float)
    q1, q3 = np.percentile(t, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    m = (t >= lo) & (t <= hi)

    out = df.loc[m].rename(columns={kolom: 't'}).reset_index(drop=True)
    kept_pct = 100 * m.mean()
    print(f"✅ IQR-filter toegepast: {out.shape[0]} / {df.shape[0]} ({kept_pct:.1f}%) bewaard")
    return out

# ---------- 2) Kenmerken per picker ----------
def build_picker_features(filtered_df: pd.DataFrame, min_n: int = 150):
    d = filtered_df.copy()
    d['logt'] = np.log1p(d['t'])

    agg = d.groupby('Requester user code').agg(
        n=('t', 'count'),
        median=('t', 'median'),
        mean=('t', 'mean'),
        std=('t', 'std'),
        q1=('t', lambda s: s.quantile(0.25)),
        q3=('t', lambda s: s.quantile(0.75)),
        frac_fast2=('t', lambda s: (s <= 2).mean()),
        mu_log=('logt', 'mean'),
        sd_log=('logt', 'std'),
    ).reset_index()
    agg['iqr'] = agg['q3'] - agg['q1']

    feats = agg[agg['n'] >= min_n].reset_index(drop=True)
    print(f"👥 Pickers met voldoende data (≥{min_n}): {len(feats)}")
    return feats

# ---------- 3) Clustering van pickers (BIC-gestuurd) ----------
def cluster_pickers(features_df: pd.DataFrame,
                    k_min: int = 1, k_max: int = 6,
                    feature_cols=('mu_log', 'sd_log', 'frac_fast2'),
                    random_state: int = 42):

    X = features_df[list(feature_cols)].values
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)

    bics, models = [], []
    for k in range(k_min, k_max + 1):
        gmm = GaussianMixture(n_components=k, covariance_type='full',
                              random_state=random_state, n_init=10, max_iter=500)
        gmm.fit(Xs)
        bics.append(gmm.bic(Xs))
        models.append(gmm)

    best_idx = int(np.argmin(bics))
    best_k = k_min + best_idx
    best_model = models[best_idx]
    labels = best_model.predict(Xs)

    out = features_df.copy()
    out['cluster'] = labels

    bic_table = pd.DataFrame({'k': list(range(k_min, k_max + 1)), 'BIC': bics})
    print("📉 BIC per k:\n", bic_table)
    print(f"🏆 Gekozen aantal clusters (laagste BIC): k = {best_k}")
    return out, best_model, bic_table

# ---------- 4) Plots: dichtheden per cluster + total ----------
def plot_cluster_kdes(filtered_df: pd.DataFrame,
                      assignments_df: pd.DataFrame,
                      xlim_max: float = 30):

    df = filtered_df.merge(assignments_df[['Requester user code', 'cluster']],
                           on='Requester user code', how='inner')
    xs = np.linspace(0, np.percentile(df['t'], 99.5), 600)

    # Totale KDE
    kde_total = gaussian_kde(df['t'])
    plt.figure(figsize=(10, 6))
    plt.plot(xs, kde_total(xs), label='Totaal (KDE)', linewidth=2)

    # KDE per cluster (geaggregeerd over pickers)
    for c in sorted(df['cluster'].unique()):
        t_c = df.loc[df['cluster'] == c, 't'].values
        if len(t_c) < 50:  # te weinig punten → sla KDE over
            continue
        kde_c = gaussian_kde(t_c)
        plt.plot(xs, kde_c(xs), label=f'Cluster {c} (n={len(t_c)})')

    plt.title("Dichtheden per cluster vs totaal")
    plt.xlabel("Picktijd (sec)")
    plt.ylabel("Dichtheid")
    plt.xlim(0, xlim_max)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def print_cluster_summary(filtered_df: pd.DataFrame, assignments_df: pd.DataFrame):
    df = filtered_df.merge(assignments_df[['Requester user code', 'cluster']],
                           on='Requester user code', how='inner')
    s = df.groupby('cluster')['t'].agg(['count','median','mean','std',
                                        lambda x: x.quantile(0.25),
                                        lambda x: x.quantile(0.75)]).reset_index()
    s.columns = ['cluster','n','median','mean','std','q1','q3']
    s['iqr'] = s['q3'] - s['q1']

    pickers_per_cluster = assignments_df.groupby('cluster')['Requester user code'].nunique().reset_index()
    pickers_per_cluster.columns = ['cluster','n_pickers']

    out = s.merge(pickers_per_cluster, on='cluster')
    print("\n📊 Samenvatting per cluster:")
    print(out.sort_values('cluster').to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    return out

def plot_cluster_kdes(filtered_df: pd.DataFrame,
                      assignments_df: pd.DataFrame,
                      xlim_max: float = 30):
    df = filtered_df.merge(assignments_df[['Requester user code', 'cluster']],
                           on='Requester user code', how='inner')
    xs = np.linspace(0, np.percentile(df['t'], 99.5), 600)

    # Totale KDE
    kde_total = gaussian_kde(df['t'])
    plt.figure(figsize=(10, 6))
    plt.plot(xs, kde_total(xs), label='Totaal (KDE)', linewidth=2)

    # KDE per cluster (geaggregeerd over pickers)
    for c in sorted(df['cluster'].unique()):
        t_c = df.loc[df['cluster'] == c, 't'].values
        if len(t_c) < 50:  # te weinig punten → sla KDE over
            continue
        kde_c = gaussian_kde(t_c)
        plt.plot(xs, kde_c(xs), label=f'Cluster {c} (n={len(t_c)})')

    plt.title("Dichtheden per cluster vs totaal")
    plt.xlabel("Picktijd (sec)")
    plt.ylabel("Dichtheid")
    plt.xlim(0, xlim_max)
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def _read_filtered(csv_path, col="Picktijd (sec)"):
    if not csv_path.endswith(".csv"):
        csv_path += ".csv"
    df = pd.read_csv(csv_path, usecols=["Requester user code", col]).dropna()
    t = pd.to_numeric(df[col], errors="coerce").dropna().values.astype(float)

    # IQR filter (zoals eerder)
    q1, q3 = np.percentile(t, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5*iqr, q3 + 1.5*iqr
    keep = (t >= lo) & (t <= hi)
    t_f = t[keep]
    print(f"IQR keep: {t_f.size}/{t.size} = {100*t_f.size/t.size:.1f}%")
    return t_f

def _fit_gmm_bic(x, kmax=10):
    X = x.reshape(-1,1)
    bics, models = [], []
    for k in range(1, kmax+1):
        gmm = GaussianMixture(n_components=k, covariance_type="full",
                              random_state=42, n_init=5, max_iter=500)
        gmm.fit(X)
        bics.append(gmm.bic(X))
        models.append(gmm)
    idx = int(np.argmin(bics))
    print("BIC per k:", [(i+1, round(b,2)) for i,b in enumerate(bics)])
    print(f"Beste k (laagste BIC): {idx+1}")
    return models[idx], idx+1, bics

def plot_empirical_vs_simulated(csv_path="test", col="Picktijd (sec)",
                                kmax=10, use_log=True, xlim_max=30, bins=120,
                                out_png="gmm_emp_vs_sim.png"):
    # 1) Data
    t = _read_filtered(csv_path, col)

    # 2) Fit (optioneel op log-schaal)
    if use_log:
        y = np.log1p(t)                    # y = log(1+t)
        gmm, k, bics = _fit_gmm_bic(y, kmax)
        # 3) Simulatie uit GMM en terugtransformeren
        y_sim, _ = gmm.sample(len(t))
        t_sim = np.expm1(y_sim.ravel())
        # 4) Theoretische PDF op x-grid met jacobian
        xgrid = np.linspace(0, np.percentile(t, 99.5), 1200)
        ygrid = np.log1p(xgrid)
        logpdf_y = gmm.score_samples(ygrid.reshape(-1,1))
        pdf_x = np.exp(logpdf_y) / (1.0 + xgrid)  # chain rule
    else:
        gmm, k, bics = _fit_gmm_bic(t, kmax)
        xgrid = np.linspace(0, np.percentile(t, 99.5), 1200)
        t_sim, _ = gmm.sample(len(t))
        t_sim = t_sim.ravel()
        logpdf = gmm.score_samples(xgrid.reshape(-1,1))
        pdf_x = np.exp(logpdf)

    # 5) Plot: empirisch vs simulatie + theoretische PDF
    plt.figure(figsize=(11,6))
    plt.hist(t, bins=bins, density=True, alpha=0.45, label="Empirisch (gefilterd)")
    plt.hist(t_sim, bins=bins, density=True, alpha=0.35, label="Gesimuleerd uit GMM")
    plt.plot(xgrid, pdf_x, label=f"Theoretische GMM-PDF (k={k})", linewidth=2)
    plt.xlabel("Picktijd (sec)")
    plt.ylabel("Dichtheid")
    plt.xlim(0, xlim_max)
    plt.title("Empirisch vs Gesimuleerd vs Theoretische GMM-fit")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    plt.show()
    print(f"Plot opgeslagen als '{out_png}'")

    # 6) Snelle goodness-of-fit (empirisch vs simulatie)
    #   (KS tussen twee samples — indicatief)
    from scipy.stats import ks_2samp
    ks_stat, ks_p = ks_2samp(t, t_sim)
    print(f"KS(empirisch vs simulatie): stat={ks_stat:.4f}, p={ks_p:.4f}")

def cluster_pickers_fixed_k(features_df, k=3,
                            feature_cols=('mu_log','sd_log','frac_fast2'),
                            random_state=42):
    X = features_df[list(feature_cols)].values
    Xs = StandardScaler().fit_transform(X)
    gmm = GaussianMixture(n_components=k, covariance_type='full',
                          random_state=random_state, n_init=10, max_iter=500)
    labels = gmm.fit_predict(Xs)
    out = features_df.copy()
    out['cluster'] = labels
    return out, gmm

def fit_gmm_fixed_k(t, k=3, use_log=True):
    if use_log:
        y = np.log1p(t).reshape(-1,1)
        gmm = GaussianMixture(n_components=k, covariance_type="full",
                              random_state=42, n_init=10, max_iter=500, reg_covar=1e-4)
        gmm.fit(y)
        # PDF op x-grid met jacobian
        xgrid = np.linspace(0, np.percentile(t, 99.5), 1200)
        ygrid = np.log1p(xgrid).reshape(-1,1)
        pdf_x = np.exp(gmm.score_samples(ygrid)) / (1.0 + xgrid)
        # simulatie
        y_sim, _ = gmm.sample(len(t))
        t_sim = np.expm1(y_sim.ravel())
        return xgrid, pdf_x, t_sim, gmm
    else:
        X = t.reshape(-1,1)
        gmm = GaussianMixture(n_components=k, covariance_type="full",
                              random_state=42, n_init=10, max_iter=500, reg_covar=1e-4)
        gmm.fit(X)
        xgrid = np.linspace(0, np.percentile(t, 99.5), 1200).reshape(-1,1)
        pdf_x = np.exp(gmm.score_samples(xgrid))
        t_sim, _ = gmm.sample(len(t)); t_sim = t_sim.ravel()
        return xgrid.ravel(), pdf_x, t_sim, gmm

def plot_emp_vs_gmm_k3(csv_path="test.csv", col="Picktijd (sec)", xlim_max=30, bins=120, out_png="gmm_k3_emp_vs_sim.png"):
    df = pd.read_csv(csv_path, usecols=[col]).dropna()
    t_all = pd.to_numeric(df[col], errors="coerce").dropna().values.astype(float)
    # IQR-filter zoals eerder
    q1,q3 = np.percentile(t_all,[25,75]); iqr=q3-q1; lo,hi=q1-1.5*iqr, q3+1.5*iqr
    t = t_all[(t_all>=lo)&(t_all<=hi)]

    xgrid, pdf_x, t_sim, _ = fit_gmm_fixed_k(t, k=3, use_log=True)

    plt.figure(figsize=(11,6))
    plt.hist(t, bins=bins, density=True, alpha=0.45, label="Empirisch (gefilterd)")
    plt.hist(t_sim, bins=bins, density=True, alpha=0.35, label="Gesimuleerd uit GMM (k=3)")
    plt.plot(xgrid, pdf_x, linewidth=2, label="Theoretische GMM-PDF (k=3)")
    plt.xlim(0, xlim_max); plt.xlabel("Picktijd (sec)"); plt.ylabel("Dichtheid")
    plt.title("Empirisch vs Gesimuleerd vs GMM-fit (k=3, parsimonieus)")
    plt.legend(); plt.grid(True); plt.tight_layout()
    plt.savefig(out_png, dpi=200); plt.show()
    print(f"Plot opgeslagen als '{out_png}'")

def fit_cluster_lognorms(df_filt, assignments):
    """Fit per cluster een lognormaal op y=log(1+t). Returnt parameters en gewichten."""
    df = df_filt.merge(assignments[['Requester user code','cluster']], on='Requester user code', how='inner')
    params = []
    weights = []
    for c in sorted(df['cluster'].unique()):
        tc = df.loc[df['cluster']==c, 't'].values.astype(float)
        y = np.log1p(tc)
        mu, sigma = float(y.mean()), float(y.std(ddof=1))
        params.append((mu, sigma))
        weights.append(len(tc))
    weights = np.array(weights, dtype=float)
    weights /= weights.sum()
    return params, weights

def sample_from_cluster_mixture(n, params, weights, rng=None):
    """Simuleer: kies cluster ~ weights; sample y ~ N(mu,sigma); zet terug t=exp(y)-1."""
    rng = np.random.default_rng(rng)
    comps = rng.choice(len(weights), size=n, p=weights)
    ys = rng.normal(loc=np.array([params[k][0] for k in comps]),
                    scale=np.array([params[k][1] for k in comps]))
    ts = np.expm1(ys)
    return ts

def plot_emp_vs_cluster_mixture(df_filt, assignments, xlim_max=30, bins=120, out_png="mix3_emp_vs_sim.png"):
    params, weights = fit_cluster_lognorms(df_filt, assignments)
    t = df_filt['t'].values.astype(float)
    t_sim = sample_from_cluster_mixture(len(t), params, weights, rng=42)

    # Theoretische 3-componenten PDF via kettingregel
    xgrid = np.linspace(0, np.percentile(t, 99.5), 1200)
    ygrid = np.log1p(xgrid)
    pdf = np.zeros_like(xgrid)
    for (mu, sigma), w in zip(params, weights):
        pdf_y = norm.pdf(ygrid, loc=mu, scale=sigma)
        pdf += w * (pdf_y / (1.0 + xgrid))  # d/dx log(1+x) = 1/(1+x)

    plt.figure(figsize=(11,6))
    plt.hist(t, bins=bins, density=True, alpha=0.45, label="Empirisch (gefilterd)")
    plt.hist(t_sim, bins=bins, density=True, alpha=0.35, label="Gesimuleerd uit 3-klassen-mengsel")
    plt.plot(xgrid, pdf, linewidth=2, label="Theoretische 3-klassen-PDF (picker-clusters)")
    plt.xlim(0, xlim_max); plt.xlabel("Picktijd (sec)"); plt.ylabel("Dichtheid")
    plt.title("Empirisch vs Gesimuleerd vs 3-klassen (picker) mengsel")
    plt.legend(); plt.grid(True); plt.tight_layout()
    plt.savefig(out_png, dpi=200); plt.show()
    print(f"Plot opgeslagen als '{out_png}'")

if __name__ == "__main__":
    pad = file_list = [
        '../Data/Input/1_VerdelingItem01_03.xlsx',
        '../Data/Input/2_VerdelingItem04_06.xlsx',
        '../Data/Input/3_VerdelingItem07_09.xlsx',
        '../Data/Input/4_VerdelingItem10_12.xlsx',
        '../Data/Input/5_VerdelingItem13_15.xlsx',
        '../Data/Input/6_VerdelingItem16_19.xlsx',
    ]

    InlezenJsonGegevens(pad,3,"bestellingen.json")
    bereken_picktijden_uit_json("bestellingen.json", "test.csv")
    analyseer_picktijden_met_filter("test.csv")
    # #gmm_model = selecteer_best_aantal_componenten("test", max_components=40)
    # #fit_en_plot_gmm_range("test","Picktijd (sec)",20, )
    #
    # fit_en_plot_gmm("test",7, xlim_max=30)
    # gmm7 = fit_gmm_model("test", "Picktijd (sec)", 7)
    # samples = sample_from_gmm(gmm7, 10)
    # print("🕒 Gesimuleerde picktijden:", samples)

    min_obs_per_picker = 150  # drempel voor robuuste picker-features

    # 1) Data filteren (IQR)
    df_filt = load_filtered_picktijden("test.csv", kolom="Picktijd (sec)")

    # 2) Picker-features bouwen en clusteren (BIC kiest k, we forceren evt. k=3)
    feats = build_picker_features(df_filt, min_n=min_obs_per_picker)
    assignments, model, bic_table = cluster_pickers(
        feats,
        k_min=1, k_max=6,
        feature_cols=('mu_log', 'sd_log', 'frac_fast2'),
        random_state=42
    )
    if assignments['cluster'].nunique() != 3:
        print(f"BIC koos k={assignments['cluster'].nunique()} → we refitten met k=3 voor de verklarende plot.")
        assignments, _ = cluster_pickers_fixed_k(
            feats, k=3,
            feature_cols=('mu_log', 'sd_log', 'frac_fast2'),
            random_state=42
        )

    # 3) Plot A: Empirisch vs gesimuleerd vs theoretische 3-klassen (picker-clusters)
    #     (maakt en bewaart: 'mix3_emp_vs_sim.png')
    plot_emp_vs_cluster_mixture(df_filt, assignments,
                                xlim_max=30, bins=120,
                                out_png="mix3_emp_vs_sim.png")

    # 4) Plot B: Empirisch vs gesimuleerd vs GMM-fit (k=3, parsimonieus; geen picker-info)
    #     (maakt en bewaart: 'gmm_k3_emp_vs_sim.png')
    plot_emp_vs_gmm_k3(csv_path="test.csv",
                       col="Picktijd (sec)",
                       xlim_max=30, bins=120,
                       out_png="gmm_k3_emp_vs_sim.png")

    print("✅ Klaar: 'mix3_emp_vs_sim.png' en 'gmm_k3_emp_vs_sim.png' aangemaakt.")