import math

import pandas as pd
from pathlib import Path
import json

def load_item_dimensions(
    excel_path: str,
    sheet_name: str = None,
    default_dimensions: tuple[float, float] = (0.1, 0.1)
) -> dict[str, tuple[float, float]]:
    """
    Laadt uit een Excel-bestand de afmetingen per Item code.

    Parameters:
    - excel_path: pad naar het Excel-bestand
    - sheet_name: optioneel, naam van de sheet. Als None, wordt de eerste sheet gebruikt.
    - default_dimensions: tuple met standaardwaarden voor (BRANDBOX_L, BRANDBOX_W)

    Returns:
    - dict van item_code -> (BRANDBOX_L, BRANDBOX_W)
    """
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"Bestand niet gevonden: {excel_path}")

    # Lees Excel
    if sheet_name is None:
        # Geen sheet opgegeven: lees eerste sheet
        df = pd.read_excel(path)
    else:
        df = pd.read_excel(path, sheet_name=sheet_name)

    # Controleer of we een DataFrame hebben
    if not isinstance(df, pd.DataFrame):
        raise ValueError(f"Lezen van Excel gaf geen DataFrame maar {type(df)}. Geef een geldige sheet_name of controleer het bestand.")

    needed = ['Item code', 'BRANDBOX_L', 'BRANDBOX_W']
    for col in needed:
        if col not in df.columns:
            raise KeyError(f"Kolom '{col}' niet gevonden in {excel_path}")
    df = df[needed].drop_duplicates(subset='Item code')

    # Bereken gemiddelde van geldige waarden (zonder NaN)
    valid_lengths = df['BRANDBOX_L'].dropna()
    valid_widths = df['BRANDBOX_W'].dropna()
    avg_l = round(valid_lengths.mean(), 2)
    avg_w = round(valid_widths.mean(), 2)

    # Bouw de dictionary, met default bij ontbrekende waarden
    item_dict = {}
    for _, row in df.iterrows():
        item_code = str(int(row['Item code']))
        l = float(row['BRANDBOX_L']) if pd.notna(row['BRANDBOX_L']) else avg_l
        w = float(row['BRANDBOX_W']) if pd.notna(row['BRANDBOX_W']) else avg_w
        item_dict[item_code] = (round(l, 2), round(w, 2))

    return item_dict


def save_item_dimensions(
    item_dict: dict[str, tuple[float, float]],
    file_path: str
) -> None:
    """
    Slaat de item-dictionary op als JSON-bestand.

    Parameters:
    - item_dict: dict van item_code -> (lengte, breedte)
    - file_path: pad naar output JSON

    De waardes worden opgeslagen als lijsten [lengte, breedte].
    """
    # Zet tuples om naar lijsten voor JSON-serialisatie
    serializable = {code: [dim[0], dim[1]] for code, dim in item_dict.items()}
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def load_saved_item_dimensions(
    file_path: str
) -> dict[str, tuple[float, float]]:
    """
    Laadt item-dictionary vanaf een eerder opgeslagen JSON-bestand.

    Parameters:
    - file_path: pad naar JSON-bestand

    Returns:
    - dict van item_code -> (lengte, breedte)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Bestand niet gevonden: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Zet lijsten terug naar tuples
    return {code: (float(vals[0]), float(vals[1])) for code, vals in data.items()}

# Voorbeeld gebruik:
# from item_utils import load_item_dimensions, save_item_dimensions, load_saved_item_dimensions
dims = load_item_dimensions('Dataverwerking_data_Input/ProductInfo.xlsx')
save_item_dimensions(dims, 'item_dims.json')
loaded = load_saved_item_dimensions('item_dims.json')

def main():
    dims = load_item_dimensions('Dataverwerking_data_Input/ProductInfo.xlsx')
    save_item_dimensions(dims, 'Dataverwerking_data_output/item_dims.json')
    loaded = load_saved_item_dimensions('Dataverwerking_data_output/item_dims.json')
    print(f"✅ {len(loaded)} items geladen uit JSON.")


if __name__ == "__main__":
    main()