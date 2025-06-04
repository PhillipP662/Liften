import json
import random
from collections import Counter
from pathlib import Path
from rectpack import newPacker
import pandas as pd


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
        print(f"⚠️ Waarschuwing: {len(missing)} item(s) hebben geen dimensie: {set(missing)}")
    return items




#Eerste Algo is een greedy gesorteert
def fill_trays_Greedy(items, tray_width, tray_height, max_trays, allow_rotation=True):
    """
    Plaatst items in trays met beperkte capaciteit.

    Parameters:
    - items: lijst van tuples (breedte, hoogte)
    - tray_width: breedte van een tray
    - tray_height: hoogte van een tray
    - max_trays: maximaal aantal trays
    - allow_rotation: of items 90° gedraaid mogen worden

    Returns:
    - tray_items: dict van tray_index -> lijst van geplaatste items
    - not_placed: lijst van niet-geplaatste item-ID's
    """
    packer = newPacker(rotation=allow_rotation)

    # Items toevoegen met ID
    for idx, (w, h) in enumerate(items):
        packer.add_rect(w, h, rid=idx)

    # Trays toevoegen
    for _ in range(max_trays):
        packer.add_bin(tray_width, tray_height)

    # Packing uitvoeren
    packer.pack()

    # Geplaatste items per tray verzamelen
    tray_items = {i: [] for i in range(max_trays)}
    for rect in packer.rect_list():
        tray_index, x, y, w, h, rid = rect
        tray_items[tray_index].append({
            "item_id": rid,
            "x": x,
            "y": y,
            "w": w,
            "h": h
        })

    # Niet-geplaatste items bepalen
    placed_ids = set(r[5] for r in packer.rect_list())
    all_ids = set(range(len(items)))
    not_placed = list(all_ids - placed_ids)

    return tray_items, not_placed

#Tweede Algo is een greedy niet gesorteerd.
def fill_trays_sequential(items, tray_width, tray_height, max_trays):
    """
    Plaatst items sequentieel in trays zonder sortering.
    Elk item wordt geplaatst op de eerstvolgende plek waar het zonder overlap past.

    Parameters:
    - items: lijst van (breedte, hoogte)
    - tray_width, tray_height: afmetingen van de tray
    - max_trays: maximum aantal trays

    Returns:
    - tray_items: dict van tray_index -> geplaatste items (met x, y)
    - not_placed: lijst van niet-geplaatste item-ID's
    """
    tray_items = {i: [] for i in range(max_trays)}
    not_placed = []

    def fits(x, y, w, h, placed, tray_w, tray_h):
        if x + w > tray_w or y + h > tray_h:
            return False
        for item in placed:
            if not (x + w <= item['x'] or
                    item['x'] + item['w'] <= x or
                    y + h <= item['y'] or
                    item['y'] + item['h'] <= y):
                return False  # overlap
        return True

    def find_position(w, h, placed, tray_w, tray_h):
        step = 0.01  # resolutie van de scan (kleiner = trager, maar preciezer)
        y = 0.0
        while y + h <= tray_h:
            x = 0.0
            while x + w <= tray_w:
                if fits(x, y, w, h, placed, tray_w, tray_h):
                    return x, y
                x += step
            y += step
        return None

    current_tray = 0
    for idx, (w_orig, h_orig) in enumerate(items):
        placed = False
        while current_tray < max_trays:
            # Probeer zowel (w,h) als (h,w)
            for w, h in [(w_orig, h_orig), (h_orig, w_orig)]:
                position = find_position(w, h, tray_items[current_tray], tray_width, tray_height)
                if position:
                    x, y = position
                    tray_items[current_tray].append({
                        "item_id": idx,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h
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

def fill_trays_random_best_fit(items, tray_width, tray_height, max_trays):
    """
    Plaatst items in trays met random volgorde van items en trays,
    en kiest per tray de best mogelijke plek (laagste y).

    Parameters:
    - items: lijst van (w, h)
    - tray_width, tray_height: afmetingen van de tray
    - max_trays: maximaal aantal trays

    Returns:
    - tray_items: dict van tray_index -> geplaatste items met x/y/w/h
    - not_placed: lijst van item-ID's die niet geplaatst konden worden
    """
    tray_items = {i: [] for i in range(max_trays)}
    not_placed = []

    def fits(x, y, w, h, placed, tray_w, tray_h):
        if x + w > tray_w or y + h > tray_h:
            return False
        for item in placed:
            if not (x + w <= item['x'] or
                    item['x'] + item['w'] <= x or
                    y + h <= item['y'] or
                    item['y'] + item['h'] <= y):
                return False
        return True

    def find_best_position(w, h, placed, tray_w, tray_h):
        step = 0.01
        best = None
        best_y = tray_h + 1
        y = 0.0
        while y + h <= tray_h:
            x = 0.0
            while x + w <= tray_w:
                if fits(x, y, w, h, placed, tray_w, tray_h):
                    if y < best_y:
                        best = (x, y)
                        best_y = y
                x += step
            y += step
        return best

    # Shuffle items
    indexed_items = list(enumerate(items))
    random.shuffle(indexed_items)

    for idx, (orig_w, orig_h) in indexed_items:
        placed = False
        tray_order = list(range(max_trays))
        random.shuffle(tray_order)

        for tray in tray_order:
            for w, h in [(orig_w, orig_h), (orig_h, orig_w)]:  # probeer rotatie
                position = find_best_position(w, h, tray_items[tray], tray_width, tray_height)
                if position:
                    x, y = position
                    tray_items[tray].append({
                        "item_id": idx,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h
                    })
                    placed = True
                    break
            if placed:
                break

        if not placed:
            not_placed.append(idx)

    return tray_items, not_placed


def fill_trays_by_frequency(ordered_item_codes, all_dimensions, tray_width, tray_height, max_trays):
    """
    Plaatst items met de hoogste frequentie in de laagste trays (0,1,2,...)

    Parameters:
    - ordered_item_codes: lijst van item_codes als strings
    - all_dimensions: dict van item_code (str) -> (w, h)
    - tray_width, tray_height: afmetingen van tray
    - max_trays: aantal trays

    Returns:
    - tray_items: dict van tray_index -> geplaatste items
    - not_placed: lijst van item_codes die niet geplaatst konden worden
    """
    tray_items = {i: [] for i in range(max_trays)}
    not_placed = []

    def fits(x, y, w, h, placed, tray_w, tray_h):
        if x + w > tray_w or y + h > tray_h:
            return False
        for item in placed:
            if not (x + w <= item['x'] or
                    item['x'] + item['w'] <= x or
                    y + h <= item['y'] or
                    item['y'] + item['h'] <= y):
                return False
        return True

    def find_best_position(w, h, placed, tray_w, tray_h):
        step = 0.05
        best = None
        best_y = tray_h + 1
        y = 0.0
        while y + h <= tray_h:
            x = 0.0
            while x + w <= tray_w:
                if fits(x, y, w, h, placed, tray_w, tray_h):
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

    for code, (w_orig, h_orig) in sorted_items:
        count = freq_table[code]
        for _ in range(count):  # plaats meerdere keren per frequentie
            placed = False
            for tray in range(max_trays):
                for w, h in [(w_orig, h_orig), (h_orig, w_orig)]:
                    pos = find_best_position(w, h, tray_items[tray], tray_width, tray_height)
                    if pos:
                        x, y = pos
                        tray_items[tray].append({
                            "item_id": item_id_counter,
                            "item_code": code,
                            "x": x,
                            "y": y,
                            "w": w,
                            "h": h
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
    - items: originele lijst van (w, h) tuples
    """
    print("📦 Tray-inhoud:")
    for tray_index, itemlist in tray_items.items():
        if itemlist:
            print(f"\nTray {tray_index + 1}:")
            for item in itemlist:
                print(f"  - Item {item['item_id']} op ({item['x']:.2f}, {item['y']:.2f}) [{item['w']} x {item['h']}]")

    if not_placed:
        print("\n⚠️ Niet geplaatste items:")
        for rid in not_placed:
            w, h = items[rid]
            print(f"- Item {rid} ({w} x {h})")
    else:
        print("\n✅ Alle items zijn geplaatst.")


def calculate_unused_space(tray_items, tray_width, tray_height):
    """
    Berekent de ongebruikte ruimte (in m²) per tray en in totaal.

    Parameters:
    - tray_items: dict van tray_index -> geplaatste items
    - tray_width, tray_height: afmetingen van de tray

    Returns:
    - per_tray_unused: dict van tray_index -> ongebruikte ruimte (m²)
    - total_unused: som van alle ongebruikte ruimte
    """
    tray_area = tray_width * tray_height
    per_tray_unused = {}
    total_unused = 0.0

    for tray_index, items in tray_items.items():
        used_area = sum(item["w"] * item["h"] for item in items)
        unused = tray_area - used_area
        per_tray_unused[tray_index] = unused
        total_unused += unused

    return per_tray_unused, total_unused

if __name__ == "__main__":
    # Load all onze Simulated bestellingen en Augemented bestellingen en dimensiematrix
    # sim_loaded = load_simulation("sim_output.csv")
    # augmented_loaded = load_simulation("augmented_output.csv")
    # loaded = load_saved_item_dimensions('item_dims.json')
    tray_width = 1.0
    tray_height = 1.2
    max_trays = 100

    #dimensions = load_item_dimensions("item_dims.json")
    #ordered_codes = load_ordered_items("sim_output.csv")  # of augmented_output.csv

    ordered_item_codes = [
        "A", "B", "A", "C", "B", "A", "D", "E", "F", "G", "B", "C", "H", "I", "J", "A", "B", "C"
    ]
    all_dimensions = {
        "A": (0.4, 0.3),  # komt vaak voor
        "B": (0.3, 0.3),
        "C": (0.5, 0.2),
        "D": (0.6, 0.6),
        "E": (0.2, 0.2),
        "F": (0.7, 0.4),
        "G": (0.5, 0.5),
        "H": (0.3, 0.6),
        "I": (0.4, 0.4),
        "J": (0.6, 0.2)
    }
    items = get_ordered_item_dimensions(ordered_item_codes, all_dimensions)
    #print("Greedy sorted: ")
    #tray_items, not_placed = fill_trays_Greedy(items, tray_width, tray_height, max_trays)
    #print("Greedy not Sorted: ")
    #tray_items, not_placed = fill_trays_sequential(items, tray_width, tray_height, max_trays)
    #print("RandomItem&Tray_Bestfit: ")
    #tray_items, not_placed = fill_trays_random_best_fit(items, tray_width, tray_height, max_trays)
    print("Frequenty greedy")
    tray_items, not_placed = fill_trays_by_frequency(ordered_item_codes, all_dimensions, tray_width, tray_height, max_trays)

    print_tray_results(tray_items, not_placed, items)
    unused_per_tray, total_unused = calculate_unused_space(tray_items, tray_width, tray_height)
    print("\n📏 Ongebruikte ruimte per tray:")
    for tray_index, unused in unused_per_tray.items():
        print(f"- Tray {tray_index + 1}: {unused:.4f} m² ongebruikt")

    print(f"\n📊 Totale ongebruikte ruimte: {total_unused:.4f} m²")
    print("----------------------------------------------------------------- ")

