import pandas as pd
import Tray_filling
import VerdelingBestellingen
import Product_Gewichtmatric

def load_simulation(filename):
    # lees CSV en groepeer terug naar dict {date: [item_codes]}
    df = pd.read_csv(filename, parse_dates=["date"])
    return df.groupby("date")["item_code"].apply(list).to_dict()


if __name__ == "__main__":
    Product_Gewichtmatric.main()
    VerdelingBestellingen.main()
    Tray_filling.main()
