import pandas as pd

def process_data(df):
    df = df.copy()

    # Sort and ensure timestamp format
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

    # ✅ Rename fields for clarity
    df.rename(columns={
        "velocity": "intake_air_velocity (m/s)",
        "temperature": "intake_air_temperature (C)",
        "humidity": "intake_air_humidity (%)",
        "env_velocity": "outtake_air_velocity (m/s)",
        "env_temperature": "outtake_air_temperature (C)",
        "env_humidity": "outtake_air_humidity (%)"
    }, inplace=True)

    # 🧪 Placeholder columns for later calculations
    df["harvesting_efficiency"] = None
    df["water_production"] = None
    df["absolute_intake_air_humidity"] = None
    df["absolute_outtake_air_humidity"] = None

    return df
