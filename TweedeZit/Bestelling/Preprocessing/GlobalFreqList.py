import pandas as pd
from pathlib import Path
import json
from collections import defaultdict

def compute_global_item_quantities(file_paths: list[str], sheet_name: str = 'BestellingDensity', output_path: str = 'Globale_Itemcode_frequentie.json') -> None:
    """
    Leest Excel-bestanden in en telt totale Inventory Qty per itemcode over alle bestanden heen.
    Schrijft resultaat naar een JSON-bestand.
    """
    total_qty_per_item = defaultdict(float)

    for path_str in file_paths:
        path = Path(path_str)
        df = pd.read_excel(path, sheet_name=sheet_name)
        df.rename(columns=lambda c: c.strip(), inplace=True)

        if 'Item code' not in df.columns or 'Inventory Qty' not in df.columns:
            print(f"⚠️  Kolommen ontbreken in bestand: {path.name}")
            continue

        for _, row in df.iterrows():
            item_code = str(row['Item code']).strip()
            qty = row['Inventory Qty']
            if pd.notna(qty):  # Vermijd NaN
                total_qty_per_item[item_code] += qty

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(total_qty_per_item, f, indent=2, ensure_ascii=False)

    print(f"✅ JSON-bestand geschreven naar: {output_path}")

if __name__ == "__main__":
    file_list = [
        '../../Data/Input/1_VerdelingItem01_03.xlsx',
        '../../Data/Input/2_VerdelingItem04_06.xlsx',
        '../../Data/Input/3_VerdelingItem07_09.xlsx',
        '../../Data/Input/4_VerdelingItem10_12.xlsx',
        '../../Data/Input/5_VerdelingItem13_15.xlsx',
        '../../Data/Input/6_VerdelingItem16_19.xlsx',
    ]
    compute_global_item_quantities(file_list)
