import pandas as pd

def process_data(df):
    df = df.copy()

    # Ensure timestamp is sorted properly
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

    # ✅ Add your custom calculations here

    # Example: Calculate change in weight
    if "weight" in df.columns:
        df["delta_weight"] = df["weight"].diff()

    # Example: Detect pump ON transitions
    if "pump_status" in df.columns:
        df["pump_activated"] = (df["pump_status"].shift(1) == 0) & (df["pump_status"] == 1)

    # Example: Efficiency (custom logic placeholder)
    if "power" in df.columns and "temperature" in df.columns:
        df["efficiency"] = df["power"] / (df["temperature"] + 273.15)

    return df

