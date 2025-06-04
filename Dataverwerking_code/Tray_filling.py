import json
import random
from collections import Counter
from pathlib import Path
from rectpack import newPacker, MaxRectsBaf
import pandas as pd

from Dataverwerking_code.Preprocessing import load_simulation


def load_simulation(filename):
    # lees CSV en groepeer terug naar dict {date: [item_codes]}
    df = pd.read_csv(filename, parse_dates=["date"])
    return df.groupby("date")["item_code"].apply(list).to_dict()

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

def load_item_dimensions(file_path):
    """
    Laadt afmetingen van items uit JSON en zet sleutels om naar str(int)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    return {str(int(float(k))): (float(v[0]), float(v[1])) for k, v in raw_data.items()}


def load_ordered_items(filename):
    # lees CSV en groepeer terug naar dict {date: [item_codes]}
    df = pd.read_csv(filename, parse_dates=["date"])
    return df["item_code"].astype(str).tolist()

def get_ordered_item_dimensions(ordered_item_codes, all_dimensions):
    """
    Filtert de dimensies van alleen de bestelde items (enkel als ze bestaan in de dimensiematrix).
    Verwacht dat alle item_codes strings van integers zijn, bv. '13974'
    """
    items = []
    missing = []
    for code in ordered_item_codes:
        if code in all_dimensions:
            items.append(all_dimensions[code])
        else:
            missing.append(code)
    if missing:
        unique_missing = set(missing)
        print(f"⚠️ Waarschuwing: {len(unique_missing)} item(s) hebben geen dimensie: {unique_missing}")
    return items


#Eerste Algo is een greedy gesorteert
def fill_trays_Greedy(items, tray_length, tray_width, max_trays, allow_rotation=True):
    """
    Plaatst items in trays met beperkte capaciteit.

    Parameters:
    - items: lijst van tuples (lengte, breedte)
    - tray_length: lengte van een tray
    - tray_width: breedte van een tray
    - max_trays: maximaal aantal trays
    - allow_rotation: of items 90° gedraaid mogen worden

    Returns:
    - tray_items: dict van tray_index -> lijst van geplaatste items
    - not_placed: lijst van niet-geplaatste item-ID's
    """
    packer = newPacker(rotation=allow_rotation)
    # Use padding on the right and top of an item to leave some space between items
    # Padding is removed after finishing the bin packing
    # padding = 0.02  # Tight packing
    padding = 0.02  # To grab box

    # Items toevoegen met ID
    for idx, (l, w) in enumerate(items):
        padded_l = l + padding
        padded_w = w + padding
        packer.add_rect(padded_l, padded_w, rid=idx)

    # Trays toevoegen
    for _ in range(max_trays):
        packer.add_bin(tray_length, tray_width)

    # Packing uitvoeren
    packer.pack()

    # Geplaatste items per tray verzamelen
    tray_items = {i: [] for i in range(max_trays)}
    for rect in packer.rect_list():
        tray_index, x, y, l, w, rid = rect
        tray_items[tray_index].append({
            "item_id": rid,
            "x": x,
            "y": y,
            "l": l - padding,   # get original size, which results in gaps between items (which we want)
            "w": w - padding
        })

    # Niet-geplaatste items bepalen
    placed_ids = set(r[5] for r in packer.rect_list())
    all_ids = set(range(len(items)))
    not_placed = list(all_ids - placed_ids)

    return tray_items, not_placed

#Tweede Algo is een greedy niet gesorteerd.
def fill_trays_sequential(items, tray_length, tray_width, max_trays):
    """
    Plaatst items sequentieel in trays zonder sortering.
    Elk item wordt geplaatst op de eerstvolgende plek waar het zonder overlap past.

    Parameters:
    - items: lijst van (lengte, breedte)
    - tray_length, tray_width: afmetingen van de tray
    - max_trays: maximum aantal trays

    Returns:
    - tray_items: dict van tray_index -> geplaatste items (met x, y)
    - not_placed: lijst van niet-geplaatste item-ID's
    """
    tray_items = {i: [] for i in range(max_trays)}
    not_placed = []

    def fits(x, y, l, w, placed, tray_l, tray_w):
        if x + l > tray_l or y + w > tray_w:
            return False
        for item in placed:
            if not (x + l <= item['x'] or
                    item['x'] + item['l'] <= x or
                    y + w <= item['y'] or
                    item['y'] + item['w'] <= y):
                return False  # overlap
        return True

    def find_position(l, w, placed, tray_l, tray_w):
        step = 0.01  # resolutie van de scan (kleiner = trager, maar preciezer)
        y = 0.0
        while y + w <= tray_w:
            x = 0.0
            while x + l <= tray_l:
                if fits(x, y, l, w, placed, tray_l, tray_w):
                    return x, y
                x += step
            y += step
        return None

    current_tray = 0
    for idx, (l_orig, w_orig) in enumerate(items):
        placed = False
        while current_tray < max_trays:
            # Probeer zowel (l,w) als (w,l)
            for l, w in [(l_orig, w_orig), (w_orig, l_orig)]:
                position = find_position(l, w, tray_items[current_tray], tray_length, tray_width)
                if position:
                    x, y = position
                    tray_items[current_tray].append({
                        "item_id": idx,
                        "x": x,
                        "y": y,
                        "l": l,
                        "w": w
                    })
                    placed = True
                    break
            if placed:
                break
            else:
                current_tray += 1

        if not placed:
            not_placed.append(idx)

    return tray_items, not_placed

def fill_trays_random_best_fit(items, tray_length, tray_width, max_trays):
    """
    Plaatst items in trays met random volgorde van items en trays,
    en kiest per tray de best mogelijke plek (laagste y).

    Parameters:
    - items: lijst van (l, w)
    - tray_length, tray_width: afmetingen van de tray
    - max_trays: maximaal aantal trays

    Returns:
    - tray_items: dict van tray_index -> geplaatste items met x/y/l/w
    - not_placed: lijst van item-ID's die niet geplaatst konden worden
    """
    tray_items = {i: [] for i in range(max_trays)}
    not_placed = []

    def fits(x, y, l, w, placed, tray_l, tray_w):
        if x + l > tray_l or y + w > tray_w:
            return False
        for item in placed:
            if not (x + l <= item['x'] or
                    item['x'] + item['l'] <= x or
                    y + w <= item['y'] or
                    item['y'] + item['w'] <= y):
                return False
        return True

    def find_best_position(l, w, placed, tray_l, tray_w):
        step = 0.01
        best = None
        best_y = tray_w + 1
        y = 0.0
        while y + w <= tray_w:
            x = 0.0
            while x + l <= tray_l:
                if fits(x, y, l, w, placed, tray_l, tray_w):
                    if y < best_y:
                        best = (x, y)
                        best_y = y
                x += step
            y += step
        return best

    # Shuffle items
    indexed_items = list(enumerate(items))
    random.shuffle(indexed_items)

    for idx, (orig_l, orig_w) in indexed_items:
        placed = False
        tray_order = list(range(max_trays))
        random.shuffle(tray_order)

        for tray in tray_order:
            for l, w in [(orig_l, orig_w), (orig_w, orig_l)]:  # probeer rotatie
                position = find_best_position(l, w, tray_items[tray], tray_length, tray_width)
                if position:
                    x, y = position
                    tray_items[tray].append({
                        "item_id": idx,
                        "x": x,
                        "y": y,
                        "l": l,
                        "w": w
                    })
                    placed = True
                    break
            if placed:
                break

        if not placed:
            not_placed.append(idx)

    return tray_items, not_placed


def fill_trays_by_frequency(ordered_item_codes, all_dimensions, tray_length, tray_width, max_trays):
    """
    Plaatst items met de hoogste frequentie in de laagste trays (0,1,2,...)

    Parameters:
    - ordered_item_codes: lijst van item_codes als strings
    - all_dimensions: dict van item_code (str) -> (l, w)
    - tray_length, tray_width: afmetingen van tray
    - max_trays: aantal trays

    Returns:
    - tray_items: dict van tray_index -> geplaatste items
    - not_placed: lijst van item_codes die niet geplaatst konden worden
    """
    tray_items = {i: [] for i in range(max_trays)}
    not_placed = []

    def fits(x, y, l, w, placed, tray_l, tray_w):
        if x + l > tray_l or y + w > tray_w:
            return False
        for item in placed:
            if not (x + l <= item['x'] or
                    item['x'] + item['l'] <= x or
                    y + w <= item['y'] or
                    item['y'] + item['w'] <= y):
                return False
        return True

    def find_best_position(l, w, placed, tray_l, tray_w):
        step = 0.01
        best = None
        best_y = tray_w + 1
        y = 0.0
        while y + w <= tray_w:
            x = 0.0
            while x + l <= tray_l:
                if fits(x, y, l, w, placed, tray_l, tray_w):
                    if y < best_y:
                        best = (x, y)
                        best_y = y
                x += step
            y += step
        return best

    # 1. Frequentietabel maken
    freq_table = Counter(ordered_item_codes)

    # 2. Filter op items met dimensies
    items_with_dims = [(code, all_dimensions[code]) for code in freq_table if code in all_dimensions]
    missing = [code for code in freq_table if code not in all_dimensions]
    if missing:
        print(f"⚠️ {len(missing)} item(s) hebben geen dimensie: {set(missing)}")

    # 3. Sorteer op frequentie (hoog → laag)
    sorted_items = sorted(items_with_dims, key=lambda x: -freq_table[x[0]])

    item_id_counter = 0

    for code, (l_orig, w_orig) in sorted_items:
        count = freq_table[code]
        for _ in range(count):  # plaats meerdere keren per frequentie
            placed = False
            for tray in range(max_trays):
                for l, w in [(l_orig, w_orig), (w_orig, l_orig)]:
                    pos = find_best_position(l, w, tray_items[tray], tray_length, tray_width)
                    if pos:
                        x, y = pos
                        tray_items[tray].append({
                            "item_id": item_id_counter,
                            "item_code": code,
                            "x": x,
                            "y": y,
                            "l": l,
                            "w": w
                        })
                        item_id_counter += 1
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                not_placed.append(code)

    return tray_items, not_placed


# Funtional funtions
def print_tray_results(tray_items, not_placed, items):
    """
    Print een overzicht van de trays en de niet-geplaatste items.

    Parameters:
    - tray_items: dict van tray_index -> geplaatste items
    - not_placed: lijst van item-ID's die niet pasten
    - items: originele lijst van (l, w) tuples
    """
    print("📦 Tray-inhoud:")
    for tray_index, itemlist in tray_items.items():
        if itemlist:
            print(f"\nTray {tray_index + 1}:")
            for item in itemlist:
                print(f"  - Item {item['item_id']} op ({item['x']:.2f}, {item['y']:.2f}) [{item['l']} x {item['w']}]")

    if not_placed:
        print("\n⚠️ Niet geplaatste items:")
        for rid in not_placed:
            l, w = items[rid]
            print(f"- Item {rid} ({l} x {w})")
    else:
        print("\n✅ Alle items zijn geplaatst.")


def calculate_unused_space(tray_items, tray_length, tray_width):
    """
    Berekent de ongebruikte ruimte (in m²) per tray en in totaal.

    Parameters:
    - tray_items: dict van tray_index -> geplaatste items
    - tray_length, tray_width: afmetingen van de tray

    Returns:
    - per_tray_unused: dict van tray_index -> ongebruikte ruimte (m²)
    - total_unused: som van alle ongebruikte ruimte
    """
    tray_area = tray_length * tray_width
    per_tray_unused = {}
    total_unused = 0.0

    for tray_index, items in tray_items.items():
        used_area = sum(item["l"] * item["w"] for item in items)
        unused = tray_area - used_area
        per_tray_unused[tray_index] = unused
        total_unused += unused

    return per_tray_unused, total_unused

def validate_trays(tray_items, tray_length=1.0, tray_width=1.0):
    def is_out_of_bounds(item):
        return (
            item['x'] + item['l'] > tray_length or
            item['y'] + item['w'] > tray_width
        )

    def items_overlap(a, b):
        return not (
            a['x'] + a['l'] <= b['x'] or
            b['x'] + b['l'] <= a['x'] or
            a['y'] + a['w'] <= b['y'] or
            b['y'] + b['w'] <= a['y']
        )

    all_valid = True

    for tray_index, items in tray_items.items():
        for i, item in enumerate(items):
            if is_out_of_bounds(item):
                print(f"❌ Item {item['item_id']} in Tray {tray_index} is out of bounds.")
                all_valid = False

            for j in range(i + 1, len(items)):
                other = items[j]
                if items_overlap(item, other):
                    print(f"❌ Item {item['item_id']} overlaps with Item {other['item_id']} in Tray {tray_index}.")
                    all_valid = False

    if all_valid:
        print("✅ All trays are valid: no overlaps and all items within bounds.")
    return all_valid


def main():
    print("Start simulatie")
    # Load all onze Simulated bestellingen en Augemented bestellingen en dimensiematrix
    sim_loaded = load_simulation("Dataverwerking_data_output/sim_output.csv")
    augmented_loaded = load_simulation("Dataverwerking_data_output/augmented_output.csv")
    loaded = load_saved_item_dimensions('Dataverwerking_data_output/item_dims.json')
    tray_length = 1.0
    tray_width = 1.0
    max_trays = 100

    # dimensions = load_item_dimensions("item_dims.json")
    ordered_codes = load_ordered_items("Dataverwerking_data_output/augmented_output.csv")  # sim_output.csv of augmented_output.csv

    # ordered_item_codes = [
    #     "A", "B", "A", "C", "B", "A", "D", "E", "F", "G", "B", "C", "H", "I", "J", "A", "B", "C"
    # ]
    # all_dimensions = {
    #     "A": (0.4, 0.3),  # komt vaak voor
    #     "B": (0.3, 0.3),
    #     "C": (0.5, 0.2),
    #     "D": (0.6, 0.6),
    #     "E": (0.2, 0.2),
    #     "F": (0.7, 0.4),
    #     "G": (0.5, 0.5),
    #     "H": (0.3, 0.6),
    #     "I": (0.4, 0.4),
    #     "J": (0.6, 0.2)
    # }

    items = get_ordered_item_dimensions(ordered_codes, loaded)
    print("Greedy sorted: ")
    tray_items, not_placed = fill_trays_Greedy(items, tray_length, tray_width, max_trays)
    # print("Greedy not Sorted: ")
    # tray_items, not_placed = fill_trays_sequential(items, tray_length, tray_width, max_trays)
    # print("RandomItem&Tray_Bestfit: ")
    # tray_items, not_placed = fill_trays_random_best_fit(items, tray_length, tray_width, max_trays)
    # print("Frequenty greedy")
    # tray_items, not_placed = fill_trays_by_frequency(ordered_codes, loaded, tray_length, tray_width,max_trays)

    print("Trays are filled")

    print_tray_results(tray_items, not_placed, items)
    unused_per_tray, total_unused = calculate_unused_space(tray_items, tray_length, tray_width)
    print("\n📏 Ongebruikte ruimte per tray:")
    for tray_index, unused in unused_per_tray.items():
        print(f"- Tray {tray_index + 1}: {unused:.4f} m² ongebruikt")

    print(f"\n📊 Totale ongebruikte ruimte: {total_unused:.4f} m²")
    print("----------------------------------------------------------------- ")

    VALIDATE = True
    if VALIDATE:
        print("Validating if trays are filled correctly...")
        if not validate_trays(tray_items, tray_length=tray_length, tray_width=tray_width):
            raise Exception("Trays were not filled properly...")


if __name__ == "__main__":
    main()


