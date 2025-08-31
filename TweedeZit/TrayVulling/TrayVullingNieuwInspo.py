from __future__ import annotations

import json
import math
import numpy as np
from pathlib import Path

from rectpack import newPacker


# ============================================
# 0) Kleine helpers
# ============================================
def _norm(k):
    """Normaliseer itemcodes (bv. '13974.0' -> '13974')."""
    try:
        return str(int(float(k)))
    except:
        return str(k)

def _lees_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def _schrijf_json(p, data):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def _raw_naar_compact(raw: dict) -> dict:
    """Converteer raw-pack-output naar compact schema: {'trays': { 'Tray 1': [ {item_code,x,y,l,w}, ...] }}"""
    trays_compact = {}
    for tray_name, items in raw.get("trays", {}).items():
        out = []
        for it in items:
            x = it.get("x", 0.0)
            y = it.get("y", 0.0)
            # velden kunnen 'l_met_tussenruimte'/'w_met_tussenruimte' of 'l'/'w' heten
            l = it.get("l_met_tussenruimte") or it.get("l")
            w = it.get("w_met_tussenruimte") or it.get("w")
            out.append({
                "item_code": it["item_code"],
                "x": round(float(x), 4),
                "y": round(float(y), 4),
                "l": round(float(l), 4),
                "w": round(float(w), 4),
            })
        trays_compact[tray_name] = out
    return {"trays": trays_compact}

# ============================================================
# 1) ORKESTRATOR — alles-in-één tot vulling bereikt is
# ============================================================
def genereer_en_pack_tot_vulling(
    dimensie_json_pad: str,
    frequentie_json_pad: str,
    aantal_trays: int,
    tray_breedte: float,
    tray_diepte: float,
    vulpercentage: float,
    tussenruimte_pct: float,
    plaatsings_algo: str = "first_fit_freq",   # "binpack" | "first_fit" | "first_fit_freq"
    batch_grootte: int = 200,                  # hoeveel nieuwe itemcodes per iteratie
    max_batches: int = 60,                     # veiligheidslimiet
    marge_pctpunt: float = 1.0,                # sta bv. 1 procentpunt onder doel toe
    seed: int | None = None,
    subset_output_pad: str = "Itemcodes_met_Afmetingen",  # wordt weggeschreven (subset van dimensies)
    output_json: str = "tray_vulling.json"     # compacte eindoutput (x,y,l,w)
):
    """
    DOEL:
      - Genereer extra items batch-voor-batch (gewogen door frequenties),
      - Pack ze met jouw parameters,
      - Stop zodra iedere tray ≥ (vulpercentage - marge) effectief gevuld is,
      - Schrijf meteen compacte output naar `output_json`,
      - Retourneer ook de gebruikte EXTRA-lijst (handig voor logging / downstream).

    VEREIST:
      - Een bestaande functie `vul_trays_met_items(...)` in scope met signatuur:
        vul_trays_met_items(item_dim_json, aantal_trays, tray_breedte, tray_diepte,
                            output_json, vulpercentage, tussenruimte_pct,
                            plaatsings_algo, frequentie_json, compact_output)
      - Deze functie wordt hier met `compact_output=False` aangeroepen om het raw-rapport te kunnen meten.
    """
    if seed is not None:
        np.random.seed(seed)

    # ---------- [A] Data laden & normaliseren ----------
    dims_all = _lees_json(dimensie_json_pad)
    dims_all = { _norm(k): v for k, v in dims_all.items() }

    freq_all = _lees_json(frequentie_json_pad)
    freq_all = { _norm(k): float(v) for k, v in freq_all.items() }

    # bruikbare codes = codes die zowel frequentie als dimensies hebben
    bruikbare_codes = [c for c in freq_all.keys() if c in dims_all]
    if not bruikbare_codes:
        raise ValueError("Geen overlap tussen frequenties en dimensies.")

    gewichten = np.array([freq_all[c] for c in bruikbare_codes], dtype=float)
    if gewichten.sum() <= 0:
        raise ValueError("Frequentiegewichten zijn nul.")

    kansen = gewichten / gewichten.sum()

    # ---------- [B] Stopcriteria voorbereiden ----------
    s = math.sqrt(vulpercentage / 100.0)       # effectieve trayschaal
    tray_eff_w = tray_breedte * s
    tray_eff_h = tray_diepte  * s
    max_oppervlak_per_tray = tray_eff_w * tray_eff_h
    doel_per_tray = max_oppervlak_per_tray * (1.0 - marge_pctpunt/100.0)

    # ---------- [C] Iteratief batches samplen + packen ----------
    extra_set: set[str] = set()
    vorige_benutting = -1.0
    tmp_subset_pad = "__tmp_subset_dims__.json"
    tmp_raw_output = "__tmp_raw_out__.json"

    for batch_idx in range(1, max_batches + 1):
        # C1) sample een batch en voeg toe
        batch = list(np.random.choice(bruikbare_codes, size=batch_grootte, p=kansen))
        extra_set.update(batch)

        # C2) subset dims schrijven (alleen codes in extra_set)
        subset_dims = { c: dims_all[c] for c in extra_set }
        _schrijf_json(tmp_subset_pad, subset_dims)

        # C3) pack-run (raw rapport nodig om te meten)
        vul_trays_met_items(
            item_dim_json=tmp_subset_pad,
            aantal_trays=aantal_trays,
            tray_breedte=tray_breedte,
            tray_diepte=tray_diepte,
            output_json=tmp_raw_output,
            vulpercentage=vulpercentage,
            tussenruimte_pct=tussenruimte_pct,
            plaatsings_algo=plaatsings_algo,
            frequentie_json=frequentie_json_pad,
            compact_output=False
        )

        raw = _lees_json(tmp_raw_output)
        trays = raw.get("trays", {})

        # C4) meten — effectieve vulling per tray
        alle_ok = True
        totaal_oppervlakte = 0.0
        trays_count = 0

        for items in trays.values():
            trays_count += 1
            tray_area_eff = 0.0
            for it in items:
                l = it.get("l_met_tussenruimte") or it.get("l")
                w = it.get("w_met_tussenruimte") or it.get("w")
                tray_area_eff += float(l) * float(w)
            totaal_oppervlakte += tray_area_eff
            if tray_area_eff + 1e-12 < doel_per_tray:
                alle_ok = False

        # globale benutting (ter diagnose)
        if trays_count == 0:
            huidige_benutting = 0.0
        else:
            huidige_benutting = totaal_oppervlakte / (max_oppervlak_per_tray * trays_count)

        print(f"[Iter {batch_idx}] trays_ok={alle_ok} | benutting_gem={huidige_benutting*100:.2f}% | items={len(extra_set)}")

        # C5) stopcondities
        if alle_ok:
            # schrijf definitieve compacte output & subset-dims die je wil bewaren
            _schrijf_json(subset_output_pad, subset_dims)
            compact = _raw_naar_compact(raw)
            _schrijf_json(output_json, compact)
            print(f"✅ Doel bereikt. Output → {output_json} | Subset → {subset_output_pad}")
            return sorted(extra_set)

        if huidige_benutting <= vorige_benutting + 1e-9:
            # geen merkbare verbetering → voorkom eindeloze loop
            print("⚠️ Benutting stagneert; stoppen om eindeloze iteratie te voorkomen.")
            break

        vorige_benutting = huidige_benutting

    # ---------- [D] Fallback: schrijf best-effort resultaat ----------
    print("ℹ️ Doel niet volledig bereikt binnen limieten; schrijf best-effort resultaat.")
    # gebruik laatste raw + subset
    _schrijf_json(subset_output_pad, subset_dims)
    compact = _raw_naar_compact(raw)
    _schrijf_json(output_json, compact)
    return sorted(extra_set)

def vul_trays_met_items(
    item_dim_json: str,
    aantal_trays: int,
    tray_breedte: float,
    tray_diepte: float,
    output_json: str,
    vulpercentage: float = 100.0,
    tussenruimte_pct: float = 0.0,
    plaatsings_algo: str = "binpack",            # "binpack" | "first_fit" | "first_fit_freq"
    frequentie_json: str | None = None,
    compact_output: bool = True                  # ⬅️ direct jouw schema ("x","y","l","w")
):
    """
    Plaatst items in trays.
    - Vulpercentage via effectieve tray-schaal s = sqrt(p/100).
    - Tussenruimte via item-schaal g = 1 + (tussenruimte_pct/100).
    - Algoritmes: "binpack" (rectpack), "first_fit", "first_fit_freq" (frequenties sorteren).
    - Schrijft standaard direct compact schema weg als compact_output=True.
    """
    assert 0.0 < vulpercentage <= 100.0, "vulpercentage moet in (0, 100] liggen"
    assert tussenruimte_pct >= 0.0, "tussenruimte_pct moet ≥ 0 zijn"
    assert plaatsings_algo in {"binpack", "first_fit", "first_fit_freq"}

    # Items laden
    with open(item_dim_json, 'r', encoding='utf-8') as f:
        item_dims: dict[str, list[float]] = json.load(f)

    # Frequenties (optioneel)
    freq_map = {}
    if plaatsings_algo == "first_fit_freq":
        assert frequentie_json is not None, "frequentie_json is vereist voor 'first_fit_freq'"
        with open(frequentie_json, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        freq_map = { _norm(k): float(v) for k, v in raw.items() }

    # Parameters
    g = 1.0 + (tussenruimte_pct / 100.0)                 # item-schaal
    s = (vulpercentage / 100.0) ** 0.5                   # tray-schaal (oppervlak)
    tray_eff_w = tray_breedte * s
    tray_eff_h = tray_diepte  * s
    off_x = (tray_breedte - tray_eff_w) / 2.0
    off_y = (tray_diepte  - tray_eff_h)  / 2.0

    # Items → (code, w_eff, h_eff, w_orig, h_orig)
    def to_eff(code, dims):
        l, w = float(dims[0]), float(dims[1])  # jouw JSON: [lengte, breedte]
        return (code, l*g, w*g, l, w)

    items = [to_eff(_norm(c), dims) for c, dims in item_dims.items()]

    # Sorteer voor first_fit_freq (hoogste eerst)
    if plaatsings_algo == "first_fit_freq":
        items.sort(key=lambda t: freq_map.get(t[0], 0.0), reverse=True)

    trays = {}
    placed_area_eff = 0.0

    # ------------------------------
    # ALGO 1: BINPACK (rectpack)
    # ------------------------------
    if plaatsings_algo == "binpack":
        packer = newPacker(rotation=True)
        for code, w_eff, h_eff, _, _ in items:
            packer.add_rect(w_eff, h_eff, rid=code)
        for _ in range(aantal_trays):
            packer.add_bin(tray_eff_w, tray_eff_h)
        packer.pack()

        for tray_index, x, y, w_eff, h_eff, code in packer.rect_list():
            trays.setdefault(f"Tray {tray_index + 1}", []).append({
                "item_code": code,
                "x": round(x + off_x, 4),
                "y": round(y + off_y, 4),
                "l": round(w_eff, 4),   # l = breedte-as die we aan rectpack doorgeven
                "w": round(h_eff, 4),
            })
            placed_area_eff += w_eff * h_eff

        geplaatste_ids = set(r[5] for r in packer.rect_list())
        niet_geplaatst = [code for code, *_ in items if code not in geplaatste_ids]

    # -------------------------------------------
    # ALGO 2/3: FIRST FIT (shelf-based, rotatie)
    # -------------------------------------------
    else:
        def place_in_tray(tray, w_eff, h_eff):
            """Probeer (met rotatie) te plaatsen op eerste shelf die past."""
            candidates = [(w_eff, h_eff), (h_eff, w_eff)]
            # Huidige shelf of eerste shelf aanmaken
            if not tray["shelves"]:
                tray["shelves"].append({"y": 0.0, "height": None, "x_cursor": 0.0})

            for rw, rh in candidates:
                # probeer huidige shelf
                shelf = tray["shelves"][-1]
                # Init shelf height indien None
                if shelf["height"] is None:
                    shelf["height"] = rh
                # past in huidige shelf?
                if rh <= shelf["height"] and shelf["x_cursor"] + rw <= tray_eff_w and shelf["y"] + shelf["height"] <= tray_eff_h:
                    x = shelf["x_cursor"]; y = shelf["y"]
                    shelf["x_cursor"] += rw
                    return True, (x, y, rw, rh)
                # anders: nieuwe shelf starten
                new_y = shelf["y"] + (shelf["height"] or 0.0)
                if new_y + rh <= tray_eff_h:
                    new_shelf = {"y": new_y, "height": rh, "x_cursor": 0.0}
                    tray["shelves"].append(new_shelf)
                    x = 0.0; y = new_shelf["y"]
                    new_shelf["x_cursor"] += rw
                    return True, (x, y, rw, rh)

            return False, None

        trays_state = [{"shelves": []} for _ in range(aantal_trays)]
        placed_codes = set()
        for code, w_eff, h_eff, *_ in items:
            placed = False
            for idx, tray in enumerate(trays_state):
                ok, pos = place_in_tray(tray, w_eff, h_eff)
                if ok:
                    x, y, rw, rh = pos
                    trays.setdefault(f"Tray {idx + 1}", []).append({
                        "item_code": code,
                        "x": round(x + off_x, 4),
                        "y": round(y + off_y, 4),
                        "l": round(rw, 4),
                        "w": round(rh, 4),
                    })
                    placed_area_eff += rw * rh
                    placed_codes.add(code)
                    placed = True
                    break
            if not placed:
                pass
        niet_geplaatst = [code for code, *_ in items if code not in placed_codes]

    # Rapport (optioneel kun je uitprinten)
    totale_tray_oppervlakte = aantal_trays * tray_breedte * tray_diepte
    max_beschikbaar_oppervlak = aantal_trays * tray_eff_w * tray_eff_h
    benut_vs_max = (placed_area_eff / max_beschikbaar_oppervlak) * 100.0 if max_beschikbaar_oppervlak else 0.0
    benut_vs_orig = (placed_area_eff / totale_tray_oppervlakte) * 100.0 if totale_tray_oppervlakte else 0.0

    resultaat = {
        "trays": trays,
        "niet_geplaatst": niet_geplaatst,
        "rapport": {
            "algo": plaatsings_algo,
            "vulpercentage_doel": vulpercentage,
            "tussenruimte_pct": tussenruimte_pct,
            "effectieve_tray_breedte": round(tray_eff_w, 4),
            "effectieve_tray_diepte": round(tray_eff_h, 4),
            "benutting_tov_max_bij_doel_%": round(benut_vs_max, 2),
            "benutting_tov_originele_tray_%": round(benut_vs_orig, 2),
        }
    }

    # ⬇️ Schrijf direct compact of volledig rapport
    if compact_output:
        compact = {"trays": trays}
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(compact, f, indent=2)
    else:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(resultaat, f, indent=2)

    print(f"✅ {plaatsings_algo}: output → {output_json}")
    if niet_geplaatst:
        print(f"⚠️ Niet geplaatste items: {len(niet_geplaatst)}")

# ============================================================
# 2) MAIN — nog maar één call 👇
# ============================================================
if __name__ == "__main__":
    # INPUTS
    dims_path = "item_dims.json"   # bron met ALLE afmetingen
    freq_path = "../Bestelling/Preprocessing/Globale_Itemcode_frequentie.json"

    aantal_trays   = 10
    tray_breedte   = 1.0
    tray_diepte    = 1.0
    vulpercentage  = 50.0
    tussenruimte   = 10.0
    algo           = "first_fit_freq"  # "binpack" | "first_fit" | "first_fit_freq"

    # ÉÉN ORKESTRATIE-CALL: genereert, packt, schrijft compacte output & subset-dims
    extra = genereer_en_pack_tot_vulling(
        dimensie_json_pad=dims_path,
        frequentie_json_pad=freq_path,
        aantal_trays=aantal_trays,
        tray_breedte=tray_breedte,
        tray_diepte=tray_diepte,
        vulpercentage=vulpercentage,
        tussenruimte_pct=tussenruimte,
        plaatsings_algo=algo,
        batch_grootte=200,
        max_batches=60,
        marge_pctpunt=1.0,
        seed=None,
        subset_output_pad="Itemcodes_met_Afmetingen",  # subset met enkel gebruikte codes
        output_json="tray_vulling.json"                # jouw compacte eind-JSON
    )

    print(f"🎯 Aantal gebruikte EXTRA itemcodes: {len(extra)}")
