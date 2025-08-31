from __future__ import annotations

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

    def vul_trays_met_items(
            item_dim_json: str,
            aantal_trays: int,
            tray_breedte: float,
            tray_diepte: float,
            output_json: str,
            vulpercentage: float = 100.0,
            tussenruimte_pct: float = 0.0,
            plaatsings_algo: str = "binpack",  # "binpack" | "first_fit" | "first_fit_freq"
            frequentie_json: str | None = None  # verplicht bij "first_fit_freq"
    ):
        """
        Plaatst items in trays met keuze uit 3 algoritmes:
          - "binpack": rectpack (beste 2D-packing, rotation=True)
          - "first_fit": shelf-based, items in gegeven volgorde
          - "first_fit_freq": shelf-based, items gesorteerd op afnemende frequentie (uit frequentie_json)

        Tussenruimte: items worden vergroot met factor (1 + tussenruimte_pct/100).
        Vulpercentage: effectieve tray-afmetingen geschaald met s = sqrt(vulpercentage/100).
        """
        import json
        from math import sqrt
        from rectpack import newPacker

        assert 0.0 < vulpercentage <= 100.0, "vulpercentage moet in (0, 100] liggen"
        assert tussenruimte_pct >= 0.0, "tussenruimte_pct moet ≥ 0 zijn"
        assert plaatsings_algo in {"binpack", "first_fit", "first_fit_freq"}

        # --- Load items ---
        with open(item_dim_json, 'r', encoding='utf-8') as f:
            item_dims: dict[str, list[float]] = json.load(f)

        # --- Load freq if needed ---
        freq_map = {}
        if plaatsings_algo == "first_fit_freq":
            assert frequentie_json is not None, "frequentie_json is vereist voor 'first_fit_freq'"
            with open(frequentie_json, 'r', encoding='utf-8') as f:
                raw = json.load(f)

            # normaliseer keys (bv. "13974.0" → "13974")
            def _norm(k):
                try:
                    return str(int(float(k)))
                except:
                    return str(k)

            freq_map = {_norm(k): float(v) for k, v in raw.items()}

        # --- Parameters ---
        g = 1.0 + (tussenruimte_pct / 100.0)  # item-schaal (witruimte)
        s = (vulpercentage / 100.0) ** 0.5  # tray-schaal (oppervlak)
        tray_eff_w = tray_breedte * s
        tray_eff_h = tray_diepte * s
        off_x = (tray_breedte - tray_eff_w) / 2.0
        off_y = (tray_diepte - tray_eff_h) / 2.0

        # --- Maak lijst met (code, l_eff, w_eff, l_orig, w_orig) ---
        def to_eff(code, dims):
            l, w = float(dims[0]), float(dims[1])
            return (code, l * g, w * g, l, w)

        items = [to_eff(c, dims) for c, dims in item_dims.items()]

        # Sorteer voor first_fit_freq
        if plaatsings_algo == "first_fit_freq":
            def f(c):  # hogere freq eerst; onbekend = 0
                return freq_map.get(c, 0.0)

            items.sort(key=lambda t: f(t[0]), reverse=True)

        # ------------------------------
        #  ALGO 1: BINPACK (rectpack)
        # ------------------------------
        if plaatsings_algo == "binpack":
            packer = newPacker(rotation=True)
            for code, l_eff, w_eff, _, _ in items:
                packer.add_rect(l_eff, w_eff, rid=code)
            for _ in range(aantal_trays):
                packer.add_bin(tray_eff_w, tray_eff_h)
            packer.pack()

            trays = {}
            placed_area_eff = 0.0
            for tray_index, x, y, l_eff, w_eff, code in packer.rect_list():
                # herleid originele maten
                l_orig = l_eff / g
                w_orig = w_eff / g
                trays.setdefault(f"Tray {tray_index + 1}", []).append({
                    "item_code": code,
                    "x": round(x + off_x, 4),
                    "y": round(y + off_y, 4),
                    "l_met_tussenruimte": round(l_eff, 4),
                    "w_met_tussenruimte": round(w_eff, 4),
                    "l_orig": round(l_orig, 4),
                    "w_orig": round(w_orig, 4),
                })
                placed_area_eff += l_eff * w_eff

            geplaatste_ids = set(r[5] for r in packer.rect_list())
            niet_geplaatst = [code for code in item_dims if code not in geplaatste_ids]

        # -------------------------------------------
        #  ALGO 2/3: FIRST FIT (shelf-based, rotation)
        # -------------------------------------------
        else:
            # Eenvoudig "shelf-packing": plaats items links→rechts tot geen ruimte; start dan nieuwe rij (shelf).
            # First-Fit: per item loop je trays af en stop je in de eerste waar het past (evt. met rotatie).
            def place_in_tray(tray, item):
                """Probeer item in tray te plaatsen; return (ok, (x,y,l_eff,w_eff))"""
                _, l_eff, w_eff, _, _ = item

                # probeer beste rotatie op basis van passen
                candidates = [(l_eff, w_eff), (w_eff, l_eff)]  # met rotatie
                for (rw, rh) in candidates:
                    # probeer huidige rij
                    shelf = tray["shelves"][-1] if tray["shelves"] else None
                    if shelf is None:
                        # start eerste rij
                        shelf = {"y": 0.0, "height": rh, "x_cursor": 0.0}
                        tray["shelves"].append(shelf)

                    # als item hoger is dan rij-hoogte, kan je rij-hoogte verhogen als nog binnen tray
                    # maar klassiek shelf-packing houdt rij-hoogte constant → start nieuwe rij indien te laag
                    # we houden 'klassiek': nieuwe rij indien rh > shelf["height"]
                    def fits_in_current_shelf():
                        if rh > shelf["height"]:
                            return False
                        if shelf["x_cursor"] + rw <= tray_eff_w:
                            return True
                        return False

                    # check: past in huidige rij?
                    if fits_in_current_shelf():
                        x = shelf["x_cursor"];
                        y = shelf["y"]
                        if y + shelf["height"] <= tray_eff_h:
                            shelf["x_cursor"] += rw
                            return True, (x, y, rw, rh)

                    # start nieuwe rij
                    new_y = (tray["shelves"][-1]["y"] + tray["shelves"][-1]["height"]) if tray["shelves"] else 0.0
                    if new_y + rh <= tray_eff_h:
                        shelf = {"y": new_y, "height": rh, "x_cursor": 0.0}
                        tray["shelves"].append(shelf)
                        if shelf["x_cursor"] + rw <= tray_eff_w:
                            x = shelf["x_cursor"];
                            y = shelf["y"]
                            shelf["x_cursor"] += rw
                            return True, (x, y, rw, rh)

                return False, None

            # Init trays
            trays_state = [{"shelves": []} for _ in range(aantal_trays)]
            trays = {}
            placed_area_eff = 0.0
            placed_codes = set()

            for item in items:
                code, l_eff, w_eff, l_orig, w_orig = item
                placed = False
                for idx, tray in enumerate(trays_state):
                    ok, pos = place_in_tray(tray, item)
                    if ok:
                        x, y, rw, rh = pos
                        trays.setdefault(f"Tray {idx + 1}", []).append({
                            "item_code": code,
                            "x": round(x + off_x, 4),
                            "y": round(y + off_y, 4),
                            "l_met_tussenruimte": round(rw, 4),
                            "w_met_tussenruimte": round(rh, 4),
                            "l_orig": round(l_orig, 4),
                            "w_orig": round(w_orig, 4),
                        })
                        placed_area_eff += rw * rh
                        placed_codes.add(code)
                        placed = True
                        break
                if not placed:
                    # geen tray kon dit item plaatsen
                    pass

            niet_geplaatst = [code for code in item_dims if code not in placed_codes]

        # --- Rapport ---
        totale_tray_oppervlakte = aantal_trays * tray_breedte * tray_diepte
        max_beschikbaar_oppervlak = aantal_trays * tray_eff_w * tray_eff_h
        benut_vs_max = (placed_area_eff / max_beschikbaar_oppervlak) * 100.0 if max_beschikbaar_oppervlak else 0.0
        benut_vs_orig = (placed_area_eff / totale_tray_oppervlakte) * 100.0 if totale_tray_oppervlakte else 0.0

        resultaat = {
            "trays": trays,
            "niet_geplaatst": niet_geplaatst,
            "rapport": {
                "algo": plaatsings_algo,
                "tray_breedte": tray_breedte,
                "tray_diepte": tray_diepte,
                "vulpercentage_doel": vulpercentage,
                "tussenruimte_pct": tussenruimte_pct,
                "effectieve_tray_breedte": round(tray_eff_w, 4),
                "effectieve_tray_diepte": round(tray_eff_h, 4),
                "geplaatste_oppervlakte_met_tussenruimte": round(placed_area_eff, 4),
                "max_beschikbaar_oppervlak_bij_doel": round(max_beschikbaar_oppervlak, 4),
                "benutting_tov_max_bij_doel_%": round(benut_vs_max, 2),
                "benutting_tov_originele_tray_%": round(benut_vs_orig, 2),
                "aantal_trays_met_items": len([k for k, v in (trays or {}).items() if v]),
                "totaal_trays": aantal_trays
            }
        }

        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(resultaat, f, indent=2)

        print(f"✅ {plaatsings_algo} → resultaat opgeslagen in {output_json}")
        print(f"📦 Niet geplaatste items: {len(niet_geplaatst)}")


if __name__ == "__main__":
    extra = genereer_extra_itemcodes("../Bestelling/CreatieBestellingLijst/BestellingJson", "../Bestelling/Preprocessing/Globale_Itemcode_frequentie.json", 20)
    print("extra item zijn de volgende: ",extra)
    maak_itemcode_dimensies_json(extra,"item_dims.json","Itemcodes_met_Afmetingen")
    vul_trays_met_items("Itemcodes_met_Afmetingen", aantal_trays=10, tray_breedte=1.0, tray_diepte=1.0, output_json="tray_vulling.json")


