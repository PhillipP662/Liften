import json
import random
from collections import Counter
from pathlib import Path
from rectpack import newPacker, MaxRectsBaf
import pandas as pd

# from Dataverwerking_code.Preprocessing import load_simulation


USE_PRINT = False

def debug_print(*args, **kwargs):
    # use this instead of "print". it automatically checks if USE_PRINT is set or not
    if USE_PRINT:
        print(*args, **kwargs)

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
    Retourneert een lijst van (l, w, code) tuples, één keer per itemcode in de lijst.
    Als een item geen dimensie heeft, gebruik dan gemiddelde dimensies als fallback.
    """
    items = []
    missing = []

    # Bereken gemiddelde lengte en breedte
    lengths = [dims[0] for dims in all_dimensions.values()]
    widths = [dims[1] for dims in all_dimensions.values()]
    avg_l = sum(lengths) / len(lengths)
    avg_w = sum(widths) / len(widths)

    for code in ordered_item_codes:
        if code in all_dimensions:
            l, w = all_dimensions[code]
        else:
            l, w = avg_l, avg_w
            missing.append(code)
        items.append((l, w, code))

    if missing:
        unique_missing = set(missing)
        debug_print(f"⚠️ Waarschuwing: {len(unique_missing)} item(s) hadden geen dimensie. "
                    f"Gemiddelde dimensies gebruikt voor: {unique_missing}")

    return items


#Eerste Algo is een greedy gesorteert
def fill_trays_Greedy(items, tray_length, tray_width, max_trays, allow_rotation=False):
    """
    item_dim_dict: dict van item_id (str of int) -> (l, w)
    """
    packer = newPacker(rotation=allow_rotation)
    padding = 0.02

    # Items toevoegen met echte item_id als rid
    for i, (l, w, code) in enumerate(items):
        padded_l = l + padding
        padded_w = w + padding
        packer.add_rect(padded_l, padded_w, rid=(code, i))  # i makes each item unique

    for _ in range(max_trays):
        packer.add_bin(tray_length, tray_width)

    packer.pack()

    # Geplaatste items per tray verzamelen
    tray_items = {i: [] for i in range(0, max_trays)}
    for rect in packer.rect_list():
        tray_index, x, y, l, w, (code, _) = rect
        tray_items[tray_index].append({
            "item_id": code,
            "item_code": code,
            "x": x,
            "y": y,
            "l": l - padding,
            "w": w - padding
        })

    # Niet-geplaatste items bepalen
    all_ids = set((code, i) for i, (_, _, code) in enumerate(items))
    placed_ids = set(r[5] for r in packer.rect_list())
    not_placed = [code for (code, i) in all_ids - placed_ids]

    return tray_items, not_placed

#Tweede Algo is een greedy niet gesorteerd.
def fill_trays_sequential(item_dim_dict, tray_length, tray_width, max_trays):
    """
    Plaatst items sequentieel in trays zonder sortering.
    Tray indices starten vanaf 1.

    Parameters:
    - item_dim_dict: dict van item_id (str of int) -> (l, w)

    Returns:
    - tray_items: dict van tray_index (1-based) -> geplaatste items (met x, y)
    - not_placed: lijst van niet-geplaatste item-ID's
    """
    tray_items = {i: [] for i in range(1, max_trays + 1)}
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
        step = 0.01
        y = 0.0
        while y + w <= tray_w:
            x = 0.0
            while x + l <= tray_l:
                if fits(x, y, l, w, placed, tray_l, tray_w):
                    return x, y
                x += step
            y += step
        return None

    tray_index = 1
    for item_id, (l_orig, w_orig) in item_dim_dict.items():
        placed = False
        while tray_index <= max_trays:
            for l, w in [(l_orig, w_orig), (w_orig, l_orig)]:
                position = find_position(l, w, tray_items[tray_index], tray_length, tray_width)
                if position:
                    x, y = position
                    tray_items[tray_index].append({
                        "item_id": item_id,
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
                tray_index += 1

        if not placed:
            not_placed.append(item_id)

    return tray_items, not_placed


def fill_trays_random_best_fit(item_dim_dict, tray_length, tray_width, max_trays):
    """
    Plaatst items in trays met random volgorde van items en trays,
    en kiest per tray de best mogelijke plek (laagste y).

    Tray indices starten vanaf 1.
    item_dim_dict: dict van item_id -> (l, w)

    Returns:
    - tray_items: dict van tray_index (1-based) -> geplaatste items met x/y/l/w
    - not_placed: lijst van item-ID's die niet geplaatst konden worden
    """
    tray_items = {i: [] for i in range(1, max_trays + 1)}
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

    # Shuffle items (dictionary → lijst van tuples)
    shuffled_items = list(item_dim_dict.items())
    random.shuffle(shuffled_items)

    for item_id, (orig_l, orig_w) in shuffled_items:
        placed = False
        tray_order = list(range(1, max_trays + 1))
        random.shuffle(tray_order)

        for tray in tray_order:
            for l, w in [(orig_l, orig_w), (orig_w, orig_l)]:  # probeer rotatie
                position = find_best_position(l, w, tray_items[tray], tray_length, tray_width)
                if position:
                    x, y = position
                    tray_items[tray].append({
                        "item_id": item_id,
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
            not_placed.append(item_id)

    return tray_items, not_placed


def fill_trays_by_frequency(ordered_item_codes, all_dimensions, tray_length, tray_width, max_trays):
    """
    Plaatst items met de hoogste frequentie in de laagste trays (1,2,3,...)

    Parameters:
    - ordered_item_codes: lijst van item_codes als strings
    - all_dimensions: dict van item_code (str) -> (l, w)
    - tray_length, tray_width: afmetingen van tray
    - max_trays: aantal trays

    Returns:
    - tray_items: dict van tray_index (1-based) -> geplaatste items
    - not_placed: lijst van item_codes die niet geplaatst konden worden
    """
    tray_items = {i: [] for i in range(1, max_trays + 1)}
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
        debug_print(f"⚠️ {len(missing)} item(s) hebben geen dimensie: {set(missing)}")

    # 3. Sorteer op frequentie (hoog → laag)
    sorted_items = sorted(items_with_dims, key=lambda x: -freq_table[x[0]])

    for code, (l_orig, w_orig) in sorted_items:
        count = freq_table[code]
        for _ in range(count):
            placed = False
            for tray_index in range(1, max_trays + 1):
                for l, w in [(l_orig, w_orig), (w_orig, l_orig)]:
                    pos = find_best_position(l, w, tray_items[tray_index], tray_length, tray_width)
                    if pos:
                        x, y = pos
                        tray_items[tray_index].append({
                            "item_id": code,
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
    debug_print("📦 Tray-inhoud:")
    for tray_index, itemlist in tray_items.items():
        if itemlist:
            debug_print(f"\nTray {tray_index}:")
            for item in itemlist:
                debug_print(f"  - Item {item['item_id']} op ({item['x']:.2f}, {item['y']:.2f}) [{item['l']} x {item['w']}]")

    if not_placed:
        debug_print("\n⚠️ Niet geplaatste items:")
        for rid in not_placed:
            l, w = items[rid]
            debug_print(f"- Item {rid} ({l} x {w})")
    else:
        debug_print("\n✅ Alle items zijn geplaatst.")


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
                debug_print(f"❌ Item {item['item_id']} in Tray {tray_index} is out of bounds.")
                all_valid = False

            for j in range(i + 1, len(items)):
                other = items[j]
                if items_overlap(item, other):
                    debug_print(f"❌ Item {item['item_id']} overlaps with Item {other['item_id']} in Tray {tray_index}.")
                    all_valid = False

    if all_valid:
        debug_print("✅ All trays are valid: no overlaps and all items within bounds.")
    return all_valid

def get_tray_filling():
    debug_print("Start simulatie")
    # Load all onze Simulated bestellingen en Augemented bestellingen en dimensiematrix
    # sim_loaded = load_simulation("Dataverwerking_code/Dataverwerking_data_output/sim_output.csv")
    # augmented_loaded = load_simulation("Dataverwerking_code/Dataverwerking_data_output/augmented_output.csv")
    loaded = load_saved_item_dimensions('Dataverwerking_code/Dataverwerking_data_output/item_dims.json')
    tray_length = 1.0
    tray_width = 1.0
    max_trays = 100

    # dimensions = load_item_dimensions("item_dims.json")
    ordered_codes = load_ordered_items(
        "Dataverwerking_code/Dataverwerking_data_output/augmented_output.csv")  # sim_output.csv of augmented_output.csv

    items = get_ordered_item_dimensions(ordered_codes, loaded)
    debug_print("Greedy sorted: ")
    tray_items, not_placed = fill_trays_Greedy(items, tray_length, tray_width, max_trays)

    debug_print("Trays are filled")

    print_tray_results(tray_items, not_placed, items)
    unused_per_tray, total_unused = calculate_unused_space(tray_items, tray_length, tray_width)
    debug_print("\n📏 Ongebruikte ruimte per tray:")
    for tray_index, unused in unused_per_tray.items():
        debug_print(f"- Tray {tray_index}: {unused:.4f} m² ongebruikt")

    debug_print(f"\n📊 Totale ongebruikte ruimte: {total_unused:.4f} m²")
    debug_print("----------------------------------------------------------------- ")

    VALIDATE = True
    if VALIDATE:
        debug_print("Validating if trays are filled correctly...")
        if not validate_trays(tray_items, tray_length=tray_length, tray_width=tray_width):
            raise Exception("Trays were not filled properly...")

    return tray_items

def get_tray_filling_from_data(augmented_data, mode,tray_length, tray_width, max_trays ):
    loaded = load_saved_item_dimensions('Dataverwerking_code/Dataverwerking_data_output/item_dims.json')
    ordered_codes = [str(code) for codes in augmented_data.values() for code in codes]
    items = get_ordered_item_dimensions(ordered_codes, loaded)

    if mode == 1:
        tray_items, not_placed = fill_trays_Greedy(items, tray_length, tray_width, max_trays)
    elif mode == 2:
        tray_items, not_placed = fill_trays_sequential(items, tray_length, tray_width, max_trays)
    elif mode == 3:
        tray_items, not_placed = fill_trays_random_best_fit(items, tray_length, tray_width, max_trays)
    elif mode == 4:
        tray_items, not_placed = fill_trays_by_frequency(items, tray_length, tray_width, max_trays)
    else:
        tray_items, not_placed = fill_trays_Greedy(items, tray_length, tray_width, max_trays)

    return tray_items

def main():
    get_tray_filling()


if __name__ == "__main__":
    main()


