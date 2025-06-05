import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import random
from pathlib import Path

from scipy import stats


SIMULATION_HOURS = 1
OVERFILL_PERCENTAGE = 0.2

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
    1) hourly_rates_per_file: gemiddelde orders per uur per bestand
    2) global_freq_series: totale frequentie per itemcode over alle bestanden
    3) file_freqs: dict per bestand van itemcode->frequentie
    """
    hourly_rates: list[float] = []
    file_freqs: dict[str, pd.Series] = {}

    for path_str in file_paths:
        path = Path(path_str)
        df = pd.read_excel(path, sheet_name=sheet_name)
        df.rename(columns=lambda c: c.strip(), inplace=True)

        # Bereken hourly rate
        start, end = df['Creation Dt'].min(), df['Creation Dt'].max()
        hours = (end - start).total_seconds() / 3600
        hourly_rates.append(len(df) / hours)

        # Frequentie per bestand
        fname = path.stem
        file_freqs[fname] = df['Item code'].value_counts()

    # Globale frequenties
    freq_df = pd.DataFrame(file_freqs).fillna(0).astype(int)
    freq_df['Total'] = freq_df.sum(axis=1)
    global_freq_series = freq_df['Total'].sort_values(ascending=False)

    return hourly_rates, global_freq_series, file_freqs

def simulate_period(
    start_date: datetime,
    hours: int,
    hourly_rates: list[float],
    freq_distribution: pd.Series,
    dist_name: str = 'global'
) -> dict[datetime, list[str]]:
    """
    Simuleert orders per uur:
    - start_date: datum waarop simulatie begint
    - hours: aantal uren te simuleren
    - hourly_rates: lijst van lambda-waarden
    - freq_distribution: pd.Series(index=item_code, value=gewichten)
    - dist_name: naam van de distributie

    Retourneert dict date -> list of itemcodes
    """
    codes = freq_distribution.index.tolist()
    weights = (freq_distribution / freq_distribution.sum()).tolist()

    sim_output: dict[datetime, list[str]] = {}
    print(f"Simulatie van {start_date.date()} over {hours} uren met '{dist_name}' distributie")

    for i in range(hours):
        current_date = start_date + timedelta(hours=i)
        lam = random.choice(hourly_rates)
        n_orders = np.random.poisson(lam)
        picks = random.choices(codes, weights=weights, k=n_orders)
        sim_output[current_date] = picks

    return sim_output


def get_hourly_topk(
    sim_output: dict[datetime, list[str]],
    k
) -> pd.DataFrame:
    """
    Maakt DataFrame met per uur de top-k meest opgehaalde items:
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
    Augmenteert elke uur met extra picks gebaseerd op bron en mode
    """
    augmented: dict[datetime, list[str]] = {}
    for date, picks in sim_output.items():
        extra_n = compute_extra_count(picks, mode, value)
        codes = code_lists[source_name]
        weights = weight_lists[source_name]
        extra_picks = random.choices(codes, weights=weights, k=extra_n)
        augmented[date] = picks + extra_picks
    return augmented

def genereer_nb_waarde(r, p):
    return stats.nbinom.rvs(r, p) +1;

# === Functie: Genereer waarde volgens Zero-Inflated Negatief Binomiaal ===
def genereer_zinb_waarde(pi,r, p):
    if np.random.rand() < pi:
        return 1
    else:
        return stats.nbinom.rvs(r, p) +1

def group_all_items_into_orders(sim_output: dict[datetime, list[str]], r: float, p: float) -> list[list[str]]:
    """
    Groepeert alle items uit de hele sim onafhankelijk van tijd in bestellingen,
    met aantallen bepaald door genereer_nb_waarde(r, p).
    Retourneert: lijst van bestellingen (elke bestelling is een lijst van itemcodes).
    """
    all_items = [item for items in sim_output.values() for item in items]
    i = 0
    grouped_orders = []
    while i < len(all_items):
        n_items = genereer_nb_waarde(r, p)
        order = all_items[i:i + n_items]
        grouped_orders.append(order)
        i += n_items
    return grouped_orders

def save_grouped_orders_flat(orders: list[list[str]], filename: str) -> None:
    records = [
        {"order_id": i+1, "items": ",".join(map(str, order))}
        for i, order in enumerate(orders)
    ]
    pd.DataFrame(records).to_csv(filename, index=False)

def get_inventory_and_orders():
    # bestandspaden = [
    #     '../Dataverwerking_data_Input/1_VerdelingItem01_03.xlsx',
    #     '../Dataverwerking_data_Input/2_VerdelingItem04_06.xlsx',
    #     '../Dataverwerking_data_Input/3_VerdelingItem07_09.xlsx',
    #     '../Dataverwerking_data_Input/4_VerdelingItem10_12.xlsx',
    #     '../Dataverwerking_data_Input/5_VerdelingItem13_15.xlsx',
    #     '../Dataverwerking_data_Input/6_VerdelingItem16_19.xlsx',
    # ]
    # Changed scope when calling from main script in root
    bestandspaden = [
        'Dataverwerking_code/Dataverwerking_data_Input/1_VerdelingItem01_03.xlsx',
        'Dataverwerking_code/Dataverwerking_data_Input/2_VerdelingItem04_06.xlsx',
        'Dataverwerking_code/Dataverwerking_data_Input/3_VerdelingItem07_09.xlsx',
        'Dataverwerking_code/Dataverwerking_data_Input/4_VerdelingItem10_12.xlsx',
        'Dataverwerking_code/Dataverwerking_data_Input/5_VerdelingItem13_15.xlsx',
        'Dataverwerking_code/Dataverwerking_data_Input/6_VerdelingItem16_19.xlsx',
    ]

    # 1) data inladen
    hourly_rates, global_freq, file_freqs = load_excel_data(bestandspaden)

    code_lists = {f: list(freq.index) for f, freq in file_freqs.items()}
    weight_lists = {f: (freq / freq.sum()).tolist() for f, freq in file_freqs.items()}
    code_lists['global'] = list(global_freq.index)
    weight_lists['global'] = (global_freq / global_freq.sum()).tolist()

    # 3) Kies distributie
    choice = "global"

    # 4) Simulatieduur
    start_date = datetime.fromisoformat("2025-06-01")
    hours = SIMULATION_HOURS

    # 5) Simuleer
    freq_dist = global_freq if choice == 'global' else file_freqs[choice]
    sim = simulate_period(start_date, hours, hourly_rates, freq_dist, dist_name=choice)

    # 6) Augmentatie vraag
    aug_answer = "ja"
    if aug_answer.lower().startswith('j'):
        # Augmentatie instellingen
        src_choice = "global"

        mode = "percent"

        if mode == 'fixed':
            value = float(input("Aantal extra items per uur (int): "))
        else:
            value = OVERFILL_PERCENTAGE

        aug_sim = augment_simulation(sim, code_lists, weight_lists, mode, value, src_choice)

    # 7) Opslaan
    # save_simulation(sim, 'Dataverwerking_code/Dataverwerking_data_output/sim_output.csv')
    # if aug_answer.lower().startswith('j'):
    #     save_simulation(aug_sim, 'Dataverwerking_code/Dataverwerking_data_output/augmented_output.csv')

    print("\nSimulatie voltooid. Resultaten opgeslagen.")

    # 8) Bestelling aanpassen op basis van
    with open("Dataverwerking_code/simulatie_parameters.json", "r") as f:
        parameters = json.load(f)

    # Extract de parameters
    r_nb = parameters["negative_binomial"]["r"]
    p_nb = parameters["negative_binomial"]["p"]
    # pi_opt = parameters["ZINB"]["pi"]
    # r_zinb = parameters["ZINB"]["r"]
    # p_zinb = parameters["ZINB"]["p"]

    # print("Parameters geladen:")
    # print("NB → r:", r_nb, "p:", p_nb)
    # print("ZINB → pi:", pi_opt, "r:", r_zinb, "p:", p_zinb)

    grouped_orders = group_all_items_into_orders(sim, r_nb, p_nb)
    # save_grouped_orders_flat(grouped_orders, 'Dataverwerking_data_output/grouped_orders.csv')


    return sim, aug_sim, grouped_orders

def main():
    get_inventory_and_orders()


# -------------------------
# Voorbeeld van gebruik
if __name__ == '__main__':
  main()