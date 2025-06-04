from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import random
from pathlib import Path



def save_simulation(sim_data: dict[datetime, list[str]], filename: str) -> None:
    """
    Schrijft simulatieresultaten weg naar CSV.
    - sim_data: dict van datum naar lijst itemcodes
    - filename: outputbestand (CSV)
    """
    records = [
        {"date": date, "item_code": code}
        for date, codes in sim_data.items()
        for code in codes
    ]
    pd.DataFrame(records).to_csv(filename, index=False)


def load_excel_data(file_paths: list[str], sheet_name: str = 'BestellingDensity') -> tuple[list[float], pd.Series, dict[str, pd.Series]]:
    """
    Leest Excel-bestanden in en berekent:
    1) daily_rates_per_file: gemiddelde orders per dag per bestand
    2) global_freq_series: totale frequentie per itemcode over alle bestanden
    3) file_freqs: dict per bestand van itemcode->frequentie
    """
    daily_rates: list[float] = []
    file_freqs: dict[str, pd.Series] = {}

    for path_str in file_paths:
        path = Path(path_str)
        df = pd.read_excel(path, sheet_name=sheet_name)
        df.rename(columns=lambda c: c.strip(), inplace=True)

        # Bereken daily rate
        start, end = df['Creation Dt'].min(), df['Creation Dt'].max()
        days = (end - start).total_seconds() / 86400
        daily_rates.append(len(df) / days)

        # Frequentie per bestand
        fname = path.stem
        file_freqs[fname] = df['Item code'].value_counts()

    # Globale frequenties
    freq_df = pd.DataFrame(file_freqs).fillna(0).astype(int)
    freq_df['Total'] = freq_df.sum(axis=1)
    global_freq_series = freq_df['Total'].sort_values(ascending=False)

    return daily_rates, global_freq_series, file_freqs

def simulate_period(
    start_date: datetime,
    days: int,
    daily_rates: list[float],
    freq_distribution: pd.Series,
    dist_name: str = 'global'
) -> dict[datetime, list[str]]:
    """
    Simuleert orders per dag:
    - start_date: datum waarop simulatie begint
    - days: aantal dagen te simuleren
    - daily_rates: lijst van lambda-waarden
    - freq_distribution: pd.Series(index=item_code, value=gewichten)
    - dist_name: naam van de distributie

    Retourneert dict date -> list of itemcodes
    """
    codes = freq_distribution.index.tolist()
    weights = (freq_distribution / freq_distribution.sum()).tolist()

    sim_output: dict[datetime, list[str]] = {}
    print(f"Simulatie van {start_date.date()} over {days} dagen met '{dist_name}' distributie")

    for i in range(days):
        current_date = start_date + timedelta(days=i)
        lam = random.choice(daily_rates)
        n_orders = np.random.poisson(lam)
        picks = random.choices(codes, weights=weights, k=n_orders)
        sim_output[current_date] = picks

    return sim_output


def get_daily_topk(
    sim_output: dict[datetime, list[str]],
    k
) -> pd.DataFrame:
    """
    Maakt DataFrame met per dag de top-k meest opgehaalde items:
    - Kolommen: item_1, freq_1, ..., item_k, freq_k, total
    - Index: datum
    """
    records = []
    for date, picks in sim_output.items():
        vc = pd.Series(picks).value_counts().nlargest(k)
        row = {'date': date, 'total': len(picks)}
        for idx, (item, count) in enumerate(vc.items(), start=1):
            row[f'item_{idx}'] = item
            row[f'freq_{idx}'] = count
        records.append(row)

    return pd.DataFrame(records).set_index('date')

def compute_extra_count(picks: list[str], mode: str = 'percent', value: float = 10) -> int:
    if mode == 'fixed':
        return int(value)
    if mode == 'percent':
        return int(len(picks) * value)
    raise ValueError("mode must be 'fixed' or 'percent'")


def augment_simulation(
    sim_output: dict[datetime, list[str]],
    code_lists: dict[str, list[str]],
    weight_lists: dict[str, list[float]],
    mode: str,
    value: float,
    source_name: str
) -> dict[datetime, list[str]]:
    """
    Augmenteert elke dag met extra picks gebaseerd op bron en mode
    """
    augmented: dict[datetime, list[str]] = {}
    for date, picks in sim_output.items():
        extra_n = compute_extra_count(picks, mode, value)
        codes = code_lists[source_name]
        weights = weight_lists[source_name]
        extra_picks = random.choices(codes, weights=weights, k=extra_n)
        augmented[date] = picks + extra_picks
    return augmented



# -------------------------
# Voorbeeld van gebruik
if __name__ == '__main__':
    bestandspaden = [
        'Dataverwerking_data_Input/1_VerdelingItem01_03.xlsx',
        'Dataverwerking_data_Input/2_VerdelingItem04_06.xlsx',
        'Dataverwerking_data_Input/3_VerdelingItem07_09.xlsx',
        'Dataverwerking_data_Input/4_VerdelingItem10_12.xlsx',
        'Dataverwerking_data_Input/5_VerdelingItem13_15.xlsx',
        'Dataverwerking_data_Input/6_VerdelingItem16_19.xlsx',
    ]



    # 1) data inladen
    daily_rates, global_freq, file_freqs = load_excel_data(bestandspaden)

    code_lists = {f: list(freq.index) for f, freq in file_freqs.items()}
    weight_lists = {f: (freq / freq.sum()).tolist() for f, freq in file_freqs.items()}
    code_lists['global'] = list(global_freq.index)
    weight_lists['global'] = (global_freq / global_freq.sum()).tolist()

    print("Beschikbare verdelingen:")
    print("- global (alle bestanden)")
    for f, freq in file_freqs.items():
        top5 = freq.nlargest(5)
        print(f"- {f}: {list(top5.items())}")

    # 3) Kies distributie
    choice = input("Kies een distributie (bestand-stamnaam of 'global'): ")
    while choice not in code_lists:
        choice = input("Ongeldige keuze. Kies opnieuw: ")

    # 4) Simulatieduur
    start_str = input("Startdatum (YYYY-MM-DD): ")
    start_date = datetime.fromisoformat(start_str)
    days = int(input("Aantal dagen voor simulatie: "))

    # 5) Simuleer
    freq_dist = global_freq if choice == 'global' else file_freqs[choice]
    sim = simulate_period(start_date, days, daily_rates, freq_dist, dist_name=choice)
    topk_df = get_daily_topk(sim,days)
    print("\n=== Dagelijkse top-5 na simulatie ===")
    print(topk_df.head(days))

    # 6) Augmentatie vraag
    aug_answer = input("Wil je de data augmenteren? (ja/nee): ")
    if aug_answer.lower().startswith('j'):
        # Augmentatie instellingen
        print("Beschikbare bronnen voor augmentatie:")
        for src in code_lists.keys():
            print(f"- {src}")
        src_choice = input("Kies bron (bestand-stamnaam of 'global'): ")
        while src_choice not in code_lists:
            src_choice = input("Ongeldige keuze. Kies opnieuw: ")

        mode = input("Mode voor extra items ('fixed' of 'percent'): ")
        while mode not in ['fixed', 'percent']:
            mode = input("Ongeldige mode. Kies 'fixed' of 'percent': ")

        if mode == 'fixed':
            value = float(input("Aantal extra items per dag (int): "))
        else:
            value = float(input("Percentage extra items (bv. 0.2 voor 20%): "))

        aug_sim = augment_simulation(sim, code_lists, weight_lists, mode, value, src_choice)
        aug_topk_df = get_daily_topk(aug_sim,days)
        print("\n=== Dagelijkse top-5 na augmentatie ===")
        print(aug_topk_df.head(days))
    else:
        print("Geen augmentatie toegepast.")

    # 7) Opslaan
    save_simulation(sim, 'sim_output.csv')
    if aug_answer.lower().startswith('j'):
        save_simulation(aug_sim, 'augmented_output.csv')

    print("\nSimulatie voltooid. Resultaten opgeslagen.")
