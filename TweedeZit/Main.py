# main.py – hoofdscript

# ✅ Bestelling - CreatieBestellingLijst
from Bestelling.CreatieBestellingLijst.CreationBestellinglijst import (
    bereken_itemkansen,
    genereer_bestellingen
)

# ✅ Bestelling - GroteBestelling
from Bestelling.GroteBestelling.VerdelingGroteBestelling import (
    NBVerdeling,
    nb_fit_report
)

# ✅ Bestelling - Preprocessing
from Bestelling.Preprocessing.GlobalFreqList import (
    compute_global_item_quantities
)

# ✅ Picktijden
from Picktijden.Picktijden_Berekenen import (
    InlezenJsonGegevens,
    bereken_picktijden_uit_json,
    analyseer_picktijden_met_filter,
    fit_gmm_model,
    sample_from_gmm
)

# ✅ Trayvulling
from TrayVulling.TrayVullingAlgo import (
    genereer_extra_itemcodes,
    maak_itemcode_dimensies_json,
    vul_trays_met_items
)

# === MAIN EXECUTIE ===
if __name__ == "__main__":

    # ✳️ Globale frequentie berekenen
    file_list = [
        'Data/Input/1_VerdelingItem01_03.xlsx',
        'Data/Input/2_VerdelingItem04_06.xlsx',
        'Data/Input/3_VerdelingItem07_09.xlsx',
        'Data/Input/4_VerdelingItem10_12.xlsx',
        'Data/Input/5_VerdelingItem13_15.xlsx',
        'Data/Input/6_VerdelingItem16_19.xlsx',
    ]
    compute_global_item_quantities(file_list, "BestellingDensity", "Data/Output/Globale_Itemcode_frequentie.json")

    # ✳️ Fitting van NB-verdeling
    data = NBVerdeling(2)
    r, b = nb_fit_report(data)

    # # ✳️ Bestellingen genereren
    kansen = bereken_itemkansen("Data/Output/Globale_Itemcode_frequentie.json")
    genereer_bestellingen(100, kansen, r, b, "Data/Output/GegenereerdeBestellingen.json")

    # # ✳️ Trayvulling
    extra = genereer_extra_itemcodes(
        "Data/Output/GegenereerdeBestellingen.json",
        "Data/Output/Globale_Itemcode_frequentie.json",
        20
    )
    print("🧩 Extra gegenereerde items:", extra)
    maak_itemcode_dimensies_json(extra, "Data/Input/item_dims.json", "Data/Output/Itemcodes_met_Afmetingen")
    vul_trays_met_items(
        "Data/Output/Itemcodes_met_Afmetingen",
        aantal_trays=10,
        tray_breedte=1.0,
        tray_diepte=1.0,
        output_json="Data/Output/tray_vulling.json"
    )

    #
    # ✳️ Picktijdenanalyse
    InlezenJsonGegevens(file_list,3,"Data/Output/bestellingen.json")
    bereken_picktijden_uit_json("Data/Output/bestellingen.json", "Data/Output/Pikcktijden.json")
    analyseer_picktijden_met_filter("Data/Output/Pikcktijden.json")
    gmm7 = fit_gmm_model("Data/Output/Pikcktijden.json", "Picktijd (sec)", 7)
    samples = sample_from_gmm(gmm7, 10)
    print("🎲 Gesamplede picktijden:", samples)

