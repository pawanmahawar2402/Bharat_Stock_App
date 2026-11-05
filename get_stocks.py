
import pandas as pd
import csv
import os

def fetch_nse_stocks():
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        df = pd.read_csv(url)
        with open("data/all_stocks.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Company Name", "Symbol"])
            for _, row in df.iterrows():
                writer.writerow([row["NAME OF COMPANY"], row["SYMBOL"] + ".NS"])
        print("Successfully fetched NSE stocks.")
    except Exception as e:
        print("Error fetching NSE:", e)

os.makedirs("data", exist_ok=True)
fetch_nse_stocks()

