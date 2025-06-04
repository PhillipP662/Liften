import pandas as pd




def load_simulation(filename):
    # lees CSV en groepeer terug naar dict {date: [item_codes]}
    df = pd.read_csv(filename, parse_dates=["date"])
    return df.groupby("date")["item_code"].apply(list).to_dict()


if __name__ == "__main__":
    sim_loaded = load_simulation("sim_output.csv")
    augmented_loaded = load_simulation("augmented_output.csv")