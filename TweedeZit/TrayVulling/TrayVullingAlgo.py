import json
import numpy as np
from pathlib import Path
from math import ceil
import rectpack as rect
from rectpack import newPacker


def genereer_extra_itemcodes(bestelling_json_path: str, frequentie_json_path: str, percentage: float) -> list[str]:
    # 📥 Inlezen JSON-bestanden
    with open(bestelling_json_path, 'r', encoding='utf-8') as f:
        bestelling_data = json.load(f)

    with open(frequentie_json_path, 'r', encoding='utf-8') as f:
        frequentie_data = json.load(f)

    # 📊 Aantal bestaande itemcodes in bestelling_json tellen
    aantal_itemcodes = sum(len(bestelling) for bestelling in bestelling_data)
    extra_aantal = ceil(aantal_itemcodes * (percentage / 100)) + aantal_itemcodes


    # 🎯 Frequentieverdeling voorbereiden
    itemcodes = list(frequentie_data.keys())
    gewichten = np.array(list(frequentie_data.values()), dtype=float)
    kansen = gewichten / gewichten.sum()

    # 🎲 Extra itemcodes samplen
    extra_items = list(np.random.choice(itemcodes, size=extra_aantal, p=kansen))

    return extra_items


def maak_itemcode_dimensies_json(itemcodes_lijst, dimensie_json_pad, output_json_pad):
    # 📥 Laad dimensies
    with open(dimensie_json_pad, 'r') as f:
        dimensies_data = json.load(f)

    # 📦 Filter de afmetingen voor de gebruikte itemcodes
    gekoppeld = {}
    ontbrekend = []

    for code in itemcodes_lijst:
        if code in dimensies_data:
            gekoppeld[code] = dimensies_data[code]
        else:
            ontbrekend.append(code)

    # 🧾 Bewaar als nieuwe JSON
    with open(output_json_pad, 'w') as f_out:
        json.dump(gekoppeld, f_out, indent=2)

    print(f"✅ {len(gekoppeld)} itemcodes succesvol gelinkt aan afmetingen.")
    if ontbrekend:
        print(f"⚠️ {len(set(ontbrekend))} itemcodes hebben geen afmetingen en zijn overgeslagen.")
        print("Bijvoorbeeld:", list(set(ontbrekend))[:10])  # eerste 10 tonen


def vul_trays_met_items(item_dim_json: str, aantal_trays: int, tray_breedte: float, tray_diepte: float,
                        output_json: str):
    """
    Vult trays met items op basis van hun afmetingen en slaat het resultaat op in JSON-formaat.

    Parameters:
        item_dim_json (str): Pad naar JSON-bestand met itemcodes en (lengte, breedte).
        aantal_trays (int): Aantal beschikbare trays.
        tray_breedte (float): Breedte van een tray.
        tray_diepte (float): Diepte van een tray.
        output_json (str): Pad om resultaat op te slaan in JSON-formaat.
    """
    # 1. Laad itemafmetingen
    with open(item_dim_json, 'r') as f:
        item_dims = json.load(f)

    # 2. Initialiseer de packer
    packer = newPacker(rotation=True)  # rotatie toegestaan

    # 3. Voeg items toe
    padding = 0.02  # optionele marge
    for item_code, (l, w) in item_dims.items():
        packer.add_rect(l + padding, w + padding, rid=item_code)

    # 4. Voeg trays toe
    for _ in range(aantal_trays):
        packer.add_bin(tray_breedte, tray_diepte)

    # 5. Start packing
    packer.pack()

    # 6. Resultaat structureren
    trays = {}
    for rect in packer.rect_list():
        tray_index, x, y, l, w, item_code = rect
        trays.setdefault(f"Tray {tray_index + 1}", []).append({
            "item_code": item_code,
            "x": round(x, 3),
            "y": round(y, 3),
            "l": round(l - padding, 3),
            "w": round(w - padding, 3)
        })

    # 7. Niet-geplaatste items
    geplaatste_ids = set(r[5] for r in packer.rect_list())
    niet_geplaatst = [code for code in item_dims if code not in geplaatste_ids]

    resultaat = {
        "trays": trays,
        "niet_geplaatst": niet_geplaatst
    }

    # 8. Opslaan
    with open(output_json, 'w') as f:
        json.dump(resultaat, f, indent=2)

    print(f"✅ Resultaat opgeslagen in {output_json}")
    print(f"📦 Geplaatste trays: {len(trays)}")
    print(f"⚠️ Niet geplaatste items: {len(niet_geplaatst)}")


extra = genereer_extra_itemcodes("../Bestelling/CreatieBestellingLijst/BestellingJson", "../Bestelling/Preprocessing/Globale_Itemcode_frequentie.json", 20)
print("extra item zijn de volgende: ",extra)
maak_itemcode_dimensies_json(extra,"item_dims.json","Itemcodes_met_Afmetingen")
vul_trays_met_items("Itemcodes_met_Afmetingen", aantal_trays=10, tray_breedte=1.0, tray_diepte=1.0, output_json="tray_vulling.json")


