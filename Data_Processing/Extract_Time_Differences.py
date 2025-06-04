import pandas as pd
import numpy as np
import scipy.stats as stats
import os
import pickle

def calculate_time_differences(df, timestamp_col='Creation Dt', max_seconds=1000):
    df[timestamp_col] = pd.to_datetime(df[timestamp_col]).dt.floor('s')
    df = df.loc[~df[timestamp_col].duplicated(keep='first')].reset_index(drop=True)

    second_differences = []

    for i in range(1, len(df)):
        current = df.loc[i, timestamp_col]
        previous = df.loc[i - 1, timestamp_col]

        if current.date() == previous.date():
            delta = int((current - previous).total_seconds())
            if delta >= 1 and delta <= max_seconds:
                second_differences.append(delta)

    return second_differences

def main():
    input_file = '../Data/Input/Pick_Orders_20250101-03.xlsx'
    output_file = '../Data/Output/time_differences.pkl'

    df = pd.read_excel(input_file)

    # Check necessary columns
    if 'Creation Dt' not in df.columns or 'Location code' not in df.columns:
        print("Required columns missing in the data.")
        return

    grouped = df.groupby('Location code')
    all_differences = {}

    for location_code, group_df in grouped:
        if len(group_df) < 1000:
            continue

        print(f"Processing '{location_code}' with {len(group_df)} rows...")

        diffs = calculate_time_differences(group_df, timestamp_col='Creation Dt')
        if diffs:
            all_differences[location_code] = diffs

    # Save to Pickle
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'wb') as f:
        pickle.dump(all_differences, f)

    print(f"\n✅ Saved time differences for {len(all_differences)} locations to: {output_file}")

if __name__ == "__main__":
    main()
