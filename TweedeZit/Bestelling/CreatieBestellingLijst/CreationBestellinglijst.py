import json

import numpy as np
from scipy.stats import nbinom
def bereken_itemkansen(json_pad):
    """
    Leest een JSON-bestand in met itemcodes en aantallen.
    Retourneert een dictionary met itemcode → kans (als float tussen 0 en 1).
    """
    with open(json_pad, 'r') as f:
        data = json.load(f)

    totaal = sum(data.values())
    if totaal == 0:
        raise ValueError("De som van alle waarden in het JSON-bestand is nul.")

    kansen = {item: freq / totaal for item, freq in data.items()}
    return kansen

def genereer_bestellingen(n_bestellingen: int, itemkansen: dict, r: float, p: float, uitvoerpad: str):
    """
    Genereert gesimuleerde bestellingen en slaat ze op als JSON.

    Parameters:
        n_bestellingen (int): Aantal bestellingen om te genereren.
        itemkansen (dict): Dictionary van itemcode → kans (totaal = 1.0).
        r (float): 'r' parameter voor de Negative Binomial verdeling.
        p (float): 'p' parameter voor de Negative Binomial verdeling.
        uitvoerpad (str): Pad naar het JSON-bestand waarin bestellingen opgeslagen worden.
    """
    itemcodes = list(itemkansen.keys())
    kansen = list(itemkansen.values())

    bestellingen = []
    for _ in range(n_bestellingen):
        aantal_items = nbinom.rvs(r, p) + 1  # NB start bij 0 ⇒ +1
        bestelling = list(np.random.choice(itemcodes, size=aantal_items, p=kansen))
        bestellingen.append(bestelling)

    with open(uitvoerpad, 'w') as f:
        json.dump(bestellingen, f, indent=4)

    print(f"✅ {n_bestellingen} bestellingen gegenereerd en opgeslagen in '{uitvoerpad}'")





kans_dict = bereken_itemkansen("../Preprocessing/Globale_Itemcode_frequentie.json")
genereer_bestellingen(100,kans_dict,0.6365,0.1340,"BestellingJson")

