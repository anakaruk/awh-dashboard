import pandas as pd
import math

def calculate_absolute_humidity(temp_c, rel_humidity):
    """
    Calculate absolute humidity (g/m³) from temperature (°C) and relative humidity (%)
    """
    exponent = (17.67 * temp_c) / (temp_c + 243.5)
    saturation_vapor_pressure = 6.112 * math.exp(exponent)
    vapor_pressure = rel_humidity / 100 * saturation_vapor_pressure
    abs_humidity = (vapor_pressure * 2.1674) / (273.15 + temp_c)
    return abs_humidity

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

    # Calculate absolute humidity
    df["absolute_intake_air_humidity"] = df.apply(
        lambda row: round(calculate_absolute_humidity(row["intake_air_temperature (C)"], row["intake_air_humidity (%)"]), 2)
        if pd.notnull(row["intake_air_temperature (C)"]) and pd.notnull(row["intake_air_humidity (%)"])
        else None,
        axis=1
    )

    df["absolute_outtake_air_humidity"] = df.apply(
        lambda row: round(calculate_absolute_humidity(row["outtake_air_temperature (C)"], row["outtake_air_humidity (%)"]), 2)
        if pd.notnull(row["outtake_air_temperature (C)"]) and pd.notnull(row["outtake_air_humidity (%)"])
        else None,
        axis=1
    )

    # 🧪 Placeholder columns for later calculations
    df["harvesting_efficiency"] = None
    df["water_production"] = None

    return df
