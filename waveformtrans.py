import os
import pandas as pd
from tqdm import tqdm

folder_path = r"C:\Users\jrlin\Downloads\help\results\20x50"
out_file = os.path.join(folder_path, "all_processed_rows.csv")
all_rows = []

csv_files = [f for f in os.listdir(folder_path) if f.endswith(".csv")]

for filename in tqdm(csv_files, desc="Processing CSV files"):
    file_path = os.path.join(folder_path, filename)
    
    try:
        # Read only the second column, skip first 19 rows, specify encoding
        data = pd.read_csv(file_path, skiprows=19, usecols=[1], header=None, encoding='latin1')
    except Exception as e:
        print(f"Skipping {filename}: {e}")
        continue
    
    # Flatten column to a list and prepend filename
    row = [filename] + data.iloc[:,0].tolist()
    all_rows.append(row)

# Write all rows to output CSV
pd.DataFrame(all_rows).to_csv(out_file, index=False, header=False, encoding='utf-8')

print("All processed rows saved to all_processed_rows.csv")
