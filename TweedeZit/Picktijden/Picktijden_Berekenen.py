import json
import os
import pandas as pd
from datetime import datetime
import seaborn as sns
import numpy as np
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture
from scipy.stats import norm

from matplotlib import pyplot as plt


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

def InlezenJsonGegevens(pad, methode):
    df = lees_bestellingdensity_kolommen(pad)
    df = afronden_op_seconde(df, methode)  # afronden naar dichtbijzijnde
    exporteer_naar_json(df, "bestellingen.json")



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


pad = file_list = [
    '../Data/Input/1_VerdelingItem01_03.xlsx',
    '../Data/Input/2_VerdelingItem04_06.xlsx',
    '../Data/Input/3_VerdelingItem07_09.xlsx',
    '../Data/Input/4_VerdelingItem10_12.xlsx',
    '../Data/Input/5_VerdelingItem13_15.xlsx',
    '../Data/Input/6_VerdelingItem16_19.xlsx',
]

#InlezenJsonGegevens(pad,3)
#bereken_picktijden_uit_json("bestellingen.json", "test")
analyseer_picktijden_met_filter("test")
#gmm_model = selecteer_best_aantal_componenten("test", max_components=40)
#fit_en_plot_gmm_range("test","Picktijd (sec)",20, )

fit_en_plot_gmm("test",7, xlim_max=30)
gmm7 = fit_gmm_model("test", "Picktijd (sec)", 7)
samples = sample_from_gmm(gmm7, 10)
print("🕒 Gesimuleerde picktijden:", samples)