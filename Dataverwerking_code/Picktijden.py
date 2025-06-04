import os

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy import stats
from scipy.stats import lognorm, probplot, ks_2samp


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

def sample_globale_picktijd(n=1):
        picktijden = []
        users = np.arange(len(verdelingen))
        gekozen = np.random.choice(users, size=n, p=gewichten)
        for i in gekozen:
            shape, loc, scale = verdelingen[i]
            sample = lognorm.rvs(shape, loc=loc, scale=scale)
            picktijden.append(sample)
        return picktijden


if __name__ == "__main__":

    pad = 'PicktijdenBerekening_IQR'
    alle_df = []

    print("📁 Bestanden gevonden in map:")
    print(os.listdir(pad))

    for bestand in os.listdir(pad):
        if bestand.endswith('_picktijden_IQR.csv'):
            df = pd.read_csv(os.path.join(pad, bestand))
            alle_df.append(df)

    df_alle = pd.concat(alle_df, ignore_index=True)
    print("Aantal rijen samengevoegd:", len(df_alle))

    # Sla gecombineerd bestand op
    output_path = os.path.join('TussenTijdseBerekening', 'AllePicktijdenSamengevoegd.csv')
    df_alle.to_csv(output_path, index=False)
    print("✅ Samengevoegd bestand opgeslagen in:", os.path.abspath(output_path))

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
    print(f"✅ {len(verdelingen)} gebruikers succesvol gefit.")



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
    print("✅ K-S test tussen echte data en simulatie:")
    print(f"   ➤ KS-statistic: {ks_resultaat.statistic:.4f}")
    print(f"   ➤ p-waarde:     {ks_resultaat.pvalue:.4f}")
    print(f"✅ Histogram verschil: {histogram_verschil:.4f}")
    print("📊 Visualisaties opgeslagen als:")
    print("   ➤ histogram_met_mixture_model.png")
    print("   ➤ qqplot_simulatie_vs_normaal.png")
    print("🎲 Voorbeeld gesimuleerde picktijden:", sample_globale_picktijd(5))



 # bestandspaden = [
    #     'ExcelData/1_VerdelingItem01_03.xlsx',
    #     'ExcelData/2_VerdelingItem04_06.xlsx',
    #     'ExcelData/3_VerdelingItem07_09.xlsx',
    #     'ExcelData/4_VerdelingItem10_12.xlsx',
    #     'ExcelData/5_VerdelingItem13_15.xlsx',
    #     'ExcelData/6_VerdelingItem16_19.xlsx',
    # ]
    #
    # # Stap 1: afronden op seconde en scheiden van data per werker
    # alle_data_per_excel_per_werker  = {}
    #
    # for pad in bestandspaden:
    #     bestand_naam = os.path.basename(pad)
    #     df = pd.read_excel(pad, sheet_name='Picktijden')
    #     df['Creation Dt'] = pd.to_datetime(df['Creation Dt'], errors='coerce')
    #     df['Creation Dt'] = afronden_op_seconde(df['Creation Dt'])
    #
    #     if bestand_naam not in alle_data_per_excel_per_werker:
    #         alle_data_per_excel_per_werker[bestand_naam] = {}
    #
    #     for user_code, group in df.groupby('Requester user code'):
    #         if user_code not in alle_data_per_excel_per_werker[bestand_naam]:
    #             alle_data_per_excel_per_werker[bestand_naam][user_code] = []
    #         tijden = group['Creation Dt'].sort_values().tolist()
    #         alle_data_per_excel_per_werker[bestand_naam][user_code].extend(tijden)
    #
    # # Voorbeeld: print de eerste 3 tijden van werker 2 uit het eerste bestand
    # voorbeeld = alle_data_per_excel_per_werker['1_VerdelingItem01_03.xlsx'].get(2, [])[:3]
    # print("Eerste 3 picktijden van werker 2 uit 1_VerdelingItem01_03.xlsx:")
    # print(voorbeeld)
    #
    # os.makedirs('PicktijdenBerekening', exist_ok=True)
    #
    # for bestand_naam, data_per_werker in alle_data_per_excel_per_werker.items():
    #     resultaten = []
    #     for user_code, tijdstempels in data_per_werker.items():
    #         picktijden = bereken_picktijden(tijdstempels)
    #         for tijd in picktijden:
    #             resultaten.append({
    #                 'Requester user code': user_code,
    #                 'Picktijd (sec)': tijd
    #             })
    #     resultaat_df = pd.DataFrame(resultaten)
    #     csv_path = f'PicktijdenBerekening/{bestand_naam.replace(".xlsx", "")}_picktijden.csv'
    #     resultaat_df.to_csv(csv_path, index=False)
    #     print(f"{bestand_naam} picktijden opgeslagen in {csv_path}")

    #############################################################"
    #Indivuduele tijden de halen en IQR filtering
    # pad_in = 'PicktijdenBerekening'
    # pad_uit = 'PicktijdenBerekening_IQR'
    # os.makedirs(pad_uit, exist_ok=True)
    #
    # gemiddeldes_per_user = []
    # gemiddeldes_per_bestand = []
    #
    # # Verwerk elk bestand
    # for bestand in os.listdir(pad_in):
    #     if bestand.endswith('_picktijden.csv'):
    #         csv_path = os.path.join(pad_in, bestand)
    #         df = pd.read_csv(csv_path)
    #
    #         # IQR-filter
    #         df_clean = filter_op_iqr(df)
    #
    #         # Opslaan gefilterde data
    #         naam_basis = bestand.replace('_picktijden.csv', '')
    #         df_clean.to_csv(os.path.join(pad_uit, f'{naam_basis}_picktijden_IQR.csv'), index=False)
    #
    #         # Gemiddelde per user
    #         per_user = df_clean.groupby('Requester user code')['Picktijd (sec)'].mean().reset_index()
    #         per_user['Bestand'] = naam_basis
    #         gemiddeldes_per_user.append(per_user)
    #
    #         # Gemiddelde per bestand
    #         gemiddeld = df_clean['Picktijd (sec)'].mean()
    #         gemiddeldes_per_bestand.append({
    #             'Bestand': naam_basis,
    #             'Gemiddelde picktijd na IQR (sec)': gemiddeld
    #         })
    #
    # # Combineer resultaten per user
    # df_per_user = pd.concat(gemiddeldes_per_user, ignore_index=True)
    # df_per_user = df_per_user[['Bestand', 'Requester user code', 'Picktijd (sec)']]
    # df_per_user.rename(columns={'Picktijd (sec)': 'Gemiddelde picktijd na IQR (sec)'}, inplace=True)
    # df_per_user.to_csv('GemiddeldePicktijden_per_user_IQR.csv', index=False)
    #
    # # Opslaan gemiddeldes per bestand
    # df_per_bestand = pd.DataFrame(gemiddeldes_per_bestand)
    # df_per_bestand.to_csv('GemiddeldePicktijden_per_bestand_IQR.csv', index=False)
    #
    # # Globaal gemiddelde
    # globaal_gemiddelde = df_per_bestand['Gemiddelde picktijd na IQR (sec)'].mean()
    # print("✅ Gefilterde picktijden opgeslagen in 'PicktijdenBerekening_IQR/'")
    # print("✅ Gemiddelde per user opgeslagen in 'GemiddeldePicktijden_per_user_IQR.csv'")
    # print("✅ Gemiddelde per bestand opgeslagen in 'GemiddeldePicktijden_per_bestand_IQR.csv'")
    # print(f"🌍 Globale gemiddelde picktijd na IQR-filtering: {globaal_gemiddelde:.2f} sec")
